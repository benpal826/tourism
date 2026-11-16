"""급증 키워드 계산 (F14). DB 를 읽지 않는 순수 함수.

'평소보다 특이하게 늘어난 단어'만 보여주는 것이 목적이다.
  - 제목에서 조사를 떼고 일반어(config.GENERIC_TERMS)를 뺀다.
  - 단어 하나뿐 아니라 이웃한 두 단어('탄소국경조정제도 유예')도 후보로 쓴다.
  - 최근 기간의 문서 빈도를 평소(기준 기간)의 문서 빈도와 비교해, 평소 기대치보다 많이 늘어난 것만 남긴다.
"""
import re
from collections import Counter

import config
from . import linking

# 단어 또는 구두점. 한 글자 단어('및', '등')와 구두점(쉼표·가운뎃점·괄호 등)도 잡아서, 그 앞뒤 단어가 한 묶음으로 이어지지 않게 한다
_WORD = re.compile(r"[가-힣]+|[A-Za-z][A-Za-z\-]+|[,;:·ㆍ/|…()\[\]「」『』“”‘’\"'!?]")


def _known() -> set[str]:
    """이미 알고 있는 일반어·상투어·불용어. 짧은 단어는 이 목록에 있는 어간일 때만 조사를 뗀다."""
    return ({s.lower() for s in config.GENERIC_TERMS} | {s.lower() for s in config.BOILERPLATE_TERMS}
            | {s.lower() for s in config.STOPWORDS})


def _norm(word: str) -> str:
    """소문자화하고 한국어 단어 끝의 조사를 뗀다 ('대응을' → '대응', '기후변화와' → '기후변화').
    '전문가' 의 '가' 처럼 명사의 끝글자를 조사로 오해하지 않도록, 어간이 3글자 이상이거나 알려진 단어일 때만 뗀다."""
    w = word.lower().strip("-")
    if w.isascii() or len(w) <= 2:
        return w
    m = linking._JOSA.search(w)
    if not m:
        return w
    stem = w[: m.start()]
    return stem if len(stem) >= 3 or stem in _known() else w


def _stop() -> set[str]:
    return {s.lower() for s in config.STOPWORDS}


def _generic() -> set[str]:
    return {_norm(g) for g in config.GENERIC_TERMS}


def _boilerplate() -> set[str]:
    return {_norm(g) for g in config.BOILERPLATE_TERMS}


def words(title: str) -> list[str | None]:
    """제목의 정규화된 단어를 순서대로. 불용어·한 글자·구두점은 None 으로 남겨, 사이에 낀 것 때문에 앞뒤 단어가 이어진 것처럼 보이지 않게 한다."""
    stop = _stop()
    out: list[str | None] = []
    for w in _WORD.findall(linking.strip_outlet(title)):
        n = _norm(w)
        out.append(None if len(n) < 2 or n in stop or not re.match(r"[가-힣A-Za-z]", n) else n)
    return out


def candidate_terms(title: str) -> set[str]:
    """한 제목에서 급증 후보가 될 수 있는 용어.

    단어 하나: 기본 어휘(GENERIC)도 과정 상투어(BOILERPLATE)도 아닌 것.
    두 단어 묶음: 이웃한 두 단어 중 상투어가 없고, 둘 다 기본 어휘인 경우도 아닌 것 ('탄소중립 기본법' O, '기후 변화' X, '도입 촉구' X).
    """
    ws = words(title)
    generic, boiler = _generic(), _boilerplate()
    unigrams = {w for w in ws if w and w not in generic and w not in boiler}
    bigrams = {f"{a} {b}" for a, b in zip(ws, ws[1:])
               if a and b and a != b and a not in boiler and b not in boiler and not (a in generic and b in generic)}
    return unigrams | bigrams


def doc_freq(titles: list[str]) -> Counter:
    df: Counter = Counter()
    for t in titles:
        df.update(candidate_terms(t))
    return df


def rising_terms(recent_titles: list[str], baseline_titles: list[str], usual_df_limit: float | None = None) -> list[dict]:
    """최근 제목들에서 평소(기준 제목들)보다 특이하게 늘어난 용어.

    평소 기대 건수 = (기준 기간에서 이 용어가 나온 비율) × (최근 제목 수). 배율 = (최근 건수 + 0.5) / (기대 건수 + 0.5).
    usual_df_limit 이 있으면 기준 기간에 그 비율 이상으로 나온 용어는 '평소에도 흔한 말'로 보고 뺀다.
    """
    n_recent, n_base = len(recent_titles), len(baseline_titles)
    if not n_recent:
        return []
    recent, base = doc_freq(recent_titles), doc_freq(baseline_titles)
    out = []
    for term, c in recent.items():
        if c < config.RISING_MIN_RECENT:
            continue
        usual = base.get(term, 0) / n_base if n_base else 0.0
        if usual_df_limit is not None and usual >= usual_df_limit:
            continue
        expected = usual * n_recent
        ratio = (c + 0.5) / (expected + 0.5)
        if ratio < config.RISING_MIN_RATIO:
            continue
        out.append({"term": term, "recent": c, "baseline": round(expected, 1), "ratio": round(ratio, 1),
                    "usual_pct": round(usual * 100, 1)})
    out.sort(key=lambda x: (-x["ratio"], -x["recent"], x["term"]))
    return _drop_subsumed(out)[: config.RISING_LIMIT]


def _drop_subsumed(items: list[dict]) -> list[dict]:
    """'플라스틱세' 와 '플라스틱세 도입' 이 같은 기사들에서 나왔다면 더 구체적인 두 단어 쪽만 남긴다."""
    bigrams = [i for i in items if " " in i["term"]]
    kept = []
    for i in items:
        if " " not in i["term"] and any(i["term"] in b["term"].split() and b["recent"] >= 0.7 * i["recent"] for b in bigrams):
            continue
        kept.append(i)
    return kept

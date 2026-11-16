"""뉴스 제목과 공식 문서 제목을 비교해 같은 사안인지 점수를 매긴다 (F16). DB 를 읽지 않는 순수 함수.

뉴스 본문은 읽지 않는다. 제목만 비교하므로 일부러 보수적이다: 애매하면 연결하지 않고 '공식 확인 안 됨'으로 둔다.
"""
import re
from datetime import datetime

import config
from . import policy

_WORD = re.compile(r"[가-힣]{2,}|[A-Za-z][A-Za-z\-]{2,}")
# '도', '만' 은 조사로도 쓰이지만 '제도', '정도' 처럼 명사의 끝글자일 때가 훨씬 많아서 뺐다
_JOSA = re.compile(r"(에서|으로|까지|부터|에게|은|는|이|가|을|를|의|에|로|와|과)$")
_NUMBER = re.compile(r"(\d{1,4})\s*(기|차|호|조|억|%)?")
_QUOTED = re.compile(r"[「『]([^」』]{3,40})[」』]")


_OUTLET = re.compile(r"\s+-\s+[^-]+$")
_SEQ_NUMBER = re.compile(r"(\d{1,3})\s*(기|차|호)")


def strip_outlet(title: str) -> str:
    """뉴스 제목 끝의 ' - 언론사' 를 뗀다. 언론사 이름이 단어 겹침으로 잡히는 것을 막는다."""
    return _OUTLET.sub("", title or "")


def _compact(text: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", policy.normalize(text))


def similarity(a: str, b: str) -> float:
    """제목 전체의 글자 두 개 단위 겹침(Dice, 0~1). 보도자료를 거의 그대로 옮겨 쓴 기사는 높게 나온다."""
    ca, cb = _compact(a), _compact(b)
    ba = {ca[i:i + 2] for i in range(len(ca) - 1)}
    bb = {cb[i:i + 2] for i in range(len(cb) - 1)}
    if not ba or not bb:
        return 0.0
    return 2 * len(ba & bb) / (len(ba) + len(bb))


def sequence_conflict(a: str, b: str) -> bool:
    """'제3차' 와 '제4차' 처럼 같은 단위(기·차·호)의 번호가 서로 달라 겹치지 않으면 다른 회차의 사안이다."""
    def by_unit(t: str) -> dict[str, set[str]]:
        out: dict[str, set[str]] = {}
        for digits, unit in _SEQ_NUMBER.findall(policy.normalize(t)):
            out.setdefault(unit, set()).add(digits)
        return out
    ua, ub = by_unit(a), by_unit(b)
    return any(unit in ub and ua[unit].isdisjoint(ub[unit]) for unit in ua)


def tokens(title: str) -> set[str]:
    """제목의 핵심 단어. 조사를 떼고, 이 분야 제목에 늘 나오는 흔한 단어는 뺀다."""
    out = set()
    for w in _WORD.findall(policy.normalize(title)):
        t = w if w.isascii() else (_JOSA.sub("", w) if len(w) > 2 else w)
        if len(t) >= 2 and t not in config.LINK_GENERIC_TOKENS and t not in config.STOPWORDS:
            out.add(t)
    return out


def numbers(title: str) -> set[str]:
    """'4기', '3차', '31호', '2035' 처럼 사안을 특정하는 숫자. 단위 없는 1~2자리 숫자와 흔한 연도는 뺀다."""
    out = set()
    for digits, unit in _NUMBER.findall(policy.normalize(title)):
        if digits in config.LINK_IGNORE_NUMBERS:
            continue
        if unit or len(digits) >= 3:
            out.add(digits + unit)
    return out


def entities(title: str) -> set[str]:
    """제목에 나온 정책 용어(이름)."""
    text = policy.normalize(title)
    return {name for name, variants in config.POLICY_ENTITY_PATTERNS.items()
            if any(policy._has(text, policy.normalize(v)) for v in variants)}


def quoted_names(title: str) -> list[str]:
    """「법령명」 처럼 따옴표로 묶인 이름 (공식 문서에서 법령을 가리키는 표기)."""
    return [_compact(m) for m in _QUOTED.findall(title or "") if len(_compact(m)) >= 4]


def agency_mentioned(news_title: str, agency: str) -> bool:
    text = policy.normalize(news_title)
    for key, aliases in config.AGENCY_ALIASES.items():
        if (agency or "").startswith(key):
            return any(policy._has(text, policy.normalize(a)) for a in aliases)
    return False


def days_between(news_published: str, official_published: str) -> float:
    return (datetime.fromisoformat(news_published) - datetime.fromisoformat(official_published)).total_seconds() / 86400


def score_pair(news: dict, official: dict) -> tuple[float, dict]:
    """(점수, 근거). 시간 조건(공식 문서 전 2일 ~ 후 14일)을 벗어나면 0점."""
    gap = days_between(news["published"], official["published"])
    if not (-config.LINK_BEFORE_DAYS <= gap <= config.LINK_AFTER_DAYS):
        return 0.0, {"reason": "시간 범위 밖", "gap_days": round(gap, 1)}
    w = config.LINK_WEIGHTS
    n_title, o_title = strip_outlet(news["title"]), official["title"]

    shared_entities = entities(n_title) & entities(o_title)
    # 공식 문서의 「법령명」이 뉴스 제목에 그대로 나오면 같은 용어로 본다
    n_compact = _compact(n_title)
    shared_entities |= {"법령:" + q for q in quoted_names(o_title) if q in n_compact}
    shared_numbers = numbers(n_title) & numbers(o_title)
    shared_tokens = tokens(n_title) & tokens(o_title)
    # 이미 '정책 용어' 점수로 센 단어('배출권', '할당계획' 등)는 단어 겹침으로 한 번 더 세지 않는다
    for name in shared_entities:
        for variant in config.POLICY_ENTITY_PATTERNS.get(name, []):
            shared_tokens -= tokens(variant)

    score = min(len(shared_entities) * w["entity"], w["entity_cap"])
    score += min(len(shared_numbers) * w["number"], w["number_cap"])
    score += min(len(shared_tokens) * w["token"], w["token_cap"])
    sim = similarity(n_title, o_title)
    sim_points = w["similarity"] * min(max((sim - w["sim_floor"]) / w["sim_span"], 0.0), 1.0)
    score += sim_points
    agency = agency_mentioned(n_title, official.get("agency", ""))
    if agency:
        score += w["agency"]
    fresh = 0 <= gap <= 3
    if fresh:
        score += w["fresh"]
    # 정책 용어도 숫자도 핵심 단어도 제목 유사성도 없으면 기관명·시간 가점만으로는 연결하지 않는다
    if not (shared_entities or shared_numbers or shared_tokens or sim_points):
        return 0.0, {"reason": "공유하는 내용 없음"}
    conflict = sequence_conflict(n_title, o_title)
    if conflict:
        score -= w["conflict"]       # 다른 회차(제3차/제4차, 3기/4기)의 같은 제도일 수 있다
    # '같은 제도 이야기' 라는 근거(정책 용어)에 기관명·시간 가점만 더해서는 연결하지 않는다.
    # 같은 사안이라는 근거(같은 숫자·핵심 단어·제목 유사도)가 하나는 있어야 한다.
    event_specific = bool(shared_numbers or shared_tokens or sim_points)
    if not event_specific:
        score = min(score, config.LINK_MIN_SCORE - 1)
    return round(max(float(score), 0.0), 1), {
        "entities": sorted(shared_entities), "numbers": sorted(shared_numbers), "tokens": sorted(shared_tokens),
        "similarity": round(sim, 2), "agency": agency, "fresh": fresh, "conflict": conflict,
        "event_specific": event_specific, "gap_days": round(gap, 1),
    }


def best_links(news: dict, officials: list[dict]) -> list[tuple[dict, float, dict]]:
    """연결할 공식 문서 목록 [(문서, 점수, 근거)]. 최소 점수를 넘고 1등과 LINK_MARGIN 이내인 문서를 최대 LINK_MAX_PER_NEWS 개."""
    scored = []
    for o in officials:
        s, ev = score_pair(news, o)
        if s >= config.LINK_MIN_SCORE:
            scored.append((o, s, ev))
    if not scored:
        return []
    scored.sort(key=lambda x: -x[1])
    top = scored[0][1]
    return [x for x in scored if top - x[1] <= config.LINK_MARGIN][: config.LINK_MAX_PER_NEWS]

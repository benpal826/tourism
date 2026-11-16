"""출처 신뢰도 등급(F13) 판정. 규칙 기반이며 DB 를 읽지 않는 순수 함수.

매체의 성향을 추측하거나 평가하지 않는다. 도메인 종류, 이름 형태, 수집 빈도처럼 눈으로 확인할 수 있는 사실만 근거로 쓰고,
왜 그 등급인지(reason)를 함께 돌려줘서 틀렸을 때 바로 보정할 수 있게 한다.
"""
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

import config

TIER_LABELS = {1: "공식", 2: "일반", 3: "단체·업계 주장", 0: "미분류"}


@dataclass
class TierResult:
    tier: int
    reason: str


def _key(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").lower())


def domain_of(value: str) -> str:
    """주소나 도메인 형태의 이름에서 도메인만 뽑는다 ('https://www.ebn.co.kr/x' → 'ebn.co.kr'). 도메인이 아니면 ''."""
    s = (value or "").strip()
    if not s:
        return ""
    if "://" not in s:
        if " " in s or "." not in s:
            return ""
        s = "http://" + s
    host = urlsplit(s).netloc.lower().split("@")[-1].split(":")[0]
    host = re.sub(r"^www\d?\.", "", host).rstrip(".")
    return host if "." in host else ""


def _domain_match(domain: str, patterns: list[str]) -> str:
    for p in patterns:
        p = p.lower().lstrip(".")
        if domain == p or domain.endswith("." + p):
            return p
    return ""


def _name_pattern(name: str, patterns: list[str]) -> str:
    low = (name or "").lower()
    for p in patterns:
        p = p.lower()
        if p.isascii():
            if re.search(rf"(?<![a-z]){re.escape(p)}(?![a-z])", low):
                return p
        elif p in low:
            return p
    return ""


def looks_like_news_name(name: str) -> bool:
    low = (name or "").lower()
    return any(h in low for h in config.NEWS_NAME_HINTS)


def classify_source(name: str, domain: str = "", count: int = 0, source_type: str = "news") -> TierResult:
    """언론사(또는 기관) 하나의 등급. count 는 최근 TIER_WINDOW_DAYS 일에 수집된 이 언론사의 기사 수."""
    domain = domain or domain_of(name)
    overrides = {_key(k): v for k, v in config.SOURCE_TIER_OVERRIDES.items()}
    for k in (_key(name), domain):
        if k and k in overrides:
            return TierResult(int(overrides[k]), "override")

    if source_type == "official":
        return TierResult(1, "official-source")
    if d := _domain_match(domain, config.OFFICIAL_DOMAIN_SUFFIXES):
        return TierResult(1, f"domain:{d}")
    if d := _domain_match(domain, config.PRESS_RELEASE_DOMAINS):
        return TierResult(3, f"press-release-site:{d}")
    if _key(name) in {_key(m) for m in config.MAJOR_OUTLETS}:
        return TierResult(2, "major-outlet-list")

    # 단체 표지: 언론사 이름(…뉴스, …신문 등)이면 적용하지 않는다 ('한국경제인협회' 는 단체, '데일리연합' 은 언론)
    if not looks_like_news_name(name):
        if d := _domain_match(domain, config.ORG_DOMAINS):
            return TierResult(3, f"domain:{d}")
        if p := _name_pattern(name, config.ORG_NAME_PATTERNS):
            return TierResult(3, f"name-pattern:{p}")

    if count >= config.TIER2_MIN_COUNT:
        # 많이 나온다는 것이 믿을 만하다는 뜻은 아니다. 근거를 'freq' 로 남겨 검수 표에서 따로 모아 보여준다
        return TierResult(2, f"freq>={config.TIER2_MIN_COUNT} ({count}건)" + _review_note(name, domain))
    reason = f"insufficient-evidence ({count}건)"
    return TierResult(0, reason + _review_note(name, domain))


def _review_note(name: str, domain: str) -> str:
    """등급은 바꾸지 않고 사람이 확인하면 좋은 이유만 붙인다 (단체일 수도 언론일 수도 있는 이름·도메인)."""
    notes = []
    if p := _name_pattern(name, config.SOFT_ORG_PATTERNS):
        notes.append(f"review:soft-org-pattern({p})")
    if domain.endswith(".org"):
        notes.append("review:.org-domain")
    return "".join("; " + n for n in notes)


def sensational_terms(title: str) -> list[str]:
    """제목에 있는 자극적 표현. 표시용이며 점수 계산이나 삭제에는 쓰지 않는다."""
    found = []
    low = (title or "").lower()
    for t in config.SENSATIONAL_TERMS:
        if t.isascii():
            if re.search(rf"(?<![a-z]){re.escape(t.lower())}(?![a-z])", low):
                found.append(t)
        elif t in (title or ""):
            found.append(t)
    return found

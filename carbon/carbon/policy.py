"""공식 문서의 정책 진행 단계(F11)와 국내 영향도(F12) 판정. 규칙 기반이며 DB 를 읽지 않는다.

뉴스 제목으로는 판정하지 않는다. 뉴스는 연결된 공식 문서의 값을 따른다 (F16).
"""
import re
from dataclasses import dataclass

import config

STAGE_LABELS = {"proposed": "추진", "decided": "확정", "unknown": "미분류"}
IMPACT_LABELS = {"direct": "직접 규제", "indirect": "간접", "reference": "참고", "unknown": "미분류"}

_DOTS = re.compile(r"[ㆍ·∙•]")


def normalize(text: str) -> str:
    """소문자화, 가운뎃점 표기 통일(ㆍ·), 공백 정리. 키워드와 본문을 같은 방식으로 맞춘다."""
    return re.sub(r"\s+", " ", _DOTS.sub("·", (text or "").lower())).strip()


def _has(text: str, kw: str) -> bool:
    if kw.isascii():
        # 영문은 앞뒤에 영문자가 붙지 않을 때만 (assets 속 ets 제외). 숫자는 허용: cop31, ets2
        return re.search(rf"(?<![a-z]){re.escape(kw)}(?![a-z])", text) is not None
    return kw in text


def classify_stage(title: str, extra: str = "") -> str:
    """proposed(추진) / decided(확정) / unknown. 표지가 둘 이상이면 글의 끝에 가장 가까운 것이 이긴다.
    extra 는 국회 법안의 처리 상태(계류, 원안가결 등)처럼 제목 뒤에 붙일 정보다."""
    text = f"{title or ''} {extra or ''}"
    best_end, best = -1, "unknown"
    for stage, patterns in config.POLICY_STAGE_RULES.items():
        for p in patterns:
            for m in re.finditer(p, text, flags=re.I):
                if m.end() > best_end or (m.end() == best_end and stage == "proposed"):
                    best_end, best = m.end(), stage
    return best


def impact_label(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score >= config.IMPACT_BANDS["direct"]:
        return "direct"
    if score >= config.IMPACT_BANDS["indirect"]:
        return "indirect"
    return "reference"


def seed_weights() -> dict[str, float]:
    return {normalize(k): float(v) for k, v in config.IMPACT_SEEDS.items()}


def score_impact(title: str, weights: dict[str, float] | None = None) -> tuple[float | None, str]:
    """제목에 나온 키워드로 영향도 점수를 정한다. 키워드가 없으면 (None, '').

    1) 더 구체적인 키워드에 포함된 키워드는 버린다. ('영국 cbam' 이 있으면 'cbam' 은 버리고, '배출권거래제' 가 있으면 '배출권' 은 버린다)
    2) 서로 무관한 키워드가 남으면 가중치가 가장 높은 것을 쓴다. ('온실가스 배출권' 은 '온실가스' 55 가 아니라 '배출권' 90)
    """
    text = normalize(title)
    weights = weights if weights is not None else seed_weights()
    matched = [kw for kw in weights if _has(text, kw)]
    if not matched:
        return None, ""
    specific = [k for k in matched if not any(k != o and k in o for o in matched)]
    kw = max(specific, key=lambda k: (weights[k], len(k)))
    return weights[kw], kw


@dataclass
class Judgement:
    stage: str
    impact: str
    impact_score: float | None
    impact_keyword: str


def classify_official(title: str, summary: str = "", agency: str = "", weights: dict[str, float] | None = None) -> Judgement:
    # summary 는 대부분 담당 부서명이라 단계 판정에 쓰지 않는다 ('태양광보급추진단' 의 '추진' 오판 방지).
    # 국회 법안만 summary 에 처리 상태(계류/가결 등)가 들어 있어 함께 본다.
    extra = summary if agency.startswith("국회") else ""
    score, kw = score_impact(title, weights)
    return Judgement(classify_stage(title, extra), impact_label(score), score, kw)

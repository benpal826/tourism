"""무관 기사 필터링 (F6). 제목만 보는 규칙 기반 판정이며 DB 를 읽지 않는 순수 함수.

관련 기사를 잘못 숨기는 것이 무관 기사가 남는 것보다 나쁘다. 그래서 '확실한 것만' 제외(0)하고,
단서가 약하면 미판정(None)으로 둔다. 미판정은 집계에 남고, 이후 LLM 단계(F5)가 판정한다.
삭제하지 않고 relevant=0 으로 표시만 하며, 판정 근거를 relevance_reason 에 남긴다.
"""
import re

import config
from . import policy


def _first(text: str, keywords: list[str]) -> str:
    """text(정규화된 제목)에 처음 걸리는 키워드. 영문은 단어 경계로 비교하되 복수형(s, es)은 같은 단어로 본다
    ('carbon markets' 가 'carbon market' 에 걸리고, 'assets' 속 'ets' 는 걸리지 않는다). 한국어는 글자 포함으로 비교한다."""
    for kw in keywords:
        k = policy.normalize(kw)
        if k.isascii():
            if re.search(rf"(?<![a-z]){re.escape(k)}(?:s|es)?(?![a-z])", text):
                return kw
        elif k in text:
            return kw
    return ""


def judge_relevance(title: str, source: str = "", source_type: str = "news",
                    domestic_impact: str | None = None) -> tuple[int | None, str]:
    """(relevant, reason). relevant: 1 관련, 0 무관, None 미판정. reason 은 'rule:' 로 시작한다 (규칙 판정 표시).

    공식 문서는 source 가 기관명이다. 국내 영향도가 판정됐으면 관련, 키워드가 하나도 없으면 무관이다.
    다만 온실가스종합정보센터처럼 전문 기관의 문서는 키워드가 없어도 무관으로 단정하지 않는다 (미판정).
    """
    if source_type == "official":
        if domestic_impact is None:
            return None, "rule:official-pending"
        if domestic_impact == "unknown":
            if source in config.SPECIALIZED_AGENCIES:
                return None, "rule:official-specialized-agency"
            return 0, "rule:official-no-carbon-keyword"
        return 1, f"rule:official-impact({domestic_impact})"

    rules = config.RELEVANCE_RULES
    text = policy.normalize(title)
    if kw := _first(text, rules["exclude_hard"]):
        return 0, f"rule:exclude-hard({kw})"
    strong = _first(text, rules["strong"])
    if strong:
        return 1, f"rule:strong({strong})"
    if kw := _first(text, rules["exclude"]):
        return 0, f"rule:exclude({kw})"
    if source and policy.normalize(source) in {policy.normalize(s) for s in rules["exclude_sources"]}:
        return 0, f"rule:exclude-source({source})"
    if weak := _first(text, rules["weak"]):
        return None, f"rule:weak({weak})"
    return None, "rule:no-keyword"

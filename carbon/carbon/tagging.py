"""키워드 기반 주제·지역 태깅."""
import re

import config

_PUNCT = re.compile(r"[,;:!?()\[\]\"“”‘’]")


def _matches(low: str, kw: str) -> bool:
    """low 는 구두점을 공백으로 바꾸고 앞뒤를 공백으로 패딩한 소문자 제목.

    영문 키워드는 단어 경계로 비교한다 ('ets' 가 'markets', 'sets', 'assets' 에 걸리지 않게. 복수형 s 는 허용).
    한국어 키워드는 글자 포함 여부로 비교한다 (조사가 붙어도 걸리게). 키워드 끝의 공백('인도 ')은 단어 끝 표시로 그대로 둔다.
    """
    if kw.isascii():
        word = kw.strip().rstrip("-")
        return re.search(rf"(?<![a-z0-9]){re.escape(word)}s?(?![a-z0-9])", low) is not None
    return kw in low


def classify(text: str, table: dict[str, list[str]]) -> list[str]:
    # 구두점을 공백으로 바꾸고 앞뒤를 패딩해, 한국어 키워드의 끝 공백 표시('인도 ')가 문장 끝·구두점 앞에서도 맞게 한다.
    low = f" {_PUNCT.sub(' ', text.lower())} "
    return [name for name, kws in table.items() if any(_matches(low, k) for k in kws)]


def tag_text(title: str, summary: str = "") -> tuple[list[str], list[str]]:
    blob = f"{title} {summary}"
    return classify(blob, config.TOPICS), classify(blob, config.REGIONS)

"""수집기 인터페이스와 공통 헬퍼."""
import hashlib
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import unescape

import config


def clean_text(text: str) -> str:
    """HTML 태그 제거, 엔티티 해제, 공백 정리."""
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def normalize_title(title: str) -> str:
    """'제목 - 언론사' 에서 언론사 접미사를 떼고 기호·공백 제거 후 소문자화."""
    t = re.sub(r"\s+-\s+[^-]+$", "", title)
    return re.sub(r"\W+", "", t.lower())


def article_id(title: str) -> str:
    return hashlib.sha1(normalize_title(title).encode()).hexdigest()


def canonical_url(url: str) -> str:
    """세션 아이디(;jsessionid=...)와 #조각을 떼어 같은 글이 다른 주소로 중복 저장되지 않게 한다."""
    url = re.sub(r";jsessionid=[^?#]*", "", url or "")
    return url.split("#", 1)[0]


def official_id(url: str) -> str:
    """공식 문서는 제목이 아니라 정규화한 원문 주소로 구분한다. (기관이 달라도 같은 제목이 있을 수 있음)"""
    return hashlib.sha1(("official|" + canonical_url(url)).encode()).hexdigest()


def matches_keywords(text: str, keywords: list[str]) -> bool:
    """키워드가 하나라도 있으면 True. 영문 키워드는 단어 경계로 비교한다 (예: 'ets' 가 'assets' 에 걸리지 않게)."""
    low = (text or "").lower()
    for kw in keywords:
        kw = kw.lower()
        if kw.isascii():
            if re.search(rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])", low):
                return True
        elif kw in low:
            return True
    return False


def kst_date_to_utc_iso(y: int, m: int, d: int) -> str:
    """게시판 날짜(한국 날짜)를 그날 0시 KST 로 보고 UTC ISO 로 변환한다."""
    return datetime(y, m, d, tzinfo=config.KST).astimezone(timezone.utc).isoformat()


@dataclass
class Article:
    title: str
    url: str
    source: str       # 언론사 (공식 출처는 기관명)
    lang: str
    query: str        # 수집에 쓴 검색어 (공식 출처는 게시판 이름)
    summary: str
    published: str    # ISO8601 UTC
    source_type: str = "news"   # news / official
    agency: str = ""            # 공식 출처의 발행 기관명
    source_url: str = ""        # 언론사 주소 (RSS 가 알려 줌). 출처 등급 판정에 쓴다
    id: str = field(init=False)

    def __post_init__(self):
        self.id = official_id(self.url) if self.source_type == "official" else article_id(self.title)


class Source(ABC):
    """모든 수집기가 따르는 인터페이스."""

    name: str = "source"

    def __init__(self):
        # fetch() 중 실패한 항목(예: 검색어)을 기록한다. 실패해도 나머지는 계속 수집한다.
        self.failures: list[str] = []

    @abstractmethod
    def fetch(self) -> list[Article]:
        ...

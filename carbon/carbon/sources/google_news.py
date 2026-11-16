"""Google News RSS 수집기."""
import logging
import time
from datetime import datetime, timezone
from urllib.parse import quote

import feedparser
import requests

import config
from .base import Article, Source, clean_text

log = logging.getLogger(__name__)


def build_feed_url(lang: str, query: str, days_back: int) -> str:
    q = f"{query} when:{days_back}d"
    if lang == "ko":
        params = "hl=ko&gl=KR&ceid=KR:ko"
    else:
        params = "hl=en-US&gl=US&ceid=US:en"
    return f"https://news.google.com/rss/search?q={quote(q)}&{params}"


class GoogleNewsSource(Source):
    name = "google_news"

    def __init__(self, queries=None, session=None, days_back=None, delay=1.0):
        super().__init__()
        self.queries = queries if queries is not None else config.QUERIES
        self.days_back = days_back if days_back is not None else config.DAYS_BACK
        self.delay = delay
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = "Mozilla/5.0 (carbon-policy-monitor)"

    def fetch(self) -> list[Article]:
        self.failures = []
        articles: list[Article] = []
        for i, (lang, query) in enumerate(self.queries):
            if i and self.delay:
                time.sleep(self.delay)
            try:
                r = self.session.get(
                    build_feed_url(lang, query, self.days_back),
                    timeout=config.REQUEST_TIMEOUT,
                )
                r.raise_for_status()
                feed = feedparser.parse(r.content)
            except Exception as e:  # 네트워크·파싱 오류: 이 검색어만 건너뛴다
                log.warning("검색어 '%s' 수집 실패: %s", query, e)
                self.failures.append(query)
                continue
            for e in feed.entries:
                a = self._to_article(e, lang, query)
                if a:
                    articles.append(a)
        return articles

    def search(self, query: str, lang: str = "ko", days_back: int | None = None) -> list[Article]:
        """검색어 하나로 기사를 가져온다. 실패하면 예외를 그대로 던진다 (호출한 쪽이 재시도 여부를 정한다)."""
        r = self.session.get(build_feed_url(lang, query, days_back or self.days_back), timeout=config.REQUEST_TIMEOUT)
        r.raise_for_status()
        feed = feedparser.parse(r.content)
        return [a for a in (self._to_article(e, lang, query) for e in feed.entries) if a]

    @staticmethod
    def _to_article(e, lang: str, query: str) -> Article | None:
        title = clean_text(e.get("title", ""))
        if not title:
            return None
        if e.get("published_parsed"):
            published = datetime(*e.published_parsed[:6], tzinfo=timezone.utc).isoformat()
        else:
            published = datetime.now(timezone.utc).isoformat()
        return Article(
            title=title,
            url=e.get("link", "") or "",
            source=(e.get("source") or {}).get("title", ""),
            lang=lang,
            query=query,
            summary=clean_text(e.get("summary", "")),
            published=published,
            source_url=(e.get("source") or {}).get("href", ""),
        )

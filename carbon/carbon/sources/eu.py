"""EU 집행위원회 보도자료(프레스코너) RSS 수집기. 기후·배출권 관련 제목만 남긴다."""
import logging
from datetime import datetime, timezone

import feedparser

import config
from .base import Article, Source, clean_text, matches_keywords
from .http import PoliteClient

log = logging.getLogger(__name__)


class EuPresscornerSource(Source):
    name = "eu_presscorner"

    def __init__(self, client: PoliteClient | None = None, url=None, keywords=None):
        super().__init__()
        self.client = client or PoliteClient()
        self.url = url or config.EU_PRESSCORNER_RSS
        self.keywords = keywords if keywords is not None else config.EU_KEYWORDS

    def fetch(self) -> list[Article]:
        self.failures = []
        resp = self.client.get(self.url)
        if resp is None:
            self.failures.append("EU presscorner")
            return []
        feed = feedparser.parse(resp.content)
        out = []
        for e in feed.entries:
            title = clean_text(e.get("title", ""))
            summary = clean_text(e.get("summary", ""))
            if not title or not matches_keywords(f"{title} {summary}", self.keywords):
                continue
            if e.get("published_parsed"):
                published = datetime(*e.published_parsed[:6], tzinfo=timezone.utc).isoformat()
            else:
                published = datetime.now(timezone.utc).isoformat()
            out.append(Article(
                title=title, url=e.get("link", ""), source="European Commission", lang="en",
                query="EU presscorner", summary=summary, published=published,
                source_type="official", agency="European Commission",
            ))
        log.info("EU presscorner: 항목 %d건 중 관련 %d건", len(feed.entries), len(out))
        return out

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from carbon import db  # noqa: E402
from carbon.sources.base import Article, Source  # noqa: E402

NOW = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    yield c
    c.close()


def make_article(title, days_ago=0.0, query="q", lang="ko", source="언론사", summary="", url="https://example.com/a"):
    pub = (NOW - timedelta(days=days_ago)).isoformat()
    return Article(title=title, url=url, source=source, lang=lang,
                   query=query, summary=summary, published=pub)


class FakeSource(Source):
    name = "fake"

    def __init__(self, articles, failures=None):
        super().__init__()
        self._articles = articles
        self._failures = failures or []

    def fetch(self):
        self.failures = list(self._failures)
        return list(self._articles)

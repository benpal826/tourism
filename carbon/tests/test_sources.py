from carbon.sources.base import article_id, normalize_title
from carbon.sources.google_news import GoogleNewsSource, build_feed_url

RSS = """<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>
<item><title>EU ETS price hits record - Reuters</title><link>https://example.com/1</link>
<pubDate>Mon, 02 Nov 2026 09:00:00 GMT</pubDate><description>&lt;b&gt;summary&lt;/b&gt; text</description>
<source url="https://reuters.com">Reuters</source></item>
<item><title>배출권거래제 개편안 발표 - 연합뉴스</title><link>https://example.com/2</link>
<pubDate>Mon, 02 Nov 2026 10:00:00 GMT</pubDate></item>
</channel></rss>""".encode()


class Resp:
    def __init__(self, content=b"", fail=False):
        self.content, self.fail = content, fail

    def raise_for_status(self):
        if self.fail:
            raise RuntimeError("HTTP 500")


class FakeSession:
    def __init__(self, bad_query=None):
        self.headers = {}
        self.bad_query = bad_query

    def get(self, url, timeout=None):
        if self.bad_query and self.bad_query in url:
            return Resp(fail=True)
        return Resp(RSS)


def test_normalize_title_ignores_outlet_suffix_and_punctuation():
    assert normalize_title("EU ETS: Price Up! - Reuters") == normalize_title("eu ets price up - Bloomberg")
    assert article_id("같은 제목 - A신문") == article_id("같은 제목 - B신문")


def test_feed_url_by_language():
    assert "hl=ko" in build_feed_url("ko", "배출권", 3)
    assert "hl=en-US" in build_feed_url("en", "ETS", 3)
    assert "when%3A3d" in build_feed_url("en", "ETS", 3)


def test_fetch_parses_entries():
    src = GoogleNewsSource(queries=[("en", "ets")], session=FakeSession(), delay=0)
    arts = src.fetch()
    assert len(arts) == 2
    first = arts[0]
    assert first.source == "Reuters" and first.lang == "en" and first.query == "ets"
    assert first.published.startswith("2026-11-02T09:00:00")
    assert "summary text" in first.summary and "<b>" not in first.summary


def test_one_failing_query_does_not_stop_others():
    src = GoogleNewsSource(queries=[("en", "good"), ("en", "bad"), ("ko", "also good")],
                           session=FakeSession(bad_query="bad"), delay=0)
    arts = src.fetch()
    assert src.failures == ["bad"]
    assert {a.query for a in arts} == {"good", "also good"}

import pytest

from carbon.sources.http import PoliteClient


class Resp:
    def __init__(self, status=200, text="", content=b"", encoding="utf-8"):
        self.status_code, self.text, self.content = status, text, content
        self.encoding, self.apparent_encoding = encoding, "utf-8"

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, robots, pages=None):
        self.headers = {}
        self.robots = robots          # Resp 또는 Exception
        self.pages = pages or {}
        self.calls = []

    def get(self, url, timeout=None, **kw):
        self.calls.append(url)
        if url.endswith("/robots.txt"):
            if isinstance(self.robots, Exception):
                raise self.robots
            return self.robots
        return self.pages.get(url, Resp(200, "ok"))


def client(robots, **kw):
    return PoliteClient(delay=0, session=FakeSession(robots, **kw), sleep=lambda s: None)


def test_respects_disallow_rules():
    c = client(Resp(200, "User-agent: *\nDisallow: /private/\n"))
    assert c.allowed("https://x.test/public/a") is True
    assert c.allowed("https://x.test/private/a") is False
    assert c.get("https://x.test/private/a") is None


def test_missing_robots_means_allowed():
    assert client(Resp(404)).allowed("https://x.test/any") is True


def test_html_instead_of_robots_is_treated_as_no_rules():
    assert client(Resp(200, "<!DOCTYPE html><html>...")).allowed("https://x.test/any") is True


@pytest.mark.parametrize("robots", [Resp(403), Resp(500), ConnectionError("down")])
def test_forbidden_error_or_unreachable_robots_means_do_not_fetch(robots):
    assert client(robots).allowed("https://x.test/any") is False


def test_full_block_is_respected():
    c = client(Resp(200, "User-agent: *\nDisallow: /\n"))
    assert c.get("https://x.test/a") is None


def test_robots_is_fetched_once_per_host():
    c = client(Resp(404))
    c.get("https://x.test/a")
    c.get("https://x.test/b")
    assert c.session.calls.count("https://x.test/robots.txt") == 1


def test_waits_between_requests_to_same_host():
    sleeps = []
    c = PoliteClient(delay=2.0, session=FakeSession(Resp(404)), sleep=sleeps.append)
    c.get("https://x.test/a")
    c.get("https://x.test/b")
    assert len(sleeps) == 1 and 1.0 < sleeps[0] <= 2.0


def test_http_error_returns_none():
    c = client(Resp(404), pages={"https://x.test/broken": Resp(500)})
    assert c.get("https://x.test/broken") is None

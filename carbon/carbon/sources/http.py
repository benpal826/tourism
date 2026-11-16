"""공식 사이트용 예의 바른 HTTP 클라이언트.

- robots.txt 를 호스트별로 한 번 읽어 허용된 경로만 요청한다.
- 같은 호스트에는 최소 간격(delay)을 둔다.
- 식별 가능한 User-Agent 를 쓴다.
robots.txt 는 이용약관을 대신하지 않는다. 약관 확인은 docs/source-research.md 에 별도로 기록한다.
"""
import logging
import time
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests

import config

log = logging.getLogger(__name__)


class PoliteClient:
    def __init__(self, delay: float | None = None, user_agent: str | None = None, session=None, sleep=time.sleep):
        self.delay = config.REQUEST_DELAY if delay is None else delay
        self.user_agent = user_agent or config.USER_AGENT
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = self.user_agent
        self._sleep = sleep
        self._robots: dict[str, RobotFileParser] = {}
        self._last: dict[str, float] = {}

    def _robots_for(self, origin: str) -> RobotFileParser:
        if origin in self._robots:
            return self._robots[origin]
        rp = RobotFileParser()
        try:
            r = self.session.get(origin + "/robots.txt", timeout=config.REQUEST_TIMEOUT)
            code = r.status_code
            if code == 200:
                text = r.text
                if text.lstrip().lower().startswith(("<!doctype", "<html")):
                    log.info("%s robots.txt 가 HTML 응답이라 규칙 없음으로 처리", origin)
                    rp.allow_all = True
                else:
                    rp.parse(text.splitlines())
            elif code in (401, 403):
                log.warning("%s robots.txt 접근 거부(%s): 수집하지 않음", origin, code)
                rp.disallow_all = True
            elif 400 <= code < 500:
                rp.allow_all = True      # robots.txt 없음
            else:
                log.warning("%s robots.txt 서버 오류(%s): 수집하지 않음", origin, code)
                rp.disallow_all = True
        except Exception as e:
            log.warning("%s robots.txt 확인 실패(%s): 수집하지 않음", origin, type(e).__name__)
            rp.disallow_all = True
        self._robots[origin] = rp
        return rp

    def allowed(self, url: str) -> bool:
        p = urlsplit(url)
        return self._robots_for(f"{p.scheme}://{p.netloc}").can_fetch(self.user_agent, url)

    def get(self, url: str, **kw):
        """허용되고 성공하면 Response, 아니면 None (이유는 로그에 남김)."""
        if not self.allowed(url):
            log.warning("robots.txt 가 허용하지 않아 건너뜀: %s", url)
            return None
        host = urlsplit(url).netloc
        wait = self.delay - (time.monotonic() - self._last.get(host, -1e9))
        if wait > 0:
            self._sleep(wait)
        try:
            r = self.session.get(url, timeout=config.REQUEST_TIMEOUT, **kw)
            self._last[host] = time.monotonic()
            r.raise_for_status()
        except Exception as e:
            self._last[host] = time.monotonic()
            log.warning("요청 실패 %s: %s", url, e)
            return None
        if not r.encoding or r.encoding.lower() == "iso-8859-1":
            r.encoding = r.apparent_encoding
        return r

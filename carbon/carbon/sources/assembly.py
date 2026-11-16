"""열린국회정보 Open API: 의원발의 법률안 중 탄소·기후 관련 법안.

- 인증키는 환경변수 ASSEMBLY_API_KEY 로만 읽는다. 없으면 샘플 모드(키워드당 최대 5건)로 동작한다.
- 이 API 는 의원발의 법률안만 다룬다. 정부제출 법률안과 법안 본문은 제공되지 않는 것으로 알려져 있으나 확인하지 못했다.
- 국회 의안정보시스템(likms.assembly.go.kr)은 robots.txt 가 전체 차단이라 접속하지 않고, 응답의 링크 주소만 저장한다.
"""
import logging
import os
import time
from datetime import datetime, timezone

import requests

import config
from .base import Article, Source, kst_date_to_utc_iso

log = logging.getLogger(__name__)
SAMPLE_PAGE_SIZE = 5


class AssemblyBillsSource(Source):
    name = "assembly_bills"

    def __init__(self, keywords=None, session=None, api_key: str | None = None, delay: float = 1.0):
        super().__init__()
        self.keywords = keywords if keywords is not None else config.ASSEMBLY_KEYWORDS
        self.session = session or requests.Session()
        self.api_key = api_key if api_key is not None else os.environ.get("ASSEMBLY_API_KEY", "")
        self.delay = delay

    def fetch(self) -> list[Article]:
        self.failures = []
        if not self.api_key:
            log.info("ASSEMBLY_API_KEY 없음: 샘플 모드로 키워드당 최대 %d건만 가져옵니다", SAMPLE_PAGE_SIZE)
        seen: dict[str, Article] = {}
        for i, kw in enumerate(self.keywords):
            if i and self.delay:
                time.sleep(self.delay)
            params = {"Type": "json", "pIndex": 1, "pSize": 100 if self.api_key else SAMPLE_PAGE_SIZE,
                      "AGE": config.ASSEMBLY_AGE, "BILL_NAME": kw}
            if self.api_key:
                params["KEY"] = self.api_key
            try:
                r = self.session.get(config.ASSEMBLY_API_URL, params=params,
                                     headers={"User-Agent": config.USER_AGENT}, timeout=config.REQUEST_TIMEOUT)
                r.raise_for_status()
                rows = self.parse(r.json())
            except Exception as e:
                log.warning("국회 법안 검색어 '%s' 실패: %s", kw, e)
                self.failures.append(f"국회 법안 {kw}")
                continue
            for row in rows:
                a = self._to_article(row, kw)
                if a:
                    seen.setdefault(a.id, a)
        log.info("국회 법안: 키워드 %d개, 법안 %d건", len(self.keywords), len(seen))
        return list(seen.values())

    @staticmethod
    def parse(data: dict) -> list[dict]:
        """응답에서 행 목록을 꺼낸다. 결과 없음(INFO-200) 등 행이 없는 응답은 빈 목록."""
        body = data.get("nzmimeepazxkubdpn")
        if not body:
            return []
        for part in body:
            if "row" in part:
                return part["row"]
        return []

    @staticmethod
    def _to_article(row: dict, keyword: str) -> Article | None:
        title = (row.get("BILL_NAME") or "").strip()
        url = row.get("DETAIL_LINK") or ""
        if not title or not url:
            return None
        dt = (row.get("PROPOSE_DT") or "")[:10]
        try:
            y, m, d = (int(x) for x in dt.split("-"))
            published = kst_date_to_utc_iso(y, m, d)
        except ValueError:
            published = datetime.now(timezone.utc).isoformat()
        status = row.get("PROC_RESULT") or "계류"
        summary = " · ".join(x for x in [row.get("PROPOSER"), row.get("COMMITTEE"), status] if x)
        return Article(title=title, url=url, source="국회", lang="ko", query=f"법안:{keyword}",
                       summary=summary, published=published, source_type="official",
                       agency="국회(의원발의 법률안)")

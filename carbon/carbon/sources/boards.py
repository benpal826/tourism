"""정부·공공기관 게시판 목록 수집기 (F7).

사이트마다 목록 HTML 이 달라서 파서를 따로 둔다. 파서는 순수 함수(HTML 문자열 -> 항목 목록)라
저장해 둔 HTML 샘플로 테스트할 수 있다. 사이트 구조가 바뀌면 항목이 0건이 되므로 실패로 기록한다.
"""
import logging
import re
from datetime import datetime, timezone
from html import unescape
from urllib.parse import parse_qs, urljoin, urlsplit

import config
from .base import Article, Source, canonical_url, kst_date_to_utc_iso, matches_keywords
from .http import PoliteClient

log = logging.getLogger(__name__)

_DATE = re.compile(r"(\d{4})[-.]\s*(\d{1,2})[-.]\s*(\d{1,2})")


def _text(fragment: str) -> str:
    fragment = re.sub(r"<!--.*?-->", " ", fragment, flags=re.S)
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", fragment))).replace("\xa0", " ").strip()


def _rows(html: str) -> list[str]:
    return re.findall(r"<tr\b.*?</tr>", html, flags=re.S | re.I)


def _cells(row: str) -> list[str]:
    # 주석 안의 <td> 가 칸 번호를 어긋나게 하므로 주석을 먼저 지운다
    row = re.sub(r"<!--.*?-->", "", row, flags=re.S)
    return re.findall(r"<td\b[^>]*>(.*?)</td>", row, flags=re.S | re.I)


def _date_of(text: str) -> tuple[int, int, int] | None:
    m = _DATE.search(text)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def _item(title, url, date, dept=""):
    return {"title": title, "url": url, "date": date, "dept": dept}


# ----------------------------------------------------------------- 사이트별 파서
def parse_mcee(html: str, base: str) -> list[dict]:
    """기후에너지환경부(mcee.go.kr) 게시판: <a title=.. href=..board/read.do..boardId=..>"""
    items, seen = [], set()
    for row in _rows(html):
        a = re.search(r"<a\b([^>]*board/read\.do[^>]*)>(.*?)</a>", row, flags=re.S | re.I)
        if not a:
            continue
        attrs, inner = a.group(1), a.group(2)
        href = re.search(r'href="([^"]*)"', attrs)
        if not href:
            continue
        q = parse_qs(urlsplit(unescape(href.group(1))).query)
        board_id = (q.get("boardId") or [""])[0]
        if not board_id or board_id in seen:
            continue
        seen.add(board_id)
        t = re.search(r'title="([^"]*)"', attrs)
        title = _text(t.group(1)) if t else _text(inner)
        origin = "{0.scheme}://{0.netloc}".format(urlsplit(base))
        url = f"{origin}/home/web/board/read.do?menuId={(q.get('menuId') or [''])[0]}" \
              f"&boardMasterId={(q.get('boardMasterId') or [''])[0]}&boardId={board_id}"
        cells = _cells(row)
        dept = _text(cells[2]) if len(cells) > 2 else ""
        items.append(_item(title, url, _date_of(_text(row)), dept))
    return items


def parse_keco(html: str, base: str) -> list[dict]:
    """한국환경공단(keco.or.kr): onclick="location.href='./view.do?article_seq=N&..'" """
    items = []
    for row in _rows(html):
        m = re.search(r"view\.do\?article_seq=(\d+)", row)
        a = re.search(r"<a\b[^>]*>(.*?)</a>", row, flags=re.S | re.I)
        if not m or not a:
            continue
        dates = _DATE.findall(_text(row))
        date = tuple(int(x) for x in dates[-1]) if dates else None
        items.append(_item(_text(a.group(1)), urljoin(base, f"./view.do?article_seq={m.group(1)}"), date))
    return items


def parse_motir(html: str, base: str) -> list[dict]:
    """산업통상부(motir.go.kr): <a href="/kor/article/ATCLxxxx/번호/view?..."><i>제목</i></a>"""
    items = []
    for row in _rows(html):
        a = re.search(r'<a\b[^>]*href="(/kor/article/ATCL\w+/\d+/view)[^"]*"[^>]*>(.*?)</a>', row, flags=re.S | re.I)
        if not a:
            continue
        d = re.search(r"<td[^>]*>\s*<i>(.*?)</i>\s*</td>", row, flags=re.S | re.I)
        items.append(_item(_text(a.group(2)), urljoin(base, a.group(1)), _date_of(_text(row)), _text(d.group(1)) if d else ""))
    return items


def parse_opinion(html: str, base: str) -> list[dict]:
    """국민참여입법센터(opinion.lawmaking.go.kr) 입법예고: 소관부처, 의견접수 시작일"""
    items = []
    for row in _rows(html):
        a = re.search(r'<a\b[^>]*href="(/gcom/ogLmPp/\d+)"[^>]*>(.*?)</a>', row, flags=re.S | re.I)
        if not a:
            continue
        dept = re.search(r'data-th="소관부처[^"]*">\s*<p>(.*?)</p>', row, flags=re.S | re.I)
        period = re.search(r'data-th="입법의견 접수기간">(.*?)</td>', row, flags=re.S | re.I)
        date = _date_of(_text(period.group(1))) if period else None   # 접수 시작일을 게시일로 본다
        items.append(_item(_text(a.group(2)), urljoin(base, a.group(1)), date, _text(dept.group(1)) if dept else ""))
    return items


def parse_gir(html: str, base: str) -> list[dict]:
    """온실가스종합정보센터(gir.go.kr): <a href="/home/board/read.do;jsessionid=..?menuId=..&boardId=..&boardMasterId=..">"""
    items, seen = [], set()
    origin = "{0.scheme}://{0.netloc}".format(urlsplit(base))
    for row in _rows(html):
        a = re.search(r'<a\b[^>]*href="([^"]*board/read\.do[^"]*)"[^>]*>(.*?)</a>', row, flags=re.S | re.I)
        if not a:
            continue
        q = parse_qs(urlsplit(unescape(a.group(1))).query)
        board_id = (q.get("boardId") or [""])[0]
        if not board_id or board_id in seen:
            continue
        seen.add(board_id)
        url = f"{origin}/home/board/read.do?menuId={(q.get('menuId') or [''])[0]}" \
              f"&boardMasterId={(q.get('boardMasterId') or [''])[0]}&boardId={board_id}"
        cells = _cells(row)
        dept = _text(cells[2]) if len(cells) > 2 else ""
        items.append(_item(_text(a.group(2)), url, _date_of(_text(row)), dept))
    return items


def parse_mofa(html: str, base: str) -> list[dict]:
    """외교부(mofa.go.kr): <a href="./view.do?seq=N&page=1"> 제목 </a>, 끝에서 두 번째 칸이 부서, 마지막 칸이 날짜"""
    items = []
    for row in _rows(html):
        a = re.search(r'<a\b[^>]*href="\./view\.do\?seq=(\d+)[^"]*"[^>]*>(.*?)</a>', row, flags=re.S | re.I)
        if not a:
            continue
        title = re.sub(r"^NEW\s+", "", _text(a.group(2)))   # 새 글 배지 제거
        cells = _cells(row)
        dept = _text(cells[-2]) if len(cells) >= 2 else ""
        items.append(_item(title, urljoin(base, f"./view.do?seq={a.group(1)}"), _date_of(_text(row)), dept))
    return items


def parse_mofe(html: str, base: str) -> list[dict]:
    """재정경제부(mofe.go.kr): <li><h3><a href="javascript:fn_egov_select('글번호')">제목</a></h3> + 날짜·부서.
    상세 주소는 페이지 스크립트가 만드는 규칙을 따른다 (보도자료: /nw/nes/detailNesDtaView.do, 입법예고: /lw/lap/detailTbPrvntcView.do)."""
    parts = urlsplit(base)
    q = parse_qs(parts.query)
    bbs_id, menu_no = (q.get("bbsId") or [""])[0], (q.get("menuNo") or [""])[0]
    origin = f"{parts.scheme}://{parts.netloc}"
    items = []
    pattern = re.compile(r"""<h3>\s*<a\b[^>]*href=["']javascript:fn_egov_select\(\s*['"](\w+)['"]\s*\);?["'][^>]*>(.*?)</a>\s*</h3>""",
                         flags=re.S | re.I)
    for m in pattern.finditer(html):
        ntt = m.group(1)
        tail = html[m.end(): m.end() + 700]                      # 같은 항목의 날짜·부서 영역
        dept = re.search(r'<span class="depart">(.*?)</span>', tail, flags=re.S)
        if "/lw/lap/" in parts.path:
            url = f"{origin}/lw/lap/detailTbPrvntcView.do?bbsId={bbs_id}&searchNttId1={ntt}&menuNo={menu_no}"
        else:
            url = f"{origin}/nw/nes/detailNesDtaView.do?searchBbsId1={bbs_id}&searchNttId1={ntt}&menuNo={menu_no}"
        items.append(_item(_text(m.group(2)), url, _date_of(_text(tail)), _text(dept.group(1)) if dept else ""))
    return items


PARSERS = {"mcee": parse_mcee, "keco": parse_keco, "motir": parse_motir, "opinion": parse_opinion,
           "gir": parse_gir, "mofa": parse_mofa, "mofe": parse_mofe}


# ----------------------------------------------------------------- 수집기
class OfficialBoardSource(Source):
    name = "official_boards"

    def __init__(self, boards=None, client: PoliteClient | None = None, keywords=None):
        super().__init__()
        self.boards = boards if boards is not None else config.BOARDS
        self.client = client or PoliteClient()
        self.keywords = keywords if keywords is not None else config.OFFICIAL_KEYWORDS

    def fetch(self) -> list[Article]:
        self.failures = []
        articles: list[Article] = []
        for b in self.boards:
            label = f"{b['agency']} {b['name']}"
            resp = self.client.get(b["url"])
            if resp is None:
                self.failures.append(label)
                continue
            try:
                items = PARSERS[b["parser"]](resp.text, b["url"])
            except Exception as e:
                log.warning("%s 파싱 오류: %s", label, e)
                self.failures.append(label)
                continue
            if not items:
                # 글이 0건이면 사이트 구조가 바뀌었을 가능성이 크다. 조용히 넘기지 않고 실패로 기록한다.
                log.warning("%s: 목록에서 글을 찾지 못함 (사이트 구조 변경 가능성)", label)
                self.failures.append(label)
                continue
            kept = 0
            for it in items:
                if b.get("filter") and not matches_keywords(it["title"], self.keywords):
                    continue
                d = it["date"]
                published = kst_date_to_utc_iso(*d) if d else datetime.now(timezone.utc).isoformat()
                articles.append(Article(
                    title=it["title"], url=canonical_url(it["url"]), source=b["agency"], lang="ko",
                    query=b["name"], summary=it["dept"], published=published,
                    source_type="official", agency=b["agency"],
                ))
                kept += 1
            log.info("%s: 글 %d건 중 관련 %d건", label, len(items), kept)
        return articles

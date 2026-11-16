from carbon.sources import boards
from carbon.sources.boards import OfficialBoardSource

# 실제 사이트에서 확인한 행 구조를 줄인 샘플 -------------------------------------------------
MCEE = """<table><tr><th>번호</th><th>제목</th></tr>
<tr style="text-align : center;"> <td><span>18979</span></td> <td class="al"> <!-- -->
<a title="제3차 고준위 방사성폐기물 관리 기본계획 수립을 위한 국민 의견수렴 추진"
 href="/home/web/board/read.do;jsessionid=3RJp.mehome2?pagerOffset=0&amp;maxPageItems=10&amp;menuId=10598&amp;orgCd=&amp;boardId=1903710&amp;boardMasterId=939&amp;decorator=" class="ellipsis"> &nbsp;제3차 고준위 ... </a>
<span class="brdIcon"><img src="/new.gif" alt="새글" /></span> </td>
<td> <!-- 고정형 부서명 --> 고준위방사성폐기물관리위원회 <!-- //고정형 --> </td> <td> 현지영 </td> <td>2026-11-03</td> <td>103</td> </tr>
<tr><td>1</td><td><a title="2035 국가 온실가스 감축목표(NDC) 이행 점검" href="/home/web/board/read.do?menuId=10598&amp;boardId=1903700&amp;boardMasterId=939">x</a></td>
<td>기후전략과</td><td>김</td><td>2026-11-02</td><td>9</td></tr>
<tr><td>dup</td><td><a title="중복 글" href="/home/web/board/read.do?menuId=10598&amp;boardId=1903700&amp;boardMasterId=939">x</a></td><td>-</td><td>-</td><td>2026-11-02</td></tr>
</table>"""

KECO = """<tbody><tr> <td class="none"> 1442 </td> <td class="tit_new">
<a href="javascript:;" onclick="location.href='./view.do?article_seq=100839&amp;cpage=1&amp;rows=10&amp;condition=&amp;keyword='">
 (한국환경공단 보도자료 11.2.) 한국환경공단, 환경분야 해외사업 확대를 위한 '인프라 파트너스' 출범 </a>
<img src="/new.png" alt="최신게시물" /> </td> <td>박성환</td> <td class="none"><div class="file_box"><span>(3)</span></div></td>
<td class="none">2026-11-02</td> </tr></tbody>"""

MOTIR = """<tbody><tr> <td> 30,194 </td> <td><span class="badge-category"><i>보도자료</i></span></td>
<td class="ta-l"><div class="board-link">
<a href="/kor/article/ATCL3f49a5a8c/172373/view?mno=&amp;pageIndex=1" onclick="article.view('172373'); return false;">
<i>대한민국 제조업 판 바꾼다... 산업부, 제조AI 4단계 확산전략 가동</i></a></div></td>
<td><i>산업인공지능정책과</i></td> <td>2026-11-03</td> <td>91</td> <td><a href="/attach/down/abc">pdf</a></td> </tr></tbody>"""

OPINION = """<tbody><!-- 목록 있을때 --><tr>
<td data-th="번호" class="reHide">184</td>
<td data-th="법령 제명" class="subject"><a href="/gcom/ogLmPp/89288" title="온실가스 감축 시행규칙 일부개정령안 입법예고">온실가스 감축 시행규칙 일부개정령안 입법예고</a><span>일부</span></td>
<td data-th="소관부처 (법령종류)"> <p>기후에너지환경부</p> <p>(부령)</p> </td>
<td data-th="입법의견 접수기간"> <p>2026. 11. 3.</p><p>~2026. 11. 10.</p> </td>
<td data-th="조회수">477</td></tr></tbody>"""


GIR = """<table><tr><th>번호</th></tr>
<tr> <td> 174 </td> <td class="tit"> <a href="/home/board/read.do;jsessionid=XYQp.og_was2_servlet_engine1?pagerOffset=0&amp;maxPageItems=10&amp;searchKey=&amp;searchValue=&amp;menuId=11&amp;boardId=2035&amp;boardMasterId=4&amp;boardCategoryId=&amp;pagerOffset=">
 투명성이 이끄는 기후행동 주제로 기후위기 대응 전담 연구기관 역할 논의 </a> </td> <td>기획총괄</td> <td>2026-09-28</td> <td>1,439</td> </tr>
<tr> <td> 173 </td> <td class="tit"> <a href="/home/board/read.do?menuId=11&amp;boardId=2034&amp;boardMasterId=4"> 2025년도 국가 온실가스 잠정배출량 6억 8,571만톤 </a> </td>
<td>기획총괄팀</td> <td>2026-09-21</td> <td>3,010</td> </tr></table>"""

MOFA = """<table><tbody>
<tr> <td><div>22844</div></td> <!-- 번호 --> <td> <div> <a href="./view.do?seq=377720&page=1&pitem=10" onclick="javascript:f_view('377720'); return false;">
<span class="krds-badge outline-primary">NEW</span> 외교부, 기후변화 대응 관련 본부-공관 합동 상황점검회의 개최 </a> </div> </td>
<!-- 첨부 S --> <td> <div> <span class="file"><img src="/i.png" alt="첨부파일"></span> </div> </td> <!-- 첨부 E -->
<td><div> <!-- 부서명 split --> 기후변화외교과 </div></td> <!-- 부서명 --> <td><div> <span class="date"> 2026-11-03</span> </div></td> <!-- 작성일 --> </tr>
<tr> <td> <div>1074</div> </td><!-- 번호 --> <!-- <td class="tal"> --> <td> <div> <a href="./view.do?seq=368090&page=1" onclick="f_view('368090');">
 [보도자료]에너지 전환·환경 보호 등 한-유럽연합(EU) 그린 파트너십 심화 </a> </div> </td>
<!-- <td class="tb_show"> --><td> <div> 기후변화외교과 </div> </td><!-- 부서명 --> <!-- <td class="tb_show"> --> <td> <div> 2026-10-21 </div> </td> </tr>
</tbody></table>"""

MOFE_PRESS = """<ul class="boardType3 explnList"> <!-- 리스트 목록 -->
<li> <h3><a href="javascript:fn_egov_select('MOSF_000000000079837');">국제 신용평가사 Fitch, 한국 연례협의 실시</a></h3>
<div class="boardInfo"> <div class="infoLeft"> <span class="date">2026.11.03.</span> <span class="depart">국제금융과</span> </div> </div></li>
<li> <h3><a href="javascript:fn_egov_select('MOSF_000000000079839');">탄소국경조정제도 대응 세제 지원 방안</a></h3>
<div class="boardInfo"> <div class="infoLeft"> <span class="date">2026.11.02.</span> <span class="depart">조세특례제도과</span> </div> </div></li></ul>"""

MOFE_LAW = """<ul class="boardType3"> <li> <h3><a href='javascript:fn_egov_select("MOSF_000000000079842");' title="「소득세법 시행령」 일부개정령(안) 입법예고" >「소득세법 시행령」 일부개정령(안) 입법예고</a></h3>
<div class="boardInfo"> <div class="infoLeft"> <span class="date">예고기간 : 2026.11.03. - 2026.12.14. </span> <span class="depart">소득법인세정책관</span> </div></div></li></ul>"""


def test_parse_gir_builds_canonical_url_and_dedupes_session_params():
    items = boards.parse_gir(GIR, "https://www.gir.go.kr/home/index.do?menuId=11")
    assert len(items) == 2
    assert items[0]["url"] == "https://www.gir.go.kr/home/board/read.do?menuId=11&boardMasterId=4&boardId=2035"
    assert items[0]["title"].startswith("투명성이 이끄는 기후행동")
    assert items[0]["dept"] == "기획총괄" and items[0]["date"] == (2026, 9, 28)


def test_parse_mofa_ignores_comment_cells_and_new_badge():
    items = boards.parse_mofa(MOFA, "https://www.mofa.go.kr/www/brd/m_4080/list.do")
    assert len(items) == 2
    assert items[0]["title"] == "외교부, 기후변화 대응 관련 본부-공관 합동 상황점검회의 개최"      # 'NEW' 배지 제거
    assert items[0]["url"] == "https://www.mofa.go.kr/www/brd/m_4080/view.do?seq=377720"
    assert items[0]["dept"] == "기후변화외교과" and items[0]["date"] == (2026, 11, 3)
    assert items[1]["dept"] == "기후변화외교과" and items[1]["date"] == (2026, 10, 21)   # 주석 속 <td> 에 속지 않음


def test_parse_mofe_press_release_detail_url():
    items = boards.parse_mofe(MOFE_PRESS, "https://mofe.go.kr/nw/nes/nesdta.do?bbsId=MOSFBBS_000000000028&menuNo=4010100")
    assert len(items) == 2
    assert items[0]["url"] == ("https://mofe.go.kr/nw/nes/detailNesDtaView.do"
                               "?searchBbsId1=MOSFBBS_000000000028&searchNttId1=MOSF_000000000079837&menuNo=4010100")
    assert items[0]["dept"] == "국제금융과" and items[0]["date"] == (2026, 11, 3)


def test_parse_mofe_legislation_notice_uses_notice_start_date_and_its_own_detail_path():
    items = boards.parse_mofe(MOFE_LAW, "https://mofe.go.kr/lw/lap/TbPrvntcList.do?bbsId=MOSFBBS_000000000055&menuNo=7050300")
    assert len(items) == 1
    assert items[0]["url"] == ("https://mofe.go.kr/lw/lap/detailTbPrvntcView.do"
                               "?bbsId=MOSFBBS_000000000055&searchNttId1=MOSF_000000000079842&menuNo=7050300")
    assert items[0]["title"] == "「소득세법 시행령」 일부개정령(안) 입법예고"
    assert items[0]["date"] == (2026, 11, 3) and items[0]["dept"] == "소득법인세정책관"


def test_every_configured_board_has_a_known_parser():
    import config
    for b in config.BOARDS:
        assert b["parser"] in boards.PARSERS, b
        assert b["url"].startswith("https://")


class FakeResp:
    def __init__(self, text, url=""):
        self.text, self.url = text, url


class FakeClient:
    """PoliteClient 대역: 주소별 HTML 을 돌려주고, 없는 주소는 None(차단·실패)."""

    def __init__(self, pages):
        self.pages = pages

    def get(self, url, **kw):
        return FakeResp(self.pages[url], url) if url in self.pages else None


# 파서 --------------------------------------------------------------------------------------
def test_parse_mcee_extracts_title_url_dept_date_and_dedupes():
    items = boards.parse_mcee(MCEE, "https://mcee.go.kr/home/web/board/list.do?menuId=10598&boardMasterId=939")
    assert len(items) == 2                                     # 헤더 행 제외, 같은 boardId 중복 제거
    first = items[0]
    assert first["title"] == "제3차 고준위 방사성폐기물 관리 기본계획 수립을 위한 국민 의견수렴 추진"
    assert first["url"] == "https://mcee.go.kr/home/web/board/read.do?menuId=10598&boardMasterId=939&boardId=1903710"
    assert "jsessionid" not in first["url"]
    assert first["dept"] == "고준위방사성폐기물관리위원회"
    assert first["date"] == (2026, 11, 3)
    assert items[1]["dept"] == "기후전략과"


def test_parse_keco():
    items = boards.parse_keco(KECO, "https://www.keco.or.kr/web/lay1/bbs/S1T109C111/A/20/list.do")
    assert len(items) == 1
    assert items[0]["url"] == "https://www.keco.or.kr/web/lay1/bbs/S1T109C111/A/20/view.do?article_seq=100839"
    assert "인프라 파트너스" in items[0]["title"]
    assert items[0]["date"] == (2026, 11, 2)


def test_parse_motir():
    items = boards.parse_motir(MOTIR, "https://www.motir.go.kr/kor/article/ATCL3f49a5a8c")
    assert len(items) == 1
    assert items[0]["url"] == "https://www.motir.go.kr/kor/article/ATCL3f49a5a8c/172373/view"
    assert items[0]["title"].startswith("대한민국 제조업 판 바꾼다")
    assert items[0]["dept"] == "산업인공지능정책과"
    assert items[0]["date"] == (2026, 11, 3)


def test_parse_opinion_uses_comment_period_start_as_date():
    items = boards.parse_opinion(OPINION, "https://opinion.lawmaking.go.kr/gcom/ogLmPp")
    assert len(items) == 1
    assert items[0]["url"] == "https://opinion.lawmaking.go.kr/gcom/ogLmPp/89288"
    assert items[0]["dept"] == "기후에너지환경부"
    assert items[0]["date"] == (2026, 11, 3)


# 수집기 ------------------------------------------------------------------------------------
BOARD_URL = "https://mcee.go.kr/home/web/board/list.do?menuId=10598&boardMasterId=939"


def board(**kw):
    return {"agency": "기후에너지환경부", "name": "보도자료", "parser": "mcee", "url": BOARD_URL, **kw}


def test_source_builds_official_articles_with_kst_date():
    src = OfficialBoardSource([board(filter=False)], client=FakeClient({BOARD_URL: MCEE}))
    arts = src.fetch()
    assert len(arts) == 2 and src.failures == []
    a = arts[0]
    assert a.source_type == "official" and a.agency == "기후에너지환경부" and a.query == "보도자료"
    assert a.published == "2026-11-02T15:00:00+00:00"           # 2026-11-03 00:00 KST
    assert a.summary == "고준위방사성폐기물관리위원회"


def test_keyword_filter_keeps_only_related_titles():
    src = OfficialBoardSource([board(filter=True)], client=FakeClient({BOARD_URL: MCEE}),
                              keywords=["온실가스", "ndc"])
    arts = src.fetch()
    assert [a.title for a in arts] == ["2035 국가 온실가스 감축목표(NDC) 이행 점검"]


def test_blocked_or_unreachable_board_is_recorded_as_failure_and_others_continue():
    other = {"agency": "한국환경공단", "name": "보도자료", "parser": "keco",
             "url": "https://www.keco.or.kr/x/list.do", "filter": False}
    src = OfficialBoardSource([board(), other], client=FakeClient({other["url"]: KECO}))
    arts = src.fetch()
    assert src.failures == ["기후에너지환경부 보도자료"]
    assert len(arts) == 1 and arts[0].agency == "한국환경공단"


def test_zero_parsed_rows_is_failure_not_silent():
    """사이트 구조가 바뀌어 글을 못 찾으면 조용히 넘어가지 않고 실패로 기록한다."""
    src = OfficialBoardSource([board()], client=FakeClient({BOARD_URL: "<html><body>개편됨</body></html>"}))
    assert src.fetch() == []
    assert src.failures == ["기후에너지환경부 보도자료"]

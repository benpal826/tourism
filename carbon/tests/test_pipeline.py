from carbon import pipeline
from carbon.sources.base import official_id
from carbon.tagging import tag_text
from tests.conftest import FakeSource, make_article


def test_tagging_ko_and_en():
    topics, regions = tag_text("EU, CBAM 전환기간 연장 논의")
    assert "CBAM/탄소국경" in topics
    assert "EU" in regions
    topics, _ = tag_text("Korea ETS allowance auction")
    assert "배출권거래제(ETS)" in topics


def test_collect_saves_tags_and_dedupes(conn):
    arts = [
        make_article("배출권거래제 개편 - A신문", query="q1"),
        make_article("배출권거래제 개편 - B신문", query="q2"),   # 같은 제목, 다른 언론사 → 중복
        make_article("CBAM 탄소국경 시행", query="q2"),
    ]
    res = pipeline.collect([FakeSource(arts)], conn=conn)
    assert res["new_total"] == 2
    assert res["by_query"]["q2"] == {"fetched": 2, "new": 1}
    rows = conn.execute("SELECT title,topics FROM articles ORDER BY title").fetchall()
    assert len(rows) == 2
    assert any("CBAM/탄소국경" in r["topics"] for r in rows)


def test_second_run_adds_nothing(conn):
    src = FakeSource([make_article("탄소세 도입 논의")])
    assert pipeline.collect([src], conn=conn)["new_total"] == 1
    assert pipeline.collect([src], conn=conn)["new_total"] == 0
    assert conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0] == 1


def official(title, url, agency="기후에너지환경부"):
    a = make_article(title, url=url, source=agency)
    a.source_type, a.agency = "official", agency
    a.id = official_id(url)
    return a


def test_official_documents_are_identified_by_url_not_title(conn):
    arts = [
        official("공고", "https://mcee.go.kr/board/read.do?boardId=1"),
        official("공고", "https://www.keco.or.kr/view.do?article_seq=9", agency="한국환경공단"),   # 같은 제목, 다른 기관
        official("공고", "https://mcee.go.kr/board/read.do;jsessionid=ABC?boardId=1"),            # 세션 아이디만 다른 같은 글
    ]
    res = pipeline.collect([FakeSource(arts)], conn=conn)
    assert res["new_total"] == 2
    rows = conn.execute("SELECT agency, source_type FROM articles ORDER BY agency").fetchall()
    assert [(r["agency"], r["source_type"]) for r in rows] == [("기후에너지환경부", "official"), ("한국환경공단", "official")]


def test_official_documents_get_stage_and_impact_at_insert(conn):
    pipeline.collect([FakeSource([
        official("배출권거래제 4기 할당계획 입법예고", "https://x.test/1"),
        official("COP31 합의문 채택", "https://x.test/2"),
    ])], conn=conn)
    rows = {r["title"]: r for r in conn.execute("SELECT * FROM articles")}
    a = rows["배출권거래제 4기 할당계획 입법예고"]
    assert (a["policy_stage"], a["domestic_impact"], a["impact_keyword"]) == ("proposed", "direct", "배출권거래제")
    assert a["impact_score"] == 95
    b = rows["COP31 합의문 채택"]
    assert (b["domestic_impact"], b["impact_keyword"]) == ("reference", "cop")


def test_reclassify_applies_changed_weights(conn):
    pipeline.collect([FakeSource([official("자발적 탄소시장 활성화 방안", "https://x.test/3")])], conn=conn)
    assert conn.execute("SELECT domestic_impact FROM articles").fetchone()[0] == "reference"
    from carbon import weights
    weights.ensure_seeds(conn)
    conn.execute("UPDATE keyword_weights SET final_weight=80 WHERE keyword='자발적 탄소시장'")   # 가중치가 올랐다고 가정
    conn.commit()
    assert pipeline.reclassify_official(conn) == 1
    assert conn.execute("SELECT domestic_impact FROM articles").fetchone()[0] == "direct"


class BrokenSource(FakeSource):
    name = "broken"

    def fetch(self):
        raise RuntimeError("사이트 폭발")


def test_a_crashing_source_does_not_stop_the_others(conn):
    res = pipeline.collect([BrokenSource([]), FakeSource([make_article("탄소세 도입")])], conn=conn)
    assert res["new_total"] == 1
    assert "broken" in res["failed"]


def test_failures_are_reported(conn):
    res = pipeline.collect([FakeSource([], failures=["bad-query"])], conn=conn)
    assert res["failed"] == ["bad-query"]

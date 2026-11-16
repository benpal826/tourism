import csv
from datetime import date

import pytest

import main
from carbon import query
from tests.conftest import NOW


def add(conn, aid, title, published, topics="", regions="", source_type="news", relevant=None, tier=2, summary="",
        llm_topics=None, llm_summary=None, agency=None, stage=None, impact=None):
    conn.execute(
        "INSERT INTO articles (id,title,url,source,lang,published,collected,summary,topics,regions,source_type,agency,source_tier,"
        "relevant,llm_topics,llm_regions,llm_summary,llm_done_at,policy_stage,domestic_impact) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (aid, title, f"https://example.com/{aid}", "언론사", "ko", published, NOW.isoformat(), summary, topics, regions,
         source_type, agency, tier, relevant, llm_topics, regions if llm_topics is not None else None, llm_summary,
         NOW.isoformat() if llm_topics is not None else None, stage, impact))
    conn.commit()


def ids(items):
    return [x["id"] for x in items]


@pytest.fixture
def sample(conn):
    # KST 날짜 경계 확인용: UTC 11-01 15:00 = KST 11-02 00:00
    add(conn, "a", "EU CBAM 기본값 개정", "2026-11-01T15:00:00+00:00", topics="CBAM/탄소국경", regions="EU")
    add(conn, "b", "한국 배출권 할당", "2026-11-01T14:59:00+00:00", topics="배출권거래제(ETS)", regions="한국")  # KST 11-01 23:59
    add(conn, "c", "EU ETS price record", "2026-11-03T01:00:00+00:00", topics="배출권거래제(ETS)", regions="EU",
        summary="Carbon allowance prices rose")
    add(conn, "d", "무관 기사 CBAM", "2026-11-02T01:00:00+00:00", topics="CBAM/탄소국경", regions="EU", relevant=0)
    add(conn, "e", "LLM 이 고친 주제", "2026-11-02T02:00:00+00:00", topics="CBAM/탄소국경", regions="EU",
        llm_topics="감축목표/NDC", llm_summary="NDC 이행 점검 요약")
    add(conn, "o", "배출권 할당계획 고시", "2026-11-02T03:00:00+00:00", topics="배출권거래제(ETS)", regions="한국",
        source_type="official", tier=1, agency="기후에너지환경부", stage="decided", impact="direct")
    return conn


def test_no_conditions_returns_all_relevant_newest_first(sample):
    assert ids(query.find(sample, query.make_filters())) == ["c", "o", "e", "a", "b"]   # 무관(d)은 제외


def test_date_range_uses_kst_days_inclusive(sample):
    f = query.make_filters(date_from="2026-11-02", date_to="2026-11-02")
    assert ids(query.find(sample, f)) == ["o", "e", "a"]
    assert ids(query.find(sample, query.make_filters(date_to="2026-11-01"))) == ["b"]
    assert ids(query.find(sample, query.make_filters(date_from="2026-11-03"))) == ["c"]


def test_topic_region_and_combination(sample):
    assert ids(query.find(sample, query.make_filters(topic="CBAM/탄소국경"))) == ["a"]     # e 는 LLM 주제를 따름
    assert ids(query.find(sample, query.make_filters(topic="NDC"))) == ["e"]              # 일부 이름
    assert ids(query.find(sample, query.make_filters(region="한국"))) == ["o", "b"]
    f = query.make_filters(topic="ETS", region="EU", date_from="2026-11-03")
    assert ids(query.find(sample, f)) == ["c"]


def test_keyword_searches_title_and_summaries_case_insensitive(sample):
    assert ids(query.find(sample, query.make_filters(keyword="cbam"))) == ["a"]
    assert ids(query.find(sample, query.make_filters(keyword="ALLOWANCE"))) == ["c"]     # RSS 요약
    assert ids(query.find(sample, query.make_filters(keyword="이행 점검"))) == ["e"]     # LLM 요약
    assert ids(query.find(sample, query.make_filters(keyword="100%"))) == []


def test_search_limit(conn):
    for i in range(25):
        add(conn, f"x{i:02d}", f"배출권 기사 {i}", f"2026-11-02T{i % 24:02d}:00:00+00:00")
    assert len(query.find(conn, query.make_filters(keyword="배출권"), limit=query.SEARCH_LIMIT)) == 20


def test_invalid_conditions_raise():
    with pytest.raises(query.QueryError):
        query.make_filters(date_from="2026/11/01")
    with pytest.raises(query.QueryError):
        query.make_filters(date_from="2026-11-05", date_to="2026-11-01")
    with pytest.raises(query.QueryError, match="없는 지역"):
        query.make_filters(region="남극")
    with pytest.raises(query.QueryError, match="여러 개"):
        query.make_filters(topic="탄소")       # 탄소가격/탄소세, 자발적 탄소시장/크레딧
    assert query.make_filters(region="eu").region == "EU"


def test_matches_is_reusable_on_items():
    item = {"title": "EU CBAM", "published": "2026-11-02T09:00:00+09:00", "topics": ["CBAM/탄소국경"], "regions": ["EU"]}
    assert query.matches(item, query.Filters(date_from=date(2026, 11, 2), topic="CBAM/탄소국경", keyword="cbam"))
    assert not query.matches(item, query.Filters(region="한국"))


def test_official_columns_and_news_columns(sample):
    items = {x["id"]: x for x in query.find(sample, query.make_filters())}
    o, c = items["o"], items["c"]
    assert (o["kind"], o["source"], o["policy_stage"], o["domestic_impact"], o["source_tier"]) == \
        ("공식", "기후에너지환경부", "확정", "직접 규제", "공식")
    # 뉴스 제목으로는 정책 단계·영향도를 판정하지 않는다
    assert (c["kind"], c["policy_stage"], c["domestic_impact"], c["official_status"]) == ("뉴스", "", "", "공식 확인 안 됨")


def test_export_csv_utf8_sig_and_formula_guard(conn, tmp_path):
    add(conn, "a", "EU CBAM 기본값 개정", "2026-11-02T01:00:00+00:00", topics="CBAM/탄소국경,산업·기업 영향", regions="EU")
    add(conn, "f", "=HYPERLINK(\"http://x\") 배출권", "2026-11-02T02:00:00+00:00")
    out = tmp_path / "sub" / "out.csv"
    query.export_csv(query.find(conn, query.make_filters()), out)
    raw = out.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")                      # Excel 이 UTF-8 로 인식하는 BOM
    rows = list(csv.reader(out.open(encoding="utf-8-sig")))
    assert rows[0] == [label for _, label in query.EXPORT_COLUMNS]
    assert rows[1][2].startswith("'=HYPERLINK")                  # 수식으로 실행되지 않게
    assert rows[2][2] == "EU CBAM 기본값 개정" and rows[2][5] == "CBAM/탄소국경, 산업·기업 영향"
    assert rows[1][0] == "2026-11-02 11:00"                      # KST, 분까지


def test_cli_export_and_search(sample, tmp_path, monkeypatch, capsys):
    import config
    db_path = tmp_path / "test.db"     # conftest 의 conn 과 같은 파일
    monkeypatch.setattr(config, "DB_PATH", db_path)
    monkeypatch.setattr(config, "LOG_DIR", tmp_path / "logs")
    out = tmp_path / "e.csv"
    assert main.main(["export", "--from", "2026-11-02", "--to", "2026-11-02", "--topic", "CBAM", "--out", str(out)]) == 0
    rows = list(csv.reader(out.open(encoding="utf-8-sig")))
    assert len(rows) == 2 and rows[1][2] == "EU CBAM 기본값 개정"
    assert main.main(["search", "배출권"]) == 0
    printed = capsys.readouterr().out
    assert "2건" in printed and "배출권 할당계획 고시" in printed and "한국 배출권 할당" in printed
    assert main.main(["export", "--region", "남극"]) == 2

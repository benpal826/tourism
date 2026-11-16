from carbon import analysis, pipeline
from carbon.sources.base import official_id
from tests.conftest import NOW, FakeSource, make_article

TOP_KEYS = {"generated_at", "period_days", "total_articles", "per_day", "topics",
            "regions", "rising_terms", "rising_basis", "articles", "official", "policy_summary", "excluded_tier3",
            "agencies", "agencies_note", "excluded_count", "briefing", "llm_stats", "daily_summary"}


def load(conn, articles):
    pipeline.collect([FakeSource(articles)], conn=conn)


def test_empty_db_returns_full_shape(conn):
    data = analysis.build_report_data(conn=conn, now=NOW)
    assert set(data) == TOP_KEYS
    assert data["total_articles"] == 0
    assert len(data["per_day"]) == 7 and all(d["count"] == 0 for d in data["per_day"])
    assert data["articles"] == [] and data["rising_terms"] == []


def test_keys_and_types(conn):
    load(conn, [
        make_article("EU CBAM 탄소국경 전환기간 논의", days_ago=0.2, source="연합"),
        make_article("한국 배출권거래제 4기 계획", days_ago=3),
        make_article("너무 오래된 기사 탄소", days_ago=30),
    ])
    d = analysis.build_report_data(conn=conn, now=NOW)
    assert d["total_articles"] == 2                      # 30일 전 기사는 제외
    assert isinstance(d["generated_at"], str) and d["period_days"] == 7
    assert all(set(x) == {"date", "count"} and isinstance(x["count"], int) for x in d["per_day"])
    assert sum(x["count"] for x in d["per_day"]) == 2
    t = {x["name"]: x for x in d["topics"]}
    assert t["CBAM/탄소국경"]["count_7d"] == 1 and t["CBAM/탄소국경"]["count_1d"] == 1
    assert t["배출권거래제(ETS)"]["count_1d"] == 0
    assert {r["name"] for r in d["regions"]} >= {"EU", "한국"}
    a = d["articles"][0]
    assert set(a) == {"title", "url", "source", "published", "lang", "topics", "regions",
                      "official_status", "official_links", "source_tier", "source_tier_reason",
                      "single_source", "sensational", "summary", "ai_impact"}
    assert a["title"].startswith("EU CBAM")              # 최신순
    assert isinstance(a["topics"], list)


def test_dates_are_bucketed_and_shown_in_kst(conn):
    # UTC 11-02 16:00 = KST 11-03 01:00 → KST 기준으로는 11-03 에 집계돼야 한다
    a = make_article("KST 경계 기사 탄소", days_ago=0)
    a.published = "2026-11-02T16:00:00+00:00"
    load(conn, [a])
    d = analysis.build_report_data(conn=conn, now=NOW)       # NOW = UTC 11-03 12:00 = KST 21:00
    assert d["generated_at"] == "2026-11-03T21:00:00+09:00"
    assert {x["date"]: x["count"] for x in d["per_day"]}["2026-11-03"] == 1
    assert d["per_day"][-1]["date"] == "2026-11-03"
    assert d["articles"][0]["published"] == "2026-11-03T01:00:00+09:00"


def official_article(title, url, days_ago=0.5, agency="기후에너지환경부"):
    a = make_article(title, days_ago=days_ago, source=agency, query="보도자료", url=url)
    a.source_type, a.agency = "official", agency
    a.id = official_id(url)
    return a


def test_official_documents_are_listed_separately_from_news(conn):
    load(conn, [
        make_article("배출권거래제 4기 개편 뉴스", days_ago=0.3),
        official_article("배출권거래제 4기 할당계획 보도자료", "https://mcee.go.kr/a"),
        official_article("한 달 전 공식 발표 온실가스", "https://mcee.go.kr/old", days_ago=20),
    ])
    d = analysis.build_report_data(conn=conn, now=NOW)
    assert [a["title"] for a in d["articles"]] == ["배출권거래제 4기 개편 뉴스"]      # 뉴스 목록에는 공식 문서 제외
    titles = [o["title"] for o in d["official"]]
    assert sorted(titles) == sorted(["배출권거래제 4기 할당계획 보도자료", "한 달 전 공식 발표 온실가스"])   # 공식은 30일까지
    assert set(d["official"][0]) == {"title", "url", "agency", "board", "published", "topics",
                                     "stage", "impact", "impact_score", "impact_keyword", "summary", "ai_impact"}
    assert d["official"][0]["agency"] == "기후에너지환경부"
    assert d["total_articles"] == 2                                                   # 7일 집계에는 뉴스+공식 모두 포함


def test_official_sorted_by_impact_then_stage_then_newest(conn):
    items = [
        ("COP 합의 확정", "https://x/1", 0.1, "decided", "reference"),           # 최신이지만 영향도가 낮다
        ("배출권거래제 개편 검토", "https://x/2", 3, "proposed", "direct"),
        ("배출권거래제 할당 고시", "https://x/3", 5, "decided", "direct"),        # 오래됐지만 직접 규제 + 확정
        ("온실가스 감축 사업 안내", "https://x/4", 0.2, "unknown", "indirect"),
        ("배출권거래제 시행령 개정 확정", "https://x/5", 1, "decided", "direct"),
    ]
    arts = []
    for title, url, days, stage, impact in items:
        a = official_article(title, url, days_ago=days)
        arts.append(a)
    pipeline.collect([FakeSource(arts)], conn=conn)
    for title, url, days, stage, impact in items:      # 규칙 판정 대신 기대 정렬을 시험하려고 값을 직접 지정
        conn.execute("UPDATE articles SET policy_stage=?, domestic_impact=? WHERE title=?", (stage, impact, title))
    conn.commit()
    order = [o["title"] for o in analysis.build_report_data(conn=conn, now=NOW)["official"]]
    assert order == ["배출권거래제 시행령 개정 확정",    # direct + decided, 더 최신
                     "배출권거래제 할당 고시",           # direct + decided
                     "배출권거래제 개편 검토",           # direct + proposed
                     "온실가스 감축 사업 안내",          # indirect
                     "COP 합의 확정"]                    # reference


def test_news_has_no_stage_or_impact(conn):
    load(conn, [make_article("배출권거래제 4기 할당계획 입법예고 뉴스")])
    row = conn.execute("SELECT policy_stage, domestic_impact, impact_score FROM articles").fetchone()
    assert (row["policy_stage"], row["domestic_impact"], row["impact_score"]) == (None, None, None)


def test_articles_limited_to_60_newest(conn):
    load(conn, [make_article(f"탄소 기사 번호 {i}", days_ago=i * 0.01) for i in range(80)])
    d = analysis.build_report_data(conn=conn, now=NOW)
    assert d["total_articles"] == 80 and len(d["articles"]) == 60
    assert d["articles"][0]["title"] == "탄소 기사 번호 0"


def test_rising_terms_detects_spike_and_ignores_rare(conn):
    spike = [make_article(f"플라스틱세 논의 {i}", days_ago=0.1 * i + 0.1) for i in range(5)]
    steady = [make_article(f"배출권 가격 동향 {i}", days_ago=3 + i * 0.3) for i in range(5)]
    rare = [make_article("희귀단어 한번", days_ago=0.1)]
    load(conn, spike + steady + rare)
    terms = {t["term"]: t for t in analysis.build_report_data(conn=conn, now=NOW)["rising_terms"]}
    assert "플라스틱세" in terms and terms["플라스틱세"]["recent"] == 5
    assert terms["플라스틱세"]["ratio"] > 3
    assert "희귀단어" not in terms                        # 최근 2일 3회 미만
    assert "배출권" not in terms                          # 이전 기간에만 등장


def test_stopwords_and_outlet_suffix_excluded(conn):
    load(conn, [make_article(f"the 탄소세 {i} - 특수언론사", days_ago=0.1) for i in range(4)])
    terms = {t["term"] for t in analysis.build_report_data(conn=conn, now=NOW)["rising_terms"]}
    assert "the" not in terms and "특수언론사" not in terms and "탄소세" in terms


# ----------------------------------------------------------------------------- 오늘의 요약
import json  # noqa: E402

from tests.test_llm import official  # noqa: E402

OFF_DD = "배출권 할당계획 고시 시행"                     # 확정 · 직접 규제
OFF_PD = "온실가스 배출권의 할당 및 거래에 관한 법률 시행령 개정안 입법예고"   # 추진 · 직접 규제
OFF_UD = "탄소국경조정제도 대응 설명회 개최"              # 미분류 · 직접 규제


def _row(conn, title):
    return conn.execute("SELECT * FROM articles WHERE title=?", (title,)).fetchone()


def _ai(conn, conclusions, items, day="2026-11-03"):
    conn.execute("INSERT OR REPLACE INTO daily_summaries (day,conclusions,report_items,model,created_at,source_ids,classified) "
                 "VALUES (?,?,?,?,?,?,?)", (day, json.dumps(conclusions, ensure_ascii=False), json.dumps(items), "m", "", "[]", 0))
    conn.commit()


def test_source_priority_ai_then_briefing_then_rules(conn):
    load(conn, [official(OFF_DD, "https://me.go.kr/1", days_ago=0.5)])
    assert analysis.build_report_data(conn=conn, now=NOW)["daily_summary"]["source"] == "rules"
    conn.execute("INSERT INTO briefings (day,text) VALUES ('2026-11-03','브리핑 문단')")
    conn.commit()
    s = analysis.build_report_data(conn=conn, now=NOW)["daily_summary"]
    assert s["source"] == "briefing" and s["briefing_text"] == "브리핑 문단" and s["conclusions"] == []
    _ai(conn, ["AI 결론"], [])
    s = analysis.build_report_data(conn=conn, now=NOW)["daily_summary"]
    assert s["source"] == "ai" and s["conclusions"] == ["AI 결론"] and s["briefing_text"] is None


def test_old_ai_summary_is_not_used(conn):
    _ai(conn, ["어제 결론"], [], day="2026-11-02")
    assert analysis.build_report_data(conn=conn, now=NOW)["daily_summary"]["source"] == "rules"


def test_rules_conclusions_text(conn):
    load(conn, [official(OFF_DD, "https://me.go.kr/1", days_ago=0.5), official(OFF_UD, "https://me.go.kr/3", days_ago=0.5),
                official(OFF_PD, "https://me.go.kr/2", days_ago=3)])
    d = analysis.build_report_data(conn=conn, now=NOW)
    top = max(d["topics"], key=lambda t: t["count_1d"])
    expected = ["최근 1일 신규 공식 문서 2건 (확정·직접 규제 1건)."]
    if d["rising_terms"]:
        expected.append("급증 키워드: " + ", ".join(t["term"] for t in d["rising_terms"][:3]) + ".")
    expected.append(f"최근 1일 가장 많이 다룬 주제: {top['name']} ({top['count_1d']}건).")
    assert d["daily_summary"]["conclusions"] == expected


def test_rules_conclusions_empty_when_nothing(conn):
    s = analysis.build_report_data(conn=conn, now=NOW)["daily_summary"]
    assert s["conclusions"] == [] and s["report_items"] == []


def test_rules_report_items_order_and_why(conn):
    load(conn, [official(OFF_UD, "https://me.go.kr/3", days_ago=0.5), official(OFF_PD, "https://me.go.kr/2", days_ago=1),
                official(OFF_DD, "https://me.go.kr/1", days_ago=2),
                official("배출권 할당계획 고시 시행 (구)", "https://me.go.kr/9", days_ago=9)])      # 7일 밖
    items = analysis.build_report_data(conn=conn, now=NOW)["daily_summary"]["report_items"]
    assert [i["title"] for i in items] == [OFF_DD, OFF_PD, OFF_UD]
    assert [i["why"] for i in items] == ["확정 · 직접 규제", "추진 · 직접 규제", "미분류 · 직접 규제"]
    assert all(i["origin"] == "rules" for i in items) and items[0]["url"] == "https://me.go.kr/1"


def test_ai_summary_without_report_items_falls_back_to_rule_items(conn):
    load(conn, [official(OFF_DD, "https://me.go.kr/1", days_ago=0.5)])
    _ai(conn, ["AI 결론"], [])
    items = analysis.build_report_data(conn=conn, now=NOW)["daily_summary"]["report_items"]
    assert [i["origin"] for i in items] == ["rules"]


def test_ai_report_item_carries_related_news_count(conn):
    load(conn, [official(OFF_PD, "https://me.go.kr/2", days_ago=0.5)])
    oid = _row(conn, OFF_PD)["id"]
    for n in ("n1", "n2"):
        conn.execute("INSERT INTO article_links (news_id, official_id, score) VALUES (?,?,0.9)", (n, oid))
    _ai(conn, ["AI 결론"], [{"id": oid, "why": "시행령 개정 추진", "via_news": None}])
    items = analysis.build_report_data(conn=conn, now=NOW)["daily_summary"]["report_items"]
    assert items == [{**items[0], "id": oid, "why": "시행령 개정 추진", "origin": "ai", "related_news": 2,
                      "policy_stage": "proposed", "domestic_impact": "direct", "title": OFF_PD}]


def test_topic_flow_top5_by_7day_count_with_7_daily_counts(conn):
    load(conn, [make_article("EU CBAM 탄소국경 논의", days_ago=0.2, url="https://e.com/1"),
                make_article("CBAM 탄소국경 보고 의무", days_ago=2.2, url="https://e.com/2"),
                make_article("배출권거래제 4기 계획", days_ago=1.2, url="https://e.com/3")])
    d = analysis.build_report_data(conn=conn, now=NOW)
    flow = d["daily_summary"]["flow"]
    assert flow["dates"] == [x["date"] for x in d["per_day"]]
    assert [t["name"] for t in flow["topics"]] == [t["name"] for t in d["topics"][:5]]
    cbam = next(t for t in flow["topics"] if t["name"] == "CBAM/탄소국경")
    assert len(cbam["counts"]) == 7 and sum(cbam["counts"]) == 2 and cbam["counts"][-1] == 1

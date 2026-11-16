import json
from datetime import timedelta

import pytest

import config
from carbon import agencies, analysis, pipeline, render
from carbon.sources.base import official_id
from tests.conftest import NOW, FakeSource, make_article
from tests.test_render import data_with


def doc(title, url, agency, days_ago=2.0):
    a = make_article(title, days_ago=days_ago, url=url, source=agency)
    a.source_type, a.agency = "official", agency
    a.id = official_id(url)
    return a


def news(title, days_ago=0.5, source="A뉴스"):
    return make_article(title, days_ago=days_ago, source=source, url="https://n.test/" + title[:10])


def load(conn, arts):
    pipeline.collect([FakeSource(arts)], conn=conn)


def set_history(conn, days):
    """DB 에 쌓인 기간이 days 일인 것처럼 수집 시각을 벌려 놓는다."""
    rows = conn.execute("SELECT id FROM articles ORDER BY id").fetchall()
    for i, r in enumerate(rows):
        t = NOW - timedelta(days=days * i / max(len(rows) - 1, 1))
        conn.execute("UPDATE articles SET collected=? WHERE id=?", (t.isoformat(), r["id"]))
    conn.commit()


def corpus():
    """A: 탄소 관련 발표 많고(6) 직접 규제·확정이 많으며 뉴스가 다룸. B: 발표 적고(3) 추진뿐이며 뉴스 없음. C: 근거 부족(1)."""
    arts = []
    for i in range(6):
        title = f"배출권거래제 할당 기준 고시 {i}" if i < 4 else f"배출권거래제 개편 입법예고 {i}"
        arts.append(doc(title, f"https://a.test/{i}", "A기관", days_ago=1 + i * 0.3))
    for i in range(3):
        arts.append(doc(f"재생에너지 보급 확대 방안 {i} 검토", f"https://b.test/{i}", "B기관", days_ago=1 + i * 0.3))
    arts.append(doc("기후 관련 행사 안내 탄소", "https://c.test/0", "C기관"))
    return arts


# ----------------------------------------------------------------------------- 시드
def test_ensure_agencies_seeds_fixed_rank_and_kinds_without_touching_scores(conn):
    load(conn, corpus())
    agencies.ensure_agencies(conn)
    rows = {r["name"]: r for r in conn.execute("SELECT * FROM agencies")}
    assert rows["기후에너지환경부"]["fixed_rank"] == 1 and rows["기후에너지환경부"]["kind"] == "부처"
    assert rows["한국환경공단"]["kind"] == "산하·유관기관" and rows["A기관"]["kind"] == "기타"
    assert all(r["fixed_rank"] is None for n, r in rows.items() if n != "기후에너지환경부")
    conn.execute("UPDATE agencies SET score=77 WHERE name='A기관'")
    agencies.ensure_agencies(conn)
    assert conn.execute("SELECT score FROM agencies WHERE name='A기관'").fetchone()[0] == 77


# ----------------------------------------------------------------------------- 누적 부족
def test_short_history_computes_nothing_but_keeps_fixed_rank(conn):
    load(conn, corpus())
    set_history(conn, 3)
    res = agencies.rank_agencies(conn, now=NOW)
    assert res["status"] == "insufficient" and "누적 부족" in res["reason"] and res["history_days"] == 3
    assert conn.execute("SELECT COUNT(*) FROM agencies WHERE score IS NOT NULL").fetchone()[0] == 0
    ranking = agencies.ranking(conn)
    assert ranking[0]["name"] == "기후에너지환경부" and ranking[0]["rank"] == 1 and ranking[0]["fixed"]
    assert all(a["rank"] is None for a in ranking[1:])


# ----------------------------------------------------------------------------- 점수
def run_ranked(conn, extra=()):
    load(conn, corpus() + list(extra))
    pipeline.assign_tiers(conn, now=NOW)
    set_history(conn, 20)
    return agencies.rank_agencies(conn, now=NOW)


def by_name(res):
    return {c["name"]: c for c in res["changes"]}


def test_more_docs_citations_decided_and_direct_means_higher_score(conn):
    extra = [news("배출권거래제 할당 기준 고시 0 소식 정리", source="B뉴스"), news("배출권거래제 개편 입법예고 5 분석 기사", source="C뉴스")]
    res = run_ranked(conn, extra)
    pipeline.link_news(conn, now=NOW)
    res = agencies.rank_agencies(conn, now=NOW)                       # 연결 뒤 다시 계산
    c = by_name(res)
    assert c["A기관"]["score_new"] > c["B기관"]["score_new"] > 0
    assert c["C기관"]["score_new"] is None                            # 탄소 관련 발표 1건 < 3건
    # 양성 대조: 공식 문서와 연결된 일반 언론 뉴스 2건이 A 기관의 인용으로 세어진다
    a_ev = json.loads(c["A기관"]["evidence"])
    assert a_ev["citations"] == 2 and a_ev["components"]["citations"] == 100.0
    assert json.loads(c["B기관"]["evidence"])["citations"] == 0


def test_score_is_the_documented_weighted_sum_and_evidence_is_stored(conn):
    res = run_ranked(conn)
    c = by_name(res)["A기관"]
    ev = json.loads(c["evidence"])
    comp, w = ev["components"], config.AGENCY_SCORE_WEIGHTS
    assert c["score_new"] == round(sum(w[k] * comp[k] for k in w), 1)
    assert ev["carbon_docs"] == 6 and ev["window_days"] == config.AGENCY_WINDOW_DAYS
    assert comp["volume"] == 100.0                                     # 발표가 가장 많은 기관
    assert comp["decided"] == round(100 * 4 / 6, 1) and comp["direct"] == 100.0
    assert abs(sum(w.values()) - 1.0) < 1e-9


def test_volume_is_log_scaled_so_one_agency_does_not_dominate(conn):
    res = run_ranked(conn)
    comp_b = json.loads(by_name(res)["B기관"]["evidence"])["components"]
    assert 60 < comp_b["volume"] < 80                                  # 발표 3건 대 6건: 선형이면 50, 로그면 약 71


def test_agencies_without_enough_evidence_have_no_score_and_a_reason(conn):
    res = run_ranked(conn)
    c = by_name(res)["C기관"]
    assert c["score_new"] is None and "근거 부족" in json.loads(c["evidence"])["reason"]
    unseen = by_name(res)["산업통상부"]                                   # 설정에는 있지만 발표가 없는 기관
    assert unseen["score_new"] is None and "공식 발표 없음" in json.loads(unseen["evidence"])["reason"]


def test_fixed_rank_stays_first_even_with_a_lower_score_than_others(conn):
    extra = [doc("기후에너지환경부 보도 탄소 1", "https://m.test/1", "기후에너지환경부")]    # 발표 1건: 점수 없음
    res = run_ranked(conn, extra)
    ranking = agencies.ranking(conn)
    assert [a["name"] for a in ranking[:3]] == ["기후에너지환경부", "A기관", "B기관"]
    assert ranking[0]["rank"] == 1 and ranking[1]["rank"] == 2 and ranking[2]["rank"] == 3
    assert ranking[0]["score"] is None and ranking[0]["fixed"]


def test_news_from_tier_3_sources_do_not_count_as_citations(conn):
    extra = [news("배출권거래제 할당 기준 고시 0 업계 요구", source="한국경제인협회")]
    run_ranked(conn, extra)
    pipeline.link_news(conn, now=NOW)
    pipeline.assign_tiers(conn, now=NOW)
    res = agencies.rank_agencies(conn, now=NOW)
    assert json.loads(by_name(res)["A기관"]["evidence"])["citations"] == 0


def test_override_replaces_the_score_and_is_shown_as_manual(conn, monkeypatch):
    run_ranked(conn)
    monkeypatch.setattr(config, "AGENCY_OVERRIDES", {"B기관": 99.0})
    ranking = {a["name"]: a for a in agencies.ranking(conn)}
    assert ranking["B기관"]["score"] == 99.0 and ranking["B기관"]["overridden"]
    assert ranking["B기관"]["rank"] < ranking["A기관"]["rank"]             # 사람이 올린 점수가 계산 점수를 이긴다
    monkeypatch.setattr(config, "AGENCY_OVERRIDES", {})
    assert not {a["name"]: a for a in agencies.ranking(conn)}["B기관"]["overridden"]


def test_csv_is_written_with_previous_and_new_scores(conn, tmp_path):
    load(conn, corpus())
    set_history(conn, 20)
    path = tmp_path / "agency_ranking.csv"
    agencies.rank_agencies(conn, now=NOW, csv_path=path)
    agencies.rank_agencies(conn, now=NOW, csv_path=path)               # 두 번째 실행: 이전 점수가 채워진다
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    assert lines[0].startswith("rank,name,kind,fixed_rank,score_prev,score_new,override")
    row = next(l for l in lines if ",A기관," in l).split(",")
    assert row[0] == "2" and row[4] == row[5] != ""


def test_ranking_is_recomputable_and_stable(conn):
    run_ranked(conn)
    first = [(a["name"], a["score"]) for a in agencies.ranking(conn)]
    agencies.rank_agencies(conn, now=NOW)
    assert [(a["name"], a["score"]) for a in agencies.ranking(conn)] == first


# ----------------------------------------------------------------------------- 리포트와 정렬
def test_official_list_uses_agency_importance_as_tiebreaker_after_impact_and_stage(conn):
    load(conn, [
        doc("배출권거래제 할당 고시 낮은기관", "https://x.test/low", "낮은기관", days_ago=0.2),
        doc("배출권거래제 할당 고시 높은기관", "https://x.test/high", "높은기관", days_ago=1.0),
        doc("배출권거래제 개편 입법예고 높은기관", "https://x.test/high2", "높은기관", days_ago=0.1),
    ])
    agencies.ensure_agencies(conn)
    conn.execute("UPDATE agencies SET score=80 WHERE name='높은기관'")
    conn.execute("UPDATE agencies SET score=10 WHERE name='낮은기관'")
    conn.commit()
    order = [o["title"] for o in analysis.build_report_data(conn=conn, now=NOW)["official"]]
    # 둘 다 직접 규제. 확정(고시) 끼리는 중요한 기관이 먼저(더 오래됐어도), 추진(입법예고)은 확정 뒤
    assert order == ["배출권거래제 할당 고시 높은기관", "배출권거래제 할당 고시 낮은기관", "배출권거래제 개편 입법예고 높은기관"]


def test_report_data_exposes_ranking_and_a_note_when_history_is_short(conn):
    load(conn, corpus())
    agencies.ensure_agencies(conn)
    d = analysis.build_report_data(conn=conn, now=NOW)
    assert d["agencies"][0]["name"] == "기후에너지환경부" and d["agencies"][0]["rank"] == 1
    assert "기관 점수는 아직 계산하지 않았습니다" in d["agencies_note"]


def test_report_shows_agency_table_with_evidence_and_waiting_state(conn):
    ev = {"carbon_docs": 6, "citations": 2, "decided": 4, "proposed": 2, "direct": 6, "components": {}}
    ranking = [
        {"name": "기후에너지환경부", "kind": "부처", "fixed": True, "rank": 1, "score": None, "overridden": False, "evidence": {}},
        {"name": "A기관", "kind": "기타", "fixed": False, "rank": 2, "score": 71.5, "overridden": False, "evidence": ev},
        {"name": "B<b>기관", "kind": "기타", "fixed": False, "rank": 3, "score": 30.0, "overridden": True, "evidence": {}},
        {"name": "C기관", "kind": "기타", "fixed": False, "rank": None, "score": None, "overridden": False,
         "evidence": {"reason": "탄소 관련 발표 1건 < 3건: 근거 부족"}},
    ]
    html = render.render_report(data_with(agencies=ranking, agencies_note="누적 기간이 짧습니다"))
    assert "공식 기관 중요도" in html and "고정" in html and "71.5" in html
    assert "탄소 관련 발표 6 · 뉴스 인용 2 · 확정 4/추진 2 · 직접 규제 6" in html
    assert "30 (사람이 지정)" in html and "누적 부족" in html and "근거 부족" in html
    assert "누적 기간이 짧습니다" in html
    assert "B<b>기관" not in html                                       # 기관명도 이스케이프


def test_v7_creates_agencies_table(conn):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(agencies)")}
    assert cols >= {"name", "kind", "fixed_rank", "score", "updated_at", "evidence"}

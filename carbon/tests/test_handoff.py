import pytest

import config
from carbon import handoff
from tests.conftest import NOW, make_article
from tests.test_llm import good, load, official, row


# ----------------------------------------------------------------------------- 분류 내보내기·가져오기
def test_export_classify_lists_pending_items_with_instructions(conn):
    load(conn, [make_article("배출권 할당 계획 발표", url="https://e.com/1"),
                make_article("한국은행 기준금리 동결", url="https://e.com/2")])
    ex = handoff.export_classify(conn, NOW)
    assert ex["kind"] == "classify" and ex["day"] == "2026-11-03"
    assert "지시" in ex["instructions"] and "results" in ex["schema"]["properties"]
    assert [i["input"]["제목"] for i in ex["items"]] == ["배출권 할당 계획 발표"]     # 무관(relevant=0) 제외


def test_export_classify_respects_session_cap(conn, monkeypatch):
    monkeypatch.setattr(config, "SESSION_AI_MAX_ITEMS", 2)
    load(conn, [make_article(f"배출권 기사 {i}", url=f"https://e.com/{i}") for i in range(5)])
    assert len(handoff.export_classify(conn, NOW)["items"]) == 2


def test_import_classify_applies_valid_and_counts_the_rest(conn):
    load(conn, [make_article("A 배출권", url="https://e.com/a"), make_article("B 배출권", url="https://e.com/b"),
                make_article("C 배출권", url="https://e.com/c")])
    ex = handoff.export_classify(conn, NOW)
    by_title = {i["input"]["제목"]: i["id"] for i in ex["items"]}
    out = {"results": [{"id": by_title["A 배출권"], **good()}, {"id": by_title["B 배출권"], **good(impact="huge")},
                       {"id": "nope", **good()}, {"id": 123, **good()}]}
    res = handoff.import_classify(conn, out, ex, NOW)
    assert res == {"applied": 1, "invalid": 1, "unknown_id": 2, "missing": 1}
    assert row(conn, "A 배출권")["llm_model"] == config.SESSION_AI_MODEL_LABEL
    assert row(conn, "B 배출권")["llm_fail_count"] == 1
    assert row(conn, "C 배출권")["llm_done_at"] is None and row(conn, "C 배출권")["llm_fail_count"] == 0
    assert conn.execute("SELECT COUNT(*) FROM llm_usage").fetchone()[0] == 0


def test_import_classify_uses_first_result_for_a_duplicated_id(conn):
    load(conn, [make_article("A 배출권", url="https://e.com/a")])
    ex = handoff.export_classify(conn, NOW)
    i = ex["items"][0]["id"]
    res = handoff.import_classify(conn, {"results": [{"id": i, **good(impact="low")}, {"id": i, **good(impact="high")}]}, ex, NOW)
    assert res["applied"] == 1 and row(conn, "A 배출권")["llm_impact"] == "low"


def test_import_classify_never_overrides_rule_judgement(conn):
    load(conn, [official("배출권 할당계획 고시 시행", "https://me.go.kr/1")])
    assert row(conn, "배출권 할당계획 고시 시행")["policy_stage"] == "decided"
    ex = handoff.export_classify(conn, NOW)
    out = {"results": [{"id": ex["items"][0]["id"], **good(policy_stage="proposed", domestic_impact="direct")}]}
    handoff.import_classify(conn, out, ex, NOW)
    after = row(conn, "배출권 할당계획 고시 시행")
    assert after["policy_stage"] == "decided" and after["llm_stage"] == "proposed"


def test_import_rejects_wrong_kind_or_day(conn):
    ex = handoff.export_classify(conn, NOW)
    with pytest.raises(handoff.HandoffError):
        handoff.import_classify(conn, {"results": []}, {**ex, "day": "2026-11-02"}, NOW)
    with pytest.raises(handoff.HandoffError):
        handoff.import_classify(conn, {"results": []}, {**ex, "kind": "summary"}, NOW)


# ----------------------------------------------------------------------------- 요약 내보내기·가져오기
OFF1, OFF2 = "배출권 할당계획 고시 시행", "온실가스 배출권의 할당 및 거래에 관한 법률 시행령 개정안 입법예고"
NEWS = "정부, 배출권 할당계획 확정"


def _setup_summary(conn):
    load(conn, [official(OFF1, "https://me.go.kr/1"), official(OFF2, "https://me.go.kr/2"),
                make_article(NEWS, url="https://e.com/n", days_ago=0.5)])
    nid = row(conn, NEWS)["id"]
    conn.execute("UPDATE articles SET llm_impact='high', llm_done_at=?, llm_summary='할당계획 확정 보도' WHERE id=?",
                 (NOW.isoformat(), nid))
    conn.commit()
    return handoff.export_summary(conn, NOW)


def _ids(conn):
    return row(conn, OFF1)["id"], row(conn, OFF2)["id"], row(conn, NEWS)["id"]


def _link(conn, news_id, official_id, score):
    conn.execute("INSERT OR REPLACE INTO article_links (news_id, official_id, score) VALUES (?,?,?)", (news_id, official_id, score))
    conn.commit()


def _saved(conn):
    import json
    r = conn.execute("SELECT * FROM daily_summaries WHERE day='2026-11-03'").fetchone()
    return None if r is None else {**dict(r), "conclusions": json.loads(r["conclusions"]), "report_items": json.loads(r["report_items"])}


def test_export_summary_has_materials_rising_and_topics(conn):
    ex = _setup_summary(conn)
    o1, o2, n = _ids(conn)
    assert ex["kind"] == "summary" and ex["day"] == "2026-11-03"
    assert {m["id"] for m in ex["materials"]} == {o1, o2, n}
    assert isinstance(ex["rising"], list) and isinstance(ex["topics"], list)
    assert "지시" in ex["instructions"] and "확정" in ex["instructions"]


def test_summary_saves_valid_ai_summary(conn):
    ex = _setup_summary(conn)
    o1, _, _ = _ids(conn)
    out = {"conclusions": ["가", "나", "다"], "report_items": [{"id": o1, "why": "할당계획 확정"}]}
    res = handoff.import_summary(conn, out, ex, NOW)
    assert res["saved"] and res["conclusions"] == 3 and res["report_items"] == 1
    s = _saved(conn)
    assert s["conclusions"] == ["가", "나", "다"] and s["report_items"] == [{"id": o1, "why": "할당계획 확정", "via_news": None}]
    assert s["model"] == config.SESSION_AI_MODEL_LABEL and o1 in s["source_ids"]


def test_conclusions_trimmed_to_max_and_length(conn):
    ex = _setup_summary(conn)
    out = {"conclusions": ["가" * 200] + [f"문장{c}" for c in "가나다라마바"], "report_items": []}
    handoff.import_summary(conn, out, ex, NOW)
    s = _saved(conn)
    assert len(s["conclusions"]) == 5 and len(s["conclusions"][0]) == 120 and s["conclusions"][0].endswith("…")


def test_conclusion_with_unknown_number_is_dropped(conn):
    ex = _setup_summary(conn)
    res = handoff.import_summary(conn, {"conclusions": ["감축률 37% 확정", "할당계획 고시"], "report_items": []}, ex, NOW)
    assert _saved(conn)["conclusions"] == ["할당계획 고시"] and any("37" in d for d in res["dropped"])


def test_conclusion_with_export_day_number_is_kept(conn):
    ex = _setup_summary(conn)
    handoff.import_summary(conn, {"conclusions": ["11월 3일 할당계획 고시"], "report_items": []}, ex, NOW)
    assert _saved(conn)["conclusions"] == ["11월 3일 할당계획 고시"]


def test_report_item_must_be_official_or_linked_news(conn):
    ex = _setup_summary(conn)
    o1, o2, n = _ids(conn)
    out = {"conclusions": ["가"], "report_items": [{"id": "nope", "why": "x"}, {"id": n, "why": "연결 없음"}]}
    res = handoff.import_summary(conn, out, ex, NOW)
    assert _saved(conn)["report_items"] == [] and len(res["dropped"]) == 2
    _link(conn, n, o2, 0.8)
    _link(conn, n, o1, 0.5)
    handoff.import_summary(conn, {"conclusions": ["가"], "report_items": [{"id": n, "why": "보도"}]}, ex, NOW)
    assert _saved(conn)["report_items"] == [{"id": o2, "why": "보도", "via_news": n}]


def test_linked_news_tie_breaks_by_official_id(conn):
    ex = _setup_summary(conn)
    o1, o2, n = _ids(conn)
    _link(conn, n, o1, 0.7)
    _link(conn, n, o2, 0.7)
    handoff.import_summary(conn, {"conclusions": ["가"], "report_items": [{"id": n, "why": "보도"}]}, ex, NOW)
    assert _saved(conn)["report_items"][0]["id"] == min(o1, o2)


def test_duplicate_official_in_report_items_is_merged(conn):
    ex = _setup_summary(conn)
    o1, _, n = _ids(conn)
    _link(conn, n, o1, 0.9)
    out = {"conclusions": ["가"], "report_items": [{"id": o1, "why": "첫째"}, {"id": n, "why": "둘째"}]}
    handoff.import_summary(conn, out, ex, NOW)
    assert _saved(conn)["report_items"] == [{"id": o1, "why": "첫째", "via_news": None}]


def test_zero_valid_conclusions_saves_nothing(conn):
    ex = _setup_summary(conn)
    res = handoff.import_summary(conn, {"conclusions": ["", "감축률 37%"], "report_items": []}, ex, NOW)
    assert res["saved"] is False and _saved(conn) is None


def test_rerun_failure_keeps_previous_ai_summary(conn):
    ex = _setup_summary(conn)
    handoff.import_summary(conn, {"conclusions": ["첫 요약"], "report_items": []}, ex, NOW)
    handoff.import_summary(conn, {"conclusions": [], "report_items": []}, ex, NOW)
    assert _saved(conn)["conclusions"] == ["첫 요약"]


def test_rerun_success_replaces(conn):
    ex = _setup_summary(conn)
    handoff.import_summary(conn, {"conclusions": ["첫 요약"], "report_items": []}, ex, NOW)
    handoff.import_summary(conn, {"conclusions": ["새 요약"], "report_items": []}, ex, NOW)
    assert _saved(conn)["conclusions"] == ["새 요약"]


def test_classified_count_is_todays_session_items(conn):
    load(conn, [make_article("A 배출권", url="https://e.com/a"), make_article("B 배출권", url="https://e.com/b")])
    exc = handoff.export_classify(conn, NOW)
    handoff.import_classify(conn, {"results": [{"id": i["id"], **good()} for i in exc["items"]]}, exc, NOW)
    ex = handoff.export_summary(conn, NOW)
    handoff.import_summary(conn, {"conclusions": ["가"], "report_items": []}, ex, NOW)
    assert _saved(conn)["classified"] == 2


def test_summary_import_rejects_other_day(conn):
    ex = _setup_summary(conn)
    with pytest.raises(handoff.HandoffError):
        handoff.import_summary(conn, {"conclusions": ["가"], "report_items": []}, {**ex, "day": "2026-11-02"}, NOW)


def test_numbers_only_in_ids_or_instructions_do_not_count_as_material(conn):
    ex = _setup_summary(conn)
    ex = {**ex, "materials": [{**m, "id": m["id"] + "-777"} for m in ex["materials"]]}   # id 에만 있는 숫자
    assert "120" in ex["instructions"]                                                  # 지시문에만 있는 숫자
    res = handoff.import_summary(conn, {"conclusions": ["감축 777건", "감축 120건", "할당계획"], "report_items": []}, ex, NOW)
    assert _saved(conn)["conclusions"] == ["할당계획"] and len(res["dropped"]) == 2


# ----------------------------------------------------------------------------- 명령 (main.py)
import json as _json  # noqa: E402
from datetime import datetime as _dt, timezone as _tz  # noqa: E402

import main  # noqa: E402
from carbon import db, pipeline  # noqa: E402
from tests.conftest import FakeSource  # noqa: E402


@pytest.fixture
def cli_env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "a.db")
    monkeypatch.setattr(config, "AI_WORK_DIR", tmp_path / "work")
    monkeypatch.setattr(config, "LOG_DIR", tmp_path / "logs")
    a = make_article("배출권 할당 계획 발표", url="https://e.com/cli")
    a.published = _dt.now(_tz.utc).isoformat()           # 명령은 실제 현재 시각을 쓴다
    c = db.connect()
    pipeline.collect([FakeSource([a])], conn=c)
    c.close()
    return tmp_path / "work"


def test_cli_roundtrip_classify(cli_env):
    assert main.main(["ai-export", "classify"]) == 0
    [exported] = list(cli_env.glob("ai_classify_*.json"))
    ex = _json.loads(exported.read_text(encoding="utf-8"))
    out = exported.with_name(exported.name.replace(".json", ".out.json"))
    out.write_text(_json.dumps({"results": [{"id": ex["items"][0]["id"], **good()}]}, ensure_ascii=False), encoding="utf-8")
    assert main.main(["ai-import", "classify"]) == 0
    c = db.connect()
    assert c.execute("SELECT llm_model FROM articles").fetchone()[0] == config.SESSION_AI_MODEL_LABEL
    c.close()


def test_cli_import_missing_or_broken_file_returns_2(cli_env):
    assert main.main(["ai-import", "classify"]) == 2                  # 내보낸 파일·결과 파일 없음
    assert main.main(["ai-export", "classify"]) == 0
    [exported] = list(cli_env.glob("ai_classify_*.json"))
    exported.with_name(exported.name.replace(".json", ".out.json")).write_text("{깨진", encoding="utf-8")
    assert main.main(["ai-import", "classify"]) == 2
    c = db.connect()
    assert c.execute("SELECT llm_done_at FROM articles").fetchone()[0] is None
    c.close()


def test_cli_kind_required(cli_env):
    assert main.main(["ai-export"]) == 2
    assert main.main(["ai-import", "nope"]) == 2


def test_cli_summary_roundtrip(cli_env):
    assert main.main(["ai-export", "summary"]) == 0
    [exported] = list(cli_env.glob("ai_summary_*.json"))
    exported.with_name(exported.name.replace(".json", ".out.json")).write_text(
        _json.dumps({"conclusions": ["할당계획 발표"], "report_items": []}, ensure_ascii=False), encoding="utf-8")
    assert main.main(["ai-import", "summary"]) == 0
    c = db.connect()
    assert c.execute("SELECT COUNT(*) FROM daily_summaries").fetchone()[0] == 1
    c.close()


def test_cli_import_accepts_utf8_bom_result_file(cli_env):
    assert main.main(["ai-export", "classify"]) == 0
    [exported] = list(cli_env.glob("ai_classify_*.json"))
    ex = _json.loads(exported.read_text(encoding="utf-8"))
    out = exported.with_name(exported.name.replace(".json", ".out.json"))
    out.write_text(_json.dumps({"results": [{"id": ex["items"][0]["id"], **good()}]}, ensure_ascii=False), encoding="utf-8-sig")
    assert main.main(["ai-import", "classify"]) == 0


def test_summary_with_no_material_at_all_is_not_saved(conn):
    ex = handoff.export_summary(conn, NOW)                     # 빈 DB: 재료·급증 키워드·주제 모두 없음
    assert ex["materials"] == [] and ex["rising"] == [] and ex["topics"] == []
    res = handoff.import_summary(conn, {"conclusions": ["근거 없는 결론"], "report_items": []}, ex, NOW)
    assert res["saved"] is False and any("재료" in d for d in res["dropped"])
    assert _saved(conn) is None

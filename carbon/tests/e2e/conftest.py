"""e2e: 고정 DB(tests/fixtures/sample.db)로 리포트를 만들어 file:// 로 연다. 실제 네트워크·운영 DB 는 쓰지 않는다."""
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

pytest.importorskip("playwright")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from carbon import analysis, db, render  # noqa: E402

FIXTURE_DB = ROOT / "tests" / "fixtures" / "sample.db"
NOW = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
QA_DIR = ROOT / "reports" / "qa"


@pytest.fixture(scope="session")
def report_data(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("e2e") / "sample.db"
    shutil.copy(FIXTURE_DB, tmp)          # 고정 DB 는 건드리지 않는다
    conn = db.connect(tmp)
    try:
        return analysis.build_report_data(conn=conn, now=NOW)
    finally:
        conn.close()


@pytest.fixture(scope="session")
def report_url(report_data, tmp_path_factory):
    path = tmp_path_factory.mktemp("html") / "report_2026-11-03.html"
    path.write_text(render.render_report(report_data), encoding="utf-8")
    return path.as_uri()


@pytest.fixture(scope="session")
def empty_report_url(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("empty")
    conn = db.connect(tmp / "empty.db")
    try:
        data = analysis.build_report_data(conn=conn, now=NOW)
    finally:
        conn.close()
    path = tmp / "report_empty.html"
    path.write_text(render.render_report(data), encoding="utf-8")
    return path.as_uri()


@pytest.fixture(scope="session")
def qa_dir():
    QA_DIR.mkdir(parents=True, exist_ok=True)
    return QA_DIR


def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: Playwright 로 리포트 화면을 여는 테스트 (tests/e2e)")


@pytest.fixture(scope="session")
def ai_summary_report_url(tmp_path_factory):
    """고정 DB 복사본에 AI 요약 1건(보고 항목: 공식 문서 1건)을 넣고 만든 리포트."""
    import json
    tmp = tmp_path_factory.mktemp("ai") / "sample.db"
    shutil.copy(FIXTURE_DB, tmp)
    conn = db.connect(tmp)
    try:
        oid = conn.execute("SELECT id FROM articles WHERE source_type='official' AND relevant IS NOT 0 "
                           "ORDER BY published DESC LIMIT 1").fetchone()[0]
        conn.execute("INSERT OR REPLACE INTO daily_summaries (day,conclusions,report_items,model,created_at,source_ids,classified) "
                     "VALUES ('2026-11-03',?,?,'claude-app-session','','[]',0)",
                     (json.dumps(["AI 결론 첫째", "AI 결론 둘째", "AI 결론 셋째"], ensure_ascii=False),
                      json.dumps([{"id": oid, "why": "보고 이유", "via_news": None}], ensure_ascii=False)))
        conn.commit()
        data = analysis.build_report_data(conn=conn, now=NOW)
    finally:
        conn.close()
    path = tmp.parent / "report_ai.html"
    path.write_text(render.render_report(data), encoding="utf-8")
    return path.as_uri()

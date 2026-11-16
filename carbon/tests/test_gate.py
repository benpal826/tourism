"""2단계 게이트: 기능 플래그를 모두 꺼도 1단계처럼 수집 → 저장 → 리포트가 끝까지 돌고,
켜면 각 기능이 다른 기능 없이 독립적으로 동작하는지 main.main 수준에서 확인한다 (네트워크 없음)."""
import csv
from datetime import datetime, timedelta, timezone

import pytest

import config
import main
from carbon import db, pipeline
from carbon.sources.base import Article
from tests.conftest import FakeSource


def _articles():
    now = datetime.now(timezone.utc)
    mk = lambda t, h, src="연합뉴스": Article(title=t, url=f"https://example.com/{abs(hash(t))}", source=src, lang="ko",
                                           query="배출권거래제", summary="", published=(now - timedelta(hours=h)).isoformat())
    return [mk("EU CBAM 철강 기본값 개정안 발표", 2), mk("환경부 배출권 할당계획 변경 행정예고", 3, "이데일리"),
            mk("2035 NDC 이행점검 결과 공개", 5)]


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "data" / "articles.db")
    monkeypatch.setattr(config, "REPORT_DIR", tmp_path / "reports")
    monkeypatch.setattr(config, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(config, "SOURCES", ["google_news"])          # 1단계와 같은 출처 하나
    monkeypatch.setattr(pipeline, "build_sources", lambda names=None: [FakeSource(_articles())])
    monkeypatch.setattr(pipeline, "search_coverage", lambda conn, **k: {})   # 네트워크 검색 차단
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "NOTIFY_TO"):
        monkeypatch.delenv(k, raising=False)
    return tmp_path


def _report(tmp):
    files = list((tmp / "reports").glob("report_*.html"))
    assert len(files) == 1
    return files[0].read_text(encoding="utf-8")


def test_all_flags_off_runs_end_to_end_like_stage1(env, monkeypatch):
    monkeypatch.setattr(config, "ENABLE_LLM", False)
    assert main.main(["run"]) == 0
    html = _report(env)
    assert "EU CBAM 철강 기본값 개정안 발표" in html
    conn = db.connect()
    try:
        assert conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0] == 3
        assert conn.execute("SELECT COUNT(*) FROM articles WHERE llm_done_at IS NOT NULL").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM notify_log").fetchone()[0] == 0     # --notify 없으면 발송 안 함
        assert conn.execute("SELECT COUNT(*) FROM llm_usage").fetchone()[0] == 0
    finally:
        conn.close()


def test_llm_on_without_credentials_does_not_break_run(env, monkeypatch):
    monkeypatch.setattr(config, "ENABLE_LLM", True)
    assert main.main(["run"]) == 0
    assert "환경부 배출권 할당계획" in _report(env)


def test_notify_dry_run_works_alone(env, monkeypatch, capsys):
    monkeypatch.setattr(config, "ENABLE_LLM", False)
    assert main.main(["run", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "[dry-run]" in out and "EU CBAM 철강 기본값 개정안 발표" in out
    # --notify 인데 SMTP 설정이 없으면 실패로 끝나되, 리포트는 이미 만들어져 있다
    assert main.main(["run", "--notify"]) == 1
    assert "EU CBAM" in _report(env)


def test_search_and_export_work_alone(env, monkeypatch, capsys):
    monkeypatch.setattr(config, "ENABLE_LLM", False)
    assert main.main(["collect"]) == 0
    assert main.main(["search", "배출권"]) == 0
    assert "환경부 배출권 할당계획" in capsys.readouterr().out
    out = env / "e.csv"
    assert main.main(["export", "--topic", "CBAM", "--out", str(out)]) == 0
    rows = list(csv.reader(out.open(encoding="utf-8-sig")))
    assert [r[2] for r in rows[1:]] == ["EU CBAM 철강 기본값 개정안 발표"]

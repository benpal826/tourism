import sqlite3

from carbon import db


def test_empty_db_creates_schema(tmp_path):
    conn = db.connect(tmp_path / "new.db")
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "articles" in tables
    assert conn.execute("PRAGMA user_version").fetchone()[0] == len(db.MIGRATIONS)
    conn.close()


def test_legacy_db_keeps_data(tmp_path):
    """버전 관리 도입 전(user_version=0)의 기존 DB도 데이터 손실 없이 편입된다."""
    path = tmp_path / "legacy.db"
    raw = sqlite3.connect(path)
    raw.execute("CREATE TABLE articles (id TEXT PRIMARY KEY, title TEXT NOT NULL, url TEXT, source TEXT,"
                " lang TEXT, query TEXT, summary TEXT, published TEXT, collected TEXT, topics TEXT, regions TEXT)")
    raw.execute("INSERT INTO articles (id,title) VALUES ('x','기존 기사')")
    raw.commit()
    raw.close()

    conn = db.connect(path)
    assert conn.execute("SELECT title FROM articles WHERE id='x'").fetchone()[0] == "기존 기사"
    assert conn.execute("PRAGMA user_version").fetchone()[0] == len(db.MIGRATIONS)
    # 2단계에서 추가된 컬럼이 붙고, 기존 기사는 뉴스로 취급된다
    row = conn.execute("SELECT source_type, agency FROM articles WHERE id='x'").fetchone()
    assert row["source_type"] == "news" and row["agency"] is None
    conn.close()


def test_v3_adds_policy_columns_and_keyword_weights(conn):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(articles)")}
    assert {"policy_stage", "domestic_impact", "impact_score", "impact_keyword"} <= cols
    wcols = {r[1] for r in conn.execute("PRAGMA table_info(keyword_weights)")}
    assert {"keyword", "seed_weight", "learned_weight", "final_weight", "updated_at", "evidence"} <= wcols


def test_v4_adds_link_columns_and_table_and_marks_existing_official_docs(tmp_path):
    path = tmp_path / "old.db"
    conn = db.connect(path)
    conn.execute("PRAGMA user_version = 3")                      # v4 이전 상태를 흉내 낸다
    conn.execute("ALTER TABLE articles RENAME TO articles_bak")
    conn.execute("CREATE TABLE articles AS SELECT id,title,url,source,lang,query,summary,published,collected,topics,regions,"
                 "source_type,agency,policy_stage,domestic_impact,impact_score,impact_keyword FROM articles_bak")
    conn.execute("INSERT INTO articles (id,title,source_type) VALUES ('o','공식','official'),('n','뉴스','news')")
    conn.execute("DROP TABLE articles_bak")
    conn.commit()
    db._m4_links(conn)
    rows = {r["id"]: r["official_status"] for r in conn.execute("SELECT id, official_status FROM articles")}
    assert rows == {"o": "n/a", "n": "unconfirmed"}
    cols = {r[1] for r in conn.execute("PRAGMA table_info(articles)")}
    assert {"official_status", "link_attempts", "link_checked_at"} <= cols
    assert {r[1] for r in conn.execute("PRAGMA table_info(article_links)")} >= {"news_id", "official_id", "score", "method", "created_at"}
    conn.close()


def test_migrate_is_idempotent(conn):
    db.migrate(conn)
    db.migrate(conn)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == len(db.MIGRATIONS)


def test_m11_creates_daily_summaries_and_keeps_data(tmp_path):
    c = db.connect(tmp_path / "t.db")
    cols = {r[1] for r in c.execute("PRAGMA table_info(daily_summaries)")}
    assert cols == {"day", "conclusions", "report_items", "model", "created_at", "source_ids", "classified"}
    assert c.execute("PRAGMA user_version").fetchone()[0] == len(db.MIGRATIONS) == 11
    c.close()


def test_session_ai_and_summary_settings_exist():
    import config
    assert config.SESSION_AI_MAX_ITEMS == 150 and config.SESSION_AI_MODEL_LABEL == "claude-app-session"
    assert config.AI_WORK_DIR == config.BASE_DIR / "work"
    assert (config.SUMMARY_MIN_CONCLUSIONS, config.SUMMARY_MAX_CONCLUSIONS, config.SUMMARY_CONCLUSION_CHARS) == (1, 5, 120)
    assert (config.SUMMARY_REPORT_ITEMS, config.SUMMARY_WHY_CHARS, config.SUMMARY_FLOW_TOPICS) == (3, 80, 5)

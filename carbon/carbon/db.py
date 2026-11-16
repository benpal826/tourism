"""SQLite 연결, 스키마 생성, 마이그레이션.

스키마 버전은 PRAGMA user_version 으로 관리한다.
컬럼을 추가할 때는 아래 MIGRATIONS 목록 끝에 함수를 하나 붙이면 된다.
"""
import logging
import sqlite3
from pathlib import Path

import config

log = logging.getLogger(__name__)


def _m1_create_articles(conn: sqlite3.Connection) -> None:
    # IF NOT EXISTS: 버전 관리 도입 전에 만들어진 기존 DB도 데이터 손실 없이 편입된다.
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS articles (
            id TEXT PRIMARY KEY,   -- 정규화한 제목의 SHA-1 (중복 제거 키)
            title TEXT NOT NULL,
            url TEXT,
            source TEXT,
            lang TEXT,
            query TEXT,
            summary TEXT,
            published TEXT,        -- ISO8601 UTC
            collected TEXT,        -- ISO8601 UTC
            topics TEXT,           -- 쉼표 구분
            regions TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_pub ON articles(published);
        """
    )


def _m2_official_columns(conn: sqlite3.Connection) -> None:
    """F7: 공식 출처 구분(source_type)과 발행 기관(agency) 컬럼."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(articles)")}
    if "source_type" not in cols:
        conn.execute("ALTER TABLE articles ADD COLUMN source_type TEXT NOT NULL DEFAULT 'news'")
    if "agency" not in cols:
        conn.execute("ALTER TABLE articles ADD COLUMN agency TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_source_type ON articles(source_type, published)")


def _m3_policy_columns(conn: sqlite3.Connection) -> None:
    """F11, F12: 공식 문서의 정책 단계·국내 영향도, 그리고 키워드 가중치 테이블."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(articles)")}
    for name, ddl in [("policy_stage", "TEXT"), ("domestic_impact", "TEXT"),
                      ("impact_score", "REAL"), ("impact_keyword", "TEXT")]:
        if name not in cols:
            conn.execute(f"ALTER TABLE articles ADD COLUMN {name} {ddl}")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS keyword_weights (
            keyword TEXT PRIMARY KEY,
            seed_weight REAL NOT NULL,     -- config.IMPACT_SEEDS 의 초기값
            learned_weight REAL,           -- 누적 데이터로 계산한 값 (근거 부족하면 NULL)
            final_weight REAL NOT NULL,    -- 실제 판정에 쓰는 값
            updated_at TEXT,
            evidence TEXT                  -- 계산 근거(JSON)
        )
        """
    )


def _m4_links(conn: sqlite3.Connection) -> None:
    """F16: 뉴스–공식 문서 연결. official_status 는 confirmed(연결됨) / unconfirmed(공식 확인 안 됨) / n/a(공식 문서 자신)."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(articles)")}
    if "official_status" not in cols:
        conn.execute("ALTER TABLE articles ADD COLUMN official_status TEXT NOT NULL DEFAULT 'unconfirmed'")
        conn.execute("UPDATE articles SET official_status='n/a' WHERE source_type='official'")
    if "link_attempts" not in cols:
        conn.execute("ALTER TABLE articles ADD COLUMN link_attempts INTEGER NOT NULL DEFAULT 0")
    if "link_checked_at" not in cols:
        conn.execute("ALTER TABLE articles ADD COLUMN link_checked_at TEXT")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS article_links (
            news_id TEXT NOT NULL,
            official_id TEXT NOT NULL,
            score REAL NOT NULL,
            method TEXT,            -- 연결 근거(JSON): 공유한 정책 용어·숫자·단어, 기관명 언급 등
            created_at TEXT,
            PRIMARY KEY (news_id, official_id)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_links_official ON article_links(official_id)")


def _m5_coverage(conn: sqlite3.Connection) -> None:
    """공식 문서별로 후속 보도를 몇 번 검색했는지 (문서당 최대 2회: 발견 직후, 48시간 뒤)."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(articles)")}
    if "coverage_checks" not in cols:
        conn.execute("ALTER TABLE articles ADD COLUMN coverage_checks INTEGER NOT NULL DEFAULT 0")
    if "coverage_checked_at" not in cols:
        conn.execute("ALTER TABLE articles ADD COLUMN coverage_checked_at TEXT")


def _m6_tiers(conn: sqlite3.Connection) -> None:
    """F13: 출처 신뢰도 등급. source_url 은 RSS 가 알려 주는 언론사 주소, sensational 은 제목의 자극적 표현(표시용)."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(articles)")}
    for name, ddl in [("source_url", "TEXT"), ("source_tier", "INTEGER"), ("source_tier_reason", "TEXT"), ("sensational", "TEXT")]:
        if name not in cols:
            conn.execute(f"ALTER TABLE articles ADD COLUMN {name} {ddl}")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_source ON articles(source)")


def _m7_agencies(conn: sqlite3.Connection) -> None:
    """F15: 공식 기관 중요도. 환경부만 순위를 고정(fixed_rank)하고 나머지는 누적 데이터로 계산한 score 를 쓴다."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS agencies (
            name TEXT PRIMARY KEY,
            kind TEXT,              -- 부처 / 산하·유관기관 / 국회 / 입법 플랫폼 / 국제
            fixed_rank INTEGER,     -- 순위를 고정한 기관만 값이 있다 (기후에너지환경부 = 1)
            score REAL,             -- 0~100. 누적 데이터가 부족하면 NULL
            updated_at TEXT,
            evidence TEXT           -- 점수 근거(JSON): 지표별 값, 정규화 값, 가중치
        )
        """
    )


def _m8_relevance(conn: sqlite3.Connection) -> None:
    """F6: 무관 기사 필터링. relevant 는 NULL=미판정, 1=관련, 0=무관. 삭제하지 않고 표시만 한다.
    relevance_reason 이 'rule:' 로 시작하면 규칙 판정이라 refilter 가 다시 계산해도 된다 (LLM·사람 판정은 건드리지 않는다)."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(articles)")}
    if "relevant" not in cols:
        conn.execute("ALTER TABLE articles ADD COLUMN relevant INTEGER")
    if "relevance_reason" not in cols:
        conn.execute("ALTER TABLE articles ADD COLUMN relevance_reason TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_relevant ON articles(relevant)")


def _m9_llm(conn: sqlite3.Connection) -> None:
    """F5: LLM 분류·요약 결과. 규칙 판정 컬럼과 나란히 두어 서로 어떻게 다른지 볼 수 있게 한다.

    llm_topics / llm_regions 는 LLM 이 정한 최종 목록이다 (llm_done_at 이 있으면 리포트는 이것을 쓴다).
    policy_source='llm' 이면 정책 단계·영향도를 LLM 이 채운 것이라 classify(규칙 재판정)가 덮어쓰지 않는다.
    """
    cols = {r[1] for r in conn.execute("PRAGMA table_info(articles)")}
    for name, ddl in [("llm_relevant", "INTEGER"), ("llm_topics", "TEXT"), ("llm_regions", "TEXT"), ("llm_summary", "TEXT"),
                      ("llm_impact", "TEXT"), ("llm_stage", "TEXT"), ("llm_domestic_impact", "TEXT"), ("llm_reason", "TEXT"),
                      ("llm_done_at", "TEXT"), ("llm_model", "TEXT"), ("llm_fail_count", "INTEGER NOT NULL DEFAULT 0"),
                      ("policy_source", "TEXT")]:
        if name not in cols:
            conn.execute(f"ALTER TABLE articles ADD COLUMN {name} {ddl}")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_llm_done ON articles(llm_done_at)")
    # 하루 호출 상한(LLM_DAILY_LIMIT) 계산과 비용 추정을 위한 사용량 기록
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS llm_usage (
            day TEXT PRIMARY KEY,           -- UTC 날짜
            calls INTEGER NOT NULL DEFAULT 0,
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            cost_usd REAL NOT NULL DEFAULT 0
        )
        """
    )
    # 하루 한 번 만드는 "오늘의 브리핑" (영향도 높은 기사·문서를 모은 5문장 이내 요약)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS briefings (
            day TEXT PRIMARY KEY,           -- KST 날짜
            text TEXT NOT NULL,
            model TEXT,
            created_at TEXT,
            source_ids TEXT                 -- 재료로 쓴 기사·문서 id (JSON)
        )
        """
    )


def _m10_notify(conn: sqlite3.Connection) -> None:
    """F9: 이메일 알림 발송 기록. '신규' 기사의 기준 시각과 급증 키워드 중복 알림 방지에 쓴다.
    수신자 주소·계정은 저장하지 않는다 (수신자 수만)."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS notify_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sent_at TEXT NOT NULL,          -- ISO8601 UTC
            subject TEXT,
            article_ids TEXT,               -- 알린 기사·문서 id (JSON)
            terms TEXT,                     -- 알린 급증 키워드 (JSON)
            recipients INTEGER NOT NULL DEFAULT 0
        )
        """
    )


def _m11_daily_summaries(conn: sqlite3.Connection) -> None:
    """오늘의 요약: Claude 앱 예약 작업 세션이 쓴 AI 요약 (규칙 요약은 리포트를 만들 때 계산하고 저장하지 않는다)."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_summaries (
            day TEXT PRIMARY KEY,                   -- KST 날짜
            conclusions TEXT NOT NULL,              -- 결론 문장 (JSON 목록)
            report_items TEXT NOT NULL,             -- 보고할 것 [{"id": 공식 문서 id, "why", "via_news"}] (JSON)
            model TEXT,
            created_at TEXT,
            source_ids TEXT,                        -- 재료로 내보낸 기사·문서 id (JSON)
            classified INTEGER NOT NULL DEFAULT 0   -- 그날 세션이 분류한 기사 수
        )
        """
    )


MIGRATIONS = [_m1_create_articles, _m2_official_columns, _m3_policy_columns, _m4_links, _m5_coverage, _m6_tiers, _m7_agencies,
              _m8_relevance, _m9_llm, _m10_notify, _m11_daily_summaries]

# 리포트·지표가 쓰는 주제·지역: LLM 이 처리한 기사는 LLM 의 최종 목록을, 아니면 키워드 규칙의 태그를 쓴다
EFFECTIVE_TOPICS = "CASE WHEN llm_done_at IS NOT NULL THEN llm_topics ELSE topics END"
EFFECTIVE_REGIONS = "CASE WHEN llm_done_at IS NOT NULL THEN llm_regions ELSE regions END"


def migrate(conn: sqlite3.Connection) -> None:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    for target, fn in enumerate(MIGRATIONS[version:], start=version + 1):
        log.info("DB 마이그레이션 v%d 적용", target)
        fn(conn)
        conn.execute(f"PRAGMA user_version = {target}")
        conn.commit()


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(path or config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    migrate(conn)
    return conn

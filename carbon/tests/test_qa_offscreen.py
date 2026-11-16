"""4-3 화면 밖 점검 중 기존 모듈 테스트에 없던 항목 (docs/qa-plan.md 의 F3-01, F6-01, F14-01, F10-01, NF-04, NF-06, NF-09).

기대값은 PRD 의 정의에서 정했다. 실패하면 단언을 느슨하게 하지 말고 docs/qa-report.md 에 결함으로 기록한다.
"""
import csv
import re
import shutil
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import config
import main
from carbon import analysis, db, filters, pipeline, query, tagging
from carbon.sources.base import Article
from tests.conftest import FakeSource

FIXTURE_DB = Path(__file__).parent / "fixtures" / "sample.db"
FIX_NOW = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)

ETS, CBAM, PRICE, NDC, CREDIT, ENERGY, INDUSTRY = (
    "배출권거래제(ETS)", "CBAM/탄소국경", "탄소가격/탄소세", "감축목표/NDC", "자발적 탄소시장/크레딧",
    "에너지 전환·재생에너지", "산업·기업 영향")

# (제목, 언론사, 반드시 들어갈 주제, 들어가면 안 되는 주제, 반드시 들어갈 지역, 관련성 기대: 1 관련 / 0 무관 / None 미판정)
TITLES_30 = [
    ("환경부, 제4차 배출권거래제 할당계획 확정", "연합뉴스", {ETS}, set(), {"한국"}, 1),
    ("EU CBAM 본격 시행 앞두고 철강업계 비상", "매일경제", {CBAM, INDUSTRY}, set(), {"EU"}, 1),
    ("정부, 2035 NDC 감축목표 61% 확정", "한겨레", {NDC}, set(), set(), 1),
    ("탄소세 도입 논의 본격화…산업계 반발", "조선일보", {PRICE}, set(), set(), 1),
    ("파리협정 6조 탄소크레딧 거래 첫 승인", "이데일리", {CREDIT}, set(), set(), 1),
    ("K-ETS 배출권 가격 2만원 돌파", "서울경제", {ETS}, set(), {"한국"}, 1),
    ("탄소국경조정제도 대응 위한 중소기업 지원 확대", "머니투데이", {CBAM}, set(), set(), 1),
    ("재생에너지 RE100 조달 기반 마련 시급", "에너지경제", {ENERGY}, set(), set(), None),
    ("수소 산업 육성 기본계획 발표", "전자신문", {ENERGY}, set(), set(), None),
    ("시멘트 업계 탈탄소 전환 가속", "한국경제", {INDUSTRY, NDC}, set(), set(), 1),
    ("EU ETS carbon price hits two-year high", "Reuters", {ETS, PRICE}, set(), {"EU"}, 1),
    ("China expands national emissions trading system to steel", "Bloomberg", {ETS, INDUSTRY}, set(), {"중국"}, 1),
    ("UK confirms CBAM start date for 2027", "Financial Times", {CBAM}, set(), {"영국"}, 1),
    ("Article 6 carbon credits deal signed at COP31", "Carbon Pulse", {CREDIT, NDC}, set(), set(), 1),
    ("US states push carbon pricing despite federal rollback", "AP", {PRICE}, set(), {"미국"}, 1),
    ("India launches carbon credit trading scheme", "Mint", {CREDIT}, set(), {"인도"}, 1),
    ("Japan GX-ETS enters mandatory phase", "Nikkei", {ETS}, set(), {"일본"}, 1),
    ("Net zero targets slip as companies miss deadlines", "Guardian", {NDC}, set(), set(), 1),
    # 단어 경계 함정: Markets/Sets/Status 가 ETS·US 로 걸리면 안 된다
    ("Stock Markets rally as Fed sets rates", "CNBC", set(), {ETS}, set(), 0),   # 'stock market' 제외 규칙 (확실한 무관)
    ("Status update on regional water projects", "Local News", set(), {ETS}, set(), None),
    # 무관 (확실한 패턴)
    ("Carbon Fiber Market Size, Share & Forecast Report 2026-2033", "openPR", set(), set(), set(), 0),
    ("Bitcoin price surges past $150,000", "CoinDesk", set(), set(), set(), 0),
    ("Brexit talks resume over fishing rights", "BBC", set(), set(), set(), 0),
    ("한국은행 기준금리 동결", "연합뉴스", set(), set(), set(), 0),
    ("[공시] OO전자, 3분기 영업이익 발표", "이데일리", set(), set(), set(), 0),
    # 미판정 (약한 단어만 있거나 단서 없음) — 무관으로 숨기면 안 된다
    ("기후 박람회 개최 소식", "지역신문", set(), set(), set(), None),
    ("Rethinking Linking", "Carbon Market Watch", set(), set(), set(), None),
    ("에너지 요금 인상 검토", "KBS", set(), set(), set(), None),
    ("Climate week opens in New York", "Reuters", set(), set(), set(), None),
    ("탄소 저감 기술 세미나", "전자신문", set(), set(), set(), None),
]


@pytest.mark.parametrize("title, source, must, must_not, regions, _rel", TITLES_30, ids=[t[0][:25] for t in TITLES_30])
def test_f3_01_tagging_30_titles(title, source, must, must_not, regions, _rel):
    topics, regs = tagging.tag_text(title)
    assert must <= set(topics), (topics, must)
    assert not (must_not & set(topics)), topics
    assert regions <= set(regs), (regs, regions)


@pytest.mark.parametrize("title, source, _m, _n, _r, rel", TITLES_30, ids=[t[0][:25] for t in TITLES_30])
def test_f6_01_relevance_30_titles(title, source, _m, _n, _r, rel):
    got, reason = filters.judge_relevance(title, source)
    assert got == rel, reason


@pytest.mark.parametrize("title, expected", [
    # QA-B3: README 가 제외한다고 안내한 패턴 (한국어 기준금리·증권 공시, 비트코인)
    ("한국은행 기준금리 동결", 0),
    ("[공시] OO전자, 3분기 영업이익 발표", 0),
    ("Bitcoin price surges past $150,000", 0),
    ("비트코인 2억원 돌파", 0),
    # 정책 용어가 있으면 이 패턴이 있어도 관련 (제외는 정책 용어가 없을 때만)
    ("기준금리 인상에도 배출권 가격 강세", 1),
    ("[공시] OO제철, 탄소국경조정제도(CBAM) 대응 투자 결정", 1),
    ("Bitcoin miners face new carbon tax in Norway", 1),
    # 비슷하지만 다른 말은 걸리지 않는다
    ("공시지가 상승에 재산세 부담", None),
])
def test_qa_b3_exclude_patterns(title, expected):
    assert filters.judge_relevance(title)[0] == expected


def test_f6_01_no_relevant_title_is_excluded():
    """원칙: 관련 기사를 잘못 숨기는 것이 더 나쁘다. 기대 '관련' 30건 중 무관(0)으로 판정된 것이 없어야 한다."""
    wrong = [t for t, s, *_x, rel in TITLES_30 if rel == 1 and filters.judge_relevance(t, s)[0] == 0]
    assert wrong == []


# ---------------------------------------------------------------- F14: 일반어가 상위 급증 키워드에 없다 (실제 제목 고정 DB)
def test_f14_01_no_generic_terms_in_top15_on_fixture(tmp_path):
    shutil.copy(FIXTURE_DB, tmp_path / "s.db")
    conn = db.connect(tmp_path / "s.db")
    try:
        terms = [t["term"] for t in analysis.build_report_data(conn=conn, now=FIX_NOW)["rising_terms"][:15]]
    finally:
        conn.close()
    prd_examples = {"carbon", "energy", "에너지", "확대"}
    generic = {w.lower() for w in config.GENERIC_TERMS | config.BOILERPLATE_TERMS} | prd_examples
    assert terms and not [t for t in terms if t.lower() in generic]


# ---------------------------------------------------------------- F10: export 결과를 SQL 로 따로 계산한 기대값과 대조
def test_f10_01_export_matches_independent_sql(tmp_path):
    shutil.copy(FIXTURE_DB, tmp_path / "s.db")
    conn = db.connect(tmp_path / "s.db")
    try:
        f = query.make_filters(date_from="2026-11-01", date_to="2026-11-03", topic="CBAM", region="EU")
        items = query.find(conn, f)
        start = datetime(2026, 11, 1, tzinfo=config.KST).astimezone(timezone.utc).isoformat()
        end = datetime(2026, 11, 4, tzinfo=config.KST).astimezone(timezone.utc).isoformat()
        rows = conn.execute(
            f"SELECT title FROM articles WHERE relevant IS NOT 0 AND published >= ? AND published < ? "
            f"AND ','||{db.EFFECTIVE_TOPICS}||',' LIKE '%,CBAM/탄소국경,%' AND ','||{db.EFFECTIVE_REGIONS}||',' LIKE '%,EU,%' "
            f"ORDER BY published DESC", (start, end)).fetchall()
    finally:
        conn.close()
    assert [i["title"] for i in items] == [r["title"] for r in rows] and len(rows) >= 2
    out = tmp_path / "out.csv"
    query.export_csv(items, out)
    assert out.read_bytes()[:3] == b"\xef\xbb\xbf"
    got = list(csv.reader(out.open(encoding="utf-8-sig")))
    assert [r[2] for r in got[1:]] == [r["title"] for r in rows]
    assert all(re.search("[가-힣]", r[5]) for r in got[1:])          # 주제 열의 한글이 깨지지 않음


# ---------------------------------------------------------------- 비기능: 소요 시간, 로그 파일, 비밀 값이 남지 않음
FAKE = {"ANTHROPIC_API_KEY": "sk-ant-FAKE-qa-0000000000000000", "SMTP_HOST": "smtp.invalid", "SMTP_USER": "qa-user@invalid",
        "SMTP_PASSWORD": "FAKE-SMTP-PW-qa-1234", "NOTIFY_TO": "qa-to@invalid", "ASSEMBLY_API_KEY": "FAKE-ASSEMBLY-KEY-qa"}


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "data" / "articles.db")
    monkeypatch.setattr(config, "REPORT_DIR", tmp_path / "reports")
    monkeypatch.setattr(config, "LOG_DIR", tmp_path / "logs")
    now = datetime.now(timezone.utc)
    arts = [Article(title=f"EU CBAM 배출권 기사 {i}", url=f"https://example.com/{i}", source="연합뉴스", lang="ko", query="q",
                    summary="", published=(now - timedelta(hours=i)).isoformat()) for i in range(40)]
    monkeypatch.setattr(pipeline, "build_sources", lambda names=None: [FakeSource(arts)])
    monkeypatch.setattr(pipeline, "search_coverage", lambda conn, **k: {})
    return tmp_path


def test_nf04_nf06_run_time_and_log_file(isolated, monkeypatch):
    monkeypatch.setattr(config, "ENABLE_LLM", False)
    t0 = time.perf_counter()
    assert main.main(["run"]) == 0
    elapsed = time.perf_counter() - t0
    assert elapsed < 30, elapsed                      # 네트워크를 뺀 처리 시간 (실제 수집 시간은 PC 에서 측정)
    assert (isolated / "logs" / "app.log").stat().st_size > 0
    print(f"run (모킹 40건) {elapsed:.2f}s")


def test_nf09_secrets_never_written_to_logs_db_or_report(isolated, monkeypatch, capsys):
    for k, v in FAKE.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(config, "ENABLE_LLM", True)
    from carbon import llm, notify

    class AuthenticationError(Exception):      # SDK 의 인증 오류와 같은 이름 (llm 은 클래스 이름으로 판별)
        pass

    class FailingBackend:
        """실제 API 를 부르지 않고, 키가 설정된 경로를 끝까지 태운 뒤 인증 오류를 낸다."""
        model = config.LLM_MODEL

        def __init__(self, *a, **k):
            pass

        def complete(self, *a, **k):
            raise AuthenticationError("Error code: 401 - invalid x-api-key")

    monkeypatch.setattr(llm, "AnthropicBackend", FailingBackend)

    def fake_smtp(*a, **k):
        raise OSError("connection refused")
    monkeypatch.setattr(notify.smtplib, "SMTP", fake_smtp)
    main.main(["run", "--notify"])          # SMTP 실패로 1 이 나와도 된다. 비밀 값이 어디에도 남지 않아야 한다
    main.main(["export", "--out", str(isolated / "reports" / "e.csv")])
    printed = capsys.readouterr()
    blobs = {"console": printed.out + printed.err}
    for p in list((isolated / "logs").rglob("*")) + list((isolated / "reports").rglob("*")):
        if p.is_file():
            blobs[str(p)] = p.read_text(encoding="utf-8", errors="replace")
    conn = sqlite3.connect(isolated / "data" / "articles.db")
    blobs["db"] = "\n".join(str(r) for t in [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
                            for r in conn.execute(f"SELECT * FROM {t}"))
    conn.close()
    secrets = [FAKE["ANTHROPIC_API_KEY"], FAKE["SMTP_PASSWORD"], FAKE["ASSEMBLY_API_KEY"], FAKE["SMTP_USER"], FAKE["NOTIFY_TO"]]
    leaks = [(where, s) for where, text in blobs.items() for s in secrets if s in text]
    assert leaks == []
    log = blobs[str(isolated / "logs" / "app.log")]
    assert "AuthenticationError" in log or "인증" in log          # 키가 있는 LLM 경로를 실제로 탔다
    assert "SMTP" in log or "connection refused" in log            # 발송 경로도 탔다


# ---------------------------------------------------------------- QA-B1: 예약 실행용 bat 파일
ROOT = Path(__file__).resolve().parent.parent


def test_qa_b1_run_daily_bat_exists_and_matches_readme():
    bat = ROOT / "run_daily.bat"
    assert bat.exists(), "README 의 schtasks 안내가 가리키는 run_daily.bat 이 없다"
    raw = bat.read_bytes()
    assert b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"")          # cmd.exe 용 CRLF
    text = raw.decode("ascii")                                             # 한글 경로 없이 ASCII 만 (코드페이지 문제 방지)
    assert 'cd /d "%~dp0"' in text                                         # bat 이 있는 프로젝트 폴더로 이동
    assert re.search(r"main\.py run >> logs\.txt 2>&1", text)              # 출력과 오류를 logs.txt 에 덧붙임
    assert "PYTHONIOENCODING=utf-8" in text
    assert "exit /b %errorlevel%" in text.lower()                        # 실패 코드를 스케줄러에 전달

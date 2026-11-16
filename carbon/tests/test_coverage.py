from datetime import timedelta

import config
from carbon import db, pipeline
from carbon.sources.base import official_id
from tests.conftest import NOW, FakeSource, make_article


class FakeSearcher:
    """GoogleNewsSource.search 대역: 검색어별 결과를 돌려주고 호출을 기록한다."""

    delay = 0

    def __init__(self, results=None, fail_for=()):
        self.results = results or {}      # 검색어에 이 문자열이 들어 있으면 해당 기사 목록을 돌려준다
        self.fail_for = fail_for
        self.calls = []

    def search(self, query, lang="ko", days_back=None):
        self.calls.append((query, lang, days_back))
        if any(f in query for f in self.fail_for):
            raise ConnectionError("down")
        for key, arts in self.results.items():
            if key in query:
                return list(arts)
        return []


def official(title, url, days_ago=1.0, agency="기후에너지환경부"):
    a = make_article(title, days_ago=days_ago, url=url, source=agency)
    a.source_type, a.agency = "official", agency
    a.id = official_id(url)
    return a


def news(title, days_ago=0.3):
    return make_article(title, days_ago=days_ago, url="https://n.test/" + title[:8])


def load(conn, articles):
    pipeline.collect([FakeSource(articles)], conn=conn)


def checks(conn, title):
    r = conn.execute("SELECT coverage_checks, coverage_checked_at FROM articles WHERE title=?", (title,)).fetchone()
    return r["coverage_checks"], r["coverage_checked_at"]


# ----------------------------------------------------------------------------- 검색어
def test_coverage_query_cleans_prefix_quotes_and_length():
    q = pipeline.coverage_query("(한국환경공단 보도자료 10. 30.)한국환경공단, 실증에서 사업화로 기후환경 기술-시장 협력 사다리")
    assert not q.startswith("(") and "보도자료 10" not in q
    assert pipeline.coverage_query("[보도자료]제4차 한-말레이시아 기후변화 대화 개최") == "제4차 한-말레이시아 기후변화 대화 개최"
    assert pipeline.coverage_query("「교통ㆍ에너지ㆍ환경세법 시행령」 일부개정령(안) 입법예고") == "교통ㆍ에너지ㆍ환경세법 시행령 일부개정령 안 입법예고"[:config.COVERAGE_QUERY_CHARS]
    long = pipeline.coverage_query("배출권거래제 " * 20)
    assert len(long) <= config.COVERAGE_QUERY_CHARS and not long.endswith(" ")


# ----------------------------------------------------------------------------- 대상 선택
ETS_DOC = "배출권거래제 4기 할당계획 입법예고"
EDU_DOC = "지방정부 10곳 2026년도 환경교육도시로 선정… 지역 중심 탄소중립 사회 실현에 기여"


def test_only_recent_carbon_related_official_docs_are_searched_direct_first(conn):
    load(conn, [
        official("지역 환경교육도시 선정 탄소중립 사회", "https://x/1"),                    # 간접(탄소중립 50)
        official(ETS_DOC, "https://x/2"),                                                  # 직접(배출권거래제)
        official("2026년도 분산 푸른하늘 유공 표창 후보자 공모", "https://x/3"),            # 키워드 없음 → 미분류 → 검색 안 함
        official("배출권거래제 오래된 고시", "https://x/4", days_ago=config.COVERAGE_DOC_DAYS + 3),   # 너무 오래됨
        make_article("뉴스는 대상 아님 배출권거래제"),
    ])
    s = FakeSearcher()
    res = pipeline.search_coverage(conn, s, now=NOW)
    assert res["docs"] == 2 and res["searched"] == 2
    assert [c[0] for c in s.calls][0].startswith("배출권거래제 4기")             # 영향도 높은 문서부터
    assert len(s.calls) == 2


def test_english_search_for_eu_documents_and_days_back(conn):
    load(conn, [official("Commission proposes 2040 climate target", "https://ec/1", agency="European Commission")])
    s = FakeSearcher()
    pipeline.search_coverage(conn, s, now=NOW)
    assert s.calls[0][1] == "en" and s.calls[0][2] == config.COVERAGE_DAYS_BACK


def test_per_run_limit(conn):
    load(conn, [official(f"배출권거래제 공고 {i}", f"https://x/{i}", days_ago=0.1 * i + 0.1) for i in range(config.COVERAGE_MAX_PER_RUN + 5)])
    s = FakeSearcher()
    res = pipeline.search_coverage(conn, s, now=NOW)
    assert res["docs"] == config.COVERAGE_MAX_PER_RUN == len(s.calls)


# ----------------------------------------------------------------------------- 저장 규칙
def test_only_results_similar_enough_to_the_document_are_stored(conn):
    load(conn, [official(EDU_DOC, "https://x/1")])
    s = FakeSearcher({"환경교육도시": [
        news("기후부, 지방정부 10곳 '2026년도 환경교육도시' 선정 - 뉴시스"),       # 같은 사안
        news("전혀 상관없는 야구 경기 결과 - 스포츠뉴스"),                          # 엉뚱한 결과
    ]})
    res = pipeline.search_coverage(conn, s, now=NOW)
    assert res["results"] == 2 and res["kept"] == 1 and res["new"] == 1
    titles = [r["title"] for r in conn.execute("SELECT title FROM articles WHERE source_type='news'")]
    assert titles == ["기후부, 지방정부 10곳 '2026년도 환경교육도시' 선정 - 뉴시스"]
    q = conn.execute("SELECT query FROM articles WHERE source_type='news'").fetchone()[0]
    assert q.startswith("공식문서:")


def test_results_per_query_cap(conn):
    load(conn, [official(EDU_DOC, "https://x/1")])
    many = [news(f"지방정부 10곳 2026년도 환경교육도시로 선정 소식 {i} - 매체{i}") for i in range(config.COVERAGE_RESULTS_PER_QUERY + 6)]
    res = pipeline.search_coverage(conn, FakeSearcher({"환경교육도시": many}), now=NOW)
    assert res["results"] == config.COVERAGE_RESULTS_PER_QUERY


def test_duplicate_news_is_not_stored_twice(conn):
    load(conn, [official(EDU_DOC, "https://x/1"), news("기후부, 지방정부 10곳 '2026년도 환경교육도시' 선정 - 뉴시스")])
    res = pipeline.search_coverage(conn, FakeSearcher({"환경교육도시": [news("기후부, 지방정부 10곳 '2026년도 환경교육도시' 선정 - 뉴시스")]}), now=NOW)
    assert res["kept"] == 1 and res["new"] == 0


# ----------------------------------------------------------------------------- 횟수 제한과 재시도
def test_each_document_is_searched_at_most_twice_with_a_gap(conn):
    load(conn, [official(ETS_DOC, "https://x/1")])
    s = FakeSearcher()
    assert pipeline.search_coverage(conn, s, now=NOW)["searched"] == 1
    assert checks(conn, ETS_DOC)[0] == 1
    assert pipeline.search_coverage(conn, s, now=NOW + timedelta(hours=config.COVERAGE_RETRY_HOURS - 1))["docs"] == 0   # 아직 이르다
    assert pipeline.search_coverage(conn, s, now=NOW + timedelta(hours=config.COVERAGE_RETRY_HOURS + 1))["searched"] == 1
    assert checks(conn, ETS_DOC)[0] == 2
    assert pipeline.search_coverage(conn, s, now=NOW + timedelta(hours=config.COVERAGE_RETRY_HOURS * 5))["docs"] == 0     # 세 번째는 없다
    assert len(s.calls) == 2


def test_failed_search_does_not_use_up_an_attempt_and_others_continue(conn):
    load(conn, [official(ETS_DOC, "https://x/1"), official("탄소중립 사회 선정 안내 공고", "https://x/2")])
    s = FakeSearcher(fail_for=("배출권거래제",))
    res = pipeline.search_coverage(conn, s, now=NOW)
    assert res["failed"] == 1 and res["searched"] == 1
    assert checks(conn, ETS_DOC)[0] == 0                              # 실패한 문서는 다음 실행에서 다시 시도
    assert checks(conn, "탄소중립 사회 선정 안내 공고")[0] == 1
    s.fail_for = ()
    assert pipeline.search_coverage(conn, s, now=NOW)["searched"] == 1


# ----------------------------------------------------------------------------- 연결까지
def test_searched_news_gets_linked_to_its_official_document(conn):
    load(conn, [official(EDU_DOC, "https://x/1", days_ago=0.8)])
    s = FakeSearcher({"환경교육도시": [news("기후부, 지방정부 10곳 '2026년도 환경교육도시' 선정 - 뉴시스")]})
    pipeline.search_coverage(conn, s, now=NOW)
    res = pipeline.link_news(conn, now=NOW)
    assert res["confirmed"] == 1
    row = conn.execute("SELECT official_status FROM articles WHERE source_type='news'").fetchone()
    assert row["official_status"] == "confirmed"


def test_v5_adds_coverage_columns(conn):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(articles)")}
    assert {"coverage_checks", "coverage_checked_at"} <= cols
    assert conn.execute("PRAGMA user_version").fetchone()[0] == len(db.MIGRATIONS) >= 5

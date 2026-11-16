from datetime import timedelta

import pytest

import config
from carbon import analysis, linking, pipeline
from carbon.sources.base import official_id
from tests.conftest import NOW, FakeSource, make_article


def doc(title, days_ago=1.0, agency="기후에너지환경부"):
    return {"title": title, "published": (NOW - timedelta(days=days_ago)).isoformat(), "agency": agency}


def news(title, days_ago=0.0):
    return {"title": title, "published": (NOW - timedelta(days=days_ago)).isoformat()}


ETS_DOC = "배출권거래제 4기 할당계획 입법예고"


# ----------------------------------------------------------------------------- 점수 계산
def test_same_policy_same_number_and_word_links():
    score, ev = linking.score_pair(news("4기 배출권 할당 확정…기업 부담 커진다"), doc(ETS_DOC))
    assert score >= config.LINK_MIN_SCORE
    assert "배출권거래제" in ev["entities"] and "4기" in ev["numbers"]


def test_topic_only_overlap_is_not_enough():
    """같은 제도 이야기라는 것만으로는 연결하지 않는다. 사안(숫자·핵심 단어)이 겹쳐야 한다."""
    score, ev = linking.score_pair(news("배출권 가격 하락세…거래량 급감"), doc(ETS_DOC))
    assert score < config.LINK_MIN_SCORE
    assert ev["entities"] == ["배출권거래제"]


def test_unrelated_topics_do_not_link():
    score, _ = linking.score_pair(news("태양광 보급사업 신청 시작"), doc(ETS_DOC))
    assert score == 0


def test_josa_is_stripped_so_word_forms_match():
    assert "할당계획" in linking.tokens("할당계획을 발표했다")
    assert "할당계획" in linking.tokens("할당계획이 나왔다")
    assert linking.tokens("할당계획을") & linking.tokens("할당계획")


def test_generic_words_and_common_years_are_ignored():
    assert linking.tokens("정부 기후 에너지 정책 발표") == set()
    assert linking.numbers("2026년 계획") == set()
    assert linking.numbers("제3차 4기 2035 NDC 31호") >= {"3차", "4기", "2035", "31호"}
    assert "10" not in linking.numbers("10곳 선정")                    # 단위 없는 두 자리 숫자는 제외


def test_time_window_is_enforced():
    late = news("4기 배출권 할당 확정…기업 부담 커진다", days_ago=0)
    old_doc = doc(ETS_DOC, days_ago=config.LINK_AFTER_DAYS + 3)
    assert linking.score_pair(late, old_doc)[0] == 0                  # 공식 문서가 너무 오래됨
    early = news("4기 배출권 할당 확정…기업 부담 커진다", days_ago=5)
    future_doc = doc(ETS_DOC, days_ago=1)                              # 문서가 뉴스보다 4일 뒤
    assert linking.score_pair(early, future_doc)[0] == 0
    assert linking.score_pair(news("4기 배출권 할당 확정", days_ago=1.5), doc(ETS_DOC, days_ago=1))[0] > 0


def test_agency_mention_adds_points():
    _, base_ev = linking.score_pair(news("4기 배출권 할당 확정"), doc(ETS_DOC))
    _, ev = linking.score_pair(news("환경부, 4기 배출권 할당 확정"), doc(ETS_DOC))
    assert ev["agency"] and not base_ev["agency"]


# 실제 데이터에서 나온 사례로 보정한 쌍들 (calibrate: 공식 문서 제목, 뉴스 제목, 연결돼야 하는가)
OFF_PUB = "2026-11-01T15:00:00+00:00"      # 2026-11-02 00:00 KST
NEWS_PUB = "2026-11-02T06:00:00+00:00"
CALIBRATION = [
    # 보도자료를 거의 그대로 옮긴 기사 / 일부만 바꾼 제목 → 연결
    (True, "지방정부 10곳 2026년도 환경교육도시로 선정… 지역 중심 탄소중립 사회 실현에 기여",
     "기후부, 지방정부 10곳 '2026년도 환경교육도시' 선정 - 뉴시스"),
    (True, "지방정부 10곳 2026년도 환경교육도시로 선정… 지역 중심 탄소중립 사회 실현에 기여",
     "지방정부 10곳 2026년도 환경교육도시로 선정… 지역 중심 탄소중립 사회 실현에 기여 - 한국경제"),
    (True, "우리의(지구를 위한) 기후행동, 전기차 전환 서명에 동참해 주세요", "지구를 위한 기후행동, 전기차 전환 서명 동참 캠페인 - 매일경제"),
    (True, "배출권거래제 4기 할당계획 입법예고", "4기 배출권 할당계획 입법예고…기업 부담 커진다 - 서울경제"),
    # 비슷해 보이지만 다른 사안 → 연결하지 않음
    (False, "지방정부 10곳 2026년도 환경교육도시로 선정… 지역 중심 탄소중립 사회 실현에 기여",
     "수원·안산·시흥·광명 ‘환경교육도시’ 재지정… 탄소중립 실현 기여 - 경기일보"),
    (False, "제6차 한-아세안 환경‧기후변화 대화 개최", "제4차 한-말레이시아 기후변화 대화 개최 - 연합뉴스"),
    (False, "제3차 고준위 방사성폐기물 관리 기본계획 수립을 위한 국민 의견수렴 추진", "제4차 고준위 방사성폐기물 관리 기본계획 의견수렴 시작 - 뉴스1"),   # 회차만 다름
    (False, "배출권거래제 4기 할당계획 입법예고", "배출권거래제 3기 할당 결과 분석 - 서울경제"),                                             # 3기 vs 4기
    (False, "배출권거래제 4기 할당계획 입법예고", "[온실가스 배출권] 11월 2일 KAU26, 250원 하락하며 3만원 턱걸이 - 데일리e뉴스"),            # 가격 뉴스
    (False, "배출권거래제 4기 할당계획 입법예고", "배출권 가격 하락세…거래량 급감 - 서울경제"),
    (False, "배출권거래제 4기 할당계획 입법예고", "환경부, 배출권 시장 안정화 대책 검토 - 서울경제"),                                         # 같은 제도 + 기관명만
    (False, "배출권거래제 4기 할당계획 입법예고", "환경부 장관 \"배출권 가격 안정에 최선\" - 뉴시스"),
    (False, "영덕 신규원전 전략환경영향평가서 초안 공고", "태양광부터 기후대응까지 탄소중립 기반 다진다 - 전국도민일보"),
]


@pytest.mark.parametrize("expected, official_title, news_title", CALIBRATION)
def test_calibration_pairs(expected, official_title, news_title):
    score, ev = linking.score_pair({"title": news_title, "published": NEWS_PUB},
                                   {"title": official_title, "agency": "기후에너지환경부", "published": OFF_PUB})
    assert (score >= config.LINK_MIN_SCORE) is expected, (score, ev)


def test_same_policy_name_plus_agency_alone_never_links():
    """같은 제도 이야기 + 기관명 + 직후 보도 가점만으로는 연결하지 않는다 (같은 사안이라는 근거가 하나는 있어야 한다)."""
    score, ev = linking.score_pair(
        {"title": "환경부, 배출권 시장 안정화 대책 검토 - 서울경제", "published": NEWS_PUB},
        {"title": ETS_DOC, "agency": "기후에너지환경부", "published": OFF_PUB})
    assert ev["entities"] == ["배출권거래제"] and ev["agency"] and ev["fresh"] and not ev["event_specific"]
    assert score == config.LINK_MIN_SCORE - 1


def test_entity_words_are_not_double_counted_as_shared_tokens():
    _, ev = linking.score_pair({"title": "배출권 시장 동향", "published": NEWS_PUB},
                               {"title": ETS_DOC, "agency": "기후에너지환경부", "published": OFF_PUB})
    assert "배출권" not in ev["tokens"]


def test_outlet_suffix_is_ignored_in_matching():
    assert linking.strip_outlet("환경교육도시 선정 - 뉴시스") == "환경교육도시 선정"
    s1, ev = linking.score_pair({"title": "환경교육도시 10곳 선정 - 환경교육도시뉴스", "published": NEWS_PUB},
                                {"title": "환경교육도시 10곳 선정", "agency": "기후에너지환경부", "published": OFF_PUB})
    assert ev["similarity"] == 1.0                                       # 언론사 이름은 유사도에 들어가지 않는다


def test_sequence_conflict_detection():
    assert linking.sequence_conflict("제3차 기본계획", "제4차 기본계획")
    assert linking.sequence_conflict("4기 할당계획", "3기 결과")
    assert not linking.sequence_conflict("4기 할당계획", "4기 배출권")
    assert not linking.sequence_conflict("할당계획 발표", "4기 배출권")             # 한쪽에만 번호가 있으면 충돌 아님
    assert not linking.sequence_conflict("3차 계획", "4기 계획")                  # 단위가 다르면 비교하지 않음


def test_similarity_bounds():
    assert linking.similarity("같은 제목입니다", "같은 제목입니다") == 1.0
    assert linking.similarity("가나다라", "마바사아") == 0.0
    assert linking.similarity("", "무엇") == 0.0


def test_quoted_statute_name_counts_as_shared_entity():
    official = doc("「산업집적활성화 및 공장설립에 관한 법률 시행령」 일부개정령(안) 입법예고", agency="산업통상부")
    score, ev = linking.score_pair(news("산업집적활성화 및 공장설립에 관한 법률 시행령 개정 추진"), official)
    assert any(e.startswith("법령:") for e in ev["entities"])


def test_best_links_returns_top_within_margin_only():
    a = doc("배출권거래제 4기 할당계획 입법예고")
    b = doc("배출권거래제 4기 할당계획 확정 고시")
    c = doc("배출권거래제 시행규칙 일부개정령안")
    links = linking.best_links(news("4기 배출권 할당계획 확정"), [c, a, b])
    titles = [o["title"] for o, _, _ in links]
    assert titles[0] in (a["title"], b["title"])
    assert c["title"] not in titles                                    # 점수가 낮은 문서는 제외
    assert len(links) <= config.LINK_MAX_PER_NEWS


def test_no_candidates_means_no_links():
    assert linking.best_links(news("아무 관련 없는 뉴스"), [doc(ETS_DOC)]) == []


# ----------------------------------------------------------------------------- DB 연결과 재시도
def official(title, url, days_ago=1.0, agency="기후에너지환경부"):
    a = make_article(title, days_ago=days_ago, url=url, source=agency)
    a.source_type, a.agency = "official", agency
    a.id = official_id(url)
    return a


def load(conn, articles):
    pipeline.collect([FakeSource(articles)], conn=conn)


def status(conn, title):
    return conn.execute("SELECT official_status, link_attempts FROM articles WHERE title=?", (title,)).fetchone()


def test_status_defaults(conn):
    load(conn, [make_article("배출권거래제 뉴스"), official(ETS_DOC, "https://x.test/1")])
    assert status(conn, "배출권거래제 뉴스")["official_status"] == "unconfirmed"
    assert status(conn, ETS_DOC)["official_status"] == "n/a"


def test_link_news_confirms_and_records_evidence(conn):
    load(conn, [official(ETS_DOC, "https://x.test/1"), make_article("4기 배출권 할당 확정…기업 부담 커진다", days_ago=0.3),
                make_article("태양광 보급사업 신청 시작", days_ago=0.3)])
    res = pipeline.link_news(conn, now=NOW)
    assert res == {"tried": 2, "confirmed": 1, "unconfirmed": 1, "retried": 0}
    assert status(conn, "4기 배출권 할당 확정…기업 부담 커진다")["official_status"] == "confirmed"
    assert status(conn, "태양광 보급사업 신청 시작")["official_status"] == "unconfirmed"
    row = conn.execute("SELECT * FROM article_links").fetchone()
    assert row["score"] >= config.LINK_MIN_SCORE and "배출권거래제" in row["method"]


def test_unconfirmed_news_is_retried_once_after_retry_hours_then_stops(conn):
    load(conn, [make_article("4기 배출권 할당 확정…기업 부담 커진다", days_ago=0.3)])
    t = "4기 배출권 할당 확정…기업 부담 커진다"
    assert pipeline.link_news(conn, now=NOW)["tried"] == 1 and status(conn, t)["link_attempts"] == 1
    # 48시간이 지나기 전에는 다시 시도하지 않는다
    assert pipeline.link_news(conn, now=NOW + timedelta(hours=config.LINK_RETRY_HOURS - 1))["tried"] == 0
    # 그 사이 공식 문서가 올라왔다: 48시간 뒤 재시도에서 연결된다
    load(conn, [official(ETS_DOC, "https://x.test/1", days_ago=0.2)])
    later = NOW + timedelta(hours=config.LINK_RETRY_HOURS + 1)
    res = pipeline.link_news(conn, now=later)
    assert res["tried"] == 1 and res["retried"] == 1 and res["confirmed"] == 1
    assert status(conn, t)["official_status"] == "confirmed"


def test_still_unconfirmed_after_retry_is_final(conn):
    load(conn, [make_article("전혀 다른 소식 하나", days_ago=0.3)])
    pipeline.link_news(conn, now=NOW)
    pipeline.link_news(conn, now=NOW + timedelta(hours=config.LINK_RETRY_HOURS + 1))
    assert status(conn, "전혀 다른 소식 하나")["link_attempts"] == 2
    assert pipeline.link_news(conn, now=NOW + timedelta(hours=config.LINK_RETRY_HOURS * 3))["tried"] == 0   # 더 시도하지 않음


def test_confirmed_news_is_not_touched_again(conn):
    load(conn, [official(ETS_DOC, "https://x.test/1"), make_article("4기 배출권 할당 확정…기업 부담 커진다", days_ago=0.3)])
    pipeline.link_news(conn, now=NOW)
    assert pipeline.link_news(conn, now=NOW + timedelta(hours=100))["tried"] == 0


def test_relink_recomputes_everything_in_window(conn):
    load(conn, [official(ETS_DOC, "https://x.test/1"), make_article("4기 배출권 할당 확정…기업 부담 커진다", days_ago=0.3)])
    pipeline.link_news(conn, now=NOW)
    old_min = config.LINK_MIN_SCORE
    try:
        config.LINK_MIN_SCORE = 999                                    # 기준을 매우 높게 고치고 다시 계산
        res = pipeline.link_news(conn, now=NOW, relink=True)
    finally:
        config.LINK_MIN_SCORE = old_min
    assert res["confirmed"] == 0 and res["unconfirmed"] == 1
    assert conn.execute("SELECT COUNT(*) FROM article_links").fetchone()[0] == 0


def test_old_news_outside_window_is_ignored(conn):
    load(conn, [make_article("4기 배출권 할당 확정", days_ago=config.LINK_WINDOW_DAYS + 2)])
    assert pipeline.link_news(conn, now=NOW)["tried"] == 0


# ----------------------------------------------------------------------------- 분석 결과
def test_analysis_exposes_links_and_excludes_unconfirmed_news_from_policy_summary(conn):
    load(conn, [
        official(ETS_DOC, "https://x.test/1", days_ago=1),
        official("COP31 합의문 채택", "https://x.test/2", days_ago=1),
        make_article("4기 배출권 할당 확정…기업 부담 커진다", days_ago=0.3),
        make_article("충격! 배출권 대폭 삭감 확정됐다", days_ago=0.3),         # 공식 문서와 무관한 자극적 제목
    ])
    pipeline.link_news(conn, now=NOW)
    d = analysis.build_report_data(conn=conn, now=NOW)
    by_title = {a["title"]: a for a in d["articles"]}
    confirmed = by_title["4기 배출권 할당 확정…기업 부담 커진다"]
    assert confirmed["official_status"] == "confirmed"
    link = confirmed["official_links"][0]
    assert link["title"] == ETS_DOC and link["stage"] == "proposed" and link["impact"] == "direct"   # 공식 문서의 값 그대로
    unconf = by_title["충격! 배출권 대폭 삭감 확정됐다"]
    assert unconf["official_status"] == "unconfirmed" and unconf["official_links"] == []

    s = d["policy_summary"]
    assert s["official_total"] == 2                                    # 정책 단계·영향도 집계는 공식 문서만
    assert s["stage"] == {"decided": 0, "proposed": 1, "unknown": 1}
    assert s["impact"]["direct"] == 1 and s["impact"]["reference"] == 1
    assert (s["news_total"], s["news_confirmed"], s["news_unconfirmed"]) == (2, 1, 1)
    # '확정'이라는 단어가 든 뉴스가 있어도 정책 단계 '확정' 집계는 0 이다
    assert s["stage"]["decided"] == 0

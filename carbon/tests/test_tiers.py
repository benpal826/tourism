from datetime import timedelta

import pytest

import config
from carbon import analysis, pipeline, render, tiers
from carbon.sources.base import official_id
from tests.conftest import NOW, FakeSource, make_article


def tier(name, domain="", count=0, source_type="news"):
    return tiers.classify_source(name, domain, count, source_type)


# ----------------------------------------------------------------------------- 도메인
@pytest.mark.parametrize("value, expected", [
    ("https://www.ebn.co.kr/news/1", "ebn.co.kr"),
    ("www.ebn.co.kr", "ebn.co.kr"),
    ("https://technovalue.com/", "technovalue.com"),
    ("Open4business.com.ua.", "open4business.com.ua"),
    ("UA.NEWS", "ua.news"),
    ("https://user@host.example.com:8080/x", "host.example.com"),
    ("한국경제", ""), ("The Financial Express", ""), ("", ""),
])
def test_domain_of(value, expected):
    assert tiers.domain_of(value) == expected


# ----------------------------------------------------------------------------- 등급 규칙
def test_official_sources_and_official_domains_are_tier_1():
    assert tier("기후에너지환경부", source_type="official") == tiers.TierResult(1, "official-source")
    assert tier("정책브리핑", "korea.kr").tier == 1
    assert tier("환경부", "mcee.go.kr").reason == "domain:go.kr"
    assert tier("European Commission", "ec.europa.eu").tier == 1
    assert tier("UNFCCC", "unfccc.int").tier == 1


def test_domain_suffix_match_does_not_fire_on_lookalikes():
    assert tier("가짜", "fakego.kr", count=1).tier == 0              # 'go.kr' 로 끝나지만 .go.kr 이 아님
    assert tier("x", "notgov.example.com", count=1).tier == 0


def test_press_release_sites_are_tier_3():
    r = tier("openPR.com", "openpr.com", count=1)
    assert (r.tier, r.reason) == (3, "press-release-site:openpr.com")
    assert tier("PR Newswire", "prnewswire.com").tier == 3
    assert tier("뉴스와이어", "newswire.co.kr").tier == 3


@pytest.mark.parametrize("name", ["한국경제인협회", "대한상공회의소", "환경운동연합", "녹색연합", "그린피스 코리아",
                                  "World Nuclear Association", "Clean Air Foundation", "Greenpeace", "Climate Action Coalition"])
def test_organizations_are_tier_3_by_name(name):
    r = tier(name, count=10)
    assert r.tier == 3 and r.reason.startswith("name-pattern:")


@pytest.mark.parametrize("name", ["연합뉴스", "연합인포맥스", "데일리연합", "Associated Press", "ESG경제"])
def test_news_outlets_with_similar_looking_names_are_not_orgs(name):
    assert tier(name, count=1).tier != 3


def test_news_hint_in_name_blocks_org_pattern():
    """'○○협회신문' 처럼 이름에 언론 표지가 있으면 단체로 보지 않는다."""
    assert tier("대한건설협회신문", count=1).tier != 3
    assert tier("전국경제인협회", count=1).tier == 3


def test_or_kr_domain_is_tier_3_unless_news_name():
    assert tier("어떤 포털", "something.or.kr", count=5).reason == "domain:or.kr"
    assert tier("가나다일보", "ganada.or.kr", count=5).tier != 3


def test_major_outlets_are_tier_2_regardless_of_count_and_spacing():
    assert tier("연합뉴스", count=1) == tiers.TierResult(2, "major-outlet-list")
    assert tier("Seoul Economic Daily", count=1).tier == 2
    assert tier("the guardian", count=1).tier == 2
    assert tier("Financial Times", count=1).tier == 2


def test_frequency_decides_the_rest():
    assert tier("에너지플랫폼뉴스", count=config.TIER2_MIN_COUNT).tier == 2
    r = tier("에너지플랫폼뉴스", count=config.TIER2_MIN_COUNT - 1)
    assert r.tier == 0 and "insufficient-evidence" in r.reason


def test_soft_org_names_are_not_reclassified_only_flagged():
    r = tier("Stockholm Environment Institute", count=1)
    assert r.tier == 0 and "review:soft-org-pattern(institute)" in r.reason
    assert tier("한국에너지경제연구원", count=1).tier == 0


def test_org_like_names_and_org_domains_are_flagged_for_review_without_changing_the_tier():
    for name, hint in [("Carnegie Endowment for International Peace", "endowment"), ("Bain & Company", "& company"),
                       ("Boston University", "university"), ("Carbon Market Watch", "watch")]:
        r = tier(name, count=1)
        assert r.tier == 0 and f"review:soft-org-pattern({hint})" in r.reason, name
    r = tier("Carbon Brief", "carbonbrief.org", count=1)
    assert r.tier == 0 and "review:.org-domain" in r.reason
    freq = tier("Some Outlet", "someoutlet.org", count=5)                  # 빈도로 2등급이 돼도 검토 표시는 붙는다
    assert freq.tier == 2 and "review:.org-domain" in freq.reason


def test_ordinary_news_outlets_get_no_review_flag():
    assert "review" not in tier("에너지플랫폼뉴스", "energy.co.kr", count=1).reason
    assert "review" not in tier("Reuters", "reuters.com", count=1).reason


def test_overrides_win_over_every_rule_and_match_name_or_domain(monkeypatch):
    monkeypatch.setattr(config, "SOURCE_TIER_OVERRIDES", {"Kalkine": 0, "greenpeace.org": 2, "한국경제": 3})
    assert tier("Kalkine", count=50) == tiers.TierResult(0, "override")
    assert tier("Greenpeace Korea", "greenpeace.org").tier == 2
    assert tier("한국경제", count=1).tier == 3
    assert tier("연합뉴스", count=1).tier == 2                       # 보정 목록에 없는 곳은 기존 규칙 그대로


# ----------------------------------------------------------------------------- 자극적 표현
def test_sensational_terms_are_found_but_ordinary_climate_words_are_not():
    assert tiers.sensational_terms("충격! 배출권 가격 폭락…업계 발칵") == ["충격", "발칵"]
    assert tiers.sensational_terms("기후위기 대응을 위한 탄소중립 기본법 개정") == []
    assert tiers.sensational_terms("Shocking new carbon tax bombshell") == ["shocking", "bombshell"]
    assert tiers.sensational_terms("shockingly calm markets") == []         # 단어 경계


# ----------------------------------------------------------------------------- DB: 등급 부여와 주소 채우기
def news(title, source, days_ago=0.5, url=""):
    a = make_article(title, days_ago=days_ago, source=source, url="https://n.test/" + title[:6])
    a.source_url = url
    return a


def load(conn, arts):
    pipeline.collect([FakeSource(arts)], conn=conn)


def tier_of(conn, title):
    r = conn.execute("SELECT source_tier, source_tier_reason FROM articles WHERE title=?", (title,)).fetchone()
    return r["source_tier"], r["source_tier_reason"]


def test_assign_tiers_uses_outlet_level_decision_and_records_reasons(conn):
    arts = [news(f"배출권 뉴스 {i}", "에너지플랫폼뉴스") for i in range(3)] + [
        news("보도자료 하나 탄소", "openPR.com", url="https://www.openpr.com/news/1"),
        news("협회 주장 탄소", "한국경제인협회"),
        news("통신 기사 탄소", "연합뉴스"),
        news("한 번 나온 곳 탄소", "처음보는곳"),
    ]
    off = make_article("공식 발표 탄소", source="기후에너지환경부", url="https://mcee.go.kr/1")
    off.source_type, off.agency = "official", "기후에너지환경부"
    off.id = official_id(off.url)
    load(conn, arts + [off])
    res = pipeline.assign_tiers(conn, now=NOW)
    assert res["outlets"] == 5                                              # 뉴스 언론사 5곳 (공식 기관은 따로 1등급 처리)
    assert tier_of(conn, "배출권 뉴스 0")[0] == tier_of(conn, "배출권 뉴스 2")[0] == 2        # 같은 언론사는 같은 등급
    assert tier_of(conn, "보도자료 하나 탄소") == (3, "press-release-site:openpr.com")
    assert tier_of(conn, "협회 주장 탄소")[0] == 3
    assert tier_of(conn, "통신 기사 탄소") == (2, "major-outlet-list")
    assert tier_of(conn, "한 번 나온 곳 탄소")[0] == 0
    assert tier_of(conn, "공식 발표 탄소") == (1, "official-source")


def test_frequency_counts_only_the_recent_window(conn):
    old = config.TIER_WINDOW_DAYS + 5
    load(conn, [news(f"오래된 기사 {i}", "옛날뉴스", days_ago=old + i * 0.1) for i in range(5)])
    pipeline.assign_tiers(conn, now=NOW)
    assert tier_of(conn, "오래된 기사 0")[0] == 0              # 5건이지만 모두 최근 30일 밖


def test_source_url_gives_domain_based_tier_and_backfills_existing_rows(conn):
    load(conn, [news("정부 도메인 기사", "어떤 이름")])                       # 처음에는 주소를 모른다
    pipeline.assign_tiers(conn, now=NOW)
    assert tier_of(conn, "정부 도메인 기사")[0] == 0
    # 같은 기사가 나중에 주소와 함께 다시 수집되면 주소가 채워지고 등급이 바뀐다
    load(conn, [news("정부 도메인 기사", "어떤 이름", url="https://www.korea.kr/news/1")])
    assert conn.execute("SELECT source_url FROM articles WHERE title='정부 도메인 기사'").fetchone()[0] == "https://www.korea.kr/news/1"
    pipeline.assign_tiers(conn, now=NOW)
    assert tier_of(conn, "정부 도메인 기사") == (1, "domain:korea.kr")


def test_assign_tiers_is_idempotent_and_reports_changes(conn):
    load(conn, [news("협회 주장", "한국경제인협회")])
    assert pipeline.assign_tiers(conn, now=NOW)["changed"] == 1
    assert pipeline.assign_tiers(conn, now=NOW)["changed"] == 0


def test_sensational_terms_are_stored_for_news_only(conn):
    off = make_article("충격 공식 발표", url="https://mcee.go.kr/9")
    off.source_type, off.agency = "official", "기후에너지환경부"
    off.id = official_id(off.url)
    load(conn, [news("충격! 탄소세 도입", "A뉴스"), off])
    rows = {r["title"]: r["sensational"] for r in conn.execute("SELECT title, sensational FROM articles")}
    assert rows["충격! 탄소세 도입"] == "충격" and rows["충격 공식 발표"] is None


# ----------------------------------------------------------------------------- 분석: 3등급은 집계에서 빠진다
def test_tier_3_articles_are_listed_but_excluded_from_every_aggregate(conn):
    arts = [news("일반 언론 CBAM 탄소국경 소식", "연합뉴스", days_ago=0.3)]
    # 같은 단어를 많이 쓰는 단체 보도자료 5건: 집계에 들어가면 급증 키워드를 왜곡한다
    arts += [news(f"플라스틱세 도입 촉구 {i}", "한국경제인협회", days_ago=0.1 * i + 0.1) for i in range(5)]
    load(conn, arts)
    pipeline.assign_tiers(conn, now=NOW)
    d = analysis.build_report_data(conn=conn, now=NOW)
    assert d["excluded_tier3"] == 5
    assert d["total_articles"] == 1
    assert sum(x["count"] for x in d["per_day"]) == 1
    assert {t["term"] for t in d["rising_terms"]} == set()                   # 5번 나온 '플라스틱세' 가 급증 키워드가 되지 않음
    assert [t["name"] for t in d["topics"]] == ["CBAM/탄소국경"]
    shown = [a for a in d["articles"] if a["source_tier"] == 3]
    assert len(shown) == 5                                                   # 목록에는 배지와 함께 남는다
    assert all(a["source_tier_reason"].startswith("name-pattern:") for a in shown)


def test_without_the_tier_3_filter_those_same_articles_would_have_become_rising_terms(conn):
    """위 테스트의 대조군: 일반 언론이 같은 기사를 냈다면 급증 키워드가 된다."""
    load(conn, [news(f"플라스틱세 도입 촉구 {i}", "에너지플랫폼뉴스", days_ago=0.1 * i + 0.1) for i in range(5)])
    pipeline.assign_tiers(conn, now=NOW)
    d = analysis.build_report_data(conn=conn, now=NOW)
    assert "플라스틱세" in {t["term"] for t in d["rising_terms"]}
    assert d["excluded_tier3"] == 0


def test_unassigned_tier_is_treated_as_not_excluded(conn):
    load(conn, [news("탄소세 소식", "아무뉴스")])
    d = analysis.build_report_data(conn=conn, now=NOW)                       # assign_tiers 를 아직 안 돌림 (등급 NULL)
    assert d["total_articles"] == 1 and d["excluded_tier3"] == 0
    assert d["articles"][0]["source_tier"] == 0


# ----------------------------------------------------------------------------- 단일 출처 주장
def test_single_source_claim_flag(conn):
    load(conn, [
        news("업계 요구 배출권 무상할당 전면 확대 촉구", "한국경제인협회", days_ago=0.2),                 # 다른 곳이 안 다룸 → 단일 출처
        news("협회 주장: 탄소국경조정제도 유예 필요", "대한상공회의소", days_ago=0.2),                  # 일반 언론이 같은 내용을 보도 → 단일 아님
        news("탄소국경조정제도 유예 필요 협회 주장", "연합뉴스", days_ago=0.1),
        news("협회가 낸 자료 4기 할당계획 의견", "한국철강협회", days_ago=0.2),                          # 공식 문서와 연결됨 → 단일 아님
    ])
    off = make_article("배출권거래제 4기 할당계획 입법예고", days_ago=0.5, source="기후에너지환경부", url="https://mcee.go.kr/1")
    off.source_type, off.agency = "official", "기후에너지환경부"
    off.id = official_id(off.url)
    load(conn, [off])
    pipeline.assign_tiers(conn, now=NOW)
    conn.execute("UPDATE articles SET official_status='confirmed' WHERE title='협회가 낸 자료 4기 할당계획 의견'")
    conn.commit()
    d = analysis.build_report_data(conn=conn, now=NOW)
    flags = {a["title"]: a["single_source"] for a in d["articles"]}
    assert flags["업계 요구 배출권 무상할당 전면 확대 촉구"] is True
    assert flags["협회 주장: 탄소국경조정제도 유예 필요"] is False
    assert flags["협회가 낸 자료 4기 할당계획 의견"] is False
    assert flags["탄소국경조정제도 유예 필요 협회 주장"] is False          # 3등급이 아니면 항상 False


# ----------------------------------------------------------------------------- 리포트 표시
def article(**kw):
    base = {"title": "t", "url": "https://n.test/a", "source": "s", "published": "2026-11-03T01:00:00+09:00", "lang": "ko",
            "topics": [], "regions": [], "official_status": "unconfirmed", "official_links": [], "source_tier": 0,
            "source_tier_reason": "", "single_source": False, "sensational": []}
    return {**base, **kw}


def render_with(articles, excluded=0):
    from tests.test_render import data_with
    return render.render_report(data_with(articles=articles, total_articles=len(articles), excluded_tier3=excluded))


def test_report_shows_tier_badges_single_source_and_sensational_terms():
    html = render_with([
        article(title="공식", source_tier=1),
        article(title="일반", source_tier=2),
        article(title="단체 단독", source_tier=3, single_source=True, sensational=["충격"]),
        article(title="단체 복수", source_tier=3, single_source=False),
        article(title="미분류", source_tier=0),
    ], excluded=2)
    assert 'b-tier-1" title="출처 신뢰도 등급">공식<' in html and 'b-tier-2" title="출처 신뢰도 등급">일반<' in html
    assert 'b-tier-0" title="출처 신뢰도 등급">미분류<' in html
    assert html.count('b-tier-3" title="출처 신뢰도 등급">단체·업계 주장<') == 2 and html.count('class="item news tier-3"') == 2
    assert html.count("단일 출처 주장") == 1 and html.count("다른 출처도 다룸") == 1
    single = html[html.index('data-title="단체 단독"'):html.index('data-title="단체 복수"')]
    assert "단일 출처 주장" in single and "자극적 표현: 충격" in single
    assert "단체·업계 주장 <strong>2건</strong> (집계 제외, 목록에는 표시)" in html


def test_report_escapes_sensational_terms():
    html = render_with([article(source_tier=3, sensational=["<b>x</b>"])])
    assert "<b>x</b>" not in html


def test_v6_adds_tier_columns(conn):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(articles)")}
    assert {"source_url", "source_tier", "source_tier_reason", "sensational"} <= cols

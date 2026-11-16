import pytest

import config
from carbon import analysis, filters, pipeline, tagging
from carbon.sources.base import official_id
from tests.conftest import NOW, FakeSource, make_article


def judge(title, source="", source_type="news", impact=None):
    return filters.judge_relevance(title, source, source_type, impact)


# ----------------------------------------------------------------------------- 관련 (1)
@pytest.mark.parametrize("title, keyword", [
    ("배출권거래제 4기 할당계획 확정", "배출권"),
    ("EU CBAM 전환기간 보고 의무", "cbam"),
    ("Argentina's Senate Backs Carbon Market Bill In 60-2 Vote", "carbon market"),
    ("Data Integrity Secures Institutional Carbon Markets", "carbon market"),         # 복수형
    ("[환경용어] 저탄소 투자 손실 막는다… '탄소차액계약제도(CCfD)'", "탄소차액계약"),
    ("COP31 앞두고 한국 기후정책 점검", "cop31"),
    ("UK ETS: What ship managers need to know", "ets"),
    ("Taiwan plans to adopt CBAM model to meet net-zero goals", "cbam"),
])
def test_policy_vocabulary_in_title_means_relevant(title, keyword):
    rel, why = judge(title)
    assert rel == 1 and why == f"rule:strong({keyword})"


# ----------------------------------------------------------------------------- 제외 (0)
@pytest.mark.parametrize("title", [
    "Develop Global Board Approves Revised Securities Trading Policy Effective 29 October",
    "Global Masters Fund Limited Adopts Revised Share Trading Policy on 2 November 2026",
    "ISO Container Market to Reach US$ 1,599.3 Billion at 10.2% CAGR",
    "Crypto Token Types | NFTs, Stablecoins, Asset-Backed, & More",
    "Earnings call transcript: POSCO Holdings posts stronger Q3 2026 profit",
    "Medium Carbon Steel Market in Japan: Size, Trends and Forecast to 2035",
])
def test_obviously_unrelated_patterns_are_excluded(title):
    rel, why = judge(title)
    assert rel == 0 and why.startswith("rule:exclude-hard(")


def test_hard_excludes_win_even_over_policy_words():
    """시장조사 스팸은 제목에 'Low Carbon' 같은 단어가 있어도 제외한다."""
    rel, why = judge("Low Carbon Footprint Formulated Crop Protection Market: Size, Trends and Forecast to 2035")
    assert rel == 0 and "exclude-hard" in why
    assert judge("Carbon credit crypto token launches")[0] == 0               # 암호화폐 토큰


def test_soft_excludes_lose_to_policy_vocabulary():
    assert judge("Businesses still grappling with Brexit red tape")[0] == 0
    assert judge("China's shift to new policy rate signals easier funding conditions")[0] == 0
    assert judge("Brexit and the UK ETS: linking talks resume")[0] == 1            # 정책 용어가 있으면 Brexit 기사도 관련


def test_excluded_sources_apply_only_without_policy_vocabulary(monkeypatch):
    rules = {**config.RELEVANCE_RULES, "exclude_sources": ["Simply Wall St"]}
    monkeypatch.setattr(config, "RELEVANCE_RULES", rules)
    assert judge("After a 368% climb, the story has changed", "Simply Wall St")[0] == 0
    assert judge("EU ETS price falls", "Simply Wall St")[0] == 1
    assert judge("After a 368% climb, the story has changed", "다른 매체")[0] is None


# ----------------------------------------------------------------------------- 미판정 (None): 확실하지 않으면 제외하지 않는다
@pytest.mark.parametrize("title", ["Rethinking Linking", "A necessary trade-off", "Actions Speak Louder Than Words - by Mitchell Beer"])
def test_titles_without_any_clue_are_undecided_not_excluded(title):
    """제목에 단서가 없는 기사 중에는 탄소시장 연계 이야기처럼 관련 있는 것도 있다. 제외하면 관련 기사를 잃는다."""
    assert judge(title) == (None, "rule:no-keyword")


def test_weak_vocabulary_is_undecided():
    rel, why = judge("Planetary Power: Geoengineering and the New Geopolitics of Climate Intervention")
    assert rel is None and why == "rule:weak(climate)"


def test_word_boundaries_prevent_false_hits():
    assert judge("Commission approves state aid for assets in rail")[0] is None     # 'assets' 속 'ets'
    assert judge("US markets rally as budgets pass")[0] is None


def test_every_reason_is_marked_as_a_rule_decision():
    for t in ["배출권 가격", "Brexit news", "climate talks", "no clue here", "Market to Reach 5 billion CAGR"]:
        assert judge(t)[1].startswith("rule:")


# ----------------------------------------------------------------------------- 공식 문서
def test_official_documents_follow_domestic_impact():
    assert judge("x", "기후에너지환경부", "official", "direct") == (1, "rule:official-impact(direct)")
    assert judge("x", "외교부", "official", "reference")[0] == 1
    assert judge("제7회 푸른하늘의 날 기념행사", "외교부", "official", "unknown") == (0, "rule:official-no-carbon-keyword")
    assert judge("x", "외교부", "official", None) == (None, "rule:official-pending")


def test_specialized_agency_documents_are_never_excluded_for_missing_keywords():
    assert judge("2025년 환경부 주요정책 추진계획", "온실가스종합정보센터", "official", "unknown") == (None, "rule:official-specialized-agency")


# ----------------------------------------------------------------------------- 태깅 (같은 단계에서 고친 부분)
def test_english_tags_use_word_boundaries_but_allow_plural():
    topics, regions = tagging.tag_text("Markets rally as budgets pass; Sets targets for status review in Indonesian bonus")
    assert topics == [] and regions == []                                          # markets/budgets/Sets/Targets/status/Indonesian 에 걸리지 않음
    assert tagging.tag_text("US markets rally")[1] == ["미국"]                       # 진짜 'US' 는 걸린다
    topics, regions = tagging.tag_text("Carbon Markets Africa Summit; US climate talks")
    assert "자발적 탄소시장/크레딧" in topics and "미국" in regions
    assert "배출권거래제(ETS)" in tagging.tag_text("EU ETS prices")[0]
    assert "배출권거래제(ETS)" in tagging.tag_text("배출권을 둘러싼 논란")[0]                  # 한국어는 조사가 붙어도 걸린다


def test_eu_with_hyphen_and_new_topics():
    assert "EU" in tagging.tag_text("EU-Canada Summit")[1]
    assert "에너지 전환·재생에너지" in tagging.tag_text("RE100 협의체 기후부에 서한")[0]
    assert "탄소가격/탄소세" in tagging.tag_text("저탄소 투자 손실 막는다 탄소차액계약제도(CCfD)")[0]
    assert "감축목표/NDC" in tagging.tag_text("COP31 앞두고 기후정책 점검")[0]


# ----------------------------------------------------------------------------- 파이프라인과 분석
def load(conn, arts):
    pipeline.collect([FakeSource(arts)], conn=conn)


def rel(conn, title):
    r = conn.execute("SELECT relevant, relevance_reason FROM articles WHERE title=?", (title,)).fetchone()
    return r["relevant"], r["relevance_reason"]


def test_relevance_is_judged_at_insert_and_nothing_is_deleted(conn):
    load(conn, [make_article("배출권거래제 4기 확정"), make_article("ISO Container Market to Reach 5 Billion at 9% CAGR"),
                make_article("Rethinking Linking")])
    assert rel(conn, "배출권거래제 4기 확정")[0] == 1
    assert rel(conn, "ISO Container Market to Reach 5 Billion at 9% CAGR")[0] == 0
    assert rel(conn, "Rethinking Linking")[0] is None
    assert conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0] == 3        # 삭제 없음


def test_refilter_applies_new_rules_to_stored_articles_and_retags(conn, monkeypatch):
    load(conn, [make_article("Brexit red tape continues"), make_article("RE100 협의체 서한")])
    assert rel(conn, "Brexit red tape continues")[0] == 0
    monkeypatch.setattr(config, "RELEVANCE_RULES", {**config.RELEVANCE_RULES, "exclude": []})   # 규칙을 고친 상황
    res = pipeline.refilter(conn)
    assert rel(conn, "Brexit red tape continues")[0] is None and res["changed"] >= 1
    assert res["total"] == 2 and res["irrelevant"] == 0
    conn.execute("UPDATE articles SET topics='' WHERE title='RE100 협의체 서한'")      # 예전 태그를 지운 상태
    conn.commit()
    assert pipeline.refilter(conn)["retagged"] == 1
    assert conn.execute("SELECT topics FROM articles WHERE title='RE100 협의체 서한'").fetchone()[0] == "에너지 전환·재생에너지"


def test_refilter_never_overwrites_llm_or_manual_decisions(conn):
    load(conn, [make_article("Crypto Token Types and more")])                      # 규칙은 제외(0)
    conn.execute("UPDATE articles SET relevant=1, relevance_reason='llm: 탄소 크레딧 토큰 설명' WHERE title LIKE 'Crypto%'")
    conn.commit()
    pipeline.refilter(conn)
    assert rel(conn, "Crypto Token Types and more") == (1, "llm: 탄소 크레딧 토큰 설명")


def test_irrelevant_articles_are_removed_from_every_aggregate_and_list_but_counted(conn):
    keep = [make_article(f"플라스틱세 소식 {i}", days_ago=0.1 * i + 0.1) for i in range(5)]
    junk = [make_article(f"ISO Container Market to Reach {i} Billion CAGR 플라스틱세", days_ago=0.1) for i in range(4)]
    undecided = [make_article("Rethinking Linking", days_ago=0.2)]
    load(conn, keep + junk + undecided)
    d = analysis.build_report_data(conn=conn, now=NOW)
    assert d["excluded_count"] == 4
    assert d["total_articles"] == 6                                                  # 관련 5 + 미판정 1
    assert sum(x["count"] for x in d["per_day"]) == 6
    titles = [a["title"] for a in d["articles"]]
    assert "Rethinking Linking" in titles and not any("CAGR" in t for t in titles)   # 미판정은 남고 무관은 빠진다
    assert d["rising_terms"] and d["rising_terms"][0]["recent"] == 5                 # 무관 기사 4건이 급증 키워드에 영향을 주지 않는다
    assert conn.execute("SELECT COUNT(*) FROM articles WHERE relevant=0").fetchone()[0] == 4


def test_irrelevant_official_documents_are_removed_from_the_official_list(conn):
    def off(title, url, agency):
        a = make_article(title, days_ago=0.5, url=url, source=agency)
        a.source_type, a.agency = "official", agency
        a.id = official_id(url)
        return a
    load(conn, [off("배출권거래제 4기 할당계획 입법예고", "https://x/1", "기후에너지환경부"),
                off("제7회 푸른하늘의 날 기념행사", "https://x/2", "외교부")])
    d = analysis.build_report_data(conn=conn, now=NOW)
    assert [o["title"] for o in d["official"]] == ["배출권거래제 4기 할당계획 입법예고"]
    assert d["excluded_count"] == 1


def test_irrelevant_news_is_not_sent_to_official_linking(conn):
    load(conn, [make_article("Crypto Token Types 4기 배출권", days_ago=0.3)])
    assert rel(conn, "Crypto Token Types 4기 배출권")[0] == 0
    assert pipeline.link_news(conn, now=NOW)["tried"] == 0


def test_v8_adds_relevance_columns(conn):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(articles)")}
    assert {"relevant", "relevance_reason"} <= cols

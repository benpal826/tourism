from datetime import timedelta

import pytest

import config
from carbon import analysis, keywords, pipeline
from tests.conftest import NOW, FakeSource, make_article


# ----------------------------------------------------------------------------- 단어 추출
def test_josa_is_stripped_so_word_forms_count_as_one_term():
    assert "배출권" in keywords.candidate_terms("배출권을 놓고 논란")
    assert keywords.candidate_terms("플라스틱세를 도입") & keywords.candidate_terms("플라스틱세가 논란") == {"플라스틱세"}
    assert "기후변화" not in keywords.candidate_terms("기후변화와 대응")          # 일반어 + 조사 제거


def test_outlet_suffix_and_stopwords_are_ignored():
    terms = keywords.candidate_terms("EU ETS price falls - Reuters")
    assert "reuters" not in " ".join(terms)
    assert "ets" in terms and "eu" in terms and "price" in terms
    assert all("the" not in t.split() for t in keywords.candidate_terms("the carbon tax is back"))


# ----------------------------------------------------------------------------- 일반어 제외
@pytest.mark.parametrize("word", ["carbon", "energy", "climate", "policy", "탄소", "에너지", "정책", "확대", "대응",
                                  "온실가스", "탄소중립", "기후위기", "개최", "보도자료"])
def test_generic_and_boilerplate_words_are_never_candidates_alone(word):
    assert word not in keywords.candidate_terms(f"{word} 소식")
    assert word not in keywords.candidate_terms(f"새로운 {word}")


def test_junk_fragments_found_in_real_titles_are_not_candidates():
    terms = keywords.candidate_terms("Re: Global markets and 2026년도 사업")
    assert not terms & {"re", "markets", "년도", "2026년도"}                 # 두 글자 조각, 복수형, 연도 꼬리
    assert "made" not in keywords.candidate_terms("Deal made after talks")   # 흔한 영어 군더더기


def test_specific_policy_words_stay_even_though_frequent_in_this_field():
    terms = keywords.candidate_terms("CBAM 배출권거래제 NDC 소식")
    assert {"cbam", "배출권거래제", "ndc"} <= terms


def test_bigrams_keep_specific_pairs_and_drop_generic_or_boilerplate_pairs():
    t = keywords.candidate_terms("탄소국경조정제도 유예 논의")
    assert "탄소국경조정제도 유예" in t                      # 구체적인 말 + 구체적인 말
    assert "유예 논의" not in t                              # 상투어(논의) 가 낀 묶음은 제외
    assert "탄소중립 기본법" in keywords.candidate_terms("탄소중립 기본법 개정")   # 기본 어휘 + 구체적인 말은 남는다
    assert "기후 변화" not in keywords.candidate_terms("기후 변화 대응")           # 둘 다 기본 어휘
    assert "도입 촉구" not in keywords.candidate_terms("탄소세 도입 촉구")
    assert "탄소세 도입" not in keywords.candidate_terms("탄소세 도입 촉구")       # 상투어(도입) 가 낀 묶음도 제외


def test_stopword_between_words_breaks_the_bigram():
    assert "배출권 가격" not in keywords.candidate_terms("배출권 및 가격")           # '및' 이 끼어 이웃이 아니다
    assert "배출권 가격" in keywords.candidate_terms("배출권 가격 하락")


def test_punctuation_breaks_the_bigram_so_lists_are_not_phrases():
    t = keywords.candidate_terms("수원·안산·시흥·광명 환경교육도시 재지정")
    assert "수원 안산" not in t and "안산 시흥" not in t                        # 지역 나열은 한 구(句)가 아니다
    assert "환경교육도시 재지정" in t
    assert "배출권 가격" not in keywords.candidate_terms("배출권, 가격")
    assert "탄소국경조정제도 유예" in keywords.candidate_terms("탄소국경조정제도 유예")


def test_word_ending_in_do_is_not_cut_like_a_particle():
    assert "탄소국경조정제도" in keywords.candidate_terms("탄소국경조정제도 시행")
    assert "전문가" in keywords.candidate_terms("전문가 인터뷰")                 # 짧은 단어는 확실할 때만 조사를 뗀다


# ----------------------------------------------------------------------------- 급증 계산
def titles(prefix, n):
    return [f"{prefix} {i}" for i in range(n)]


def test_injected_spike_ranks_first_and_generic_words_do_not_appear():
    recent = titles("플라스틱세 소식", 6) + titles("탄소 에너지 정책 확대 대응", 12)         # 일반어는 아주 많이 나와도 후보가 아니다
    base = titles("배출권 가격 동향", 20)
    out = keywords.rising_terms(recent, base)
    assert out[0]["term"] == "플라스틱세" and out[0]["recent"] == 6
    terms = {t["term"] for t in out}
    assert not terms & {"탄소", "에너지", "정책", "확대", "대응"}


def test_usual_words_are_not_rising_even_if_common_now():
    """평소에도 같은 비율로 나오는 말은 급증이 아니다 (수학 과목 기사에 숫자가 많이 나오는 것은 특이한 일이 아니다)."""
    recent = titles("배출권 가격 동향", 10) + titles("플라스틱세 소식", 5)
    base = titles("배출권 가격 동향", 20) + titles("기타 잡다한 소식", 20)
    terms = {t["term"]: t for t in keywords.rising_terms(recent, base)}
    assert "플라스틱세" in terms
    assert "배출권" not in terms                              # 평소에도 절반 가까이 나옴 → 배율 1.x


def test_ratio_formula_and_baseline_expected_count():
    recent = titles("플라스틱세 소식", 4) + titles("그밖의 일", 6)          # 최근 10건
    base = titles("플라스틱세 소식", 2) + titles("그밖의 일", 18)           # 평소 20건 중 2건 = 10%
    t = {x["term"]: x for x in keywords.rising_terms(recent, base)}["플라스틱세"]
    assert t["baseline"] == 1.0 and t["usual_pct"] == 10.0              # 기대 건수 = 0.10 × 10건
    assert t["ratio"] == round((4 + 0.5) / (1.0 + 0.5), 1) == 3.0


def test_usual_df_limit_removes_words_that_are_common_in_the_baseline():
    recent = titles("플라스틱세 소식", 8) + titles("그밖의 일", 2)
    base = titles("플라스틱세 소식", 7) + titles("그밖의 일", 13)           # 평소 35%
    assert "플라스틱세" in {t["term"] for t in keywords.rising_terms(recent, base, usual_df_limit=None)}   # 배율 2.1 이라 한계가 없으면 남는다
    assert "플라스틱세" not in {t["term"] for t in keywords.rising_terms(recent, base, usual_df_limit=0.30)}


def test_minimum_recent_count_and_minimum_ratio():
    base = titles("그밖의 일", 30)
    assert keywords.rising_terms(titles("희귀단어 소식", config.RISING_MIN_RECENT - 1), base) == []   # 너무 적게 나옴
    # 평소와 비슷하게 나오는 말은 배율 2 미만이라 급증이 아니다
    recent = titles("플라스틱세 소식", 3) + titles("그밖의 일", 7)
    base2 = titles("플라스틱세 소식", 12) + titles("그밖의 일", 28)             # 평소 30% → 기대 3건, 실제 3건
    assert "플라스틱세" not in {t["term"] for t in keywords.rising_terms(recent, base2)}


def test_no_recent_titles_returns_empty_and_no_baseline_still_works():
    assert keywords.rising_terms([], titles("a b", 3)) == []
    out = keywords.rising_terms(titles("플라스틱세 소식", 4), [])
    assert out and out[0]["term"] == "플라스틱세" and out[0]["usual_pct"] == 0.0


def test_unigram_is_dropped_when_a_bigram_covers_it():
    recent = titles("탄소국경조정제도 유예 소식", 5)
    terms = [t["term"] for t in keywords.rising_terms(recent, titles("그밖의 일", 20))]
    assert "탄소국경조정제도 유예" in terms and "탄소국경조정제도" not in terms and "유예" not in terms


# ----------------------------------------------------------------------------- 분석 연결
def load(conn, arts):
    pipeline.collect([FakeSource(arts)], conn=conn)


def set_history(conn, days):
    """DB 에 쌓인 기간이 days 일인 것처럼 수집 시각을 벌려 놓는다."""
    rows = conn.execute("SELECT id FROM articles ORDER BY id").fetchall()
    for i, r in enumerate(rows):
        t = NOW - timedelta(days=days * i / max(len(rows) - 1, 1))
        conn.execute("UPDATE articles SET collected=? WHERE id=?", (t.isoformat(), r["id"]))
    conn.commit()


def corpus():
    spike = [make_article(f"플라스틱세 소식 {i} 탄소 에너지 정책", days_ago=0.1 * i + 0.1) for i in range(5)]
    usual = [make_article(f"배출권 가격 동향 {i}", days_ago=0.1 * i + 0.1) for i in range(6)]
    earlier = [make_article(f"배출권 가격 동향 이전 {i}", days_ago=3 + i * 0.4) for i in range(8)]
    return spike + usual + earlier


def test_short_history_uses_window_mode_and_says_so(conn):
    load(conn, corpus())
    set_history(conn, 3)
    d = analysis.build_report_data(conn=conn, now=NOW)
    basis = d["rising_basis"]
    assert basis["mode"] == "window" and basis["history_days"] == 3 and "일반어만 제외" in basis["note"]
    terms = [t["term"] for t in d["rising_terms"]]
    assert terms[0] == "플라스틱세"
    assert not {"탄소", "에너지", "정책"} & set(terms)


def test_long_history_uses_30_day_baseline_and_drops_usual_words(conn):
    old = [make_article(f"배출권 가격 동향 옛날 {i}", days_ago=10 + i * 0.5) for i in range(20)]       # 평소(10~20일 전)에도 흔한 말
    load(conn, corpus() + old)
    set_history(conn, 25)
    d = analysis.build_report_data(conn=conn, now=NOW, days=7)
    basis = d["rising_basis"]
    assert basis["mode"] == "usual" and basis["baseline_days"] == config.KEYWORD_BASELINE_DAYS
    assert "평소 빈도" in basis["note"] and f"{config.KEYWORD_USUAL_DF:.0%}" in basis["note"]
    terms = [t["term"] for t in d["rising_terms"]]
    assert terms[0] == "플라스틱세" and "배출권" not in terms


def test_tier_3_articles_still_do_not_feed_rising_terms(conn):
    load(conn, [make_article(f"플라스틱세 소식 {i}", days_ago=0.1 * i + 0.1, source="한국경제인협회") for i in range(5)])
    pipeline.assign_tiers(conn, now=NOW)
    assert analysis.build_report_data(conn=conn, now=NOW)["rising_terms"] == []

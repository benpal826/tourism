import pytest

from carbon import policy


# ---------------------------------------------------------------- 정책 단계 (F11)
@pytest.mark.parametrize("title, expected", [
    # 추진: 입법예고, 의견수렴, 예정, 검토, (안)
    ("배출권거래제 4기 할당계획 입법예고", "proposed"),
    ("「소득세법 시행령」 일부개정령(안) 입법예고", "proposed"),
    ("제3차 고준위 방사성폐기물 관리 기본계획 수립을 위한 국민 의견수렴 추진", "proposed"),
    ("탄소국경조정제도 대응 방안 검토", "proposed"),
    ("2027년 탄소세 도입 시행 예정", "proposed"),            # '시행' 이 있어도 '예정' 이 뒤에 있으면 추진
    ("온실가스 배출량 산정 고시(안) 행정예고", "proposed"),   # '고시' 가 있어도 '행정예고' 가 뒤에 있으면 추진
    ("미확정 사항 추가 검토", "proposed"),                    # '미확정' 은 확정이 아니다
    # 확정: 공포, 고시, 의결, 확정, 시행
    ("탄소중립기본법 시행령 일부개정령 공포", "decided"),
    ("2035 국가 온실가스 감축목표(NDC) 확정", "decided"),
    ("탄소국경조정제도 본격 시행", "decided"),
    ("온실가스 감축 시행규칙 개정안 국무회의 의결", "decided"),  # '개정안' 이 있어도 '의결' 이 뒤에 있으면 확정
    ("배출권거래제 할당 기준 고시", "decided"),
    # 판단 불가
    ("전기차 전환 서명에 동참해 주세요", "unknown"),
    ("배출권거래제 시행령 일부개정", "unknown"),              # '시행령' 은 '시행' 이 아니다
    ("2026년도 분산에너지 분야 유공 장관표창 후보자 공모", "unknown"),
    ("재생에너지자립도시 조성 및 지원에 관한 특별법안", "proposed"),       # '법률안' 이 아닌 '특별법안'
    ("", "unknown"),
])
def test_stage_from_title(title, expected):
    assert policy.classify_stage(title) == expected


def test_assembly_bill_stage_uses_processing_status():
    title = "기후위기 대응을 위한 탄소중립ㆍ녹색성장 기본법 일부개정법률안"
    assert policy.classify_stage(title, "박지혜의원 등 10인 · 환경노동위원회 · 계류") == "proposed"
    assert policy.classify_stage("재생에너지 지원 특별법", "계류") == "proposed"     # 제목에 표지가 없어도 '계류' 로 추진
    assert policy.classify_stage(title, "박지혜의원 등 10인 · 환경노동위원회 · 원안가결") == "decided"


def test_department_name_in_summary_does_not_decide_stage():
    """summary 는 보통 담당 부서명이다. '태양광보급추진단' 의 '추진' 으로 추진 판정이 되면 안 된다."""
    j = policy.classify_official("2026년 가정형 태양광 보급사업 변경 공고", "태양광보급추진단", "기후에너지환경부")
    assert j.stage == "unknown"


def test_summary_is_used_only_for_assembly():
    title = "철강산업 경쟁력 강화 및 탄소중립 전환을 위한 특별법 일부개정법률안"
    assert policy.classify_official(title, "이상휘의원 등 17인 · 산업통상부 · 원안가결", "국회(의원발의 법률안)").stage == "decided"
    assert policy.classify_official(title, "원안가결", "기후에너지환경부").stage == "proposed"   # 국회가 아니면 summary 무시


# ---------------------------------------------------------------- 국내 영향도 (F12)
@pytest.mark.parametrize("title, label, keyword", [
    ("배출권거래제 4기 할당계획 확정", "direct", "배출권거래제"),
    ("2035 국가 온실가스 감축목표 확정", "direct", "국가 온실가스 감축목표"),
    ("EU 탄소국경조정제도(CBAM) 이행 안내", "direct", "탄소국경조정"),
    ("EU CBAM 전환기간 보고 의무", "direct", "cbam"),
    ("영국 CBAM 도입 계획 발표", "reference", "영국 cbam"),            # 더 구체적인 키워드가 있으면 'cbam' 은 무시된다
    ("온실가스 배출권의 할당 및 거래에 관한 법률 일부개정법률안", "direct", "배출권"),   # 무관한 키워드끼리는 점수가 높은 쪽
    ("탄소중립ㆍ녹색성장 기본법 시행령 개정", "direct", "탄소중립·녹색성장 기본법"),     # '탄소중립' 은 더 구체적인 법 이름에 가려진다
    ("한-말레이시아 기후변화 대화 개최", "reference", "기후변화"),
    ("자원안보위기 경보에 따른 에너지절약 국민행동", "reference", "에너지"),
    ("기후변화영향평가서 초안 공고", "indirect", "기후변화영향평가"),             # 일반어 '기후변화' 보다 구체적인 이름이 이긴다
    ("제31차 COP31 합의문 채택", "reference", "cop"),                 # 숫자가 붙어도 인식
    ("자발적 탄소시장 활성화 방안", "reference", "자발적 탄소시장"),
    ("탄소차액계약(CCfD) 시범사업 추진", "reference", "탄소차액계약"),
    ("Carbon Contracts for Difference pilot", "reference", "carbon contracts for difference"),
    ("청정수소 발전 입찰시장 개편", "indirect", "청정수소"),
    ("「교통ㆍ에너지ㆍ환경세법 시행령」 일부개정령(안) 입법예고", "indirect", "교통·에너지·환경세"),   # ㆍ 표기 차이 흡수
    ("전기차 전환 서명에 동참해 주세요", "unknown", ""),
])
def test_impact_label_and_matched_keyword(title, label, keyword):
    score, kw = policy.score_impact(title)
    assert policy.impact_label(score) == label
    assert kw == keyword


def test_english_keywords_respect_word_boundaries():
    assert policy.score_impact("Commission approves state aid for assets in rail")[0] is None   # 'assets' 속 'ets'
    assert policy.score_impact("ETS2 start delayed")[0] is None          # 'ets' 단독은 seed 가 아니다 ('eu ets' 만)
    assert policy.score_impact("EU ETS2 start delayed")[1] == "eu ets"   # ets2 처럼 숫자가 붙어도 인식


def test_custom_weights_override_seeds():
    w = {"배출권거래제": 10.0}
    assert policy.score_impact("배출권거래제 할당", w) == (10.0, "배출권거래제")
    assert policy.impact_label(10.0) == "reference"


def test_classify_official_bundle():
    j = policy.classify_official("배출권거래제 4기 할당계획 입법예고", "기후전략과", "기후에너지환경부")
    assert (j.stage, j.impact, j.impact_keyword) == ("proposed", "direct", "배출권거래제")
    assert j.impact_score == 95


def test_band_edges():
    assert policy.impact_label(70) == "direct" and policy.impact_label(69.9) == "indirect"
    assert policy.impact_label(40) == "indirect" and policy.impact_label(39.9) == "reference"
    assert policy.impact_label(None) == "unknown"

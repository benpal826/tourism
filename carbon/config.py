"""모니터링 설정: 검색어, 주제 분류, 지역 분류를 여기서 수정하세요."""
from datetime import timedelta, timezone
from pathlib import Path

# 저장은 UTC, 날짜 집계·화면 표시는 KST. 한국은 서머타임이 없어 고정 +9시간이면 정확하다.
KST = timezone(timedelta(hours=9), "KST")

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "articles.db"
REPORT_DIR = BASE_DIR / "reports"
LOG_DIR = BASE_DIR / "logs"

# Google News RSS 검색어 (lang, query)
QUERIES = [
    ("ko", "배출권거래제"),
    ("ko", "탄소국경조정제도"),
    ("ko", "CBAM 탄소국경"),
    ("ko", "탄소중립 정책"),
    ("ko", "온실가스 감축목표 NDC"),
    ("ko", "탄소세 OR 탄소가격"),
    ("en", "EU ETS carbon price"),
    ("en", "CBAM carbon border adjustment"),
    ("en", "emissions trading system"),
    ("en", "carbon market policy"),
    ("en", "Article 6 carbon credits"),
    ("en", "K-ETS Korea emissions trading"),
]

# 주제 분류: 제목+요약에 키워드가 하나라도 포함되면 해당 주제로 태깅
TOPICS = {
    "배출권거래제(ETS)": ["배출권", "ets", "emissions trading", "emission trading", "k-ets", "allowance", "eua"],
    "CBAM/탄소국경": ["cbam", "탄소국경", "border adjustment", "carbon border"],
    "탄소가격/탄소세": ["탄소세", "탄소가격", "탄소 가격", "carbon tax", "carbon price", "carbon pricing",
                  "탄소차액계약", "ccfd", "carbon contracts for difference"],
    "감축목표/NDC": ["ndc", "감축목표", "온실가스 감축", "net zero", "net-zero", "넷제로", "탄소중립", "탈탄소",
                  "cop31", "cop 31", "당사국총회", "unfccc", "파리협정", "paris agreement", "기후협상", "decarbonis", "decarboniz"],
    "자발적 탄소시장/크레딧": ["article 6", "6조", "carbon credit", "carbon market", "carbon removal", "offset",
                     "탄소시장", "탄소 제거", "상쇄", "크레딧", "voluntary carbon"],
    "에너지 전환·재생에너지": ["재생에너지", "re100", "전기본", "수소", "태양광", "풍력", "renewable", "solar", "hydrogen", "clean energy"],
    "산업·기업 영향": ["철강", "시멘트", "알루미늄", "수출", "steel", "cement", "aluminium", "aluminum", "fertilizer", "fertiliser"],
}

# ---------------------------------------------------------------- 무관 기사 필터링 (F6)
# 제목만으로 판정한다. 관련 기사를 잘못 숨기는 것이 무관 기사가 남는 것보다 나쁘므로 '확실한 것만' 제외한다.
#   관련(1)   : strong 단어가 제목에 있음
#   제외(0)   : exclude_hard 가 있음(strong 이 있어도 제외), 또는 strong 이 없고 exclude/제외 언론사에 해당
#   미판정(NULL): 위에 해당하지 않음 (약한 단어만 있거나 단서가 없음). 집계에 남기고 이후 LLM 단계(F5)가 판정한다.
# 공식 문서는 국내 영향도가 판정됐으면 관련, 키워드가 하나도 없으면 무관으로 본다.
RELEVANCE_RULES = {
    "strong": [
        "배출권", "k-ets", "ets", "emissions trading", "emission trading", "cbam", "탄소국경", "carbon border", "border adjustment",
        "ndc", "국가결정기여", "감축목표", "탄소세", "탄소가격", "탄소 가격", "carbon tax", "carbon price", "carbon pricing",
        "carbon market", "탄소시장", "carbon credit", "탄소크레딧", "탄소상쇄", "carbon offset", "article 6",
        "탄소차액계약", "ccfd", "carbon contracts for difference", "탄소중립", "녹색분류체계", "net zero", "net-zero", "넷제로",
        "unfccc", "당사국총회", "cop31", "paris agreement", "파리협정", "온실가스", "greenhouse gas", "decarbonis", "decarboniz", "탈탄소",
    ],
    "weak": [
        "탄소", "기후", "에너지", "carbon", "climate", "energy", "emission", "emissions", "renewable", "solar", "재생에너지",
        "수소", "hydrogen", "re100", "전기본", "esg", "low-carbon", "low carbon", "sustainability",
    ],
    # strong 단어가 있어도 제외: 탄소와 무관한 시장조사 스팸·증권 공시·암호화폐
    "exclude_hard": [
        "cagr", "market to reach", "market size", "market report", "forecast to 20", "size, trends",
        "securities trading policy", "share trading policy", "earnings call", "crypto", "stablecoin", "nft",
    ],
    # strong 단어가 없을 때만 제외. '[공시]' 는 괄호까지 맞춰 '공시지가' 같은 말에 걸리지 않게 한다.
    # 비트코인은 채굴 탄소 문제처럼 정책 기사가 될 수 있어 exclude_hard 가 아니라 여기에 둔다 (정책 용어가 있으면 관련)
    "exclude": ["brexit", "policy rate", "bond market", "stock market", "기준금리", "[공시]", "bitcoin", "비트코인"],
    "exclude_sources": [],
}
# 모든 발표가 기후·배출권 업무인 전문 기관: 공식 문서 제목에 키워드가 없어도 무관으로 제외하지 않는다
SPECIALIZED_AGENCIES = ["온실가스종합정보센터"]

# 지역/국가 태깅
REGIONS = {
    "한국": ["한국", "korea", "k-ets", "환경부", "기후부", "산업부"],
    "EU": ["eu ", "유럽", "european", "brussels", "eu-", "eua"],
    "중국": ["중국", "china", "chinese"],
    "미국": ["미국", "u.s.", "us ", "united states", "washington"],
    "일본": ["일본", "japan"],
    "인도": ["인도 ", "india"],
    "영국": ["영국", "uk ", "britain"],
}

# 트렌드용 불용어 (제목 단어 빈도 계산 시 제외)
STOPWORDS = set("""
the a an of to in for and on with by at from is are as be its it this that new
about after over into more will says say amid vs
or if we he me my no so up do how what why can may has have was were than their per via not all out get set one two re
made make makes could would should year years now today here there when which who also just only very most such other
first last next back off down then them they you your our onto upon across against between during could
및 의 에 를 을 이 가 은 는 로 으로 에서 와 과 도 등 위한 대한 관련 통해 올해 내년 오늘
""".split())

# ---------------------------------------------------------------- 급증 키워드 특이도 (F14)
# 급증 키워드는 "평소 많이 나오는 단어"가 아니라 "평소보다 특이하게 늘어난 단어"여야 한다.
# 이 분야 제목에는 늘 나오는 원론적인 단어와 상투어가 많아서(수학 과목 기사에 숫자가 많이 나오는 것이 특이한 일이 아닌 것과 같다)
# 1) 일반어 목록으로 제외하고, 2) 평소 빈도와 비교해 늘어난 정도(배율)가 큰 단어만 보여준다. 3) 두 단어 묶음('탄소국경조정제도 유예')도 후보로 쓴다.
#
# 일반어는 두 종류다.
#  GENERIC_TERMS     : 분야의 기본 어휘. 단어 하나로는 제외하지만, 구체적인 말과 묶이면('탄소중립 기본법', '배출권 가격') 후보로 남는다.
#                      두 단어가 모두 기본 어휘인 묶음('기후 변화')은 제외한다.
#  BOILERPLATE_TERMS : 과정·상투어. 단어 하나로도, 두 단어 묶음에서도 제외한다. ('도입 촉구', '개최 안내' 같은 뜻 없는 묶음 방지)
# 판단이 갈리는 단어(재생에너지, 수소, cop, ets, cbam, esg 등 분야 용어와 지역명)는 일부러 넣지 않았다. 평소 빈도 비교가 가려낸다.
GENERIC_TERMS = set("""
carbon energy climate policy global market markets investment
탄소 에너지 기후 정책 기후변화 기후위기 온실가스 탄소중립 변화
""".split())
BOILERPLATE_TERMS = set("""
확대 대응 전환 강화 협력 육성 지원 추진 사업 방안 계획 제도 기업 정부 발표 국제 환경 교육
개최 관한 보도자료 일부개정법률안 법률 발행 이벤트
도입 촉구 논의 검토 마련 시행 개정 선정 모집 공모 안내 공고 신청 참여 운영 활성화 구축 확보 개선 필요 발의 제정
의견 수렴 입법예고 행정예고 설명회 공청회 간담회
소식 뉴스 현황 동향 전망 분석 이슈 결과 성과 사례 년도
""".split())
RISING_RECENT_DAYS = 2       # '최근' 으로 보는 기간
RISING_MIN_RECENT = 3        # 최근 기간에 이 건수 미만으로 나온 단어는 제외
RISING_MIN_RATIO = 2.0       # 평소 예상의 2배 미만이면 급증이 아니다
RISING_LIMIT = 15
KEYWORD_BASELINE_DAYS = 30   # '평소' 를 재는 기간
KEYWORD_USUAL_DF = 0.30      # 평소에도 기사 제목의 30% 이상에 나오는 단어는 후보에서 제외
KEYWORD_MIN_HISTORY_DAYS = 14   # DB 에 쌓인 기간이 이보다 짧으면 30일 평소 빈도 비교를 하지 않고, 조회 기간 안의 이전 날들과 비교한다

REQUEST_TIMEOUT = 20
REQUEST_DELAY = 2.0   # 같은 호스트 요청 사이 최소 간격(초). 공식 사이트에 부담을 주지 않기 위함
USER_AGENT = "carbon-policy-monitor/0.2 (personal research; contact: see repository)"

# ---------------------------------------------------------------- 공식 출처 (F7)
# 수집할 출처. 이름은 carbon/sources/registry.py 에 등록된 것만 가능
SOURCES = ["google_news", "official_boards", "eu_presscorner", "assembly_bills"]

# 게시판 목록 페이지 수집 대상. parser 는 carbon/sources/boards.py 의 파서 이름.
# filter=True 이면 제목에 OFFICIAL_KEYWORDS 가 있는 글만 저장한다 (부처 전체 보도자료 중 탄소·에너지 관련만).
# 부처 개편으로 기관명과 주소가 바뀔 수 있다: 환경부 → 기후에너지환경부(mcee.go.kr), 산업통상자원부 → 산업통상부(motir.go.kr)
BOARDS = [
    {"agency": "기후에너지환경부", "name": "보도자료", "parser": "mcee", "filter": True,
     "url": "https://mcee.go.kr/home/web/board/list.do?menuId=10598&boardMasterId=939"},
    {"agency": "기후에너지환경부", "name": "공지·공고", "parser": "mcee", "filter": True,
     "url": "https://mcee.go.kr/home/web/board/list.do?menuId=10524&boardMasterId=39"},
    {"agency": "한국환경공단", "name": "보도자료", "parser": "keco", "filter": True,
     "url": "https://www.keco.or.kr/web/lay1/bbs/S1T109C111/A/20/list.do"},
    {"agency": "한국환경공단", "name": "공지사항", "parser": "keco", "filter": True,
     "url": "https://www.keco.or.kr/web/lay1/bbs/S1T10C108/A/18/list.do"},
    {"agency": "산업통상부", "name": "보도자료", "parser": "motir", "filter": True,
     "url": "https://www.motir.go.kr/kor/article/ATCL3f49a5a8c"},
    {"agency": "산업통상부", "name": "입법·행정예고", "parser": "motir", "filter": True,
     "url": "https://www.motir.go.kr/kor/article/ATCLa1cb24c71"},
    {"agency": "국민참여입법센터", "name": "부처 입법예고", "parser": "opinion", "filter": True,
     "url": "https://opinion.lawmaking.go.kr/gcom/ogLmPp"},
    # 온실가스종합정보센터: 배출권거래제 운영 기관. 보도자료는 거의 전부 관련 글이라 필터를 쓰지 않는다
    {"agency": "온실가스종합정보센터", "name": "보도자료", "parser": "gir", "filter": False,
     "url": "https://www.gir.go.kr/home/index.do?menuId=11"},
    {"agency": "온실가스종합정보센터", "name": "공지사항", "parser": "gir", "filter": True,
     "url": "https://www.gir.go.kr/home/index.do?menuId=10"},
    {"agency": "재정경제부", "name": "보도·참고자료", "parser": "mofe", "filter": True,
     "url": "https://mofe.go.kr/nw/nes/nesdta.do?bbsId=MOSFBBS_000000000028&menuNo=4010100"},
    {"agency": "재정경제부", "name": "입법·행정예고", "parser": "mofe", "filter": True,
     "url": "https://mofe.go.kr/lw/lap/TbPrvntcList.do?bbsId=MOSFBBS_000000000055&menuNo=7050300"},
    {"agency": "외교부", "name": "보도자료", "parser": "mofa", "filter": True,
     "url": "https://www.mofa.go.kr/www/brd/m_4080/list.do"},
    # 외교부 기후변화·환경 외교 게시판(기후변화외교과): 전부 관련 글
    {"agency": "외교부", "name": "기후변화·환경 외교", "parser": "mofa", "filter": False,
     "url": "https://www.mofa.go.kr/www/brd/m_20152/list.do"},
]

# 공식 출처 제목 1차 필터 (소문자 비교, 영문은 단어 경계). 정교한 관련성 판정은 F6/F5 에서 한다.
OFFICIAL_KEYWORDS = [
    "탄소", "온실가스", "배출권", "기후", "에너지", "감축", "녹색", "넷제로", "저탄소", "탈탄소",
    "국가결정기여", "재생에너지", "수소", "태양광", "풍력", "친환경", "순환경제",
    "cbam", "ndc", "ets", "net-zero", "net zero", "decarbon", "climate", "emission", "carbon",
]

# ---------------------------------------------------------------- 정책 단계·국내 영향도 (F11, F12)
# 정책 진행 단계: 공식 문서 제목에서 찾은 표지 중 "문장 끝에 가장 가까운 것"이 이긴다 (동사가 뒤에 오는 한국어 특성).
#   '고시(안) 행정예고' → 행정예고가 뒤 → 추진 / '개정안 국무회의 의결' → 의결이 뒤 → 확정 / '시행 예정' → 예정이 뒤 → 추진
# 시행령·시행규칙·시행계획은 '시행' 으로 보지 않는다. '미확정' 도 확정이 아니다.
POLICY_STAGE_RULES = {
    "proposed": [  # 추진: 검토, 계획, 입법예고, 논의 등 아직 확정되지 않은 것
        r"입법\s*예고", r"행정\s*예고", r"의견\s*수렴", r"공청회", r"초안", r"\(안\)", r"\[안\]",
        r"개정안", r"제정안", r"법률안", r"법안", r"령안", r"발의", r"계류", r"예정", r"추진", r"검토", r"논의", r"협의", r"\bTF\b",
    ],
    "decided": [   # 확정: 공포, 고시, 시행, 의결 등 법적·행정적으로 확정된 것
        r"공포", r"고시", r"의결", r"(?<![미불])확정", r"시행(?!령|규칙|계획|세칙)", r"가결", r"통과",
    ],
}

# 국내 영향도 키워드 초기값(seed, 0~100). 제목에 여러 키워드가 있으면:
#   1) 더 구체적인 키워드에 포함된 키워드는 버린다. 예: '영국 cbam' 이 있으면 'cbam' 은 무시 → 영국 CBAM 은 낮게 판정
#   2) 서로 무관한 키워드가 남으면 가중치가 가장 높은 것을 쓴다. 예: '온실가스 배출권' → '배출권' 90 (온실가스 55 가 아님)
# 가중치는 `python main.py reweight` 로 누적 데이터에 맞춰 조금씩 갱신된다. 최상위(85 이상)는 IMPACT_FLOOR 아래로 내려가지 않는다.
IMPACT_SEEDS = {
    # 최상위: 시행 중인 직접 규제이고 한국 산업계에 가장 영향이 큼
    "배출권거래제": 95, "배출권": 90, "k-ets": 95, "할당계획": 90,
    "ndc": 90, "국가결정기여": 90, "온실가스 감축목표": 90, "국가 온실가스 감축목표": 90,
    "cbam": 90, "탄소국경조정": 90, "탄소국경": 85, "carbon border": 90,
    "탄소중립기본법": 85, "탄소중립·녹색성장 기본법": 85, "탄소중립 녹색성장 기본법": 85, "목표관리제": 85,
    # 중간: 국내 의무가 있거나 산업·에너지 정책에 영향
    "교통·에너지·환경세": 60, "녹색분류체계": 55, "k-택소노미": 55, "기후변화영향평가": 55,
    "emissions trading": 60, "eu ets": 60, "온실가스": 55, "탄소중립": 50, "탄소가격": 50,
    "청정수소": 45, "탄소세": 45, "2040 target": 45, "기후공시": 40, "재생에너지": 40, "태양광": 40, "수소": 40,
    # 낮음: 계획 단계이거나 국내 영향이 당장 작음
    "국제감축": 35, "원전": 35,
    # 기후·에너지 일반어: 키워드가 이것뿐이면 '참고'. 더 구체적인 키워드가 있으면 자동으로 무시된다
    "기후변화": 30, "기후위기": 30, "녹색성장": 30, "탄소": 25, "기후": 20, "에너지": 20,
    "emissions": 25, "greenhouse": 25, "net-zero": 25, "decarbonisation": 25, "decarbonization": 25, "climate": 20,
    "2040 climate target": 45,
    "자발적 탄소시장": 30, "voluntary carbon": 30, "탄소크레딧": 30, "carbon credit": 30, "article 6": 30,
    "탄소차액계약": 30, "carbon contracts for difference": 30, "ccfd": 30,
    "영국 cbam": 25, "uk cbam": 25, "영국 탄소국경": 25, "cop": 25, "당사국총회": 25,
}
IMPACT_BANDS = {"direct": 70, "indirect": 40}   # 점수 70 이상 직접 규제, 40 이상 간접, 그 미만 참고. 키워드가 없으면 '미분류'
IMPACT_BORDER = 5                               # 경계 ±5 이내는 "애매한 사례" 로 따로 보고
IMPACT_TOP_SEED = 85                            # seed 가 이 이상이면 최상위 키워드
IMPACT_FLOOR = 75                               # 최상위 키워드는 학습 결과가 낮아도 이 값 아래로 내려가지 않음
IMPACT_LEARN_RATE = 0.3                         # 최종 점수 = seed*(1-0.3) + 학습값*0.3
IMPACT_MIN_HISTORY_DAYS = 14                    # DB 에 쌓인 기간이 이보다 짧으면 학습하지 않고 seed 만 쓴다
IMPACT_MIN_EVIDENCE = 3                         # 키워드가 이 횟수 미만으로 등장하면 학습값을 내지 않는다

# ---------------------------------------------------------------- 뉴스–공식 문서 연결 (F16)
# 뉴스 제목이 다루는 공식 문서(정부 발표·입법정보)를 찾아 연결한다. 뉴스 제목은 자극적일 수 있어서
# 정책 단계·영향도는 연결된 공식 문서의 값을 따르고, 연결되지 않은 뉴스는 '공식 확인 안 됨'으로 표시한다.
# 점수 = 공유한 정책 용어(45점씩, 최대 60) + 같은 숫자(15점씩, 최대 20) + 같은 핵심 단어(8점씩, 최대 32)
#        + 제목 전체 유사도(0.4~0.8 구간에서 0~50) + 기관명 언급(10) + 공식 문서 직후 보도(5) - 회차 번호 불일치(25).
#        LINK_MIN_SCORE 이상이면 연결한다. 오연결을 줄이려고 기준을 높게 잡았다.
LINK_MIN_SCORE = 60
LINK_MARGIN = 5              # 1등 점수와 이 차이 이내인 문서도 함께 연결 (같은 사안을 다룬 여러 문서)
LINK_MAX_PER_NEWS = 3
LINK_WINDOW_DAYS = 7         # 최근 이 기간의 뉴스만 연결을 시도
LINK_RETRY_HOURS = 48        # 연결 안 된 뉴스는 이 시간이 지난 뒤 한 번 더 시도 (공식 문서가 늦게 올라올 수 있음)
LINK_BEFORE_DAYS = 2         # 뉴스가 공식 문서보다 이만큼 먼저 나온 것까지 허용
LINK_AFTER_DAYS = 14         # 뉴스가 공식 문서보다 이만큼 늦게 나온 것까지 허용
LINK_WEIGHTS = {"entity": 45, "entity_cap": 60, "number": 15, "number_cap": 20,
                "token": 8, "token_cap": 32, "agency": 10, "fresh": 5,
                "similarity": 50, "sim_floor": 0.4, "sim_span": 0.4,   # 제목 유사도 0.4 이하 0점 ~ 0.8 이상 50점
                "conflict": 25}                                       # 회차 번호(제3차/제4차)가 다르면 감점
LINK_IGNORE_NUMBERS = {"2024", "2025", "2026", "2027"}   # 거의 모든 제목에 있는 연도

# ---------------------------------------------------------------- LLM 분류·요약 (F5)
# 인증 정보(ANTHROPIC_API_KEY 등)는 환경변수·`ant auth login` 프로필로만 읽는다. 코드·설정·로그·DB 에 남기지 않는다.
# 인증 정보가 없으면 enrich 는 조용히 건너뛰고, 수집과 리포트는 그대로 동작한다 (LLM 결과가 없으면 키워드 태그를 쓴다).
ENABLE_LLM = True
LLM_MODEL = "claude-opus-5-5"     # 비용을 낮추려면 "claude-sonnet-5-5"($2/$10) 또는 "claude-haiku-5-5"($0.10/$0.50) 로 바꿀 수 있다
LLM_EFFORT = "low"                # 분류·요약처럼 단순한 작업은 낮은 effort 로 충분 (low/medium/high/xhigh/max)
LLM_MAX_TOKENS = 4000             # 응답 JSON 은 작지만, 생각(thinking) 토큰도 이 한도에 들어간다
LLM_DAILY_LIMIT = 200             # 하루에 보낼 API 호출 상한 (기사 1건 = 1호출, 브리핑 1건 = 1호출)
LLM_MAX_AGE_DAYS = 30             # 이 기간보다 오래된 기사는 처리하지 않는다
LLM_MAX_FAILS = 3                 # 한 기사가 이만큼 실패하면 더 시도하지 않는다
LLM_MAX_CONSECUTIVE_ERRORS = 3    # API 오류가 연속으로 이만큼 나면 이번 실행을 중단한다 (호출 상한을 헛되이 쓰지 않으려고)
LLM_SUMMARY_CHARS = 60            # 한 줄 요약 길이 상한
LLM_FALLBACKS = True              # 서버측 refusal fallback (beta). 거절된 요청을 서버가 다른 모델로 다시 처리한다. 400 이 나면 자동으로 끈다
# 모델별 가격($ / 100만 토큰, 입력·출력). 비용 추정용이며 실제 청구와 다를 수 있다 (2026-10 기준 공개 가격)
LLM_PRICES = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}
BRIEFING_ITEMS = 15               # 브리핑 재료로 쓸 상위 기사·문서 수
BRIEFING_MAX_SENTENCES = 5

# ---------------------------------------------------------------- 세션 AI · 오늘의 요약
# API 키 대신 Claude 앱 예약 작업 세션이 분류·요약을 쓴다: ai-export 로 파일을 내보내고, 세션이 쓴 결과를 ai-import 로 검증해 저장한다.
# 세션 방식은 llm_usage(API 호출 상한 LLM_DAILY_LIMIT)에 기록하지 않는다.
SESSION_AI_MAX_ITEMS = 150                    # 하루에 세션이 분류할 최대 기사 수 (구독 사용량 조절)
SESSION_AI_MODEL_LABEL = "claude-app-session" # 세션이 처리한 기사의 llm_model 값
AI_WORK_DIR = BASE_DIR / "work"               # 내보내기·결과 파일 위치 (git 제외)
SUMMARY_MIN_CONCLUSIONS = 1                   # 유효한 결론이 이보다 적으면 AI 요약을 저장하지 않는다 (규칙 요약이 보임)
SUMMARY_MAX_CONCLUSIONS = 5
SUMMARY_CONCLUSION_CHARS = 120
SUMMARY_REPORT_ITEMS = 3                      # "보고할 것" 최대 건수
SUMMARY_WHY_CHARS = 80
SUMMARY_FLOW_TOPICS = 5                       # 흐름 그림에 그릴 주제 수

# ---------------------------------------------------------------- 이메일 알림 (F9)
# python main.py run --notify 일 때만 보낸다. --dry-run 은 메일 내용을 콘솔에만 출력하고 발송 기록도 남기지 않는다.
# SMTP 서버·계정·비밀번호·수신자는 환경변수로만 읽는다 (코드·설정·로그·DB 에 남기지 않음):
#   SMTP_HOST, SMTP_PORT(기본 587, 465 면 SSL), SMTP_USER, SMTP_PASSWORD, NOTIFY_TO(쉼표 구분), NOTIFY_FROM(기본 SMTP_USER)
# 아래 조건 중 하나라도 해당 항목이 있을 때만 보낸다. 해당 항목이 없으면 보내지 않는다.
NOTIFY_RULES = {
    "new_topics": ["CBAM/탄소국경", "배출권거래제(ETS)"],  # 이 주제의 신규 기사·공식 문서 (TOPICS 의 키)
    "impact_levels": ["high"],         # LLM 중요도(llm_impact)가 이 값인 신규 기사·공식 문서
    "rising_min_ratio": 3.0,           # 급증 배율이 이 이상인 키워드
    "rising_repeat_days": 2,           # 같은 급증 키워드는 이 기간 안에 이미 알렸으면 다시 알리지 않음
    "exclude_tier3": True,             # 단체·업계 주장(3등급) 기사는 알림 조건에 쓰지 않음 (집계와 같은 기준)
    "max_age_days": 7,                 # 발행된 지 이보다 오래된 기사는 '신규' 로 보지 않음 (뒤늦게 수집된 옛 기사)
    "first_run_hours": 24,             # 발송 기록이 없을 때는 최근 이 시간 안에 수집된 것을 '신규' 로 봄
    "max_items": 20,                   # 메일 본문 섹션당 최대 표시 건수
}
NOTIFY_ATTACH = True                   # True: 요약 본문 + 리포트 HTML 첨부, False: 리포트 HTML 을 본문으로
NOTIFY_SUBJECT_PREFIX = "[탄소정책 모니터링]"
SMTP_TIMEOUT = 30

# ---------------------------------------------------------------- 공식 기관 중요도 (F15)
# 환경부(현 기후에너지환경부)는 최상위로 고정하고, 나머지 기관은 이 프로젝트에 쌓인 데이터로 점수를 계산한다.
# '학습'은 머신러닝이 아니라 누적 지표 기반의 단순한 가중합이다. 외부 웹 검색으로 영향력을 추정하지 않는다.
#   점수(0~100) = Σ 가중치 × 지표(0~100)
#     volume    : 최근 AGENCY_WINDOW_DAYS 일의 탄소 관련 발표 수 (로그 스케일, 최다 기관 = 100). 수집 설정의 영향을 받으므로 완만하게 반영
#     citations : 그 발표를 다룬 뉴스(공식 문서와 연결된 뉴스, 3등급 제외) 수 (최다 기관 = 100)
#     decided   : 정책 단계가 판정된 발표 중 '확정' 비율
#     direct    : 탄소 관련 발표 중 '직접 규제' 비율
AGENCY_FIXED = {"기후에너지환경부": 1}
AGENCY_KINDS = {
    "기후에너지환경부": "부처", "산업통상부": "부처", "재정경제부": "부처", "외교부": "부처",
    "한국환경공단": "산하·유관기관", "온실가스종합정보센터": "산하·유관기관",
    "국회(의원발의 법률안)": "국회", "국민참여입법센터": "입법 플랫폼", "European Commission": "국제",
}
AGENCY_SCORE_WEIGHTS = {"volume": 0.30, "citations": 0.30, "decided": 0.20, "direct": 0.20}
# 창을 30일로 하면 기관마다 탄소 관련 발표가 3건 미만이라 환경부 외에는 점수가 거의 나오지 않았다(시뮬레이션). 그래서 90일.
AGENCY_WINDOW_DAYS = 90
AGENCY_MIN_DOCS = 3            # 탄소 관련 발표가 이보다 적은 기관은 점수를 내지 않는다 (근거 부족)
AGENCY_MIN_HISTORY_DAYS = 14    # DB 에 쌓인 기간이 이보다 짧으면 계산하지 않는다 ('누적 부족')
AGENCY_OVERRIDES: dict[str, float] = {}   # 사람이 점수를 직접 정하는 기관: {"한국환경공단": 80}

# ---------------------------------------------------------------- 출처 신뢰도 등급 (F13)
# 목적은 단체·업계의 주장이나 자극적으로 쓴 기사를 공식 정보와 구별해 보여주는 것이다. 매체의 정치적 성향 같은 것은 판단하지 않는다.
# 등급은 관찰 가능한 기준으로만 자동 부여하고, 근거(source_tier_reason)를 함께 기록한다. 문제가 있으면 SOURCE_TIER_OVERRIDES 로 보정한다.
#   1 공식      : 공식 출처(F7) 문서, 정부·국제기구 도메인
#   2 일반      : 통신사·주요 언론 목록에 있거나, 최근 30일에 TIER2_MIN_COUNT 건 이상 수집된 언론사
#   3 단체·업계 주장: 협회·재단·환경단체 같은 단체 이름/도메인, 보도자료 배포 사이트. 집계의 근거로 쓰지 않고 별도 배지로 표시
#   0 미분류    : 위에 해당하지 않고 수집 건수가 적어 판단할 근거가 부족
TIER2_MIN_COUNT = 3
TIER_WINDOW_DAYS = 30

# 언론사 이름 또는 도메인(소문자)별 등급 보정. 예: {"kalkine": 0, "greenpeace.org": 3, "한국경제": 2}
SOURCE_TIER_OVERRIDES: dict[str, int] = {}

OFFICIAL_DOMAIN_SUFFIXES = [
    "go.kr", "korea.kr", "gov", "gov.uk", "europa.eu", "un.org", "unfccc.int", "oecd.org", "iea.org",
    "worldbank.org", "imf.org", "ipcc.ch", "wto.org", "iaea.org",
]
# 기업·단체가 보도자료를 직접 올려 배포하는 사이트: 보도자료는 그 기업·단체의 주장이다
PRESS_RELEASE_DOMAINS = [
    "openpr.com", "prnewswire.com", "businesswire.com", "globenewswire.com", "newswire.co.kr", "einpresswire.com",
    "accesswire.com", "prweb.com", "marketwired.com", "pr.co.kr",
]
# 이름이나 도메인이 단체임을 드러내는 표지. 이름에 NEWS_NAME_HINTS 가 들어 있으면(언론사) 적용하지 않는다.
# '연합' 은 연합뉴스 때문에 넣지 않았다 (연합회·환경운동연합처럼 구체적인 형태만).
ORG_NAME_PATTERNS = [
    "협회", "재단", "연합회", "총연합", "환경운동연합", "녹색연합", "그린피스", "시민단체", "노동조합", "상공회의소", "경제인협회", "경총", "전경련",
    "association", "foundation", "greenpeace", "wwf", "ngo", "coalition", "alliance", "friends of the earth", "sierra club",
]
ORG_DOMAINS = ["greenpeace.org", "wwf.org", "kfem.or.kr", "or.kr"]   # or.kr 은 한국에서 비영리 법인에 주는 도메인
# 연구소·센터·대학·컨설팅사처럼 단체일 수도 언론일 수도 있는 이름: 자동으로 등급을 바꾸지 않고 검수 표에 '검토 필요' 로만 표시한다.
# .org 도메인도 같은 이유로 표시만 한다 (비영리 단체도 있지만 carbonbrief.org 처럼 언론도 있다)
SOFT_ORG_PATTERNS = ["institute", "연구원", "연구소", "센터", "center", "forum", "포럼", "council", "university", "대학",
                     "endowment", "& company", "consulting", "컨설팅", "watch", "society", "initiative", "trust"]
NEWS_NAME_HINTS = ["뉴스", "신문", "일보", "방송", "타임스", "저널", "데일리", "투데이", "미디어", "news", "times", "journal", "daily", "post", "herald", "media"]

# 통신사·주요 언론 (이름, 대소문자·공백 무시). 목록에 없는 언론은 수집 빈도로 판단한다.
MAJOR_OUTLETS = [
    "연합뉴스", "연합뉴스tv", "연합인포맥스", "뉴시스", "뉴스1", "한국경제", "매일경제", "서울경제", "조선일보", "중앙일보", "동아일보", "한겨레",
    "경향신문", "한국일보", "세계일보", "문화일보", "국민일보", "머니투데이", "이데일리", "헤럴드경제", "아시아경제", "파이낸셜뉴스", "전자신문",
    "kbs", "mbc", "sbs", "ytn", "jtbc", "yonhap", "reuters", "bloomberg", "ap", "afp", "bbc", "cnn", "financial times", "the guardian",
    "the new york times", "the wall street journal", "nature", "seoul economic daily", "the korea herald", "the korea times",
]

# 자극적 표현: 제목에 있으면 '표시'만 한다. 점수 계산이나 삭제에는 쓰지 않는다. ('기후위기' 같은 일반 표현은 넣지 않았다)
SENSATIONAL_TERMS = [
    "충격", "경악", "폭로", "발칵", "초비상", "대혼란", "재앙", "파국", "최악", "난리", "긴급",
    "shocking", "bombshell", "catastrophe", "doomsday", "explosive", "alarming",
]
SINGLE_SOURCE_SIM = 0.5   # 단체·업계 기사와 제목이 이만큼 비슷한 1·2등급 기사가 있으면 '다른 출처도 다뤘다'고 본다
SINGLE_SOURCE_DAYS = 3

# 공식 문서 기반 뉴스 검색: 일반 키워드 검색으로는 작은 보도자료의 후속 기사가 거의 모이지 않아서,
# 새 공식 문서의 제목으로 구글 뉴스를 따로 검색한다. 공식 문서 한 건당 최대 2번(발견 직후, 48시간 뒤).
COVERAGE_DOC_DAYS = 7           # 이 기간 안에 발행된 공식 문서만 검색
COVERAGE_RETRY_HOURS = 48       # 첫 검색 뒤 이 시간이 지나면 한 번 더 (후속 기사는 뒤늦게 나온다)
COVERAGE_MAX_PER_RUN = 15       # 한 번 실행에 보낼 검색 요청 상한 (영향도 높은 문서부터)
COVERAGE_DAYS_BACK = 7          # 검색할 뉴스 기간
COVERAGE_RESULTS_PER_QUERY = 8  # 검색 결과 중 앞에서부터 볼 건수
COVERAGE_MIN_SCORE = 40         # 공식 문서와 이 점수 미만인 결과는 저장하지 않음 (엉뚱한 기사 방지, 연결 기준 60보다 낮음)
COVERAGE_QUERY_CHARS = 45       # 검색어로 쓸 제목 길이

# 정책 용어: 이름 → 같은 것을 가리키는 표기들. 뉴스와 공식 문서가 같은 용어를 공유하면 강한 연결 근거가 된다.
POLICY_ENTITY_PATTERNS = {
    "배출권거래제": ["배출권거래제", "k-ets", "배출권 거래", "배출권 할당", "할당계획", "배출권"],
    "NDC": ["ndc", "국가 온실가스 감축목표", "국가결정기여", "온실가스 감축목표"],
    "CBAM": ["cbam", "탄소국경조정", "탄소국경", "carbon border"],
    "탄소중립기본법": ["탄소중립기본법", "탄소중립·녹색성장 기본법", "탄소중립 녹색성장 기본법"],
    "목표관리제": ["목표관리제"],
    "교통에너지환경세": ["교통·에너지·환경세"],
    "수소": ["수소경제", "청정수소", "수소법"],
    "재생에너지": ["신에너지 및 재생에너지", "재생에너지법", "재생에너지 공급"],
    "녹색분류체계": ["녹색분류체계", "k-택소노미"],
    "기후공시": ["기후공시", "지속가능성 공시"],
    "탄소차액계약": ["탄소차액계약", "탄소 차액 계약", "carbon contracts for difference", "ccfd"],
    "자발적탄소시장": ["자발적 탄소시장", "voluntary carbon"],
    "국제감축": ["국제감축", "article 6"],
    "위탁거래": ["위탁거래"],
}

# 기관 별칭: 뉴스 제목에 기관명이 나오면 가점 (기관명 접두 일치)
AGENCY_ALIASES = {
    "기후에너지환경부": ["기후에너지환경부", "기후부", "환경부"],
    "산업통상부": ["산업통상부", "산업부", "산업통상자원부"],
    "재정경제부": ["재정경제부", "재경부", "기획재정부", "기재부"],
    "한국환경공단": ["환경공단"],
    "온실가스종합정보센터": ["온실가스종합정보센터", "온실가스센터", "gir"],
    "외교부": ["외교부"],
    "국회": ["국회", "의원"],
    "European Commission": ["eu 집행위", "유럽연합 집행위", "유럽위원회", "european commission"],
}

# 연결 근거로 쓰기에는 너무 흔한 단어 (이 분야 제목에 늘 나오는 말)
LINK_GENERIC_TOKENS = set("""
정부 발표 개정 추진 관련 기업 정책 지원 사업 확대 대응 강화 도입 방안 계획 제도 시행 입법예고 행정예고 보도자료 공고 안내
탄소 기후 에너지 온실가스 배출 산업 국가 환경 기후변화 기후위기 녹색 성장 중립 탄소중립 국내 해외 글로벌 국제 신규 올해 내년
개최 선정 모집 공모 확인 논의 검토 마련 실시 진행 예정 일부 법률 시행령 시행규칙 부처 장관 위원회 협의 협력 전환 규제 감축
carbon climate policy energy emissions emission commission european union news
""".split())

EU_PRESSCORNER_RSS = "https://ec.europa.eu/commission/presscorner/api/rss?language=en"
EU_KEYWORDS = [
    "climate", "emission", "emissions", "ets", "carbon", "cbam", "net-zero", "net zero",
    "decarbonisation", "decarbonization", "greenhouse", "2040 target", "green deal",
]

# 열린국회정보 의원발의 법률안 API. 인증키는 환경변수 ASSEMBLY_API_KEY (없으면 샘플 모드: 키워드당 5건)
ASSEMBLY_API_URL = "https://open.assembly.go.kr/portal/openapi/nzmimeepazxkubdpn"
ASSEMBLY_AGE = 22   # 국회 대수
ASSEMBLY_KEYWORDS = ["탄소", "온실가스", "배출권", "기후위기", "탄소중립", "녹색성장", "탄소국경", "재생에너지", "수소"]
DAYS_BACK = 3  # 수집 시 최근 N일 기사만 요청

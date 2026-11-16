# 탄소정책 모니터링 — Claude Code 작업 지침

배출권거래제(ETS)·CBAM 등 탄소 관련 뉴스와 정부·국회·EU 공식 문서를 매일 자동 수집해 분류하고, 정책 변화와 이슈 트렌드를 HTML 리포트로 보여주는 Python 프로그램이다.
기획은 `PRD.md`, 단계별 구현 프롬프트는 `PROMPTS.md`, 사용법은 `README.md`를 본다.

## 명령어

```
pip install -r requirements-dev.txt     # 설치 (테스트 포함)
python -m pytest -q                      # 테스트. 변경 후 항상 실행
python main.py run                       # 하루치 전체 실행: 수집 → 등급 → LLM 분류 → 후속 보도 검색 → 연결 → 기관 점수 → 리포트
python main.py collect | report          # 수집만 / 리포트만 (reports/report_날짜.html)
python main.py refilter | classify | reweight | link --relink | tiers | rank-agencies | enrich --limit N
python main.py run --notify | --dry-run  # 알림 메일 발송 / 내용만 출력. notify 명령은 수집 없이 알림만
python main.py search "키워드" | export --from --to --topic --region --out  # 검색(최근 20건) / CSV 내보내기
python main.py ai-export classify|summary / ai-import classify|summary   # 예약 작업 세션의 AI 분류·오늘의 요약 (docs/scheduled-task-prompt.md)
```

각 명령의 의미는 `python main.py --help`와 `README.md`에 있다. Windows PowerShell 5.1 환경이라 `&&`를 쓸 수 없고, 한글 출력은 `$env:PYTHONIOENCODING='utf-8'`가 필요하다.

## 구조와 의존 방향 (역방향 import 금지)

```
config.py                  모든 설정(검색어, 키워드, 임계값, 가중치). 동작을 바꾸려면 코드가 아니라 여기를 고친다
main.py                    명령 진입점
carbon/
  db.py                    SQLite, 마이그레이션(MIGRATIONS 목록, PRAGMA user_version)
  sources/                 수집기: base(Article, Source), google_news, boards(정부 게시판 파서), eu, assembly, http(PoliteClient), registry
  pipeline.py              수집 → 중복 제거 → 태깅 → 저장, 연결(link_news), 후속 보도 검색, 출처 등급 부여
  tagging.py policy.py     주제·지역 태깅 / 정책 단계(추진·확정)·국내 영향도 규칙
  filters.py tiers.py      무관 기사 필터 / 출처 신뢰도 등급
  linking.py               뉴스 제목 ↔ 공식 문서 연결 점수
  keywords.py weights.py agencies.py   급증 키워드 / 영향도 가중치 학습 / 기관 중요도
  llm.py                   Claude 분류·요약·브리핑 (호출부 AnthropicBackend 와 로직 분리)
  handoff.py               세션 AI: llm.py 의 선택·검증·저장을 재사용해 파일로 내보내고 결과를 가져온다 (llm_usage 에 기록 안 함)
  query.py                 검색·내보내기 조건 조합(matches). 3단계 화면 필터도 같은 규칙을 쓴다
  notify.py                이메일 알림: 조건 판정(select_alerts) / 메일 구성 / SMTP 발송 분리. 발송 기록 notify_log
  analysis.py              DB → 리포트용 dict (HTML 을 만들지 않는다)
  render.py                dict → HTML (DB 를 읽지 않는다)
tests/                     pytest. 모듈마다 test_*.py
tools/                     검수·측정 도구 (baseline, stage_review, link_review, tier_review, filter_review, llm_review)
docs/source-research.md    공식 출처 조사 결과(접속·robots·RSS·약관 확인 상태)
docs/price-research.md     배출권 가격(KAU·EUA) 출처 조사 (구현 없음)
```

`render.py`는 db·analysis 를 import 하지 않고, `analysis.py`는 HTML 을 만들지 않는다. 화면(3단계)은 `render.py`만 고쳐서 만든다.

## 반드시 지킬 규칙

- **설정은 `config.py`에서만.** 키워드·임계값·가중치를 코드에 하드코딩하지 않는다.
- **시각:** DB 에는 UTC, 날짜 집계와 화면 표시는 KST(`config.KST`).
- **기사 본문은 저장하지 않는다.** 제목, 링크, 언론사, 발행 시각, RSS 요약만 다룬다.
- **삭제하지 않는다.** 무관 기사는 `relevant=0`으로 표시만 하고 모든 집계·목록에서 뺀다.
- **스키마 변경은 `db.MIGRATIONS` 끝에 함수를 추가**한다. 기존 DB 데이터는 보존한다.
- **비밀 값(API 키, SMTP 계정)은 환경변수로만** 읽는다. 코드·설정·로그·DB·커밋에 남기지 않는다. 인증 정보가 없으면 LLM 단계만 조용히 건너뛴다.
- **뉴스 제목으로 정책 단계·국내 영향도를 판정하지 않는다.** 공식 문서에만 판정하고, 뉴스는 연결된 공식 문서의 값을 따른다. 연결되지 않은 뉴스는 "공식 확인 안 됨".
- **규칙 vs LLM:** LLM 은 규칙이 판정하지 못한 부분(관련성 미판정, 공식 문서의 미분류 단계·영향도)만 채우고 규칙 판정을 덮어쓰지 않는다. 의견이 다르면 `llm_*` 컬럼에 따로 둔다.
- **관련 기사를 잘못 숨기는 것이 무관 기사가 남는 것보다 나쁘다.** 제외는 확실한 패턴만 하고 애매하면 미판정(NULL)로 둔다.
- **공식 사이트 수집은 예의 바르게:** `robots.txt` 준수(`PoliteClient`), 같은 호스트 2초 간격, 목록 첫 페이지만. 사이트 구조가 바뀌어 글을 0건 찾으면 조용히 넘기지 않고 실패로 기록한다. `likms.assembly.go.kr`은 robots 가 전체 차단이라 접속하지 않는다.
- **모든 판정에는 근거를 남긴다** (`relevance_reason`, `source_tier_reason`, `impact_keyword`, `agencies.evidence` 등). 틀렸을 때 바로 보정할 수 있어야 한다.
- **새 기능마다 테스트를 추가**하고, 실제 데이터에 돌려 결과를 눈으로 확인한다. 테스트를 통과시키려고 단언을 느슨하게 만들지 않는다 (실제로 결함을 잡은 사례가 여러 번 있다).
- **숫자를 부풀리지 않는다.** 측정하지 못한 것은 "미측정", 검증하지 못한 것은 "검증 못 함"이라고 쓴다.
- 커밋은 사용자가 요청했을 때만 한다. 메시지는 파일로 만들어 `git commit -F` 로 전달한다 (PowerShell 에서 여러 줄 인자가 깨진다). BOM 이 붙지 않게 `Set-Content` 대신 Write 도구를 쓴다.

## 단계 구조 (PROMPTS.md)

1단계 기본 뼈대 → 2단계 주요 기능 → 3단계 UI 디자인 → 4단계 PRD 충족 여부·버그 검토(Playwright). 단계마다 완료 기준(게이트)을 통과한 뒤 다음으로 간다.
한 단계에서는 그 단계의 범위만 다룬다. 범위 밖 기능이 필요해 보이면 만들지 말고 제안만 한다.

## 현재 상태

- 1단계 완료, 2단계 2-0~2-11 완료, 2단계 마무리 점검 완료 (`stage-2`·`stage-3` 태그는 2026-11-13 PC 에서 원격에 올림). 2단계 게이트의 지표(태깅률 85%, 관련성 90%)는 미달·미측정. 2-11 은 조사만 (`docs/price-research.md`, 구현 여부는 사용자 결정). 3단계 UI(A안: 상단 요약 + 왼쪽 필터 + 목록)는 3-1~3-3 구현 완료,  4단계 점검 보고서는 `docs/qa-report.md` (QA-B1·QA-B3 수정 완료, QA-B2·PRD 불일치는 사용자 결정 대기).
- 이전 환경(Windows)의 git 이력과 `stage-1` 태그는 옮겨 오지 못했다. `run_daily.bat` 은 4단계 QA-B1 에서 다시 만들었고 2026-11-13 PC(Windows 11, Python 3.10.9)에서 실행을 확인했다. 매일 실행은 Windows 작업 스케줄러가 아니라 Claude 앱 예약 작업이 맡는다 (사용자 결정, 2026-11-13). 지금 저장소는 GitHub `benpal826/news`.
- 2-9 이메일 알림은 dry-run 과 모의 SMTP 로만 검증했다. 실제 발송 테스트는 사용자 승인 후 1회 해야 한다 (미검증).
- LLM 단계(F5)는 실제 API 호출을 검증하지 못했다 (인증 정보 없음). 모의 응답으로만 테스트했다.
- 기관 중요도(F15)·키워드 평소 빈도 비교(F14)는 DB 에 14일 이상 쌓여야 작동한다.
- 정부 사이트 이용약관은 읽지 못했다 (`docs/source-research.md`).
- 주제 태깅률은 55.7%(4단계 QA, 실제 제목 61건)로 목표 85%에 못 미친다. 나머지는 AI 분류의 몫이다. API 키 대신 Claude 앱 예약 작업 세션이 ai-export/ai-import 로 분류·오늘의 요약을 채운다 (`docs/superpowers/specs/2026-11-13-daily-summary-design.md`).

## 알려진 함정

- `Markets`의 `ets`처럼 영문 키워드가 단어 일부에 걸리지 않게 영문은 단어 경계로 비교한다 (`tagging.py`, `filters.py`, `policy.py`).
- 한국어 조사 `도`/`만`을 떼면 `제도`가 `제`로 잘린다. 조사 제거는 어간이 3글자 이상이거나 알려진 단어일 때만 한다 (`keywords.py`).
- Google News RSS 의 요약은 제목의 반복이라 본문 정보가 없다. 제목만으로 판단할 수 없는 기사가 많다.
- 정책 단계는 제목에서 문장 끝에 가까운 표지가 이긴다 (`고시(안) 행정예고` → 추진). 시행령·시행규칙·시행계획은 '시행'이 아니다.

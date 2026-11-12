# 운영 규칙 (tourism: 데이트·놀거리 추천)

1. **모든 출력은 맨 위에 한 줄 요약**(굵게). 그 아래에 상세.
2. **단일 스키마**: 모든 data/*.csv 는 `date,place_id,field,value,source` 5열. 예외 없음.
   세로형 누적(append only), **빈값은 행 자체를 만들지 않음(skip)**. 읽을 때는 같은 필드의 최신 값 사용.
3. **규칙·구조 변경 시** decisions.md 에 `YYYY-MM-DD — 한 줄 요약` 추가.
4. **API 키는 환경변수로만** (KAKAO_REST_KEY, SEOUL_OPEN_KEY, SWIPE_SYNC_URL). 커밋 금지, .env 는 gitignore.
5. 지역/반경/카테고리는 **config.yaml 만** 수정. 코드에 지역 하드코딩 금지.
6. main 에 바로 커밋·푸시.

## 파일
- `run_weekly.sh` 주 1회 갱신 단일 진입점 (`--sample` 키 없이 테스트, `--import-swipes CSV` 스와이프 반영)
- `data/candidates.csv` 후보 속성 / `mentions.csv` 후기 수 주간 스냅샷 / `places.csv` 스와이프·점수·한줄평
- `taste.md` 취향 요약(자동), `report.md` 이번 주 추천, `docs/cards.json` 스와이프 앱용 카드
- `python3 -m src.record 가게명 점수 "한줄평"` 방문 기록, `python3 -m src.course 신사 저녁` 코스 제안

## 대표메뉴·가격대 (주간 갱신 때 Claude 가 직접 선별)
- 카카오맵 메뉴 데이터는 공식 API 에 없음 → `python3 -m src.menus todo 30` 으로 메뉴 없는 곳의 후기 요약을 뽑아, Claude 가 읽고 **가게가 맞고 메뉴명이 분명한 것만** 골라 `{"place_id":[메뉴,가격,가격대,후기날짜]}` JSON 으로 만든 뒤 `python3 -m src.menus import FILE`. 확인 안 되면 비워 둠(지어내지 않음). 선별된 곳은 자동추출이 덮어쓰지 않음.
- `--sample` 실행은 data/_sample, out/sample 에만 씀(실데이터와 분리).

## 요청 처리
- "토요일 신사 저녁 코스 짜줘" → `src.course 신사 저녁` 실행 후 결과를 요약해 제안(저장한 곳만 사용, 도보 동선).
- "○○ 갔다왔는데 4점, ~했어" → `src.record` 로 기록.
- 후기 집계는 체험단·협찬·원고료·제공받아 문구 글 제외(config.yaml trend.exclude_phrases).

## 스와이프
- `docs/index.html`(GitHub Pages) → Apps Script(`apps_script/Code.gs`) → 시트 `swipes`. 주소는 `docs/config.js`(공개), 동기화 주소는 환경변수 `SWIPE_SYNC_URL`.
- run_weekly.sh 실행 시 시트의 스와이프가 data/places.csv 로 들어가고 본 곳은 cards.json 에서 제외됨.
- 앱의 '저장/패스' 메뉴는 docs/history.json(run 이 생성) + 폰 로컬 기록을 합쳐 보여줌. 저장↔패스 이동은 새 스와이프로 시트에 추가됨(스와이프 date 는 초 단위 시각이라 같은 날 번복도 마지막 값이 유지됨).
- Apps Script(`apps_script/Code.gs`)를 고치면 시트에서 **배포 관리 → 새 버전으로 재배포**해야 반영됨(주소는 유지). 앱 헤더의 '⏳ 전송 대기 N'이 계속 보이면 전송 실패.

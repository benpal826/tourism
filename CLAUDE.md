# 운영 규칙 (tourism: 데이트·놀거리 추천)

1. **모든 출력은 맨 위에 한 줄 요약**(굵게). 그 아래에 상세.
2. **단일 스키마**: 모든 data/*.csv 는 `date,place_id,field,value,source` 5열. 예외 없음.
   세로형 누적(append only), **빈값은 행 자체를 만들지 않음(skip)**. 읽을 때는 같은 필드의 최신 값 사용.
3. **규칙·구조 변경 시** decisions.md 에 `YYYY-MM-DD — 한 줄 요약` 추가.
4. **API 키는 환경변수로만** (KAKAO_REST_KEY, SEOUL_OPEN_KEY, SWIPE_SYNC_URL, NAVER_CLIENT_ID·NAVER_CLIENT_SECRET=NAVER API HUB 검색, NAVER_MAP_CLIENT_ID·NAVER_MAP_CLIENT_SECRET=NCP Maps — 검색 키는 src.trend 후기 합산에 사용). 커밋 금지, .env 는 gitignore.
   - 예외: `NAVER_MAP_CLIENT_ID` 는 네이버 지도 JS SDK 용으로 `docs/config.js` 에 공개(NCP 에 등록한 도메인에서만 동작). Secret 은 어디에도 공개하지 않음.
5. 지역/반경/카테고리는 **config.yaml 만** 수정. 코드에 지역 하드코딩 금지. (앱 설정에서 더한 역은 시트→`data/regions.csv` 로 받아 수집 대상에 더해짐, F19)
6. main 에 바로 커밋·푸시.

## 파일
- `run_weekly.sh` 주 1회 갱신 단일 진입점 (`--sample` 키 없이 테스트, `--import-swipes CSV` 스와이프 반영)
- `data/candidates.csv` 후보 속성 / `mentions.csv` 후기 수 주간 스냅샷 / `places.csv` 스와이프·점수·한줄평
- `taste.md` 취향 요약(자동), `report.md` 이번 주 추천, `docs/cards.json` 스와이프 앱용 카드
- `python3 -m src.record 가게명 점수 "한줄평"` 방문 기록, `python3 -m src.course 신사 저녁` 코스 제안

## 대표메뉴·가격대 (주간 갱신 때 Claude 가 직접 선별)
- 카카오맵 메뉴 데이터는 공식 API 에 없음 → `python3 -m src.menus todo 30` 으로 메뉴 없는 곳의 후기 요약을 뽑아, Claude 가 읽고 **가게가 맞고 메뉴명이 분명한 것만** 골라 `{"place_id":[메뉴,가격,가격대,후기날짜]}` JSON 으로 만든 뒤 `python3 -m src.menus import FILE`. 확인 안 되면 비워 둠(지어내지 않음). 선별된 곳은 자동추출이 덮어쓰지 않음.
- `--sample` 실행은 data/_sample, out/sample 에만 씀(실데이터와 분리).

## 후보·순위 (F11·F12)
- 후보는 역 반경 카카오 목록 + config.yaml discover.place_keywords(루프탑·칵테일바 등). 역·카테고리별 추천글(discover.rec_queries)에 나온 횟수(rec_mentions) 상위만 후기·사진 보강.
- 순위: 식당은 맛 신호, 카페·술집은 분위기·뷰 신호(config signals) + 후기 규모·최근 30일·추천글 언급. 카드는 카테고리별 상위 rank.cards_per_category 곳.

## 카드 사진·설명 (주간 갱신 때 Claude 가 직접)
- 사진: `python -m src.photos todo 10 percat` — 카테고리별 상위 10곳 중 미선별만. 나머지는 자동 사진 4~8장.
- 설명: `python -m src.photos notes missing`(설명 없는 카드 전부, 주간 갱신 기본) 또는 `notes 20 percat` 로 후기 발췌를 보고 `{"place_id":{"summary":"캐치프레이즈
메뉴: …
가격: …
맛: …
분위기: …
팁: …
추천: …"}}` 를 import(사진은 그대로). 후기·사진에서 확인되는 것만, 없는 줄은 생략. 메뉴=메뉴 이름·가격, 맛=맛·식감 평가만(메뉴 나열 금지), 팁=위치·웨이팅·예약·주차(가격 금지) — 줄끼리 반복하지 않음. 앱의 먹거리 카드 정보 칸은 업종·후기뿐이라 대표메뉴·가격대·위치는 이 글에 담는다(F17).
- 자동 사진은 검색어 기준 분류라 메뉴판·거리·복도가 섞임 → `python -m src.photos todo 30`(이미 선별된 곳도 다시: `todo 200 all`) 으로 미선별 카드 상위 30곳의 후보 모음 이미지(out/photos/<place_id>.jpg, 번호 붙음)를 만들고, Claude 가 이미지를 직접 보고 `{"place_id":{"food":[번호],"interior":[번호],"summary":"2~3줄 요약"}}` JSON 을 만든 뒤 `python -m src.photos import FILE`.
- food=메인 요리가 잘 보이는 것, interior=실내 공간·좌석·조명(분위기 사진도 여기). 종류당 최대 4장. 외관·메뉴판·영수증·거리·안내문·사람 위주 사진은 고르지 않음. 맞는 사진이 없으면 빈 목록(지어내지 않음). 선별된 곳은 자동 수집이 덮어쓰지 않음.
- summary: todo 가 함께 출력하는 후기 요약과 사진에서 확인되는 것만으로 2~3줄(어떤 곳·대표 메뉴·분위기·웨이팅/팁). 다른 가게 글뿐이면 비움.

## 팝업 (F23, 주간 갱신 때 Claude 가 직접)
- 블로그 제목 자동 추출은 이름·장소·기간이 부정확해 카드에 안 냄(config popup.curated_only). `python -m src.popups todo` 로 역별 최근 팝업 글을 보고, 행사마다 `[{"name","venue","address","start","end","summary","link"}]` JSON 을 써서 `python -m src.popups import FILE`.
- 글에서 확인되는 것만. 종료일·장소를 모르면 넣지 않음. import 가 장소를 카카오 지도로 찾아 가장 가까운 역에 붙이고, 끝났거나 역에서 1.5km 넘으면 뺌. 같은 행사를 여러 이름으로 넣지 않음.
- summary: `캐치프레이즈
기간: …
장소: …
볼거리: …
혜택: …
팁: …`(확인되는 줄만).

## 요청 처리
- "토요일 신사 저녁 코스 짜줘" → `src.course 신사 저녁` 실행 후 결과를 요약해 제안(저장한 곳만 사용, 도보 동선).
- "○○ 갔다왔는데 4점, ~했어" → `src.record` 로 기록.
- 후기 집계는 체험단·협찬·원고료·제공받아 문구 글 제외(config.yaml trend.exclude_phrases).

## 스와이프
- `docs/index.html`(GitHub Pages) → Apps Script(`apps_script/Code.gs`) → 시트 `swipes`. 주소는 `docs/config.js`(공개), 동기화 주소는 환경변수 `SWIPE_SYNC_URL`.
- run_weekly.sh 실행 시 시트의 스와이프가 data/places.csv 로 들어가고 본 곳은 cards.json 에서 제외됨.
- 앱의 '저장/패스' 메뉴는 docs/history.json(run 이 생성) + 폰 로컬 기록을 합쳐 보여줌. 저장↔패스 이동은 새 스와이프로 시트에 추가됨(스와이프 date 는 초 단위 시각이라 같은 날 번복도 마지막 값이 유지됨).
- Apps Script(`apps_script/Code.gs`)를 고치면 시트에서 **배포 관리 → 새 버전으로 재배포**해야 반영됨(주소는 유지). 앱 헤더의 '⏳ 전송 대기 N'이 계속 보이면 전송 실패.

## 실행·검증 (방법론)
- 실행: `bash run_weekly.sh` (주간 갱신, 키는 .env) · Windows 로컬은 `$env:PYTHONUTF8=1; python -m src.run`
- 검증: `powershell -File init.ps1` — F00(샘플 모드 전체 파이프라인)이 통과하면 exit 0. 기능별은 `features.json`의 `verify`

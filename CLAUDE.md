# 운영 규칙 (tourism: 데이트·놀거리 추천)

1. **모든 출력은 맨 위에 한 줄 요약**(굵게). 그 아래에 상세.
2. **단일 스키마**: 모든 data/*.csv 는 `date,place_id,field,value,source` 5열. 예외 없음.
   세로형 누적(append only), **빈값은 행 자체를 만들지 않음(skip)**. 읽을 때는 같은 필드의 최신 값 사용.
3. **규칙·구조 변경 시** decisions.md 에 `YYYY-MM-DD — 한 줄 요약` 추가.
4. **API 키는 환경변수로만** (KAKAO_REST_KEY, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, SEOUL_OPEN_KEY). 커밋 금지, .env 는 gitignore.
5. 지역/반경/카테고리는 **config.yaml 만** 수정. 코드에 지역 하드코딩 금지.
6. main 에 바로 커밋·푸시.

## 파일
- `run_weekly.sh` 주 1회 갱신 단일 진입점 (`--sample` 키 없이 테스트, `--import-swipes CSV` 스와이프 반영)
- `data/candidates.csv` 후보 속성 / `mentions.csv` 후기 수 주간 스냅샷 / `places.csv` 스와이프·점수·한줄평
- `taste.md` 취향 요약(자동), `report.md` 이번 주 추천, `docs/cards.json` 스와이프 앱용 카드
- `python3 -m src.record 가게명 점수 "한줄평"` 방문 기록, `python3 -m src.course 신사 저녁` 코스 제안

## 요청 처리
- "토요일 신사 저녁 코스 짜줘" → `src.course 신사 저녁` 실행 후 결과를 요약해 제안(저장한 곳만 사용, 도보 동선).
- "○○ 갔다왔는데 4점, ~했어" → `src.record` 로 기록.
- 후기 집계는 체험단·협찬·원고료·제공받아 문구 글 제외(config.yaml trend.exclude_phrases).

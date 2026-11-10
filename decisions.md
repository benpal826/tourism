# 결정 기록
- 2026-11-10 — 초기 구조: 단일 5열 세로형 CSV 스키마, nearby 모드(5개 역 반경 700m), theme 모드는 구조만 예약.
- 2026-11-10 — 키 없으면 sample/ 데이터로 동작하는 단일 스크립트(run_weekly.sh) 채택.
- 2026-11-10 — 스와이프 웹앱 구현 방식은 사용자 확인 대기 중(제안: GitHub Pages + Apps Script + 시트).
- 2026-11-10 — 스와이프 방식 확정: GitHub Pages(docs/) + Apps Script 웹앱 + 구글 시트, 주간 실행 시 SWIPE_SYNC_URL 로 places.csv 반영.

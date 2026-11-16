샘플데이터 설명

sample.db: tests/fixtures/sample.db의 원본 복사본. 자동 테스트와 화면 테스트에 쓰는 고정 SQLite DB이며 실제 운영 DB가 아닙니다.
sample_items.json: tests/fixtures/sample_items.json의 원본 복사본. 테스트용 샘플 항목 데이터입니다.
ai_classify_2026-11-13.json: 실제 세션에 내보낸 분류 입력. instructions, schema, items를 통해 에이전트가 읽는 지시·형식·기사 재료를 확인할 수 있습니다.
ai_classify_2026-11-13.out.json: Claude 세션이 작성한 분류 결과. ai-import classify가 검증하고 반영하는 출력입니다.
ai_summary_2026-11-13.json: 실제 세션에 내보낸 요약 입력. 공식 문서·뉴스와 주제 건수 등 요약의 근거입니다.
ai_summary_2026-11-13.out.json: Claude 세션이 작성한 결론과 보고 항목. ai-import summary가 검증하고 저장하는 출력입니다.

입력 JSON과 같은 이름의 .out.json을 짝지어 보면 에이전트가 무엇을 읽고 쓰는지 확인할 수 있습니다. 2026-11-13 파일은 실제 실행 자료이며 더미 데이터가 아닙니다. 다른 날짜의 운영 DB에 그대로 가져오지 마세요. 고정 DB는 테스트용으로 별도 사용합니다.
실행·설치 방법은 ../핵심산출물/README.md, 예약 작업 순서는 ../핵심산출물/scheduled-task-prompt.md를 참고하세요.

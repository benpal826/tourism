# 진행 기록

## 완료
- 2026-11-24 F00 기존 시스템이 돈다 — `init.ps1` 통과("init OK", exit 0). 방법론 v0.2 적용.

## 진행 중

## 다음 할 일
- 새 기능은 /change 로 prd.md·features.json 에 추가한다. 후보: 네이버 블로그 검색으로 후기 수집 보강(NAVER API HUB 키는 .env 에 있음, 아직 코드 미사용).

## 실패한 접근 (다시 시도하지 말 것)
- Windows 에서 `python -m src.run` 을 그냥 돌리면 출력의 `—` 때문에 UnicodeEncodeError(cp949)로 죽는다. `PYTHONUTF8=1` 필요(init.ps1 에 반영).

## 가정한 것
- F00 은 이미 운영 중인 기존 시스템이라 /review 대상 기능이 없다고 보고 검토 단계를 건너뛴다. 새 기능(F01~)부터 /review 를 적용한다.
- 실키 주간 갱신(`run_weekly.sh`)은 F00 검증에 넣지 않았다. 외부 API 호출·실데이터 변경이 있어서다.

## 제안 (features.json 변경 제안 — 사람이 판단)
- 이 PC 에서 `run_weekly.sh` 는 `python3` 를 부르는데, `python3` 가 Microsoft Store 바로가기(실제 파이썬 아님)라 실패할 수 있다. 로컬 실행용으로 고칠지 결정 필요. (지금까지 실데이터 갱신은 클라우드 세션에서 했다.)
- `SEOUL_OPEN_KEY` 가 이 PC 에 없다. 없으면 서울 문화행사 수집만 건너뛴다.

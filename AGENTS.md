# Codex 등 다른 AI용 안내
> 한 줄 요약: 규칙 원본은 `./CLAUDE.md`(이 폴더)와 `../CLAUDE.md`(방법론). 작업 전에 둘 다 읽고 그대로 따른다.

- 명령 절차(/next, /change, /review, /wrap 등)는 `../_commands/`의 같은 이름 .md 파일을 따른다. 사용자가 "계속", "다음"이라고 해도 같다.
- CLAUDE.md 의 "Claude 가 직접 선별"(대표메뉴)은 이 파일을 읽는 AI 자신이 한다는 뜻이다.
- 검증: 전체 `powershell -File init.ps1`, 기능별은 `features.json`의 `verify`.
- AskUserQuestion 도구가 없으면 일반 대화로 한 번에 한 질문씩, 추천 답을 붙여 묻는다.
- 서브에이전트가 없으면 /review 는 "새 세션에서 검토만 하세요"라고 안내하고 직접 채점하지 않는다.
- 이 파일은 규칙을 복사하지 않는다. 규칙이 바뀌면 CLAUDE.md 만 고친다.

from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import shutil, json, html, hashlib

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / '제출'
WORK = OUT / '_작업'
for name in ['핵심산출물', '샘플데이터', 'screenshots']:
    (OUT/name).mkdir(exist_ok=True)
copies = {'reports/report_2026-11-13.html':'index.html', 'CLAUDE.md':'CLAUDE.md', 'README.md':'README.md', 'PRD.md':'PRD.md', 'run_daily.bat':'run_daily.bat', 'docs/scheduled-task-prompt.md':'scheduled-task-prompt.md'}
for src, dst in copies.items(): shutil.copy2(ROOT/src, OUT/'핵심산출물'/dst)
samples=['tests/fixtures/sample.db','tests/fixtures/sample_items.json'] + ['work/ai_'+k+'_2026-11-13'+s+'.json' for k in ['classify','summary'] for s in ['', '.out']]
for src in samples: shutil.copy2(ROOT/src, OUT/'샘플데이터'/Path(src).name)
(OUT/'샘플데이터/README.txt').write_text('''샘플데이터 설명

sample.db: tests/fixtures/sample.db의 원본 복사본. 자동 테스트와 화면 테스트에 쓰는 고정 SQLite DB이며 실제 운영 DB가 아닙니다.
sample_items.json: tests/fixtures/sample_items.json의 원본 복사본. 테스트용 샘플 항목 데이터입니다.
ai_classify_2026-11-13.json: 실제 세션에 내보낸 분류 입력. instructions, schema, items를 통해 에이전트가 읽는 지시·형식·기사 재료를 확인할 수 있습니다.
ai_classify_2026-11-13.out.json: Claude 세션이 작성한 분류 결과. ai-import classify가 검증하고 반영하는 출력입니다.
ai_summary_2026-11-13.json: 실제 세션에 내보낸 요약 입력. 공식 문서·뉴스와 주제 건수 등 요약의 근거입니다.
ai_summary_2026-11-13.out.json: Claude 세션이 작성한 결론과 보고 항목. ai-import summary가 검증하고 저장하는 출력입니다.

입력 JSON과 같은 이름의 .out.json을 짝지어 보면 에이전트가 무엇을 읽고 쓰는지 확인할 수 있습니다. 2026-11-13 파일은 실제 실행 자료이며 더미 데이터가 아닙니다. 다른 날짜의 운영 DB에 그대로 가져오지 마세요. 고정 DB는 테스트용으로 별도 사용합니다.
실행·설치 방법은 ../핵심산출물/README.md, 예약 작업 순서는 ../핵심산출물/scheduled-task-prompt.md를 참고하세요.
''',encoding='utf-8-sig')
files=[ROOT/'main.py',ROOT/'config.py',ROOT/'run_daily.bat']+list(ROOT.glob('requirements*.txt'))
for directory in ['carbon','tests']:
    files += [p for p in (ROOT/directory).rglob('*') if p.is_file() and not any(x in p.relative_to(ROOT).parts for x in ['__pycache__','data','reports','logs','work']) and p.suffix not in ['.pyc','.pyo']]
with ZipFile(OUT/'핵심산출물/source.zip','w',ZIP_DEFLATED) as z:
    for p in sorted(files): z.write(p,p.relative_to(ROOT).as_posix())

prompt=(ROOT/'docs/scheduled-task-prompt.md').read_text(encoding='utf-8')
lines=(ROOT/'logs/app.log').read_text(encoding='utf-8').splitlines()
start=next(i for i,l in enumerate(lines) if l.startswith('2026-11-13 15:01:53') and '실패한 항목' in l)
end=next(i for i,l in enumerate(lines) if l.startswith('2026-11-13 15:03:35') and '완료' in l)
tail=lines[start:end+1]
assert all(x in '\n'.join(tail) for x in ['신규 기사 총 5건','(150건)',"'applied': 150","'saved': True"])
(WORK/'log_excerpt.txt').write_text('\n'.join(tail)+'\n',encoding='utf-8')
def page(title,body,dark=False):
    return '<!doctype html><html lang="ko"><meta charset="utf-8"><title>'+title+'</title><style>body{margin:0;padding:28px;font-family:"Malgun Gothic",sans-serif;background:'+('#0b1220;color:#e2e8f0' if dark else '#fff;color:#182235')+'}h1{font-size:25px;margin:0 0 10px}.note{font-size:14px;color:#64748b;margin-bottom:20px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-family:'+('Consolas,"Malgun Gothic",monospace' if dark else '"Malgun Gothic",sans-serif')+';font-size:'+('17' if dark else '16')+'px;line-height:1.55;margin:0}b{color:#83e3bf}</style><h1>'+title+'</h1>'+body+'</html>'
(WORK/'prompt.html').write_text(page('Claude 앱 예약 작업 지시문','<div class="note">실제 docs/scheduled-task-prompt.md 원문 렌더링 · Claude 데스크톱 앱 화면 아님</div><pre>'+html.escape(prompt)+'</pre>'),encoding='utf-8')
(WORK/'log.html').write_text(page('중간 도구 실행 기록','<div class="note">실제 logs/app.log 연속 발췌 · 2026-11-13 15:01–15:03 · 로그 렌더링</div><pre>'+html.escape('\n\n'.join(tail))+'</pre>',True),encoding='utf-8')
(WORK/'baseline.json').write_text(json.dumps({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},indent=2),encoding='utf-8')
print('Prepared source archive, sample files and capture pages')

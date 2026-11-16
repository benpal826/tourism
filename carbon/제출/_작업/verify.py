from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib,json
from docx import Document
ROOT=Path(__file__).resolve().parents[2]; OUT=ROOT/'제출'
hashit=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
baseline=json.loads((OUT/'_작업/baseline.json').read_text())
baseline={k.replace('\\','/'):v for k,v in baseline.items()}
assert all(hashit(ROOT/k)==v for k,v in baseline.items()), 'Source changed'
for src,dst in {'reports/report_2026-11-13.html':'index.html','CLAUDE.md':'CLAUDE.md','README.md':'README.md','PRD.md':'PRD.md','run_daily.bat':'run_daily.bat','docs/scheduled-task-prompt.md':'scheduled-task-prompt.md'}.items():
 assert hashit(ROOT/src)==hashit(OUT/'핵심산출물'/dst)
with ZipFile(OUT/'핵심산출물/source.zip') as z:
 assert z.testzip() is None
 assert set(z.namelist())==set(baseline)
 for n in z.namelist(): assert hashlib.sha256(z.read(n)).hexdigest()==baseline[n]
 print('source.zip:',len(z.namelist()),'verified files')
for f in (OUT/'샘플데이터').iterdir():
 if f.name=='README.txt': continue
 src=ROOT/('tests/fixtures' if f.name.startswith('sample') else 'work')/f.name
 assert hashit(src)==hashit(f)
d=Document(OUT/'결과보고서.docx')
text='\n'.join(p.text for p in d.paragraphs)+'\n'+'\n'.join(c.text for t in d.tables for row in t.rows for c in row.cells)
assert '작성 팁' not in text and '붙여넣기' not in text
assert len(d.inline_shapes)==3
assert all(t in text for t in ['88.0%','533','55.7%','4.5만','SMTP','BOM','Codex','교체'])
with ZipFile(OUT/'결과보고서.docx') as z: assert z.testzip() is None
files=[p for p in OUT.rglob('*') if p.is_file() and '_작업' not in p.relative_to(OUT).parts and p.name!='최종제출물.zip']
with ZipFile(OUT/'최종제출물.zip','w',ZIP_DEFLATED) as z:
 for p in sorted(files): z.write(p,p.relative_to(OUT).as_posix())
with ZipFile(OUT/'최종제출물.zip') as z:
 assert z.testzip() is None
 assert len(z.namelist())==len(files)
print('Final submission:',len(files)+1,'files including final ZIP')
for p in sorted(files+[OUT/'최종제출물.zip']): print(p.relative_to(OUT).as_posix(),p.stat().st_size)

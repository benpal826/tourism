from pathlib import Path
from copy import deepcopy
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib, json
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'제출'
REF=Path(r'C:\Users\LJS\.claude\uploads\7032197a-b2b8-45d0-a8bf-8b7e9c4f9eac\bb8e1193-_____AI_Agent_______3.docx')
reference_hash=hashlib.sha256(REF.read_bytes()).hexdigest()
d=Document(REF)
original_headings=[p.text for p in d.paragraphs if p.text[:1] in '1234' and p.text]
original_sections=[s._sectPr.xml for s in d.sections]
p=d.paragraphs

(OUT/'_작업/artifact.md').write_text(f'''# Template contract
Reference: {REF}
SHA256: {reference_hash}
One Letter portrait section 21.59 x 27.94 cm; all margins 2.032 cm.
Title: Malgun Gothic 20 pt bold 1E3A8A; subtitle 10.5 pt 64748B.
Preserve all existing section/subsection heading strings, run formatting and paragraph properties.
Preserve the two-column identity table, one-cell content tables, existing fills, borders, margins and widths.
Editable slots: identity table values; summary table; three picture tables; three action-description paragraphs; reflection table; checklist checkbox markers.
Clone body paragraphs within content cells for expanded explanations; body 10 pt Malgun Gothic 1E293B, line spacing 1.15.
Name remains blank unless user provides it. Topic filled. Replace all instructional placeholders.
Five intentional pages: overview; start; tool log; result; reflections/checklist. Explicit breaks before sections 2, 2.2, 2.3 and 3 prevent picture splits.
Render evidence: canonical render_docx.py failed because soffice.exe absent. Word COM unavailable and native Word launch approval denied. Actual Word pagination unverified; preserve geometry and bound each page conservatively.
All template package parts other than document.xml, document relationships and Content_Types are preserve-only. New image parts permitted.
''',encoding='utf-8')

def write(p,text,size=10,bold=False):
    p.clear()
    r=p.add_run(text)
    r.font.name='맑은 고딕'; r._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'맑은 고딕')
    r.font.size=Pt(size); r.font.color.rgb=RGBColor.from_string('1E293B'); r.bold=bold
    p.paragraph_format.space_after=Pt(6)
    p.paragraph_format.line_spacing=1.15
    p.paragraph_format.keep_together=True
    return p

def fill(cell,paras):
    for el in list(cell._tc):
        if el.tag!=qn('w:tcPr'): cell._tc.remove(el)
    for text in paras: write(cell.add_paragraph(),text)

write(d.tables[0].cell(1,1).paragraphs[0],'탄소정책 뉴스 수집·분류·요약 AI Agent',10)
fill(d.tables[1].cell(0,0),[
'배출권거래제·CBAM 등 탄소 정책 뉴스와 정부·국회·EU 공식 문서를 매일 수집하고, 규칙 분류와 AI 분류·요약을 거쳐 HTML 리포트로 정리했다. 아침에 정책 흐름을 파악하고 팀에 보고할 근거를 찾는 것이 목적이다.',
'리포트 맨 위의 ‘오늘의 요약’은 결론 3~5줄, 보고할 것 최대 3건, 상위 5개 주제의 7일 흐름 그림으로 구성된다. 보고 항목에는 공식 문서 링크·정책 단계·국내 영향도·이유를 붙인다. AI 요약이 없으면 규칙 요약으로 자동 대체한다.',
'실행 구조: API 키 없이 Claude 앱 예약 작업 carbon-daily가 매일 08:00에 세션을 연다. 세션이 명령을 실행하고 입력 파일을 읽어 분류·요약 결과를 쓰며, Python 코드가 결과를 검증해 저장한다.',
'① run으로 수집 → ② ai-export classify → ③ Claude가 분류 JSON 작성 → ④ ai-import classify → ⑤ ai-export summary → ⑥ Claude가 요약 JSON 작성 → ⑦ ai-import summary → ⑧ report → ⑨ claude.ai 고정 페이지 갱신 순서로 동작한다. 고정 페이지는 휴대폰에서 열람한다.',
'검증 장치: 분류 결과의 허용 값과 id를 확인하고, 관련성·정책 단계·국내 영향도의 기존 규칙 판정을 덮어쓰지 않는다. 요약에서는 재료에 없는 숫자가 든 문장과 공식 근거 없는 보고 항목을 제거한다. 중간 단계가 실패해도 report를 실행하도록 지시했다.',
'2026-11-13 실제 실행: 신규 기사 5건(누적 약 290건), AI 분류 150건 반영(오류 0), 요약 저장 완료(결론 5개·보고 항목 3개·버린 항목 0개). 주제 태깅률은 무관 기사 제외 284건 중 250건으로 88.0%이며 목표 85%를 넘었다. AI 분류 전 QA 표본 기준은 55.7%로, 표본이 달라 동일 조건의 전후 비교로 보지는 않는다.',
'테스트 결과는 pytest 533개 통과이며 Playwright 화면 테스트를 포함한다. 이 수치는 프로젝트에서 확인한 결과이고, 제출물 작성 과정에서 테스트를 새로 실행한 결과는 아니다. 실행 환경은 Windows 11·PowerShell 5.1·Python 3.10이다.'
])

for index in [5,8,10,12]: p[index].paragraph_format.page_break_before=True
for index in [3,5,6,8,10,12,14]: p[index].paragraph_format.keep_with_next=True

for i,name in enumerate(['01_에이전트_시작.png','02_중간_도구실행.png','03_최종결과.png']):
    cell=d.tables[2+i].cell(0,0)
    fill(cell,[''])
    ip=cell.paragraphs[0]
    ip.paragraph_format.space_after=Pt(0)
    ip.paragraph_format.line_spacing=1
    ip.add_run().add_picture(str(OUT/'screenshots'/name),width=Inches(6.55))
    for pic in ip._p.xpath('.//wp:docPr'): pic.set('descr',['실제 예약 작업 지시문 파일 렌더링','실제 수집 및 AI 내보내기·가져오기 로그 렌더링','2026-11-13 HTML 리포트 오늘의 요약 화면'][i])
    trpr=cell._tc.getparent().get_or_add_trPr()
    trpr.append(OxmlElement('w:cantSplit'))

write(p[7], '• 동작 설명: 예약 작업에 넣는 실제 docs/scheduled-task-prompt.md를 단순한 웹 페이지로 렌더링한 화면이다. Claude 데스크톱 앱 자체의 스크린샷은 아니며, 사용자가 실제 앱 화면으로 교체할 수 있다. 지시문은 수집부터 고정 페이지 갱신까지의 9단계, 외부 기사 속 지시 무시, UTF-8 결과 파일 작성, 실패 시에도 리포트 생성이라는 실행 기준을 정한다.')
write(p[9], '• 동작 설명: logs/app.log의 2026-11-13 15:01~15:03 연속 구간을 원문 그대로 터미널 형태로 렌더링했다. Claude 데스크톱 앱 자체의 스크린샷이나 내부 사고 과정은 아니며, 사용자가 실제 앱의 도구 실행 화면으로 교체할 수 있다. 신규 5건 수집 뒤 분류 입력 150건을 내보냈고, applied 150·invalid 0·unknown_id 0·missing 0으로 반영했다. 요약은 saved True, 결론 5개, 보고 항목 3개, dropped 빈 목록으로 저장됐다. 로그의 ‘LLM 분류 건너뜀’은 API 인증이 없는 기존 단계이며, 이후 파일 기반 세션 분류는 정상 반영됐다. EU presscorner 실패도 실제 로그에 남아 있다.')
write(p[11], '• 동작 설명: reports/report_2026-11-13.html을 Playwright Chromium으로 열어 데스크톱 너비에서 캡처했다. 상단의 AI 요약과 공식 문서 링크·정책 단계·국내 영향도, 7일 흐름 그림을 함께 볼 수 있다. 보고 항목은 EU CBAM 국내 첫 검증기관 인정(확정), 배출권선물 도입 법령 연구 입찰 공고(추진), 교통·에너지·환경세법 시행령 개정안 입법예고(추진)다. 핵심산출물/index.html을 열면 링크와 필터를 직접 확인할 수 있다. 화면 상단 집계는 최근 7일 리포트 범위이므로 전체 누적 건수·당일 분류 반영 건수와 다를 수 있다.')

fill(d.tables[5].cell(0,0),[
'클라우드 세션에서 로컬 PC로 옮길 때 인수인계 문서와 CLAUDE.md가 맥락을 이어 주었다. 새 세션에 목표·구조·금지 사항·남은 일을 문서로 전달하니 앞선 결정을 다시 설명하는 부담이 줄었다.',
'큰 기능은 superpowers의 브레인스토밍 → 설계 문서 → 검토자 서브에이전트의 빌더 체크 → 구현 계획 → TDD 구현 → 최종 코드 리뷰 순서로 만들었다. 최종 리뷰는 PowerShell BOM으로 가져오기가 실패하는 문제와 재료 없는 날 근거 없는 요약이 저장되는 결함 2건을 찾았다. 테스트를 먼저 작성한 뒤 수정해 같은 문제가 다시 생기는지 확인할 수 있게 했다.',
'API 키 대신 구독 안에서 처리하도록 설계했다. claude -p는 이 PC에서 호출당 설정 로딩에 약 4.5만 토큰이 들어 제외하고, 예약 작업의 Claude 세션이 파일 내보내기·가져오기로 직접 분류·요약하도록 했다. 도구가 읽고 쓰는 파일을 남기니 결과를 확인하기도 쉬웠다.',
'예약 작업 첫 실행은 권한 승인 대기에서 멈췄다. 무인 실행을 하려면 명령 자체뿐 아니라 권한 모드와 실행 환경도 확인해야 한다는 점을 배웠다. 사용량 한도를 관리하려고 디자인 개선과 제출물 작성은 Codex(GPT)에 맡겨 여러 에이전트를 역할별로 나눠 썼다.',
'현업에서는 정책·ESG 담당자가 아침에 흐름을 훑고, 수출 담당자가 CBAM의 공식 근거를 열어 확인하는 용도로 사용할 수 있다. 추진과 확정을 구분하고 원문 링크를 남기는 방식이 보고 판단에 도움이 된다.',
'한계: 정부 사이트 이용약관은 아직 확인하지 못했고 실제 SMTP 알림 발송도 검증하지 못했다. 이날 EU 보도자료 수집은 실패했다. 제목과 제공 요약을 중심으로 판단하므로 중요한 내용은 공식 원문을 확인해야 한다.'
])
for i in [15,16,17]:
    for r in p[i].runs:
        if '[  ]' in r.text: r.text=r.text.replace('[  ]','[✓]')

# Preserve original parts that python-docx may reserialize despite no intentional edit.
target=OUT/'결과보고서.docx'
d.save(target)
with ZipFile(REF) as rz, ZipFile(target) as oz:
    final={n:oz.read(n) for n in oz.namelist()}
    mutable={'word/document.xml','word/_rels/document.xml.rels','[Content_Types].xml'}
    for n in rz.namelist():
        if n not in mutable: final[n]=rz.read(n)
with ZipFile(target,'w',ZIP_DEFLATED) as z:
    for n,data in final.items(): z.writestr(n,data)
check=Document(target)
assert len(check.inline_shapes)==3
assert [x.text for x in check.paragraphs if x.text[:1] in '1234' and x.text]==original_headings
assert [s._sectPr.xml for s in check.sections]==original_sections
assert hashlib.sha256(REF.read_bytes()).hexdigest()==reference_hash
print('Saved',target,'pictures',len(check.inline_shapes),'intentional pages',5)

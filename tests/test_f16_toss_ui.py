"""F16 자체검사: python -m tests.test_f16_toss_ui (화면 구조·색 확인. 모양은 모바일 화면에서 확인)."""
from src.common import ROOT

html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
# 1) 색: 배경·카드는 토스 느낌, 강조는 분홍, 네이버지도는 녹색(파랑 없음)
assert "--bg:#17171c" in html and "--card:#202027" in html and "--pink:#ff4d79" in html
assert ".map.nv,.item .bt a.nv{background:var(--naver);color:#fff}" in html and "--naver:#03c75a" in html
assert "blue" not in html and "3182f6" not in html
# 2) 위: 큰 제목 + '남은 N곳' 알약
assert "<header><b>데이트 스와이프</b><span id=\"count\"></span></header>" in html and "#count{background:var(--sub)" in html
# 3) 아래: 카드 위에 떠 있는 작은 알약(패스·되돌리기·저장 아이콘), 아래로 스크롤하면 숨김. 그 아래 탭바(스와이프·저장·패스, 개수)
nav, tab = html.index('<nav><button id="no" aria-label="패스"><svg'), html.index('<div class="tabbar">')
assert nav < tab and '<button id="yes" aria-label="저장"><svg' in html and "#yes{background:linear-gradient(135deg,#ff7a9a,var(--pink))" in html
assert "nav.hide{" in html and 'NAV.classList.toggle("hide",d>0' in html
for v in ("deck", "save", "pass"):
    assert f'data-v="{v}"' in html[tab:]
assert 'id="ns"' in html[tab:] and 'id="np"' in html[tab:]
assert 'document.querySelectorAll(".tabbar button")' in html and ".seg" not in html
# 4) 목록 화면은 버튼 줄 숨김(탭바만), 목록은 둥근 행
assert 'document.querySelector("nav").style.display=deck?"":"none"' in html
assert ".item{display:flex;gap:14px;background:var(--card);border-radius:20px" in html
print("F16 OK")

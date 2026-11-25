"""F15 자체검사: python -m tests.test_f15_photo_swipe (앱 코드 구조 확인. 실제 손가락 동작은 모바일 화면에서 확인)."""
from src.common import ROOT

html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
# 1) 사진은 가로로 나란히 놓인 슬라이드, 끌면 손가락 따라 이동하고 끝에서 멈춤
assert "<div class=track>" in html and ".slide{" in html
assert "translateX(calc(${-i*100}% + ${edge?dx/4:dx}px))" in html
assert "go(dx<0?i+1:i-1,false)" in html and "Math.max(0,Math.min(ph.length-1,n))" in html
# 2) 저장/패스 끌기는 사진 칸에서 시작하지 않음
assert 'e.target.closest("a,button,.photo")' in html
# 3) 지도는 맨 아래(버튼 다음), 끌리지 않고 탭하면 네이버지도
i_links, i_map = html.index("<div class=links>"), html.index("<a class=mapslot")
assert i_links < i_map
assert '보기"></a>`:""}</div>' in html  # 지도 다음에 바로 정보 칸이 끝남(맨 아래)
assert ".mapslot #map{pointer-events:none}" in html
print("F15 OK")

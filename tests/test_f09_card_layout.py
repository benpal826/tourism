"""F09 자체검사: python -m tests.test_f09_card_layout
정적 검사. 실제 스크롤·드래그·지도 이동은 localhost 모바일 화면에서 확인(progress.md 기록)."""
import re
from src.common import ROOT

html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
card_css = re.search(r"\.card\{[^}]*\}", html).group(0)
assert "overflow-y:auto" in card_css and "touch-action:pan-y" in card_css, "카드가 세로 스크롤 우선이어야 함"
assert ".photo{position:relative;aspect-ratio:4/3" in html, "사진은 4:3"
assert "<dl class=facts>" in html and "<div class=mapslot></div>" in html, "정보 격자·카드 안 지도 자리 필요"
assert html.index("<dl class=facts>") < html.index("<div class=mapslot></div>") < html.index("<div class=links>"), "순서: 정보 → 지도 → 버튼"
assert '<div hidden><div id="map"></div></div>' in html, "고정 지도 띠가 남아 있음"
assert "slot.appendChild(box)" in html, "지도를 지금 카드로 옮겨야 함"
assert "horiz=Math.abs(mx)>2*Math.abs(my)" in html and "Math.abs(dx)>110" in html, "가로가 확실할 때만 넘김"
assert "el.onpointercancel=reset" in html, "스크롤로 바뀌면 드래그 취소"
print("F09 OK")

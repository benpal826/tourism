"""F07 자체검사: python -m tests.test_f07_photo_fit (정적 검사. 실제 화면은 localhost 브라우저에서 확인)."""
from src.common import ROOT

html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
assert ".pic .fg{object-fit:contain}" in html, "사진을 자르지 않아야 함"
assert ".pic .bg{object-fit:cover;filter:blur(" in html, "흐린 배경 없음"
assert "<div class=slide>${k<2?imgTag(p):\"\"}</div>" in html and "s.innerHTML=imgTag(ph[k])" in html, "사진마다 흐린 배경과 함께(F15 슬라이드)"
assert "im.src=lo;bg.src=lo" in html, "로드 실패 시 썸네일로 바꿔야 함"
assert 'querySelector("img")' not in html, "옛 단일 img 처리 잔존"
print("F07 OK")

"""F03 자체검사: python -m tests.test_f03_naverlink
카드·저장/패스 목록 모두에 네이버지도 검색 링크가 있는지 정적 검사. 실제 화면은 localhost 브라우저에서 확인."""
from src.common import ROOT

html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
assert 'nvUrl=c=>"https://map.naver.com/p/search/"+encodeURIComponent' in html, "네이버지도 검색 주소 함수 없음"
assert html.count('href="${esc(nvUrl(c))}"') == 2, "카드·목록 두 곳에 네이버지도 버튼이 있어야 함"
assert html.count('href="${esc(c.map_url)}"') == 2, "카카오맵 버튼이 사라짐"
print("F03 OK")

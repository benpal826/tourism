"""F03 자체검사: python -m tests.test_f03_naverlink
지도 링크는 네이버지도 하나만(앱 카드·목록, report.md, 코스). 실제 화면은 localhost 브라우저에서 확인."""
from src.common import ROOT, naver_map_url

html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
assert 'nvUrl=c=>"https://map.naver.com/p/search/"+encodeURIComponent' in html, "네이버지도 검색 주소 함수 없음"
assert html.count('href="${esc(nvUrl(c))}"') == 2, "카드·목록 두 곳에 네이버지도 링크가 있어야 함"
assert "c.map_url" not in html and "카카오맵" not in html, "카카오맵 링크가 남아 있음"
for f in ("src/run.py", "src/course.py"):
    src = (ROOT / f).read_text(encoding="utf-8")
    assert "naver_map_url(" in src and "map_url']" not in src, f"{f} 의 지도 링크가 네이버가 아님"
assert naver_map_url("스타벅스 압구정", "압구정").endswith("%EC%8A%A4%ED%83%80%EB%B2%85%EC%8A%A4%20%EC%95%95%EA%B5%AC%EC%A0%95")  # 역명 중복 안 붙임
assert naver_map_url("향방", "신사").endswith("%ED%96%A5%EB%B0%A9%20%EC%8B%A0%EC%82%AC")
print("F03 OK")

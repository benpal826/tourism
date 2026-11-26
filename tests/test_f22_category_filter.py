"""F22 자체검사: python -m tests.test_f22_category_filter (앱 코드 구조 + notes missing 목록. 실제 드롭다운 동작은 모바일 화면에서 확인)."""
import json
from src import photos
from src.common import ROOT

html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
# 1) 헤더에 '남은 N곳' 바로 앞 종류 드롭다운, 전체 + 다섯 종류
assert '<select id="cat" aria-label="카드 종류 고르기"></select><span id="count">' in html
assert '["식당","음식점"],["카페","카페"],["술집","주점"],["팝업스토어","팝업"],["전시·축제·기타","행사"]' in html
# 2) 고르면 그 종류 카드만(남은 수·지도·스와이프 모두 deckCards 기준), 고른 값은 기억
assert "function deckCards(){return deckAll().filter(c=>!CAT||c.category===CAT)}" in html
assert 'CAT=e.target.value;SV("cat",CAT);render()' in html and 'let CAT=LS("cat")||""' in html
# 3) 남은 카드 없는 종류는 못 고름, 고른 종류를 다 보면 안내
assert 'a.some(c=>c.category===k)?"":" disabled"' in html and "이 종류는 다 봤어요" in html
# 4) 주간 갱신: 설명 없는 카드는 티어 상관없이 전부 목록에 오름
cards = json.loads((ROOT / "docs/cards.json").read_text(encoding="utf-8"))
assert photos.missing_cards() == [c["place_id"] for c in cards if not c.get("summary")]
print("F22 OK")

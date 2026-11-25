"""F17 자체검사: python -m tests.test_f17_text_card (외부 호출 없음)."""
import json
from src.common import ROOT

html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
# 1) 먹거리 카드 정보 칸은 업종·후기만, 팝업·전시는 그대로
assert '.filter(x=>x&&(c.tier!=="1"||["업종","후기"].includes(x[0])))' in html
assert 'const facts=c.tier==="1"?`<div class=meta>' in html and '.meta span{' in html  # 업종·후기 한 줄 칩
assert 'fetch(u,{cache:"no-cache"})' in html  # 폰 캐시에 옛 카드가 남지 않게
# 2) 설명 라벨에 메뉴·가격
assert "(메뉴|가격|맛|분위기|팁|추천)" in html
# 3) 설명 작성 형식(도구·규칙)에 메뉴·가격 줄
assert '"메뉴: ..."' in (ROOT / "src/photos.py").read_text(encoding="utf-8")
assert "메뉴: …\n가격: …" in (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
# 4) 지금 카드: 먹거리 설명 대부분에 메뉴 줄이 있고, 메뉴·가격 줄은 캐치프레이즈 바로 다음
food = [c for c in json.loads((ROOT / "docs/cards.json").read_text(encoding="utf-8")) if c.get("tier") == "1"]
with_menu = [c for c in food if "\n메뉴: " in c.get("summary", "")]
assert len(with_menu) >= len(food) * 0.8, (len(with_menu), len(food))
for c in with_menu:
    L = c["summary"].split("\n")
    assert L[1].startswith("메뉴: ") and not L[0].startswith(("메뉴", "가격")), c["place_id"]
# 5) 메뉴·맛·팁이 겹치지 않음: 메뉴 줄이 있는 곳의 팁에는 가격이 없음
import re
for c in with_menu:
    tip = [x for x in c["summary"].split("\n") if x.startswith("팁:")]
    assert not (tip and re.search(r"가성비|만원대|안주 \d", tip[0])), (c["place_id"], tip)
assert "맛=맛·식감 평가만" in (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
print("F17 OK")

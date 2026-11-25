"""F17 자체검사: python -m tests.test_f17_text_card (외부 호출 없음)."""
import json
from src.common import ROOT

html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
# 1) 먹거리 카드 정보 칸은 업종·후기만, 팝업·전시는 그대로
assert '.filter(x=>x&&(c.tier!=="1"||["업종","후기"].includes(x[0])))' in html
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
print("F17 OK")

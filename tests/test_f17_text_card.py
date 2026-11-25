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
# 6) 가격 발췌: '가게명 역 가격' 검색 결과 중 이 가게 글·광고 아님·가격 있는 것만
from src import photos
photos.naver_search = lambda kind, q, **k: {"items": [
    {"title": "하늘집 신사 메뉴 가격", "description": "김치찌개 9,000원 계란말이 1.2만원", "postdate": "20261120"},
    {"title": "하늘집 신사 협찬", "description": "김치찌개 9,000원", "postdate": "20261120"},
    {"title": "다른집 신사", "description": "라면 5,000원", "postdate": "20261120"},
    {"title": "하늘집 신사 후기", "description": "분위기 좋아요", "postdate": "20261120"}]} if q == "하늘집 신사 가격" else {}
photos.kakao_search = lambda *a, **k: (_ for _ in ()).throw(OSError("down"))  # 한쪽 실패는 건너뜀
got = photos.price_snips({"name": "하늘집", "station": "신사"})
assert len(got) == 1 and "9,000원" in got[0], got
# 7) 설명을 다 쓴 먹거리 카드에 가격 줄이 없으면 제외(설명 전 새 후보·한 줄 설명은 통과)
import tempfile
from src import rank
from src.common import load_config
cfg = load_config(); cfg["trend"]["min_reviews"] = 0
st = cfg["nearby"]["stations"][0]
base = {"tier": "1", "category": "식당", "station": st["name"], "lat": st["lat"], "lng": st["lng"], "reviews_total": "100", "menu_source": "curated"}
cands = {"a": {**base, "place_id": "a", "name": "가", "summary": "캐치\n메뉴: 국밥\n가격: 1만원"},
         "b": {**base, "place_id": "b", "name": "나", "summary": "캐치\n메뉴: 국밥\n맛: 진함"},
         "c": {**base, "place_id": "c", "name": "다"}, "d": {**base, "place_id": "d", "name": "라", "summary": "한 줄 설명"}}
ids = {x["place_id"] for x in rank.build_cards(cfg, cands, [], [], taste_path=tempfile.mktemp())}
assert ids == {"a", "c", "d"}, ids
print("F17 OK")

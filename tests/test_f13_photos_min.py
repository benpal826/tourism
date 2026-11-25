"""F13 자체검사: python -m tests.test_f13_photos_min (외부 호출 없음)."""
import json, tempfile
from pathlib import Path
from src import trend, photos

kd = lambda key, u, doc: (key, {"image_url": u, "thumbnail_url": "", "doc_url": doc})
cands = [kd("mood", "m1", "d1"), kd("food", "f1", "d1"), kd("food", "f2", "d2"), kd("mood", "m2", "d3"), kd("outside", "o1", "d4")]
trend.photo_candidates = lambda *a, **k: list(cands)
photos.naver_images = lambda a: [{"hi": "n1", "lo": ""}, {"hi": "n2", "lo": ""}]
allp = lambda r: [x.split("|")[0] for k in ("photo_food", "photo_mood", "photo_etc", "photo_outside") for x in r[k].split("§") if x != "-"]

# 1) 식당은 음식 사진 먼저, 카페는 분위기 사진 먼저 (8장 한도 안이면 전부)
r = trend.photos("집", "신사", [], "", "식당")
assert r["photo_food"].startswith("f1") and len(allp(r)) == 5, r
r = trend.photos("집", "신사", [], "", "카페")
assert r["photo_mood"].startswith("m1"), r

# 2) 4장 미만이면 네이버 이미지로 4장까지 채움
cands[:] = [kd("food", "f1", "d1"), kd("food", "f2", "d1")]
r = trend.photos("집", "신사", [], "", "식당")
assert len(allp(r)) == 4 and r["photo_etc"] == "n1|§n2|", r

# 3) 최대 8장, 한 글에서 최대 3장
cands[:] = [kd("food", f"f{i}", "same") for i in range(6)] + [kd("food", f"g{i}", f"d{i}") for i in range(9)]
r = trend.photos("집", "신사", [], "", "식당")
assert len(allp(r)) == 8 and sum(1 for x in allp(r) if x.startswith("f")) == 3, r

# 4) 카테고리별 상위 N 선별 대상(미선별만, redo 면 전부)
tmp = Path(tempfile.mkdtemp())
cards = [{"place_id": f"s{i}", "tier": "1", "category": "식당"} for i in range(3)] + \
        [{"place_id": f"c{i}", "tier": "1", "category": "카페"} for i in range(3)] + [{"place_id": "p", "tier": "2", "category": "팝업스토어"}]
(tmp / "docs").mkdir()
(tmp / "docs" / "cards.json").write_text(json.dumps(cards), encoding="utf-8")
photos.ROOT = tmp
photos.latest_cands = lambda p: {"s0": {"photo_source": "curated"}}
assert photos.pending_cards(2, percat=True) == ["s1", "c0", "c1"], photos.pending_cards(2, percat=True)
assert photos.pending_cards(2, redo=True, percat=True) == ["s0", "s1", "c0", "c1"]
print("F13 OK")

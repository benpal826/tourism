"""F21 자체검사: python -m tests.test_f21_station_cards (외부 호출 없음)."""
import tempfile
from src import rank
from src.common import load_config

cfg = load_config()
assert cfg["rank"]["cards_per_station_category"] == 10 and "cards_per_category" not in cfg["rank"]
cfg["trend"]["min_reviews"] = 0
cfg["rank"]["cards_per_station_category"] = 2
st = cfg["nearby"]["stations"]
cands = {}
for si, s in enumerate(st[:2]):            # 두 역 × 식당 4곳 + 첫 역 카페 1곳
    for i in range(4):
        pid = f"k{si}{i}"
        cands[pid] = {"place_id": pid, "tier": "1", "category": "식당", "name": f"집{si}{i}", "station": s["name"],
                      "lat": s["lat"], "lng": s["lng"], "reviews_total": str(1000 - 100 * i), "menu_source": "curated"}
cands["c0"] = {**cands["k00"], "place_id": "c0", "category": "카페", "name": "카페"}
cards = rank.build_cards(cfg, cands, [], [], taste_path=tempfile.mktemp())
ids = {c["place_id"] for c in cards}
assert ids == {"k00", "k01", "k10", "k11", "c0"}, ids  # 역마다 식당 상위 2곳씩, 카페는 따로
print("F21 OK")

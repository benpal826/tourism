"""F12 자체검사: python -m tests.test_f12_rank (외부 호출 없음)."""
from datetime import date
from src import trend, rank
from src.common import load_config

cfg = load_config()
today = date.today().strftime("%Y%m%d")
P = lambda t: {"title": t, "description": "", "postdate": today, "url": t, "src": "kakao"}

# 1) 신호 비율: 이 가게 글 4개 중 맛 2, 분위기 1 (광고 글은 분모 제외)
posts = [P("하늘집 신사 존맛 재방문"), P("하늘집 신사역 웨이팅 김치찌개"), P("하늘집 신사 루프탑 뷰"), P("하늘집 신사 점심"),
         P("하늘집 신사 협찬 맛있어요"), P("다른집 신사 맛있")]
res = trend.analyze(cfg, {"kakao": 6}, posts, "하늘집", "신사")
assert (res["taste_share"], res["vibe_share"]) == (50, 25), res

# 2) 점수: 식당은 맛, 카페·술집은 분위기 비율을 씀
base = {"tier": "1", "place_id": "x", "reviews_total": "100", "reviews_30d": "5", "rec_mentions": "4"}
food_taste = rank.score({**base, "category": "식당", "taste_share": "80", "vibe_share": "0"}, None, set(), {})
food_vibe = rank.score({**base, "category": "식당", "taste_share": "0", "vibe_share": "80"}, None, set(), {})
bar_vibe = rank.score({**base, "category": "술집", "taste_share": "0", "vibe_share": "80"}, None, set(), {})
assert food_taste > food_vibe and bar_vibe == food_taste, (food_taste, food_vibe, bar_vibe)

# 3) 카드: 카테고리별 상위 k 곳, 추천글 언급 0 은 제외, 2순위는 그대로
cfg["rank"]["cards_per_category"] = 2
cfg["trend"]["min_reviews"] = 0
st = cfg["nearby"]["stations"][0]
mk = lambda i, cat, rec, rev: (f"k{i}", {"place_id": f"k{i}", "tier": "1", "category": cat, "name": f"집{i}", "station": st["name"],
                                       "lat": st["lat"], "lng": st["lng"], "rec_mentions": str(rec), "reviews_total": str(rev)})
cands = dict([mk(1, "식당", 5, 900), mk(2, "식당", 3, 500), mk(3, "식당", 1, 100), mk(4, "식당", 0, 9999), mk(5, "카페", 2, 50)])
cands["p1"] = {"place_id": "p1", "tier": "2", "category": "팝업스토어", "name": "팝업", "station": st["name"],
               "popup_source": "curated", "period_end": "2099-12-31"}
cands["p2"] = {"place_id": "p2", "tier": "2", "category": "팝업스토어", "name": "굿즈 팝업", "station": st["name"]}
cards = rank.build_cards(cfg, cands, [], [], taste_path=__import__("tempfile").mktemp())
ids = [c["place_id"] for c in cards]
assert set(ids) == {"k1", "k2", "k5", "p1"}, ids  # k3 는 식당 3위, k4 는 언급 0, p2 는 확인 안 된 팝업(F23)

# 4) 폐업(closed=1)은 제외, 옛 후기 수라도 기간으로는 빼지 않음
cands["k1"]["closed"] = "1"
men = [{"date": "2026-01-01", "place_id": "k2", "field": "reviews_total", "value": "500", "source": "kakao"},
       {"date": "2026-11-25", "place_id": "k2", "field": "rec_mentions", "value": "3", "source": "discover"}]
ids = [c["place_id"] for c in rank.build_cards(cfg, cands, men, [], taste_path=__import__("tempfile").mktemp())]
assert "k1" not in ids and "k2" in ids, ids

# 5) 폐업 확인: 같은 id 가 검색되면 0, 없으면 1, 검색 실패면 행 없음
from src import collect
res = {"하늘집": [{"id": "1"}], "구름집": [{"id": "999"}]}
def fake_http(url, params, h):
    if params["query"] == "에러집":
        raise OSError("down")
    return {"documents": res[params["query"]]}
collect.http_json = fake_http
got = {r["place_id"]: r["value"] for r in collect.check_open(
    {"k1": {"name": "하늘집", "lat": 1, "lng": 1}, "k2": {"name": "구름집", "lat": 1, "lng": 1}, "k3": {"name": "에러집", "lat": 1, "lng": 1}})}
assert got == {"k1": "0", "k2": "1"}, got
print("F12 OK")

"""F11 자체검사: python -m tests.test_f11_discover (외부 호출 없음)."""
from src import discover, collect
from src.common import load_config

cfg = load_config()
cfg["nearby"]["stations"] = [{"name": "신사", "lat": 37.5163, "lng": 127.0203}]
cfg["discover"]["rec_queries"] = {"술집": ["{st} 칵테일바"], "카페": ["{st} 분위기 좋은 카페"]}

# 1) 업종명으로 카테고리: 음식점>술집 은 술집, 카페는 카페
assert collect.kakao_cat({"category_group_code": "FD6", "category_name": "음식점 > 술집 > 칵테일바"}, "식당") == "술집"
assert collect.kakao_cat({"category_group_code": "CE7", "category_name": "음식점 > 카페"}, "식당") == "카페"
assert collect.kakao_cat({"category_group_code": "FD6", "category_name": "음식점 > 한식"}, "술집") == "식당"
assert collect.kakao_cat({"category_group_code": "FD6", "category_name": "음식점 > 간식 > 제과,베이커리"}, "식당") == "카페"

# 2) 추천글 언급 수: 이 가게 글로 확인된 글만, 검색어의 {st} 치환
seen_q = []
def fake_rec(q):
    seen_q.append(q)
    if "칵테일바" in q:
        return [{"title": "신사 칵테일바 추천 바틀앤 신사역", "description": "", "url": "u1"},
                {"title": "신사역 바틀앤 분위기", "description": "", "url": "u2"},
                {"title": "신사 바틀앤드 다른 집", "description": "", "url": "u3"}]
    return [{"title": "신사 카페 투어", "description": "", "url": "u4"}]
discover.rec_posts = fake_rec
cands = {"k1": {"tier": "1", "station": "신사", "category": "술집", "name": "바틀앤", "address": ""},
         "k2": {"tier": "1", "station": "신사", "category": "카페", "name": "모모카페", "address": ""},
         "p1": {"tier": "2", "station": "신사", "category": "팝업스토어", "name": "팝업"}}
rows = discover.run(cfg, cands)
got = {r["place_id"]: r["value"] for r in rows}
assert got == {"k1": 2, "k2": 0}, got  # '바틀앤드'는 다른 가게
assert set(seen_q) == {"신사 칵테일바", "신사 분위기 좋은 카페"}, seen_q

# 2-1) 검색 실패한 역·카테고리는 행을 남기지 않음(0 으로 덮지 않음)
def fail_bar(q):
    if "칵테일바" in q:
        raise RuntimeError("down")
    return fake_rec(q)
discover.rec_posts = fail_bar
assert {r["place_id"] for r in discover.run(cfg, cands)} == {"k2"}

# 3) 보강 대상: 역·카테고리별 상위 k (0 제외), 2·3순위는 전부
cfg["discover"]["enrich_per_station"] = 1
cands["k3"] = {"tier": "1", "station": "신사", "category": "술집", "name": "다른바", "address": ""}
men = [{"date": "2026-11-25", "place_id": "k1", "field": "rec_mentions", "value": "2", "source": "discover"},
       {"date": "2026-11-25", "place_id": "k3", "field": "rec_mentions", "value": "1", "source": "discover"},
       {"date": "2026-11-25", "place_id": "k2", "field": "rec_mentions", "value": "0", "source": "discover"}]
assert set(discover.pick(cfg, cands, men)) == {"k1", "p1"}, set(discover.pick(cfg, cands, men))
print("F11 OK")

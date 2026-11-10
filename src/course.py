"""저장한 곳으로 코스: python -m src.course 신사 저녁  (먹거리→카페→술집/전시 순, 가까운 순 동선)"""
import sys
from .common import *
from .run import latest_cands

SLOTS = {"저녁": ["식당", "카페", "술집"], "점심": ["식당", "카페", "전시·축제·기타"], "오후": ["카페", "전시·축제·기타", "식당"],
         "밤": ["술집", "카페"], "낮": ["식당", "카페", "전시·축제·기타"]}


def main():
    station = sys.argv[1] if len(sys.argv) > 1 else None
    slot = sys.argv[2] if len(sys.argv) > 2 else "저녁"
    cands = latest_cands(DATA / "candidates.csv")
    places = read_rows(DATA / "places.csv")
    saved = {r["place_id"] for r in places if r["field"] == "swipe" and r["value"] == "save"}
    scores = {p: float(s[-1][1]) for p, s in series(places, "score").items()}
    pool = [cands[p] for p in saved if p in cands and (not station or cands[p].get("station") == station)]
    if not pool:
        print(f"요약: {station or '전체'}에 저장된 곳이 없어 코스를 못 짰습니다. 먼저 스와이프로 저장하세요.")
        return
    order = SLOTS.get(slot, SLOTS["저녁"])
    route, used = [], set()
    for cat in order:
        opts = [a for a in pool if a["category"] == cat and a["place_id"] not in used]
        if not opts:
            continue
        if route:  # 직전 장소에서 가까운 곳 우선, 점수 높으면 가산
            last = route[-1]
            key = lambda a: haversine(float(last["lat"]), float(last["lng"]), float(a["lat"]), float(a["lng"])) - scores.get(a["place_id"], 3) * 50
        else:
            key = lambda a: -scores.get(a["place_id"], 3)
        pick = min(opts, key=key)
        route.append(pick)
        used.add(pick["place_id"])
    print(f"**요약: {station or '전체'} {slot} 코스 {len(route)}곳 — " + " → ".join(a["name"] for a in route) + "**\n")
    for i, a in enumerate(route, 1):
        walk = ""
        if i > 1:
            p = route[i - 2]
            walk = f" (이전에서 도보 약 {int(haversine(float(p['lat']), float(p['lng']), float(a['lat']), float(a['lng'])) / 70)}분)"
        print(f"{i}. {a['name']} [{a['category']}]{walk} — [지도]({a['map_url']})")


if __name__ == "__main__":
    main()

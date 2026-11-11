"""급상승 / 취향(taste.md) / 점수화 / 카드 생성."""
from collections import Counter
from .common import *

ACTIONS = ("swipe", "score", "review")


def weekly_growth(mentions):
    """주간 증가량 = 최근 스냅샷 reviews_total - 약 7일 전(그 이전 중 가장 가까운) 스냅샷."""
    out = {}
    for pid, s in series(mentions, "reviews_total").items():
        if len(s) < 2:
            out[pid] = None
            continue
        last_d, last_v = s[-1]
        target = date.fromisoformat(last_d).toordinal() - 7
        prev = min(s[:-1], key=lambda x: abs(date.fromisoformat(x[0]).toordinal() - target))
        out[pid] = int(last_v - prev[1])
    return out


def seen_ids(places):
    return {r["place_id"] for r in places if r["field"] == "swipe"}


def build_taste(cands, places):
    """저장/패스 이력 → 카테고리·역 선호 가중치와 taste.md."""
    swipes = {r["place_id"]: r["value"] for r in sorted(places, key=lambda r: r["date"]) if r["field"] == "swipe"}
    scores = {}
    for r in places:
        if r["field"] == "score":
            try:
                scores[r["place_id"]] = float(r["value"])
            except ValueError:
                pass
    w = {}
    for pid, v in swipes.items():
        a = cands.get(pid, {})
        delta = 1.0 if v == "save" else -0.5
        delta += (scores.get(pid, 3) - 3) * 0.5 if pid in scores else 0
        for key in (("category", a.get("category")), ("station", a.get("station")), ("vibe", a.get("vibe"))):
            if key[1]:
                w[key] = w.get(key, 0) + delta
    saved = [p for p, v in swipes.items() if v == "save"]
    lines = [f"# 취향 요약\n", f"> 저장 {len(saved)}곳 · 패스 {len(swipes) - len(saved)}곳 기준 ({date.today().isoformat()}). 자동 생성 파일.\n"]
    if not swipes:
        lines.append("아직 스와이프 이력이 없습니다.")
    for kind, title in (("category", "카테고리"), ("station", "역"), ("vibe", "분위기")):
        items = sorted(((k[1], v) for k, v in w.items() if k[0] == kind), key=lambda x: -x[1])
        if items:
            lines.append(f"\n## 선호 {title}\n" + "\n".join(f"- {n}: {v:+.1f}" for n, v in items[:5]))
    (ROOT / ("out/sample/taste.md" if any(r.get("source") == "sample" for r in places[:1]) else "taste.md")).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return w


def score(a, growth, surge_set, taste):
    s = 10 - 3 * (int(a.get("tier", 3)) - 1)           # 카테고리 우선순위
    s += min(float(a.get("reviews_30d", 0)) / 20, 5)    # 요즘 후기
    s += min(max(growth or 0, 0) / 10, 5)               # 주간 증가
    s += 3 if a["place_id"] in surge_set else 0
    for key in (("category", a.get("category")), ("station", a.get("station")), ("vibe", a.get("vibe"))):
        s += taste.get(key, 0)
    s -= float(a.get("distance_m", 0)) / 1000
    return round(s, 2)


def build_cards(cfg, cands, mentions, places):
    growth = weekly_growth(mentions)
    m_latest = latest(mentions)
    ranked_growth = sorted((p for p, g in growth.items() if g and g > 0), key=lambda p: -growth[p])
    surge = set(ranked_growth[: cfg["trend"]["surge_top_n"]])
    taste = build_taste(cands, places)
    seen = seen_ids(places)
    today = date.today().isoformat()
    stations = {st["name"]: st for st in cfg["nearby"]["stations"]}
    cards = []
    for pid, a in cands.items():
        if pid in seen:
            continue
        end = a.get("period_end")
        if end and end < today:
            continue
        c = {"place_id": pid, **a, **m_latest.get(pid, {})}
        if c.get("tier") == "1" and float(c.get("reviews_total", 0)) < cfg["trend"]["min_reviews"]:
            continue  # 후기 수가 너무 적은 곳 제외 (카카오맵 평점은 공식 API에 없어 후기 수로 대체)
        if c.get("menu_source") != "curated" and int(c.get("menu_mentions") or 0) < 2:
            for k in ("menu", "price", "price_band", "menu_mentions"):  # 자동추출은 2회 이상 확인된 것만
                c.pop(k, None)
        if not c.get("lat") and c.get("station") in stations:  # 좌표 없는 팝업은 역 위치로 대략 표시
            st = stations[c["station"]]
            c["lat"], c["lng"], c["approx"] = st["lat"], st["lng"], True
        c["weekly_growth"] = growth.get(pid)
        c["surge"] = pid in surge
        c["rank_score"] = score(c, growth.get(pid), surge, taste)
        cards.append(c)
    cards.sort(key=lambda c: -c["rank_score"])
    return cards

"""팝업 정리(주간 갱신 때 Claude 가 직접).
  python -m src.popups todo         역별 최근 팝업 글 → out/popups/todo.json + 화면(Claude 가 읽고 정리)
  python -m src.popups import FILE  Claude 가 정리한 팝업 목록 → 장소 좌표 확인 → candidates.csv → 카드 다시 만듦

FILE 형식: [{"name": "디올 뷰티 홀리데이 팝업", "venue": "신세계백화점 강남점", "address": "서울 서초구 신반포로 176",
            "start": "2026-11-20", "end": "2026-12-01", "summary": "캐치프레이즈\n기간: …\n장소: …\n볼거리: …\n팁: …",
            "link": "출처 글 주소"}]
글에서 확인되는 것만. 종료일·장소를 모르면 넣지 않는다(카드에도 안 나감).
"""
import json, sys
from datetime import date, timedelta
from .common import *
from .collect import POPUP_JUNK, attrs, clean, hid, place_url

OUT = ROOT / "out" / "popups"


def todo():
    from .collect import popup_posts
    cfg = load_config()
    fresh = (date.today() - timedelta(days=45)).isoformat()
    seen, keep = set(), []
    for p in popup_posts(cfg):
        t, d = clean(p["title"]), clean(p["description"])
        if p["link"] in seen or "팝업" not in t + d or any(j in t for j in POPUP_JUNK) or (p["_dt"] and p["_dt"] < fresh):
            continue
        seen.add(p["link"])
        keep.append({"station": p["_station"], "date": p["_dt"], "title": t, "text": d[:220], "link": p["link"]})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "todo.json").write_text(json.dumps(keep, ensure_ascii=False, indent=1), encoding="utf-8")
    for k in keep:
        print(f"[{k['station']}] {k['date']} {k['title']} — {k['text']} ({k['link']})")
    print(f"요약: 최근 팝업 글 {len(keep)}개. 팝업마다 name·venue·address·start·end·summary·link JSON 목록으로 import 하세요.")


def locate(cfg, venue, address=""):
    """장소명(없으면 주소)을 카카오 장소 검색 → (lat, lng, 주소, 장소 링크). 못 찾으면 None."""
    h = {"Authorization": "KakaoAK " + env("KAKAO_REST_KEY")}
    sts = cfg["nearby"]["stations"]  # 수집 역 가운데 기준 10km 안에서 찾음(다른 지역 동명 장소 방지)
    near = {"y": sum(s["lat"] for s in sts) / len(sts), "x": sum(s["lng"] for s in sts) / len(sts), "radius": 10000}
    for q in filter(None, (venue, address)):
        docs = http_json("https://dapi.kakao.com/v2/local/search/keyword.json", {"query": q, "size": 1, **near}, h).get("documents", [])
        if docs:
            d = docs[0]
            return float(d["y"]), float(d["x"]), d.get("road_address_name") or d.get("address_name", ""), place_url(d["id"])
    if address:  # 장소명이 지도에 없으면 주소로
        docs = http_json("https://dapi.kakao.com/v2/local/search/address.json", {"query": address, "size": 1}, h).get("documents", [])
        if docs:
            d = docs[0]
            return float(d["y"]), float(d["x"]), address, ""
    return None


def check(cfg, p, today, where):
    """팝업 하나를 카드에 올릴 수 있는지. (attrs 행, None) 또는 (None, 건너뛴 이유)."""
    name, venue, end = (p.get(k, "").strip() for k in ("name", "venue", "end"))
    if not (name and venue and end):
        return None, "이름·장소·종료일 중 빠진 것"
    try:
        start = date.fromisoformat(p["start"]).isoformat() if p.get("start") else ""
        end = date.fromisoformat(end).isoformat()
    except ValueError:
        return None, "날짜 형식(YYYY-MM-DD)"
    if end < today:
        return None, "이미 끝남"
    loc = where(cfg, venue, p.get("address", ""))
    if not loc:
        return None, "장소를 지도에서 못 찾음"
    lat, lng, addr, link = loc
    st, dist = nearest_station(cfg, lat, lng)
    if dist > cfg["nearby"]["culture_radius_m"]:
        return None, f"역에서 멀음({st}역 {dist}m)"
    pid = hid("p", name + "|" + venue)
    return attrs(pid, "popup-curated", name=name, category="팝업스토어", tier=2, popup_source="curated", venue=venue,
                 station=st, distance_m=dist, lat=lat, lng=lng, address=addr or p.get("address", ""), map_url=link,
                 period_start=start, period_end=end, summary=p.get("summary", "").strip(),
                 source_link=p.get("link", "")), None


def import_file(path, where=locate, data=DATA, rebuild=True):
    from . import trend
    cfg, today = load_config(), date.today().isoformat()
    rows, ok = [], 0
    for p in json.loads(Path(path).read_text(encoding="utf-8")):
        r, why = check(cfg, p, today, where)
        if why:
            print(f"건너뜀: {p.get('name', '?')} — {why}")
            continue
        if rebuild:  # 사진: 팝업 이름+장소로 이미지 검색(실데이터만)
            hi, lo = trend.thumb(p["name"], p["venue"])
            r += attrs(r[0]["place_id"], "kakao-image", thumb=hi, thumb_lo=lo)
        rows += [x for x in r if x["value"] not in ("", None)]
        ok += 1
    n = append_rows(Path(data) / "candidates.csv", rows)
    if rebuild:
        from .run import write_outputs
        write_outputs(cfg, False, DATA / "candidates.csv", DATA / "mentions.csv", DATA / "places.csv")
    print(f"요약: 팝업 {ok}곳 반영({n}행 추가){', 카드 다시 만듦' if rebuild else ''}.")


if __name__ == "__main__":
    if sys.argv[1:2] == ["todo"]:
        todo()
    elif len(sys.argv) > 2 and sys.argv[1] == "import":
        import_file(sys.argv[2])
    else:
        print(__doc__)

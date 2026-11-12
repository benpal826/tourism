"""공용: 설정, 단일 스키마 CSV(세로형 누적), HTTP, 거리."""
import csv, json, math, os, urllib.parse, urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SCHEMA = ["date", "place_id", "field", "value", "source"]  # 모든 CSV 공통


def load_config():
    import yaml
    return yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def append_rows(path, rows):
    """세로형 누적. 빈값은 skip. 같은 (date,place_id,field,value) 중복도 skip."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    seen = {(r["date"], r["place_id"], r["field"], r["value"]) for r in read_rows(path)}
    new = []
    for r in rows:
        v = r.get("value")
        if v is None or str(v).strip() == "":
            continue
        r = {k: r.get(k, "") for k in SCHEMA}
        r["value"] = str(v).strip()
        r["date"] = r["date"] or date.today().isoformat()
        key = (r["date"], r["place_id"], r["field"], r["value"])
        if key in seen:
            continue
        seen.add(key)
        new.append(r)
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=SCHEMA)
        if write_header:
            w.writeheader()
        w.writerows(new)
    return len(new)


def read_rows(path):
    path = Path(path)
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def latest(rows):
    """{place_id: {field: value}} — 같은 필드는 가장 최근 값."""
    out = {}
    for r in sorted(rows, key=lambda r: r["date"]):
        out.setdefault(r["place_id"], {})[r["field"]] = r["value"]
    return out


def series(rows, field):
    """{place_id: [(date, float)]} 날짜순."""
    out = {}
    for r in sorted(rows, key=lambda r: r["date"]):
        if r["field"] == field:
            try:
                v = float(r["value"])
            except ValueError:
                continue
            if math.isfinite(v):  # nan/inf 는 버림(카드 JSON 손상 방지)
                out.setdefault(r["place_id"], []).append((r["date"], v))
    return out


def haversine(lat1, lng1, lat2, lng2):
    R = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def nearest_station(cfg, lat, lng):
    best = min(cfg["nearby"]["stations"], key=lambda s: haversine(lat, lng, s["lat"], s["lng"]))
    return best["name"], int(haversine(lat, lng, best["lat"], best["lng"]))


def http_json(url, params=None, headers=None):
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def kakao_search(kind, query, **params):
    """다음 검색(blog/web/image). 같은 카카오 REST 키 사용."""
    h = {"Authorization": "KakaoAK " + env("KAKAO_REST_KEY")}
    return http_json(f"https://dapi.kakao.com/v2/search/{kind}", {"query": query, **params}, h)


def env(name):
    return os.environ.get(name, "").strip()


def have_keys():
    return {
        "kakao": bool(env("KAKAO_REST_KEY")),
        "seoul": bool(env("SEOUL_OPEN_KEY")),
    }


def in_scope(cfg, a):
    """현재 config 의 역·반경 안에 있는 후보인지. 지역을 바꾸면 누적 CSV 의 이전 지역 후보는 제외된다."""
    st = {s["name"]: s for s in cfg["nearby"]["stations"]}
    name = a.get("station")
    if name not in st:
        return False
    limit = cfg["nearby"]["culture_radius_m"] if str(a.get("tier")) == "3" else cfg["nearby"]["radius_m"]
    try:
        d = haversine(float(a["lat"]), float(a["lng"]), st[name]["lat"], st[name]["lng"])
    except (KeyError, ValueError, TypeError):
        try:
            d = float(a["distance_m"])  # 좌표 없으면 저장된 거리
        except (KeyError, ValueError, TypeError):
            return True  # 좌표도 거리도 없는 팝업(역 인근 표기)은 역 기준만 확인
    return d <= limit

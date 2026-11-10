"""후보 수집: 카카오(먹거리) / 카카오 검색(팝업) / 서울 열린데이터(전시·축제). 키 없으면 sample/ 사용."""
import hashlib, html, json, re
from datetime import timedelta
from .common import *

TAG = re.compile(r"<[^>]+>")
clean = lambda s: html.unescape(TAG.sub("", s or "")).strip()
hid = lambda p, s: p + hashlib.md5(s.encode()).hexdigest()[:10]
map_url = lambda name, area="": "https://map.kakao.com/link/search/" + urllib.parse.quote(f"{name} {area}".strip())
place_url = lambda kid: f"https://place.map.kakao.com/{kid}"


def attrs(pid, src, **kw):
    return [{"place_id": pid, "field": k, "value": v, "source": src} for k, v in kw.items()]


def sample(name):
    return json.loads((ROOT / "sample" / name).read_text(encoding="utf-8"))


# ---- 1순위: 카카오 로컬 ----
def collect_food(cfg, use_sample):
    rows = []
    if use_sample:
        items = sample("kakao.json")
    else:
        items = []
        n = cfg["limits"]["places_per_station_per_category"]
        h = {"Authorization": "KakaoAK " + env("KAKAO_REST_KEY")}
        for st in cfg["nearby"]["stations"]:
            for cat in cfg["categories"]:
                if cat["priority"] != 1:
                    continue
                params = {"x": st["lng"], "y": st["lat"], "radius": cfg["nearby"]["radius_m"],
                          "size": min(n, 15), "sort": "distance"}
                if "kakao_code" in cat:
                    url = "https://dapi.kakao.com/v2/local/search/category.json"
                    params["category_group_code"] = cat["kakao_code"]
                else:
                    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
                    params["query"] = st["name"] + "역 " + cat["kakao_query"]
                for d in http_json(url, params, h).get("documents", []):
                    d["_cat"] = cat["label"]
                    items.append(d)
    for d in items:
        lat, lng = float(d["y"]), float(d["x"])
        stn, dist = nearest_station(cfg, lat, lng)
        if dist > cfg["nearby"]["radius_m"] * 1.2:
            continue
        pid = "k" + str(d["id"])
        rows += attrs(pid, "kakao", name=d["place_name"], category=d["_cat"], lat=lat, lng=lng,
                      address=d.get("road_address_name") or d.get("address_name"), station=stn,
                      distance_m=dist, map_url=place_url(d["id"]), tier=1,
                      kind=" · ".join(x.strip() for x in d.get("category_name", "").split(">")[1:3]))
    return rows


# ---- 2순위: 팝업 (다음 블로그/웹 검색, 최신순) ----
POPUP_NAME = re.compile(r"([가-힣A-Za-z0-9&·]{2,12})\s*팝업(?:스토어)?")
POPUP_GENERIC = {"서울", "강남", "신사", "압구정", "성수", "카페", "크리스마스", "체험형", "홍보", "논란", "기념", "대구", "부산", "무료", "전용", "신세계", "현대", "백화점", "신규", "오픈", "이색", "인기", "핫플", "한정"}
POPUP_JUNK = ("임대", "매물", "맛집", "나무위키", "사무실", "상가", "건물", "권리금", "채용", "창업", "추천", "순위", "총정리", "정리", "베스트", "BEST", "코스", "비교")
DATE_RE = re.compile(r"(\d{1,2})[./월]\s*(\d{1,2})일?\s*[~\-–부터]+\s*(?:(\d{1,2})[./월]\s*)?(\d{1,2})")


def parse_period(text, year):
    m = DATE_RE.search(text)
    if not m:
        return "", ""
    m1, d1, m2, d2 = m.group(1), m.group(2), m.group(3) or m.group(1), m.group(4)
    try:
        return f"{year}-{int(m1):02d}-{int(d1):02d}", f"{year}-{int(m2):02d}-{int(d2):02d}"
    except ValueError:
        return "", ""


def collect_popup(cfg, use_sample):
    rows, posts = [], []
    if use_sample:
        posts = sample("popup_posts.json")
    else:
        for st in cfg["nearby"]["stations"]:
            for kind in ("blog", "web"):
                j = kakao_search(kind, f"{st['name']}역 팝업스토어", sort="recency", size=30)
                for d in j.get("documents", []):
                    posts.append({"title": d["title"], "description": d["contents"], "link": d["url"],
                                  "_station": st["name"], "_dt": d.get("datetime", "")[:10]})
    seen = set()
    fresh = (date.today() - timedelta(days=45)).isoformat()
    for it in posts:
        title, desc = clean(it["title"]), clean(it.get("description", ""))
        if "팝업" not in title or any(j in title for j in POPUP_JUNK):
            continue  # 제목에 팝업이 없거나 부동산·순위·정리글이면 제외
        if it.get("_dt") and it["_dt"] < fresh:
            continue  # 오래된 글 제외 (샘플엔 날짜 없음)
        m = next((m for m in POPUP_NAME.finditer(title) if m.group(1) not in POPUP_GENERIC), None)
        if not m:
            continue
        name = m.group(1) + " 팝업"
        if name in seen:
            continue
        seen.add(name)
        start, end = parse_period(title + " " + desc, date.today().year)
        if end and end < date.today().isoformat():
            continue  # 종료된 팝업 제외
        pid = hid("p", name)
        rows += attrs(pid, "kakao-popup", name=name, category="팝업스토어", station=it["_station"],
                      period_start=start, period_end=end, map_url=map_url(name, it["_station"]),
                      address=it["_station"] + "역 인근", source_link=it.get("link", ""), tier=2)
    return rows


# ---- 3순위: 서울 열린데이터광장 문화행사 ----
def collect_culture(cfg, use_sample):
    rows = []
    if use_sample:
        items = sample("seoul_culture.json")
    else:
        j = http_json(f"http://openapi.seoul.go.kr:8088/{env('SEOUL_OPEN_KEY')}/json/culturalEventInfo/1/1000/")
        items = j.get("culturalEventInfo", {}).get("row", [])
    today = date.today().isoformat()
    for d in items:
        end = (d.get("END_DATE") or "")[:10]
        if end and end < today:
            continue
        try:
            a, b = float(d["LOT"]), float(d["LAT"])
        except (KeyError, ValueError, TypeError):
            continue
        lat, lng = (a, b) if 36 < a < 39 else (b, a)  # LOT/LAT 필드가 뒤바뀐 데이터 대응
        stn, dist = nearest_station(cfg, lat, lng)
        if dist > cfg["nearby"]["culture_radius_m"]:
            continue
        name = d["TITLE"]
        rows += attrs(hid("s", name + d.get("STRTDATE", "")), "seoul-open", name=name,
                      category="전시·축제·기타", subcategory=d.get("CODENAME"), lat=lat, lng=lng,
                      address=d.get("PLACE"), station=stn, distance_m=dist,
                      period_start=(d.get("STRTDATE") or "")[:10], period_end=end,
                      thumb=d.get("MAIN_IMG"), map_url=map_url(d.get("PLACE") or name, stn), tier=3)
    return rows


def run(cfg, keys, force_sample=False):
    if cfg["mode"] != "nearby":
        raise SystemExit(f"mode={cfg['mode']} 는 아직 미구현입니다 (구조만 열어둠). config.yaml 의 mode 를 nearby 로 두세요.")
    rows = []
    # 키가 없는 소스는 --sample 일 때만 샘플 사용, 아니면 건너뜀(샘플이 실데이터에 섞이지 않게)
    if force_sample or keys["kakao"]:
        rows += collect_food(cfg, force_sample)
        rows += collect_popup(cfg, force_sample)
    if force_sample or keys["seoul"]:
        rows += collect_culture(cfg, force_sample)
    return rows

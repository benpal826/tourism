"""F18 역 목록: 카카오 지하철역 카테고리(SW8)로 서울(+근교) 역 이름·노선·좌표를 모아 docs/subway.json 으로.
앱의 지역 검색이 이 파일만 읽는다(앱에 API 키를 두지 않기 위해). 역이 거의 안 바뀌니 가끔 한 번만:
  python -m src.subway
"""
import json, re
from .common import *

URL = "https://dapi.kakao.com/v2/local/search/category.json"
BBOX = (126.76, 37.41, 127.19, 37.71)  # 서울 경계 넉넉히 (lng0, lat0, lng1, lat1)


def search_rect(rect, h, out, depth=0):
    """한 사각형에 45곳(카카오 한도) 넘게 있으면 4등분해 다시 검색."""
    params = {"category_group_code": "SW8", "rect": ",".join(f"{v:.5f}" for v in rect), "size": 15}
    first = http_json(URL, {**params, "page": 1}, h)
    if first["meta"]["total_count"] > 45 and depth < 6:
        x0, y0, x1, y1 = rect; mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        for r in ((x0, y0, mx, my), (mx, y0, x1, my), (x0, my, mx, y1), (mx, my, x1, y1)):
            search_rect(r, h, out, depth + 1)
        return
    docs, page, j = list(first["documents"]), 1, first
    while not j["meta"]["is_end"] and page < 3:
        page += 1; j = http_json(URL, {**params, "page": page}, h); docs += j["documents"]
    for d in docs:
        out[d["id"]] = d


def parse(docs):
    """'잠원역 3호선' → {name: 잠원, lines: [3호선], lat, lng}. 같은 이름 여러 노선은 한 역으로(좌표 평균)."""
    st = {}
    for d in docs.values():
        m = re.match(r"(.+?)역(?:\s+(.+))?$", d["place_name"].strip())
        if not m:
            continue
        name, line = m.group(1).strip(), (m.group(2) or "").strip()
        s = st.setdefault(name, {"name": name, "lines": [], "_p": []})
        if line and line not in s["lines"]:
            s["lines"].append(line)
        s["_p"].append((float(d["y"]), float(d["x"])))
    out = []
    for s in st.values():
        p = s.pop("_p")
        out.append({**s, "lat": round(sum(a for a, _ in p) / len(p), 5), "lng": round(sum(b for _, b in p) / len(p), 5)})
    return sorted(out, key=lambda s: s["name"])


if __name__ == "__main__":
    h = {"Authorization": "KakaoAK " + env("KAKAO_REST_KEY")}
    docs = {}
    search_rect(BBOX, h, docs)
    stations = parse(docs)
    (ROOT / "docs" / "subway.json").write_text(json.dumps(stations, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"요약: 역 {len(stations)}곳 → docs/subway.json")

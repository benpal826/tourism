"""대표메뉴·가격대 선별 도구 (출처: 후기 요약, Claude 가 읽고 선별).
  python3 -m src.menus todo [N]     메뉴 없는 먹거리 N곳의 후기 요약을 출력(선별용)
  python3 -m src.menus import FILE  {"place_id":[메뉴,가격,가격대,후기날짜]} JSON 을 candidates.csv 에 반영
"""
import html, json, re, sys
from .common import *
from .run import latest_cands

TAG = re.compile(r"<[^>]+>")
clean = lambda s: html.unescape(TAG.sub("", s or ""))
QUERIES = ("메뉴 가격", "메뉴판", "대표메뉴 추천")
PRICE_HINT = re.compile(r"\d{1,3},\d{3}\s*원|\d\.\d|\d{4,5}\s*원")


def snippets(name, station, per_query=15, limit=6):
    key = name.replace(" ", "")[:4]
    out, seen = [], set()
    for q in QUERIES:
        try:
            j = kakao_search("blog", f"{name} {station} {q}", sort="accuracy", size=per_query)
        except Exception:
            continue
        for d in j.get("documents", []):
            t = clean(d["title"] + " " + d["contents"])
            if key not in t.replace(" ", "") or not PRICE_HINT.search(t) or t[:50] in seen:
                continue
            seen.add(t[:50])
            out.append(d["datetime"][:10] + " " + t[:240])
    return out[:limit]


def todo(n):
    cands = latest_cands(DATA / "candidates.csv")
    m, min_rev = latest(read_rows(DATA / "mentions.csv")), load_config()["trend"]["min_reviews"]
    todo = [(p, a) for p, a in cands.items() if a.get("tier") == "1" and not a.get("menu")
            and float(m.get(p, {}).get("reviews_total", 0)) >= min_rev]  # 카드에 올라가는 곳만
    print(f"요약: 메뉴 없는 먹거리 {len(todo)}곳 중 {min(n, len(todo))}곳의 후기 요약.\n")
    for p, a in todo[:n]:
        print(f"### {p} {a['name']} [{a.get('kind', '')}]")
        for s in snippets(a["name"], a.get("station", "")):
            print("-", s)
        print()


def import_file(path):
    cur = json.load(open(path, encoding="utf-8"))
    rows = []
    for pid, (menu, price, band, d) in cur.items():
        rows += [{"place_id": pid, "field": f, "value": v, "source": "menu-curated"} for f, v in
                 (("menu", menu), ("price", "" if price == "-" else price), ("price_band", band),
                  ("menu_date", d), ("menu_source", "curated"))]
    n = append_rows(DATA / "candidates.csv", rows)
    print(f"요약: {len(cur)}곳 대표메뉴·가격대 반영 ({n}행 추가).")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "todo":
        todo(int(sys.argv[2]) if len(sys.argv) > 2 else 20)
    elif len(sys.argv) > 2 and sys.argv[1] == "import":
        import_file(sys.argv[2])
    else:
        raise SystemExit(__doc__)

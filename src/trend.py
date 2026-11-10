"""네이버 블로그로 후기 수/최근 30일 수 집계 + 대표 메뉴·가격·분위기·썸네일."""
import re
from datetime import timedelta
from .collect import attrs, clean, naver_h, sample
from .common import *

PRICE_RE = re.compile(r"([가-힣A-Za-z ]{2,14}?)\s*[:\-]?\s*(\d{1,3}(?:,\d{3})+|\d{4,6})\s*원")
VIBE = {"데이트": "데이트하기 좋은", "조용": "조용한", "감성": "감성적인", "분위기": "분위기 있는", "웨이팅": "웨이팅 있는 인기",
        "뷰": "뷰가 좋은", "루프탑": "루프탑", "아늑": "아늑한", "힙": "힙한", "혼술": "혼술하기 좋은", "와인": "와인 한잔하기 좋은"}


def is_ad(text, phrases):
    return any(p in text for p in phrases)


def fetch_posts(cfg, name, station):
    t = cfg["trend"]
    q = f"{name} {station}"
    posts, total = [], 0
    for start in range(1, t["max_posts_per_place"] + 1, 100):
        j = http_json("https://openapi.naver.com/v1/search/blog.json",
                      {"query": q, "display": 100, "start": start, "sort": "date"}, naver_h())
        total = j.get("total", 0)
        items = j.get("items", [])
        posts += items
        if len(items) < 100:
            break
    return total, posts


def analyze(cfg, total, posts):
    t = cfg["trend"]
    cutoff = (date.today() - timedelta(days=t["recent_days"])).strftime("%Y%m%d")
    ads = recent = 0
    menus, vibes, last_date = {}, {}, ""
    for p in posts:
        text = clean(p["title"]) + " " + clean(p.get("description", ""))
        if is_ad(text, t["exclude_phrases"]):
            ads += 1
            continue
        pd = p.get("postdate", "")
        if pd >= cutoff:
            recent += 1
        for m in PRICE_RE.finditer(text):
            key = (m.group(1).strip(), m.group(2).replace(",", ""))
            menus.setdefault(key, pd)
        for k, v in VIBE.items():
            if k in text:
                vibes[v] = vibes.get(v, 0) + 1
    out = {"reviews_total": max(total - ads, 0), "reviews_30d": recent}
    if menus:
        (mn, price), pd = max(menus.items(), key=lambda kv: kv[1])
        out["menu"], out["price"] = mn, f"{int(price):,}원"
        out["menu_date"] = f"{pd[:4]}-{pd[4:6]}-{pd[6:]}" if len(pd) == 8 else ""
    if vibes:
        top = sorted(vibes, key=vibes.get, reverse=True)[:2]
        out["vibe"] = ", ".join(top) + " 곳"
    return out


def thumb(name, station):
    j = http_json("https://openapi.naver.com/v1/search/image",
                  {"query": f"{name} {station}", "display": 1}, naver_h())
    it = (j.get("items") or [{}])[0]
    return it.get("thumbnail", "")


def run(cfg, cands, keys, force_sample=False):
    """cands: {place_id: attrs}. 팝업/문화행사는 후기 집계 대상 아님(썸네일만)."""
    mention_rows, detail_rows = [], []
    use_sample = force_sample or not keys["naver"]
    samp = sample("naver_blog.json") if use_sample else {}
    for pid, a in cands.items():
        if a.get("tier") == "1":
            if use_sample:
                s = samp.get(a["name"])
                if not s:
                    continue
                res = {k: s[k] for k in s if k not in ("thumb",)}
                th = s.get("thumb", "")
            else:
                total, posts = fetch_posts(cfg, a["name"], a["station"])
                res = analyze(cfg, total, posts)
                th = thumb(a["name"], a["station"])
            for f in ("reviews_total", "reviews_30d"):
                if f in res:
                    mention_rows.append({"place_id": pid, "field": f, "value": res.pop(f), "source": "naver-blog"})
            detail_rows += attrs(pid, "naver-blog", thumb=th, **res)
        elif not a.get("thumb") and not use_sample:
            detail_rows += attrs(pid, "naver-image", thumb=thumb(a["name"], a.get("station", "")))
    return mention_rows, detail_rows

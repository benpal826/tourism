"""다음(카카오) 블로그 검색으로 후기 수/최근 30일 수 집계 + 대표 메뉴·가격·분위기·썸네일."""
import re
from datetime import timedelta
from .collect import attrs, clean, sample
from .common import *

PRICE_RE = re.compile(r"([가-힣A-Za-z]{2,10})\s*[:\-]?\s*(\d{1,3},\d{3})\s*원")
BAD_MENU = ("가격", "비용", "요금", "금액", "티켓", "주차", "발레", "입장", "합계", "총", "메뉴", "이용", "할인", "포인트", "적립", "서비스", "예약", "발렛", "영화", "각각", "최대", "인당", "기본", "추가", "최소", "평균", "대략", "약", "총액")
VIBE = {"데이트": "데이트하기 좋은", "조용": "조용한", "감성": "감성적인", "분위기": "분위기 있는", "웨이팅": "웨이팅 있는 인기",
        "뷰": "뷰가 좋은", "루프탑": "루프탑", "아늑": "아늑한", "힙": "힙한", "혼술": "혼술하기 좋은", "와인": "와인 한잔하기 좋은"}


def is_ad(text, phrases):
    return any(p in text for p in phrases)


def fetch_posts(cfg, name, station):
    """카카오(다음) 블로그 검색, 최신순. 최근 recent_days 이전 글이 나오면 중단."""
    t = cfg["trend"]
    cutoff = (date.today() - timedelta(days=t["recent_days"])).strftime("%Y%m%d")
    posts, total = [], 0
    for page in range(1, min(50, -(-t["max_posts_per_place"] // 50)) + 1):
        j = kakao_search("blog", f"{name} {station}", sort="recency", size=50, page=page)
        total = j["meta"].get("total_count", 0)
        for d in j["documents"]:
            posts.append({"title": d["title"], "description": d["contents"],
                          "postdate": d["datetime"][:10].replace("-", "")})
        if j["meta"].get("is_end") or (posts and posts[-1]["postdate"] < cutoff):
            break
    return total, posts


def analyze(cfg, total, posts, name=""):
    t = cfg["trend"]
    cutoff = (date.today() - timedelta(days=t["recent_days"])).strftime("%Y%m%d")
    key = name.replace(" ", "")
    if key:  # 가게 이름이 실제로 들어간 글만 대상 (검색 엔진이 느슨하게 매칭한 글 제외)
        hit = [p for p in posts if key in (clean(p["title"]) + clean(p.get("description", ""))).replace(" ", "")]
        ratio = len(hit) / len(posts) if posts else 0
        total, posts = int(total * ratio), hit
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
            mn, pr = m.group(1), int(m.group(2).replace(",", ""))
            if any(b in mn for b in BAD_MENU) or not 3000 <= pr <= 200000:
                continue
            menus.setdefault((mn, str(pr)), pd)
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
    """(고화질 원본, 저화질 썸네일). 후기(블로그·카페) 사진 중 폭 400px 이상을 우선."""
    j = kakao_search("image", f"{name} {station}", size=8)
    docs = j.get("documents") or []
    wide = [d for d in docs if d.get("width", 0) >= 400]
    mine = [d for d in wide if d.get("collection") in ("blog", "cafe")]  # 뉴스·기타 엉뚱한 사진보다 후기 사진 우선
    best = (mine or wide or docs or [{}])[0]
    return best.get("image_url", ""), best.get("thumbnail_url", "")


PHOTO_KINDS = [("menu", "메뉴판"), ("food", "음식"), ("mood", "내부 분위기"), ("outside", "외관")]


def pick(docs, used):
    wide = [d for d in docs if d.get("width", 0) >= 400 and d.get("image_url") not in used]
    mine = [d for d in wide if d.get("collection") in ("blog", "cafe")]
    return (mine or wide or [None])[0]


def photos(name, station):
    """카테고리별(메뉴판/음식/분위기/외관) 사진. 카카오 이미지 검색 기반이라 카카오맵 사진탭과는 다름."""
    out, used = {}, set()
    for key, q in PHOTO_KINDS:
        try:
            docs = kakao_search("image", f"{name} {station} {q}", size=10).get("documents", [])
        except Exception:
            continue
        d = pick(docs, used)
        if d:
            used.add(d["image_url"])
            out["photo_" + key] = d["image_url"] + "|" + d.get("thumbnail_url", "")
    return out


def one(cfg, pid, a, use_sample, samp):
    """한 곳의 (mention_rows, detail_rows)."""
    mention_rows, detail_rows = [], []
    if a.get("tier") == "1":
        if use_sample:
            s = samp.get(a["name"])
            if not s:
                return [], []
            res = {k: s[k] for k in s if k != "thumb"}
            th = (s.get("thumb", ""), "")
        else:
            total, posts = fetch_posts(cfg, a["name"], a["station"])
            res = analyze(cfg, total, posts, a["name"])
            th = thumb(a["name"], a["station"])
        for f in ("reviews_total", "reviews_30d"):
            if f in res:
                mention_rows.append({"place_id": pid, "field": f, "value": res.pop(f), "source": "kakao-blog"})
        ph = {} if use_sample else photos(a["name"], a["station"])
        detail_rows += attrs(pid, "kakao-blog", thumb=th[0], thumb_lo=th[1], **res, **ph)
    elif not a.get("thumb") and not use_sample:
        th = thumb(a["name"], a.get("station", ""))
        detail_rows += attrs(pid, "kakao-image", thumb=th[0], thumb_lo=th[1])
    return mention_rows, detail_rows


def run(cfg, cands, keys, force_sample=False):
    """팝업/문화행사는 후기 집계 없이 썸네일만. 가게별 호출은 4개씩 병렬."""
    from concurrent.futures import ThreadPoolExecutor
    use_sample = force_sample
    samp = sample("blog_stats.json") if use_sample else {}
    with ThreadPoolExecutor(4) as ex:
        results = list(ex.map(lambda kv: one(cfg, kv[0], kv[1], use_sample, samp), cands.items()))
    return [r for m, _ in results for r in m], [r for _, d in results for r in d]

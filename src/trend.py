"""다음(카카오) 블로그 검색으로 후기 수/최근 30일 수 집계 + 대표 메뉴·가격·분위기·썸네일."""
import re
from datetime import timedelta
from .collect import attrs, clean, sample
from .common import *

PRICE_RE = re.compile(r"([가-힣A-Za-z]{2,10})\s*[:\-]?\s*(\d{1,3},\d{3})\s*원")
BAD_MENU = ("가격", "비용", "요금", "금액", "티켓", "주차", "발레", "입장", "합계", "총", "메뉴", "이용", "할인", "포인트", "적립", "서비스", "예약", "수강", "학원", "회비", "보증금", "임대", "발렛", "영화", "각각", "최대", "인당", "기본", "추가", "최소", "평균", "대략", "약", "총액")
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
                          "postdate": d["datetime"][:10].replace("-", ""), "url": d.get("url", "")})
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
    seen_posts = set()
    for p in posts:
        text = clean(p["title"]) + " " + clean(p.get("description", ""))
        sig = re.sub(r"\s+", "", text)[:120]
        if sig in seen_posts:
            continue  # 같은 글이 중복 수집된 경우 한 번만
        seen_posts.add(sig)
        if is_ad(text, t["exclude_phrases"]):
            ads += 1
            continue
        pd = p.get("postdate", "")
        if pd >= cutoff:
            recent += 1
        in_post = {}  # 한 글 안에서 반복된 같은 메뉴는 1회로 셈('2회 확인' = 서로 다른 글 2개)
        for m in PRICE_RE.finditer(text):
            mn, pr = m.group(1), int(m.group(2).replace(",", ""))
            if any(b in mn for b in BAD_MENU) or not 3000 <= pr <= 200000:
                continue
            in_post.setdefault(mn, (pr, pd))
        for mn, v in in_post.items():
            menus.setdefault(mn, []).append(v)
        for k, v in VIBE.items():
            if k in text:
                vibes[v] = vibes.get(v, 0) + 1
    out = {"reviews_total": max(total - ads, 0), "reviews_30d": recent}
    if menus:
        # 대표메뉴 = 후기에서 가장 자주 가격과 함께 언급된 메뉴(동률이면 최근), 가격 = 그 메뉴 언급 가격의 중앙값
        mn, rows = max(menus.items(), key=lambda kv: (len(kv[1]), max(d for _, d in kv[1])))
        prices = sorted(p for p, _ in rows)
        allp = sorted(p for r in menus.values() for p, _ in r)
        mid, med = prices[len(prices) // 2], allp[len(allp) // 2]
        out["menu"], out["price"] = mn, f"{mid:,}원"
        out["price_band"] = f"{med // 1000}천원대" if med < 10000 else f"{med // 10000}만원대"
        out["menu_mentions"] = len(rows)
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


PHOTO_KINDS = [("food", "음식 메뉴"), ("mood", "내부 분위기"), ("outside", "외관")]
MIN_PHOTOS, MAX_PHOTOS, PER_POST = 3, 6, 2


def url_key(u):
    """블로그·카페 글 주소를 비교용 키로 정규화(http/https·모바일·쿼리 차이 무시)."""
    u = re.sub(r"^https?://(www\.|m\.)?", "", (u or "").strip().lower()).split("#")[0]
    m = re.match(r"blog\.naver\.com/(?:postview\.naver\?blogid=(\w+)&logno=(\d+)|(\w+)/(\d+))", u)
    if m:
        return "nb/" + "/".join(x for x in m.groups() if x)
    return u.split("?")[0].rstrip("/")


def verified_urls(name, posts, station=""):
    """가게 이름이 제목·요약에 실제로 들어간 글의 주소 집합."""
    key = re.sub(r"(본점|직영점|[가-힣]{1,4}점)$", "", name.replace(" ", "")) or name.replace(" ", "")  # 지점명 뗀 이름
    return {url_key(p["url"]) for p in posts
            if p.get("url") and key in (txt := (clean(p["title"]) + clean(p.get("description", ""))).replace(" ", ""))
            and (not station or station.replace("역", "") in txt)}  # 체인점 오인 방지: 역(지역)명도 함께 언급된 글만


def good_image(d):
    """메뉴판·영수증·지도·배너로 보이는 이미지 제외(크기·비율)."""
    w, h = d.get("width", 0), d.get("height", 0)
    if w < 400 or h < 300:
        return False
    r = w / h
    return 0.6 <= r <= 1.8  # 너무 길쭉한 캡처·배너·긴 메뉴판 제외


def photos(name, station, posts):
    """가게가 확인된 후기 글의 사진만 사용(이미지 검색 doc_url == 글 주소). 한 글에서 최대 2장, 부족하면 적게."""
    extra = []
    for pg in (1, 2, 3):  # 정확도순 블로그 글도 확인 대상에 추가(이미지 검색 결과와 겹침을 늘림)
        try:
            j = kakao_search("blog", f"{name} {station}", sort="accuracy", size=50, page=pg)
        except Exception:
            break
        extra += [{"title": d["title"], "description": d["contents"], "url": d["url"]} for d in j["documents"]]
        if j["meta"].get("is_end"):
            break
    ok = verified_urls(name, posts + extra, station)
    none = {"photo_" + k: "-" for k in ("food", "mood", "outside", "etc")}  # 이전 주 사진을 덮는 표식
    if not ok:
        return none
    cand, seen = [], set()
    queries = [(k, f"{name} {station} {q}", 1) for k, q in PHOTO_KINDS] + [(k, f"{name} {q}", 1) for k, q in PHOTO_KINDS]
    queries += [("etc", f"{name} {station}", pg) for pg in (1, 2, 3)]  # 분류 불명 사진
    for key, query, pg in queries:
        try:
            docs = kakao_search("image", query, size=30, page=pg).get("documents", [])
        except Exception:
            continue
        for d in docs:
            u = d.get("image_url")
            if not u or u in seen or url_key(d.get("doc_url")) not in ok or not good_image(d):
                continue
            seen.add(u)
            cand.append((key, d))
    out, per_post, picked = {}, {}, 0
    for key, d in sorted(cand, key=lambda x: -x[1].get("width", 0) * x[1].get("height", 0) // 1):  # 큰 사진 먼저
        pk = url_key(d["doc_url"])
        if picked >= MAX_PHOTOS or per_post.get(pk, 0) >= PER_POST:
            continue
        per_post[pk] = per_post.get(pk, 0) + 1
        picked += 1
        out.setdefault("photo_" + key, []).append(d["image_url"] + "|" + d.get("thumbnail_url", ""))
    return {**none, **{k: "§".join(v) for k, v in out.items()}}


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
        if a.get("menu_source") == "curated":
            for k in ("menu", "price", "price_band", "menu_mentions", "menu_date"):
                res.pop(k, None)
        for f in ("reviews_total", "reviews_30d"):
            if f in res:
                mention_rows.append({"place_id": pid, "field": f, "value": res.pop(f), "source": "kakao-blog"})
        ph = {} if use_sample else photos(a["name"], a["station"], posts)
        detail_rows += attrs(pid, "kakao-blog", thumb=th[0], thumb_lo=th[1], **res, **ph)
    elif not a.get("thumb") and not use_sample:
        th = thumb(a["name"], a.get("station", ""))
        detail_rows += attrs(pid, "kakao-image", thumb=th[0], thumb_lo=th[1])
    return mention_rows, detail_rows


def run(cfg, cands, keys, force_sample=False):
    """팝업/문화행사는 후기 집계 없이 썸네일만. 가게별 호출은 4개씩 병렬."""
    from concurrent.futures import ThreadPoolExecutor
    use_sample = force_sample
    if not use_sample and not keys.get("kakao"):
        return [], []  # 카카오 키가 없으면 후기·사진 보강을 건너뜀
    samp = sample("blog_stats.json") if use_sample else {}
    failed = []

    def safe(kv):  # 장소 하나의 오류가 전체 갱신을 멈추지 않게 격리
        try:
            return one(cfg, kv[0], kv[1], use_sample, samp)
        except Exception as e:
            failed.append((kv[1].get("name"), type(e).__name__))
            return [], []
    with ThreadPoolExecutor(4) as ex:
        results = list(ex.map(safe, cands.items()))
    if failed:
        print(f"경고: 보강 실패 {len(failed)}곳(나머지는 정상 반영): " + ", ".join(f"{n}({t})" for n, t in failed[:5]))
    return [r for m, _ in results for r in m], [r for _, d in results for r in d]

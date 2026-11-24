"""다음(카카오)+네이버 블로그 검색으로 후기 수/최근 30일 수 집계 + 대표 메뉴·가격·분위기·썸네일."""
import re
from datetime import timedelta
from .collect import attrs, clean, sample
from .common import *

# 출처 표기: 집계 기준이 바뀌면 이름을 바꿔 급상승이 다른 기준 스냅샷과 비교되지 않게 함(rank.weekly_growth)
SRC_KAKAO, SRC_BOTH = "kakao-blog/v3", "kakao+naver-blog/v3"  # v3: 해시태그만 있는 글 제외(F10)
PRICE_RE = re.compile(r"([가-힣A-Za-z]{2,10})\s*[:\-]?\s*(\d{1,3},\d{3})\s*원")
BAD_MENU = ("가격", "비용", "요금", "금액", "티켓", "주차", "발레", "입장", "합계", "총", "메뉴", "이용", "할인", "포인트", "적립", "서비스", "예약", "수강", "학원", "회비", "보증금", "임대", "발렛", "영화", "각각", "최대", "인당", "기본", "추가", "최소", "평균", "대략", "약", "총액")
VIBE = {"데이트": "데이트하기 좋은", "조용": "조용한", "감성": "감성적인", "분위기": "분위기 있는", "웨이팅": "웨이팅 있는 인기",
        "뷰": "뷰가 좋은", "루프탑": "루프탑", "아늑": "아늑한", "힙": "힙한", "혼술": "혼술하기 좋은", "와인": "와인 한잔하기 좋은"}


def is_ad(text, phrases):
    return any(p in text for p in phrases)


def fetch_posts(cfg, name, station):
    """카카오(다음)+네이버 블로그 검색, 최신순. 최근 recent_days 이전 글이 나오면 중단.
    반환: ({출처: 전체 건수}, 글 목록(각 글에 src), mentions 출처 표기)."""
    t = cfg["trend"]
    cap = t["max_posts_per_place"]
    cutoff = (date.today() - timedelta(days=t["recent_days"])).strftime("%Y%m%d")
    posts, total = [], 0
    for page in range(1, min(50, -(-cap // 50)) + 1):
        j = kakao_search("blog", f"{name} {station}", sort="recency", size=50, page=page)
        total = j["meta"].get("total_count", 0)
        for d in j["documents"]:
            posts.append({"title": d["title"], "description": d["contents"], "src": "kakao",
                          "postdate": d["datetime"][:10].replace("-", ""), "url": d.get("url", "")})
        if j["meta"].get("is_end") or (posts and posts[-1]["postdate"] < cutoff):
            break
    if not have_keys()["naver"]:
        return {"kakao": total}, posts, SRC_KAKAO
    seen = {url_key(p["url"]) for p in posts}
    nposts, ntotal = [], 0
    try:
        for start in range(1, min(1000, cap) + 1, 100):  # 네이버: display 최대 100, start 최대 1000
            j = naver_search("blog", f"{name} {station}", sort="date", display=min(100, cap - len(nposts)), start=start)
            ntotal = j.get("total", 0)
            items = j.get("items", [])
            nposts += [{"title": d["title"], "description": d["description"], "postdate": d["postdate"],
                        "url": d["link"], "src": "naver"} for d in items]
            if len(items) < 100 or len(nposts) >= cap or nposts[-1]["postdate"] < cutoff:
                break
    except Exception:
        return {"kakao": total}, posts, SRC_KAKAO  # 네이버 장애·한도 초과면 카카오만으로(가게 보강 전체를 잃지 않게)
    new = [p for p in nposts if url_key(p["url"]) not in seen]
    cafe = []
    try:  # 카페 글: 작성일이 없어 후기 수·최근 30일 수에는 안 넣고 본문 재료(메뉴·분위기·요약 발췌)로만
        items = naver_search("cafearticle", f"{name} {station}", sort="date", display=100).get("items", [])
        seen |= {url_key(p["url"]) for p in new}
        cafe = [{"title": d["title"], "description": d["description"], "postdate": "", "url": d["link"], "src": "cafe"}
                for d in items if url_key(d["link"]) not in seen]
    except Exception:
        pass
    # shortcut: 카카오와 겹치는 비율을 가져온 글로 추정해 네이버 전체 건수에 적용. 겹침이 크게 틀리면 출처별 따로 집계로 바꿀 것
    return {"kakao": total, "naver": int(ntotal * len(new) / len(nposts)) if nposts else 0}, posts + new + cafe, SRC_BOTH


PARTICLES = set("은는이가을를에의도과와로랑")
SOLID = re.compile(r"[가-힣A-Za-z0-9]")
ROAD = re.compile(r"([가-힣]+(?:대로|로|길)[0-9]*(?:번?길)?)\s*[0-9]")


def name_pattern(name):
    """글에서 찾을 이름 정규식. 한 단어면 그대로. 여러 단어면 '상호 + 지점명 핵심'이 붙어 나와야 함
    ('스타벅스 압구정역점' → '스타벅스 ?압구정역(N호점|점)?'). 상호만 쓴 글은 어느 지점인지 몰라 안 셈."""
    toks = name.split()
    if len(toks) == 1:
        return re.escape(name.strip()), name.strip()
    branch = re.sub(r"(호점|점)$", "", re.sub(r"[0-9]+", "", toks[1]))
    return re.escape(toks[0]) + r" ?" + re.escape(branch) + r"(?:[0-9]*호?점)?", toks[0]


def is_about(p, name, station="", address="", hashtags=False):
    """이 글이 이 가게 후기인가. 이름이 앞뒤에 붙지 않고(뒤 조사 허용) 나오고,
    이름을 뺀 나머지에 위치 단서(역명·도로명 길 이름)가 있어야 함. 두 글자 이하 상호는 제목에 있어야 함."""
    title, body = clean(p["title"]), clean(p.get("description", ""))
    text = re.sub(r"\s+", " ", title + " " + body)
    pat, b = name_pattern(name)
    if not b or (len(b) <= 2 and b not in title):
        return False
    spans = []
    for m in re.finditer(pat, text):
        before = text[m.start() - 1] if m.start() else " "
        after = text[m.end()] if m.end() < len(text) else " "
        if (hashtags or before != "#") and not SOLID.match(before) and (not SOLID.match(after) or after in PARTICLES):  # #가게명 해시태그는 후기 근거로 안 봄(이미지 제목은 해시태그가 전부라 hashtags=True)
            spans.append(m.span())
    if not spans:
        return False
    rest = "".join(text[a:b2] for a, b2 in zip([0] + [e for _, e in spans], [s for s, _ in spans] + [len(text)]))
    clues = [station.replace("역", "")] if station else []
    road = ROAD.search(address or "")
    clues += [road.group(1)] if road else []
    return not clues or any(c and c in rest for c in clues)


def analyze(cfg, total, posts, name="", station="", address=""):
    """total: 전체 건수(int) 또는 {출처: 건수}. 출처별로 '이 가게 글' 비율을 곱해 보정."""
    t = cfg["trend"]
    cutoff = (date.today() - timedelta(days=t["recent_days"])).strftime("%Y%m%d")
    if name:  # 이 가게 후기로 확인된 글만 대상 (검색 엔진이 느슨하게 매칭한 글 제외)
        totals = total if isinstance(total, dict) else {None: total}
        hit = [p for p in posts if is_about(p, name, station, address)]
        ok = {id(p) for p in hit}
        total = 0
        for src, n in totals.items():
            mine = [p for p in posts if src is None or p.get("src") == src]
            total += int(n * sum(id(p) in ok for p in mine) / len(mine)) if mine else 0
        posts = hit
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


def verified_urls(name, posts, station="", address=""):
    """이 가게 후기로 확인된 글의 주소 집합. 후기 집계와 같은 is_about 판정(이름 정확히·위치 단서·지점명)."""
    return {url_key(p["url"]) for p in posts if p.get("url") and is_about(p, name, station, address)}


def good_image(d):
    """메뉴판·영수증·지도·배너로 보이는 이미지 제외(크기·비율)."""
    w, h = d.get("width", 0), d.get("height", 0)
    if w < 400 or h < 300:
        return False
    r = w / h
    return 0.6 <= r <= 1.8  # 너무 길쭉한 캡처·배너·긴 메뉴판 제외


def photo_candidates(name, station, posts, address=""):
    """[(검색어 종류, 이미지 검색 결과)] 큰 사진 순. 가게가 확인된 후기 글의 사진만 사용(이미지 검색 doc_url == 글 주소)."""
    extra = []
    for pg in (1, 2, 3):  # 정확도순 블로그 글도 확인 대상에 추가(이미지 검색 결과와 겹침을 늘림)
        try:
            j = kakao_search("blog", f"{name} {station}", sort="accuracy", size=50, page=pg)
        except Exception:
            break
        extra += [{"title": d["title"], "description": d["contents"], "url": d["url"]} for d in j["documents"]]
        if j["meta"].get("is_end"):
            break
    ok = verified_urls(name, posts + extra, station, address)
    if not ok:
        return []
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
    return sorted(cand, key=lambda x: -x[1].get("width", 0) * x[1].get("height", 0))  # 큰 사진 먼저


def photos(name, station, posts, address=""):
    """자동 사진(미선별 가게용). 한 글에서 최대 2장, 최대 6장. 분류는 검색어 기준이라 앱은 '사진' 하나로 보여 줌."""
    none = {"photo_" + k: "-" for k in ("food", "mood", "outside", "etc")}  # 이전 주 사진을 덮는 표식
    out, per_post, picked = {}, {}, 0
    for key, d in photo_candidates(name, station, posts, address):
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
    src = SRC_KAKAO
    if a.get("tier") == "1":
        if use_sample:
            s = samp.get(a["name"])
            if not s:
                return [], []
            res = {k: s[k] for k in s if k != "thumb"}
            th = (s.get("thumb", ""), "")
        else:
            total, posts, src = fetch_posts(cfg, a["name"], a["station"])
            res = analyze(cfg, total, posts, a["name"], a["station"], a.get("address", ""))
            th = thumb(a["name"], a["station"])
        if a.get("menu_source") == "curated":
            for k in ("menu", "price", "price_band", "menu_mentions", "menu_date"):
                res.pop(k, None)
        for f in ("reviews_total", "reviews_30d"):
            if f in res:
                mention_rows.append({"place_id": pid, "field": f, "value": res.pop(f), "source": src})
        ph = {} if use_sample or a.get("photo_source") == "curated" else photos(a["name"], a["station"], posts, a.get("address", ""))  # 선별 사진은 덮지 않음
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

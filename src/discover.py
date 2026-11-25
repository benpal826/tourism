"""F11 추천글 기반 발굴: 역·카테고리별 추천글(블로그)에서 후보가 언급된 글 수(rec_mentions)."""
from .common import *


def rec_posts(query):
    """추천글 후보: 네이버 블로그(정확도순 100) + 카카오 블로그(정확도순 100). 실패한 쪽은 건너뜀."""
    posts = []
    try:
        posts += [{"title": d["title"], "description": d["description"], "url": d["link"]}
                  for d in naver_search("blog", query, sort="sim", display=100).get("items", [])]
    except Exception:
        pass
    for page in (1, 2):
        try:
            j = kakao_search("blog", query, sort="accuracy", size=50, page=page)
        except Exception:
            break
        posts += [{"title": d["title"], "description": d["contents"], "url": d["url"]} for d in j["documents"]]
        if j["meta"].get("is_end"):
            break
    return posts


def run(cfg, cands):
    """[mentions 행] rec_mentions = 이 가게 글(is_about)로 확인된 추천글 수. 0 도 남김(이번 주 언급 없음)."""
    from .trend import is_about, url_key
    d, rows = cfg.get("discover", {}), []
    for st in cfg["nearby"]["stations"]:
        for cat, qs in d.get("rec_queries", {}).items():
            group = [(p, a) for p, a in cands.items()
                     if a.get("tier") == "1" and a.get("station") == st["name"] and a.get("category") == cat]
            if not group:
                continue
            posts = {}
            for q in qs:
                for p in rec_posts(q.format(st=st["name"])):
                    posts.setdefault(url_key(p["url"]), p)
            for pid, a in group:
                n = sum(1 for p in posts.values() if is_about(p, a["name"], st["name"], a.get("address", "")))
                rows.append({"place_id": pid, "field": "rec_mentions", "value": n, "source": "discover"})
    return rows


def pick(cfg, cands, mentions):
    """보강할 후보: 1순위는 역·카테고리별 rec_mentions 상위 enrich_per_station 곳(0 제외), 2·3순위는 전부."""
    k = cfg.get("discover", {}).get("enrich_per_station", 8)
    rec = {p: float(v.get("rec_mentions", 0) or 0) for p, v in latest(mentions).items()}
    groups, out = {}, {}
    for p, a in cands.items():
        if a.get("tier") != "1":
            out[p] = a
        elif rec.get(p, 0) > 0:
            groups.setdefault((a.get("station"), a.get("category")), []).append(p)
    for ps in groups.values():
        for p in sorted(ps, key=lambda p: -rec[p])[:k]:
            out[p] = cands[p]
    return out

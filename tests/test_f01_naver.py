"""F01 자체검사: python -m tests.test_f01_naver (외부 호출 없음, 실패 시 AssertionError 로 exit 1)."""
import os
from datetime import date, timedelta
from src import trend, rank
from src.common import load_config

cfg = load_config()
today = date.today().strftime("%Y%m%d")
old = (date.today() - timedelta(days=60)).strftime("%Y%m%d")


def fake_kakao(kind, query, **kw):
    docs = [{"title": "한우집 신사 후기", "contents": "한우집 맛있음", "datetime": date.today().isoformat() + "T00:00:00",
             "url": "http://blog.naver.com/aaa/111"},
            {"title": "한우집 신사", "contents": "좋아요", "datetime": date.today().isoformat() + "T00:00:00",
             "url": "https://xx.tistory.com/5"}]
    return {"meta": {"total_count": 2, "is_end": True}, "documents": docs}


def fake_naver(kind, query, **kw):
    items = [{"title": "<b>한우집</b> 신사", "description": "중복 글", "postdate": today, "link": "https://blog.naver.com/aaa/111"},
             {"title": "한우집 신사 데이트", "description": "새 글", "postdate": today, "link": "https://blog.naver.com/bbb/222"},
             {"title": "한우집 옛날 글", "description": "오래됨", "postdate": old, "link": "https://blog.naver.com/ccc/333"}]
    return {"total": 3, "items": items}


trend.kakao_search, trend.naver_search = fake_kakao, fake_naver

# 1) 네이버 키 없음: 카카오만
for k in ("NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET"):
    os.environ.pop(k, None)
total, posts, src = trend.fetch_posts(cfg, "한우집", "신사")
assert (total, len(posts), src) == ({"kakao": 2}, 2, trend.SRC_KAKAO), (total, len(posts), src)

# 2) 네이버 키 있음: 합치고 같은 글(aaa/111, http/https 차이)은 한 번만
os.environ["NAVER_CLIENT_ID"], os.environ["NAVER_CLIENT_SECRET"] = "x", "y"
total, posts, src = trend.fetch_posts(cfg, "한우집", "신사")
assert src == trend.SRC_BOTH and len(posts) == 4, (src, len(posts))
assert total == {"kakao": 2, "naver": int(3 * 2 / 3)}, total  # 네이버 3건 중 2건이 새 글
res = trend.analyze(cfg, total, posts, "한우집", "신사")
assert res["reviews_30d"] == 3, res  # 60일 전 글 제외

# 3) 출처가 바뀐 주는 급상승으로 세지 않음, 같은 출처끼리는 비교
d = lambda n: (date.today() - timedelta(days=n)).isoformat()
m = [{"date": d(7), "place_id": "p", "field": "reviews_total", "value": "100", "source": "kakao-blog"},
     {"date": d(0), "place_id": "p", "field": "reviews_total", "value": "900", "source": "kakao+naver-blog"}]
assert rank.weekly_growth(m)["p"] is None, rank.weekly_growth(m)
m.append({"date": d(14), "place_id": "p", "field": "reviews_total", "value": "850", "source": "kakao+naver-blog"})
assert rank.weekly_growth(m)["p"] == 50, rank.weekly_growth(m)
print("F01 OK")

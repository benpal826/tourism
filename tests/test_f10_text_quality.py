"""F10 자체검사: python -m tests.test_f10_text_quality (외부 호출 없음)."""
import os
from datetime import date
from src import trend
from src.common import load_config

today = date.today().strftime("%Y%m%d")
P = lambda t, d="", url="u", src="kakao": {"title": t, "description": d, "postdate": today, "url": url, "src": src}

# 1) 사진 후보용 글 판정 = is_about (예전 느슨한 판정은 '압구정 떡볶이' 글도 통과시켰음)
posts = [P("압구정떡볶이 압구정역 후기", url="https://a/1"), P("압구정 떡볶이 맛집", url="https://a/2"),
         P("대왕족발 신사", url="https://a/3")]
assert trend.verified_urls("압구정떡볶이", posts, "압구정") == {"a/1"}, trend.verified_urls("압구정떡볶이", posts, "압구정")
assert trend.verified_urls("대왕", posts, "신사") == set()

# 2) 해시태그로만 나오면 이 가게 글 아님, 본문에 한 번이라도 제대로 나오면 인정
assert not trend.is_about(P("압구정 김밥 맛집 #압구정떡볶이 #압구정맛집"), "압구정떡볶이", "압구정")
assert trend.is_about(P("압구정떡볶이 다녀옴 #압구정떡볶이 #압구정"), "압구정떡볶이", "압구정")

# 3) 카페 글: 본문 재료로만(후기 수·30일 수 제외), 주소 중복 제외, 카페 실패해도 집계 유지
os.environ["NAVER_CLIENT_ID"], os.environ["NAVER_CLIENT_SECRET"] = "x", "y"
trend.kakao_search = lambda *a, **k: {"meta": {"total_count": 10, "is_end": True}, "documents": [
    {"title": "압구정면옥 압구정역", "contents": "냉면", "datetime": date.today().isoformat() + "T00:00:00", "url": "https://k/1"}]}

def naver(kind, q, **k):
    if kind == "blog":
        return {"total": 4, "items": [{"title": "압구정면옥 압구정", "description": "비빔냉면 12,000원", "postdate": today, "link": "https://n/1"}]}
    return {"items": [{"title": "압구정면옥 압구정 후기", "description": "평양냉면 16,000원 맛있음", "link": "https://cafe.naver.com/x/1"},
                      {"title": "압구정면옥 압구정", "description": "중복", "link": "https://n/1"}]}
trend.naver_search = naver
cfg = load_config()
total, posts, src = trend.fetch_posts(cfg, "압구정면옥", "압구정")
assert [p["src"] for p in posts] == ["kakao", "naver", "cafe"], [p["src"] for p in posts]
assert total == {"kakao": 10, "naver": 4}, total  # 카페는 건수에 안 들어감
res = trend.analyze(cfg, total, posts, "압구정면옥", "압구정")
assert res["reviews_total"] == 14 and res["reviews_30d"] == 2, res  # 카페 글(작성일 없음)은 30일 수 제외

def cafe_fail(kind, q, **k):
    if kind == "cafearticle":
        raise OSError("quota")
    return naver(kind, q, **k)
trend.naver_search = cafe_fail
total, posts, src = trend.fetch_posts(cfg, "압구정면옥", "압구정")
assert total == {"kakao": 10, "naver": 4} and len(posts) == 2 and src == trend.SRC_BOTH, (total, len(posts), src)
print("F10 OK")

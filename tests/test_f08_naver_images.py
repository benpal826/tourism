"""F08 자체검사: python -m tests.test_f08_naver_images (외부 호출 없음)."""
import os
from src import photos, trend

a = {"name": "압구정면옥", "station": "압구정", "address": "서울 강남구 압구정로30길 16"}
items = [{"title": "#압구정역맛집 #압구정면옥", "link": "https://n/1.jpg", "thumbnail": "t1", "sizewidth": "1080", "sizeheight": "1080"},
         {"title": "압구정 냉면 맛집", "link": "https://n/2.jpg", "thumbnail": "t2", "sizewidth": "1080", "sizeheight": "1080"},  # 이름 없음
         {"title": "#압구정면옥 #압구정", "link": "https://n/3.jpg", "thumbnail": "t3", "sizewidth": "200", "sizeheight": "200"}]  # 너무 작음
photos.naver_search = lambda *a, **k: {"items": items}
got = photos.naver_images(a)
assert {c["hi"] for c in got} == {"https://n/1.jpg"}, got

# 합치기: 카카오 후보 + 네이버, 같은 주소 중복 제거, 최대 SHEET_N+4
os.environ["NAVER_CLIENT_ID"], os.environ["NAVER_CLIENT_SECRET"] = "x", "y"
trend.fetch_posts = lambda cfg, n, s: ({"kakao": 0}, [], trend.SRC_BOTH)
kd = lambda u: {"image_url": u, "thumbnail_url": "", "doc_url": u}
trend.photo_candidates = lambda n, s, p, addr="": [("etc", kd("https://k/1.jpg")), ("etc", kd("https://n/1.jpg"))]
c, sn = photos.candidates(a)
assert [x["hi"] for x in c] == ["https://k/1.jpg", "https://n/1.jpg"], c

# 네이버 실패 → 카카오만
def fail(*a, **k):
    raise OSError("quota")
photos.naver_search = fail
c, _ = photos.candidates(a)
assert [x["hi"] for x in c] == ["https://k/1.jpg", "https://n/1.jpg"], c
assert photos.SHEET_N == 16
print("F08 OK")

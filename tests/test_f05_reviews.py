"""F05 자체검사: python -m tests.test_f05_reviews (외부 호출 없음)."""
from datetime import date, timedelta
from src import trend, rank
from src.common import load_config

P = lambda title, body="", src="kakao": {"title": title, "description": body, "src": src, "postdate": date.today().strftime("%Y%m%d"), "url": title}
addr = "서울 강남구 압구정로30길 16"

# 1) 이름 일치: 띄어쓰기 그대로, 다른 글자에 붙으면 아님, 뒤 조사는 허용
yes = ["압구정떡볶이 다녀옴 압구정로30길", "압구정떡볶이에서 먹음, 압구정로30길 골목"]
no = ["압구정 떡볶이 맛집 추천 압구정로30길", "신압구정떡볶이 압구정로30길", "압구정떡볶이 맛집 추천"]  # 마지막: 이름 밖 위치 단서 없음
for t in yes:
    assert trend.is_about(P(t), "압구정떡볶이", "압구정", addr), t
for t in no:
    assert not trend.is_about(P(t), "압구정떡볶이", "압구정", addr), t
# 짧은 이름: 제목에 있어야 하고, 대왕족발·세종대왕은 아님
assert trend.is_about(P("신사 대왕 이자카야 후기"), "대왕", "신사")
assert trend.is_about(P("대왕은 처음", "신사역 근처"), "대왕", "신사")
for t in ("신사 대왕족발", "세종대왕 신사", "신사 맛집"):
    assert not trend.is_about(P(t), "대왕", "신사"), t
assert not trend.is_about(P("신사 맛집", "대왕 이자카야"), "대왕", "신사")  # 제목에 없음
# 지점명이 붙은 이름은 상호(첫 단어)로
assert trend.is_about(P("탄주 고속터미널 2호점 야키토리 고속터미널역"), "탄주 고속터미널 2호점", "고속터미널")
assert not trend.is_about(P("탄주 야키토리 고속터미널"), "탄주 고속터미널 2호점", "고속터미널")  # 상호만으론 어느 지점인지 모름
assert not trend.is_about(P("스타벅스 신메뉴 압구정"), "스타벅스 압구정역점", "압구정")  # 다른 지점일 수 있음
assert trend.is_about(P("스타벅스 압구정역점 방문", "압구정 카페"), "스타벅스 압구정역점", "압구정")

# 2) 출처별 보정: 카카오 10건 중 1건, 네이버 10건 중 5건이 이 가게 글
posts = [P("압구정떡볶이 압구정역", src="kakao")] + [P("압구정 떡볶이", src="kakao")] * 9 \
      + [P("압구정떡볶이 압구정역", src="naver")] * 5 + [P("다른 글", src="naver")] * 5
res = trend.analyze(load_config(), {"kakao": 1000, "naver": 200}, posts, "압구정떡볶이", "압구정", addr)
assert res["reviews_total"] == 1000 * 1 // 10 + 200 * 5 // 10, res

# 3) 네이버 실패 시 카카오만
trend.kakao_search = lambda *a, **k: {"meta": {"total_count": 7, "is_end": True}, "documents": []}
def fail(*a, **k):
    raise OSError("quota")
trend.naver_search = fail
import os
os.environ["NAVER_CLIENT_ID"], os.environ["NAVER_CLIENT_SECRET"] = "x", "y"
total, _, src = trend.fetch_posts(load_config(), "압구정떡볶이", "압구정")
assert (total, src) == ({"kakao": 7}, trend.SRC_KAKAO), (total, src)

# 4) 주간 증가: 5일 미만 간격이면 None, 7일 전과는 비교
d = lambda n: (date.today() - timedelta(days=n)).isoformat()
row = lambda n, v: {"date": d(n), "place_id": "p", "field": "reviews_total", "value": str(v), "source": trend.SRC_BOTH}
assert rank.weekly_growth([row(2, 100), row(0, 900)])["p"] is None
assert rank.weekly_growth([row(7, 100), row(2, 500), row(0, 130)])["p"] == 30
print("F05 OK")

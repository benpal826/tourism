"""F14 자체검사: python -m tests.test_f14_notes (외부 호출 없음, 실데이터 안 건드림)."""
import json, tempfile
from datetime import date
from pathlib import Path
from src import photos, trend
from src.common import ROOT, read_rows, latest

tmp = Path(tempfile.mkdtemp())
(tmp / "docs").mkdir()
cards = [{"place_id": "k1", "tier": "1", "category": "식당"}, {"place_id": "k2", "tier": "1", "category": "카페"}]
(tmp / "docs" / "cards.json").write_text(json.dumps(cards), encoding="utf-8")
orig_root, orig_out = photos.ROOT, photos.OUT
photos.ROOT, photos.OUT = tmp, tmp / "out"
photos.latest_cands = lambda p: {"k1": {"name": "하늘집", "station": "신사", "category": "식당"},
                                 "k2": {"name": "구름카페", "station": "신사", "category": "카페"}}
today = date.today().strftime("%Y%m%d")
long = "가" * 300
trend.fetch_posts = lambda cfg, n, s: ({}, [{"title": f"{n} 신사 후기 {i}", "description": long, "postdate": today, "url": str(i)}
                                         for i in range(20)], "x")

# 1) notes: 카드 상위 N곳, 곳당 발췌 최대 15개·260자, notes.json 저장
photos.notes(2)
book = json.loads((tmp / "out" / "notes.json").read_text(encoding="utf-8"))
assert list(book) == ["k1", "k2"] and len(book["k1"]["snippets"]) == 15, book.keys()
assert all(len(x) <= len(today) + 1 + 260 for x in book["k1"]["snippets"]), max(map(len, book["k1"]["snippets"]))
photos.ROOT, photos.OUT = orig_root, orig_out

# 2) summary 만 있는 import 는 사진을 건드리지 않음(todo.json 없어도 됨)
(tmp / "pick.json").write_text(json.dumps({"k1": {"summary": "한 줄 캐치\n맛: 김치찌개\n팁: 웨이팅 20분"}}), encoding="utf-8")
(tmp / "cards.json").write_text(json.dumps([{"place_id": "k1", "photo_food": "keep", "photo_source": "curated"}]), encoding="utf-8")
photos.import_file(tmp / "pick.json", data=tmp, docs=tmp, book_path=tmp / "없음.json")
a = latest(read_rows(tmp / "candidates.csv"))["k1"]
assert a == {"summary": "한 줄 캐치\n맛: 김치찌개\n팁: 웨이팅 20분"}, a
c = json.loads((tmp / "cards.json").read_text(encoding="utf-8"))[0]
assert c["photo_food"] == "keep" and c["summary"].startswith("한 줄 캐치"), c

# 3) 앱: 여러 줄이면 캐치프레이즈 + 항목, 한 줄이면 예전처럼
html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
assert "${desc(c.summary)}" in html and "<p class=catch>" in html and "(메뉴|가격|맛|분위기|팁|추천)" in html
print("F14 OK")

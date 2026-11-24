"""F04 자체검사: python -m tests.test_f04_photos (외부 호출 없음, 실데이터 안 건드림)."""
import json, tempfile
from pathlib import Path
from PIL import Image
from src import photos, trend
from src.common import ROOT, read_rows, latest

tmp = Path(tempfile.mkdtemp())

# 1) 모음 이미지: 번호 격자 한 장
photos.make_sheet([Image.new("RGB", (300, 200), c) for c in ("red", "green", "blue", "gray", "white")], tmp / "s.jpg")
im = Image.open(tmp / "s.jpg")
assert im.size == (photos.COLS * photos.TILE, 2 * photos.TILE), im.size

# 2) import: 번호→필드, 종류당 최대 2장, 범위 밖 번호 무시, 외관·기타는 '-', 카드 즉시 갱신
book = {"k1": {"name": "가게", "photos": [{"hi": f"https://x/{i}.jpg", "lo": f"https://t/{i}"} for i in range(1, 6)]}}
(tmp / "todo.json").write_text(json.dumps(book), encoding="utf-8")
(tmp / "pick.json").write_text(json.dumps({"k1": {"food": [1, 2, 3], "interior": [9], "mood": [4]}, "zz": {"food": [1]}}), encoding="utf-8")
(tmp / "cards.json").write_text(json.dumps([{"place_id": "k1", "photo_outside": "https://o|", "photo_etc": "e"},
                                             {"place_id": "k2", "photo_food": "keep"}]), encoding="utf-8")
photos.import_file(tmp / "pick.json", data=tmp, docs=tmp, book_path=tmp / "todo.json")
a = latest(read_rows(tmp / "candidates.csv"))["k1"]
assert a["photo_food"] == "https://x/1.jpg|https://t/1§https://x/2.jpg|https://t/2", a
assert a["photo_interior"] == "-" and a["photo_outside"] == "-" and a["photo_source"] == "curated", a
assert a["photo_mood"] == "https://x/4.jpg|https://t/4", a
c = json.loads((tmp / "cards.json").read_text(encoding="utf-8"))
assert "photo_outside" not in c[0] and "photo_interior" not in c[0] and c[0]["photo_source"] == "curated", c[0]
assert c[1] == {"place_id": "k2", "photo_food": "keep"}, c[1]

# 3) 주간 갱신: 선별된 곳은 자동 사진 수집을 건너뜀
def boom(*a, **k):
    raise AssertionError("선별된 곳에서 photos() 호출됨")
trend.photos, trend.thumb = boom, lambda n, s: ("", "")
trend.fetch_posts = lambda cfg, n, s: (100, [], "kakao-blog")
from src.common import load_config
trend.one(load_config(), "k1", {"tier": "1", "name": "가게", "station": "신사", "photo_source": "curated"}, False, {})

# 4) 앱: 선별은 종류 탭, 자동은 '사진' 하나
html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
assert '["food","메인요리"],["interior","인테리어"],["mood","분위기"]' in html
assert 'c.photo_source==="curated"?KINDS_CUR:KINDS_AUTO' in html
print("F04 OK")

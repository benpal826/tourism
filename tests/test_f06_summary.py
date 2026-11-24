"""F06 자체검사: python -m tests.test_f06_summary (외부 호출 없음, 실데이터 안 건드림)."""
import json, tempfile
from datetime import date
from pathlib import Path
from src import photos
from src.common import ROOT, read_rows, latest

a = {"name": "압구정면옥", "station": "압구정", "address": "서울 강남구 압구정로30길 16"}
today = date.today().strftime("%Y%m%d")
P = lambda t, d="": {"title": t, "description": d, "postdate": today}
posts = [P("압구정면옥 평양냉면 압구정역 후기", "육수가 깔끔"), P("압구정 냉면 맛집 추천", "다른 집"),
         P("압구정면옥 압구정 체험단", "협찬 받아"), P("압구정면옥 압구정역 웨이팅", "점심 20분")]
sn = photos.snippets(posts, a)
assert len(sn) == 2 and all("압구정면옥" in x for x in sn), sn  # 다른 가게 글·광고 글 제외

tmp = Path(tempfile.mkdtemp())
(tmp / "todo.json").write_text(json.dumps({"k1": {"name": "x", "photos": [{"hi": "h", "lo": "l"}], "snippets": sn}}), encoding="utf-8")
(tmp / "pick.json").write_text(json.dumps({"k1": {"food": [1], "summary": " 평양냉면 노포.\n점심 웨이팅 20분. "}}), encoding="utf-8")
(tmp / "cards.json").write_text(json.dumps([{"place_id": "k1"}]), encoding="utf-8")
photos.import_file(tmp / "pick.json", data=tmp, docs=tmp, book_path=tmp / "todo.json")
assert latest(read_rows(tmp / "candidates.csv"))["k1"]["summary"] == "평양냉면 노포.\n점심 웨이팅 20분."
assert json.loads((tmp / "cards.json").read_text(encoding="utf-8"))[0]["summary"].startswith("평양냉면")

html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
assert '${c.summary?`<p class=sum>${esc(c.summary)}</p>`:""}' in html
print("F06 OK")

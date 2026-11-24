"""카드 사진 선별 도구 (AI 가 후보 모음 이미지를 보고 고름).
  python -m src.photos todo [N]     미선별 카드 상위 N곳의 후보 사진 모음 → out/photos/<place_id>.jpg, out/photos/todo.json
  python -m src.photos import FILE  {"place_id": {"food":[번호..], "interior":[..], "mood":[..]}} 반영
고르는 기준: food=메인 요리(음식이 잘 보이는 것), interior=실내 공간·좌석, mood=조명·테이블 등 분위기.
외관·메뉴판·영수증·거리·안내문·사람 위주 사진은 고르지 않는다. 종류마다 최대 2장, 없으면 빈 목록.
"""
import io, json, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
from .common import *
from .run import latest_cands

KINDS = ("food", "interior", "mood")
OUT = ROOT / "out" / "photos"
SHEET_N, PER_POST, TILE, COLS = 12, 3, 300, 4


def fetch_img(url):
    from PIL import Image
    req = urllib.request.Request(url.replace("http://", "https://", 1), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        im = Image.open(io.BytesIO(r.read()))
        im.thumbnail((TILE, TILE))
        return im.convert("RGB")


def make_sheet(images, path):
    """번호(1부터) 붙인 격자 한 장."""
    from PIL import Image, ImageDraw, ImageFont
    rows = -(-len(images) // COLS)
    sheet = Image.new("RGB", (COLS * TILE, rows * TILE), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=40)
    for i, im in enumerate(images):
        x, y = i % COLS * TILE, i // COLS * TILE
        sheet.paste(im, (x + (TILE - im.width) // 2, y + (TILE - im.height) // 2))
        draw.rectangle((x, y, x + 56, y + 50), fill="black")
        draw.text((x + 8, y + 2), str(i + 1), fill="yellow", font=font)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, quality=85)


def candidates(name, station):
    from . import trend
    _, posts, _ = trend.fetch_posts(load_config(), name, station)
    out, per_post = [], {}
    for _, d in trend.photo_candidates(name, station, posts):
        pk = trend.url_key(d["doc_url"])
        if per_post.get(pk, 0) < PER_POST:  # 한 글에 몰리지 않게
            per_post[pk] = per_post.get(pk, 0) + 1
            out.append({"hi": d["image_url"], "lo": d.get("thumbnail_url", "")})
    return out[:SHEET_N + 4]  # 몇 장은 내려받기 실패 대비


def sheet_for(pid, a):
    loaded = []
    with ThreadPoolExecutor(8) as ex:
        def get(c):
            for u in (c["hi"], c["lo"]):
                try:
                    return c, fetch_img(u)
                except Exception:
                    continue
            return c, None
        for c, im in ex.map(get, candidates(a["name"], a.get("station", ""))):
            if im and len(loaded) < SHEET_N:
                loaded.append((c, im))
    if loaded:
        make_sheet([im for _, im in loaded], OUT / f"{pid}.jpg")
    return [c for c, _ in loaded]


def todo(n):
    cards = json.loads((ROOT / "docs" / "cards.json").read_text(encoding="utf-8"))
    cands = latest_cands(DATA / "candidates.csv")
    pending = [c["place_id"] for c in cards if c.get("tier") == "1"
               and cands.get(c["place_id"], {}).get("photo_source") != "curated"][:n]
    todo_path = OUT / "todo.json"
    book = json.loads(todo_path.read_text(encoding="utf-8")) if todo_path.exists() else {}
    for pid in pending:
        a = cands[pid]
        book[pid] = {"name": a["name"], "photos": sheet_for(pid, a)}
        print(f"{pid} {a['name']} [{a.get('kind', a.get('category', ''))}] 후보 {len(book[pid]['photos'])}장 → "
              + (str(OUT / f"{pid}.jpg") if book[pid]["photos"] else "사진 없음"))
    OUT.mkdir(parents=True, exist_ok=True)
    todo_path.write_text(json.dumps(book, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"요약: 미선별 카드 {len(pending)}곳 모음 이미지 생성. 고른 번호를 JSON 으로 만들어 import 하세요.")


def fields(photos, pick):
    """선별 번호 → 저장할 사진 필드. 빈 종류와 외관·기타는 '-'(이전 자동 사진을 덮는 표식)."""
    f = {"photo_outside": "-", "photo_etc": "-", "photo_source": "curated"}
    for k in KINDS:
        nums = [i for i in pick.get(k, []) if 1 <= i <= len(photos)][:2]
        f["photo_" + k] = "§".join(photos[i - 1]["hi"] + "|" + photos[i - 1]["lo"] for i in nums) or "-"
    return f


def import_file(path, data=DATA, docs=ROOT / "docs", book_path=OUT / "todo.json"):
    picks = json.loads(Path(path).read_text(encoding="utf-8"))
    book = json.loads(Path(book_path).read_text(encoding="utf-8"))
    rows, upd = [], {}
    for pid, pick in picks.items():
        if pid not in book:
            print(f"경고: {pid} 는 todo.json 에 없음(건너뜀)")
            continue
        upd[pid] = fields(book[pid]["photos"], pick)
        rows += [{"place_id": pid, "field": k, "value": v, "source": "photo-curated"} for k, v in upd[pid].items()]
    n = append_rows(Path(data) / "candidates.csv", rows)
    for name in ("cards.json", "history.json"):  # 다음 주간 갱신 전에도 앱에 바로 보이게
        p = Path(docs) / name
        if not p.exists():
            continue
        items = json.loads(p.read_text(encoding="utf-8"))
        for c in items:
            if c.get("place_id") in upd:
                for k, v in upd[c["place_id"]].items():
                    c.pop(k, None) if v == "-" else c.__setitem__(k, v)
        p.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"요약: {len(upd)}곳 사진 선별 반영 ({n}행 추가).")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "todo":
        todo(int(sys.argv[2]) if len(sys.argv) > 2 else 30)
    elif len(sys.argv) > 2 and sys.argv[1] == "import":
        import_file(sys.argv[2])
    else:
        raise SystemExit(__doc__)

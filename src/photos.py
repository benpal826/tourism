"""카드 사진 선별 도구 (AI 가 후보 모음 이미지를 보고 고름).
  python -m src.photos todo [N] [all]  (all: 이미 선별된 곳도 다시) 미선별 카드 상위 N곳의 후보 사진 모음 → out/photos/<place_id>.jpg, out/photos/todo.json
  python -m src.photos import FILE  {"place_id": {"food":[번호..], "interior":[..], "mood":[..], "summary": "2~3줄 요약"}} 반영
고르는 기준: food=메인 요리(음식이 잘 보이는 것), interior=실내 공간·좌석, mood=조명·테이블 등 분위기.
외관·메뉴판·영수증·거리·안내문·사람 위주 사진은 고르지 않는다. 종류마다 최대 2장, 없으면 빈 목록.
summary: todo 가 출력한 후기 요약만 근거로 2~3줄(어떤 곳·대표 메뉴·분위기·웨이팅/팁). 확인 안 되는 내용은 쓰지 않음.
"""
import io, json, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
from .common import *
from .run import latest_cands

KINDS = ("food", "interior", "mood")
OUT = ROOT / "out" / "photos"
SHEET_N, PER_POST, TILE, COLS = 16, 3, 300, 4


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


def naver_images(a):
    """네이버 이미지 검색 후보. 출처 글 주소가 없어서 제목에 가게 이름이 정확히 있는 것만(trend.is_about 기준)."""
    from . import trend
    name, station = a["name"], a.get("station", "")
    out = []
    for q in (f"{name} {station}", f"{name} {station} 메뉴", f"{name} {station} 내부"):
        try:
            items = naver_search("image", q, display=30, sort="sim").get("items", [])
        except Exception:
            return out  # 네이버 장애·한도 초과면 카카오 후보만
        for d in items:
            w, h = int(d.get("sizewidth") or 0), int(d.get("sizeheight") or 0)
            if trend.is_about({"title": d.get("title", "")}, name, station, a.get("address", ""))                     and trend.good_image({"width": w, "height": h}):
                out.append({"hi": d["link"], "lo": d.get("thumbnail", "")})
    return out


def snippets(posts, a, n=8):
    """이 가게로 확인된 최근 후기 요약(요약 작성용). 광고 문구 글 제외."""
    from . import trend
    cfg = load_config()
    out, seen = [], set()
    for p in sorted(posts, key=lambda p: p.get("postdate", ""), reverse=True):
        if not trend.is_about(p, a["name"], a.get("station", ""), a.get("address", "")):
            continue
        t = trend.clean(p["title"]) + " — " + trend.clean(p.get("description", ""))
        if trend.is_ad(t, cfg["trend"]["exclude_phrases"]) or t[:40] in seen:
            continue
        seen.add(t[:40])
        out.append(p.get("postdate", "") + " " + t[:220])
    return out[:n]


def candidates(a):
    """(사진 후보, 후기 요약). 카카오(확인된 후기 글의 사진) 먼저, 네이버 이미지로 보충."""
    from . import trend
    name, station = a["name"], a.get("station", "")
    _, posts, _ = trend.fetch_posts(load_config(), name, station)
    out, per_post, seen = [], {}, set()
    for _, d in trend.photo_candidates(name, station, posts):
        pk = trend.url_key(d["doc_url"])
        if per_post.get(pk, 0) < PER_POST:  # 한 글에 몰리지 않게
            per_post[pk] = per_post.get(pk, 0) + 1
            out.append({"hi": d["image_url"], "lo": d.get("thumbnail_url", "")})
    out = out[:SHEET_N // 2 + 2] if have_keys()["naver"] else out  # 네이버 몫을 남겨 둠
    for c in naver_images(a) if have_keys()["naver"] else []:
        out.append(c)
    uniq = []
    for c in out:
        if c["hi"] not in seen:
            seen.add(c["hi"])
            uniq.append(c)
    return uniq[:SHEET_N + 4], snippets(posts, a)  # 몇 장은 내려받기 실패 대비


def sheet_for(pid, a):
    cands, snips = candidates(a)
    loaded = []
    with ThreadPoolExecutor(8) as ex:
        def get(c):
            for u in (c["hi"], c["lo"]):
                try:
                    return c, fetch_img(u)
                except Exception:
                    continue
            return c, None
        for c, im in ex.map(get, cands):
            if im and len(loaded) < SHEET_N:
                loaded.append((c, im))
    if loaded:
        make_sheet([im for _, im in loaded], OUT / f"{pid}.jpg")
    return [c for c, _ in loaded], snips


def todo(n, redo=False):
    cards = json.loads((ROOT / "docs" / "cards.json").read_text(encoding="utf-8"))
    cands = latest_cands(DATA / "candidates.csv")
    pending = [c["place_id"] for c in cards if c.get("tier") == "1"
               and (redo or cands.get(c["place_id"], {}).get("photo_source") != "curated")][:n]
    todo_path = OUT / "todo.json"
    book = json.loads(todo_path.read_text(encoding="utf-8")) if todo_path.exists() else {}
    for pid in pending:  # 카드 순서(점수 높은 곳 먼저)
        a = cands[pid]
        ph, sn = sheet_for(pid, a)
        book[pid] = {"name": a["name"], "photos": ph, "snippets": sn}
        print(f"### {pid} {a['name']} [{a.get('kind', a.get('category', ''))}] 후보 {len(ph)}장 → "
              + (str(OUT / f"{pid}.jpg") if ph else "사진 없음"))
        for x in sn:
            print("-", x)
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
        if pick.get("summary"):
            upd[pid]["summary"] = pick["summary"].strip()
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
        todo(int(sys.argv[2]) if len(sys.argv) > 2 else 30, "all" in sys.argv[3:])  # all: 선별된 곳도 다시
    elif len(sys.argv) > 2 and sys.argv[1] == "import":
        import_file(sys.argv[2])
    else:
        raise SystemExit(__doc__)

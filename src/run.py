"""주간 갱신 단일 진입점: python -m src.run [--sample] [--import-swipes FILE]"""
import argparse, csv, json, math
from . import collect, trend, rank
from .common import *


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true", help="키 없이 샘플 데이터로 실행")
    ap.add_argument("--import-swipes", metavar="CSV", help="스와이프 결과 CSV(place_id,action,ts)를 places.csv에 반영")
    args = ap.parse_args()
    cfg, keys = load_config(), have_keys()
    sample = args.sample or not any(keys.values())

    if args.import_swipes:
        n = import_swipes(args.import_swipes)
        print(f"요약: 스와이프 {n}건을 data/places.csv 에 반영했습니다.")
        return

    url = env("SWIPE_SYNC_URL")  # Apps Script 웹앱 /exec 주소 (환경변수)
    if url and not args.sample:
        n = sync_swipes(url)
        print(f"시트에서 스와이프 {n}건 반영")

    base = DATA / "_sample" if sample else DATA  # 샘플은 실데이터와 섞이지 않게 별도 폴더
    cand_path, men_path, pl_path = base / "candidates.csv", base / "mentions.csv", base / "places.csv"
    n_c = append_rows(cand_path, collect.run(cfg, keys, sample))
    cands = latest_cands(cand_path)
    m_rows, d_rows = trend.run(cfg, cands, keys, sample)
    n_m = append_rows(men_path, m_rows)
    n_d = append_rows(cand_path, d_rows)
    cands = latest_cands(cand_path)
    out = ROOT / "out" / "sample" if sample else ROOT / "docs"
    out.mkdir(parents=True, exist_ok=True)
    cards = rank.build_cards(cfg, cands, read_rows(men_path), read_rows(pl_path),
                             out / "taste.md" if sample else ROOT / "taste.md")
    (out / "cards.json").write_text(json.dumps(cards, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "stations.json").write_text(json.dumps({st["name"]: st for st in cfg["nearby"]["stations"]},
                                                  ensure_ascii=False), encoding="utf-8")
    (out / "history.json").write_text(json.dumps(build_history(cands, read_rows(men_path), read_rows(pl_path)),
                                                 ensure_ascii=False, indent=1), encoding="utf-8")
    surge = [c for c in cards if c["surge"]]
    top = cards[:10]
    lines = [f"**요약: 후보 {len(cards)}곳(미확인), 급상승 {len(surge)}곳 — {'샘플' if sample else '실데이터'} 모드, 신규 행 {n_c + n_m + n_d}건.**\n",
             f"# 이번 주 추천 ({date.today().isoformat()})\n"]
    for c in top:
        lines.append(card_md(c))
    (out / "report.md" if sample else ROOT / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


def latest_cands(path):
    d = latest(read_rows(path))
    return {pid: {"place_id": pid, **a} for pid, a in d.items() if "name" in a}


def build_history(cands, mentions, places):
    """저장/패스한 곳을 카드 정보와 함께. 스와이프 앱의 기록 메뉴용.
    docs/ 는 공개 저장소(GitHub Pages)라 방문 점수·한줄평(개인 기록)은 넣지 않는다(places.csv 에만 보관)."""
    m = latest(mentions)
    last = {}
    for r in sorted(places, key=lambda r: r["date"]):
        if r["field"] == "swipe":
            last[r["place_id"]] = {"action": r["value"], "swiped": r["date"]}
    return [{"place_id": pid, **cands[pid], **m.get(pid, {}), **v}
            for pid, v in last.items() if pid in cands and v.get("action") in ("save", "pass")]


def card_md(c):
    period = f" · 기간 {c.get('period_start', '?')}~{c.get('period_end', '?')}" if c.get("period_end") or c.get("period_start") else ""
    dist = f" · {c['station']}역 {c['distance_m']}m" if c.get("distance_m") else f" · {c.get('station', '')}역 인근"
    g = c.get("weekly_growth")
    rev = f"\n  - 후기 {c['reviews_total']}건 (주간 {'+' + str(g) if g else '-'})" if c.get("reviews_total") else ""
    menu = f"\n  - 대표: {c['menu']} {c.get('price', '')} · 가격대 {c.get('price_band', '-')} (후기 {c.get('menu_date', '')} 기준)" if c.get("menu") else ""
    vibe = f"\n  - 분위기: {c['vibe']}" if c.get("vibe") else ""
    thumb = f"\n  - 사진: {c['thumb']}" if c.get("thumb") else ""
    return f"- {'🔥' if c.get('surge') else ''}**{c['name']}** [{c['category']}]{dist}{period}{rev}{menu}{vibe}{thumb}\n  - [카카오맵]({c['map_url']})"


def sync_swipes(url):
    import io, urllib.request
    with urllib.request.urlopen(url, timeout=30) as r:
        text = r.read().decode("utf-8")
    return import_swipes(io.StringIO(text))


def import_swipes(path):
    """시트/CSV(place_id,action,ts[,id])의 스와이프를 반영. date 에 전체 시각(초 단위)을 보존해
    같은 날 저장→패스→저장 번복도 마지막 값이 최신으로 남고, 같은 이벤트 재수신만 중복 제거된다."""
    rows = []
    f = open(path, newline="", encoding="utf-8") if isinstance(path, str) else path
    for r in csv.DictReader(f):
        act = {"right": "save", "left": "pass"}.get(r.get("action"), r.get("action"))
        pid, ts = (r.get("place_id") or "").strip(), (r.get("ts") or "").strip()
        if act not in ("save", "pass", "undo") or not pid or len(ts) < 10:
            continue  # 헤더 중복·잘못된 행 무시
        rows.append({"date": ts[:19].replace("Z", ""), "place_id": pid, "field": "swipe", "value": act, "source": "swipe"})
    return append_rows(DATA / "places.csv", rows)


if __name__ == "__main__":
    main()

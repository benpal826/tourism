"""주간 갱신 단일 진입점: python -m src.run [--sample] [--import-swipes FILE]"""
import argparse, csv, json
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

    cand_path, men_path, pl_path = DATA / "candidates.csv", DATA / "mentions.csv", DATA / "places.csv"
    n_c = append_rows(cand_path, collect.run(cfg, keys, sample))
    cands = latest_cands(cand_path)
    m_rows, d_rows = trend.run(cfg, cands, keys, sample)
    n_m = append_rows(men_path, m_rows)
    n_d = append_rows(cand_path, d_rows)
    cands = latest_cands(cand_path)
    cards = rank.build_cards(cfg, cands, read_rows(men_path), read_rows(pl_path))

    out = ROOT / "docs"
    out.mkdir(exist_ok=True)
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
    (ROOT / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


def latest_cands(path):
    d = latest(read_rows(path))
    return {pid: {"place_id": pid, **a} for pid, a in d.items() if "name" in a}


def build_history(cands, mentions, places):
    """저장/패스한 곳(+방문 점수·한줄평)을 카드 정보와 함께. 스와이프 앱의 기록 메뉴용."""
    m = latest(mentions)
    last = {}
    for r in sorted(places, key=lambda r: r["date"]):
        if r["field"] == "swipe":
            last[r["place_id"]] = {"action": r["value"], "swiped": r["date"]}
        elif r["field"] in ("score", "review"):
            last.setdefault(r["place_id"], {})[r["field"]] = r["value"]
    return [{"place_id": pid, **cands[pid], **m.get(pid, {}), **v}
            for pid, v in last.items() if pid in cands and "action" in v]


def card_md(c):
    period = f" · 기간 {c.get('period_start', '?')}~{c.get('period_end', '?')}" if c.get("period_end") or c.get("period_start") else ""
    dist = f" · {c['station']}역 {c['distance_m']}m" if c.get("distance_m") else f" · {c.get('station', '')}역 인근"
    g = c.get("weekly_growth")
    rev = f"\n  - 후기 {c['reviews_total']}건 (주간 {'+' + str(g) if g else '-'})" if c.get("reviews_total") else ""
    menu = f"\n  - 대표: {c['menu']} {c.get('price', '')} · 가격대 {c.get('price_band', '-')} (후기 언급 기준)" if c.get("menu") else ""
    vibe = f"\n  - 분위기: {c['vibe']}" if c.get("vibe") else ""
    thumb = f"\n  - 사진: {c['thumb']}" if c.get("thumb") else ""
    return f"- {'🔥' if c.get('surge') else ''}**{c['name']}** [{c['category']}]{dist}{period}{rev}{menu}{vibe}{thumb}\n  - [카카오맵]({c['map_url']})"


def sync_swipes(url):
    import io, urllib.request
    with urllib.request.urlopen(url, timeout=30) as r:
        text = r.read().decode("utf-8")
    return import_swipes(io.StringIO(text))


def import_swipes(path):
    rows = []
    f = open(path, newline="", encoding="utf-8") if isinstance(path, str) else path
    if True:
        for r in csv.DictReader(f):
            act = {"right": "save", "left": "pass"}.get(r.get("action"), r.get("action"))
            if act in ("save", "pass"):
                rows.append({"date": (r.get("ts") or "")[:10], "place_id": r.get("place_id"),
                             "field": "swipe", "value": act, "source": "swipe"})
    return append_rows(DATA / "places.csv", rows)


if __name__ == "__main__":
    main()

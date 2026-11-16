"""뉴스–공식 문서 연결 결과를 사람이 검수할 수 있게 뽑는다.

  python tools/link_review.py [건수]     최근 뉴스의 연결 결과 표 + 연결 안 됐지만 근접한 후보
  python tools/link_review.py --score    CSV 의 '사람_판정' 열로 오연결 비율 계산

'사람_판정' 에는 맞음 / 오연결(연결됐지만 다른 사안) / 누락(연결돼야 하는데 안 됨) 중 하나를 적는다.
"""
import csv
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402
from carbon import db, linking  # noqa: E402

OUT = Path(__file__).resolve().parent / "link_review.csv"


def make(n: int) -> None:
    conn = db.connect()
    now = datetime.now(timezone.utc)
    news = conn.execute(
        "SELECT id,title,published,official_status FROM articles WHERE source_type='news' "
        "ORDER BY published DESC LIMIT ?", (n,)).fetchall()
    officials = [dict(r) for r in conn.execute(
        "SELECT id,title,agency,published FROM articles WHERE source_type='official' AND published >= ?",
        ((now - timedelta(days=config.LINK_WINDOW_DAYS + config.LINK_AFTER_DAYS + 3)).isoformat(),))]
    links = {}
    for r in conn.execute("SELECT l.news_id, l.score, o.title, o.agency FROM article_links l JOIN articles o ON o.id=l.official_id ORDER BY l.score DESC"):
        links.setdefault(r["news_id"], []).append(r)

    rows, near = [], []
    for r in news:
        ls = links.get(r["id"], [])
        if ls:
            rows.append((r["title"], "연결됨", "; ".join(f"[{x['agency']}] {x['title']} ({x['score']:g})" for x in ls)))
            continue
        # 연결 안 된 뉴스 중 점수가 기준에 근접한 후보 (누락 가능성)
        best = max(((linking.score_pair(dict(r), o), o) for o in officials), key=lambda x: x[0][0], default=None)
        rows.append((r["title"], "공식 확인 안 됨", ""))
        if best and best[0][0] >= config.LINK_MIN_SCORE - 25:
            near.append((r["title"], best[1]["title"], best[0][0], best[0][1]))
    conn.close()

    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["뉴스 제목", "결과", "연결된 공식 문서(점수)", "사람_판정(맞음/오연결/누락)"])
        for t, s, l in rows:
            w.writerow([t, s, l, ""])
    n_linked = sum(1 for _, s, _ in rows if s == "연결됨")
    print(f"최근 뉴스 {len(rows)}건 중 연결됨 {n_linked}건, 공식 확인 안 됨 {len(rows) - n_linked}건\n")
    print("[연결된 뉴스]")
    for t, s, l in rows:
        if s == "연결됨":
            print(f"  뉴스: {t[:60]}\n  → {l[:110]}\n")
    if n_linked == 0:
        print("  (없음)\n")
    print(f"[연결은 안 됐지만 점수가 {config.LINK_MIN_SCORE - 25}점 이상인 근접 후보] — 누락일 수 있어 확인이 필요합니다")
    for t, o, s, ev in near:
        print(f"  뉴스: {t[:60]}\n  후보: {o[:60]}  ({s:g}점, 공유: 용어 {ev.get('entities')}, 숫자 {ev.get('numbers')}, 단어 {ev.get('tokens')})\n")
    if not near:
        print("  (없음)")
    print(f"저장: {OUT}")


def score() -> None:
    with OUT.open(encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["사람_판정(맞음/오연결/누락)"].strip()]
    linked = [r for r in rows if r["결과"] == "연결됨"]
    wrong = [r for r in linked if r["사람_판정(맞음/오연결/누락)"].strip() == "오연결"]
    miss = [r for r in rows if r["사람_판정(맞음/오연결/누락)"].strip() == "누락"]
    if linked:
        print(f"오연결 비율: {len(wrong)}/{len(linked)} = {len(wrong) / len(linked):.0%} (목표 10% 이하)")
    print(f"누락 표시: {len(miss)}건")


if __name__ == "__main__":
    if "--score" in sys.argv:
        score()
    else:
        make(int(next((a for a in sys.argv[1:] if a.isdigit()), 50)))

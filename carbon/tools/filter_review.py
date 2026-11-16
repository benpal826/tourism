"""무관 기사 필터(F6) 결과를 사람이 검수할 수 있게 뽑는다.

  python tools/filter_review.py [건수]    관련성 분포, 제외된 기사 표본, 미판정 표본
  python tools/filter_review.py --score   CSV 의 '사람_판정' 열로 오제외 비율 계산

'사람_판정' 에는 제외된 기사에 대해 맞음(정말 무관) / 오제외(관련 있는 기사를 잘못 제외) 를 적는다.
규칙은 config.py 의 RELEVANCE_RULES 에서 고치고 `python main.py refilter` 로 다시 적용한다.
"""
import csv
import random
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from carbon import db  # noqa: E402

OUT = Path(__file__).resolve().parent / "filter_review.csv"
COL = "사람_판정(맞음/오제외)"


def clean(title: str) -> str:
    return re.sub(r"\s+-\s+[^-]+$", "", title or "")


def main(n: int) -> None:
    conn = db.connect()
    rows = conn.execute(f"SELECT id,title,source,source_type,agency,relevant,relevance_reason,{db.EFFECTIVE_TOPICS} AS topics FROM articles").fetchall()
    conn.close()
    total = len(rows)
    dist = Counter({1: 0, 0: 0, None: 0})
    dist.update(r["relevant"] for r in rows)
    print(f"전체 {total}건: 관련 {dist[1]}건 · 무관(제외) {dist[0]}건 · 미판정 {dist[None]}건")
    kept = [r for r in rows if r["relevant"] != 0]
    tagged = sum(1 for r in kept if r["topics"])
    print(f"주제 태깅률(제외 후 기준): {tagged / len(kept):.1%} ({tagged}/{len(kept)})")
    reasons = Counter(re.sub(r"\(.*", "", r["relevance_reason"] or "없음") for r in rows)
    print("판정 근거:", dict(reasons.most_common()))

    rng = random.Random(11)
    excluded = [r for r in rows if r["relevant"] == 0]
    sample = rng.sample(excluded, min(n, len(excluded)))
    print(f"\n[제외된 기사 {len(excluded)}건 중 {len(sample)}건] — 관련 있는 기사가 섞여 있는지 확인해 주세요")
    for r in sample:
        who = r["agency"] if r["source_type"] == "official" else "뉴스"
        print(f"  {r['relevance_reason']:<38} [{who}] {clean(r['title'])[:62]}")
    if not excluded:
        print("  (없음)")

    undecided = [r for r in rows if r["relevant"] is None]
    pick = rng.sample(undecided, min(n, len(undecided)))
    print(f"\n[미판정 {len(undecided)}건 중 {len(pick)}건] — 제목만으로는 판단할 수 없어 집계에 남겨 둔 기사 (이후 LLM 단계가 판정)")
    for r in pick:
        print(f"  {r['relevance_reason']:<28} {clean(r['title'])[:70]}")

    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "구분", "제목", "판정 근거", COL])
        for r in sample:
            w.writerow([r["id"], r["source_type"], clean(r["title"]), r["relevance_reason"], ""])
    print(f"\n저장: {OUT}  (제외 표본 {len(sample)}건)")


def score() -> None:
    with OUT.open(encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r[COL].strip()]
    if not rows:
        print(f"'{COL}' 열이 비어 있습니다.")
        return
    wrong = sum(1 for r in rows if r[COL].strip() == "오제외")
    print(f"오제외: {wrong}/{len(rows)} = {wrong / len(rows):.0%}  (목표: 20건 중 1건 이하)")


if __name__ == "__main__":
    if "--score" in sys.argv:
        score()
    else:
        main(int(next((a for a in sys.argv[1:] if a.isdigit()), 20)))

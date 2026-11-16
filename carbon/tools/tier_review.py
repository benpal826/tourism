"""출처 신뢰도 등급(F13) 결과를 사람이 검수할 수 있게 뽑는다.

  python tools/tier_review.py [건수]

수집 건수 상위 언론사의 등급과 근거를 표로 보여주고, 사람이 보정이 필요할 수 있는 곳을 따로 모은다.
틀린 등급은 config.py 의 SOURCE_TIER_OVERRIDES 에 {"언론사명 또는 도메인": 등급} 으로 적고 `python main.py tiers` 를 다시 실행한다.
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402
from carbon import db, tiers  # noqa: E402

OUT = Path(__file__).resolve().parent / "tier_review.csv"


def main(n: int) -> None:
    conn = db.connect()
    rows = conn.execute(
        "SELECT source, source_tier t, source_tier_reason why, COUNT(*) n, "
        "MAX(source_url) url, SUM(sensational IS NOT NULL AND sensational <> '') sens "
        "FROM articles WHERE source_type='news' GROUP BY source ORDER BY n DESC, source").fetchall()
    total_news = sum(r["n"] for r in rows)
    with_url = conn.execute("SELECT COUNT(*) FROM articles WHERE source_type='news' AND source_url IS NOT NULL AND source_url<>''").fetchone()[0]
    conn.close()

    by_tier = {}
    for r in rows:
        by_tier.setdefault(r["t"], []).append(r)
    print(f"뉴스 {total_news}건, 언론사 {len(rows)}곳 (언론사 주소를 아는 기사 {with_url}건)")
    print("등급별 언론사 수 / 기사 수:", {tiers.TIER_LABELS.get(t, t): (len(v), sum(x['n'] for x in v)) for t, v in sorted(by_tier.items(), key=lambda x: (x[0] is None, x[0]))})

    print(f"\n[수집 건수 상위 {n}곳]")
    print("| 건수 | 언론사 | 등급 | 근거 | 도메인 |\n|---|---|---|---|---|")
    for r in rows[:n]:
        print(f"| {r['n']} | {r['source'][:30]} | {tiers.TIER_LABELS.get(r['t'], '?')} | {r['why']} | {tiers.domain_of(r['url'] or '') or tiers.domain_of(r['source'])} |")

    print("\n[3등급(단체·업계 주장)으로 분류된 모든 언론사]  — 집계에서 제외되는 곳이라 가장 먼저 확인해 주세요")
    for r in by_tier.get(3, []):
        print(f"  {r['n']:>3}건  {r['source']}  ← {r['why']}")
    if not by_tier.get(3):
        print("  (없음)")

    freq_only = [r for r in by_tier.get(2, []) if r["why"].startswith("freq")]
    print("\n[빈도만으로 2등급이 된 곳]  — 많이 나온다는 것이 믿을 만하다는 뜻은 아니라서, 아는 곳이면 확인해 주세요")
    for r in freq_only:
        print(f"  {r['n']:>3}건  {r['source']}  ← {r['why']}")
    if not freq_only:
        print("  (없음)")

    review = [r for r in rows if "review:" in (r["why"] or "")]
    print("\n[연구소·센터처럼 단체일 수도 언론일 수도 있어 자동으로 바꾸지 않은 곳]")
    for r in review:
        print(f"  {r['n']:>3}건  {r['source']}  ← {r['why']}")
    if not review:
        print("  (없음)")

    sens = [r for r in rows if r["sens"]]
    print(f"\n[제목에 자극적 표현이 있는 기사가 있는 언론사]  (표시만 하고 점수에는 쓰지 않음)")
    for r in sens[:15]:
        print(f"  {r['sens']:>3}건  {r['source']} ({tiers.TIER_LABELS.get(r['t'], '?')})")
    if not sens:
        print("  (없음)")

    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["언론사", "기사 수", "자동 등급", "근거", "도메인", "사람_등급(공식=1/일반=2/단체·업계=3/미분류=0)"])
        for r in rows:
            w.writerow([r["source"], r["n"], tiers.TIER_LABELS.get(r["t"], r["t"]), r["why"],
                        tiers.domain_of(r["url"] or "") or tiers.domain_of(r["source"]), ""])
    print(f"\n저장: {OUT}  (전체 {len(rows)}곳)")


if __name__ == "__main__":
    main(int(next((a for a in sys.argv[1:] if a.isdigit()), 50)))

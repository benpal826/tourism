"""공식 문서 판정(정책 단계·국내 영향도)을 사람이 검수할 수 있게 표로 뽑는다.

  python tools/stage_review.py [건수]

기관이 골고루 섞이도록 기관별로 번갈아 뽑는다. 결과는 tools/stage_review.csv 에 저장되고,
'사람_단계', '사람_영향도' 열에 정답을 적으면 정확도를 계산할 수 있다 (python tools/stage_review.py --score).
"""
import csv
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from carbon import db, policy  # noqa: E402

OUT = Path(__file__).resolve().parent / "stage_review.csv"
STAGE_KO = {**policy.STAGE_LABELS}
IMPACT_KO = {**policy.IMPACT_LABELS}
ANSWER_STAGE = {"추진": "proposed", "확정": "decided", "미분류": "unknown"}
ANSWER_IMPACT = {"직접규제": "direct", "직접 규제": "direct", "간접": "indirect", "참고": "reference", "미분류": "unknown"}


def sample(n: int) -> list:
    conn = db.connect()
    rows = conn.execute(
        "SELECT id,agency,query,title,policy_stage,domestic_impact,impact_score,impact_keyword,published "
        "FROM articles WHERE source_type='official' ORDER BY published DESC").fetchall()
    conn.close()
    by_agency = defaultdict(list)
    for r in rows:
        by_agency[r["agency"]].append(r)
    rng = random.Random(7)                       # 매번 같은 표가 나오게 고정
    for lst in by_agency.values():
        rng.shuffle(lst)
    picked = []
    while len(picked) < n and any(by_agency.values()):
        for agency in sorted(by_agency):
            if by_agency[agency] and len(picked) < n:
                picked.append(by_agency[agency].pop())
    return picked


def make(n: int) -> None:
    rows = sample(n)
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "기관", "게시판", "제목", "판정_단계", "판정_영향도", "점수", "근거키워드", "사람_단계(추진/확정/미분류)", "사람_영향도(직접규제/간접/참고/미분류)"])
        for r in rows:
            w.writerow([r["id"], r["agency"], r["query"], r["title"], STAGE_KO.get(r["policy_stage"], r["policy_stage"]),
                        IMPACT_KO.get(r["domestic_impact"], r["domestic_impact"]), r["impact_score"] or "",
                        r["impact_keyword"] or "", "", ""])
    print(f"| # | 기관 | 제목 | 단계 | 영향도(점수, 근거) |\n|---|---|---|---|---|")
    for i, r in enumerate(rows, 1):
        imp = IMPACT_KO.get(r["domestic_impact"], "?")
        if r["impact_keyword"]:
            imp += f" ({r['impact_score']:g}, {r['impact_keyword']})"
        print(f"| {i} | {r['agency']} | {r['title'][:46]} | {STAGE_KO.get(r['policy_stage'], '?')} | {imp} |")
    print(f"\n저장: {OUT}")
    borderline()


def borderline() -> None:
    """점수가 직접/간접, 간접/참고의 경계(±IMPACT_BORDER) 근처인 키워드: 사람이 기준을 정해 줘야 하는 애매한 사례."""
    import config
    conn = db.connect()
    rows = conn.execute("SELECT impact_keyword kw, impact_score s, domestic_impact d, COUNT(*) n, MIN(title) sample "
                        "FROM articles WHERE source_type='official' AND impact_score IS NOT NULL "
                        "GROUP BY impact_keyword ORDER BY impact_score DESC").fetchall()
    conn.close()
    edges = sorted(config.IMPACT_BANDS.values())
    near = [r for r in rows if any(abs(r["s"] - e) <= config.IMPACT_BORDER for e in edges)]
    print(f"\n[경계 사례] 점수가 {edges} ±{config.IMPACT_BORDER} 안인 키워드 (현재 판정은 점수 기준일 뿐이라 사람이 확인해 주세요)")
    for r in near:
        print(f"  - {r['kw']} ({r['s']:g}점 → {IMPACT_KO.get(r['d'])}) {r['n']}건. 예: {r['sample'][:44]}")
    if not near:
        print("  (없음)")


def score() -> None:
    with OUT.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    done = [r for r in rows if r["사람_단계(추진/확정/미분류)"].strip()]
    if not done:
        print("사람_단계 열이 비어 있습니다.")
        return
    stage_ok = sum(ANSWER_STAGE.get(r["사람_단계(추진/확정/미분류)"].strip()) == {v: k for k, v in STAGE_KO.items()}.get(r["판정_단계"], r["판정_단계"]) for r in done)
    print(f"단계 정확도: {stage_ok}/{len(done)} = {stage_ok / len(done):.0%}")
    imp_done = [r for r in done if r["사람_영향도(직접규제/간접/참고/미분류)"].strip()]
    if imp_done:
        imp_ok = sum(ANSWER_IMPACT.get(r["사람_영향도(직접규제/간접/참고/미분류)"].strip()) == {v: k for k, v in IMPACT_KO.items()}.get(r["판정_영향도"], r["판정_영향도"]) for r in imp_done)
        print(f"영향도 정확도: {imp_ok}/{len(imp_done)} = {imp_ok / len(imp_done):.0%}")


if __name__ == "__main__":
    if "--score" in sys.argv:
        score()
    else:
        make(int(next((a for a in sys.argv[1:] if a.isdigit()), 30)))

"""LLM 분류·요약(F5) 결과를 사람이 검수할 수 있게 뽑는다.

  python tools/llm_review.py [건수]    사용량·비용, 규칙 판정과 LLM 판정의 일치율, 표본 표
  python tools/llm_review.py --score   CSV 의 '사람_*' 열로 LLM 의 관련성·주제 정확도를 계산

표본 CSV(tools/llm_review.csv)에는 사람이 정답을 적는 열이 있다.
  사람_관련성: 관련 / 무관     사람_주제_맞음: 예 / 아니오 (LLM 이 붙인 주제가 맞는지)
완료 기준: 관련성 90% 이상, 주제 태깅률 85% 이상 (tools/baseline.py).
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

OUT = Path(__file__).resolve().parent / "llm_review.csv"
C_REL, C_TOPIC = "사람_관련성(관련/무관)", "사람_주제_맞음(예/아니오)"


def clean(t: str) -> str:
    return re.sub(r"\s+-\s+[^-]+$", "", t or "")


def main(n: int) -> None:
    conn = db.connect()
    done = conn.execute("SELECT * FROM articles WHERE llm_done_at IS NOT NULL").fetchall()
    total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    usage = conn.execute("SELECT COALESCE(SUM(calls),0) c, COALESCE(SUM(input_tokens),0) i, COALESCE(SUM(output_tokens),0) o, "
                         "COALESCE(SUM(cost_usd),0) usd FROM llm_usage").fetchone()
    print(f"LLM 처리: {len(done)}건 / 전체 {total}건 | 누적 호출 {usage['c']}회, 입력 {usage['i']:,}·출력 {usage['o']:,} 토큰, 추정 비용 ${usage['usd']:.4f}")
    if usage["c"]:
        print(f"호출당 평균: 입력 {usage['i'] / usage['c']:.0f}·출력 {usage['o'] / usage['c']:.0f} 토큰, ${usage['usd'] / usage['c']:.4f}")
    if not done:
        print("아직 LLM 이 처리한 기사가 없습니다. 인증 정보를 설정하고 `python main.py enrich --limit 3` 으로 먼저 시험해 보세요.")
        conn.close()
        return

    # 규칙 판정과 LLM 판정이 얼마나 일치하는가 (규칙이 판정한 것만 비교)
    both = [r for r in done if r["relevant"] in (0, 1) and r["llm_relevant"] is not None and not (r["relevance_reason"] or "").startswith("llm")]
    agree = sum(1 for r in both if r["relevant"] == r["llm_relevant"])
    if both:
        print(f"관련성: 규칙이 판정한 {len(both)}건 중 LLM 과 일치 {agree}건 ({agree / len(both):.0%})")
    diff = [r for r in both if r["relevant"] != r["llm_relevant"]]
    print(f"규칙과 LLM 이 다르게 판정한 관련성 {len(diff)}건")
    for r in diff[:10]:
        print(f"  규칙={'관련' if r['relevant'] else '무관'} LLM={'관련' if r['llm_relevant'] else '무관'}  {clean(r['title'])[:56]}  | {r['llm_reason']}")
    stage_diff = [r for r in done if r["source_type"] == "official" and r["llm_stage"] not in (None, "unknown") and r["policy_stage"] not in (None, "unknown")
                  and r["llm_stage"] != r["policy_stage"]]
    print(f"공식 문서 정책 단계 불일치 {len(stage_diff)}건" + ("" if not stage_diff else " (규칙 값 유지, 비교용으로 보관)"))
    for r in stage_diff[:5]:
        print(f"  규칙={r['policy_stage']} LLM={r['llm_stage']}  {clean(r['title'])[:56]}")

    rng = random.Random(5)
    sample = rng.sample(done, min(n, len(done)))
    print(f"\n[표본 {len(sample)}건]")
    print("| # | 제목 | 규칙 주제 → LLM 주제 | 관련성(규칙→LLM) | 중요도 | 요약 |\n|---|---|---|---|---|---|")
    for i, r in enumerate(sample, 1):
        rel = {1: "관련", 0: "무관", None: "미판정"}
        print(f"| {i} | {clean(r['title'])[:40]} | {r['topics'] or '-'} → {r['llm_topics'] or '-'} | "
              f"{rel[r['relevant']]}→{'관련' if r['llm_relevant'] else '무관'} | {r['llm_impact']} | {r['llm_summary']} |")
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "제목", "LLM 관련성", "LLM 주제", "LLM 요약", "LLM 근거", C_REL, C_TOPIC])
        for r in sample:
            w.writerow([r["id"], clean(r["title"]), "관련" if r["llm_relevant"] else "무관", r["llm_topics"], r["llm_summary"], r["llm_reason"], "", ""])
    print(f"\n저장: {OUT}")
    conn.close()


def score() -> None:
    with OUT.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    rel = [r for r in rows if r[C_REL].strip()]
    if rel:
        ok = sum(1 for r in rel if r[C_REL].strip() == r["LLM 관련성"])
        print(f"관련성 정확도: {ok}/{len(rel)} = {ok / len(rel):.0%}  (목표 90% 이상)")
    top = [r for r in rows if r[C_TOPIC].strip()]
    if top:
        ok = sum(1 for r in top if r[C_TOPIC].strip() == "예")
        print(f"주제 정확도: {ok}/{len(top)} = {ok / len(top):.0%}")
    if not rel and not top:
        print("사람_* 열이 비어 있습니다.")


if __name__ == "__main__":
    if "--score" in sys.argv:
        score()
    else:
        main(int(next((a for a in sys.argv[1:] if a.isdigit()), 10)))

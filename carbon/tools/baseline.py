"""정확도 개선 전 현재 상태(기준선)를 측정한다. 기존 코드는 수정하지 않는다.

  python tools/baseline.py

출력: 전체 기사 수, 주제 태깅률, 지역 태그 없는 비율, 검색어별 태깅률
저장: tools/sample_untagged.csv  (주제 태그가 없는 기사 무작위 50건, 사람_판정 열을 직접 채운다)
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from carbon import db  # noqa: E402

OUT = Path(__file__).resolve().parent / "sample_untagged.csv"
SAMPLE_SIZE = 50


def main() -> None:
    conn = db.connect()
    total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    if total == 0:
        print("기사가 없습니다. 먼저 python main.py collect 를 실행하세요.")
        return
    # 주제 태그는 LLM 이 처리한 기사는 LLM 의 최종 목록을, 아니면 키워드 규칙의 태그를 쓴다 (리포트와 같은 기준)
    topic_tagged = conn.execute(f"SELECT COUNT(*) FROM articles WHERE COALESCE({db.EFFECTIVE_TOPICS},'') <> ''").fetchone()[0]
    region_tagged = conn.execute("SELECT COUNT(*) FROM articles WHERE COALESCE(regions,'') <> ''").fetchone()[0]
    ko = conn.execute("SELECT COUNT(*) FROM articles WHERE lang='ko'").fetchone()[0]

    print(f"전체 기사: {total}건 (한국어 {ko}, 영어 {total - ko})")
    print(f"주제 태깅률: {topic_tagged / total:.1%} ({topic_tagged}/{total})")
    # 무관 기사 필터(F6) 이후에는 '제외되지 않은 기사' 기준 태깅률이 공식 지표다 (PRD 성공 지표)
    kept = conn.execute("SELECT COUNT(*) FROM articles WHERE relevant IS NOT 0").fetchone()[0]
    kept_tagged = conn.execute(f"SELECT COUNT(*) FROM articles WHERE relevant IS NOT 0 AND COALESCE({db.EFFECTIVE_TOPICS},'') <> ''").fetchone()[0]
    llm_done = conn.execute("SELECT COUNT(*) FROM articles WHERE llm_done_at IS NOT NULL").fetchone()[0]
    print(f"LLM 이 처리한 기사: {llm_done}건 (나머지는 키워드 규칙 태그)")
    if kept != total:
        print(f"무관 기사 {total - kept}건 제외 후 주제 태깅률: {kept_tagged / kept:.1%} ({kept_tagged}/{kept})  ← 성공 지표 기준")
    print(f"지역 태그 없는 비율: {(total - region_tagged) / total:.1%}")

    print("\n[검색어별 주제 태깅률]  (낮은 검색어는 무관 기사가 많이 섞였을 가능성)")
    rows = conn.execute(
        "SELECT query, COUNT(*) n, SUM(COALESCE(topics,'') <> '') t FROM articles "
        "GROUP BY query ORDER BY 1.0 * SUM(COALESCE(topics,'') <> '') / COUNT(*)"
    ).fetchall()
    for r in rows:
        print(f"  {r['t'] / r['n']:>6.1%}  {r['t']:>3}/{r['n']:<3}  {r['query']}")

    sample = conn.execute(
        "SELECT id, title, source, query FROM articles WHERE COALESCE(topics,'') = '' "
        "ORDER BY RANDOM() LIMIT ?", (SAMPLE_SIZE,)
    ).fetchall()
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "title", "source", "query", "사람_판정(관련/무관)"])
        for r in sample:
            w.writerow([r["id"], r["title"], r["source"], r["query"], ""])
    print(f"\n태그 없는 기사 {len(sample)}건을 저장했습니다: {OUT}")
    print("'사람_판정' 열에 관련/무관을 적으면 F6(무관 기사 필터)의 정답 데이터로 쓸 수 있습니다.")
    conn.close()


if __name__ == "__main__":
    main()

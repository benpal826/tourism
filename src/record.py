"""방문 후 한 줄 평·점수 기록: python -m src.record "가게명" 4 "한 줄 평" """
import sys
from .common import *
from .run import latest_cands


def main():
    if len(sys.argv) < 3:
        raise SystemExit("사용: python -m src.record 가게명 점수(1-5) [한줄평]")
    name, score = sys.argv[1], sys.argv[2]
    review = " ".join(sys.argv[3:])
    cands = latest_cands(DATA / "candidates.csv")
    hits = [p for p, a in cands.items() if name in a["name"]]
    if len(hits) != 1:
        raise SystemExit(f"요약: '{name}' 일치 {len(hits)}건 — 더 정확한 이름으로 다시 시도하세요. {[cands[h]['name'] for h in hits]}")
    pid = hits[0]
    n = append_rows(DATA / "places.csv", [
        {"place_id": pid, "field": "score", "value": score, "source": "visit"},
        {"place_id": pid, "field": "review", "value": review, "source": "visit"}])
    print(f"요약: {cands[pid]['name']} 점수 {score} 기록({n}행).")


if __name__ == "__main__":
    main()

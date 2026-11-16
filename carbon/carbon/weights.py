"""국내 영향도 키워드 가중치: 초기값(seed)을 누적 데이터로 조금씩 갱신한다 (F12).

'학습'은 머신러닝이 아니라 누적 지표 기반 점수다. 근거는 keyword_weights.evidence 에 JSON 으로 남아 왜 그 값인지 볼 수 있다.

키워드마다 세 지표를 구한다 (최근 30일 기사 기준).
  1) 언급 빈도의 백분위: 모든 기사에서 얼마나 자주 나오는가
  2) 공식 문서 언급의 백분위: 정부·국회 문서에서 얼마나 자주 나오는가
  3) 확정 비율: 공식 문서 중 단계가 판정된 것 가운데 '확정'의 비율
학습값은 이 지표들의 평균이고, 최종값 = seed × (1 - 학습 비율) + 학습값 × 학습 비율 이다.
"""
import csv
import json
import logging
from datetime import datetime, timedelta, timezone

import config
from . import policy

log = logging.getLogger(__name__)
WINDOW_DAYS = 30


def ensure_seeds(conn) -> None:
    """config 의 seed 를 테이블에 반영한다. 새 키워드는 추가하고, 기존 키워드는 seed 만 갱신(학습값은 유지)."""
    now = datetime.now(timezone.utc).isoformat()
    for kw, seed in policy.seed_weights().items():
        row = conn.execute("SELECT learned_weight FROM keyword_weights WHERE keyword=?", (kw,)).fetchone()
        if row is None:
            conn.execute("INSERT INTO keyword_weights (keyword,seed_weight,learned_weight,final_weight,updated_at) VALUES (?,?,?,?,?)",
                         (kw, seed, None, seed, now))
        else:
            final = _final(seed, row["learned_weight"])
            conn.execute("UPDATE keyword_weights SET seed_weight=?, final_weight=? WHERE keyword=?", (seed, final, kw))
    conn.commit()


def _final(seed: float, learned: float | None) -> float:
    if learned is None:
        return seed
    value = seed * (1 - config.IMPACT_LEARN_RATE) + learned * config.IMPACT_LEARN_RATE
    if seed >= config.IMPACT_TOP_SEED:
        value = max(value, config.IMPACT_FLOOR)       # 최상위 키워드는 하한 아래로 내려가지 않는다
    return round(value, 1)


def load_weights(conn) -> dict[str, float]:
    """판정에 쓸 키워드별 최종 가중치. 테이블에 없는 키워드는 config 의 seed 를 쓴다. 파일·DB 를 바꾸지 않는다."""
    weights = policy.seed_weights()
    for r in conn.execute("SELECT keyword, final_weight FROM keyword_weights"):
        if r["keyword"] in weights:                    # 설정에서 삭제된 키워드는 무시
            weights[r["keyword"]] = r["final_weight"]
    return weights


def history_days(conn) -> int:
    row = conn.execute("SELECT MIN(collected) lo, MAX(collected) hi FROM articles").fetchone()
    if not row or not row["lo"]:
        return 0
    return (datetime.fromisoformat(row["hi"]) - datetime.fromisoformat(row["lo"])).days


def _percentiles(values: dict[str, int]) -> dict[str, float]:
    """값의 크기 순위를 0~100 점으로 바꾼다 (동률은 평균 순위)."""
    n = len(values)
    out = {}
    for k, v in values.items():
        below = sum(1 for x in values.values() if x < v)
        equal = sum(1 for x in values.values() if x == v)
        out[k] = 100.0 * (below + (equal - 1) / 2) / max(n - 1, 1)
    return out


def compute_learned(conn, now: datetime | None = None) -> tuple[dict[str, tuple[float | None, dict]], str]:
    """키워드별 (학습값 또는 None, 근거). 두 번째 값은 학습하지 못한 이유 (학습했으면 빈 문자열)."""
    now = now or datetime.now(timezone.utc)
    seeds = policy.seed_weights()
    days = history_days(conn)
    if days < config.IMPACT_MIN_HISTORY_DAYS:
        return {k: (None, {}) for k in seeds}, f"누적 기간 {days}일 < {config.IMPACT_MIN_HISTORY_DAYS}일: seed 만 사용"

    since = (now - timedelta(days=WINDOW_DAYS)).isoformat()
    rows = conn.execute("SELECT title, source_type, policy_stage FROM articles WHERE published >= ?", (since,)).fetchall()
    stat = {k: {"all": 0, "official": 0, "decided": 0, "proposed": 0} for k in seeds}
    for r in rows:
        text = policy.normalize(r["title"])
        for kw in seeds:
            if policy._has(text, kw):
                s = stat[kw]
                s["all"] += 1
                if r["source_type"] == "official":
                    s["official"] += 1
                    if r["policy_stage"] in ("decided", "proposed"):
                        s[r["policy_stage"]] += 1

    enough = {k: s for k, s in stat.items() if s["all"] >= config.IMPACT_MIN_EVIDENCE}
    freq_pct = _percentiles({k: s["all"] for k, s in enough.items()})
    off_pct = _percentiles({k: s["official"] for k, s in enough.items()})
    result = {}
    for kw in seeds:
        if kw not in enough:
            result[kw] = (None, {**stat[kw], "reason": f"언급 {stat[kw]['all']}회 < {config.IMPACT_MIN_EVIDENCE}회"})
            continue
        s = stat[kw]
        parts = [freq_pct[kw], off_pct[kw]]
        judged = s["decided"] + s["proposed"]
        if judged:
            parts.append(100.0 * s["decided"] / judged)
        result[kw] = (round(sum(parts) / len(parts), 1),
                      {**s, "freq_pct": round(freq_pct[kw], 1), "official_pct": round(off_pct[kw], 1)})
    return result, ""


def reweight(conn, now: datetime | None = None, csv_path=None) -> list[dict]:
    """학습값을 다시 계산해 keyword_weights 를 갱신하고 변경 내역을 반환한다. csv_path 가 있으면 CSV 로도 저장."""
    ensure_seeds(conn)
    learned, reason = compute_learned(conn, now)
    if reason:
        log.info("가중치 학습 건너뜀 (%s)", reason)
    stamp = (now or datetime.now(timezone.utc)).isoformat()
    changes = []
    for kw, (value, evidence) in learned.items():
        before = conn.execute("SELECT seed_weight, learned_weight, final_weight FROM keyword_weights WHERE keyword=?", (kw,)).fetchone()
        final = _final(before["seed_weight"], value)
        conn.execute("UPDATE keyword_weights SET learned_weight=?, final_weight=?, updated_at=?, evidence=? WHERE keyword=?",
                     (value, final, stamp, json.dumps(evidence, ensure_ascii=False), kw))
        changes.append({
            "keyword": kw, "seed": before["seed_weight"],
            "learned_prev": before["learned_weight"], "learned_new": value,
            "final_prev": before["final_weight"], "final_new": final,
            "changed": before["final_weight"] != final,
            "evidence": json.dumps(evidence, ensure_ascii=False),
        })
    conn.commit()
    n_changed = sum(c["changed"] for c in changes)
    log.info("가중치 갱신: 키워드 %d개 중 %d개 변경", len(changes), n_changed)
    if csv_path is not None:
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(changes[0].keys()) if changes else ["keyword"])
            w.writeheader()
            w.writerows(sorted(changes, key=lambda c: (not c["changed"], -c["final_new"])))
        log.info("변경 내역 저장: %s", csv_path)
    return changes

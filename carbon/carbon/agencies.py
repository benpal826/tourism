"""공식 기관 중요도 (F15): 환경부는 최상위로 고정하고, 나머지는 이 프로젝트에 쌓인 데이터로 점수를 계산한다.

머신러닝이 아니라 누적 지표의 가중합이다. 지표별 값과 가중치를 evidence(JSON)에 남겨 왜 그 점수인지 볼 수 있다.
외부 웹 검색으로 기관의 영향력을 추정하지 않는다. 먼저 쌓인 데이터만 쓰고, 부족하면 어떤 신호를 더할지 제안만 한다.
"""
import csv
import json
import logging
import math
from datetime import datetime, timedelta, timezone

import config
from . import weights

log = logging.getLogger(__name__)


def ensure_agencies(conn) -> None:
    """공식 문서에 나온 기관과 설정(고정 순위·종류)에 있는 기관을 agencies 테이블에 넣는다. 기존 점수는 건드리지 않는다."""
    names = {r[0] for r in conn.execute("SELECT DISTINCT agency FROM articles WHERE source_type='official' AND agency <> ''")}
    names |= set(config.AGENCY_FIXED) | set(config.AGENCY_KINDS)
    for name in sorted(names):
        kind = config.AGENCY_KINDS.get(name, "기타")
        fixed = config.AGENCY_FIXED.get(name)
        if conn.execute("SELECT 1 FROM agencies WHERE name=?", (name,)).fetchone():
            conn.execute("UPDATE agencies SET kind=?, fixed_rank=? WHERE name=?", (kind, fixed, name))
        else:
            conn.execute("INSERT INTO agencies (name,kind,fixed_rank) VALUES (?,?,?)", (name, kind, fixed))
    conn.commit()


def _stats(conn, since: str) -> dict[str, dict]:
    """기관별 지표의 원재료: 최근 기간의 탄소 관련 발표 수, 확정·추진·직접 규제 수, 그리고 인용된 뉴스 수."""
    stats: dict[str, dict] = {}
    for r in conn.execute(
        "SELECT agency, policy_stage, domestic_impact FROM articles "
        "WHERE source_type='official' AND published >= ? AND agency <> ''", (since,)):
        s = stats.setdefault(r["agency"], {"docs": 0, "carbon_docs": 0, "decided": 0, "proposed": 0, "direct": 0, "citations": 0})
        s["docs"] += 1
        if r["domestic_impact"] in (None, "unknown"):
            continue                                   # 탄소와 관련이 확인되지 않은 발표는 세지 않는다
        s["carbon_docs"] += 1
        if r["policy_stage"] in ("decided", "proposed"):
            s[r["policy_stage"]] += 1
        if r["domestic_impact"] == "direct":
            s["direct"] += 1
    # 인용: 그 기관의 발표와 연결된 뉴스(서로 다른 기사). 단체·업계 주장(3등급) 뉴스는 영향력의 근거로 보지 않는다
    for r in conn.execute(
        "SELECT o.agency, COUNT(DISTINCT l.news_id) n FROM article_links l "
        "JOIN articles o ON o.id = l.official_id JOIN articles n ON n.id = l.news_id "
        "WHERE o.published >= ? AND n.source_tier IS NOT 3 GROUP BY o.agency", (since,)):
        if r["agency"] in stats:
            stats[r["agency"]]["citations"] = r["n"]
    return stats


def compute(conn, now: datetime | None = None) -> dict[str, tuple[float | None, dict]]:
    """기관별 (점수 또는 None, 근거). 점수는 0~100."""
    now = now or datetime.now(timezone.utc)
    since = (now - timedelta(days=config.AGENCY_WINDOW_DAYS)).isoformat()
    stats = _stats(conn, since)
    eligible = {a: s for a, s in stats.items() if s["carbon_docs"] >= config.AGENCY_MIN_DOCS}
    max_docs = max((s["carbon_docs"] for s in eligible.values()), default=0)
    max_cit = max((s["citations"] for s in eligible.values()), default=0)
    w = config.AGENCY_SCORE_WEIGHTS
    out: dict[str, tuple[float | None, dict]] = {}
    for agency, s in stats.items():
        base = {**s, "window_days": config.AGENCY_WINDOW_DAYS, "weights": w}
        if agency not in eligible:
            out[agency] = (None, {**base, "reason": f"탄소 관련 발표 {s['carbon_docs']}건 < {config.AGENCY_MIN_DOCS}건: 근거 부족"})
            continue
        judged = s["decided"] + s["proposed"]
        comp = {
            "volume": 100 * math.log1p(s["carbon_docs"]) / math.log1p(max_docs) if max_docs else 0.0,
            "citations": 100 * s["citations"] / max_cit if max_cit else 0.0,
            "decided": 100 * s["decided"] / judged if judged else 0.0,
            "direct": 100 * s["direct"] / s["carbon_docs"],
        }
        score = round(sum(w[k] * comp[k] for k in w), 1)
        out[agency] = (score, {**base, "components": {k: round(v, 1) for k, v in comp.items()}})
    return out


def effective_score(row) -> float | None:
    """사람이 정한 점수(AGENCY_OVERRIDES)가 있으면 그것을, 없으면 계산한 점수를 쓴다."""
    ov = config.AGENCY_OVERRIDES.get(row["name"])
    return float(ov) if ov is not None else row["score"]


def sort_key(row) -> tuple:
    """클수록 중요. 고정 순위가 있는 기관이 맨 위, 그다음 점수 순, 점수가 없으면 맨 아래."""
    if row["fixed_rank"] is not None:
        return (2, -row["fixed_rank"])
    score = effective_score(row)
    return (1, score) if score is not None else (0, 0)


def ranking(conn) -> list[dict]:
    """리포트용 기관 순위. 점수가 없는 기관은 rank=None('누적 부족')."""
    rows = [dict(r) for r in conn.execute("SELECT * FROM agencies")]
    rows.sort(key=lambda r: (sort_key(r), r["name"]), reverse=True)
    out, rank = [], 0
    for r in rows:
        scored = r["fixed_rank"] is not None or effective_score(r) is not None
        if scored:
            rank += 1
        out.append({
            "name": r["name"], "kind": r["kind"], "fixed": r["fixed_rank"] is not None,
            "rank": rank if scored else None, "score": effective_score(r),
            "overridden": r["name"] in config.AGENCY_OVERRIDES,
            "evidence": json.loads(r["evidence"]) if r["evidence"] else {},
        })
    return out


def sort_keys(conn) -> dict[str, tuple]:
    """기관명 → 정렬 키 (공식 발표 목록 정렬용)."""
    return {r["name"]: sort_key(dict(r)) for r in conn.execute("SELECT * FROM agencies")}


def rank_agencies(conn, now: datetime | None = None, csv_path=None) -> dict:
    """기관 점수를 다시 계산해 agencies 테이블을 갱신한다.

    DB 에 쌓인 기간이 AGENCY_MIN_HISTORY_DAYS 미만이면 계산하지 않는다 ('누적 부족'). 고정 순위(환경부)는 항상 적용된다.
    """
    ensure_agencies(conn)
    days = weights.history_days(conn)
    if days < config.AGENCY_MIN_HISTORY_DAYS:
        msg = f"누적 부족: DB에 쌓인 기간 {days}일 < {config.AGENCY_MIN_HISTORY_DAYS}일"
        log.info("기관 중요도 계산 건너뜀 (%s)", msg)
        return {"status": "insufficient", "reason": msg, "history_days": days, "changes": []}

    now = now or datetime.now(timezone.utc)
    computed = compute(conn, now)
    stamp = now.isoformat()
    changes = []
    for r in [dict(x) for x in conn.execute("SELECT * FROM agencies")]:
        score, evidence = computed.get(r["name"], (None, {"reason": f"최근 {config.AGENCY_WINDOW_DAYS}일 공식 발표 없음"}))
        conn.execute("UPDATE agencies SET score=?, updated_at=?, evidence=? WHERE name=?",
                     (score, stamp, json.dumps(evidence, ensure_ascii=False), r["name"]))
        changes.append({"name": r["name"], "kind": r["kind"], "fixed_rank": r["fixed_rank"],
                        "score_prev": r["score"], "score_new": score,
                        "override": config.AGENCY_OVERRIDES.get(r["name"]),
                        "docs": evidence.get("carbon_docs"), "citations": evidence.get("citations"),
                        "decided": evidence.get("decided"), "proposed": evidence.get("proposed"), "direct": evidence.get("direct"),
                        "evidence": json.dumps(evidence, ensure_ascii=False)})
    conn.commit()
    ranked = {a["name"]: a["rank"] for a in ranking(conn)}
    for c in changes:
        c["rank"] = ranked.get(c["name"])
    log.info("기관 중요도 갱신: %d개 기관", len(changes))
    if csv_path is not None:
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["rank", "name", "kind", "fixed_rank", "score_prev", "score_new", "override",
                                              "docs", "citations", "decided", "proposed", "direct", "evidence"])
            w.writeheader()
            for c in sorted(changes, key=lambda c: (c["rank"] is None, c["rank"] or 0, c["name"])):
                w.writerow({k: c.get(k) for k in w.fieldnames})
        log.info("기관 순위 저장: %s", csv_path)
    return {"status": "ok", "history_days": days, "changes": changes}

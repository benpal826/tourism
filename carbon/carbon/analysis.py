"""리포트용 데이터 계산. DB만 읽고 dict 를 반환한다 (HTML·파일 출력 없음)."""
import json
from collections import Counter
from datetime import datetime, timedelta, timezone

import config
from . import agencies, db, keywords, linking, weights

ARTICLE_LIMIT = 60
OFFICIAL_DAYS = 30
OFFICIAL_LIMIT = 40
OFFICIAL_FETCH = 200   # 정렬 전에 넉넉히 읽고, 정렬한 뒤 OFFICIAL_LIMIT 개만 남긴다


def _split(tags: str | None) -> list[str]:
    return [t for t in (tags or "").split(",") if t]


def _rising_section(conn, rows, now: datetime, days: int) -> tuple[list[dict], dict]:
    """급증 키워드(F14)와 그 계산 방식 설명.

    DB 에 쌓인 기간이 KEYWORD_MIN_HISTORY_DAYS 이상이면 최근 KEYWORD_BASELINE_DAYS 일의 '평소 빈도' 와 비교하고,
    평소에도 기사의 KEYWORD_USUAL_DF 이상에 나오는 말은 뺀다. 그보다 짧으면 평소 빈도가 아직 의미 없으므로
    조회 기간(days) 안의 이전 날들과 비교하고 일반어 제외만 적용한다 (리포트에 그 사실을 표시).
    단체·업계 주장(3등급) 기사는 rows 에서 이미 빠져 있다.
    """
    cut = (now - timedelta(days=config.RISING_RECENT_DAYS)).isoformat()
    history = weights.history_days(conn)
    enough = history >= config.KEYWORD_MIN_HISTORY_DAYS
    base_days = config.KEYWORD_BASELINE_DAYS if enough else days
    base = conn.execute(
        "SELECT title FROM articles WHERE published >= ? AND published < ? AND source_tier IS NOT 3 AND relevant IS NOT 0",
        ((now - timedelta(days=base_days)).isoformat(), cut)).fetchall()
    recent_titles = [r["title"] for r in rows if r["published"] >= cut]
    terms = keywords.rising_terms(recent_titles, [r["title"] for r in base],
                                  config.KEYWORD_USUAL_DF if enough else None)
    if enough:
        note = (f"최근 {config.RISING_RECENT_DAYS}일을 최근 {base_days}일의 평소 빈도와 비교했습니다. "
                f"평소 기사 제목의 {config.KEYWORD_USUAL_DF:.0%} 이상에 나오는 단어와 일반어는 제외했습니다.")
    else:
        note = (f"DB에 쌓인 기간이 {history}일(기준 {config.KEYWORD_MIN_HISTORY_DAYS}일 미만)이라 평소 빈도 비교는 하지 않고, "
                f"조회 기간 {days}일 안의 이전 날들과 비교했습니다. 일반어만 제외했습니다.")
    return terms, {"mode": "usual" if enough else "window", "history_days": history, "baseline_days": base_days, "note": note}


def _to_kst_iso(iso: str) -> str:
    """저장된 UTC ISO 문자열을 KST ISO 문자열로 변환."""
    return datetime.fromisoformat(iso).astimezone(config.KST).isoformat()


def build_report_data(days: int = 7, conn=None, now: datetime | None = None) -> dict:
    """DB 시각은 UTC 로 비교하고, 날짜 집계와 출력 시각은 KST 로 만든다."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    now_kst = now.astimezone(config.KST)
    own_conn = conn is None
    conn = conn or db.connect()
    try:
        since = (now - timedelta(days=days)).isoformat()
        # 주제·지역은 LLM 이 처리한 기사는 LLM 의 최종 목록을, 아니면 키워드 규칙의 태그를 쓴다
        rows = conn.execute(
            f"SELECT id,title,url,source,lang,published,{db.EFFECTIVE_TOPICS} AS topics,{db.EFFECTIVE_REGIONS} AS regions,"
            "source_type,agency,query,official_status,source_tier,source_tier_reason,sensational,relevant,"
            "llm_summary,llm_impact,llm_done_at FROM articles "
            "WHERE published >= ? ORDER BY published DESC",
            (since,),
        ).fetchall()
        # 무관 기사(relevant=0)는 삭제하지 않지만 모든 집계와 목록에서 뺀다. 미판정(NULL)은 남긴다
        excluded_count = sum(1 for r in rows if r["relevant"] == 0)
        rows = [r for r in rows if r["relevant"] != 0]
        news_ids = [r["id"] for r in rows if r["source_type"] == "news"][:ARTICLE_LIMIT * 3]
        links = _links_for(conn, news_ids)
        single_source_ids = _single_source_ids(rows)
        # 단체·업계 주장(3등급) 기사는 목록에는 배지와 함께 보여주되, 집계(일별·주제·지역·급증 키워드)의 근거로는 쓰지 않는다
        agg_rows = [r for r in rows if r["source_tier"] != 3]
        rising, rising_basis = _rising_section(conn, agg_rows, now, days)
        agency_keys = agencies.sort_keys(conn)
        agency_ranking = agencies.ranking(conn)
        agency_note = _agency_note(conn, agency_ranking)
        # 공식 발표는 발행 빈도가 낮아 더 긴 기간을 따로 본다
        official_since = (now - timedelta(days=OFFICIAL_DAYS)).isoformat()
        official_rows = conn.execute(
            f"SELECT title,url,agency,query,published,{db.EFFECTIVE_TOPICS} AS topics,policy_stage,domestic_impact,impact_score,"
            "impact_keyword,llm_summary,llm_impact FROM articles "
            "WHERE source_type='official' AND relevant IS NOT 0 AND published >= ? ORDER BY published DESC LIMIT ?",
            (official_since, OFFICIAL_FETCH),
        ).fetchall()
        briefing = _briefing(conn, now_kst)
        summary_inputs = _summary_inputs(conn, now, now_kst)
    finally:
        if own_conn:
            conn.close()

    day_cut = (now - timedelta(days=1)).isoformat()

    all_rows = rows
    rows = agg_rows
    excluded_tier3 = len(all_rows) - len(rows)

    # 날짜 경계는 KST 기준 (UTC 15:00 이후 기사는 KST 로 다음 날)
    per_day_counter = Counter(_to_kst_iso(r["published"])[:10] for r in rows)
    per_day = []
    for i in range(days - 1, -1, -1):
        d = (now_kst - timedelta(days=i)).strftime("%Y-%m-%d")
        per_day.append({"date": d, "count": per_day_counter.get(d, 0)})

    topic_7, topic_1, region_7 = Counter(), Counter(), Counter()
    for r in rows:
        recent = r["published"] >= day_cut
        for t in _split(r["topics"]):
            topic_7[t] += 1
            if recent:
                topic_1[t] += 1
        for g in _split(r["regions"]):
            region_7[g] += 1

    topics_out = [{"name": n, "count_7d": c, "count_1d": topic_1.get(n, 0)} for n, c in topic_7.most_common()]
    daily_summary = _compose_summary(summary_inputs, briefing, rising, topics_out,
                                     topic_flow(rows, [d["date"] for d in per_day], [t["name"] for t in topics_out]))

    return {
        "daily_summary": daily_summary,
        "generated_at": now_kst.isoformat(),
        "period_days": days,
        "total_articles": len(rows),
        "per_day": per_day,
        "topics": topics_out,
        "regions": [{"name": n, "count_7d": c} for n, c in region_7.most_common()],
        "rising_terms": rising,
        "rising_basis": rising_basis,
        # 뉴스 목록: 공식 문서는 아래 "official" 에 따로 담는다.
        # 정책 단계·영향도는 뉴스 제목으로 판정하지 않으므로, 연결된 공식 문서(official_links)의 값을 그대로 보여준다.
        "articles": [
            {
                "title": r["title"], "url": r["url"], "source": r["source"],
                "published": _to_kst_iso(r["published"]), "lang": r["lang"],
                "topics": _split(r["topics"]), "regions": _split(r["regions"]),
                "official_status": r["official_status"],
                "official_links": links.get(r["id"], []),
                "source_tier": r["source_tier"] or 0, "source_tier_reason": r["source_tier_reason"] or "",
                "single_source": r["source_tier"] == 3 and r["id"] in single_source_ids,
                "sensational": _split(r["sensational"]),
                "summary": r["llm_summary"] or "", "ai_impact": r["llm_impact"] or "",
            }
            for r in [x for x in all_rows if x["source_type"] == "news"][:ARTICLE_LIMIT]
        ],
        "excluded_tier3": excluded_tier3,
        "excluded_count": excluded_count,
        "official": _official_list(official_rows, agency_keys),
        "policy_summary": _policy_summary(official_rows, all_rows),
        "agencies": agency_ranking,
        "agencies_note": agency_note,
        "briefing": briefing,
        "llm_stats": {"done": sum(1 for r in rows if r["llm_done_at"]), "total": len(rows)},
    }


def _briefing(conn, now_kst: datetime) -> str:
    """오늘(KST)의 브리핑. 오래된 브리핑은 오늘 상황과 다를 수 있으므로 오늘 것만 쓴다."""
    row = conn.execute("SELECT text FROM briefings WHERE day=?", (now_kst.strftime("%Y-%m-%d"),)).fetchone()
    return row["text"] if row else ""


# ----------------------------------------------------------------------------- 오늘의 요약
STAGE_LABELS = {"proposed": "추진", "decided": "확정", "unknown": "미분류"}
IMPACT_LABELS = {"direct": "직접 규제", "indirect": "간접"}
_ITEM_COLS = "id,title,url,agency,published,policy_stage,domestic_impact"


def _summary_inputs(conn, now: datetime, now_kst: datetime) -> dict:
    """오늘의 요약에 필요한 DB 값만 읽어 둔다 (조합은 _compose_summary)."""
    day = now_kst.strftime("%Y-%m-%d")
    ai = conn.execute("SELECT conclusions, report_items FROM daily_summaries WHERE day=?", (day,)).fetchone()
    ai_items = json.loads(ai["report_items"]) if ai else []
    ai_rows = {}
    for it in ai_items:
        r = conn.execute(f"SELECT {_ITEM_COLS} FROM articles WHERE id=?", (it["id"],)).fetchone()
        if r:
            ai_rows[it["id"]] = dict(r)
    # 규칙 보고 항목: llm.briefing_candidates 의 공식 문서와 같은 조건·순서
    rule_rows = [dict(r) for r in conn.execute(
        f"SELECT {_ITEM_COLS} FROM articles WHERE source_type='official' AND relevant IS NOT 0 AND published >= ? "
        "AND domestic_impact IN ('direct','indirect') "
        "ORDER BY CASE domestic_impact WHEN 'direct' THEN 0 ELSE 1 END, "
        "CASE policy_stage WHEN 'decided' THEN 0 WHEN 'proposed' THEN 1 ELSE 2 END, published DESC LIMIT ?",
        ((now - timedelta(days=7)).isoformat(), config.SUMMARY_REPORT_ITEMS)).fetchall()]
    ids = set(ai_rows) | {r["id"] for r in rule_rows}
    related = {i: conn.execute("SELECT COUNT(*) FROM article_links WHERE official_id=?", (i,)).fetchone()[0] for i in ids}
    day_cut = (now - timedelta(days=1)).isoformat()
    new_official = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(policy_stage='decided' AND domestic_impact='direct'), 0) FROM articles "
        "WHERE source_type='official' AND relevant IS NOT 0 AND published >= ?", (day_cut,)).fetchone()
    return {"ai_conclusions": json.loads(ai["conclusions"]) if ai else None, "ai_items": ai_items, "ai_rows": ai_rows,
            "rule_rows": rule_rows, "related": related, "new_official": (new_official[0], new_official[1])}


def _item(row: dict, why: str, origin: str, related: dict) -> dict:
    return {"id": row["id"], "title": row["title"], "url": row["url"], "agency": row["agency"] or "",
            "published": _to_kst_iso(row["published"]), "policy_stage": row["policy_stage"] or "unknown",
            "domestic_impact": row["domestic_impact"] or "unknown", "why": why, "origin": origin,
            "related_news": related.get(row["id"], 0)}


def rule_why(row: dict) -> str:
    return f'{STAGE_LABELS.get(row["policy_stage"] or "unknown", "미분류")} · {IMPACT_LABELS.get(row["domestic_impact"], "참고")}'


def rules_conclusions(new_official: tuple[int, int], rising: list[dict], topics: list[dict]) -> list[str]:
    out = []
    n, m = new_official
    if n:
        out.append(f"최근 1일 신규 공식 문서 {n}건 (확정·직접 규제 {m}건).")
    if rising:
        out.append("급증 키워드: " + ", ".join(t["term"] for t in rising[:3]) + ".")
    top = max(topics, key=lambda t: t["count_1d"], default=None)        # 같은 건수면 7일 많은 순서(topics 순서)가 이긴다
    if top and top["count_1d"]:
        out.append(f'최근 1일 가장 많이 다룬 주제: {top["name"]} ({top["count_1d"]}건).')
    return out


def topic_flow(rows, dates: list[str], topic_order: list[str]) -> dict:
    """흐름 그림: 7일 건수 상위 주제의 일별(KST) 건수."""
    names = topic_order[: config.SUMMARY_FLOW_TOPICS]
    counts = {n: Counter() for n in names}
    for r in rows:
        d = _to_kst_iso(r["published"])[:10]
        for t in _split(r["topics"]):
            if t in counts:
                counts[t][d] += 1
    return {"dates": dates, "topics": [{"name": n, "counts": [counts[n].get(d, 0) for d in dates]} for n in names]}


def _compose_summary(inp: dict, briefing: str, rising: list[dict], topics: list[dict], flow: dict) -> dict:
    rule_items = [_item(r, rule_why(r), "rules", inp["related"]) for r in inp["rule_rows"]]
    if inp["ai_conclusions"] is not None:
        ai_items = [_item(inp["ai_rows"][it["id"]], it["why"], "ai", inp["related"])
                    for it in inp["ai_items"] if it["id"] in inp["ai_rows"]]
        return {"source": "ai", "conclusions": inp["ai_conclusions"], "briefing_text": None,
                "report_items": ai_items or rule_items, "flow": flow}
    if briefing:
        return {"source": "briefing", "conclusions": [], "briefing_text": briefing, "report_items": rule_items, "flow": flow}
    return {"source": "rules", "conclusions": rules_conclusions(inp["new_official"], rising, topics), "briefing_text": None,
            "report_items": rule_items, "flow": flow}


def _agency_note(conn, ranking: list[dict]) -> str:
    """기관 점수가 아직 없을 때 그 이유 (환경부 순위 고정만 적용된 상태)."""
    if any(a["rank"] is not None and not a["fixed"] for a in ranking):
        return ""
    days = weights.history_days(conn)
    if days < config.AGENCY_MIN_HISTORY_DAYS:
        return (f"DB에 쌓인 기간이 {days}일(기준 {config.AGENCY_MIN_HISTORY_DAYS}일 미만)이라 기관 점수는 아직 계산하지 않았습니다. "
                "순위를 고정한 기관만 표시됩니다.")
    return f"최근 {config.AGENCY_WINDOW_DAYS}일에 탄소 관련 발표가 {config.AGENCY_MIN_DOCS}건 이상인 기관이 없어 점수를 계산하지 못했습니다."


def _single_source_ids(rows) -> set[str]:
    """단일 출처 주장: 단체·업계(3등급) 뉴스 중 다른 출처가 같은 사안을 다루지 않은 것.

    다른 출처가 다뤘다고 보는 경우: (1) 공식 문서와 연결됐다(공식 확인됨), 또는
    (2) 1·2등급 뉴스 중 SINGLE_SOURCE_DAYS 일 안에 제목이 SINGLE_SOURCE_SIM 이상 비슷한 것이 있다.
    """
    news = [r for r in rows if r["source_type"] == "news"]
    corroborators = [r for r in news if r["source_tier"] in (1, 2)]
    out = set()
    for r in news:
        if r["source_tier"] != 3 or r["official_status"] == "confirmed":
            continue
        title = linking.strip_outlet(r["title"])
        corroborated = any(
            abs(linking.days_between(r["published"], c["published"])) <= config.SINGLE_SOURCE_DAYS
            and linking.similarity(title, linking.strip_outlet(c["title"])) >= config.SINGLE_SOURCE_SIM
            for c in corroborators
        )
        if not corroborated:
            out.add(r["id"])
    return out


def _links_for(conn, news_ids: list[str]) -> dict[str, list[dict]]:
    """뉴스별로 연결된 공식 문서 (점수 높은 순)."""
    out: dict[str, list[dict]] = {}
    for i in range(0, len(news_ids), 500):
        chunk = news_ids[i:i + 500]
        marks = ",".join("?" * len(chunk))
        for r in conn.execute(
            f"SELECT l.news_id, l.score, o.title, o.url, o.agency, o.policy_stage, o.domestic_impact "
            f"FROM article_links l JOIN articles o ON o.id = l.official_id "
            f"WHERE l.news_id IN ({marks}) ORDER BY l.score DESC", chunk,
        ):
            out.setdefault(r["news_id"], []).append({
                "title": r["title"], "url": r["url"], "agency": r["agency"] or "", "score": r["score"],
                "stage": r["policy_stage"] or "unknown", "impact": r["domestic_impact"] or "unknown",
            })
    return out


def _policy_summary(official_rows, rows) -> dict:
    """정책 단계·영향도 집계는 공식 문서만 센다. 공식 확인이 안 된 뉴스는 여기에 들어가지 않는다."""
    stage, impact = Counter(), Counter()
    for r in official_rows:
        stage[r["policy_stage"] or "unknown"] += 1
        impact[r["domestic_impact"] or "unknown"] += 1
    news = [r for r in rows if r["source_type"] == "news"]
    return {
        "official_total": len(official_rows),
        "stage": {k: stage.get(k, 0) for k in ("decided", "proposed", "unknown")},
        "impact": {k: impact.get(k, 0) for k in ("direct", "indirect", "reference", "unknown")},
        "news_total": len(news),
        "news_confirmed": sum(1 for r in news if r["official_status"] == "confirmed"),
        "news_unconfirmed": sum(1 for r in news if r["official_status"] != "confirmed"),
    }


# 공식 발표 정렬: 국내 영향이 큰 것(직접 규제) → 정책 단계가 확정된 것 → 중요한 기관 → 최신순
_IMPACT_RANK = {"direct": 0, "indirect": 1, "reference": 2}
_STAGE_RANK = {"decided": 0, "proposed": 1}


def _official_list(rows, agency_keys: dict[str, tuple] | None = None) -> list[dict]:
    agency_keys = agency_keys or {}
    rows = sorted(rows, key=lambda r: r["published"], reverse=True)                       # 1) 최신순
    rows.sort(key=lambda r: agency_keys.get(r["agency"], (0, 0)), reverse=True)             # 2) 기관 중요도 (같은 조건일 때)
    rows.sort(key=lambda r: _STAGE_RANK.get(r["policy_stage"], 2))                          # 3) 단계 (안정 정렬)
    rows.sort(key=lambda r: _IMPACT_RANK.get(r["domestic_impact"], 3))                      # 4) 영향도가 가장 우선
    return [
        {
            "title": r["title"], "url": r["url"], "agency": r["agency"] or "",
            "board": r["query"] or "", "published": _to_kst_iso(r["published"]),
            "topics": _split(r["topics"]),
            "stage": r["policy_stage"] or "unknown", "impact": r["domestic_impact"] or "unknown",
            "impact_score": r["impact_score"], "impact_keyword": r["impact_keyword"] or "",
            "summary": r["llm_summary"] or "", "ai_impact": r["llm_impact"] or "",
        }
        for r in rows[:OFFICIAL_LIMIT]
    ]

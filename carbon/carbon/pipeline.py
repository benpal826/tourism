"""수집 → 중복 제거 → 태깅 → 저장 흐름."""
import logging
from collections import defaultdict
from datetime import datetime, timezone

import json
import re
import time
from datetime import timedelta

import config
from . import db, filters, linking, policy, tagging, tiers, weights
from .sources.base import Source
from .sources.google_news import GoogleNewsSource
from .sources.registry import build_sources
from .tagging import tag_text

log = logging.getLogger(__name__)


def refilter(conn) -> dict:
    """저장된 기사에 현재 규칙으로 태그와 관련성(F6)을 다시 판정한다.

    관련성은 근거가 'rule:' 로 시작하거나 비어 있는 기사만 다시 계산한다. LLM·사람이 내린 판정은 건드리지 않는다.
    반환: {"total": n, "relevant": n, "irrelevant": n, "undecided": n, "changed": n, "retagged": n}
    """
    changed = retagged = 0
    for r in conn.execute("SELECT id,title,summary,source,source_type,domestic_impact,topics,regions,relevant,relevance_reason FROM articles").fetchall():
        topics, regions = tagging.tag_text(r["title"], r["summary"] or "")
        t, g = ",".join(topics), ",".join(regions)
        if (t, g) != (r["topics"] or "", r["regions"] or ""):
            conn.execute("UPDATE articles SET topics=?, regions=? WHERE id=?", (t, g, r["id"]))
            retagged += 1
        why = r["relevance_reason"]
        if why and not why.startswith("rule:"):
            continue
        rel, new_why = filters.judge_relevance(r["title"], r["source"], r["source_type"], r["domestic_impact"])
        if (rel, new_why) != (r["relevant"], why):
            conn.execute("UPDATE articles SET relevant=?, relevance_reason=? WHERE id=?", (rel, new_why, r["id"]))
            changed += 1
    conn.commit()
    dist = {r[0]: r[1] for r in conn.execute("SELECT relevant, COUNT(*) FROM articles GROUP BY relevant")}
    res = {"total": sum(dist.values()), "relevant": dist.get(1, 0), "irrelevant": dist.get(0, 0), "undecided": dist.get(None, 0),
           "changed": changed, "retagged": retagged}
    log.info("관련성 재판정: 전체 %(total)d건 → 관련 %(relevant)d, 무관 %(irrelevant)d, 미판정 %(undecided)d (판정 변경 %(changed)d, 태그 변경 %(retagged)d)", res)
    return res


def reclassify_official(conn) -> int:
    """저장된 모든 공식 문서의 정책 단계·국내 영향도를 현재 규칙과 가중치로 다시 판정한다."""
    w = weights.load_weights(conn)
    # policy_source='llm' 은 LLM 이 단계·영향도를 채운 문서라 규칙으로 덮어쓰지 않는다
    rows = conn.execute("SELECT id,title,summary,agency FROM articles WHERE source_type='official' "
                        "AND COALESCE(policy_source,'') <> 'llm'").fetchall()
    for r in rows:
        j = policy.classify_official(r["title"], r["summary"] or "", r["agency"] or "", w)
        conn.execute("UPDATE articles SET policy_stage=?, domestic_impact=?, impact_score=?, impact_keyword=? WHERE id=?",
                     (j.stage, j.impact, j.impact_score, j.impact_keyword, r["id"]))
    conn.commit()
    log.info("공식 문서 %d건 재판정", len(rows))
    return len(rows)


_QUERY_NOISE = re.compile(r"[「」『』\[\]()（）\"“”‘’·]")


def coverage_query(title: str) -> str:
    """공식 문서 제목을 뉴스 검색어로 다듬는다. 앞의 '(한국환경공단 보도자료 10. 30.)', '[보도자료]' 같은 꼬리표와 따옴표·괄호를
    떼고 길이를 제한한다."""
    t = re.sub(r"^\s*[\[(（][^\])）]{0,30}[\])）]\s*", "", title or "")     # 맨 앞 꼬리표 하나
    t = _QUERY_NOISE.sub(" ", t)
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > config.COVERAGE_QUERY_CHARS:
        t = t[: config.COVERAGE_QUERY_CHARS].rsplit(" ", 1)[0]               # 단어 중간에서 자르지 않는다
    return t


def search_coverage(conn, searcher=None, now: datetime | None = None, delay: float | None = None) -> dict:
    """새 공식 문서의 제목으로 뉴스를 검색해 후속 보도를 모은다 (F16 보강).

    대상: 최근 COVERAGE_DOC_DAYS 일 안에 발행된 공식 문서 중 국내 영향도가 판정된(탄소 관련) 것.
      - 아직 검색하지 않은 문서, 또는 한 번 검색했고 COVERAGE_RETRY_HOURS 가 지난 문서 (최대 2회)
      - 영향도가 높은 문서부터, 한 번에 COVERAGE_MAX_PER_RUN 건까지
    저장: 공식 문서와의 연결 점수가 COVERAGE_MIN_SCORE 이상인 결과만 (엉뚱한 기사 방지). 연결 자체는 link 단계가 한다.
    검색에 실패한 문서는 횟수를 올리지 않아 다음 실행에서 다시 시도한다.
    반환: {"docs": n, "searched": n, "failed": n, "results": n, "kept": n, "new": n}
    """
    now = now or datetime.now(timezone.utc)
    searcher = searcher or GoogleNewsSource(queries=[])
    delay = getattr(searcher, "delay", 0) if delay is None else delay
    docs = conn.execute(
        "SELECT id,title,agency,published,coverage_checks FROM articles "
        "WHERE source_type='official' AND published >= ? AND domestic_impact IS NOT NULL AND domestic_impact <> 'unknown' "
        "AND (coverage_checks = 0 OR (coverage_checks = 1 AND coverage_checked_at <= ?)) "
        "ORDER BY CASE domestic_impact WHEN 'direct' THEN 0 WHEN 'indirect' THEN 1 ELSE 2 END, published DESC LIMIT ?",
        ((now - timedelta(days=config.COVERAGE_DOC_DAYS)).isoformat(),
         (now - timedelta(hours=config.COVERAGE_RETRY_HOURS)).isoformat(), config.COVERAGE_MAX_PER_RUN),
    ).fetchall()
    stats = {"docs": len(docs), "searched": 0, "failed": 0, "results": 0, "kept": 0, "new": 0}
    stamp = now.isoformat()
    w = weights.load_weights(conn)
    for i, d in enumerate(docs):
        if i and delay:
            time.sleep(delay)
        query = coverage_query(d["title"])
        lang = "en" if (d["agency"] or "") == "European Commission" else "ko"
        try:
            found = searcher.search(query, lang, config.COVERAGE_DAYS_BACK)[: config.COVERAGE_RESULTS_PER_QUERY]
        except Exception as e:
            log.warning("공식 문서 후속 보도 검색 실패 '%s': %s", query, e)
            stats["failed"] += 1
            continue
        stats["searched"] += 1
        stats["results"] += len(found)
        doc = {"title": d["title"], "agency": d["agency"] or "", "published": d["published"]}
        for a in found:
            score, _ = linking.score_pair({"title": a.title, "published": a.published}, doc)
            if score < config.COVERAGE_MIN_SCORE:
                continue
            a.query = f"공식문서:{query[:20]}"
            stats["kept"] += 1
            stats["new"] += _insert(conn, a, now.isoformat(), w)
        conn.execute("UPDATE articles SET coverage_checks=coverage_checks+1, coverage_checked_at=? WHERE id=?", (stamp, d["id"]))
    conn.commit()
    log.info("공식 문서 후속 보도 검색: 문서 %(docs)d건 → 검색 %(searched)d (실패 %(failed)d), 결과 %(results)d건 중 저장 대상 %(kept)d, 신규 %(new)d", stats)
    return stats


def _insert(conn, a, collected: str, w: dict) -> int:
    """기사 한 건을 저장하고 새로 들어갔으면 1, 이미 있었으면 0. 공식 문서에는 정책 단계·영향도를 판정해 넣는다."""
    topics, regions = tag_text(a.title, a.summary)
    # 정책 단계·영향도는 공식 문서에만 판정한다. 뉴스 제목으로는 판정하지 않는다 (NULL).
    j = policy.classify_official(a.title, a.summary, a.agency, w) if a.source_type == "official" else None
    # 자극적 표현은 뉴스 제목에만 표시한다 (표시용. 점수 계산이나 삭제에는 쓰지 않는다)
    sensational = ",".join(tiers.sensational_terms(a.title)) if a.source_type == "news" else None
    relevant, why = filters.judge_relevance(a.title, a.source, a.source_type, j.impact if j else None)
    cur = conn.execute(
        "INSERT OR IGNORE INTO articles "
        "(id,title,url,source,lang,query,summary,published,collected,topics,regions,source_type,agency,"
        "policy_stage,domestic_impact,impact_score,impact_keyword,official_status,source_url,sensational,"
        "relevant,relevance_reason) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (a.id, a.title, a.url, a.source, a.lang, a.query, a.summary,
         a.published, collected, ",".join(topics), ",".join(regions), a.source_type, a.agency,
         j.stage if j else None, j.impact if j else None,
         j.impact_score if j else None, j.impact_keyword if j else None,
         "n/a" if a.source_type == "official" else "unconfirmed", a.source_url or None, sensational,
         relevant, why),
    )
    if cur.rowcount == 0 and a.source_url:
        # 이미 저장된 기사가 다시 수집되면, 예전에는 몰랐던 언론사 주소를 채워 넣는다
        conn.execute("UPDATE articles SET source_url=? WHERE id=? AND (source_url IS NULL OR source_url='')", (a.source_url, a.id))
    return cur.rowcount


def assign_tiers(conn, now: datetime | None = None) -> dict:
    """모든 기사에 출처 신뢰도 등급(F13)과 근거를 붙인다. 언론사 단위로 한 번 판정해 그 언론사의 기사 전체에 적용한다.

    수집 건수는 최근 TIER_WINDOW_DAYS 일의 뉴스 기준이다. 데이터가 쌓일수록 빈도 기준(2등급)이 의미 있어진다.
    반환: {"outlets": n, "tiers": {등급: 기사 수}, "changed": 등급이 바뀐 기사 수}
    """
    now = now or datetime.now(timezone.utc)
    since = (now - timedelta(days=config.TIER_WINDOW_DAYS)).isoformat()
    counts = {r["source"]: r["n"] for r in conn.execute(
        "SELECT source, COUNT(*) n FROM articles WHERE source_type='news' AND published >= ? GROUP BY source", (since,))}
    # 언론사별 도메인: RSS 가 알려 준 주소 중 가장 많이 나온 것. 없으면 이름이 도메인 형태일 때 그것을 쓴다
    domains: dict[str, str] = {}
    for r in conn.execute("SELECT source, source_url, COUNT(*) n FROM articles WHERE source_type='news' "
                          "AND source_url IS NOT NULL AND source_url <> '' GROUP BY source, source_url ORDER BY n DESC"):
        domains.setdefault(r["source"], tiers.domain_of(r["source_url"]))

    before = {r["id"]: r["source_tier"] for r in conn.execute("SELECT id, source_tier FROM articles")}
    outlets = [r["source"] for r in conn.execute("SELECT DISTINCT source FROM articles WHERE source_type='news'")]
    for name in outlets:
        res = tiers.classify_source(name or "", domains.get(name, ""), counts.get(name, 0), "news")
        conn.execute("UPDATE articles SET source_tier=?, source_tier_reason=? WHERE source_type='news' AND source IS ?",
                     (res.tier, res.reason, name))
    conn.execute("UPDATE articles SET source_tier=1, source_tier_reason='official-source' WHERE source_type='official'")
    # 이전 실행에서 자극적 표현을 계산하지 못한 뉴스(이 기능 도입 전에 저장된 기사)를 채운다
    for r in conn.execute("SELECT id,title FROM articles WHERE source_type='news' AND sensational IS NULL").fetchall():
        conn.execute("UPDATE articles SET sensational=? WHERE id=?", (",".join(tiers.sensational_terms(r["title"])), r["id"]))
    conn.commit()

    dist = {r["source_tier"]: r["n"] for r in conn.execute("SELECT source_tier, COUNT(*) n FROM articles GROUP BY source_tier")}
    changed = sum(1 for r in conn.execute("SELECT id, source_tier FROM articles") if before.get(r["id"]) != r["source_tier"])
    log.info("출처 등급 부여: 언론사 %d곳, 기사 등급 분포 %s (변경 %d건)", len(outlets),
             {tiers.TIER_LABELS.get(k, k): v for k, v in sorted(dist.items(), key=lambda x: (x[0] is None, x[0]))}, changed)
    return {"outlets": len(outlets), "tiers": dist, "changed": changed}


def link_news(conn, now: datetime | None = None, relink: bool = False) -> dict:
    """최근 뉴스를 공식 문서와 연결한다 (F16). 뉴스 본문은 읽지 않고 제목만 비교한다.

    대상: 최근 LINK_WINDOW_DAYS 일 뉴스 중 아직 연결되지 않은 것.
      - 처음 시도하는 뉴스
      - 한 번 시도했지만 연결되지 않았고 LINK_RETRY_HOURS 가 지난 뉴스 (공식 문서가 늦게 올라올 수 있어 한 번 더 시도)
    relink=True 이면 기존 연결을 지우고 기간 내 뉴스 전체를 다시 계산한다 (기준을 고친 뒤 사용).
    반환: {"tried": n, "confirmed": n, "unconfirmed": n, "retried": n}
    """
    now = now or datetime.now(timezone.utc)
    since = (now - timedelta(days=config.LINK_WINDOW_DAYS)).isoformat()
    if relink:
        conn.execute("DELETE FROM article_links WHERE news_id IN (SELECT id FROM articles WHERE source_type='news' AND published >= ?)", (since,))
        conn.execute("UPDATE articles SET official_status='unconfirmed', link_attempts=0, link_checked_at=NULL "
                     "WHERE source_type='news' AND published >= ?", (since,))
    retry_before = (now - timedelta(hours=config.LINK_RETRY_HOURS)).isoformat()
    news_rows = conn.execute(
        "SELECT id,title,published,link_attempts FROM articles WHERE source_type='news' AND published >= ? "
        "AND relevant IS NOT 0 AND official_status <> 'confirmed' AND (link_attempts = 0 OR (link_attempts = 1 AND link_checked_at <= ?))",
        (since, retry_before),
    ).fetchall()

    # 후보 공식 문서: 가장 오래된 뉴스보다 LINK_AFTER_DAYS 이전부터 지금까지
    off_since = (now - timedelta(days=config.LINK_WINDOW_DAYS + config.LINK_AFTER_DAYS)).isoformat()
    officials = [dict(r) for r in conn.execute(
        "SELECT id,title,agency,published FROM articles WHERE source_type='official' AND published >= ?", (off_since,))]

    stamp = now.isoformat()
    result = {"tried": len(news_rows), "confirmed": 0, "unconfirmed": 0, "retried": 0}
    for n in news_rows:
        links = linking.best_links(dict(n), officials)
        if n["link_attempts"] >= 1:
            result["retried"] += 1
        if links:
            for o, score, evidence in links:
                conn.execute("INSERT OR REPLACE INTO article_links (news_id,official_id,score,method,created_at) VALUES (?,?,?,?,?)",
                             (n["id"], o["id"], score, json.dumps(evidence, ensure_ascii=False), stamp))
            conn.execute("UPDATE articles SET official_status='confirmed', link_attempts=link_attempts+1, link_checked_at=? WHERE id=?",
                         (stamp, n["id"]))
            result["confirmed"] += 1
        else:
            conn.execute("UPDATE articles SET official_status='unconfirmed', link_attempts=link_attempts+1, link_checked_at=? WHERE id=?",
                         (stamp, n["id"]))
            result["unconfirmed"] += 1
    conn.commit()
    log.info("뉴스–공식 문서 연결: 시도 %(tried)d건 → 연결됨 %(confirmed)d, 공식 확인 안 됨 %(unconfirmed)d (재시도 %(retried)d)", result)
    return result


def collect(sources: list[Source] | None = None, conn=None) -> dict:
    """모든 출처를 수집해 저장하고 결과 요약을 반환한다.

    한 출처가 통째로 실패해도 나머지는 계속 수집한다.
    반환: {"by_query": {검색어/게시판: {"fetched": n, "new": m}}, "failed": [...], "new_total": n}
    """
    own_conn = conn is None
    conn = conn or db.connect()
    sources = sources if sources is not None else build_sources()
    stats: dict[str, dict[str, int]] = defaultdict(lambda: {"fetched": 0, "new": 0})
    failed: list[str] = []
    w = weights.load_weights(conn)
    try:
        for src in sources:
            try:
                articles = src.fetch()
            except Exception:
                log.exception("출처 '%s' 수집 실패", src.name)
                failed.append(src.name)
                continue
            failed += src.failures
            now = datetime.now(timezone.utc).isoformat()
            for a in articles:
                inserted = _insert(conn, a, now, w)
                key = f"{a.agency}·{a.query}" if a.source_type == "official" else a.query
                stats[key]["fetched"] += 1
                stats[key]["new"] += inserted
            conn.commit()
    finally:
        if own_conn:
            conn.close()

    new_total = sum(s["new"] for s in stats.values())
    for q, s in stats.items():
        log.info("%s: %d건 중 신규 %d건", q, s["fetched"], s["new"])
    if failed:
        log.warning("실패한 항목: %s", ", ".join(failed))
    log.info("신규 기사 총 %d건 저장", new_total)
    return {"by_query": dict(stats), "failed": failed, "new_total": new_total}

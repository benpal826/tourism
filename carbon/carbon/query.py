"""검색·내보내기 (F10) 의 조건 조합.

조건 판정은 matches() 하나에 모아, CLI(search, export)와 이후 화면 필터(3단계)가 같은 규칙을 쓰게 한다.
- 날짜(--from/--to)는 KST 날짜이고 양 끝을 포함한다. DB 는 UTC 이므로 KST 자정 경계를 UTC 로 바꿔 비교한다.
- 주제·지역은 리포트와 같은 기준(LLM 이 처리한 기사는 LLM 목록, 아니면 키워드 태그)으로 정확히 일치하는 태그를 찾는다.
  이름 일부만 써도 되지만(예: "CBAM" → "CBAM/탄소국경"), 여러 개에 걸리거나 없는 이름이면 오류로 알린다.
- 검색어는 제목·RSS 요약·LLM 한 줄 요약에서 대소문자 구분 없이 포함 여부로 찾는다.
- 무관 기사(relevant=0)는 다른 목록과 마찬가지로 결과에서 뺀다. 단체·업계 주장(3등급)은 등급과 함께 남긴다.
"""
import csv
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import config
from . import db

SEARCH_LIMIT = 20
TIER_LABELS = {1: "공식", 2: "일반", 3: "단체·업계 주장", 0: "미분류"}
STAGE_LABELS = {"decided": "확정", "proposed": "추진", "unknown": "미분류"}
IMPACT_LABELS = {"direct": "직접 규제", "indirect": "간접", "reference": "참고", "unknown": "미분류"}
STATUS_LABELS = {"confirmed": "공식 확인", "unconfirmed": "공식 확인 안 됨"}

EXPORT_COLUMNS = [
    ("published", "발행(KST)"), ("kind", "구분"), ("title", "제목"), ("source", "언론사·기관"), ("url", "링크"),
    ("topics", "주제"), ("regions", "지역"), ("source_tier", "출처 등급"), ("official_status", "공식 확인"),
    ("policy_stage", "정책 단계"), ("domestic_impact", "국내 영향도"), ("ai_summary", "AI 요약"), ("ai_impact", "AI 중요도"),
]


class QueryError(ValueError):
    """사용자가 준 조건이 잘못됐다 (날짜 형식, 없는 주제·지역 이름 등)."""


@dataclass
class Filters:
    date_from: date | None = None
    date_to: date | None = None
    topic: str | None = None      # 정확한 주제 이름 (resolve_name 으로 정규화한 값)
    region: str | None = None
    keyword: str | None = None


def parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise QueryError(f"날짜 형식은 YYYY-MM-DD 입니다: {s}") from None


def resolve_name(value: str | None, names, label: str) -> str | None:
    """정확한 이름이면 그대로, 아니면 대소문자 무시 부분 일치가 하나뿐일 때 그 이름."""
    if not value:
        return None
    names = list(names)
    if value in names:
        return value
    hits = [n for n in names if value.strip().lower() in n.lower()]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise QueryError(f"없는 {label}입니다: {value}. 가능한 값: {', '.join(names)}")
    raise QueryError(f"{label} '{value}' 가 여러 개에 해당합니다: {', '.join(hits)}")


def make_filters(date_from=None, date_to=None, topic=None, region=None, keyword=None) -> Filters:
    f = Filters(parse_date(date_from), parse_date(date_to), resolve_name(topic, config.TOPICS, "주제"),
                resolve_name(region, config.REGIONS, "지역"), (keyword or "").strip() or None)
    if f.date_from and f.date_to and f.date_from > f.date_to:
        raise QueryError(f"시작일({f.date_from})이 종료일({f.date_to})보다 늦습니다")
    return f


def utc_range(f: Filters) -> tuple[str | None, str | None]:
    """KST 날짜 [from, to] 를 UTC ISO 반열린 구간 [start, end) 로."""
    start = end = None
    if f.date_from:
        start = datetime.combine(f.date_from, time(0), config.KST).astimezone(timezone.utc).isoformat()
    if f.date_to:
        end = datetime.combine(f.date_to + timedelta(days=1), time(0), config.KST).astimezone(timezone.utc).isoformat()
    return start, end


def matches(item: dict, f: Filters) -> bool:
    """item: to_item() 이 만든 dict (topics/regions 는 목록, published 는 KST ISO).
    화면 필터도 이 함수와 같은 규칙을 따른다."""
    day = item["published"][:10]
    if f.date_from and day < f.date_from.isoformat():
        return False
    if f.date_to and day > f.date_to.isoformat():
        return False
    if f.topic and f.topic not in item["topics"]:
        return False
    if f.region and f.region not in item["regions"]:
        return False
    if f.keyword:
        k = f.keyword.lower()
        hay = " ".join([item["title"], item.get("rss_summary", ""), item.get("ai_summary", "")]).lower()
        if k not in hay:
            return False
    return True


def _split(tags: str | None) -> list[str]:
    return [t.strip() for t in (tags or "").split(",") if t.strip()]


def to_item(r) -> dict:
    official = r["source_type"] == "official"
    return {
        "id": r["id"], "title": r["title"], "url": r["url"] or "",
        "published": datetime.fromisoformat(r["published"]).astimezone(config.KST).isoformat(),
        "kind": "공식" if official else "뉴스",
        "source": (r["agency"] or r["source"] or "") if official else (r["source"] or ""),
        "topics": _split(r["topics"]), "regions": _split(r["regions"]),
        "source_tier": TIER_LABELS.get(r["source_tier"] or 0, "미분류"),
        # 정책 단계·영향도는 공식 문서에만 판정한다. 뉴스는 연결 여부만 보여준다 (연결 문서의 값은 리포트에서 확인)
        "official_status": "" if official else STATUS_LABELS.get(r["official_status"], r["official_status"] or ""),
        "policy_stage": STAGE_LABELS.get(r["policy_stage"] or "unknown", "") if official else "",
        "domestic_impact": IMPACT_LABELS.get(r["domestic_impact"] or "unknown", "") if official else "",
        "rss_summary": r["summary"] or "", "ai_summary": r["llm_summary"] or "", "ai_impact": r["llm_impact"] or "",
    }


def find(conn, f: Filters, limit: int | None = None) -> list[dict]:
    """조건에 맞는 기사·공식 문서를 최신순으로. 날짜는 SQL 로 먼저 좁히고 나머지는 matches() 로 거른다."""
    start, end = utc_range(f)
    where, params = ["relevant IS NOT 0", "published IS NOT NULL"], []
    if start:
        where.append("published >= ?")
        params.append(start)
    if end:
        where.append("published < ?")
        params.append(end)
    rows = conn.execute(
        f"SELECT id,title,url,source,agency,source_type,published,summary,{db.EFFECTIVE_TOPICS} AS topics,"
        f"{db.EFFECTIVE_REGIONS} AS regions,source_tier,official_status,policy_stage,domestic_impact,llm_summary,llm_impact "
        f"FROM articles WHERE {' AND '.join(where)} ORDER BY published DESC", params).fetchall()
    out = []
    for r in rows:
        item = to_item(r)
        if matches(item, f):
            out.append(item)
            if limit and len(out) >= limit:
                break
    return out


def _cell(v) -> str:
    """Excel 이 수식으로 해석하지 않게 =,+,-,@ 로 시작하는 값 앞에 ' 를 붙인다 (외부에서 온 제목이라)."""
    s = ", ".join(v) if isinstance(v, list) else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@") else s


def export_csv(items: list[dict], path: Path) -> None:
    """Excel 에서 한글이 깨지지 않게 utf-8-sig(BOM) 로 저장한다."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow([label for _, label in EXPORT_COLUMNS])
        for it in items:
            # 발행 시각은 Excel 에서 읽기 쉽게 'YYYY-MM-DD HH:MM' (KST)
            row = {**it, "published": it["published"][:16].replace("T", " ")}
            w.writerow([_cell(row[k]) for k, _ in EXPORT_COLUMNS])


def format_table(items: list[dict], width: int = 60) -> str:
    if not items:
        return "결과 없음"
    lines = []
    for it in items:
        title = it["title"] if len(it["title"]) <= width else it["title"][:width - 1] + "…"
        lines.append(f"{it['published'][:16].replace('T', ' ')}  [{it['kind']}] {title}  ({it['source']})")
        lines.append(f"    {it['url']}")
    return "\n".join(lines)

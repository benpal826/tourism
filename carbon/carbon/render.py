"""분석 결과 dict -> HTML 문자열 (3단계 UI). DB·네트워크에 접근하지 않는다.

화면 구성(A안): 상단 요약(날짜·기간·건수·브리핑) + 왼쪽 필터 + 본문(공식 발표 → 급증 키워드 → 분포 → 뉴스).
- HTML 파일 하나에 CSS·JS 를 모두 넣는다. 외부 CDN·폰트를 쓰지 않아 오프라인에서도 열린다.
- 모든 동적 값은 escape 한다. 필터용 값은 JSON 을 <script> 에 넣지 않고 각 항목의 data-* 속성(escape 됨)으로 전달한다.
- 필터 조건은 URL 해시(#topic=...&q=...)에 저장해 새로고침해도 유지된다.
- 4단계 Playwright 점검을 위해 필터 컨트롤과 주요 영역에 안정적인 id·data-testid 를 둔다.
"""
from html import escape

EMPTY = '<p class="empty">해당 없음</p>'
STAGE_LABELS = {"proposed": "추진", "decided": "확정", "unknown": "미분류"}
IMPACT_LABELS = {"direct": "직접 규제", "indirect": "간접", "reference": "참고", "unknown": "미분류"}
TIER_LABELS = {1: "공식", 2: "일반", 3: "단체·업계 주장", 0: "미분류"}
AI_IMPACT_LABELS = {"high": "높음", "medium": "보통", "low": "낮음"}


def _safe_url(url: str) -> str:
    """http(s) 링크만 허용한다. 그 밖의 스킴은 '#'으로 대체."""
    return url if (url or "").lower().startswith(("http://", "https://")) else "#"


def _a(url: str, text: str, cls: str = "") -> str:
    c = f' class="{cls}"' if cls else ""
    return f'<a{c} href="{escape(_safe_url(url), quote=True)}" target="_blank" rel="noopener">{escape(text)}</a>'


def _attr(values) -> str:
    """data-* 속성 값. 목록은 '|' 로 이어 붙인다 (태그 이름에 '|' 는 없다)."""
    if isinstance(values, (list, tuple, set)):
        values = "|".join(str(v) for v in values)
    return escape(str(values), quote=True)


def _badge(text: str, kind: str, title: str = "") -> str:
    t = f' title="{escape(title, quote=True)}"' if title else ""
    return f'<span class="badge b-{kind}"{t}>{escape(text)}</span>'


def _ai_badge(item: dict) -> str:
    v = item.get("ai_impact") or ""
    return _badge(f"AI 중요도 {AI_IMPACT_LABELS[v]}", f"ai-{v}") if v in AI_IMPACT_LABELS else ""


def _summary(item: dict) -> str:
    """AI 한 줄 요약. 제목·요약만 보고 쓴 것이라 원문과 다를 수 있다."""
    s = item.get("summary") or ""
    return f'<p class="summary">{escape(s)}</p>' if s else ""


def _tags(values: list[str]) -> str:
    return "".join(f'<span class="tag">{escape(v)}</span>' for v in values)


# ----------------------------------------------------------------------------- 섹션
def _official_section(data: dict) -> str:
    s = data["policy_summary"]
    summary = (
        f'<p class="note">공식 문서 {int(s["official_total"])}건 기준 — '
        f'정책 단계: 확정 {int(s["stage"]["decided"])} · 추진 {int(s["stage"]["proposed"])} · 미분류 {int(s["stage"]["unknown"])} / '
        f'국내 영향도: 직접 규제 {int(s["impact"]["direct"])} · 간접 {int(s["impact"]["indirect"])} · '
        f'참고 {int(s["impact"]["reference"])} · 미분류 {int(s["impact"]["unknown"])}</p>'
        f'<p class="note">뉴스 {int(s["news_total"])}건 중 공식 확인됨 {int(s["news_confirmed"])}건, '
        f'공식 확인 안 됨 {int(s["news_unconfirmed"])}건 (뉴스는 화제성 신호로만 쓰고 단계·영향도 집계에는 넣지 않습니다)</p>'
    )
    items = []
    for o in data["official"]:
        stage, impact = o["stage"], o["impact"]
        hot = stage == "decided" and impact == "direct"
        basis = ""
        if o.get("impact_keyword"):
            score = f', {o["impact_score"]:g}점' if o.get("impact_score") is not None else ""
            basis = f'<span class="basis">영향도 근거: {escape(o["impact_keyword"])}{score}</span>'
        badges = (_badge("확정 · 직접 규제", "hot") if hot else "") + \
            _badge(STAGE_LABELS.get(stage, "미분류"), f"stage-{stage}", "정책 단계") + \
            _badge(IMPACT_LABELS.get(impact, "미분류"), f"impact-{impact}", "국내 영향도") + _ai_badge(o)
        items.append(
            f'<li class="item official{" hot" if hot else ""}" data-kind="official" '
            f'data-topics="{_attr(o.get("topics", []))}" data-regions="" data-ai="{_attr(o.get("ai_impact") or "")}" '
            f'data-stages="{_attr(stage)}" data-impacts="{_attr(impact)}" data-tier="1" data-conf="" '
            f'data-date="{_attr(o["published"])}" data-title="{_attr(o["title"])}" data-summary="{_attr(o.get("summary") or "")}">'
            f'<div class="badges">{badges}</div>'
            f'<h3 class="title">{_a(o["url"], o["title"])}</h3>{_summary(o)}'
            f'<p class="meta">{escape(o["agency"])} · {escape(o["board"])} · {escape(o["published"][:10])} {basis}</p></li>')
    body = f'<ul class="list" id="official-list" data-testid="official-list">{"".join(items)}</ul>' if items else EMPTY
    empty = '<p class="empty filtered-empty" hidden>필터 조건에 맞는 공식 발표가 없습니다.</p>'
    return (f'<section id="official" aria-labelledby="h-official"><h2 id="h-official">공식 발표 '
            f'<small>(정부·국회·EU, 최근 30일)</small></h2>{summary}'
            f'<p class="count" id="official-count" data-testid="official-count" aria-live="polite"></p>{body}{empty}</section>')


def _agency_section(data: dict) -> str:
    rows = []
    for a in data["agencies"]:
        ev = a.get("evidence") or {}
        if ev.get("carbon_docs") is not None and "components" in ev:
            basis = (f'탄소 관련 발표 {ev["carbon_docs"]} · 뉴스 인용 {ev["citations"]} · '
                     f'확정 {ev["decided"]}/추진 {ev["proposed"]} · 직접 규제 {ev["direct"]}')
        else:
            basis = ev.get("reason", "")
        if a["fixed"]:
            score = "고정"
        elif a["score"] is not None:
            score = f'{a["score"]:g}' + (" (사람이 지정)" if a["overridden"] else "")
        else:
            score = "누적 부족"
        rows.append(f'<tr><td>{a["rank"] if a["rank"] else "-"}</td><td>{escape(a["name"])}</td>'
                    f'<td>{escape(a.get("kind") or "")}</td><td>{escape(score)}</td><td>{escape(basis)}</td></tr>')
    note = f'<p class="note">{escape(data["agencies_note"])}</p>' if data.get("agencies_note") else ""
    table = ('<div class="table-wrap"><table><thead><tr><th scope="col">순위</th><th scope="col">기관</th>'
             '<th scope="col">종류</th><th scope="col">중요도 점수</th><th scope="col">근거</th></tr></thead>'
             f'<tbody>{"".join(rows)}</tbody></table></div>') if rows else EMPTY
    return (f'<section id="agencies" aria-labelledby="h-agencies"><details><summary><h2 id="h-agencies">공식 기관 중요도</h2>'
            f'</summary>{note}{table}</details></section>')


def _rising_section(data: dict) -> str:
    note = f'<p class="note">{escape(data["rising_basis"]["note"])}</p>' if data.get("rising_basis") else ""
    terms = sorted(data["rising_terms"], key=lambda t: -t["ratio"])
    if terms:
        btns = "".join(
            f'<li><button type="button" class="chip" data-term="{_attr(t["term"])}" aria-pressed="false" '
            f'data-testid="rising-term">{escape(t["term"])} <span class="ratio">×{t["ratio"]:g}</span>'
            f'<span class="sr"> — 최근 2일 {int(t["recent"])}건, 평소라면 {t["baseline"]}건</span></button></li>'
            for t in terms)
        body = (f'<p class="hint">키워드를 누르면 그 말이 제목에 들어간 기사만 남습니다. 다시 누르면 해제됩니다.</p>'
                f'<ul class="chips" id="rising-terms">{btns}</ul>')
    else:
        body = EMPTY
    return (f'<section id="rising" aria-labelledby="h-rising"><h2 id="h-rising">급증 키워드 '
            f'<small>(평소보다 특이하게 늘어난 말, 배율 순)</small></h2>{note}{body}</section>')


def _day_chart(per_day: list[dict]) -> str:
    if not per_day:
        return EMPTY
    w, h, top, bottom = 560, 180, 22, 26
    n = len(per_day)
    slot = w / n
    bw = min(48, slot * 0.6)
    mx = max((d["count"] for d in per_day), default=0) or 1
    parts = []
    for i, d in enumerate(per_day):
        c = int(d["count"])
        bh = (h - top - bottom) * c / mx
        x = i * slot + (slot - bw) / 2
        y = h - bottom - bh
        cx = i * slot + slot / 2
        parts.append(
            f'<rect class="bar" x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{max(bh, 0):.1f}" rx="3"></rect>'
            f'<text class="val" x="{cx:.1f}" y="{y - 6:.1f}" text-anchor="middle">{c}</text>'
            f'<text class="lbl" x="{cx:.1f}" y="{h - 8}" text-anchor="middle">{escape(d["date"][5:])}</text>')
    label = "일별 기사 수: " + ", ".join(f'{d["date"]} {int(d["count"])}건' for d in per_day)
    return (f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(label, quote=True)}" '
            f'data-testid="day-chart"><line class="axis" x1="0" y1="{h - bottom}" x2="{w}" y2="{h - bottom}"></line>'
            f'{"".join(parts)}</svg>')


SUMMARY_SOURCE_LABELS = {"ai": "AI 요약", "briefing": "AI 브리핑", "rules": "규칙 요약 (AI 요약 없음)"}
AI_NOTE = '<p class="note">AI가 제목과 요약만 보고 작성했습니다. 중요한 내용은 원문을 확인하세요.</p>'


def _flow_chart(flow: dict) -> str:
    """흐름: 주제마다 한 줄, 7일 일별 건수 작은 막대 + 숫자 라벨."""
    topics = [t for t in flow.get("topics", []) if any(t["counts"])]
    dates = flow.get("dates", [])
    if not topics or not dates:
        return EMPTY
    label_w, w, row_h, top = 150, 560, 40, 4
    n = len(dates)
    slot = (w - label_w) / n
    bw = min(26, slot * 0.6)
    mx = max(max(t["counts"]) for t in topics) or 1
    bar_h = row_h - 18
    parts = []
    for r, t in enumerate(topics):
        base = top + r * row_h + row_h - 4
        parts.append(f'<text class="lbl" x="0" y="{base - 6}">{escape(t["name"])}</text>')
        for i, c in enumerate(t["counts"]):
            c = int(c)
            bh = bar_h * c / mx
            x = label_w + i * slot + (slot - bw) / 2
            parts.append(f'<rect class="bar" x="{x:.1f}" y="{base - bh:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="2"></rect>'
                         f'<text class="val" x="{x + bw / 2:.1f}" y="{base - bh - 3:.1f}" text-anchor="middle">{c}</text>')
    h = top + len(topics) * row_h + 18
    for i, d in enumerate(dates):
        parts.append(f'<text class="lbl" x="{label_w + i * slot + slot / 2:.1f}" y="{h - 4}" text-anchor="middle">{escape(d[5:])}</text>')
    label = "주제별 최근 7일 일별 기사 수: " + "; ".join(
        f'{t["name"]} ' + ", ".join(f"{d[5:]} {int(c)}" for d, c in zip(dates, t["counts"])) for t in topics)
    return (f'<svg class="chart flow" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(label, quote=True)}" data-testid="flow-chart">'
            f'<title>{escape(label)}</title>{"".join(parts)}</svg>')


def _report_item(it: dict) -> str:
    stage, impact = it.get("policy_stage") or "unknown", it.get("domestic_impact") or "unknown"
    badges = (_badge(STAGE_LABELS.get(stage, "미분류"), f"stage-{stage}", "정책 단계")
              + _badge(IMPACT_LABELS.get(impact, "미분류"), f"impact-{impact}", "국내 영향도"))
    if it.get("origin") == "rules":
        badges += _badge("규칙", "unknown", "규칙으로 고른 항목")
    meta = " · ".join(x for x in (escape(it.get("agency") or ""), escape((it.get("published") or "")[:10])) if x)
    related = f' · 관련 보도 {int(it["related_news"])}건' if it.get("related_news") else ""
    return (f'<li class="report-item"><div class="badges">{badges}</div><h3 class="title">{_a(it["url"], it["title"])}</h3>'
            f'<p class="meta">{meta}{related}</p><p class="why">왜: {escape(it.get("why") or "")}</p></li>')


def _summary_block(data: dict) -> str:
    s = data.get("daily_summary") or {
        "source": "briefing" if data.get("briefing") else "rules", "conclusions": [],
        "briefing_text": data.get("briefing") or None, "report_items": [], "flow": {"dates": [], "topics": []}}
    source = s.get("source", "rules")
    if source == "briefing" and s.get("briefing_text"):
        body = f'<p>{escape(s["briefing_text"])}</p>{AI_NOTE}'
    elif s.get("conclusions"):
        body = "<ul>" + "".join(f"<li>{escape(c)}</li>" for c in s["conclusions"]) + "</ul>" + (AI_NOTE if source == "ai" else "")
    else:
        body = EMPTY
    items = s.get("report_items") or []
    report = (f'<ol class="report-items" data-testid="report-items">{"".join(_report_item(i) for i in items)}</ol>' if items else EMPTY)
    return (f'<section class="briefing daily-summary" aria-labelledby="h-brief" data-testid="daily-summary">'
            f'<h2 id="h-brief">오늘의 요약 <small data-testid="summary-source">{escape(SUMMARY_SOURCE_LABELS.get(source, ""))}</small></h2>'
            f'<div class="conclusions" data-testid="briefing">{body}</div>'
            f'<div class="summary-grid"><div class="summary-reports"><h3 class="sub">보고할 것</h3>{report}</div>'
            f'<div class="summary-flow"><h3 class="sub">흐름 <small>(주제별 최근 7일)</small></h3>'
            f'{_flow_chart(s.get("flow") or {})}</div></div></section>')


def _hbars(rows: list[tuple[str, int, str]], testid: str) -> str:
    """가로 막대. 색 대신 길이와 숫자 라벨로 값을 읽을 수 있게 한다."""
    if not rows:
        return EMPTY
    mx = max(r[1] for r in rows) or 1
    lis = "".join(
        f'<li><span class="hb-name">{escape(name)}</span>'
        f'<span class="hb-track" aria-hidden="true"><span class="hb-bar" style="width:{100 * v / mx:.1f}%"></span></span>'
        f'<span class="hb-val">{int(v)}{escape(extra)}</span></li>'
        for name, v, extra in rows)
    return f'<ul class="hbars" data-testid="{testid}">{lis}</ul>'


def _distribution_section(data: dict) -> str:
    days = int(data["period_days"])
    topics = _hbars([(t["name"], t["count_7d"], f' (최근 1일 {int(t["count_1d"])})') for t in data["topics"]], "topic-bars")
    regions = _hbars([(r["name"], r["count_7d"], "") for r in data["regions"]], "region-bars")
    return (f'<section id="distribution" aria-labelledby="h-dist"><h2 id="h-dist">기사 분포 <small>(최근 {days}일)</small></h2>'
            f'<div class="grid2"><div><h3>일별 기사 수</h3>{_day_chart(data["per_day"])}</div>'
            f'<div><h3>주제별</h3>{topics}<h3>지역별</h3>{regions}</div></div></section>')


def _news_item(a: dict) -> str:
    tier = int(a.get("source_tier") or 0)
    links = a.get("official_links") or []
    confirmed = a.get("official_status") == "confirmed" and bool(links)
    badges = _badge(TIER_LABELS.get(tier, "미분류"), f"tier-{tier}", "출처 신뢰도 등급")
    extra = ""
    if tier == 3:
        extra += (f'<p class="claim-note">단체 주장 — '
                  f'{"단일 출처 주장: 공식 문서나 다른 언론이 다루지 않았습니다" if a.get("single_source") else "다른 출처도 다룸"}</p>')
    if a.get("sensational"):
        badges += _badge("자극적 표현", "sens", "자극적 표현: " + ", ".join(a["sensational"]))
    badges += _ai_badge(a)
    if confirmed:
        badges += _badge("공식 확인됨", "conf")
        docs = "".join(
            f'<li>{escape(l["agency"])}: {_a(l["url"], l["title"])} '
            f'({STAGE_LABELS.get(l["stage"], "미분류")} · {IMPACT_LABELS.get(l["impact"], "미분류")})</li>' for l in links)
        extra += f'<div class="links"><span>공식 확인됨 → 연결된 공식 문서</span><ul>{docs}</ul></div>'
    else:
        badges += _badge("공식 확인 안 됨", "unconf")
    if a.get("sensational"):
        extra += f'<p class="sens-note">자극적 표현: {escape(", ".join(a["sensational"]))}</p>'
    stages = sorted({l["stage"] for l in links}) if confirmed else []
    impacts = sorted({l["impact"] for l in links}) if confirmed else []
    meta = f'{escape(a["source"])} · {escape(a["published"][:16].replace("T", " "))} · {escape(a.get("lang") or "")}'
    return (f'<li class="item news tier-{tier}" data-kind="news" data-topics="{_attr(a["topics"])}" '
            f'data-regions="{_attr(a["regions"])}" data-ai="{_attr(a.get("ai_impact") or "")}" '
            f'data-stages="{_attr(stages)}" data-impacts="{_attr(impacts)}" data-tier="{tier}" '
            f'data-conf="{"confirmed" if confirmed else "unconfirmed"}" data-date="{_attr(a["published"])}" '
            f'data-title="{_attr(a["title"])}" data-summary="{_attr(a.get("summary") or "")}">'
            f'<div class="badges">{badges}</div><h3 class="title">{_a(a["url"], a["title"])}</h3>{_summary(a)}'
            f'<p class="meta">{meta}</p><div class="tags">{_tags(a["topics"] + a["regions"])}</div>{extra}</li>')


def _news_section(data: dict) -> str:
    items = "".join(_news_item(a) for a in data["articles"])
    body = f'<ul class="list" id="news-list" data-testid="news-list">{items}</ul>' if items else EMPTY
    note = (f'<p class="note">최근 뉴스 {len(data["articles"])}건을 담았습니다. 급증 키워드와 분포는 기간 전체 기사(공식 문서 포함)로 '
            f'계산하므로, 키워드를 눌러도 이 목록에 해당 기사가 없을 수 있습니다.</p>') if data["articles"] else ""
    return (f'<section id="news" aria-labelledby="h-news"><h2 id="h-news">최근 뉴스</h2>{note}'
            f'<p class="count" id="news-count" data-testid="news-count" aria-live="polite"></p>{body}'
            f'<p class="empty filtered-empty" id="news-empty" data-testid="news-empty" hidden>필터 조건에 맞는 뉴스가 없습니다. '
            f'왼쪽 필터에서 조건을 줄이거나 "필터 초기화"를 누르세요.</p></section>')


def _select(fid: str, label: str, options: list[tuple[str, str]], note: str = "") -> str:
    opts = '<option value="">전체</option>' + "".join(
        f'<option value="{escape(v, quote=True)}">{escape(t)}</option>' for v, t in options)
    n = f' <small>{escape(note)}</small>' if note else ""
    return (f'<div class="field"><label for="f-{fid}">{escape(label)}{n}</label>'
            f'<select id="f-{fid}" name="{fid}" data-testid="filter-{fid}">{opts}</select></div>')


def _filters(data: dict) -> str:
    topics = sorted({t for a in data["articles"] for t in a["topics"]} | {t for o in data["official"] for t in o.get("topics", [])}
                    | {t["name"] for t in data["topics"]})
    regions = sorted({r for a in data["articles"] for r in a["regions"]} | {r["name"] for r in data["regions"]})
    fields = [
        '<div class="field"><label for="f-q">제목 검색</label>'
        '<input type="search" id="f-q" name="q" data-testid="filter-q" placeholder="예: 배출권" autocomplete="off"></div>',
        _select("days", "기간", [("1", "최근 1일"), ("3", "최근 3일"), ("7", "최근 7일")]),
        _select("topic", "주제", [(t, t) for t in topics]),
        _select("region", "지역", [(r, r) for r in regions], "뉴스만"),
        _select("ai", "AI 중요도", [(k, v) for k, v in AI_IMPACT_LABELS.items()]),
        _select("stage", "정책 단계", [("decided", "확정"), ("proposed", "추진"), ("unknown", "미분류")], "뉴스는 연결 문서 기준"),
        _select("impact", "국내 영향도", [(k, v) for k, v in IMPACT_LABELS.items()], "뉴스는 연결 문서 기준"),
        _select("tier", "출처 등급", [("1", "공식"), ("2", "일반"), ("3", "단체·업계 주장"), ("0", "미분류")], "뉴스만"),
        _select("conf", "공식 확인", [("confirmed", "공식 확인됨"), ("unconfirmed", "공식 확인 안 됨")], "뉴스만"),
    ]
    return (f'<aside id="filters" aria-labelledby="h-filters" data-testid="filters"><details id="filter-panel" open>'
            f'<summary><h2 id="h-filters">필터</h2></summary><form id="filter-form" role="search" onsubmit="return false">'
            f'{"".join(fields)}<p class="kw-state" id="kw-state" data-testid="kw-state" hidden></p>'
            f'<button type="reset" id="f-reset" data-testid="filter-reset">필터 초기화</button></form>'
            f'<p class="hint">조건은 주소(#…)에 저장되어 새로고침해도 유지됩니다.</p></details></aside>')


# ----------------------------------------------------------------------------- 정적 자산
CSS = """
:root{--bg:#f3f5f7;--surface:#fff;--text:#202d3b;--muted:#526171;--line:#dce3e9;--link:#245a88;--focus:#b45309;
--accent:#28665f;--soft:#eef5f3;--control-line:#82919f;--shadow:0 4px 20px rgba(24,44,62,.05);
--space-1:4px;--space-2:8px;--space-3:12px;--space-4:16px;--space-5:24px;--space-6:32px;
--bar:#477a96;--track:#e7edf1;--hot-bg:#fff7f5;--hot-line:#b42318;
--b-dec-bg:#e2f2e7;--b-dec:#145a32;--b-pro-bg:#fff0d1;--b-pro:#6b4200;--b-unk-bg:#ececec;--b-unk:#3d3d3d;
--b-dir-bg:#fde4e2;--b-dir:#8f1d16;--b-ind-bg:#e3ecfb;--b-ind:#1d4485;--b-ref-bg:#efeff0;--b-ref:#3d3d3d;
--b-claim-bg:#f6e6ff;--b-claim:#5b2181;--claim-line:#8a4fb4;--b-sens-bg:#fff0d1;--b-sens:#6b4200;--b-conf-bg:#e2f2e7;--b-conf:#145a32;
--b-unconf-bg:#ececec;--b-unconf:#3d3d3d;--b-hot-bg:#b42318;--b-hot:#fff;--b-ai-bg:#e3ecfb;--b-ai:#1d4485}
@media (prefers-color-scheme:dark){:root{--bg:#121417;--surface:#1b1e23;--text:#ebebeb;--muted:#b9bcc2;--line:#363a41;--link:#8ab4ff;--focus:#fdba74;
--accent:#9ccfc4;--soft:#202e2e;--control-line:#778596;--shadow:0 4px 20px rgba(0,0,0,.12);
--bar:#7aa7e0;--track:#2b2f36;--hot-bg:#2d1a19;--hot-line:#f97066;
--b-dec-bg:#173525;--b-dec:#9fe0b5;--b-pro-bg:#3a2c10;--b-pro:#f5cf85;--b-unk-bg:#2d3036;--b-unk:#d0d3d8;
--b-dir-bg:#3d1b19;--b-dir:#ffb4ad;--b-ind-bg:#1b2a44;--b-ind:#a9c6ff;--b-ref-bg:#2d3036;--b-ref:#d0d3d8;
--b-claim-bg:#33213f;--b-claim:#e2b8ff;--claim-line:#b98ad9;--b-sens-bg:#3a2c10;--b-sens:#f5cf85;--b-conf-bg:#173525;--b-conf:#9fe0b5;
--b-unconf-bg:#2d3036;--b-unconf:#d0d3d8;--b-hot-bg:#f97066;--b-hot:#1b0b0a;--b-ai-bg:#1b2a44;--b-ai:#a9c6ff}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.7 system-ui,-apple-system,"Segoe UI","Malgun Gothic","Apple SD Gothic Neo",sans-serif;word-break:keep-all;overflow-wrap:anywhere}
.nowrap{white-space:nowrap}
a{color:var(--link);text-underline-offset:3px;text-decoration-thickness:1px}
.title a{text-decoration:none}.title a:hover{text-decoration:underline}
a:focus-visible,button:focus-visible,select:focus-visible,input:focus-visible,summary:focus-visible{outline:3px solid var(--focus);outline-offset:2px}
.skip{position:absolute;left:-999px}.skip:focus{left:8px;top:8px;background:var(--surface);padding:6px 10px;z-index:9}
header.top{max-width:1280px;margin:0 auto;padding:var(--space-6) var(--space-5) 0}
header.top h1{margin:0 0 var(--space-3);font-size:1.25rem;line-height:1.5;letter-spacing:-.025em}
header.top h1 .nowrap{font-weight:500;color:var(--muted);font-size:1rem;font-variant-numeric:tabular-nums}
.stats{display:flex;flex-wrap:wrap;gap:var(--space-2) var(--space-5);margin:0 0 var(--space-2);padding:0;list-style:none;color:var(--muted);font-size:.875rem}
.stats strong{color:var(--text)}
.briefing{margin-top:var(--space-5);padding:var(--space-6);border:1px solid var(--line);border-top:4px solid var(--accent);background:var(--surface);border-radius:16px;box-shadow:var(--shadow)}
.briefing h2{display:flex;align-items:center;flex-wrap:wrap;gap:var(--space-3);margin:0 0 var(--space-5);font-size:1.75rem;line-height:1.35;letter-spacing:-.035em}
.briefing h2 small{font-size:.8125rem;font-weight:600;letter-spacing:0;color:var(--accent);background:var(--soft);border-radius:6px;padding:var(--space-1) var(--space-2)}
.conclusions{padding:var(--space-4) var(--space-5);background:var(--soft);border-radius:10px;font-size:1.0625rem;line-height:1.85}
.conclusions p{margin:0}.conclusions .note{margin-top:var(--space-3);font-size:.8125rem}
.daily-summary ul{margin:0;padding-left:20px}.daily-summary ul li{padding-left:var(--space-1);margin:var(--space-1) 0}
.conclusions li::marker{color:var(--accent)}
.summary-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:var(--space-5);margin-top:var(--space-5);align-items:start}
.daily-summary h3.sub{margin:0 0 var(--space-3);font-size:1rem}
.daily-summary h3.sub small{font-size:.8125rem;font-weight:400;color:var(--muted)}
.report-items{margin:0;padding-left:var(--space-5)}
.report-item{margin:0 0 var(--space-3);padding:var(--space-4);border:1px solid var(--line);border-radius:10px;background:var(--surface);box-shadow:0 2px 6px rgba(24,44,62,.03)}
.report-item:last-child{margin-bottom:0}.report-item::marker{color:var(--accent);font-weight:700;font-variant-numeric:tabular-nums}
.report-item h3.title{margin:var(--space-2) 0;font-size:1.0625rem;line-height:1.6;letter-spacing:-.015em}
.report-item .meta{margin:0;color:var(--muted);font-size:.8125rem}
.report-item .why{margin:var(--space-3) 0 0;padding-top:var(--space-3);border-top:1px solid var(--line);font-size:.9375rem}
.summary-flow{padding:var(--space-4);background:var(--bg);border:1px solid var(--line);border-radius:10px}
.chart.flow{max-width:640px;margin:var(--space-4) auto 0}
.layout{display:grid;grid-template-columns:240px minmax(0,1fr);gap:var(--space-5);max-width:1280px;margin:0 auto;padding:var(--space-5)}
main,.summary-grid>div,.grid2>div{min-width:0}
aside#filters{position:sticky;top:16px;align-self:start;background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:var(--space-4);max-height:calc(100vh - 32px);overflow:auto;box-shadow:var(--shadow)}
aside summary{cursor:pointer;list-style:none}aside summary::-webkit-details-marker{display:none}
aside summary h2{display:inline;font-size:1.05rem;margin:0}
aside summary::after{content:" ▾";color:var(--muted)}
.field{margin:var(--space-4) 0}
.field label{display:block;font-weight:600;font-size:.9rem;margin-bottom:3px}
.field label small{font-weight:400;color:var(--muted)}
select,input[type=search]{width:100%;min-width:0;min-height:44px;font:inherit;padding:var(--space-2);border:1px solid var(--control-line);border-radius:8px;background:var(--surface);color:var(--text)}
input::placeholder{color:var(--muted);opacity:1}
button{font:inherit;cursor:pointer}
#f-reset{width:100%;min-height:44px;margin-top:var(--space-2);padding:var(--space-2) var(--space-3);border:1px solid var(--control-line);border-radius:8px;background:var(--bg);color:var(--text);font-weight:600}
.hint,.note{color:var(--muted);font-size:.88rem;margin:4px 0}
main section{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:var(--space-5);margin-bottom:var(--space-5);box-shadow:var(--shadow)}
main h2{font-size:1.1875rem;margin:0 0 var(--space-3);letter-spacing:-.025em;line-height:1.5}
main h2 small{font-weight:400;color:var(--muted);font-size:.85rem}
h3{font-size:1rem;margin:12px 0 6px}
.list{list-style:none;margin:0;padding:0}
.item{border-top:1px solid var(--line);padding:var(--space-5) 0}
.item:first-child{border-top:0}
.item .title{margin:var(--space-2) 0 var(--space-1);font-size:1.0625rem;font-weight:600;line-height:1.6;letter-spacing:-.015em}
.item .meta{margin:2px 0;color:var(--muted);font-size:.88rem}
.item .summary{margin:2px 0;font-size:.92rem}
.item.hot{background:var(--hot-bg);border:1px solid var(--line);border-left:4px solid var(--hot-line);border-radius:8px;padding:var(--space-4);margin:var(--space-3) 0}
.item.tier-3{border-left:4px dashed var(--claim-line);padding-left:10px;background:var(--bg)}
.basis{font-size:.85rem}
.badges{display:flex;flex-wrap:wrap;gap:6px}
.badge{display:inline-block;font-size:.8125rem;font-weight:600;line-height:1.4;padding:3px 8px;border-radius:6px;border:1px solid transparent}
.b-hot{background:var(--b-hot-bg);color:var(--b-hot)}
.b-stage-decided{background:var(--b-dec-bg);color:var(--b-dec)}
.b-stage-proposed{background:var(--b-pro-bg);color:var(--b-pro)}
.b-stage-unknown,.b-impact-unknown,.b-unknown{background:var(--b-unk-bg);color:var(--b-unk)}
.b-impact-direct{background:var(--b-dir-bg);color:var(--b-dir)}
.b-impact-indirect{background:var(--b-ind-bg);color:var(--b-ind)}
.b-impact-reference{background:var(--b-ref-bg);color:var(--b-ref)}
.b-tier-1,.b-tier-2,.b-tier-0{background:var(--b-unk-bg);color:var(--b-unk)}
.b-tier-3,.b-claim{background:var(--b-claim-bg);color:var(--b-claim)}
.b-sens{background:var(--b-sens-bg);color:var(--b-sens)}
.b-conf{background:var(--b-conf-bg);color:var(--b-conf)}
.b-unconf{background:var(--b-unconf-bg);color:var(--b-unconf);border-color:var(--line)}
.b-ai-high,.b-ai-medium,.b-ai-low{background:var(--b-ai-bg);color:var(--b-ai)}
.b-ai-high{border-color:var(--b-ai)}
.tags{margin-top:3px}
.tag{display:inline-block;font-size:.78rem;color:var(--muted);border:1px solid var(--line);border-radius:4px;padding:0 5px;margin:2px 4px 0 0}
.links{font-size:.88rem;margin-top:4px}
.links ul{margin:2px 0 0;padding-left:18px}
.claim-note,.sens-note{font-size:.85rem;color:var(--b-claim);margin:3px 0}
.sens-note{color:var(--b-sens)}
.chips{list-style:none;display:flex;flex-wrap:wrap;gap:6px;margin:6px 0 0;padding:0}
.chip{min-height:44px;border:1px solid var(--line);background:var(--bg);color:var(--text);border-radius:8px;padding:var(--space-2) var(--space-3)}
.chip .ratio{font-weight:700;color:var(--link)}
.chip[aria-pressed=true]{background:var(--link);color:var(--surface);border-color:var(--link)}
.chip[aria-pressed=true] .ratio{color:var(--surface)}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.grid2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
.chart{width:100%;height:auto;display:block}
.chart .bar{fill:var(--bar)}.chart .axis{stroke:var(--line)}
.chart text{fill:var(--text);font-size:13px}.chart .lbl{fill:var(--muted)}
.hbars{list-style:none;margin:0;padding:0}
.hbars li{display:grid;grid-template-columns:minmax(0,9.5em) minmax(0,1fr) 8.5em;gap:8px;align-items:center;margin:4px 0;font-size:.9rem}
.hb-track{background:var(--track);border-radius:4px;height:12px;overflow:hidden}
.hb-bar{display:block;height:100%;background:var(--bar)}
.hb-val{font-variant-numeric:tabular-nums;white-space:nowrap}
.count{font-size:.8125rem;font-weight:600;color:var(--muted);margin:var(--space-4) 0 var(--space-2)}
.empty{color:var(--muted)}
.kw-state{font-size:.9rem}
.table-wrap{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:.9rem}
th,td{border-bottom:1px solid var(--line);padding:var(--space-3) var(--space-2);text-align:left;vertical-align:top}
th{background:var(--bg);font-weight:600}
#agencies summary{cursor:pointer}#agencies summary h2{display:inline}
footer{max-width:1280px;margin:0 auto;padding:0 var(--space-5) var(--space-6);color:var(--muted);font-size:.8125rem}
@media (max-width:860px){
 .layout{grid-template-columns:minmax(0,1fr);padding:var(--space-4);gap:var(--space-4)}
 aside#filters{position:static;max-height:none}
 .grid2,.summary-grid{grid-template-columns:minmax(0,1fr)}
 header.top{padding:var(--space-5) var(--space-4) 0}
 .briefing{padding:var(--space-5)}
 main section{margin-bottom:var(--space-4)}
}
@media (max-width:480px){
 header.top h1{font-size:1.0625rem}
 .briefing{padding:var(--space-4);border-radius:12px}
 .briefing h2{font-size:1.5rem;margin-bottom:var(--space-4)}
 .conclusions{padding:var(--space-3) var(--space-4);font-size:1rem}
 .summary-grid{gap:var(--space-4)}
 .report-item{padding:var(--space-3)}
 .summary-flow{padding:var(--space-3)}
 main section{padding:var(--space-4)}
 main h2 small{display:block;margin-top:var(--space-1)}
 .hbars li{grid-template-columns:minmax(0,1fr) auto;row-gap:2px}
 .hb-track{grid-column:1 / -1;grid-row:2}
 .chart text{font-size:20px}
 .chart.flow .lbl{font-size:15px}
}
@media print{
 :root{--bg:#fff;--surface:#fff;--text:#000;--muted:#333;--line:#ccc;--link:#000;--accent:#244e48;--soft:#f3f5f4;--bar:#466879;--track:#eee;--shadow:none}
 aside#filters,.skip,#rising .hint,.filtered-empty{display:none!important}
 header.top{padding:0}
 .briefing{padding:16px;margin-top:16px;box-shadow:none}
 .summary-grid{display:block}.summary-flow{margin-top:16px}
 .conclusions,.report-item,.summary-flow{break-inside:avoid}
 .report-item{box-shadow:none}
 .layout{display:block;padding:0}
 body{background:#fff;color:#000}
 main section{border:0;padding:0;box-shadow:none;margin-top:24px}
 h2,h3{break-after:avoid}
 .item{break-inside:avoid}
 a{color:#000}
}
"""

JS = r"""
(function(){
  var KEYS=["q","days","topic","region","ai","stage","impact","tier","conf"];
  var gen=new Date(document.body.getAttribute("data-generated"));
  var state={kw:""};
  function el(id){return document.getElementById(id);}
  function split(v){return v?v.split("|"):[];}
  function readHash(){
    var p=new URLSearchParams(location.hash.replace(/^#/,""));
    KEYS.forEach(function(k){var f=el("f-"+k);if(f){f.value=p.get(k)||"";if(k!=="q"&&f.value!==(p.get(k)||""))f.value="";}});
    state.kw=p.get("kw")||"";
  }
  function writeHash(){
    var p=new URLSearchParams();
    KEYS.forEach(function(k){var v=el("f-"+k).value;if(v)p.set(k,v);});
    if(state.kw)p.set("kw",state.kw);
    var s=p.toString();
    history.replaceState(null,"",s?"#"+s:location.pathname+location.search);
  }
  // 급증 키워드: 영문은 단어 경계로 비교한다 ('act' 가 'action' 에 걸리지 않게). 한글은 조사가 붙으므로 포함 여부로.
  function hasWord(text,w){
    if(/[a-z0-9]/.test(w)&&/^[\x00-\x7f]+$/.test(w)){
      var re=new RegExp("(^|[^a-z0-9])"+w.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")+"($|[^a-z0-9])");return re.test(text);}
    return text.indexOf(w)>=0;
  }
  function matches(it,c){
    var d=it.dataset, news=d.kind==="news";
    if(c.days){var t=new Date(d.date);if(isNaN(t)||(gen-t)>c.days*864e5)return false;}
    if(c.topic&&split(d.topics).indexOf(c.topic)<0)return false;
    if(c.ai&&d.ai!==c.ai)return false;
    if(c.stage&&split(d.stages).indexOf(c.stage)<0)return false;
    if(c.impact&&split(d.impacts).indexOf(c.impact)<0)return false;
    if(news){
      if(c.region&&split(d.regions).indexOf(c.region)<0)return false;
      if(c.tier&&d.tier!==c.tier)return false;
      if(c.conf&&d.conf!==c.conf)return false;
    }
    var title=(d.title||"").toLowerCase();
    if(c.q&&(title+" "+(d.summary||"").toLowerCase()).indexOf(c.q.toLowerCase())<0)return false;
    if(c.kw){var ws=c.kw.toLowerCase().split(/\s+/);for(var i=0;i<ws.length;i++){if(ws[i]&&!hasWord(title,ws[i]))return false;}}
    return true;
  }
  function apply(){
    var c={kw:state.kw};
    KEYS.forEach(function(k){c[k]=el("f-"+k).value.trim();});
    c.days=c.days?parseInt(c.days,10):0;
    [["news","news-list","news-count","뉴스"],["official","official-list","official-count","공식 발표"]].forEach(function(s){
      var list=el(s[1]);var cnt=el(s[2]);if(!list){if(cnt)cnt.textContent="";return;}
      var items=list.querySelectorAll(".item"),n=0;
      items.forEach(function(it){var ok=matches(it,c);it.hidden=!ok;if(ok)n++;});
      cnt.textContent=s[3]+" "+n+"건 표시 / 전체 "+items.length+"건";
      var empty=list.parentNode.querySelector(".filtered-empty");if(empty)empty.hidden=n>0;
    });
    document.querySelectorAll(".chip[data-term]").forEach(function(b){b.setAttribute("aria-pressed",b.getAttribute("data-term")===state.kw?"true":"false");});
    var ks=el("kw-state");if(ks){ks.hidden=!state.kw;ks.textContent=state.kw?"급증 키워드: “"+state.kw+"” (키워드를 다시 누르면 해제)":"";}
    writeHash();
  }
  el("filter-form").addEventListener("input",apply);
  el("filter-form").addEventListener("change",apply);
  el("filter-form").addEventListener("reset",function(){state.kw="";setTimeout(apply,0);});
  document.querySelectorAll(".chip[data-term]").forEach(function(b){
    b.addEventListener("click",function(){var t=b.getAttribute("data-term");state.kw=(state.kw===t)?"":t;apply();
      var n=el("news");if(n&&state.kw)n.scrollIntoView({block:"start"});});
  });
  window.addEventListener("hashchange",function(){readHash();apply();});
  if(window.matchMedia&&window.matchMedia("(max-width:860px)").matches&&!location.hash){el("filter-panel").open=false;}
  readHash();apply();
})();
"""


def render_report(data: dict) -> str:
    date = escape(data["generated_at"][:10])
    days = int(data["period_days"])
    n_tier3 = int(data.get("excluded_tier3", 0))
    n_irrelevant = int(data.get("excluded_count", 0))
    llm = data.get("llm_stats") or {}
    stats = [f'<li>기간 <strong>최근 {days}일</strong></li>',
             f'<li>기사 <strong>{int(data["total_articles"])}건</strong></li>',
             f'<li>탄소 정책과 무관한 기사 <strong>{n_irrelevant}건</strong> 제외</li>']
    if n_tier3:
        stats.append(f'<li>단체·업계 주장 <strong>{n_tier3}건</strong> (집계 제외, 목록에는 표시)</li>')
    if llm.get("total"):
        stats.append(f'<li>AI 분류·요약 <strong>{int(llm["done"])}/{int(llm["total"])}건</strong></li>')
    excluded_note = ('<p class="note">무관 기사는 삭제하지 않고 집계와 목록에서만 뺐습니다.</p>' if n_irrelevant else "")

    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>탄소정책 모니터링 {date}</title>
<style>{CSS}</style></head>
<body data-generated="{escape(data["generated_at"], quote=True)}">
<a class="skip" href="#news">뉴스 목록으로 건너뛰기</a>
<header class="top" data-testid="summary">
<h1>탄소정책 일일 모니터링 — <span class="nowrap">{date}</span></h1>
<ul class="stats">{"".join(stats)}</ul>{excluded_note}
{_summary_block(data)}
</header>
<div class="layout">
{_filters(data)}
<main id="main">
{_official_section(data)}
{_agency_section(data)}
{_rising_section(data)}
{_distribution_section(data)}
{_news_section(data)}
</main>
</div>
<footer>뉴스 제목은 화제성 신호로만 씁니다. 정책 단계·국내 영향도는 공식 문서에서만 판정하고, 뉴스는 연결된 공식 문서의 값을 따릅니다.</footer>
<script>{JS}</script>
</body></html>
"""

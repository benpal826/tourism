import inspect

from carbon import render
from tests.conftest import NOW

EMPTY = {"generated_at": NOW.isoformat(), "period_days": 7, "total_articles": 0,
         "per_day": [], "topics": [], "regions": [], "rising_terms": [], "articles": [], "official": [], "excluded_tier3": 0, "agencies": [], "agencies_note": "",
         "policy_summary": {"official_total": 0, "stage": {"decided": 0, "proposed": 0, "unknown": 0},
                            "impact": {"direct": 0, "indirect": 0, "reference": 0, "unknown": 0},
                            "news_total": 0, "news_confirmed": 0, "news_unconfirmed": 0}}


def data_with(**kw):
    return {**EMPTY, **kw}


def test_empty_sections_show_placeholder():
    html = render.render_report(EMPTY)
    # 오늘의 요약(결론·보고할 것·흐름), 공식 발표, 기관 중요도, 급증 키워드, 일별 차트, 주제, 지역, 뉴스 — 10곳 모두 "해당 없음"
    assert html.count("해당 없음") == 10
    assert "<h1>" in html and "2026-11-03" in html


def test_report_notes_how_many_irrelevant_articles_were_excluded():
    html = render.render_report(data_with(excluded_count=15))
    assert "탄소 정책과 무관한 기사 <strong>15건</strong> 제외" in html and "삭제하지 않고 집계와 목록에서만 뺐습니다" in html
    zero = render.render_report(data_with(excluded_count=0))     # 3단계: 제외 건수는 0이어도 상단에 늘 표시
    assert "탄소 정책과 무관한 기사 <strong>0건</strong> 제외" in zero and "삭제하지 않고" not in zero


def test_official_section_shows_agency_and_escapes():
    off = {"title": "<img src=x onerror=alert(1)>", "url": "javascript:alert(1)", "agency": "기후에너지환경부<b>",
           "board": "보도자료", "published": "2026-11-03T00:00:00+09:00", "topics": ["CBAM/탄소국경"],
           "stage": "proposed", "impact": "direct", "impact_score": 95.0, "impact_keyword": "배출권거래제<i>"}
    html = render.render_report(data_with(official=[off]))
    assert "공식 발표" in html and "기후에너지환경부&lt;b&gt;" in html
    assert "<img src=x" not in html and "javascript:" not in html and "<i>" not in html


def test_official_section_shows_stage_and_impact_labels():
    base = {"title": "t", "url": "https://x.test/a", "agency": "기관", "board": "게시판",
            "published": "2026-11-03T00:00:00+09:00", "topics": []}
    rows = [
        {**base, "stage": "decided", "impact": "direct", "impact_score": 95.0, "impact_keyword": "배출권거래제"},
        {**base, "stage": "proposed", "impact": "reference", "impact_score": 25.0, "impact_keyword": "cop"},
        {**base, "stage": "unknown", "impact": "unknown", "impact_score": None, "impact_keyword": ""},
    ]
    html = render.render_report(data_with(official=rows))
    assert "확정" in html and "추진" in html and "미분류" in html
    assert "영향도 근거: 배출권거래제, 95점" in html and "영향도 근거: cop, 25점" in html
    assert 'b-impact-direct' in html and 'b-impact-reference' in html and 'b-stage-decided' in html
    # 확정이면서 직접 규제인 항목만 가장 눈에 띄게 (강조 배지 1개)
    assert html.count('class="item official hot"') == 1 and html.count("확정 · 직접 규제") == 1


def test_user_data_is_escaped():
    art = {"title": "<script>alert(1)</script>", "url": "https://example.com/?a=1&b=2", "source": "<b>x</b>",
           "published": "2026-11-03T01:00:00+00:00", "lang": "ko", "topics": ["<i>t</i>"], "regions": []}
    html = render.render_report(data_with(articles=[art], total_articles=1))
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert "<b>x</b>" not in html and "<i>t</i>" not in html


def test_news_shows_official_confirmation_or_unconfirmed_label():
    base = {"url": "https://n.test/a", "source": "언론", "published": "2026-11-03T01:00:00+09:00", "lang": "ko",
            "topics": [], "regions": []}
    confirmed = {**base, "title": "4기 배출권 할당 확정", "official_status": "confirmed", "official_links": [
        {"title": "배출권거래제 4기 할당계획 입법예고", "url": "https://mcee.go.kr/1", "agency": "기후에너지환경부",
         "score": 68.0, "stage": "proposed", "impact": "direct"}]}
    unconfirmed = {**base, "title": "충격! 대폭 삭감", "official_status": "unconfirmed", "official_links": []}
    html = render.render_report(data_with(articles=[confirmed, unconfirmed], total_articles=2))
    assert "확인됨 →" in html and "기후에너지환경부" in html and "추진 · 직접 규제" in html
    assert "공식 확인 안 됨" in html


def test_policy_summary_counts_are_shown():
    s = {"official_total": 12, "stage": {"decided": 3, "proposed": 5, "unknown": 4},
         "impact": {"direct": 6, "indirect": 2, "reference": 3, "unknown": 1},
         "news_total": 40, "news_confirmed": 9, "news_unconfirmed": 31}
    html = render.render_report(data_with(policy_summary=s))
    assert "공식 문서 12건 기준" in html and "확정 3 · 추진 5 · 미분류 4" in html
    assert "직접 규제 6 · 간접 2 · 참고 3 · 미분류 1" in html
    assert "공식 확인됨 9건, 공식 확인 안 됨 31건" in html


def test_linked_official_title_is_escaped():
    art = {"url": "https://n.test/a", "source": "s", "published": "2026-11-03T01:00:00+09:00", "lang": "ko", "topics": [],
           "regions": [], "title": "t", "official_status": "confirmed", "official_links": [
               {"title": "<script>x</script>", "url": "javascript:alert(1)", "agency": "<b>", "score": 70.0,
                "stage": "decided", "impact": "direct"}]}
    html = render.render_report(data_with(articles=[art], total_articles=1))
    assert "<script>x" not in html and "javascript:" not in html


def test_non_http_links_are_neutralized():
    art = {"title": "t", "url": "javascript:alert(1)", "source": "s",
           "published": "2026-11-03T01:00:00+00:00", "lang": "ko", "topics": [], "regions": []}
    html = render.render_report(data_with(articles=[art], total_articles=1))
    assert "javascript:" not in html
    assert 'rel="noopener"' in html


def test_render_does_not_depend_on_db_or_analysis():
    src = inspect.getsource(render)
    assert "import db" not in src and "analysis" not in src and "sqlite3" not in src


ART = {"title": "기사", "url": "https://n.test/a", "source": "언론", "published": "2026-11-03T10:00:00+09:00", "lang": "ko",
       "topics": ["CBAM/탄소국경"], "regions": ["EU"], "official_status": "unconfirmed", "official_links": [], "source_tier": 2}


def test_filter_controls_have_stable_ids_and_labels():
    html = render.render_report(data_with(articles=[ART], total_articles=1))
    for f in ("q", "days", "topic", "region", "ai", "stage", "impact", "tier", "conf"):
        assert f'id="f-{f}"' in html and f'data-testid="filter-{f}"' in html and f'<label for="f-{f}">' in html
    assert 'data-testid="filter-reset"' in html and 'id="news-count"' in html and 'id="news-empty"' in html
    assert '<option value="CBAM/탄소국경">' in html and '<option value="EU">' in html


def test_self_contained_without_external_resources():
    html = render.render_report(data_with(articles=[ART], total_articles=1))
    assert "<link" not in html and "<script src" not in html and "@import" not in html and "url(" not in html
    assert "prefers-color-scheme:dark" in html and "@media print" in html


def test_claims_and_sensational_are_marked():
    claim = {**ART, "title": "협회 주장", "source_tier": 3, "single_source": True, "sensational": ["충격"]}
    html = render.render_report(data_with(articles=[claim], total_articles=1))
    assert 'class="item news tier-3"' in html and "단체 주장" in html and "단일 출처 주장" in html
    assert "자극적 표현: 충격" in html


def test_news_item_carries_filter_attributes_from_linked_official_docs():
    conf = {**ART, "official_status": "confirmed", "ai_impact": "high", "official_links": [
        {"title": "고시", "url": "https://mcee.go.kr/1", "agency": "기후에너지환경부", "score": 70, "stage": "decided", "impact": "direct"}]}
    html = render.render_report(data_with(articles=[conf, ART], total_articles=2))
    assert 'data-conf="confirmed"' in html and 'data-stages="decided"' in html and 'data-impacts="direct"' in html
    assert 'data-conf="unconfirmed"' in html and 'data-stages=""' in html     # 연결 안 된 뉴스는 단계·영향도 없음
    assert "AI 중요도 높음" in html and 'href="https://mcee.go.kr/1"' in html


def test_rising_terms_are_sorted_by_ratio_and_clickable():
    terms = [{"term": "할당", "recent": 4, "baseline": 1.0, "ratio": 2.5}, {"term": "유예", "recent": 6, "baseline": 1.0, "ratio": 5.0}]
    html = render.render_report(data_with(rising_terms=terms))
    assert html.index('data-term="유예"') < html.index('data-term="할당"')
    assert html.count('data-testid="rising-term"') == 2 and "×5" in html


def test_charts_have_value_labels():
    per_day = [{"date": "2026-11-02", "count": 3}, {"date": "2026-11-03", "count": 0}]
    topics = [{"name": "CBAM/탄소국경", "count_7d": 5, "count_1d": 2}]
    html = render.render_report(data_with(per_day=per_day, topics=topics))
    assert 'aria-label="일별 기사 수: 2026-11-02 3건, 2026-11-03 0건"' in html and ">11-02</text>" in html
    assert '<span class="hb-val">5 (최근 1일 2)</span>' in html


def test_filter_data_attributes_are_escaped():
    bad = {**ART, "title": '"><img src=x onerror=alert(1)>', "topics": ['"><b>t']}
    html = render.render_report(data_with(articles=[bad], total_articles=1))
    assert "<img src=x" not in html and '"><b>' not in html


# ----------------------------------------------------------------------------- 오늘의 요약
def _item(**kw):
    base = {"id": "o1", "title": "배출권 할당계획 고시", "url": "https://me.go.kr/1", "agency": "기후에너지환경부",
            "published": "2026-11-03T09:00:00+09:00", "policy_stage": "decided", "domestic_impact": "direct",
            "why": "할당계획 확정", "origin": "ai", "related_news": 2}
    return {**base, **kw}


FLOW = {"dates": [f"2026-10-{d:02d}" for d in range(28, 32)] + ["2026-11-01", "2026-11-02", "2026-11-03"],
        "topics": [{"name": "CBAM/탄소국경", "counts": [0, 1, 0, 2, 0, 0, 3]}, {"name": "배출권거래제(ETS)", "counts": [1, 0, 0, 0, 0, 0, 1]}]}


def _summary(**kw):
    base = {"source": "ai", "conclusions": ["결론 하나", "결론 <둘>"], "briefing_text": None, "report_items": [_item()], "flow": FLOW}
    return {**base, **kw}


def test_summary_block_ai():
    html = render.render_report(data_with(daily_summary=_summary()))
    assert 'data-testid="daily-summary"' in html and 'data-testid="summary-source">AI 요약<' in html
    assert "<li>결론 하나</li>" in html and "결론 &lt;둘&gt;" in html
    assert 'href="https://me.go.kr/1" target="_blank" rel="noopener">배출권 할당계획 고시</a>' in html
    assert ">확정<" in html and ">직접 규제<" in html and "왜: 할당계획 확정" in html and "관련 보도 2건" in html
    assert "AI가 제목과 요약만 보고 작성했습니다" in html


def test_summary_block_rules_label_and_rule_origin_marker():
    html = render.render_report(data_with(daily_summary=_summary(source="rules", report_items=[_item(origin="rules", related_news=0)])))
    assert 'data-testid="summary-source">규칙 요약 (AI 요약 없음)<' in html
    assert 'title="규칙으로 고른 항목">규칙<' in html and "관련 보도" not in html


def test_summary_block_briefing_paragraph():
    html = render.render_report(data_with(daily_summary=_summary(source="briefing", conclusions=[], briefing_text="브리핑 <문단>")))
    assert 'data-testid="summary-source">AI 브리핑<' in html and "<p>브리핑 &lt;문단&gt;</p>" in html


def test_flow_chart_has_numeric_labels_and_title():
    html = render.render_report(data_with(daily_summary=_summary()))
    svg = html[html.index('data-testid="flow-chart"'):]
    svg = svg[: svg.index("</svg>")]
    assert svg.count('class="bar"') == 14 and "<title>" in svg and 'role="img"' in html
    assert ">3</text>" in svg and "CBAM/탄소국경" in svg


def test_flow_chart_all_zero_is_empty():
    flow = {**FLOW, "topics": [{"name": "CBAM/탄소국경", "counts": [0] * 7}]}
    html = render.render_report(data_with(daily_summary=_summary(flow=flow)))
    assert 'data-testid="flow-chart"' not in html

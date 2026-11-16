"""4-2 리포트 화면 자동 검증 (docs/qa-plan.md 의 UI-xx).

기대값은 화면(JS)이 아니라 analysis 가 만든 report_data 에서 따로 계산해 비교한다.
"""
import re
from datetime import datetime, timedelta

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def news_count(page) -> int:
    return page.locator("#news-list .item:not([hidden])").count()


def count_text(page, which="news") -> str:
    return page.locator(f"#{which}-count").inner_text()


def expected(data, pred) -> int:
    return sum(1 for a in data["articles"] if pred(a))


def _lum(rgb):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a, b) -> float:
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


CONTRAST_JS = """sel => Array.from(document.querySelectorAll(sel)).filter(e => e.offsetParent).slice(0, 40).map(e => {
  const rgb = s => s.match(/[\\d.]+/g).map(Number);
  let b = e, bg;
  while (b) { const c = rgb(getComputedStyle(b).backgroundColor); if (c.length < 4 || c[3] > 0) { bg = c; break; } b = b.parentElement; }
  return {fg: rgb(getComputedStyle(e).color).slice(0, 3), bg: (bg || [255, 255, 255]).slice(0, 3), text: e.textContent.trim().slice(0, 30)};
})"""


# 1. 로드 -----------------------------------------------------------------------------------
def test_ui01_load_without_errors(page, report_url):
    errors, failed, external = [], [], []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("requestfailed", lambda r: failed.append(r.url))
    page.on("request", lambda r: external.append(r.url) if not r.url.startswith(("file:", "data:")) else None)
    page.goto(report_url)
    expect(page.locator("h1")).to_contain_text("탄소정책 일일 모니터링 — 2026-11-03")
    expect(page.get_by_test_id("briefing")).to_contain_text("제4차 배출권 할당계획")
    assert errors == [] and failed == []
    assert external == []          # UI-26 오프라인: 외부 리소스 요청 없음


# 2. 섹션 -----------------------------------------------------------------------------------
def test_ui02_sections_render(page, report_url, report_data):
    page.goto(report_url)
    for sid in ("official", "rising", "distribution", "news"):
        expect(page.locator(f"section#{sid}")).to_be_visible()
    assert page.locator("#official-list .item").count() == len(report_data["official"])
    assert page.locator("#news-list .item").count() == len(report_data["articles"])
    assert page.get_by_test_id("rising-term").count() == len(report_data["rising_terms"]) > 0
    expect(page.get_by_test_id("day-chart")).to_be_visible()
    expect(page.get_by_test_id("topic-bars")).to_be_visible()
    expect(page.get_by_test_id("region-bars")).to_be_visible()


def test_ui03_empty_sections_say_none(page, empty_report_url):
    page.goto(empty_report_url)
    for sel in ("[data-testid=briefing]", "section#official", "section#rising", "section#news"):
        expect(page.locator(sel)).to_contain_text("해당 없음")
    assert page.locator("section#distribution .empty").count() == 2       # 주제·지역 (일별 차트는 0건 막대로 그림)


# 3. 필터 -----------------------------------------------------------------------------------
def test_ui04_topic_filter(page, report_url, report_data):
    page.goto(report_url)
    page.select_option("#f-topic", "CBAM/탄소국경")
    n = expected(report_data, lambda a: "CBAM/탄소국경" in a["topics"])
    assert n > 0 and news_count(page) == n
    assert count_text(page).startswith(f"뉴스 {n}건 표시")
    no = sum(1 for o in report_data["official"] if "CBAM/탄소국경" in o["topics"])
    assert page.locator("#official-list .item:not([hidden])").count() == no


def test_ui05_region_filter(page, report_url, report_data):
    page.goto(report_url)
    page.select_option("#f-region", "EU")
    n = expected(report_data, lambda a: "EU" in a["regions"])
    assert n > 0 and news_count(page) == n


def test_ui06_ai_impact_filter(page, report_url, report_data):
    page.goto(report_url)
    for level in ("high", "medium", "low"):
        page.select_option("#f-ai", level)
        assert news_count(page) == expected(report_data, lambda a: a["ai_impact"] == level) == 1


def test_ui07_stage_impact_filters_use_linked_docs(page, report_url, report_data):
    page.goto(report_url)
    page.select_option("#f-stage", "decided")
    # 뉴스는 연결된 공식 문서가 '확정'인 것만, 공식 발표는 자기 단계가 '확정'인 것만
    assert news_count(page) == expected(report_data, lambda a: any(l["stage"] == "decided" for l in a["official_links"])) == 1
    assert page.locator("#official-list .item:not([hidden])").count() == sum(o["stage"] == "decided" for o in report_data["official"])
    page.select_option("#f-stage", "")
    page.select_option("#f-impact", "direct")
    assert page.locator("#official-list .item:not([hidden])").count() == sum(o["impact"] == "direct" for o in report_data["official"])
    assert news_count(page) == 1


def test_ui08_tier_and_confirmation_filters(page, report_url, report_data):
    page.goto(report_url)
    page.select_option("#f-tier", "3")
    assert news_count(page) == expected(report_data, lambda a: a["source_tier"] == 3)
    page.select_option("#f-tier", "")
    page.select_option("#f-conf", "confirmed")
    assert news_count(page) == expected(report_data, lambda a: a["official_status"] == "confirmed") == 1
    page.select_option("#f-conf", "unconfirmed")
    assert news_count(page) == expected(report_data, lambda a: a["official_status"] != "confirmed")


def test_ui09_period_filter(page, report_url, report_data):
    page.goto(report_url)
    gen = datetime.fromisoformat(report_data["generated_at"])
    for days in (1, 3, 7):
        page.select_option("#f-days", str(days))
        n = expected(report_data, lambda a: gen - datetime.fromisoformat(a["published"]) <= timedelta(days=days))
        assert news_count(page) == n, days
    page.select_option("#f-days", "1")
    assert news_count(page) < len(report_data["articles"])     # 2·5일 전 기사가 실제로 빠진다


def test_ui10_title_search_case_insensitive(page, report_url, report_data):
    page.goto(report_url)
    page.fill("#f-q", "cbam")
    n = expected(report_data, lambda a: "cbam" in (a["title"] + " " + a["summary"]).lower())
    assert n > 0 and news_count(page) == n


def test_ui11_combined_filters(page, report_url, report_data):
    page.goto(report_url)
    page.select_option("#f-topic", "CBAM/탄소국경")
    page.select_option("#f-region", "EU")
    page.fill("#f-q", "철강")
    n = expected(report_data, lambda a: "CBAM/탄소국경" in a["topics"] and "EU" in a["regions"] and "철강" in a["title"])
    assert n >= 1 and news_count(page) == n


def test_ui12_no_results_message(page, report_url):
    page.goto(report_url)
    expect(page.get_by_test_id("news-empty")).to_be_hidden()
    page.fill("#f-q", "존재하지않는검색어")
    assert news_count(page) == 0
    expect(page.get_by_test_id("news-empty")).to_be_visible()


def test_ui13_state_persists_in_hash(page, report_url):
    page.goto(report_url)
    page.select_option("#f-topic", "배출권거래제(ETS)")
    page.select_option("#f-region", "한국")
    before = news_count(page)
    assert "topic=" in page.url and "region=" in page.url
    page.reload()
    assert page.input_value("#f-topic") == "배출권거래제(ETS)" and page.input_value("#f-region") == "한국"
    assert news_count(page) == before
    page.click("#f-reset")
    page.wait_for_function("() => !location.hash")
    assert news_count(page) == page.locator("#news-list .item").count()


# 4. 급증 키워드 ----------------------------------------------------------------------------
def _has_word(title: str, term: str) -> bool:
    t = title.lower()
    for w in term.lower().split():
        if re.fullmatch(r"[\x00-\x7f]+", w) and re.search(r"[a-z0-9]", w):
            if not re.search(rf"(^|[^a-z0-9]){re.escape(w)}($|[^a-z0-9])", t):
                return False
        elif w not in t:
            return False
    return True


def test_ui14_rising_term_click_filters(page, report_url, report_data):
    page.goto(report_url)
    checked = 0
    for t in report_data["rising_terms"][:6]:
        term = t["term"]
        btn = page.locator(f'[data-testid=rising-term][data-term="{term}"]')
        btn.click()
        titles = page.locator("#news-list .item:not([hidden])").evaluate_all("els => els.map(e => e.dataset.title)")
        assert all(_has_word(x, term) for x in titles), term
        assert len(titles) == expected(report_data, lambda a: _has_word(a["title"], term)), term
        assert btn.get_attribute("aria-pressed") == "true"
        btn.click()
        assert news_count(page) == len(report_data["articles"])
        checked += 1
    assert checked > 0


# 5. 링크 -----------------------------------------------------------------------------------
def test_ui15_external_links_open_safely(page, report_url):
    page.goto(report_url)
    links = page.locator("main a[href]").evaluate_all(
        "els => els.map(a => ({href: a.getAttribute('href'), target: a.target, rel: a.rel}))")
    assert len(links) > 50
    for l in links:
        assert l["href"].startswith(("http://", "https://")), l
        assert l["target"] == "_blank" and "noopener" in l["rel"], l


# 6. 반응형 ---------------------------------------------------------------------------------
@pytest.mark.parametrize("width", [360, 768, 1280])
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_ui16_responsive_no_horizontal_scroll(browser, report_url, qa_dir, width, scheme):
    ctx = browser.new_context(viewport={"width": width, "height": 900}, color_scheme=scheme)
    page = ctx.new_page()
    page.goto(report_url)
    sw, cw = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
    assert sw <= cw, (sw, cw)
    expect(page.locator("#filter-panel > summary")).to_be_visible()
    expect(page.get_by_test_id("news-list")).to_be_attached()
    if width <= 768:
        page.click("#filter-panel > summary") if not page.locator("#filter-panel").evaluate("e => e.open") else None
    expect(page.locator("#f-topic")).to_be_visible()
    page.screenshot(path=str(qa_dir / f"report_{scheme}_{width}.png"), full_page=False)
    ctx.close()


# 7. 다크 모드 대비 -------------------------------------------------------------------------
@pytest.mark.parametrize("scheme", ["dark", "light"])
def test_ui17_text_contrast(browser, report_url, scheme):
    ctx = browser.new_context(color_scheme=scheme)
    page = ctx.new_page()
    page.goto(report_url)
    bad = []
    for sel in ("body", "h1", "h2", ".meta", ".note", ".summary", ".badge", ".tag", "main a", ".chip", ".hb-val", "label"):
        for s in page.evaluate(CONTRAST_JS, sel):
            r = contrast(s["fg"], s["bg"])
            if r < 4.5:
                bad.append((sel, s["text"], round(r, 2)))
    ctx.close()
    assert bad == []


# 8. 접근성 ---------------------------------------------------------------------------------
def test_ui18_keyboard_reaches_all_filters_and_first_news_link(page, report_url):
    page.set_viewport_size({"width": 1280, "height": 900})
    page.goto(report_url)
    first_news_href = page.locator("#news-list .item a").first.get_attribute("href")
    want = {f"f-{k}" for k in ("q", "days", "topic", "region", "ai", "stage", "impact", "tier", "conf", "reset")}
    seen, reached_news, no_outline = set(), False, []
    for _ in range(400):
        page.keyboard.press("Tab")
        info = page.evaluate("""() => { const e = document.activeElement; const cs = getComputedStyle(e);
            return {id: e.id, href: e.getAttribute('href'), news: !!e.closest('#news-list'),
                    outline: cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0}; }""")
        if info["id"] in want:
            seen.add(info["id"])
        if not info["outline"]:
            no_outline.append(info["id"] or info["href"])
        if info["news"] and info["href"] == first_news_href:
            reached_news = True
            break
    assert want <= seen, want - seen
    assert reached_news
    assert no_outline == []


def test_ui19_accessible_names_and_axe(page, report_url):
    page.goto(report_url)
    unlabeled = page.evaluate("""() => Array.from(document.querySelectorAll('select, input, button')).filter(e => {
        const lab = e.id && document.querySelector('label[for="' + e.id + '"]');
        return !(lab || e.getAttribute('aria-label') || e.textContent.trim()); }).map(e => e.outerHTML.slice(0, 80))""")
    assert unlabeled == []
    assert page.locator("svg[role=img][aria-label]").count() == page.locator("svg").count() > 0
    axe_mod = pytest.importorskip("axe_playwright_python.sync_playwright")
    results = axe_mod.Axe().run(page)
    violations = [(v["id"], v["impact"], len(v["nodes"])) for v in results.response["violations"]]
    assert violations == []


# 9. 보안 -----------------------------------------------------------------------------------
def test_ui20_script_in_title_is_not_executed(page, report_url):
    dialogs = []
    page.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
    page.goto(report_url)
    page.fill("#f-q", "시험 기사")
    expect(page.locator("#news-list .item:not([hidden]) .title")).to_have_text("<script>alert(1)</script> 배출권 시험 기사")
    assert dialogs == []
    assert page.evaluate("document.querySelectorAll('main script, #news-list script').length") == 0


# 추가 화면 항목 ------------------------------------------------------------------------------
def test_ui21_decided_direct_is_highlighted_first(page, report_url):
    page.goto(report_url)
    first = page.locator("#official-list .item").first
    expect(first).to_have_class(re.compile(r"\bhot\b"))
    expect(first).to_contain_text("확정 · 직접 규제")
    assert page.locator("#official-list .item.hot").count() == 1


def test_ui22_claims_and_sensational_marked(page, report_url):
    page.goto(report_url)
    claim = page.locator('#news-list .item[data-tier="3"]')
    expect(claim).to_have_count(1)
    expect(claim).to_contain_text("단체 주장")
    expect(claim).to_contain_text("단일 출처 주장")
    expect(claim.locator(".b-sens")).to_have_text("자극적 표현")


def test_ui23_official_confirmation(page, report_url):
    page.goto(report_url)
    conf = page.locator('#news-list .item[data-conf="confirmed"]')
    expect(conf).to_contain_text("공식 확인됨")
    expect(conf.locator(".links a")).to_have_attribute("href", "https://mcee.go.kr/sample/hot")
    unconf = page.locator('#news-list .item[data-conf="unconfirmed"]')
    assert unconf.count() == page.locator("#news-list .item").count() - 1
    expect(unconf.first).to_contain_text("공식 확인 안 됨")


def test_ui24_times_shown_in_kst(page, report_url):
    page.goto(report_url)
    # 연결된 뉴스는 07:00 UTC 발행 → 화면에는 16:00 KST
    expect(page.locator('#news-list .item[data-conf="confirmed"] .meta')).to_contain_text("2026-11-03 16:00")


def test_ui25_print_hides_filters(page, report_url):
    page.goto(report_url)
    page.emulate_media(media="print")
    expect(page.locator("#filters")).to_be_hidden()
    expect(page.get_by_test_id("news-list")).to_be_visible()


# 10. 오늘의 요약 ---------------------------------------------------------------------------
def test_ui27_summary_source_labels(page, report_url, ai_summary_report_url, empty_report_url):
    for url, label in ((ai_summary_report_url, "AI 요약"), (report_url, "AI 브리핑"), (empty_report_url, "규칙 요약 (AI 요약 없음)")):
        page.goto(url)
        expect(page.get_by_test_id("summary-source")).to_have_text(label)
    page.goto(ai_summary_report_url)
    expect(page.get_by_test_id("briefing").locator("li")).to_have_count(3)


def test_ui28_report_items_link_safely_and_flow_chart_visible(page, ai_summary_report_url):
    page.goto(ai_summary_report_url)
    items = page.get_by_test_id("report-items").locator("li")
    expect(items).to_have_count(1)
    expect(items.first).to_contain_text("왜: 보고 이유")
    link = items.first.locator("a")
    assert link.get_attribute("target") == "_blank" and "noopener" in link.get_attribute("rel")
    expect(page.get_by_test_id("flow-chart")).to_be_visible()


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_ui29_summary_visible_in_dark_and_print_and_axe_clean(browser, ai_summary_report_url, scheme):
    ctx = browser.new_context(color_scheme=scheme)
    page = ctx.new_page()
    page.goto(ai_summary_report_url)
    page.emulate_media(media="print")
    expect(page.get_by_test_id("daily-summary")).to_be_visible()
    page.emulate_media(media="screen")
    axe_mod = pytest.importorskip("axe_playwright_python.sync_playwright")
    results = axe_mod.Axe().run(page)
    assert [(v["id"], v["impact"]) for v in results.response["violations"]] == []
    ctx.close()

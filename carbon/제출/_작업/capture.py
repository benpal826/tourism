from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'제출'
with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1280,'height':950},device_scale_factor=1)
    for src,dst in [('prompt.html','01_에이전트_시작.png'),('log.html','02_중간_도구실행.png')]:
        page.goto((OUT/'_작업'/src).as_uri())
        page.screenshot(path=str(OUT/'screenshots'/dst),full_page=True)
        print(dst,page.locator('body').bounding_box())
    page.set_viewport_size({'width':1440,'height':1220})
    page.goto((ROOT/'reports/report_2026-11-13.html').as_uri())
    page.get_by_text('오늘의 요약',exact=False).first.wait_for()
    page.screenshot(path=str(OUT/'screenshots/03_최종결과.png'))
    print('Final report screenshot captured', page.title())
    browser.close()

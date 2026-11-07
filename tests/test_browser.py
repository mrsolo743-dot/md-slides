"""Сквозные проверки собранной страницы в настоящем браузере (Playwright).

Пропускаются, если Playwright/Chromium не установлен:
    pip install playwright && python -m playwright install chromium
"""

import pytest

from md_slides.deck import parse_deck
from md_slides.render import build_html

sync_api = pytest.importorskip("playwright.sync_api")

DECK = """---
title: Тест
theme: light
---
# Один
Note: заметка **один**
---
<!-- fragments -->
## Два
- a
- b
---
## Три
```python
print(1)
```
"""


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as exc:  # браузер не скачан
            pytest.skip(f"Chromium недоступен: {exc}")
        yield b
        b.close()


@pytest.fixture
def page(browser, tmp_path):
    path = tmp_path / "deck.html"
    path.write_text(build_html(parse_deck(DECK)), encoding="utf-8")
    pg = browser.new_page(viewport={"width": 1280, "height": 720})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.goto(path.as_uri())
    pg.errors = errors
    yield pg
    assert errors == [], errors
    pg.close()


def active(pg):
    return pg.evaluate("window.mdSlides.current")


def test_navigation_and_fragments(page):
    assert active(page) == 0
    assert page.inner_text(".counter") == "1 / 3"
    page.keyboard.press("ArrowRight")
    assert active(page) == 1
    assert page.evaluate("mdSlides.visibleFragments") == 0
    page.keyboard.press("Space")
    page.keyboard.press("Space")
    assert page.evaluate("mdSlides.visibleFragments") == 2
    assert active(page) == 1
    page.keyboard.press("ArrowRight")
    assert active(page) == 2
    assert page.url.endswith("#3")
    page.keyboard.press("ArrowLeft")
    assert active(page) == 1
    assert page.evaluate("mdSlides.visibleFragments") == 2  # назад — со всеми фрагментами
    page.keyboard.press("Home")
    assert active(page) == 0
    page.keyboard.press("End")
    assert page.inner_text(".counter") == "3 / 3"


def test_only_active_slide_visible(page):
    visible = page.eval_on_selector_all(".stage > .slide", "els => els.map(e => getComputedStyle(e).display)")
    assert visible == ["flex", "none", "none"]


def test_hash_opens_slide(page):
    page.goto(page.url.split("#")[0] + "#3")
    page.reload()
    assert active(page) == 2


def test_goto_by_number_and_title(page):
    page.keyboard.press("g")
    assert page.is_visible("#goto-input")
    page.fill("#goto-input", "3")
    page.keyboard.press("Enter")
    assert active(page) == 2
    page.keyboard.press("g")
    page.fill("#goto-input", "два")
    page.keyboard.press("Enter")
    assert active(page) == 1


def test_presenter_mode(page):
    page.keyboard.press("p")
    assert page.is_visible(".presenter-ui")
    assert "заметка" in page.inner_text(".pres-notes")
    assert page.query_selector(".pres-next .slide") is not None
    page.keyboard.press("End")
    assert "Конец презентации" in page.inner_text(".pres-next")
    page.keyboard.press("p")
    assert not page.is_visible(".presenter-ui")


def test_overview_click(page):
    page.keyboard.press("o")
    assert page.locator(".thumb").count() == 3
    page.locator(".thumb").nth(2).click()
    assert active(page) == 2
    assert not page.is_visible("#overview")


def test_theme_cycle_and_help(page):
    assert page.get_attribute("body", "data-theme") == "light"
    page.keyboard.press("t")
    assert page.get_attribute("body", "data-theme") == "dark"
    page.keyboard.press("?")
    assert page.is_visible("#help")
    page.keyboard.press("Escape")
    assert not page.is_visible("#help")


def test_slide_scales_to_viewport(page):
    page.set_viewport_size({"width": 640, "height": 360})
    box = page.locator(".slide.active").bounding_box()
    assert box["width"] <= 640 and box["height"] <= 360
    assert box["width"] > 500


def test_print_shows_all_slides(page):
    page.emulate_media(media="print")
    displays = page.eval_on_selector_all(".stage > .slide", "els => els.map(e => getComputedStyle(e).display)")
    assert displays == ["flex"] * 3

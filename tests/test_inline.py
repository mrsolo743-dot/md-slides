import pytest

from md_slides.inline import is_safe_url, render_inline


@pytest.mark.parametrize(
    "src, expected",
    [
        ("**жирный**", "<strong>жирный</strong>"),
        ("__жирный__", "<strong>жирный</strong>"),
        ("*курсив*", "<em>курсив</em>"),
        ("_курсив_", "<em>курсив</em>"),
        ("~~нет~~", "<del>нет</del>"),
        ("`a < b`", "<code>a &lt; b</code>"),
        ("``код с ` внутри``", "<code>код с ` внутри</code>"),
    ],
)
def test_basic_inline(src, expected):
    assert render_inline(src) == expected


def test_html_is_escaped():
    assert render_inline("<script>alert(1)</script>") == "&lt;script&gt;alert(1)&lt;/script&gt;"


def test_markup_inside_code_is_literal():
    assert render_inline("`**не жирный**`") == "<code>**не жирный**</code>"


def test_snake_case_is_not_italic():
    assert render_inline("snake_case_name") == "snake_case_name"


def test_backslash_escape():
    assert render_inline(r"\*звёздочки\*") == "*звёздочки*"


def test_link_with_title_and_markup():
    out = render_inline('[**сайт**](https://example.com "Пример")')
    assert out == '<a href="https://example.com" title="Пример"><strong>сайт</strong></a>'


def test_javascript_link_is_not_rendered():
    out = render_inline("[клик](javascript:alert(1))")
    assert "<a" not in out
    assert "javascript" in out  # показан как текст


def test_image():
    assert render_inline("![кот](img/cat.png)") == '<img src="img/cat.png" alt="кот">'


def test_image_resolver_is_used():
    out = render_inline("![x](a.png)", resolve_image=lambda s: "data:image/png;base64,AAA")
    assert 'src="data:image/png;base64,AAA"' in out


def test_autolink():
    assert render_inline("<https://a.b/c>") == '<a href="https://a.b/c">https://a.b/c</a>'


def test_quotes_in_attributes_are_escaped():
    out = render_inline('![a"b](x.png)')
    assert 'alt="a&quot;b"' in out


@pytest.mark.parametrize("url, ok", [
    ("https://x.y", True), ("mailto:a@b.c", True), ("#3", True), ("img/a.png", True),
    ("javascript:alert(1)", False), ("JAVASCRIPT:x", False), ("vbscript:x", False), ("data:text/html,x", False),
])
def test_is_safe_url(url, ok):
    assert is_safe_url(url) is ok

import json
import re

import pytest

from md_slides.deck import parse_deck
from md_slides.render import BuildError, BuildOptions, build_file, build_html

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082"
)


def config_of(page: str) -> dict:
    raw = re.search(r'<script type="application/json" id="md-slides-config">(.*?)</script>', page, re.S).group(1)
    return json.loads(raw)


def test_basic_page_structure():
    page = build_html(parse_deck("---\ntitle: T & T\n---\n# A\n---\n# B"))
    assert page.startswith("<!doctype html>")
    assert "<title>T &amp; T</title>" in page
    assert page.count('<section class="slide"') == 2
    assert "{{" not in page  # все плейсхолдеры подставлены
    assert config_of(page)["title"] == "T & T"


def test_theme_from_meta_and_override():
    deck = parse_deck("---\ntheme: dark\n---\n# A")
    assert 'data-theme="dark"' in build_html(deck)
    assert 'data-theme="sepia"' in build_html(deck, BuildOptions(theme="sepia"))


def test_unknown_theme_raises():
    with pytest.raises(BuildError, match="тема"):
        build_html(parse_deck("# A"), BuildOptions(theme="neon"))


def test_aspect():
    page = build_html(parse_deck("---\naspect: 4:3\n---\n# A"))
    assert config_of(page)["height"] == 960
    with pytest.raises(BuildError):
        build_html(parse_deck("# A"), BuildOptions(aspect="21:9"))


def test_empty_deck_raises():
    with pytest.raises(BuildError, match="нет ни одного слайда"):
        build_html(parse_deck("\n---\n"))


def test_notes_rendered_in_aside():
    page = build_html(parse_deck("# A\nNote: **важно**"))
    assert '<aside class="notes"><p><strong>важно</strong></p></aside>' in page


def test_directives_applied():
    page = build_html(parse_deck("<!-- class: center -->\n<!-- background: #123456 -->\n<!-- fragments -->\n# A\n- x"))
    assert 'class="slide center"' in page
    assert 'style="background:#123456"' in page
    assert '<li class="fragment">x</li>' in page


def test_unsafe_directive_values_rejected():
    opts = BuildOptions()
    page = build_html(parse_deck('<!-- background: red;"><script> -->\n<!-- class: a"b -->\n# A'), opts)
    assert "<script>" not in page.split("<script type")[0]
    assert len(opts.warnings) == 2


def test_footer_and_pagination():
    page = build_html(parse_deck("---\nfooter: *Доклад*\npaginate: true\n---\n# A\n---\n# B"))
    assert '<div class="footer"><span><em>Доклад</em></span><span>2 / 2</span></div>' in page


def test_config_json_cannot_break_script():
    page = build_html(parse_deck("---\ntitle: </script><b>x\n---\n# A"))
    assert config_of(page)["title"] == "</script><b>x"


def test_template_values_not_reinterpreted():
    page = build_html(parse_deck("# {{css}}"))
    assert "<h1>{{css}}</h1>" in page


def test_build_file_writes_next_to_source(tmp_path):
    src = tmp_path / "talk.md"
    src.write_text("# Привет", encoding="utf-8")
    out = build_file(src)
    assert out == tmp_path / "talk.html"
    assert "<h1>Привет</h1>" in out.read_text(encoding="utf-8")


def test_build_file_missing_source(tmp_path):
    with pytest.raises(BuildError, match="не найден"):
        build_file(tmp_path / "nope.md")


def test_embed_images(tmp_path):
    (tmp_path / "img").mkdir()
    (tmp_path / "img" / "dot.png").write_bytes(PNG)
    src = tmp_path / "talk.md"
    src.write_text("![точка](img/dot.png)\n\n![нет](missing.png)\n\n![web](https://x.y/a.png)", encoding="utf-8")
    opts = BuildOptions(embed_images=True)
    page = build_file(src, tmp_path / "out" / "talk.html", opts).read_text(encoding="utf-8")
    assert 'src="data:image/png;base64,' in page
    assert 'src="missing.png"' in page
    assert 'src="https://x.y/a.png"' in page
    assert opts.warnings == ["картинка не найдена: missing.png"]


def test_example_deck_builds():
    from importlib import resources
    text = resources.files("md_slides").joinpath("assets", "example.md").read_text(encoding="utf-8")
    page = build_html(parse_deck(text))
    assert page.count('<section class="slide') == 7

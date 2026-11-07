from md_slides.markdown import render_markdown


def test_headings():
    assert render_markdown("# A\n## B ##") == "<h1>A</h1>\n<h2>B</h2>"


def test_paragraphs_and_hard_break():
    out = render_markdown("строка 1  \nстрока 2\n\nабзац 2")
    assert out == "<p>строка 1<br>\nстрока 2</p>\n<p>абзац 2</p>"


def test_fenced_code_with_language():
    out = render_markdown("```python\nx = 1\n```")
    assert out.startswith('<pre data-lang="python"><code class="language-python">')
    assert "tok-number" in out


def test_fence_keeps_markdown_literal():
    out = render_markdown("~~~\n# не заголовок\n- не список\n~~~")
    assert "<h1>" not in out and "<li>" not in out
    assert "# не заголовок" in out


def test_unclosed_fence_runs_to_end():
    out = render_markdown("```\ncode")
    assert "<pre><code>code</code></pre>" == out


def test_unordered_list_tight():
    assert render_markdown("- a\n- b") == "<ul>\n<li>a</li>\n<li>b</li>\n</ul>"


def test_ordered_list_with_start():
    out = render_markdown("3. c\n4. d")
    assert out.startswith('<ol start="3">')


def test_nested_list():
    out = render_markdown("- a\n  - b\n  - c\n- d")
    assert out == "<ul>\n<li>a\n<ul>\n<li>b</li>\n<li>c</li>\n</ul></li>\n<li>d</li>\n</ul>"


def test_loose_list_wraps_paragraphs():
    out = render_markdown("- a\n\n- b")
    assert "<li><p>a</p></li>" in out


def test_task_list():
    out = render_markdown("- [x] готово\n- [ ] нет")
    assert '<ul class="tasks">' in out
    assert '<input type="checkbox" disabled checked> готово' in out
    assert '<input type="checkbox" disabled> нет' in out


def test_fragments_mark_list_items():
    out = render_markdown("- a\n- b", fragments=True)
    assert out.count('class="fragment"') == 2


def test_blockquote_with_nested_blocks():
    out = render_markdown("> # Заголовок\n> - пункт\n>\n> текст")
    assert out.startswith("<blockquote>")
    assert "<h1>Заголовок</h1>" in out and "<li>пункт</li>" in out and "<p>текст</p>" in out


def test_table_with_alignment():
    md = "| A | B | C |\n|:--|:-:|--:|\n| 1 | 2 | 3 |"
    out = render_markdown(md)
    assert '<th style="text-align:left">A</th>' in out
    assert '<td style="text-align:center">2</td>' in out
    assert '<td style="text-align:right">3</td>' in out


def test_table_pipe_in_code_and_escaped():
    out = render_markdown("| a | b |\n|---|---|\n| `x|y` | c \\| d |")
    assert "<code>x|y</code>" in out
    assert "c | d" in out


def test_table_short_rows_are_padded():
    out = render_markdown("| a | b |\n|---|---|\n| 1 |")
    assert out.count("<td>") == 2


def test_hr():
    assert render_markdown("***") == "<hr>"


def test_paragraph_interrupted_by_list():
    out = render_markdown("Текст:\n- пункт")
    assert out == "<p>Текст:</p>\n<ul>\n<li>пункт</li>\n</ul>"


def test_raw_html_is_escaped():
    assert render_markdown("<div onclick=x>hi</div>") == "<p>&lt;div onclick=x&gt;hi&lt;/div&gt;</p>"


def test_crlf_and_tabs():
    assert render_markdown("# A\r\n\r\n-\tb") == "<h1>A</h1>\n<ul>\n<li>b</li>\n</ul>"

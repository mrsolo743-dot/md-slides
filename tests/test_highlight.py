from md_slides.highlight import highlight, normalize_lang, supported_languages


def test_python_tokens():
    out = highlight('def f(x):\n    return "s"  # c', "python")
    assert '<span class="tok-keyword">def</span>' in out
    assert '<span class="tok-function">f</span>' in out
    assert '<span class="tok-string">&quot;s&quot;</span>' in out
    assert '<span class="tok-comment"># c</span>' in out


def test_keyword_inside_string_is_not_highlighted():
    out = highlight('x = "for if while"', "python")
    assert "tok-keyword" not in out


def test_aliases():
    assert normalize_lang("JS") == "javascript"
    assert normalize_lang("py") == "python"
    assert normalize_lang("sh") == "bash"


def test_unknown_language_is_escaped_only():
    assert highlight("<b>", "brainfuck") == "&lt;b&gt;"


def test_javascript_and_bash():
    js = highlight("const a = 1; // hi", "js")
    assert '<span class="tok-keyword">const</span>' in js and "tok-comment" in js
    sh = highlight('echo "$HOME" # x', "bash")
    assert '<span class="tok-builtin">echo</span>' in sh and "tok-comment" in sh


def test_text_preserved():
    code = "for i in range(10):\n    print(i ** 2)"
    import re
    import html
    stripped = html.unescape(re.sub(r"<[^>]+>", "", highlight(code, "python")))
    assert stripped == code


def test_supported_languages():
    assert {"python", "javascript", "bash", "css", "html", "json"} <= set(supported_languages())

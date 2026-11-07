from md_slides.deck import parse_deck, parse_front_matter, split_slides


def test_front_matter_parsed():
    deck = parse_deck("---\ntitle: Доклад\ntheme: 'dark'\n---\n# Слайд")
    assert deck.meta == {"title": "Доклад", "theme": "dark"}
    assert len(deck.slides) == 1
    assert deck.title == "Доклад"


def test_leading_separator_without_meta_is_not_front_matter():
    meta, rest = parse_front_matter(["---", "# Привет", "---", "# Два"])
    assert meta == {}
    assert rest[0] == "---"


def test_split_ignores_separator_in_code():
    chunks = split_slides(["# A", "```", "---", "```", "---", "# B"])
    assert len(chunks) == 2
    assert "---" in chunks[0]


def test_empty_slides_dropped():
    deck = parse_deck("# A\n---\n\n---\n# B\n---\n")
    assert [s.title for s in deck.slides] == ["A", "B"]


def test_notes_extracted():
    deck = parse_deck("# A\nтекст\n\nNote: секрет\nвторая строка")
    s = deck.slides[0]
    assert "секрет" not in s.source
    assert s.notes == "секрет\nвторая строка"


def test_russian_notes_keyword():
    deck = parse_deck("# A\nЗаметки: тут")
    assert deck.slides[0].notes == "тут"


def test_note_inside_code_is_not_note():
    deck = parse_deck("```\nNote: код\n```")
    assert deck.slides[0].notes == ""
    assert "Note: код" in deck.slides[0].source


def test_directives():
    deck = parse_deck("<!-- class: center big -->\n<!-- fragments -->\n<!-- unknown: x -->\n# A")
    s = deck.slides[0]
    assert s.directives == {"class": "center big", "fragments": "true"}
    assert "<!-- unknown: x -->" in s.source  # неизвестные комментарии остаются как текст


def test_title_fallbacks():
    deck = parse_deck("просто текст")
    assert deck.slides[0].title == "Слайд 1"
    assert deck.title == "Слайд 1"


def test_indexes_sequential():
    deck = parse_deck("# 1\n---\n# 2\n---\n# 3")
    assert [s.index for s in deck.slides] == [0, 1, 2]

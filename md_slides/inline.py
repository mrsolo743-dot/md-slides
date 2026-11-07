"""Разбор строчной (inline) разметки Markdown.

Поддерживается: `код`, **жирный**, *курсив* / _курсив_, ~~зачёркнутый~~,
[ссылки](url "заголовок"), ![картинки](src), автоссылки <https://...>,
экранирование символов обратной косой чертой.

Весь пользовательский текст экранируется, «сырой» HTML не пропускается.
"""

from __future__ import annotations

import html
import re
from typing import Callable, Optional

# Функция, которая может подменить src картинки (например, встроить data: URI).
ImageResolver = Callable[[str], str]

_PLACEHOLDER = "\x00{}\x00"
_PLACEHOLDER_RE = re.compile("\x00(\\d+)\x00")

_ESCAPABLE = r"\\`*_{}[]()#+-.!~|<>"
_SAFE_SCHEMES = ("http://", "https://", "mailto:", "#", "/", "./", "../", "data:image/")

_CODE_RE = re.compile(r"(`+)(.+?)(?<!`)\1(?!`)", re.S)
_AUTOLINK_RE = re.compile(r"<((?:https?://|mailto:)[^\s<>]+)>")
_IMAGE_RE = re.compile(r'!\[([^\]]*)\]\(\s*([^)\s]+)(?:\s+"([^"]*)")?\s*\)')
_LINK_RE = re.compile(r'\[([^\]]+)\]\(\s*([^)\s]+)(?:\s+"([^"]*)")?\s*\)')
_BOLD_RE = re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1")
_ITALIC_STAR_RE = re.compile(r"(?<![\*\w])\*(?=\S)(.+?)(?<=\S)\*(?![\*\w])")
_ITALIC_UNDER_RE = re.compile(r"(?<![_\w])_(?=\S)(.+?)(?<=\S)_(?![_\w])")
_STRIKE_RE = re.compile(r"~~(?=\S)(.+?)(?<=\S)~~")


def is_safe_url(url: str) -> bool:
    """Разрешены только безопасные схемы, никаких javascript: и т. п."""
    low = url.strip().lower()
    if ":" not in low.split("/")[0]:
        # относительный путь без схемы: images/a.png, page.html
        return True
    return low.startswith(_SAFE_SCHEMES)


def _attr(value: str) -> str:
    return html.escape(value, quote=True)


class _Stash:
    """Хранилище уже готовых HTML-фрагментов, спрятанных за плейсхолдерами."""

    def __init__(self) -> None:
        self.items: list[str] = []

    def put(self, fragment: str) -> str:
        self.items.append(fragment)
        return _PLACEHOLDER.format(len(self.items) - 1)

    def restore(self, text: str) -> str:
        # Фрагменты могут содержать вложенные плейсхолдеры — раскрываем до конца.
        prev = None
        while prev != text:
            prev = text
            text = _PLACEHOLDER_RE.sub(lambda m: self.items[int(m.group(1))], text)
        return text


def render_inline(text: str, resolve_image: Optional[ImageResolver] = None) -> str:
    """Преобразует строку Markdown в HTML (без обрамляющих блочных тегов)."""
    stash = _Stash()
    text = text.replace("\x00", "")

    # 1. Экранированные символы: \* → литерал.
    text = re.sub(
        r"\\([%s])" % re.escape(_ESCAPABLE),
        lambda m: stash.put(html.escape(m.group(1))),
        text,
    )

    # 2. Код — внутри него разметка не работает.
    def code(m: re.Match) -> str:
        body = m.group(2)
        if body.startswith(" ") and body.endswith(" ") and body.strip():
            body = body[1:-1]
        return stash.put(f"<code>{html.escape(body)}</code>")

    text = _CODE_RE.sub(code, text)

    # 3. Автоссылки.
    text = _AUTOLINK_RE.sub(
        lambda m: stash.put(f'<a href="{_attr(m.group(1))}">{html.escape(m.group(1))}</a>'),
        text,
    )

    # 4. Картинки (раньше ссылок, т. к. синтаксис похож).
    def image(m: re.Match) -> str:
        alt, src, title = m.group(1), m.group(2), m.group(3)
        if not is_safe_url(src):
            return stash.put(html.escape(m.group(0)))
        if resolve_image is not None:
            src = resolve_image(src)
        title_attr = f' title="{_attr(title)}"' if title else ""
        return stash.put(f'<img src="{_attr(src)}" alt="{_attr(alt)}"{title_attr}>')

    text = _IMAGE_RE.sub(image, text)

    # 5. Ссылки: текст ссылки сам может содержать разметку.
    def link(m: re.Match) -> str:
        label, href, title = m.group(1), m.group(2), m.group(3)
        if not is_safe_url(href):
            return stash.put(html.escape(m.group(0)))
        title_attr = f' title="{_attr(title)}"' if title else ""
        inner = _emphasis(html.escape(label, quote=False))
        return stash.put(f'<a href="{_attr(href)}"{title_attr}>{inner}</a>')

    text = _LINK_RE.sub(link, text)

    # 6. Остальной текст экранируем и размечаем выделение.
    text = _emphasis(html.escape(text, quote=False))
    return stash.restore(text)


def _emphasis(text: str) -> str:
    text = _BOLD_RE.sub(r"<strong>\2</strong>", text)
    text = _STRIKE_RE.sub(r"<del>\1</del>", text)
    text = _ITALIC_STAR_RE.sub(r"<em>\1</em>", text)
    text = _ITALIC_UNDER_RE.sub(r"<em>\1</em>", text)
    return text

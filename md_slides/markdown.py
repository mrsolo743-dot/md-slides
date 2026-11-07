"""Блочный парсер Markdown → HTML.

Поддерживаемые блоки:
  * заголовки `#`…`######`;
  * абзацы (жёсткий перенос — два пробела или `\\` в конце строки);
  * блоки кода ``` / ~~~ с указанием языка и подсветкой;
  * цитаты `>` (вложенные, с любыми блоками внутри);
  * маркированные (`-`, `*`, `+`) и нумерованные (`1.`) списки с вложенностью
    и чекбоксами `- [ ]` / `- [x]`;
  * таблицы GFM с выравниванием столбцов;
  * горизонтальная линия `***` или `___`
    (`---` зарезервирован как разделитель слайдов).

Парсер работает построчно: определяет тип блока по первой строке,
«забирает» его строки и переходит дальше. Для цитат и пунктов списка
содержимое разбирается рекурсивно тем же парсером.
"""

from __future__ import annotations

import html
import re
from typing import Optional

from .highlight import highlight, normalize_lang
from .inline import ImageResolver, render_inline

_HEADING_RE = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$")
_FENCE_RE = re.compile(r"^( {0,3})(`{3,}|~{3,})[ \t]*([\w+#.-]*)[^`]*$")
_HR_RE = re.compile(r"^ {0,3}(?:(?:\*[ \t]*){3,}|(?:_[ \t]*){3,})$")
_QUOTE_RE = re.compile(r"^ {0,3}> ?(.*)$")
_LIST_RE = re.compile(r"^( {0,3})([-*+]|\d{1,9}[.)])([ \t]+)(.*)$")
_TASK_RE = re.compile(r"^\[([ xX])\][ \t]+(.*)$", re.S)
_TABLE_SEP_RE = re.compile(r"^ {0,3}\|?[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)*\|?[ \t]*$")


def _is_blank(line: str) -> bool:
    return not line.strip()


def _split_row(line: str) -> list[str]:
    """Делит строку таблицы на ячейки, учитывая `\\|` и код в обратных кавычках."""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    cells, buf, in_code = [], [], False
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s) and s[i + 1] == "|":
            buf.append("|")
            i += 2
            continue
        if ch == "`":
            in_code = not in_code
        if ch == "|" and not in_code:
            cells.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
        i += 1
    cells.append("".join(buf).strip())
    return cells


def _alignments(sep_line: str) -> list[Optional[str]]:
    result: list[Optional[str]] = []
    for cell in _split_row(sep_line):
        left, right = cell.startswith(":"), cell.endswith(":")
        result.append("center" if left and right else "right" if right else "left" if left else None)
    return result


class MarkdownRenderer:
    """Преобразует Markdown в HTML. Экземпляр можно переиспользовать."""

    def __init__(self, resolve_image: Optional[ImageResolver] = None, fragments: bool = False):
        self.resolve_image = resolve_image
        # fragments=True — пункты списков появляются по одному (класс "fragment").
        self.fragments = fragments

    # ------------------------------------------------------------------ API
    def render(self, text: str) -> str:
        lines = text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", "    ").split("\n")
        return self._blocks(lines)

    def inline(self, text: str) -> str:
        return render_inline(text, self.resolve_image)

    # --------------------------------------------------------------- blocks
    def _blocks(self, lines: list[str], tight: bool = False) -> str:
        out: list[str] = []
        i, n = 0, len(lines)
        while i < n:
            line = lines[i]
            if _is_blank(line):
                i += 1
                continue

            if m := _FENCE_RE.match(line):
                i = self._fence(lines, i, m, out)
                continue
            if m := _HEADING_RE.match(line):
                level = len(m.group(1))
                out.append(f"<h{level}>{self.inline(m.group(2))}</h{level}>")
                i += 1
                continue
            if _HR_RE.match(line):
                out.append("<hr>")
                i += 1
                continue
            if _QUOTE_RE.match(line):
                i = self._quote(lines, i, out)
                continue
            if _LIST_RE.match(line):
                i = self._list(lines, i, out)
                continue
            if "|" in line and i + 1 < n and _TABLE_SEP_RE.match(lines[i + 1]):
                i = self._table(lines, i, out)
                continue
            i = self._paragraph(lines, i, out, tight)
        return "\n".join(out)

    def _fence(self, lines: list[str], i: int, m: re.Match, out: list[str]) -> int:
        indent, fence, lang = len(m.group(1)), m.group(2), m.group(3)
        body: list[str] = []
        i += 1
        while i < len(lines):
            stripped = lines[i].strip()
            if stripped.startswith(fence[0] * len(fence)) and set(stripped) == {fence[0]}:
                i += 1
                break
            line = lines[i]
            # убираем отступ, с которым был открыт блок
            body.append(line[indent:] if line[:indent].strip() == "" else line.lstrip())
            i += 1
        code = "\n".join(body)
        norm = normalize_lang(lang)
        cls = f' class="language-{html.escape(norm)}"' if norm else ""
        label = f' data-lang="{html.escape(lang)}"' if lang else ""
        out.append(f"<pre{label}><code{cls}>{highlight(code, norm)}</code></pre>")
        return i

    def _quote(self, lines: list[str], i: int, out: list[str]) -> int:
        inner: list[str] = []
        while i < len(lines):
            m = _QUOTE_RE.match(lines[i])
            if m:
                inner.append(m.group(1))
            elif not _is_blank(lines[i]) and inner and not _is_blank(inner[-1]):
                inner.append(lines[i])  # «ленивое» продолжение абзаца
            else:
                break
            i += 1
        out.append(f"<blockquote>\n{self._blocks(inner)}\n</blockquote>")
        return i

    def _list(self, lines: list[str], i: int, out: list[str]) -> int:
        first = _LIST_RE.match(lines[i])
        assert first is not None
        base_indent = len(first.group(1))
        ordered = first.group(2)[0].isdigit()
        items: list[list[str]] = []
        loose = False
        n = len(lines)

        while i < n:
            m = _LIST_RE.match(lines[i])
            if not m or len(m.group(1)) != base_indent or m.group(2)[0].isdigit() != ordered:
                break
            content_indent = len(m.group(1)) + len(m.group(2)) + len(m.group(3))
            item = [m.group(4)]
            i += 1
            while i < n:
                line = lines[i]
                if _is_blank(line):
                    # пустая строка: продолжаем, только если дальше идёт отступ
                    j = i
                    while j < n and _is_blank(lines[j]):
                        j += 1
                    if j < n and len(lines[j]) - len(lines[j].lstrip()) >= content_indent:
                        item.extend([""] * (j - i))
                        loose = True
                        i = j
                        continue
                    break
                indent = len(line) - len(line.lstrip())
                if indent >= content_indent:
                    item.append(line[content_indent:])
                elif _LIST_RE.match(line) or _FENCE_RE.match(line) or _HEADING_RE.match(line) or _QUOTE_RE.match(line):
                    break
                else:
                    item.append(line.strip())  # ленивое продолжение
                i += 1
            items.append(item)
            # пустая строка между пунктами делает список «свободным»
            if i < n and _is_blank(lines[i]):
                j = i
                while j < n and _is_blank(lines[j]):
                    j += 1
                nxt = _LIST_RE.match(lines[j]) if j < n else None
                if nxt and len(nxt.group(1)) == base_indent and nxt.group(2)[0].isdigit() == ordered:
                    loose = True
                    i = j

        tag = "ol" if ordered else "ul"
        start_attr = ""
        if ordered:
            start = int(first.group(2)[:-1])
            if start != 1:
                start_attr = f' start="{start}"'
        rendered = []
        has_task = False
        for item in items:
            task = _TASK_RE.match(item[0]) if item else None
            prefix = ""
            if task:
                has_task = True
                checked = " checked" if task.group(1) in "xX" else ""
                prefix = f'<input type="checkbox" disabled{checked}> '
                item = [task.group(2)] + item[1:]
            body = self._blocks(item, tight=not loose)
            cls = []
            if self.fragments:
                cls.append("fragment")
            if task:
                cls.append("task")
            cls_attr = f' class="{" ".join(cls)}"' if cls else ""
            rendered.append(f"<li{cls_attr}>{prefix}{body}</li>")
        list_cls = ' class="tasks"' if has_task else ""
        out.append(f"<{tag}{start_attr}{list_cls}>\n" + "\n".join(rendered) + f"\n</{tag}>")
        return i

    def _table(self, lines: list[str], i: int, out: list[str]) -> int:
        header = _split_row(lines[i])
        aligns = _alignments(lines[i + 1])
        i += 2
        rows: list[list[str]] = []
        while i < len(lines) and "|" in lines[i] and not _is_blank(lines[i]):
            rows.append(_split_row(lines[i]))
            i += 1

        def cell(tag: str, text: str, col: int) -> str:
            align = aligns[col] if col < len(aligns) else None
            style = f' style="text-align:{align}"' if align else ""
            return f"<{tag}{style}>{self.inline(text)}</{tag}>"

        head = "".join(cell("th", c, k) for k, c in enumerate(header))
        body_rows = []
        for row in rows:
            row = (row + [""] * len(header))[: len(header)]
            body_rows.append("<tr>" + "".join(cell("td", c, k) for k, c in enumerate(row)) + "</tr>")
        body = f"\n<tbody>\n{chr(10).join(body_rows)}\n</tbody>" if body_rows else ""
        out.append(f"<table>\n<thead>\n<tr>{head}</tr>\n</thead>{body}\n</table>")
        return i

    def _paragraph(self, lines: list[str], i: int, out: list[str], tight: bool) -> int:
        buf: list[str] = []
        n = len(lines)
        while i < n:
            line = lines[i]
            if _is_blank(line):
                break
            if buf and (
                _FENCE_RE.match(line) or _HEADING_RE.match(line) or _QUOTE_RE.match(line)
                or _HR_RE.match(line) or _LIST_RE.match(line)
            ):
                break
            buf.append(line)
            i += 1
        parts = []
        for k, line in enumerate(buf):
            last = k == len(buf) - 1
            hard = not last and (line.endswith("  ") or line.endswith("\\"))
            text = line.strip()
            if hard and text.endswith("\\"):
                text = text[:-1]
            parts.append(self.inline(text) + ("<br>" if hard else ""))
        content = "\n".join(parts)
        out.append(content if tight else f"<p>{content}</p>")
        return i


def render_markdown(text: str, **kwargs) -> str:
    """Удобная функция: Markdown → HTML."""
    return MarkdownRenderer(**kwargs).render(text)

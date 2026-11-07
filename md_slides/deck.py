"""Разбор колоды: front matter, деление на слайды, заметки, директивы.

Формат исходного файла::

    ---
    title: Моя презентация
    author: Тимур
    theme: dark
    ---

    # Первый слайд
    Текст

    Note: это видит только докладчик

    ---

    <!-- class: center -->
    <!-- fragments -->
    ## Второй слайд
    - появится первым
    - появится вторым

Разделитель слайдов — строка ровно из `---` (внутри блоков кода игнорируется).
Front matter распознаётся, только если файл начинается с `---` и все строки до
закрывающего `---` имеют вид `ключ: значение`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_SEPARATOR_RE = re.compile(r"^---[ \t]*$")
_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_META_RE = re.compile(r"^([A-Za-z][\w-]*)[ \t]*:[ \t]*(.*?)[ \t]*$")
_NOTE_RE = re.compile(r"^(?:Note|Notes|Заметки)[ \t]*:[ \t]?(.*)$", re.I)
_DIRECTIVE_RE = re.compile(r"^[ \t]*<!--[ \t]*([\w-]+)[ \t]*(?::[ \t]*(.*?))?[ \t]*-->[ \t]*$")

KNOWN_DIRECTIVES = {"class", "fragments", "background", "color", "id"}


@dataclass
class Slide:
    index: int
    source: str
    notes: str = ""
    directives: dict[str, str] = field(default_factory=dict)

    @property
    def title(self) -> str:
        """Первый заголовок слайда (для оглавления и подсказок)."""
        for line in self.source.splitlines():
            m = re.match(r"^ {0,3}#{1,6}[ \t]+(.*?)[ \t#]*$", line)
            if m:
                return m.group(1)
        return f"Слайд {self.index + 1}"


@dataclass
class Deck:
    meta: dict[str, str]
    slides: list[Slide]

    @property
    def title(self) -> str:
        if self.meta.get("title"):
            return self.meta["title"]
        return self.slides[0].title if self.slides else "Презентация"


def parse_front_matter(lines: list[str]) -> tuple[dict[str, str], list[str]]:
    """Отделяет front matter. Возвращает (meta, оставшиеся строки)."""
    if not lines or not _SEPARATOR_RE.match(lines[0]):
        return {}, lines
    meta: dict[str, str] = {}
    for k in range(1, len(lines)):
        line = lines[k]
        if _SEPARATOR_RE.match(line):
            if not meta:
                return {}, lines  # «--- ---» в начале — это не метаданные
            return meta, lines[k + 1:]
        if not line.strip():
            continue
        m = _META_RE.match(line)
        if not m:
            return {}, lines  # обычный разделитель, а не front matter
        value = m.group(2)
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        meta[m.group(1).lower()] = value
    return {}, lines


def split_slides(lines: list[str]) -> list[list[str]]:
    """Делит строки на слайды по `---`, не трогая блоки кода."""
    chunks: list[list[str]] = [[]]
    fence: str | None = None
    for line in lines:
        m = _FENCE_RE.match(line)
        if m:
            marker = m.group(1)
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence) and not line.strip().strip(marker[0]):
                fence = None
        if fence is None and _SEPARATOR_RE.match(line):
            chunks.append([])
            continue
        chunks[-1].append(line)
    return chunks


def _extract(lines: list[str]) -> tuple[str, str, dict[str, str]]:
    """Возвращает (markdown слайда, заметки, директивы)."""
    body: list[str] = []
    notes: list[str] = []
    directives: dict[str, str] = {}
    in_notes = False
    fence: str | None = None
    for line in lines:
        m = _FENCE_RE.match(line)
        if m:
            marker = m.group(1)
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and not line.strip().strip(marker[0]):
                fence = None
            (notes if in_notes else body).append(line)
            continue
        if fence is None and not in_notes:
            d = _DIRECTIVE_RE.match(line)
            if d and d.group(1).lower() in KNOWN_DIRECTIVES:
                directives[d.group(1).lower()] = (d.group(2) or "true").strip()
                continue
            n = _NOTE_RE.match(line)
            if n:
                in_notes = True
                if n.group(1).strip():
                    notes.append(n.group(1))
                continue
        (notes if in_notes else body).append(line)
    return "\n".join(body).strip("\n"), "\n".join(notes).strip(), directives


def parse_deck(text: str) -> Deck:
    """Разбирает исходный Markdown в объект Deck."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    meta, rest = parse_front_matter(lines)
    slides: list[Slide] = []
    for chunk in split_slides(rest):
        source, notes, directives = _extract(chunk)
        if not source.strip() and not notes and not directives:
            continue  # пустые слайды (например, лишний --- в конце) пропускаем
        slides.append(Slide(index=len(slides), source=source, notes=notes, directives=directives))
    return Deck(meta=meta, slides=slides)

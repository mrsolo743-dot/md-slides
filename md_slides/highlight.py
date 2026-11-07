"""Минимальная подсветка синтаксиса без внешних зависимостей.

Каждый язык описан набором правил (класс токена → регулярное выражение).
Правила объединяются в одно регулярное выражение с именованными группами,
и текст проходит за один проход слева направо: первое совпавшее правило
побеждает. Это проще полноценного лексера, но для слайдов более чем
достаточно.
"""

from __future__ import annotations

import html
import re
from functools import lru_cache

_PY_KEYWORDS = (
    "False None True and as assert async await break class continue def del elif else "
    "except finally for from global if import in is lambda nonlocal not or pass raise "
    "return try while with yield match case"
).split()
_PY_BUILTINS = "print len range open int str float list dict set tuple isinstance super self".split()

_JS_KEYWORDS = (
    "break case catch class const continue debugger default delete do else export extends "
    "finally for function if import in instanceof let new return super switch this throw try "
    "typeof var void while with yield async await of null undefined true false"
).split()
_JS_BUILTINS = "console document window Math JSON Promise Array Object String Number".split()

_SH_KEYWORDS = "if then else elif fi for in do done while case esac function return export local".split()
_SH_BUILTINS = "echo cd ls cat grep sed awk pip python python3 git npm node mkdir rm cp mv".split()

def _words(words: list[str]) -> str:
    return r"\b(?:" + "|".join(map(re.escape, words)) + r")\b" if words else r"(?!x)x"


_LANGS: dict[str, list[tuple[str, str]]] = {
    "python": [
        ("comment", r"#[^\n]*"),
        ("string", r'[rbfu]{0,2}(?:"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\')'),
        ("decorator", r"@[\w.]+"),
        ("number", r"\b\d[\d_]*(?:\.\d+)?(?:[eE][+-]?\d+)?\b"),
        ("keyword", _words(_PY_KEYWORDS)),
        ("builtin", _words(_PY_BUILTINS)),
        ("function", r"\b[A-Za-z_]\w*(?=\()"),
    ],
    "javascript": [
        ("comment", r"//[^\n]*|/\*[\s\S]*?\*/"),
        ("string", r'"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'|`(?:\\.|[^`\\])*`'),
        ("number", r"\b\d[\d_]*(?:\.\d+)?\b"),
        ("keyword", _words(_JS_KEYWORDS)),
        ("builtin", _words(_JS_BUILTINS)),
        ("function", r"\b[A-Za-z_$][\w$]*(?=\()"),
    ],
    "bash": [
        ("comment", r"(?<![\w$])#[^\n]*"),
        ("string", r'"(?:\\.|[^"\\])*"|\'[^\']*\''),
        ("variable", r"\$\{?\w+\}?"),
        ("keyword", _words(_SH_KEYWORDS)),
        ("builtin", _words(_SH_BUILTINS)),
        ("number", r"\b\d+\b"),
    ],
    "css": [
        ("comment", r"/\*[\s\S]*?\*/"),
        ("string", r'"[^"\n]*"|\'[^\'\n]*\''),
        ("keyword", r"@[\w-]+"),
        ("builtin", r"[\w-]+(?=\s*:)"),
        ("number", r"#[0-9a-fA-F]{3,8}\b|\b\d+(?:\.\d+)?(?:px|em|rem|%|vh|vw|s|ms)?\b"),
    ],
    "html": [
        ("comment", r"<!--[\s\S]*?-->"),
        ("keyword", r"</?[\w-]+|/?>"),
        ("string", r'"[^"]*"|\'[^\']*\''),
        ("builtin", r"\b[\w-]+(?==)"),
    ],
    "json": [
        ("builtin", r'"(?:\\.|[^"\\])*"(?=\s*:)'),
        ("string", r'"(?:\\.|[^"\\])*"'),
        ("number", r"-?\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b"),
        ("keyword", r"\b(?:true|false|null)\b"),
    ],
}

_ALIASES = {
    "py": "python", "python3": "python",
    "js": "javascript", "ts": "javascript", "typescript": "javascript", "node": "javascript",
    "sh": "bash", "shell": "bash", "zsh": "bash", "console": "bash",
    "htm": "html", "xml": "html", "svg": "html",
    "scss": "css",
}


def normalize_lang(lang: str) -> str:
    lang = (lang or "").strip().lower()
    return _ALIASES.get(lang, lang)


def supported_languages() -> list[str]:
    return sorted(_LANGS)


@lru_cache(maxsize=None)
def _compiled(lang: str) -> re.Pattern:
    parts = [f"(?P<{name}_{i}>{rx})" for i, (name, rx) in enumerate(_LANGS[lang])]
    return re.compile("|".join(parts))


def highlight(code: str, lang: str) -> str:
    """Возвращает экранированный HTML с <span class="tok-…"> для токенов.

    Неизвестный язык — просто экранированный текст.
    """
    lang = normalize_lang(lang)
    if lang not in _LANGS:
        return html.escape(code)
    pattern = _compiled(lang)
    out: list[str] = []
    pos = 0
    for m in pattern.finditer(code):
        if m.start() == m.end():
            continue
        out.append(html.escape(code[pos:m.start()]))
        kind = m.lastgroup.rsplit("_", 1)[0]
        out.append(f'<span class="tok-{kind}">{html.escape(m.group(0))}</span>')
        pos = m.end()
    out.append(html.escape(code[pos:]))
    return "".join(out)

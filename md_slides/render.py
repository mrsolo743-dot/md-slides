"""Сборка автономного HTML-файла презентации из объекта Deck."""

from __future__ import annotations

import base64
import html
import json
import mimetypes
import re
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Optional

from . import __version__
from .deck import Deck, Slide, parse_deck
from .markdown import MarkdownRenderer

THEMES = ("light", "dark", "terminal", "sepia")
ASPECTS = {"16:9": (1280, 720), "4:3": (1280, 960), "16:10": (1280, 800)}
_SAFE_CSS_VALUE = re.compile(r"^[#\w\s.,%()/-]+$")
_SAFE_CLASS = re.compile(r"^[\w-]+$")
_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


class BuildError(ValueError):
    """Ошибка сборки, понятная пользователю."""


@dataclass
class BuildOptions:
    theme: Optional[str] = None          # переопределяет theme из front matter
    aspect: Optional[str] = None         # 16:9 | 4:3 | 16:10
    embed_images: bool = False           # встраивать локальные картинки как data: URI
    base_dir: Optional[Path] = None      # относительно чего искать картинки
    live_reload: bool = False            # опрос /__version (режим serve)
    warnings: list[str] = field(default_factory=list)


def _asset(name: str) -> str:
    return resources.files("md_slides").joinpath("assets", name).read_text(encoding="utf-8")


def _render_template(template: str, values: dict[str, str]) -> str:
    """Подстановка {{ключ}} за один проход: подставленные значения не разбираются повторно."""
    return _PLACEHOLDER.sub(lambda m: values.get(m.group(1), m.group(0)), template)


def make_image_resolver(base_dir: Path, warnings: list[str]):
    """Возвращает функцию, превращающую локальный путь в data: URI."""

    def resolve(src: str) -> str:
        if re.match(r"^[a-z][a-z0-9+.-]*:", src, re.I) or src.startswith("//"):
            return src  # внешний URL или уже data:
        path = (base_dir / src).resolve()
        if not path.is_file():
            warnings.append(f"картинка не найдена: {src}")
            return src
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if not mime.startswith("image/"):
            warnings.append(f"не картинка, пропущено встраивание: {src}")
            return src
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{data}"

    return resolve


def _slide_html(slide: Slide, deck: Deck, total: int, opts: BuildOptions) -> str:
    resolver = None
    if opts.embed_images:
        resolver = make_image_resolver(opts.base_dir or Path.cwd(), opts.warnings)
    fragments = slide.directives.get("fragments", "false").lower() in ("true", "yes", "1", "on")
    renderer = MarkdownRenderer(resolve_image=resolver, fragments=fragments)

    classes = ["slide"]
    for cls in slide.directives.get("class", "").split():
        if _SAFE_CLASS.match(cls):
            classes.append(cls)
        else:
            opts.warnings.append(f"слайд {slide.index + 1}: недопустимый класс {cls!r}")

    styles = []
    for key, prop in (("background", "background"), ("color", "color")):
        value = slide.directives.get(key)
        if value:
            if _SAFE_CSS_VALUE.match(value):
                styles.append(f"{prop}:{value}")
            else:
                opts.warnings.append(f"слайд {slide.index + 1}: недопустимое значение {key}: {value!r}")

    attrs = [f'class="{" ".join(classes)}"', f'data-index="{slide.index}"', f'data-title="{html.escape(slide.title)}"']
    slide_id = slide.directives.get("id")
    if slide_id and _SAFE_CLASS.match(slide_id):
        attrs.append(f'id="{slide_id}"')
    if styles:
        attrs.append(f'style="{html.escape(";".join(styles))}"')
    attrs.append('role="region"')
    attrs.append(f'aria-label="Слайд {slide.index + 1} из {total}"')

    parts = [f"<section {' '.join(attrs)}>", renderer.render(slide.source)]
    if slide.notes:
        parts.append(f'<aside class="notes">{MarkdownRenderer().render(slide.notes)}</aside>')

    footer = deck.meta.get("footer", "")
    paginate = deck.meta.get("paginate", "").lower() in ("true", "yes", "1", "on")
    if footer or paginate:
        num = f"{slide.index + 1} / {total}" if paginate else ""
        parts.append(
            f'<div class="footer"><span>{renderer.inline(footer)}</span><span>{num}</span></div>'
        )
    parts.append("</section>")
    return "\n".join(parts)


def build_html(deck: Deck, opts: Optional[BuildOptions] = None) -> str:
    """Собирает HTML-страницу. Бросает BuildError при некорректных настройках."""
    opts = opts or BuildOptions()
    theme = (opts.theme or deck.meta.get("theme") or "light").lower()
    if theme not in THEMES:
        raise BuildError(f"неизвестная тема {theme!r}; доступны: {', '.join(THEMES)}")
    aspect = opts.aspect or deck.meta.get("aspect") or "16:9"
    if aspect not in ASPECTS:
        raise BuildError(f"неизвестное соотношение сторон {aspect!r}; доступны: {', '.join(ASPECTS)}")
    width, height = ASPECTS[aspect]

    if not deck.slides:
        raise BuildError("в файле нет ни одного слайда")

    total = len(deck.slides)
    slides_html = "\n\n".join(_slide_html(s, deck, total, opts) for s in deck.slides)

    meta_tags = ""
    if deck.meta.get("author"):
        meta_tags += f'<meta name="author" content="{html.escape(deck.meta["author"])}">\n'
    if deck.meta.get("description"):
        meta_tags += f'<meta name="description" content="{html.escape(deck.meta["description"])}">\n'

    config = {
        "title": deck.title,
        "themes": list(THEMES),
        "width": width,
        "height": height,
        "live": opts.live_reload,
    }
    config_json = json.dumps(config, ensure_ascii=False).replace("</", "<\\/")

    return _render_template(
        _asset("template.html"),
        {
            "lang": html.escape(deck.meta.get("lang", "ru")),
            "version": __version__,
            "meta_tags": meta_tags,
            "title": html.escape(deck.title),
            "css": _asset("style.css"),
            "width": str(width),
            "height": str(height),
            "theme": theme,
            "slides": slides_html,
            "config": config_json,
            "js": _asset("app.js"),
        },
    )


def build_file(source: Path, output: Optional[Path] = None, opts: Optional[BuildOptions] = None) -> Path:
    """Читает .md, пишет .html рядом (или в output). Возвращает путь к результату."""
    source = Path(source)
    if not source.is_file():
        raise BuildError(f"файл не найден: {source}")
    opts = opts or BuildOptions()
    if opts.base_dir is None:
        opts.base_dir = source.parent
    deck = parse_deck(source.read_text(encoding="utf-8"))
    output = Path(output) if output else source.with_suffix(".html")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_html(deck, opts), encoding="utf-8")
    return output

"""Командная строка md-slides.

    md-slides build talk.md [-o out.html] [--theme dark] [--aspect 4:3] [--embed-images] [--watch]
    md-slides serve talk.md [--port 8000] [--open]
    md-slides init [talk.md]
    md-slides outline talk.md
    md-slides themes
"""

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path
from typing import Optional, Sequence

from . import __version__
from .deck import parse_deck
from .render import ASPECTS, THEMES, BuildError, BuildOptions, build_file


def _print_warnings(opts: BuildOptions) -> None:
    for w in dict.fromkeys(opts.warnings):  # без повторов, с сохранением порядка
        print(f"  ⚠ {w}", file=sys.stderr)


def _build_once(args: argparse.Namespace) -> int:
    opts = BuildOptions(theme=args.theme, aspect=args.aspect, embed_images=args.embed_images)
    try:
        out = build_file(Path(args.source), Path(args.output) if args.output else None, opts)
    except BuildError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    deck_size = out.stat().st_size / 1024
    print(f"✓ {args.source} → {out} ({deck_size:.0f} КБ)")
    _print_warnings(opts)
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    code = _build_once(args)
    if not args.watch:
        return code
    from .watch import FileWatcher

    print(f"Слежу за {args.source}. Ctrl+C — выход.")
    watcher = FileWatcher(Path(args.source), lambda: _build_once(args))
    try:
        watcher.run()
    except KeyboardInterrupt:
        print("\nОстановлено.")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from .server import create_server

    source = Path(args.source)
    if not source.is_file():
        print(f"Ошибка: файл не найден: {source}", file=sys.stderr)
        return 1
    try:
        server, watcher, _state = create_server(source, port=args.port, theme=args.theme, aspect=args.aspect)
    except OSError as exc:
        print(f"Ошибка: не удалось занять порт {args.port}: {exc}", file=sys.stderr)
        return 1
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"Предпросмотр: {url}  (страница обновится сама при сохранении файла). Ctrl+C — выход.")
    watcher.start()
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nОстановлено.")
    finally:
        watcher.stop()
        server.server_close()
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    from importlib import resources

    target = Path(args.path)
    if target.exists() and not args.force:
        print(f"Ошибка: {target} уже существует (используйте --force)", file=sys.stderr)
        return 1
    text = resources.files("md_slides").joinpath("assets", "example.md").read_text(encoding="utf-8")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    print(f"✓ Создан {target}. Дальше: md-slides serve {target}")
    return 0


def cmd_outline(args: argparse.Namespace) -> int:
    source = Path(args.source)
    if not source.is_file():
        print(f"Ошибка: файл не найден: {source}", file=sys.stderr)
        return 1
    deck = parse_deck(source.read_text(encoding="utf-8"))
    print(f"{deck.title} — слайдов: {len(deck.slides)}")
    for s in deck.slides:
        marks = []
        if s.notes:
            marks.append("заметки")
        if s.directives:
            marks.append(", ".join(f"{k}={v}" for k, v in s.directives.items()))
        suffix = f"  [{'; '.join(marks)}]" if marks else ""
        print(f"{s.index + 1:>3}. {s.title}{suffix}")
    return 0


def cmd_themes(_args: argparse.Namespace) -> int:
    print("Темы:", ", ".join(THEMES))
    print("Соотношения сторон:", ", ".join(ASPECTS))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="md-slides", description="Автономные HTML-презентации из Markdown.")
    p.add_argument("--version", action="version", version=f"md-slides {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    def style_args(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--theme", choices=THEMES, help="тема (по умолчанию из front matter или light)")
        sp.add_argument("--aspect", choices=list(ASPECTS), help="соотношение сторон (по умолчанию 16:9)")

    b = sub.add_parser("build", help="собрать HTML")
    b.add_argument("source", help="исходный .md")
    b.add_argument("-o", "--output", help="куда записать .html (по умолчанию рядом с исходником)")
    style_args(b)
    b.add_argument("--embed-images", action="store_true", help="встроить локальные картинки в HTML")
    b.add_argument("-w", "--watch", action="store_true", help="пересобирать при изменении файла")
    b.set_defaults(func=cmd_build)

    s = sub.add_parser("serve", help="предпросмотр с живой перезагрузкой")
    s.add_argument("source")
    s.add_argument("-p", "--port", type=int, default=8000)
    s.add_argument("--open", action="store_true", help="открыть браузер")
    style_args(s)
    s.set_defaults(func=cmd_serve)

    i = sub.add_parser("init", help="создать пример презентации")
    i.add_argument("path", nargs="?", default="slides.md")
    i.add_argument("--force", action="store_true", help="перезаписать существующий файл")
    i.set_defaults(func=cmd_init)

    o = sub.add_parser("outline", help="показать список слайдов")
    o.add_argument("source")
    o.set_defaults(func=cmd_outline)

    t = sub.add_parser("themes", help="список тем")
    t.set_defaults(func=cmd_themes)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

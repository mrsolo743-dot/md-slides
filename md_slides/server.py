"""Локальный сервер предпросмотра с живой перезагрузкой.

`/` отдаёт собранную презентацию, `/__version` — номер сборки (страница
опрашивает его раз в секунду и перезагружается при изменении), остальные пути —
статические файлы из папки с исходником (картинки и т. п.).
Сервер слушает только 127.0.0.1.
"""

from __future__ import annotations

import html
import mimetypes
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse

from .deck import parse_deck
from .render import BuildError, BuildOptions, build_html
from .watch import FileWatcher

_ERROR_PAGE = """<!doctype html><meta charset="utf-8"><title>Ошибка сборки</title>
<body style="font:16px system-ui;padding:40px;background:#2b0f12;color:#ffd7d7">
<h1>Ошибка сборки</h1><pre>{}</pre>
<script>let v=null;setInterval(()=>fetch('/__version').then(r=>r.text()).then(t=>{{if(v!==null&&t!==v)location.reload();v=t}}),1000)</script>"""


class PreviewState:
    """Текущая сборка и её версия; потокобезопасна."""

    def __init__(self, source: Path, theme: Optional[str] = None, aspect: Optional[str] = None):
        self.source = Path(source)
        self.theme = theme
        self.aspect = aspect
        self.version = 0
        self.html = ""
        self.warnings: list[str] = []
        self._lock = threading.Lock()
        self.rebuild()

    def rebuild(self) -> None:
        opts = BuildOptions(theme=self.theme, aspect=self.aspect, base_dir=self.source.parent, live_reload=True)
        try:
            page = build_html(parse_deck(self.source.read_text(encoding="utf-8")), opts)
        except (BuildError, OSError, UnicodeDecodeError) as exc:
            page = _ERROR_PAGE.format(html.escape(str(exc)))
        with self._lock:
            self.html = page
            self.warnings = opts.warnings
            self.version += 1

    def snapshot(self) -> tuple[int, str]:
        with self._lock:
            return self.version, self.html


def make_handler(state: PreviewState):
    root = state.source.parent.resolve()

    class Handler(BaseHTTPRequestHandler):
        server_version = "md-slides"

        def log_message(self, fmt, *args):  # тихий режим
            pass

        def _send(self, status: int, body: bytes, ctype: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802 - имя из стандартной библиотеки
            path = unquote(urlparse(self.path).path)
            version, page = state.snapshot()
            if path in ("/", "/index.html"):
                return self._send(HTTPStatus.OK, page.encode("utf-8"), "text/html; charset=utf-8")
            if path == "/__version":
                return self._send(HTTPStatus.OK, str(version).encode(), "text/plain; charset=utf-8")
            target = (root / path.lstrip("/")).resolve()
            # защита от выхода за пределы папки (../../etc/passwd)
            if root not in target.parents or not target.is_file():
                return self._send(HTTPStatus.NOT_FOUND, "Не найдено".encode("utf-8"), "text/plain; charset=utf-8")
            ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            return self._send(HTTPStatus.OK, target.read_bytes(), ctype)

    return Handler


def create_server(source: Path, port: int = 8000, theme: Optional[str] = None,
                  aspect: Optional[str] = None, interval: float = 0.5):
    """Создаёт (но не запускает) сервер и наблюдатель. Возвращает (server, watcher, state)."""
    state = PreviewState(source, theme=theme, aspect=aspect)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(state))
    watcher = FileWatcher(source, state.rebuild, interval=interval)
    return server, watcher, state

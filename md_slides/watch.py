"""Отслеживание изменений файла опросом mtime (без внешних зависимостей)."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable, Optional


class FileWatcher:
    """Вызывает callback, когда меняется время модификации или размер файла.

    Опрос выбран сознательно: он работает одинаково на Linux, macOS и Windows
    и не требует сторонних библиотек вроде watchdog.
    """

    def __init__(self, path: Path, callback: Callable[[], None], interval: float = 0.5):
        self.path = Path(path)
        self.callback = callback
        self.interval = interval
        self._stop = threading.Event()
        self._last = self._signature()

    def _signature(self) -> Optional[tuple[float, int]]:
        try:
            st = self.path.stat()
        except FileNotFoundError:
            return None
        return (st.st_mtime_ns, st.st_size)

    def check(self) -> bool:
        """Один шаг опроса. Возвращает True, если файл изменился (callback вызван)."""
        sig = self._signature()
        if sig != self._last:
            self._last = sig
            if sig is not None:  # файл удалён — ждём, пока появится снова
                self.callback()
                return True
        return False

    def run(self, max_checks: Optional[int] = None) -> None:
        """Блокирующий цикл. max_checks ограничивает число итераций (для тестов)."""
        checks = 0
        while not self._stop.is_set():
            self.check()
            checks += 1
            if max_checks is not None and checks >= max_checks:
                break
            self._stop.wait(self.interval)

    def start(self) -> threading.Thread:
        thread = threading.Thread(target=self.run, daemon=True, name="md-slides-watcher")
        thread.start()
        return thread

    def stop(self) -> None:
        self._stop.set()


def wait_forever() -> None:  # pragma: no cover - интерактивный режим
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass

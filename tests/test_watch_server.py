import os
import threading
import time
import urllib.error
import urllib.request

import pytest

from md_slides.server import create_server
from md_slides.watch import FileWatcher


def bump(path, text):
    path.write_text(text, encoding="utf-8")
    st = path.stat()
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))


def test_watcher_detects_change(tmp_path):
    f = tmp_path / "a.md"
    f.write_text("1", encoding="utf-8")
    calls = []
    w = FileWatcher(f, lambda: calls.append(1), interval=0)
    assert w.check() is False
    bump(f, "22")
    assert w.check() is True
    assert w.check() is False
    assert calls == [1]


def test_watcher_survives_deleted_file(tmp_path):
    f = tmp_path / "a.md"
    f.write_text("1", encoding="utf-8")
    calls = []
    w = FileWatcher(f, lambda: calls.append(1), interval=0)
    f.unlink()
    assert w.check() is False
    f.write_text("new", encoding="utf-8")
    assert w.check() is True
    assert calls == [1]


def test_watcher_run_limited(tmp_path):
    f = tmp_path / "a.md"
    f.write_text("1", encoding="utf-8")
    w = FileWatcher(f, lambda: None, interval=0)
    w.run(max_checks=3)  # не зависает


@pytest.fixture
def server(tmp_path):
    src = tmp_path / "talk.md"
    src.write_text("# Первый", encoding="utf-8")
    (tmp_path / "pic.txt").write_text("static", encoding="utf-8")
    srv, watcher, state = create_server(src, port=0, interval=0.05)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    watcher.start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    yield base, src, state
    watcher.stop()
    srv.shutdown()
    srv.server_close()


def get(url):
    with urllib.request.urlopen(url, timeout=5) as r:
        return r.status, r.read().decode("utf-8")


def test_server_serves_page_and_version(server):
    base, _src, _state = server
    status, page = get(base + "/")
    assert status == 200 and "<h1>Первый</h1>" in page
    assert '"live": true' in page
    assert get(base + "/__version")[1] == "1"


def test_server_rebuilds_on_change(server):
    base, src, _state = server
    bump(src, "# Второй")
    deadline = time.time() + 5
    while time.time() < deadline and get(base + "/__version")[1] == "1":
        time.sleep(0.05)
    assert get(base + "/__version")[1] == "2"
    assert "<h1>Второй</h1>" in get(base + "/")[1]


def test_server_shows_build_error(server):
    base, src, state = server
    bump(src, "")  # пустой файл → «нет ни одного слайда»
    state.rebuild()
    assert "Ошибка сборки" in get(base + "/")[1]


def test_server_static_and_traversal(server):
    base, _src, _state = server
    assert get(base + "/pic.txt")[1] == "static"
    with pytest.raises(urllib.error.HTTPError) as exc:
        get(base + "/../../etc/passwd")
    assert exc.value.code == 404
    with pytest.raises(urllib.error.HTTPError):
        get(base + "/%2e%2e/%2e%2e/etc/passwd")

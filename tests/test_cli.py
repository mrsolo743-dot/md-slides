import pytest

from md_slides import __version__
from md_slides.cli import main


def test_build_command(tmp_path, capsys):
    src = tmp_path / "a.md"
    src.write_text("# A\n---\n# B", encoding="utf-8")
    assert main(["build", str(src), "--theme", "dark"]) == 0
    html = (tmp_path / "a.html").read_text(encoding="utf-8")
    assert 'data-theme="dark"' in html
    assert "✓" in capsys.readouterr().out


def test_build_custom_output(tmp_path):
    src = tmp_path / "a.md"
    src.write_text("# A", encoding="utf-8")
    out = tmp_path / "dist" / "index.html"
    assert main(["build", str(src), "-o", str(out)]) == 0
    assert out.is_file()


def test_build_missing_file(tmp_path, capsys):
    assert main(["build", str(tmp_path / "x.md")]) == 1
    assert "не найден" in capsys.readouterr().err


def test_build_reports_warnings(tmp_path, capsys):
    src = tmp_path / "a.md"
    src.write_text("![x](nope.png)", encoding="utf-8")
    assert main(["build", str(src), "--embed-images"]) == 0
    assert "картинка не найдена" in capsys.readouterr().err


def test_invalid_theme_rejected_by_argparse(tmp_path):
    with pytest.raises(SystemExit):
        main(["build", "a.md", "--theme", "neon"])


def test_init_and_no_overwrite(tmp_path, capsys):
    target = tmp_path / "slides.md"
    assert main(["init", str(target)]) == 0
    assert target.read_text(encoding="utf-8").startswith("---")
    assert main(["init", str(target)]) == 1
    assert main(["init", str(target), "--force"]) == 0


def test_outline(tmp_path, capsys):
    src = tmp_path / "a.md"
    src.write_text("---\ntitle: Т\n---\n# Один\nNote: n\n---\n<!-- fragments -->\n## Два", encoding="utf-8")
    assert main(["outline", str(src)]) == 0
    out = capsys.readouterr().out
    assert "Т — слайдов: 2" in out
    assert "1. Один  [заметки]" in out
    assert "2. Два  [fragments=true]" in out


def test_themes(capsys):
    assert main(["themes"]) == 0
    assert "terminal" in capsys.readouterr().out


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out

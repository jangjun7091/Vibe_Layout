from pathlib import Path

from klayout_harness.cli import find_klayout_executable


def test_find_klayout_executable_uses_explicit_path(tmp_path: Path) -> None:
    exe = tmp_path / "klayout.exe"
    exe.write_text("", encoding="utf-8")

    assert find_klayout_executable(str(exe)) == exe


def test_find_klayout_executable_uses_environment(monkeypatch, tmp_path: Path) -> None:
    exe = tmp_path / "klayout.exe"
    exe.write_text("", encoding="utf-8")
    monkeypatch.setenv("KLAYOUT_EXE", str(exe))

    assert find_klayout_executable() == exe

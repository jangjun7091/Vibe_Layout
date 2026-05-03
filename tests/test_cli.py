from pathlib import Path
import subprocess
import sys

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


def test_cli_outputs_required_sections_and_generates_gds(tmp_path: Path) -> None:
    prompt = (
        "Vibe_Layout, $1mm \\times 1mm$ root cell 'CHIP_ROOT'. "
        "Create sub cell 'ELECTRODE_UNIT' with width $50\\mu m$ and length $800\\mu m$ "
        "on Microwriter layer (1, 0)."
    )

    result = subprocess.run(
        [sys.executable, "-m", "klayout_harness.cli", prompt, "--out-dir", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Engineering Analysis" in result.stdout
    assert "Python Code" in result.stdout
    assert "Design Validation" in result.stdout
    assert (tmp_path / "CHIP_ROOT.gds").is_file()


def test_cli_rejects_subresolution_request(tmp_path: Path) -> None:
    prompt = (
        "Vibe_Layout, $1mm \\times 1mm$ root cell 'CHIP_ROOT'. "
        "Create sub cell 'ELECTRODE_UNIT' with width $0.5\\mu m$ and length $800\\mu m$ "
        "on Microwriter layer (1, 0)."
    )

    result = subprocess.run(
        [sys.executable, "-m", "klayout_harness.cli", prompt, "--out-dir", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "Design Validation" in result.stdout
    assert "drc.minimum_resolution" in result.stdout
    assert not (tmp_path / "CHIP_ROOT.gds").exists()

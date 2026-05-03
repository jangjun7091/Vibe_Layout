from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess

from .cad import CADHarness
from .design_request import (
    build_electrode_layout,
    default_context_for_request,
    output_path_for_request,
    parse_electrode_request,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Vibe Layout GDS files from constrained requests.")
    parser.add_argument("prompt", help="Natural language layout request.")
    parser.add_argument("--out-dir", default="build", help="Output directory for generated GDS.")
    parser.add_argument("--open", action="store_true", help="Open the generated GDS in KLayout if available.")
    parser.add_argument("--klayout-exe", help="Path to klayout.exe. Overrides KLAYOUT_EXE and PATH lookup.")
    args = parser.parse_args()

    try:
        request = parse_electrode_request(args.prompt)
    except ValueError as exc:
        print("generated=False")
        print(f"reason={exc}")
        return 2
    context = default_context_for_request()
    try:
        cad = CADHarness(context)
    except RuntimeError as exc:
        print(f"generated=False")
        print(f"reason={exc}")
        return 2
    build_electrode_layout(request, cad)
    output_path = cad.write_gds(output_path_for_request(request, args.out_dir)).resolve()

    print(f"generated={output_path}")
    if args.open:
        _open_in_klayout(output_path, args.klayout_exe)
    return 0


def _open_in_klayout(path: Path, explicit_executable: str | None = None) -> bool:
    executable = find_klayout_executable(explicit_executable)
    if executable is not None:
        subprocess.Popen([str(executable), str(path)])
        print("klayout_opened=True")
        print(f"klayout_exe={executable}")
        return True

    if os.name == "nt":
        try:
            os.startfile(path)  # type: ignore[attr-defined]
            print("klayout_opened=True")
            print("klayout_exe=windows-file-association")
            return True
        except OSError:
            pass

    print("klayout_opened=False")
    print("reason=klayout executable not found")
    print("hint=Install KLayout GUI, add klayout.exe to PATH, set KLAYOUT_EXE, or pass --klayout-exe C:\\Path\\To\\klayout.exe")
    return False


def find_klayout_executable(explicit_executable: str | None = None) -> Path | None:
    candidates: list[str | Path | None] = [
        explicit_executable,
        os.environ.get("KLAYOUT_EXE"),
        shutil.which("klayout"),
        shutil.which("klayout_app"),
    ]

    if os.name == "nt":
        candidates.extend(_windows_klayout_candidates())

    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        if path.is_file():
            return path
    return None


def _windows_klayout_candidates() -> list[Path]:
    roots = [
        os.environ.get("ProgramFiles"),
        os.environ.get("ProgramFiles(x86)"),
        os.environ.get("LOCALAPPDATA"),
    ]
    relative_paths = [
        Path("KLayout") / "klayout.exe",
        Path("KLayout") / "bin" / "klayout.exe",
        Path("Programs") / "KLayout" / "klayout.exe",
        Path("Programs") / "KLayout" / "bin" / "klayout.exe",
    ]

    candidates: list[Path] = []
    for root in roots:
        if not root:
            continue
        root_path = Path(root)
        candidates.extend(root_path / relative_path for relative_path in relative_paths)

    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        candidates.append(Path(user_profile) / "KLayout" / "klayout.exe")
    return candidates


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
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
    output_path = cad.write_gds(output_path_for_request(request, args.out_dir))

    print(f"generated={output_path}")
    if args.open:
        _open_in_klayout(output_path)
    return 0


def _open_in_klayout(path: Path) -> None:
    executable = shutil.which("klayout")
    if executable is None:
        print("klayout_opened=False")
        print("reason=klayout executable not found on PATH")
        return
    subprocess.Popen([executable, str(path)])
    print("klayout_opened=True")


if __name__ == "__main__":
    raise SystemExit(main())

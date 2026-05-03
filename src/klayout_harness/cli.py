from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess

from .cad import CADHarness
from .actuation import ToolActuationHarness
from .feedback import FeedbackHarness, ValidationReport
from .semantic import ElectrodeLayoutSpec, SemanticHarness


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Vibe Layout GDS files from constrained requests.")
    parser.add_argument("prompt", help="Natural language layout request.")
    parser.add_argument("--out-dir", default="build", help="Output directory for generated GDS.")
    parser.add_argument("--open", action="store_true", help="Open the generated GDS in KLayout if available.")
    parser.add_argument("--klayout-exe", help="Path to klayout.exe. Overrides KLAYOUT_EXE and PATH lookup.")
    args = parser.parse_args()

    semantic = SemanticHarness()
    try:
        spec = semantic.parse(args.prompt)
    except ValueError as exc:
        print("generated=False")
        print(f"reason={exc}")
        return 2
    actuation = ToolActuationHarness(spec)
    output_path = actuation.output_path(args.out_dir).resolve()
    context = actuation.create_context()
    feedback = FeedbackHarness(context)

    print(_engineering_analysis(spec))
    print(_python_code(actuation, output_path))

    spec_report = feedback.validate_electrode_spec(spec)
    if not spec_report.passed:
        print(_design_validation(spec_report, None))
        print("generated=False")
        return 3

    try:
        cad = CADHarness(context)
    except RuntimeError as exc:
        print(_design_validation(spec_report, None))
        print(f"generated=False")
        print(f"reason={exc}")
        return 2
    actuation.build(cad)
    output_path = cad.write_gds(output_path).resolve()
    gds_report = feedback.validate_gds_electrode(output_path, spec)
    print(_design_validation(gds_report, output_path))
    if not gds_report.passed:
        print(f"generated={output_path}")
        return 3

    print(f"generated={output_path}")
    if args.open:
        _open_in_klayout(output_path, args.klayout_exe)
    return 0


def _engineering_analysis(spec: ElectrodeLayoutSpec) -> str:
    return "\n".join(
        [
            "Engineering Analysis",
            f"- Root cell: {spec.root_cell} ({spec.root_width_um:g}um x {spec.root_height_um:g}um)",
            f"- Unit cell: {spec.unit_cell}",
            f"- Electrode: {spec.electrode_width_um:g}um x {spec.electrode_length_um:g}um centered at unit origin",
            f"- Hierarchy: {spec.root_cell} contains one {spec.unit_cell} instance at (0um, 0um)",
            f"- Layer: {spec.layer_name} = ({spec.layer}, {spec.datatype})",
            f"- Fabrication: {spec.rules.process} minimum resolution {spec.rules.minimum_resolution_um:g}um",
            f"- DBU: {spec.rules.dbu_um:g}um per database unit",
        ]
    )


def _python_code(actuation: ToolActuationHarness, output_path: Path) -> str:
    return "\n".join(
        [
            "Python Code",
            "```python",
            actuation.equivalent_python_code(output_path).rstrip(),
            "```",
        ]
    )


def _design_validation(report: ValidationReport, output_path: Path | None) -> str:
    lines = ["Design Validation", f"- Passed: {report.passed}"]
    if output_path is not None:
        lines.append(f"- GDS: {output_path}")
    if report.findings:
        lines.extend(f"- [{finding.rule_id}] {finding.message}" for finding in report.findings)
    else:
        lines.extend(
            [
                "- Resolution check: passed",
                "- DBU mapping check: passed",
                "- Polygon integrity check: passed",
                "- Hierarchy/layer readback check: passed",
            ]
        )
    return "\n".join(lines)


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

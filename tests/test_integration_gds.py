from pathlib import Path

import pytest

from klayout_harness import CADHarness, FeedbackHarness, SemanticHarness, ToolActuationHarness


PROMPT = (
    "Vibe_Layout, $1mm \\times 1mm$ root cell 'CHIP_ROOT'. "
    "Create sub cell 'ELECTRODE_UNIT' with width $50\\mu m$ and length $800\\mu m$ "
    "on Microwriter layer (1, 0)."
)


def test_generated_gds_readback_matches_spec(tmp_path: Path) -> None:
    pytest.importorskip("klayout.db")
    spec = SemanticHarness().parse(PROMPT)
    actuation = ToolActuationHarness(spec)
    context = actuation.create_context()
    cad = CADHarness(context)
    output = tmp_path / "CHIP_ROOT.gds"

    actuation.build(cad)
    cad.write_gds(output)
    report = FeedbackHarness(context).validate_gds_electrode(output, spec)

    assert report.passed, [finding.message for finding in report.findings]

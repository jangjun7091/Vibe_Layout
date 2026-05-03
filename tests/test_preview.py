from pathlib import Path

import pytest

from klayout_harness import CADHarness, SemanticHarness, ToolActuationHarness
from klayout_harness.preview import render_gds_preview


PROMPT = (
    "Vibe_Layout, $1mm \\times 1mm$ root cell 'CHIP_ROOT'. "
    "Create sub cell 'ELECTRODE_UNIT' with width $50\\mu m$ and length $800\\mu m$ "
    "on Microwriter layer (1, 0)."
)


def test_preview_renderer_creates_png(tmp_path: Path) -> None:
    pytest.importorskip("klayout.db")
    spec = SemanticHarness().parse(PROMPT)
    actuation = ToolActuationHarness(spec)
    cad = CADHarness(actuation.create_context())
    gds_path = tmp_path / "layout.gds"
    png_path = tmp_path / "preview.png"

    actuation.build(cad)
    cad.write_gds(gds_path)
    output = render_gds_preview(gds_path, png_path, spec.root_cell, spec.layer, spec.datatype)

    assert output == png_path
    assert png_path.is_file()
    assert png_path.stat().st_size > 0

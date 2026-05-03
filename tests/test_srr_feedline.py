from pathlib import Path
import subprocess
import sys

import pytest

from klayout_harness import CADHarness, FeedbackHarness, SRRFeedlineLayoutSpec, SemanticHarness, ToolActuationHarness


PROMPT = (
    "[Vibe_Layout] Feedline으로 SRR 을 inductive coupling하는 소자를 설계하려고 해. "
    "SRR은 가로 세로 4500 um 정사각형에서 그 중앙에 가로 세로 1500 um 정사각형을 뺀 모양이야. "
    "그리고 위쪽의 capacitive gap은 200 um 이야. "
    "그리고 SRR 아래에 feedline 과의 거리도 200 um 이야. "
    "Feedline은 총 8000 um의 길이를 갖고 있고 폭은 100 um야. "
    "그 아래의 그라운드 패드가 아주 넓게 있는데 feedline과의 거리는 400 um이고, "
    "가로 세로 8000 um, 3000 um이야."
)


def test_semantic_harness_creates_srr_feedline_spec() -> None:
    spec = SemanticHarness().parse(PROMPT)

    assert isinstance(spec, SRRFeedlineLayoutSpec)
    assert spec.root_cell == "SRR_FEEDLINE_ROOT"
    assert spec.srr_cell == "SRR_FEEDLINE"
    assert spec.srr_outer_size_um == 4500
    assert spec.srr_inner_size_um == 1500
    assert spec.ring_width_um == 1500
    assert spec.capacitive_gap_um == 200
    assert spec.srr_feedline_gap_um == 200
    assert spec.feedline_length_um == 8000
    assert spec.feedline_width_um == 100
    assert spec.feedline_ground_gap_um == 400
    assert spec.ground_width_um == 8000
    assert spec.ground_height_um == 3000


def test_srr_feedline_gds_readback(tmp_path: Path) -> None:
    pytest.importorskip("klayout.db")
    spec = SemanticHarness().parse(PROMPT)
    assert isinstance(spec, SRRFeedlineLayoutSpec)
    actuation = ToolActuationHarness(spec)
    context = actuation.create_context()
    cad = CADHarness(context)
    output = tmp_path / "SRR_FEEDLINE_ROOT.gds"

    actuation.build(cad)
    cad.write_gds(output)
    report = FeedbackHarness(context).validate_gds_layout(output, spec)

    assert report.passed, [finding.message for finding in report.findings]


def test_srr_feedline_cli_outputs_sections(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "klayout_harness.cli", PROMPT, "--out-dir", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Engineering Analysis" in result.stdout
    assert "SRR outer square: 4500um x 4500um" in result.stdout
    assert "Capacitive gap: 200um" in result.stdout
    assert "Feedline: 8000um x 100um" in result.stdout
    assert "Ground pad: 8000um x 3000um" in result.stdout
    assert "Python Code" in result.stdout
    assert "Design Validation" in result.stdout
    assert "Passed: True" in result.stdout
    assert (tmp_path / "SRR_FEEDLINE_ROOT.gds").is_file()

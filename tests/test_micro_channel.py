from pathlib import Path
import subprocess
import sys

import pytest

from klayout_harness import CADHarness, FeedbackHarness, MicroChannelLayoutSpec, SemanticHarness, ToolActuationHarness


PROMPT = (
    "Vibe_Layout, 바이오 센서용 미세 채널(Micro-channel) 패턴을 설계해줘. "
    "액체의 흐름이 원활하면서도 반응 면적이 넓어야 해. "
    "장비의 최소 해상도($0.6\\mu m$)를 고려해줘."
)


def test_semantic_harness_creates_micro_channel_defaults() -> None:
    spec = SemanticHarness().parse(PROMPT)

    assert isinstance(spec, MicroChannelLayoutSpec)
    assert spec.root_cell == "BIO_SENSOR_ROOT"
    assert spec.channel_cell == "MICRO_CHANNEL"
    assert spec.channel_width_um == 20
    assert spec.channel_pitch_um == 60
    assert spec.lane_count == 11
    assert spec.layer == 1
    assert spec.datatype == 0
    assert spec.rules.minimum_resolution_um == 0.6
    assert spec.estimated_centerline_length_um == 8960


def test_micro_channel_gds_readback(tmp_path: Path) -> None:
    pytest.importorskip("klayout.db")
    spec = SemanticHarness().parse(PROMPT)
    assert isinstance(spec, MicroChannelLayoutSpec)
    actuation = ToolActuationHarness(spec)
    context = actuation.create_context()
    cad = CADHarness(context)
    output = tmp_path / "BIO_SENSOR_ROOT.gds"

    actuation.build(cad)
    cad.write_gds(output)
    report = FeedbackHarness(context).validate_gds_layout(output, spec)

    assert report.passed, [finding.message for finding in report.findings]


def test_micro_channel_cli_outputs_sections(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "klayout_harness.cli", PROMPT, "--out-dir", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Engineering Analysis" in result.stdout
    assert "Micro-channel" not in result.stderr
    assert "Channel cell: MICRO_CHANNEL" in result.stdout
    assert "Python Code" in result.stdout
    assert "Design Validation" in result.stdout
    assert "Passed: True" in result.stdout
    assert (tmp_path / "BIO_SENSOR_ROOT.gds").is_file()

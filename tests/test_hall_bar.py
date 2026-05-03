from pathlib import Path
import subprocess
import sys

import pytest

from klayout_harness import CADHarness, FeedbackHarness, HallBarLayoutSpec, SemanticHarness, ToolActuationHarness


PROMPT = (
    "Vibe_Layout, 양자 홀 효과(Quantum Hall Effect) 측정을 위한 Standard 6-terminal Hall Bar 레이아웃을 설계해줘. "
    "메인 채널의 폭은 $50\\mu m$로 하고, 전압 리드(Voltage leads)는 신호 간섭을 줄이기 위해 "
    "$10\\mu m$ 폭으로 아주 얇게 설계해. 외부 측정 장비와 연결하기 위해 각 리드 끝에는 "
    "$200\\mu m \\times 200\\mu m$ 크기의 본딩 패드(Bonding Pad)를 추가해줘. "
    "전체 소자는 (1, 0) 레이어에 배치해"
)


def test_semantic_harness_creates_hall_bar_spec() -> None:
    spec = SemanticHarness().parse(PROMPT)

    assert isinstance(spec, HallBarLayoutSpec)
    assert spec.root_cell == "HALL_BAR_ROOT"
    assert spec.hall_cell == "HALL_BAR_6T"
    assert spec.channel_width_um == 50
    assert spec.voltage_lead_width_um == 10
    assert spec.bonding_pad_size_um == 200
    assert spec.terminal_count == 6
    assert spec.layer == 1
    assert spec.datatype == 0


def test_hall_bar_gds_readback(tmp_path: Path) -> None:
    pytest.importorskip("klayout.db")
    spec = SemanticHarness().parse(PROMPT)
    assert isinstance(spec, HallBarLayoutSpec)
    actuation = ToolActuationHarness(spec)
    context = actuation.create_context()
    cad = CADHarness(context)
    output = tmp_path / "HALL_BAR_ROOT.gds"

    actuation.build(cad)
    cad.write_gds(output)
    report = FeedbackHarness(context).validate_gds_layout(output, spec)

    assert report.passed, [finding.message for finding in report.findings]


def test_hall_bar_cli_outputs_sections(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "klayout_harness.cli", PROMPT, "--out-dir", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Engineering Analysis" in result.stdout
    assert "standard 6-terminal Hall bar" in result.stdout
    assert "Bonding pads: 6 pads, 200um x 200um" in result.stdout
    assert "Python Code" in result.stdout
    assert "Design Validation" in result.stdout
    assert "Passed: True" in result.stdout
    assert (tmp_path / "HALL_BAR_ROOT.gds").is_file()

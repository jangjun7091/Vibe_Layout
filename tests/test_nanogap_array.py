from pathlib import Path
import subprocess
import sys

import pytest

from klayout_harness import CADHarness, FeedbackHarness, NanoGapArrayLayoutSpec, SemanticHarness, ToolActuationHarness


PROMPT = (
    "[Vibe_Layout] 터널링 효과(Tunneling effect) 실험을 위해 나노 갭(Nano-gap) 어레이를 만들 거야. "
    "두 전극 사이의 간격을 $0.6\\mu m$부터 $2.0\\mu m$까지 $0.2\\mu m$ 간격으로 키워가며 "
    "총 8개의 소자를 가로로 나열해줘. 각 소자 사이의 간격은 $100\\mu m$로 유지하고, "
    "각 소자 옆에 어떤 간격인지 알 수 있도록 간단한 식별용 박스 패턴을 레이어 (2, 0)에 표시해줘."
)


def test_semantic_harness_creates_nanogap_array_spec() -> None:
    spec = SemanticHarness().parse(PROMPT)

    assert isinstance(spec, NanoGapArrayLayoutSpec)
    assert spec.root_cell == "NANOGAP_ARRAY_ROOT"
    assert spec.array_cell == "NANOGAP_ARRAY"
    assert spec.device_count == 8
    assert spec.gaps_um == (0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0)
    assert spec.device_spacing_um == 100
    assert spec.layer == 1
    assert spec.datatype == 0
    assert spec.marker_layer == 2
    assert spec.marker_datatype == 0


def test_nanogap_array_gds_readback(tmp_path: Path) -> None:
    pytest.importorskip("klayout.db")
    spec = SemanticHarness().parse(PROMPT)
    assert isinstance(spec, NanoGapArrayLayoutSpec)
    actuation = ToolActuationHarness(spec)
    context = actuation.create_context()
    cad = CADHarness(context)
    output = tmp_path / "NANOGAP_ARRAY_ROOT.gds"

    actuation.build(cad)
    cad.write_gds(output)
    report = FeedbackHarness(context).validate_gds_layout(output, spec)

    assert report.passed, [finding.message for finding in report.findings]


def test_nanogap_array_cli_outputs_sections(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "klayout_harness.cli", PROMPT, "--out-dir", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Engineering Analysis" in result.stdout
    assert "8 horizontal nano-gap devices" in result.stdout
    assert "Gap sweep: 0.6um to 2um in 0.2um steps" in result.stdout
    assert "Identifier layer: IDENT = (2, 0)" in result.stdout
    assert "Python Code" in result.stdout
    assert "Design Validation" in result.stdout
    assert "Passed: True" in result.stdout
    assert (tmp_path / "NANOGAP_ARRAY_ROOT.gds").is_file()

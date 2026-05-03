from pathlib import Path

from klayout_harness import CADHarness, DesignAgent, DesignContext, FeedbackHarness, RecordingBackend


def test_agent_refines_after_validation_failure(tmp_path: Path) -> None:
    context = DesignContext.from_mapping(
        {
            "dbu_um": 0.001,
            "layers": {"M1": {"layer": 1, "datatype": 0}},
            "parameters": {},
            "rules": {"min_width_um": 0.2},
        }
    )
    backend = RecordingBackend()
    cad = CADHarness(context, backend=backend)
    agent = DesignAgent(cad, FeedbackHarness(context), expected_cells={"TOP"}, expected_layers={"M1"})

    def design_step(cad_harness: CADHarness, findings):
        if findings:
            cad_harness.add_box_um("TOP", "M1", 0, 0, 1.0, 1.0)

    result = agent.run(design_step, tmp_path / "out.gds", max_iterations=2)

    assert result.report.passed
    assert result.iterations == 2

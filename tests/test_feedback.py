from klayout_harness import CADHarness, DesignContext, FeedbackHarness, RecordingBackend


def _context() -> DesignContext:
    return DesignContext.from_mapping(
        {
            "dbu_um": 0.001,
            "layers": {"M1": {"layer": 1, "datatype": 0}},
            "parameters": {},
            "rules": {"min_width_um": 0.2, "min_spacing_um": 0.2},
        }
    )


def test_feedback_fails_empty_layout() -> None:
    context = _context()

    report = FeedbackHarness(context).validate_recording(RecordingBackend())

    assert not report.passed
    assert report.findings[0].rule_id == "geometry.empty"


def test_feedback_detects_min_width_violation() -> None:
    context = _context()
    backend = RecordingBackend()
    cad = CADHarness(context, backend=backend)

    cad.add_box_um("TOP", "M1", 0, 0, 0.1, 1.0)
    report = FeedbackHarness(context).validate_recording(backend)

    assert not report.passed
    assert {finding.rule_id for finding in report.findings} == {"drc.min_width"}


def test_feedback_detects_min_spacing_violation() -> None:
    context = _context()
    backend = RecordingBackend()
    cad = CADHarness(context, backend=backend)

    cad.add_box_um("TOP", "M1", 0, 0, 1.0, 1.0)
    cad.add_box_um("TOP", "M1", 1.1, 0, 2.0, 1.0)
    report = FeedbackHarness(context).validate_recording(backend)

    assert not report.passed
    assert "drc.min_spacing" in {finding.rule_id for finding in report.findings}


def test_feedback_enforces_microwriter_minimum_resolution() -> None:
    context = DesignContext.from_mapping(
        {
            "dbu_um": 0.001,
            "layers": {"M1": {"layer": 1, "datatype": 0}},
            "parameters": {},
            "rules": {"min_width_um": 0.6, "min_spacing_um": 0.6},
        }
    )
    backend = RecordingBackend()
    cad = CADHarness(context, backend=backend)

    cad.add_box_um("TOP", "M1", 0, 0, 0.5, 1.0)
    report = FeedbackHarness(context).validate_recording(backend)

    assert not report.passed
    assert "drc.min_width" in {finding.rule_id for finding in report.findings}


def test_feedback_detects_non_positive_box_area() -> None:
    context = _context()
    backend = RecordingBackend()
    cad = CADHarness(context, backend=backend)

    cad.add_box_um("TOP", "M1", 0, 0, 0, 1.0)
    report = FeedbackHarness(context).validate_recording(backend)

    assert not report.passed
    assert "geometry.positive_area" in {finding.rule_id for finding in report.findings}


def test_feedback_passes_valid_simple_cell() -> None:
    context = _context()
    backend = RecordingBackend()
    cad = CADHarness(context, backend=backend)

    cad.add_box_um("TOP", "M1", 0, 0, 1.0, 1.0)
    report = FeedbackHarness(context).validate_recording(
        backend,
        expected_cells={"TOP"},
        expected_layers={"M1"},
    )

    assert report.passed

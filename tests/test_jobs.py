from pathlib import Path

from klayout_harness.jobs import LayoutJobRunner


VALID_PROMPT = (
    "Vibe_Layout, $1mm \\times 1mm$ root cell 'CHIP_ROOT'. "
    "Create sub cell 'ELECTRODE_UNIT' with width $50\\mu m$ and length $800\\mu m$ "
    "on Microwriter layer (1, 0)."
)

INVALID_PROMPT = (
    "Vibe_Layout, $1mm \\times 1mm$ root cell 'CHIP_ROOT'. "
    "Create sub cell 'ELECTRODE_UNIT' with width $0.5\\mu m$ and length $800\\mu m$ "
    "on Microwriter layer (1, 0)."
)


def test_job_runner_creates_artifacts(tmp_path: Path) -> None:
    runner = LayoutJobRunner(tmp_path)

    job = runner.run(VALID_PROMPT)

    assert job.status == "completed"
    assert job.validation_passed
    assert job.gds_path is not None and Path(job.gds_path).is_file()
    assert job.preview_path is not None and Path(job.preview_path).is_file()
    assert job.python_code is not None
    assert "import klayout.db as kdb" in job.python_code
    assert (tmp_path / job.job_id / "job.json").is_file()
    assert [event["event"] for event in job.events] == [
        "semantic_started",
        "semantic_resolved",
        "actuation_started",
        "gds_written",
        "preview_rendered",
        "validation_passed",
        "completed",
    ]


def test_job_runner_fails_before_gds_for_subresolution_request(tmp_path: Path) -> None:
    runner = LayoutJobRunner(tmp_path)

    job = runner.run(INVALID_PROMPT)

    assert job.status == "failed"
    assert not job.validation_passed
    assert job.gds_path is None
    assert any(finding["rule_id"] == "drc.minimum_resolution" for finding in job.findings)

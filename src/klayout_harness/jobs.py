from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Callable
from uuid import uuid4

from .actuation import ToolActuationHarness
from .cad import CADHarness
from .feedback import FeedbackHarness, ValidationFinding
from .preview import render_gds_preview
from .semantic import LayoutSpec, SemanticHarness


EventSink = Callable[[dict], None]


@dataclass
class LayoutJob:
    job_id: str
    prompt: str
    status: str
    created_at: str
    updated_at: str
    events: list[dict] = field(default_factory=list)
    spec: dict | None = None
    gds_path: str | None = None
    preview_path: str | None = None
    validation_passed: bool = False
    findings: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class LayoutJobRunner:
    def __init__(self, jobs_dir: str | Path = "build/jobs") -> None:
        self.jobs_dir = Path(jobs_dir)

    def run(self, prompt: str, event_sink: EventSink | None = None) -> LayoutJob:
        job = LayoutJob(
            job_id=uuid4().hex,
            prompt=prompt,
            status="running",
            created_at=_now(),
            updated_at=_now(),
        )
        job_dir = self.jobs_dir / job.job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        def emit(event: str, **payload) -> None:
            item = {"event": event, "timestamp": _now(), **payload}
            job.events.append(item)
            job.updated_at = item["timestamp"]
            self._write_job(job_dir, job)
            if event_sink is not None:
                event_sink(item)

        try:
            emit("semantic_started")
            spec = SemanticHarness().parse(prompt)
            job.spec = _spec_summary(spec)
            emit("semantic_resolved", spec=job.spec)

            actuation = ToolActuationHarness(spec)
            context = actuation.create_context()
            feedback = FeedbackHarness(context)
            spec_report = feedback.validate_layout_spec(spec)
            if not spec_report.passed:
                job.status = "failed"
                job.findings = [_finding_to_dict(finding) for finding in spec_report.findings]
                job.validation_passed = False
                emit("validation_failed", findings=job.findings)
                emit("failed", reason="spec validation failed")
                self._write_job(job_dir, job)
                return job

            emit("actuation_started")
            cad = CADHarness(context)
            actuation.build(cad)
            gds_path = cad.write_gds(job_dir / f"{spec.root_cell}.gds").resolve()
            job.gds_path = str(gds_path)
            emit("gds_written", gds_path=job.gds_path)

            preview_path = render_gds_preview(gds_path, job_dir / "preview.png", spec.root_cell, spec.layer, spec.datatype).resolve()
            job.preview_path = str(preview_path)
            emit("preview_rendered", preview_path=job.preview_path)

            gds_report = feedback.validate_gds_layout(gds_path, spec)
            job.validation_passed = gds_report.passed
            job.findings = [_finding_to_dict(finding) for finding in gds_report.findings]
            if gds_report.passed:
                job.status = "completed"
                emit("validation_passed")
                emit("completed")
            else:
                job.status = "failed"
                emit("validation_failed", findings=job.findings)
                emit("failed", reason="gds validation failed")
            self._write_job(job_dir, job)
            return job
        except Exception as exc:
            job.status = "failed"
            job.findings = [{"severity": "error", "rule_id": "job.exception", "message": str(exc)}]
            emit("failed", reason=str(exc))
            self._write_job(job_dir, job)
            return job

    def load(self, job_id: str) -> LayoutJob | None:
        job_path = self.jobs_dir / job_id / "job.json"
        if not job_path.is_file():
            return None
        data = json.loads(job_path.read_text(encoding="utf-8"))
        return LayoutJob(**data)

    def _write_job(self, job_dir: Path, job: LayoutJob) -> None:
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "job.json").write_text(json.dumps(job.to_dict(), indent=2), encoding="utf-8")


def _spec_summary(spec: LayoutSpec) -> dict:
    data = asdict(spec)
    data["kind"] = spec.__class__.__name__
    return data


def _finding_to_dict(finding: ValidationFinding) -> dict:
    return asdict(finding)


def _now() -> str:
    return datetime.now(UTC).isoformat()

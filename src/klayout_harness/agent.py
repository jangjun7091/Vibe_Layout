from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .cad import CADHarness, RecordingBackend
from .feedback import FeedbackHarness, ValidationFinding, ValidationReport


DesignStep = Callable[[CADHarness, list[ValidationFinding]], None]


@dataclass(frozen=True)
class IterationResult:
    output_path: Path
    report: ValidationReport
    iterations: int
    findings_history: list[list[ValidationFinding]] = field(default_factory=list)


class DesignAgent:
    def __init__(
        self,
        cad: CADHarness,
        feedback: FeedbackHarness,
        expected_cells: set[str] | None = None,
        expected_layers: set[str] | None = None,
    ) -> None:
        self.cad = cad
        self.feedback = feedback
        self.expected_cells = expected_cells
        self.expected_layers = expected_layers

    def run(self, design_step: DesignStep, output_path: str | Path, max_iterations: int = 3) -> IterationResult:
        findings: list[ValidationFinding] = []
        history: list[list[ValidationFinding]] = []
        report = ValidationReport(passed=False)

        for iteration in range(1, max_iterations + 1):
            design_step(self.cad, findings)
            path = self.cad.write_gds(output_path)
            report = self._validate()
            history.append(report.findings)
            if report.passed:
                return IterationResult(path, report, iteration, history)
            findings = report.findings

        return IterationResult(Path(output_path), report, max_iterations, history)

    def _validate(self) -> ValidationReport:
        backend = self.cad.backend
        if isinstance(backend, RecordingBackend):
            return self.feedback.validate_recording(
                backend,
                expected_cells=self.expected_cells,
                expected_layers=self.expected_layers,
            )
        return ValidationReport(
            passed=True,
            findings=[],
        )

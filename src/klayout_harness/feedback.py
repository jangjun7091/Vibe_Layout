from __future__ import annotations

from dataclasses import dataclass, field

from .cad import RecordingBackend
from .context import DesignContext


@dataclass(frozen=True)
class ValidationFinding:
    severity: str
    rule_id: str
    cell: str | None
    layer: str | None
    message: str


@dataclass(frozen=True)
class ValidationReport:
    passed: bool
    findings: list[ValidationFinding] = field(default_factory=list)


class FeedbackHarness:
    def __init__(self, context: DesignContext) -> None:
        self.context = context

    def validate_recording(
        self,
        backend: RecordingBackend,
        expected_cells: set[str] | None = None,
        expected_layers: set[str] | None = None,
    ) -> ValidationReport:
        findings: list[ValidationFinding] = []

        if not backend.cells:
            findings.append(_finding("geometry.empty", None, None, "Layout has no cells."))

        for cell in expected_cells or set():
            if cell not in backend.cells:
                findings.append(_finding("cell.missing", cell, None, f"Missing cell '{cell}'."))

        used_layers = {op.layer.name for op in backend.boxes}
        for layer in expected_layers or set():
            if layer not in used_layers:
                findings.append(_finding("layer.missing", None, layer, f"Missing geometry on layer '{layer}'."))

        min_width_um = self.context.rules.get("min_width_um")
        if min_width_um is not None:
            min_width_dbu = self.context.dbu(min_width_um)
            for op in backend.boxes:
                width = abs(op.x2 - op.x1)
                height = abs(op.y2 - op.y1)
                if width < min_width_dbu or height < min_width_dbu:
                    findings.append(
                        _finding(
                            "drc.min_width",
                            op.cell,
                            op.layer.name,
                            f"Box violates min width rule of {min_width_um} um.",
                        )
                    )

        min_spacing_um = self.context.rules.get("min_spacing_um")
        if min_spacing_um is not None:
            min_spacing_dbu = self.context.dbu(min_spacing_um)
            for index, first in enumerate(backend.boxes):
                for second in backend.boxes[index + 1 :]:
                    if first.cell != second.cell or first.layer != second.layer:
                        continue
                    if _box_spacing(first, second) < min_spacing_dbu:
                        findings.append(
                            _finding(
                                "drc.min_spacing",
                                first.cell,
                                first.layer.name,
                                f"Boxes violate min spacing rule of {min_spacing_um} um.",
                            )
                        )

        return ValidationReport(passed=not findings, findings=findings)


def _finding(rule_id: str, cell: str | None, layer: str | None, message: str) -> ValidationFinding:
    return ValidationFinding(
        severity="error",
        rule_id=rule_id,
        cell=cell,
        layer=layer,
        message=message,
    )


def _box_spacing(first, second) -> int:
    first_x1, first_x2 = sorted((first.x1, first.x2))
    first_y1, first_y2 = sorted((first.y1, first.y2))
    second_x1, second_x2 = sorted((second.x1, second.x2))
    second_y1, second_y2 = sorted((second.y1, second.y2))

    dx = max(second_x1 - first_x2, first_x1 - second_x2, 0)
    dy = max(second_y1 - first_y2, first_y1 - second_y2, 0)
    return max(dx, dy)

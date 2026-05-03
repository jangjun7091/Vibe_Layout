from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .cad import RecordingBackend
from .context import DesignContext
from .semantic import ElectrodeLayoutSpec, LayoutSpec, MicroChannelLayoutSpec, maps_exactly_to_dbu


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
                if width <= 0 or height <= 0:
                    findings.append(
                        _finding(
                            "geometry.positive_area",
                            op.cell,
                            op.layer.name,
                            "Box must have positive closed rectangular area.",
                        )
                    )
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

    def validate_electrode_spec(self, spec: ElectrodeLayoutSpec) -> ValidationReport:
        return self.validate_layout_spec(spec)

    def validate_layout_spec(self, spec: LayoutSpec) -> ValidationReport:
        findings: list[ValidationFinding] = []
        resolution = spec.rules.minimum_resolution_um
        dimensions = _spec_dimensions(spec)
        for name, value in dimensions.items():
            if value <= 0:
                findings.append(_finding("geometry.positive_dimension", None, None, f"{name} must be positive."))
            if value < resolution:
                findings.append(
                    _finding(
                        "drc.minimum_resolution",
                        None,
                        spec.layer_name,
                        f"{name}={value:g}um is below Microwriter minimum resolution {resolution:g}um.",
                    )
                )
            if not maps_exactly_to_dbu(value, spec.rules.dbu_um):
                findings.append(
                    _finding(
                        "dbu.exact_mapping",
                        None,
                        None,
                        f"{name}={value:g}um does not map cleanly to DBU {spec.rules.dbu_um:g}um.",
                    )
                )
        return ValidationReport(passed=not findings, findings=findings)

    def validate_gds_electrode(self, path: str | Path, spec: ElectrodeLayoutSpec) -> ValidationReport:
        return self.validate_gds_layout(path, spec)

    def validate_gds_layout(self, path: str | Path, spec: LayoutSpec) -> ValidationReport:
        findings = list(self.validate_layout_spec(spec).findings)
        try:
            import klayout.db as kdb
        except ModuleNotFoundError:
            return ValidationReport(
                passed=False,
                findings=findings
                + [_finding("tool.klayout_missing", None, None, "klayout.db is required for real GDS readback.")],
            )

        layout = kdb.Layout()
        layout.read(str(path))
        if layout.dbu != spec.rules.dbu_um:
            findings.append(
                _finding(
                    "dbu.value",
                    None,
                    None,
                    f"Expected DBU {spec.rules.dbu_um:g}um, found {layout.dbu:g}um.",
                )
            )

        root = layout.cell(spec.root_cell)
        child_cell_name = spec.unit_cell if isinstance(spec, ElectrodeLayoutSpec) else spec.channel_cell
        unit = layout.cell(child_cell_name)
        if root is None:
            findings.append(_finding("cell.missing", spec.root_cell, None, f"Missing cell '{spec.root_cell}'."))
        if unit is None:
            findings.append(_finding("cell.missing", child_cell_name, None, f"Missing cell '{child_cell_name}'."))
        if root is None or unit is None:
            return ValidationReport(passed=False, findings=findings)

        instance_count = sum(1 for inst in root.each_inst() if inst.cell.name == child_cell_name)
        if instance_count != 1:
            findings.append(
                _finding(
                    "hierarchy.instance",
                    spec.root_cell,
                    None,
                    f"Expected one '{child_cell_name}' instance in '{spec.root_cell}', found {instance_count}.",
                )
            )

        layer_index = layout.layer(spec.layer, spec.datatype)
        root_shapes = root.shapes(layer_index).size()
        unit_shapes = unit.shapes(layer_index).size()
        if root_shapes < 1:
            findings.append(_finding("layer.missing", spec.root_cell, spec.layer_name, "Root has no frame geometry."))
        if isinstance(spec, ElectrodeLayoutSpec) and unit_shapes != 1:
            findings.append(
                _finding(
                    "geometry.electrode_count",
                    child_cell_name,
                    spec.layer_name,
                    f"Expected one electrode shape, found {unit_shapes}.",
                )
            )
        if isinstance(spec, MicroChannelLayoutSpec) and unit_shapes < spec.lane_count:
            findings.append(
                _finding(
                    "geometry.channel_count",
                    child_cell_name,
                    spec.layer_name,
                    f"Expected at least {spec.lane_count} channel lane shapes, found {unit_shapes}.",
                )
            )

        _expect_bbox(findings, root.bbox(), layout.dbu, spec.root_width_um, spec.root_height_um, spec.root_cell, spec.layer_name)
        if isinstance(spec, ElectrodeLayoutSpec):
            _expect_bbox(
                findings,
                unit.bbox(),
                layout.dbu,
                spec.electrode_width_um,
                spec.electrode_length_um,
                child_cell_name,
                spec.layer_name,
            )
        else:
            _expect_bbox(
                findings,
                unit.bbox(),
                layout.dbu,
                spec.lane_length_um + spec.port_size_um * 2,
                spec.active_height_um + spec.port_size_um - spec.channel_width_um,
                child_cell_name,
                spec.layer_name,
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


def _expect_bbox(
    findings: list[ValidationFinding],
    bbox,
    dbu_um: float,
    expected_width_um: float,
    expected_height_um: float,
    cell: str,
    layer: str,
) -> None:
    width_um = bbox.width() * dbu_um
    height_um = bbox.height() * dbu_um
    if abs(width_um - expected_width_um) > dbu_um or abs(height_um - expected_height_um) > dbu_um:
        findings.append(
            _finding(
                "geometry.bbox",
                cell,
                layer,
                f"Expected bbox {expected_width_um:g}um x {expected_height_um:g}um, found {width_um:g}um x {height_um:g}um.",
            )
        )


def _spec_dimensions(spec: LayoutSpec) -> dict[str, float]:
    if isinstance(spec, ElectrodeLayoutSpec):
        return {
            "root_width_um": spec.root_width_um,
            "root_height_um": spec.root_height_um,
            "electrode_width_um": spec.electrode_width_um,
            "electrode_length_um": spec.electrode_length_um,
            "frame_width_um": spec.frame_width_um,
        }
    return {
        "root_width_um": spec.root_width_um,
        "root_height_um": spec.root_height_um,
        "channel_width_um": spec.channel_width_um,
        "channel_pitch_um": spec.channel_pitch_um,
        "lane_length_um": spec.lane_length_um,
        "port_size_um": spec.port_size_um,
        "frame_width_um": spec.frame_width_um,
    }

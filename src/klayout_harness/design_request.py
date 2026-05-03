from __future__ import annotations

from pathlib import Path

from .actuation import ToolActuationHarness
from .cad import CADHarness
from .context import DesignContext
from .semantic import ElectrodeLayoutSpec, SemanticHarness


ElectrodeRequest = ElectrodeLayoutSpec


def parse_electrode_request(prompt: str) -> ElectrodeRequest:
    return SemanticHarness().parse(prompt)


def build_electrode_layout(request: ElectrodeRequest, cad: CADHarness) -> None:
    ToolActuationHarness(request).build(cad)


def default_context_for_request() -> DesignContext:
    placeholder = ElectrodeLayoutSpec(
        root_cell="ROOT",
        root_width_um=1.0,
        root_height_um=1.0,
        unit_cell="UNIT",
        electrode_width_um=1.0,
        electrode_length_um=1.0,
        layer=1,
        datatype=0,
    )
    return ToolActuationHarness(placeholder).create_context()


def output_path_for_request(request: ElectrodeRequest, directory: str | Path) -> Path:
    return ToolActuationHarness(request).output_path(directory)

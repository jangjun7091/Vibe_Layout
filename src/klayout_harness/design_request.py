from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path

from .cad import CADHarness
from .context import DesignContext


@dataclass(frozen=True)
class ElectrodeRequest:
    root_cell: str
    root_width_um: float
    root_height_um: float
    unit_cell: str
    electrode_width_um: float
    electrode_length_um: float
    layer: int
    datatype: int
    layer_name: str = "MWRITER"
    frame_width_um: float = 1.0


def parse_electrode_request(prompt: str) -> ElectrodeRequest:
    cells = re.findall(r"'([^']+)'|\"([^\"]+)\"", prompt)
    cell_names = [left or right for left, right in cells]
    if len(cell_names) < 2:
        raise ValueError("Request must include root and unit cell names in quotes.")

    root_size = _find_pair(prompt, r"(\d+(?:\.\d+)?)\s*mm\s*[x×]\s*(\d+(?:\.\d+)?)\s*mm")
    if root_size is None:
        root_size = _find_pair(prompt, r"(\d+(?:\.\d+)?)\s*mm\s*\\times\s*(\d+(?:\.\d+)?)\s*mm")
    if root_size is None:
        raise ValueError("Request must include root cell size in mm, for example 1mm x 1mm.")

    width_um = _find_value(prompt, [r"폭\s*\$?(\d+(?:\.\d+)?)\s*\\?mu\s*m", r"width\s*(\d+(?:\.\d+)?)\s*um"])
    length_um = _find_value(prompt, [r"길이\s*\$?(\d+(?:\.\d+)?)\s*\\?mu\s*m", r"length\s*(\d+(?:\.\d+)?)\s*um"])
    if width_um is None or length_um is None:
        raise ValueError("Request must include electrode width and length in um.")

    layer_match = re.search(r"\((\d+)\s*,\s*(\d+)\)", prompt)
    if layer_match is None:
        raise ValueError("Request must include layer tuple, for example (1, 0).")

    return ElectrodeRequest(
        root_cell=cell_names[0],
        root_width_um=root_size[0] * 1000,
        root_height_um=root_size[1] * 1000,
        unit_cell=cell_names[1],
        electrode_width_um=width_um,
        electrode_length_um=length_um,
        layer=int(layer_match.group(1)),
        datatype=int(layer_match.group(2)),
    )


def build_electrode_layout(request: ElectrodeRequest, cad: CADHarness) -> None:
    cad.ensure_layer(request.layer_name, request.layer, request.datatype)
    cad.create_cell(request.root_cell)
    cad.create_cell(request.unit_cell)
    cad.add_frame_um(
        request.root_cell,
        request.layer_name,
        request.root_width_um,
        request.root_height_um,
        request.frame_width_um,
    )
    cad.add_centered_box_um(
        request.unit_cell,
        request.layer_name,
        request.electrode_width_um,
        request.electrode_length_um,
    )
    cad.add_instance_um(request.root_cell, request.unit_cell, 0, 0)


def default_context_for_request() -> DesignContext:
    return DesignContext.from_mapping(
        {
            "dbu_um": 0.001,
            "layers": {},
            "parameters": {},
            "rules": {"min_width_um": 0.2, "min_spacing_um": 0.2},
        }
    )


def output_path_for_request(request: ElectrodeRequest, directory: str | Path) -> Path:
    return Path(directory) / f"{request.root_cell}.gds"


def _find_pair(text: str, pattern: str) -> tuple[float, float] | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if match is None:
        return None
    return float(match.group(1)), float(match.group(2))


def _find_value(text: str, patterns: list[str]) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match is not None:
            return float(match.group(1))
    return None

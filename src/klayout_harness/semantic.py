from __future__ import annotations

from dataclasses import dataclass
import math
import re


@dataclass(frozen=True)
class FabricationRules:
    process: str = "Microwriter"
    minimum_resolution_um: float = 0.6
    dbu_um: float = 0.001


@dataclass(frozen=True)
class ElectrodeLayoutSpec:
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
    rules: FabricationRules = FabricationRules()

    @property
    def electrode_height_um(self) -> float:
        return self.electrode_length_um


class SemanticHarness:
    def parse(self, prompt: str) -> ElectrodeLayoutSpec:
        cells = re.findall(r"'([^']+)'|\"([^\"]+)\"", prompt)
        cell_names = [left or right for left, right in cells]
        if len(cell_names) < 2:
            raise ValueError("Request must include root and unit cell names in quotes.")

        root_size = _find_pair(prompt, r"(\d+(?:\.\d+)?)\s*mm\s*[xX×]\s*(\d+(?:\.\d+)?)\s*mm")
        if root_size is None:
            root_size = _find_pair(prompt, r"(\d+(?:\.\d+)?)\s*mm\s*\\times\s*(\d+(?:\.\d+)?)\s*mm")
        if root_size is None:
            raise ValueError("Request must include root cell size in mm, for example 1mm x 1mm.")

        um_values = [float(value) for value in re.findall(r"(\d+(?:\.\d+)?)\s*\\?mu\s*m", prompt, re.IGNORECASE)]
        if len(um_values) < 2:
            um_values = [float(value) for value in re.findall(r"(\d+(?:\.\d+)?)\s*u\s*m", prompt, re.IGNORECASE)]
        if len(um_values) < 2:
            raise ValueError("Request must include electrode width and length in um.")

        layer_match = re.search(r"\((\d+)\s*,\s*(\d+)\)", prompt)
        if layer_match is None:
            raise ValueError("Request must include layer tuple, for example (1, 0).")

        return ElectrodeLayoutSpec(
            root_cell=cell_names[0],
            root_width_um=root_size[0] * 1000,
            root_height_um=root_size[1] * 1000,
            unit_cell=cell_names[1],
            electrode_width_um=um_values[0],
            electrode_length_um=um_values[1],
            layer=int(layer_match.group(1)),
            datatype=int(layer_match.group(2)),
        )

    def validate_spec(self, spec: ElectrodeLayoutSpec) -> list[str]:
        errors: list[str] = []
        resolution = spec.rules.minimum_resolution_um
        for name, value in {
            "root_width_um": spec.root_width_um,
            "root_height_um": spec.root_height_um,
            "electrode_width_um": spec.electrode_width_um,
            "electrode_length_um": spec.electrode_length_um,
            "frame_width_um": spec.frame_width_um,
        }.items():
            if value <= 0:
                errors.append(f"{name} must be positive.")
            if value < resolution:
                errors.append(f"{name}={value:g}um is below Microwriter minimum resolution {resolution:g}um.")
            if not maps_exactly_to_dbu(value, spec.rules.dbu_um):
                errors.append(f"{name}={value:g}um does not map cleanly to DBU {spec.rules.dbu_um:g}um.")
        return errors


def maps_exactly_to_dbu(value_um: float, dbu_um: float) -> bool:
    scaled = value_um / dbu_um
    return math.isclose(scaled, round(scaled), rel_tol=0, abs_tol=1e-9)


def _find_pair(text: str, pattern: str) -> tuple[float, float] | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if match is None:
        return None
    return float(match.group(1)), float(match.group(2))

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import TypeAlias


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


@dataclass(frozen=True)
class MicroChannelLayoutSpec:
    root_cell: str = "BIO_SENSOR_ROOT"
    root_width_um: float = 1000.0
    root_height_um: float = 1000.0
    channel_cell: str = "MICRO_CHANNEL"
    channel_width_um: float = 20.0
    channel_pitch_um: float = 60.0
    lane_length_um: float = 760.0
    lane_count: int = 11
    port_size_um: float = 100.0
    layer: int = 1
    datatype: int = 0
    layer_name: str = "MWRITER"
    frame_width_um: float = 1.0
    rules: FabricationRules = FabricationRules()

    @property
    def active_height_um(self) -> float:
        return (self.lane_count - 1) * self.channel_pitch_um + self.channel_width_um

    @property
    def estimated_centerline_length_um(self) -> float:
        return self.lane_count * self.lane_length_um + (self.lane_count - 1) * self.channel_pitch_um


LayoutSpec: TypeAlias = ElectrodeLayoutSpec | MicroChannelLayoutSpec


class SemanticHarness:
    def parse(self, prompt: str) -> LayoutSpec:
        if _is_micro_channel_request(prompt):
            return self._parse_micro_channel(prompt)
        return self._parse_electrode(prompt)

    def _parse_electrode(self, prompt: str) -> ElectrodeLayoutSpec:
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

    def _parse_micro_channel(self, prompt: str) -> MicroChannelLayoutSpec:
        cells = re.findall(r"'([^']+)'|\"([^\"]+)\"", prompt)
        cell_names = [left or right for left, right in cells]
        layer_match = re.search(r"\((\d+)\s*,\s*(\d+)\)", prompt)
        return MicroChannelLayoutSpec(
            root_cell=cell_names[0] if len(cell_names) >= 1 else "BIO_SENSOR_ROOT",
            channel_cell=cell_names[1] if len(cell_names) >= 2 else "MICRO_CHANNEL",
            layer=int(layer_match.group(1)) if layer_match else 1,
            datatype=int(layer_match.group(2)) if layer_match else 0,
        )

    def validate_spec(self, spec: LayoutSpec) -> list[str]:
        errors: list[str] = []
        resolution = spec.rules.minimum_resolution_um
        for name, value in _physical_dimensions(spec).items():
            if value <= 0:
                errors.append(f"{name} must be positive.")
            if value < resolution:
                errors.append(f"{name}={value:g}um is below Microwriter minimum resolution {resolution:g}um.")
            if not maps_exactly_to_dbu(value, spec.rules.dbu_um):
                errors.append(f"{name}={value:g}um does not map cleanly to DBU {spec.rules.dbu_um:g}um.")
        if isinstance(spec, MicroChannelLayoutSpec):
            if spec.lane_count < 2:
                errors.append("lane_count must be at least 2 for serpentine flow.")
            if spec.lane_count % 2 == 0:
                errors.append("lane_count must be odd so inlet and outlet land on opposite sides.")
            if spec.active_height_um > spec.root_height_um - 2 * spec.port_size_um:
                errors.append("Serpentine active height exceeds root cell clearance.")
            if spec.lane_length_um + spec.port_size_um > spec.root_width_um:
                errors.append("Serpentine lane length and ports exceed root cell width.")
        return errors


def maps_exactly_to_dbu(value_um: float, dbu_um: float) -> bool:
    scaled = value_um / dbu_um
    return math.isclose(scaled, round(scaled), rel_tol=0, abs_tol=1e-9)


def _find_pair(text: str, pattern: str) -> tuple[float, float] | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if match is None:
        return None
    return float(match.group(1)), float(match.group(2))


def _is_micro_channel_request(prompt: str) -> bool:
    lowered = prompt.lower()
    return any(token in lowered for token in ["micro-channel", "micro channel", "microchannel", "미세 채널", "바이오 센서"])


def _physical_dimensions(spec: LayoutSpec) -> dict[str, float]:
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

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


@dataclass(frozen=True)
class HallBarLayoutSpec:
    root_cell: str = "HALL_BAR_ROOT"
    root_width_um: float = 1400.0
    root_height_um: float = 1200.0
    hall_cell: str = "HALL_BAR_6T"
    channel_length_um: float = 600.0
    channel_width_um: float = 50.0
    current_lead_length_um: float = 100.0
    voltage_lead_width_um: float = 10.0
    voltage_lead_length_um: float = 275.0
    voltage_probe_spacing_um: float = 300.0
    bonding_pad_size_um: float = 200.0
    layer: int = 1
    datatype: int = 0
    layer_name: str = "MWRITER"
    frame_width_um: float = 1.0
    rules: FabricationRules = FabricationRules()

    @property
    def terminal_count(self) -> int:
        return 6

    @property
    def device_width_um(self) -> float:
        return self.channel_length_um + 2 * self.current_lead_length_um + 2 * self.bonding_pad_size_um

    @property
    def device_height_um(self) -> float:
        return self.channel_width_um + 2 * self.voltage_lead_length_um + 2 * self.bonding_pad_size_um


@dataclass(frozen=True)
class NanoGapArrayLayoutSpec:
    root_cell: str = "NANOGAP_ARRAY_ROOT"
    root_width_um: float = 1900.0
    root_height_um: float = 360.0
    array_cell: str = "NANOGAP_ARRAY"
    device_count: int = 8
    gap_start_um: float = 0.6
    gap_stop_um: float = 2.0
    gap_step_um: float = 0.2
    device_spacing_um: float = 100.0
    electrode_length_um: float = 60.0
    electrode_width_um: float = 30.0
    marker_box_size_um: float = 8.0
    marker_box_pitch_um: float = 12.0
    marker_offset_y_um: float = -70.0
    layer: int = 1
    datatype: int = 0
    layer_name: str = "MWRITER"
    marker_layer: int = 2
    marker_datatype: int = 0
    marker_layer_name: str = "IDENT"
    frame_width_um: float = 1.0
    rules: FabricationRules = FabricationRules()

    @property
    def gaps_um(self) -> tuple[float, ...]:
        return tuple(round(self.gap_start_um + index * self.gap_step_um, 10) for index in range(self.device_count))

    @property
    def max_device_width_um(self) -> float:
        return 2 * self.electrode_length_um + self.gap_stop_um

    @property
    def array_width_um(self) -> float:
        return self.device_count * self.max_device_width_um + (self.device_count - 1) * self.device_spacing_um

    @property
    def active_width_um(self) -> float:
        return (
            (self.device_count - 1) * (self.max_device_width_um + self.device_spacing_um)
            + 2 * self.electrode_length_um
            + self.gap_start_um / 2
            + self.gap_stop_um / 2
        )

    @property
    def array_height_um(self) -> float:
        return self.electrode_width_um / 2 + abs(self.marker_offset_y_um) + self.marker_box_size_um / 2


LayoutSpec: TypeAlias = ElectrodeLayoutSpec | MicroChannelLayoutSpec | HallBarLayoutSpec | NanoGapArrayLayoutSpec


VIBE_COMMAND = "[Vibe_Layout]"
_COMMAND_PATTERN = re.compile(r"^\s*(?:\[Vibe_Layout\]|Vibe_Layout)\s*[:,，-]?\s*(.+)$", re.IGNORECASE | re.DOTALL)


class SemanticHarness:
    def parse(self, prompt: str) -> LayoutSpec:
        design_prompt = _extract_design_prompt(prompt)
        if _is_hall_bar_request(design_prompt):
            return self._parse_hall_bar(design_prompt)
        if _is_nanogap_request(design_prompt):
            return self._parse_nanogap_array(design_prompt)
        if _is_micro_channel_request(design_prompt):
            return self._parse_micro_channel(design_prompt)
        return self._parse_electrode(design_prompt)

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

    def _parse_hall_bar(self, prompt: str) -> HallBarLayoutSpec:
        layer_match = re.search(r"\((\d+)\s*,\s*(\d+)\)", prompt)
        values = [float(value) for value in re.findall(r"(\d+(?:\.\d+)?)\s*\\?mu\s*m", prompt, re.IGNORECASE)]
        if len(values) < 3:
            values = [float(value) for value in re.findall(r"(\d+(?:\.\d+)?)\s*u\s*m", prompt, re.IGNORECASE)]
        channel_width = values[0] if len(values) >= 1 else 50.0
        voltage_width = values[1] if len(values) >= 2 else 10.0
        pad_size = values[2] if len(values) >= 3 else 200.0
        return HallBarLayoutSpec(
            channel_width_um=channel_width,
            voltage_lead_width_um=voltage_width,
            bonding_pad_size_um=pad_size,
            layer=int(layer_match.group(1)) if layer_match else 1,
            datatype=int(layer_match.group(2)) if layer_match else 0,
        )

    def _parse_nanogap_array(self, prompt: str) -> NanoGapArrayLayoutSpec:
        layer_tuples = [(int(layer), int(datatype)) for layer, datatype in re.findall(r"\((\d+)\s*,\s*(\d+)\)", prompt)]
        values = [float(value) for value in re.findall(r"(\d+(?:\.\d+)?)\s*\\?mu\s*m", prompt, re.IGNORECASE)]
        if len(values) < 4:
            values = [float(value) for value in re.findall(r"(\d+(?:\.\d+)?)\s*u\s*m", prompt, re.IGNORECASE)]
        gap_start = values[0] if len(values) >= 1 else 0.6
        gap_stop = values[1] if len(values) >= 2 else 2.0
        gap_step = values[2] if len(values) >= 3 else 0.2
        device_spacing = values[3] if len(values) >= 4 else 100.0
        count_match = re.search(r"총\s*(\d+)|(\d+)\s*개", prompt)
        device_count = int(count_match.group(1) or count_match.group(2)) if count_match else 8
        electrode_layer = layer_tuples[0] if len(layer_tuples) >= 2 else (1, 0)
        marker_layer = layer_tuples[-1] if layer_tuples else (2, 0)
        return NanoGapArrayLayoutSpec(
            device_count=device_count,
            gap_start_um=gap_start,
            gap_stop_um=gap_stop,
            gap_step_um=gap_step,
            device_spacing_um=device_spacing,
            layer=electrode_layer[0],
            datatype=electrode_layer[1],
            marker_layer=marker_layer[0],
            marker_datatype=marker_layer[1],
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
        if isinstance(spec, HallBarLayoutSpec):
            if spec.terminal_count != 6:
                errors.append("Standard Hall bar must have exactly 6 terminals.")
            if spec.voltage_lead_width_um >= spec.channel_width_um:
                errors.append("Voltage leads must be narrower than the main channel.")
            if spec.device_width_um > spec.root_width_um - spec.bonding_pad_size_um / 2:
                errors.append("Hall bar device width exceeds root cell clearance.")
            if spec.device_height_um > spec.root_height_um - spec.bonding_pad_size_um / 2:
                errors.append("Hall bar device height exceeds root cell clearance.")
        if isinstance(spec, NanoGapArrayLayoutSpec):
            expected_stop = spec.gap_start_um + (spec.device_count - 1) * spec.gap_step_um
            if not math.isclose(expected_stop, spec.gap_stop_um, rel_tol=0, abs_tol=1e-9):
                errors.append("Nano-gap count, start, stop, and step are inconsistent.")
            if spec.array_width_um > spec.root_width_um - 2 * spec.frame_width_um:
                errors.append("Nano-gap array width exceeds root cell clearance.")
        return errors


def maps_exactly_to_dbu(value_um: float, dbu_um: float) -> bool:
    scaled = value_um / dbu_um
    return math.isclose(scaled, round(scaled), rel_tol=0, abs_tol=1e-9)


def _find_pair(text: str, pattern: str) -> tuple[float, float] | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if match is None:
        return None
    return float(match.group(1)), float(match.group(2))


def _extract_design_prompt(prompt: str) -> str:
    match = _COMMAND_PATTERN.match(prompt)
    if match is None:
        raise ValueError(f"Layout generation prompts must begin with {VIBE_COMMAND}.")
    design_prompt = match.group(1).strip()
    if not design_prompt:
        raise ValueError(f"Layout generation prompts must include a design request after {VIBE_COMMAND}.")
    return design_prompt


def _is_micro_channel_request(prompt: str) -> bool:
    lowered = prompt.lower()
    return any(token in lowered for token in ["micro-channel", "micro channel", "microchannel", "미세 채널", "바이오 센서"])


def _is_hall_bar_request(prompt: str) -> bool:
    lowered = prompt.lower()
    return any(token in lowered for token in ["hall bar", "quantum hall", "6-terminal", "6 terminal", "홀 효과", "홀 바"])


def _is_nanogap_request(prompt: str) -> bool:
    lowered = prompt.lower()
    return any(token in lowered for token in ["nano-gap", "nanogap", "nano gap", "나노 갭", "터널링", "tunneling"])


def _physical_dimensions(spec: LayoutSpec) -> dict[str, float]:
    if isinstance(spec, ElectrodeLayoutSpec):
        return {
            "root_width_um": spec.root_width_um,
            "root_height_um": spec.root_height_um,
            "electrode_width_um": spec.electrode_width_um,
            "electrode_length_um": spec.electrode_length_um,
            "frame_width_um": spec.frame_width_um,
        }
    if isinstance(spec, MicroChannelLayoutSpec):
        return {
            "root_width_um": spec.root_width_um,
            "root_height_um": spec.root_height_um,
            "channel_width_um": spec.channel_width_um,
            "channel_pitch_um": spec.channel_pitch_um,
            "lane_length_um": spec.lane_length_um,
            "port_size_um": spec.port_size_um,
            "frame_width_um": spec.frame_width_um,
        }
    if isinstance(spec, NanoGapArrayLayoutSpec):
        return {
            "root_width_um": spec.root_width_um,
            "root_height_um": spec.root_height_um,
            "gap_start_um": spec.gap_start_um,
            "gap_stop_um": spec.gap_stop_um,
            "device_spacing_um": spec.device_spacing_um,
            "electrode_length_um": spec.electrode_length_um,
            "electrode_width_um": spec.electrode_width_um,
            "marker_box_size_um": spec.marker_box_size_um,
            "marker_box_pitch_um": spec.marker_box_pitch_um,
            "frame_width_um": spec.frame_width_um,
        }
    return {
        "root_width_um": spec.root_width_um,
        "root_height_um": spec.root_height_um,
        "channel_length_um": spec.channel_length_um,
        "channel_width_um": spec.channel_width_um,
        "current_lead_length_um": spec.current_lead_length_um,
        "voltage_lead_width_um": spec.voltage_lead_width_um,
        "voltage_lead_length_um": spec.voltage_lead_length_um,
        "voltage_probe_spacing_um": spec.voltage_probe_spacing_um,
        "bonding_pad_size_um": spec.bonding_pad_size_um,
        "frame_width_um": spec.frame_width_um,
    }

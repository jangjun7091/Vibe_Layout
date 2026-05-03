from __future__ import annotations

from pathlib import Path

from .cad import CADHarness
from .context import DesignContext
from .semantic import (
    ElectrodeLayoutSpec,
    HallBarLayoutSpec,
    LayoutSpec,
    MicroChannelLayoutSpec,
    NanoGapArrayLayoutSpec,
    SRRFeedlineLayoutSpec,
)


class ToolActuationHarness:
    def __init__(self, spec: LayoutSpec) -> None:
        self.spec = spec

    def create_context(self) -> DesignContext:
        return DesignContext.from_mapping(
            {
                "dbu_um": self.spec.rules.dbu_um,
                "layers": {
                    self.spec.layer_name: {
                        "layer": self.spec.layer,
                        "datatype": self.spec.datatype,
                    },
                    **_extra_layers(self.spec),
                },
                "parameters": {},
                "rules": {
                    "min_width_um": self.spec.rules.minimum_resolution_um,
                    "min_spacing_um": self.spec.rules.minimum_resolution_um,
                },
            }
        )

    def build(self, cad: CADHarness) -> None:
        if isinstance(self.spec, HallBarLayoutSpec):
            self._build_hall_bar(cad)
            return
        if isinstance(self.spec, NanoGapArrayLayoutSpec):
            self._build_nanogap_array(cad)
            return
        if isinstance(self.spec, SRRFeedlineLayoutSpec):
            self._build_srr_feedline(cad)
            return
        if isinstance(self.spec, MicroChannelLayoutSpec):
            self._build_micro_channel(cad)
            return
        self._build_electrode(cad)

    def _build_electrode(self, cad: CADHarness) -> None:
        spec = self.spec
        assert isinstance(spec, ElectrodeLayoutSpec)
        cad.create_cell(spec.root_cell)
        cad.create_cell(spec.unit_cell)
        cad.add_frame_um(
            spec.root_cell,
            spec.layer_name,
            spec.root_width_um,
            spec.root_height_um,
            spec.frame_width_um,
        )
        cad.add_centered_box_um(
            spec.unit_cell,
            spec.layer_name,
            spec.electrode_width_um,
            spec.electrode_length_um,
        )
        cad.add_instance_um(spec.root_cell, spec.unit_cell, 0, 0)

    def _build_micro_channel(self, cad: CADHarness) -> None:
        spec = self.spec
        assert isinstance(spec, MicroChannelLayoutSpec)
        cad.create_cell(spec.root_cell)
        cad.create_cell(spec.channel_cell)
        cad.add_frame_um(
            spec.root_cell,
            spec.layer_name,
            spec.root_width_um,
            spec.root_height_um,
            spec.frame_width_um,
        )

        half_lane = spec.lane_length_um / 2
        half_width = spec.channel_width_um / 2
        first_y = -((spec.lane_count - 1) * spec.channel_pitch_um) / 2
        lane_ys = [first_y + index * spec.channel_pitch_um for index in range(spec.lane_count)]
        for y in lane_ys:
            cad.add_box_um(spec.channel_cell, spec.layer_name, -half_lane, y - half_width, half_lane, y + half_width)

        for index in range(spec.lane_count - 1):
            connector_x = half_lane if index % 2 == 0 else -half_lane
            y1 = min(lane_ys[index], lane_ys[index + 1]) - half_width
            y2 = max(lane_ys[index], lane_ys[index + 1]) + half_width
            cad.add_box_um(
                spec.channel_cell,
                spec.layer_name,
                connector_x - half_width,
                y1,
                connector_x + half_width,
                y2,
            )

        inlet_y = lane_ys[0]
        outlet_y = lane_ys[-1]
        cad.add_box_um(
            spec.channel_cell,
            spec.layer_name,
            -half_lane - spec.port_size_um,
            inlet_y - spec.port_size_um / 2,
            -half_lane,
            inlet_y + spec.port_size_um / 2,
        )
        cad.add_box_um(
            spec.channel_cell,
            spec.layer_name,
            half_lane,
            outlet_y - spec.port_size_um / 2,
            half_lane + spec.port_size_um,
            outlet_y + spec.port_size_um / 2,
        )
        cad.add_instance_um(spec.root_cell, spec.channel_cell, 0, 0)

    def _build_hall_bar(self, cad: CADHarness) -> None:
        spec = self.spec
        assert isinstance(spec, HallBarLayoutSpec)
        cad.create_cell(spec.root_cell)
        cad.create_cell(spec.hall_cell)
        cad.add_frame_um(spec.root_cell, spec.layer_name, spec.root_width_um, spec.root_height_um, spec.frame_width_um)

        half_channel = spec.channel_length_um / 2
        half_channel_width = spec.channel_width_um / 2
        half_pad = spec.bonding_pad_size_um / 2
        half_voltage = spec.voltage_lead_width_um / 2
        half_spacing = spec.voltage_probe_spacing_um / 2

        # Main Hall bar and current leads.
        cad.add_box_um(spec.hall_cell, spec.layer_name, -half_channel, -half_channel_width, half_channel, half_channel_width)
        cad.add_box_um(
            spec.hall_cell,
            spec.layer_name,
            -half_channel - spec.current_lead_length_um,
            -half_channel_width,
            -half_channel,
            half_channel_width,
        )
        cad.add_box_um(
            spec.hall_cell,
            spec.layer_name,
            half_channel,
            -half_channel_width,
            half_channel + spec.current_lead_length_um,
            half_channel_width,
        )

        # Current bonding pads.
        left_pad_cx = -half_channel - spec.current_lead_length_um - half_pad
        right_pad_cx = half_channel + spec.current_lead_length_um + half_pad
        cad.add_box_um(spec.hall_cell, spec.layer_name, left_pad_cx - half_pad, -half_pad, left_pad_cx + half_pad, half_pad)
        cad.add_box_um(spec.hall_cell, spec.layer_name, right_pad_cx - half_pad, -half_pad, right_pad_cx + half_pad, half_pad)

        # Four voltage probes and pads.
        for x in (-half_spacing, half_spacing):
            for direction in (-1, 1):
                y1 = direction * half_channel_width
                y2 = direction * (half_channel_width + spec.voltage_lead_length_um)
                cad.add_box_um(
                    spec.hall_cell,
                    spec.layer_name,
                    x - half_voltage,
                    min(y1, y2),
                    x + half_voltage,
                    max(y1, y2),
                )
                pad_cy = direction * (half_channel_width + spec.voltage_lead_length_um + half_pad)
                cad.add_box_um(
                    spec.hall_cell,
                    spec.layer_name,
                    x - half_pad,
                    pad_cy - half_pad,
                    x + half_pad,
                    pad_cy + half_pad,
                )

        cad.add_instance_um(spec.root_cell, spec.hall_cell, 0, 0)

    def _build_nanogap_array(self, cad: CADHarness) -> None:
        spec = self.spec
        assert isinstance(spec, NanoGapArrayLayoutSpec)
        cad.create_cell(spec.root_cell)
        cad.create_cell(spec.array_cell)
        cad.add_frame_um(spec.root_cell, spec.layer_name, spec.root_width_um, spec.root_height_um, spec.frame_width_um)

        start_x = -spec.array_width_um / 2 + spec.max_device_width_um / 2
        half_electrode_w = spec.electrode_width_um / 2
        half_marker = spec.marker_box_size_um / 2
        for index, gap_um in enumerate(spec.gaps_um):
            center_x = start_x + index * (spec.max_device_width_um + spec.device_spacing_um)
            half_gap = gap_um / 2
            left_x2 = center_x - half_gap
            left_x1 = left_x2 - spec.electrode_length_um
            right_x1 = center_x + half_gap
            right_x2 = right_x1 + spec.electrode_length_um
            cad.add_box_um(spec.array_cell, spec.layer_name, left_x1, -half_electrode_w, left_x2, half_electrode_w)
            cad.add_box_um(spec.array_cell, spec.layer_name, right_x1, -half_electrode_w, right_x2, half_electrode_w)

            marker_y = spec.marker_offset_y_um
            marker_start_x = center_x - ((index + 1) - 1) * spec.marker_box_pitch_um / 2
            for marker_index in range(index + 1):
                marker_x = marker_start_x + marker_index * spec.marker_box_pitch_um
                cad.add_box_um(
                    spec.array_cell,
                    spec.marker_layer_name,
                    marker_x - half_marker,
                    marker_y - half_marker,
                    marker_x + half_marker,
                    marker_y + half_marker,
                )

        cad.add_instance_um(spec.root_cell, spec.array_cell, 0, 0)

    def _build_srr_feedline(self, cad: CADHarness) -> None:
        spec = self.spec
        assert isinstance(spec, SRRFeedlineLayoutSpec)
        cad.create_cell(spec.root_cell)
        cad.create_cell(spec.srr_cell)
        cad.add_frame_um(spec.root_cell, spec.layer_name, spec.root_width_um, spec.root_height_um, spec.frame_width_um)

        y0 = spec.vertical_offset_um
        half_outer = spec.srr_outer_size_um / 2
        half_inner = spec.srr_inner_size_um / 2
        half_gap = spec.capacitive_gap_um / 2

        # SRR: square ring represented as closed rectangular conductors, with a top capacitive gap.
        cad.add_box_um(spec.srr_cell, spec.layer_name, -half_outer, y0 + half_inner, -half_gap, y0 + half_outer)
        cad.add_box_um(spec.srr_cell, spec.layer_name, half_gap, y0 + half_inner, half_outer, y0 + half_outer)
        cad.add_box_um(spec.srr_cell, spec.layer_name, -half_outer, y0 - half_outer, half_outer, y0 - half_inner)
        cad.add_box_um(spec.srr_cell, spec.layer_name, -half_outer, y0 - half_inner, -half_inner, y0 + half_inner)
        cad.add_box_um(spec.srr_cell, spec.layer_name, half_inner, y0 - half_inner, half_outer, y0 + half_inner)

        feed_top = y0 - half_outer - spec.srr_feedline_gap_um
        feed_bottom = feed_top - spec.feedline_width_um
        cad.add_box_um(
            spec.srr_cell,
            spec.layer_name,
            -spec.feedline_length_um / 2,
            feed_bottom,
            spec.feedline_length_um / 2,
            feed_top,
        )

        ground_top = feed_bottom - spec.feedline_ground_gap_um
        ground_bottom = ground_top - spec.ground_height_um
        cad.add_box_um(
            spec.srr_cell,
            spec.layer_name,
            -spec.ground_width_um / 2,
            ground_bottom,
            spec.ground_width_um / 2,
            ground_top,
        )
        cad.add_instance_um(spec.root_cell, spec.srr_cell, 0, 0)

    def output_path(self, directory: str | Path) -> Path:
        return Path(directory) / f"{self.spec.root_cell}.gds"

    def equivalent_python_code(self, output_path: str | Path) -> str:
        spec = self.spec
        if isinstance(spec, HallBarLayoutSpec):
            return self._hall_bar_python_code(output_path)
        if isinstance(spec, NanoGapArrayLayoutSpec):
            return self._nanogap_array_python_code(output_path)
        if isinstance(spec, SRRFeedlineLayoutSpec):
            return self._srr_feedline_python_code(output_path)
        if isinstance(spec, MicroChannelLayoutSpec):
            return self._micro_channel_python_code(output_path)
        assert isinstance(spec, ElectrodeLayoutSpec)
        return f'''import klayout.db as kdb

dbu_um = {spec.rules.dbu_um!r}
layout = kdb.Layout()
layout.dbu = dbu_um
layer = layout.layer({spec.layer}, {spec.datatype})
root = layout.create_cell("{spec.root_cell}")
unit = layout.create_cell("{spec.unit_cell}")

def dbu(value_um):
    return int(round(value_um / dbu_um))

half_root_w = {spec.root_width_um!r} / 2
half_root_h = {spec.root_height_um!r} / 2
stroke = {spec.frame_width_um!r}
root.shapes(layer).insert(kdb.Box(dbu(-half_root_w), dbu(-half_root_h), dbu(half_root_w), dbu(-half_root_h + stroke)))
root.shapes(layer).insert(kdb.Box(dbu(-half_root_w), dbu(half_root_h - stroke), dbu(half_root_w), dbu(half_root_h)))
root.shapes(layer).insert(kdb.Box(dbu(-half_root_w), dbu(-half_root_h + stroke), dbu(-half_root_w + stroke), dbu(half_root_h - stroke)))
root.shapes(layer).insert(kdb.Box(dbu(half_root_w - stroke), dbu(-half_root_h + stroke), dbu(half_root_w), dbu(half_root_h - stroke)))

half_electrode_w = {spec.electrode_width_um!r} / 2
half_electrode_h = {spec.electrode_length_um!r} / 2
unit.shapes(layer).insert(kdb.Box(dbu(-half_electrode_w), dbu(-half_electrode_h), dbu(half_electrode_w), dbu(half_electrode_h)))
root.insert(kdb.CellInstArray(unit.cell_index(), kdb.Trans(0, 0)))
layout.write(r"{Path(output_path)}")
'''

    def _hall_bar_python_code(self, output_path: str | Path) -> str:
        spec = self.spec
        assert isinstance(spec, HallBarLayoutSpec)
        return f'''import klayout.db as kdb

dbu_um = {spec.rules.dbu_um!r}
layout = kdb.Layout()
layout.dbu = dbu_um
layer = layout.layer({spec.layer}, {spec.datatype})
root = layout.create_cell("{spec.root_cell}")
hall = layout.create_cell("{spec.hall_cell}")

def dbu(value_um):
    return int(round(value_um / dbu_um))

def add_box(cell, x1, y1, x2, y2):
    cell.shapes(layer).insert(kdb.Box(dbu(x1), dbu(y1), dbu(x2), dbu(y2)))

half_channel = {spec.channel_length_um!r} / 2
half_channel_width = {spec.channel_width_um!r} / 2
half_pad = {spec.bonding_pad_size_um!r} / 2
half_voltage = {spec.voltage_lead_width_um!r} / 2
half_spacing = {spec.voltage_probe_spacing_um!r} / 2
half_root_w = {spec.root_width_um!r} / 2
half_root_h = {spec.root_height_um!r} / 2
stroke = {spec.frame_width_um!r}
add_box(root, -half_root_w, -half_root_h, half_root_w, -half_root_h + stroke)
add_box(root, -half_root_w, half_root_h - stroke, half_root_w, half_root_h)
add_box(root, -half_root_w, -half_root_h + stroke, -half_root_w + stroke, half_root_h - stroke)
add_box(root, half_root_w - stroke, -half_root_h + stroke, half_root_w, half_root_h - stroke)

add_box(hall, -half_channel, -half_channel_width, half_channel, half_channel_width)
add_box(hall, -half_channel - {spec.current_lead_length_um!r}, -half_channel_width, -half_channel, half_channel_width)
add_box(hall, half_channel, -half_channel_width, half_channel + {spec.current_lead_length_um!r}, half_channel_width)
left_pad_cx = -half_channel - {spec.current_lead_length_um!r} - half_pad
right_pad_cx = half_channel + {spec.current_lead_length_um!r} + half_pad
add_box(hall, left_pad_cx - half_pad, -half_pad, left_pad_cx + half_pad, half_pad)
add_box(hall, right_pad_cx - half_pad, -half_pad, right_pad_cx + half_pad, half_pad)
for x in (-half_spacing, half_spacing):
    for direction in (-1, 1):
        y1 = direction * half_channel_width
        y2 = direction * (half_channel_width + {spec.voltage_lead_length_um!r})
        add_box(hall, x - half_voltage, min(y1, y2), x + half_voltage, max(y1, y2))
        pad_cy = direction * (half_channel_width + {spec.voltage_lead_length_um!r} + half_pad)
        add_box(hall, x - half_pad, pad_cy - half_pad, x + half_pad, pad_cy + half_pad)
root.insert(kdb.CellInstArray(hall.cell_index(), kdb.Trans(0, 0)))
layout.write(r"{Path(output_path)}")
'''

    def _micro_channel_python_code(self, output_path: str | Path) -> str:
        spec = self.spec
        assert isinstance(spec, MicroChannelLayoutSpec)
        return f'''import klayout.db as kdb

dbu_um = {spec.rules.dbu_um!r}
layout = kdb.Layout()
layout.dbu = dbu_um
layer = layout.layer({spec.layer}, {spec.datatype})
root = layout.create_cell("{spec.root_cell}")
channel = layout.create_cell("{spec.channel_cell}")

def dbu(value_um):
    return int(round(value_um / dbu_um))

def add_box(cell, x1, y1, x2, y2):
    cell.shapes(layer).insert(kdb.Box(dbu(x1), dbu(y1), dbu(x2), dbu(y2)))

half_root_w = {spec.root_width_um!r} / 2
half_root_h = {spec.root_height_um!r} / 2
stroke = {spec.frame_width_um!r}
add_box(root, -half_root_w, -half_root_h, half_root_w, -half_root_h + stroke)
add_box(root, -half_root_w, half_root_h - stroke, half_root_w, half_root_h)
add_box(root, -half_root_w, -half_root_h + stroke, -half_root_w + stroke, half_root_h - stroke)
add_box(root, half_root_w - stroke, -half_root_h + stroke, half_root_w, half_root_h - stroke)

half_lane = {spec.lane_length_um!r} / 2
half_width = {spec.channel_width_um!r} / 2
first_y = -(({spec.lane_count} - 1) * {spec.channel_pitch_um!r}) / 2
lane_ys = [first_y + index * {spec.channel_pitch_um!r} for index in range({spec.lane_count})]
for y in lane_ys:
    add_box(channel, -half_lane, y - half_width, half_lane, y + half_width)
for index in range({spec.lane_count} - 1):
    connector_x = half_lane if index % 2 == 0 else -half_lane
    y1 = min(lane_ys[index], lane_ys[index + 1]) - half_width
    y2 = max(lane_ys[index], lane_ys[index + 1]) + half_width
    add_box(channel, connector_x - half_width, y1, connector_x + half_width, y2)
add_box(channel, -half_lane - {spec.port_size_um!r}, lane_ys[0] - {spec.port_size_um!r} / 2, -half_lane, lane_ys[0] + {spec.port_size_um!r} / 2)
add_box(channel, half_lane, lane_ys[-1] - {spec.port_size_um!r} / 2, half_lane + {spec.port_size_um!r}, lane_ys[-1] + {spec.port_size_um!r} / 2)
root.insert(kdb.CellInstArray(channel.cell_index(), kdb.Trans(0, 0)))
layout.write(r"{Path(output_path)}")
'''

    def _nanogap_array_python_code(self, output_path: str | Path) -> str:
        spec = self.spec
        assert isinstance(spec, NanoGapArrayLayoutSpec)
        return f'''import klayout.db as kdb

dbu_um = {spec.rules.dbu_um!r}
layout = kdb.Layout()
layout.dbu = dbu_um
electrode_layer = layout.layer({spec.layer}, {spec.datatype})
marker_layer = layout.layer({spec.marker_layer}, {spec.marker_datatype})
root = layout.create_cell("{spec.root_cell}")
array = layout.create_cell("{spec.array_cell}")

def dbu(value_um):
    return int(round(value_um / dbu_um))

def add_box(cell, layer, x1, y1, x2, y2):
    cell.shapes(layer).insert(kdb.Box(dbu(x1), dbu(y1), dbu(x2), dbu(y2)))

half_root_w = {spec.root_width_um!r} / 2
half_root_h = {spec.root_height_um!r} / 2
stroke = {spec.frame_width_um!r}
add_box(root, electrode_layer, -half_root_w, -half_root_h, half_root_w, -half_root_h + stroke)
add_box(root, electrode_layer, -half_root_w, half_root_h - stroke, half_root_w, half_root_h)
add_box(root, electrode_layer, -half_root_w, -half_root_h + stroke, -half_root_w + stroke, half_root_h - stroke)
add_box(root, electrode_layer, half_root_w - stroke, -half_root_h + stroke, half_root_w, half_root_h - stroke)

gaps_um = {list(spec.gaps_um)!r}
max_device_width_um = {spec.max_device_width_um!r}
array_width_um = {spec.array_width_um!r}
start_x = -array_width_um / 2 + max_device_width_um / 2
half_electrode_w = {spec.electrode_width_um!r} / 2
half_marker = {spec.marker_box_size_um!r} / 2
for index, gap_um in enumerate(gaps_um):
    center_x = start_x + index * (max_device_width_um + {spec.device_spacing_um!r})
    half_gap = gap_um / 2
    add_box(array, electrode_layer, center_x - half_gap - {spec.electrode_length_um!r}, -half_electrode_w, center_x - half_gap, half_electrode_w)
    add_box(array, electrode_layer, center_x + half_gap, -half_electrode_w, center_x + half_gap + {spec.electrode_length_um!r}, half_electrode_w)
    marker_start_x = center_x - ((index + 1) - 1) * {spec.marker_box_pitch_um!r} / 2
    for marker_index in range(index + 1):
        marker_x = marker_start_x + marker_index * {spec.marker_box_pitch_um!r}
        add_box(array, marker_layer, marker_x - half_marker, {spec.marker_offset_y_um!r} - half_marker, marker_x + half_marker, {spec.marker_offset_y_um!r} + half_marker)
root.insert(kdb.CellInstArray(array.cell_index(), kdb.Trans(0, 0)))
layout.write(r"{Path(output_path)}")
'''

    def _srr_feedline_python_code(self, output_path: str | Path) -> str:
        spec = self.spec
        assert isinstance(spec, SRRFeedlineLayoutSpec)
        return f'''import klayout.db as kdb

dbu_um = {spec.rules.dbu_um!r}
layout = kdb.Layout()
layout.dbu = dbu_um
layer = layout.layer({spec.layer}, {spec.datatype})
root = layout.create_cell("{spec.root_cell}")
srr = layout.create_cell("{spec.srr_cell}")

def dbu(value_um):
    return int(round(value_um / dbu_um))

def add_box(cell, x1, y1, x2, y2):
    cell.shapes(layer).insert(kdb.Box(dbu(x1), dbu(y1), dbu(x2), dbu(y2)))

half_root_w = {spec.root_width_um!r} / 2
half_root_h = {spec.root_height_um!r} / 2
stroke = {spec.frame_width_um!r}
add_box(root, -half_root_w, -half_root_h, half_root_w, -half_root_h + stroke)
add_box(root, -half_root_w, half_root_h - stroke, half_root_w, half_root_h)
add_box(root, -half_root_w, -half_root_h + stroke, -half_root_w + stroke, half_root_h - stroke)
add_box(root, half_root_w - stroke, -half_root_h + stroke, half_root_w, half_root_h - stroke)

y0 = {spec.vertical_offset_um!r}
half_outer = {spec.srr_outer_size_um!r} / 2
half_inner = {spec.srr_inner_size_um!r} / 2
half_gap = {spec.capacitive_gap_um!r} / 2
add_box(srr, -half_outer, y0 + half_inner, -half_gap, y0 + half_outer)
add_box(srr, half_gap, y0 + half_inner, half_outer, y0 + half_outer)
add_box(srr, -half_outer, y0 - half_outer, half_outer, y0 - half_inner)
add_box(srr, -half_outer, y0 - half_inner, -half_inner, y0 + half_inner)
add_box(srr, half_inner, y0 - half_inner, half_outer, y0 + half_inner)

feed_top = y0 - half_outer - {spec.srr_feedline_gap_um!r}
feed_bottom = feed_top - {spec.feedline_width_um!r}
add_box(srr, -{spec.feedline_length_um!r} / 2, feed_bottom, {spec.feedline_length_um!r} / 2, feed_top)
ground_top = feed_bottom - {spec.feedline_ground_gap_um!r}
ground_bottom = ground_top - {spec.ground_height_um!r}
add_box(srr, -{spec.ground_width_um!r} / 2, ground_bottom, {spec.ground_width_um!r} / 2, ground_top)
root.insert(kdb.CellInstArray(srr.cell_index(), kdb.Trans(0, 0)))
layout.write(r"{Path(output_path)}")
'''


def _extra_layers(spec: LayoutSpec) -> dict:
    if isinstance(spec, NanoGapArrayLayoutSpec):
        return {
            spec.marker_layer_name: {
                "layer": spec.marker_layer,
                "datatype": spec.marker_datatype,
            }
        }
    return {}

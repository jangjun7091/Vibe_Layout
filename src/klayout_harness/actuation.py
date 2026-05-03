from __future__ import annotations

from pathlib import Path

from .cad import CADHarness
from .context import DesignContext
from .semantic import ElectrodeLayoutSpec, LayoutSpec, MicroChannelLayoutSpec


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
                    }
                },
                "parameters": {},
                "rules": {
                    "min_width_um": self.spec.rules.minimum_resolution_um,
                    "min_spacing_um": self.spec.rules.minimum_resolution_um,
                },
            }
        )

    def build(self, cad: CADHarness) -> None:
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

    def output_path(self, directory: str | Path) -> Path:
        return Path(directory) / f"{self.spec.root_cell}.gds"

    def equivalent_python_code(self, output_path: str | Path) -> str:
        spec = self.spec
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

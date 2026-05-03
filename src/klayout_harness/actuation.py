from __future__ import annotations

from pathlib import Path

from .cad import CADHarness
from .context import DesignContext
from .semantic import ElectrodeLayoutSpec


class ToolActuationHarness:
    def __init__(self, spec: ElectrodeLayoutSpec) -> None:
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
        spec = self.spec
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

    def output_path(self, directory: str | Path) -> Path:
        return Path(directory) / f"{self.spec.root_cell}.gds"

    def equivalent_python_code(self, output_path: str | Path) -> str:
        spec = self.spec
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

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from .context import DesignContext, LayerSpec


@dataclass(frozen=True)
class BoxOp:
    cell: str
    layer: LayerSpec
    x1: int
    y1: int
    x2: int
    y2: int


@dataclass(frozen=True)
class TextOp:
    cell: str
    layer: LayerSpec
    text: str
    x: int
    y: int


@dataclass(frozen=True)
class InstanceOp:
    parent_cell: str
    child_cell: str
    x: int
    y: int


class CADBackend(Protocol):
    def create_cell(self, name: str) -> None: ...

    def add_box(self, op: BoxOp) -> None: ...

    def add_text(self, op: TextOp) -> None: ...

    def add_instance(self, op: InstanceOp) -> None: ...

    def write_gds(self, path: str | Path) -> Path: ...


@dataclass
class RecordingBackend:
    cells: set[str] = field(default_factory=set)
    boxes: list[BoxOp] = field(default_factory=list)
    texts: list[TextOp] = field(default_factory=list)
    instances: list[InstanceOp] = field(default_factory=list)
    written_path: Path | None = None

    def create_cell(self, name: str) -> None:
        self.cells.add(name)

    def add_box(self, op: BoxOp) -> None:
        self.cells.add(op.cell)
        self.boxes.append(op)

    def add_text(self, op: TextOp) -> None:
        self.cells.add(op.cell)
        self.texts.append(op)

    def add_instance(self, op: InstanceOp) -> None:
        self.cells.add(op.parent_cell)
        self.cells.add(op.child_cell)
        self.instances.append(op)

    def write_gds(self, path: str | Path) -> Path:
        self.written_path = Path(path)
        return self.written_path


class KLayoutBackend:
    def __init__(self, context: DesignContext) -> None:
        self.context = context
        self.kdb = _import_klayout()
        self.layout = self.kdb.Layout()
        self.layout.dbu = context.dbu_um
        self.cells: dict[str, object] = {}

    def create_cell(self, name: str) -> None:
        if name not in self.cells:
            self.cells[name] = self.layout.create_cell(name)

    def add_box(self, op: BoxOp) -> None:
        cell = self._cell(op.cell)
        layer_index = self.layout.layer(op.layer.layer, op.layer.datatype)
        box = self.kdb.Box(op.x1, op.y1, op.x2, op.y2)
        cell.shapes(layer_index).insert(box)

    def add_text(self, op: TextOp) -> None:
        cell = self._cell(op.cell)
        layer_index = self.layout.layer(op.layer.layer, op.layer.datatype)
        text = self.kdb.Text(op.text, self.kdb.Trans(op.x, op.y))
        cell.shapes(layer_index).insert(text)

    def add_instance(self, op: InstanceOp) -> None:
        parent = self._cell(op.parent_cell)
        child = self._cell(op.child_cell)
        parent.insert(self.kdb.CellInstArray(child.cell_index(), self.kdb.Trans(op.x, op.y)))

    def write_gds(self, path: str | Path) -> Path:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        self.layout.write(str(output))
        return output

    def _cell(self, name: str):
        self.create_cell(name)
        return self.cells[name]


class CADHarness:
    def __init__(self, context: DesignContext, backend: CADBackend | None = None) -> None:
        self.context = context
        self.backend = backend if backend is not None else KLayoutBackend(context)

    def create_cell(self, name: str) -> None:
        self.backend.create_cell(name)

    def ensure_layer(self, name: str, layer: int, datatype: int = 0) -> None:
        self.context.layers[name] = LayerSpec(name=name, layer=layer, datatype=datatype)

    def add_box_um(
        self,
        cell: str,
        layer: str,
        x1_um: float,
        y1_um: float,
        x2_um: float,
        y2_um: float,
    ) -> None:
        op = BoxOp(
            cell=cell,
            layer=self.context.layer(layer),
            x1=self.context.dbu(x1_um),
            y1=self.context.dbu(y1_um),
            x2=self.context.dbu(x2_um),
            y2=self.context.dbu(y2_um),
        )
        self.backend.add_box(op)

    def add_text_um(self, cell: str, layer: str, text: str, x_um: float, y_um: float) -> None:
        op = TextOp(
            cell=cell,
            layer=self.context.layer(layer),
            text=text,
            x=self.context.dbu(x_um),
            y=self.context.dbu(y_um),
        )
        self.backend.add_text(op)

    def add_instance_um(self, parent_cell: str, child_cell: str, x_um: float, y_um: float) -> None:
        op = InstanceOp(
            parent_cell=parent_cell,
            child_cell=child_cell,
            x=self.context.dbu(x_um),
            y=self.context.dbu(y_um),
        )
        self.backend.add_instance(op)

    def add_centered_box_um(self, cell: str, layer: str, width_um: float, height_um: float) -> None:
        half_width = width_um / 2
        half_height = height_um / 2
        self.add_box_um(cell, layer, -half_width, -half_height, half_width, half_height)

    def add_frame_um(self, cell: str, layer: str, width_um: float, height_um: float, stroke_um: float) -> None:
        half_width = width_um / 2
        half_height = height_um / 2
        half_stroke = stroke_um / 2
        self.add_box_um(cell, layer, -half_width, -half_height, half_width, -half_height + stroke_um)
        self.add_box_um(cell, layer, -half_width, half_height - stroke_um, half_width, half_height)
        self.add_box_um(cell, layer, -half_width, -half_height + stroke_um, -half_width + stroke_um, half_height - stroke_um)
        self.add_box_um(cell, layer, half_width - stroke_um, -half_height + stroke_um, half_width, half_height - stroke_um)

    def write_gds(self, path: str | Path) -> Path:
        return self.backend.write_gds(path)


def _import_klayout():
    try:
        import klayout.db as kdb

        return kdb
    except ModuleNotFoundError:
        try:
            import pya

            return pya
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "KLayout Python bindings are not available. "
                "Install KLayout or inject a test backend."
            ) from exc

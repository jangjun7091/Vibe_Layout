from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LayerSpec:
    name: str
    layer: int
    datatype: int = 0


@dataclass(frozen=True)
class DesignContext:
    dbu_um: float
    layers: dict[str, LayerSpec]
    parameters: dict[str, Any]
    rules: dict[str, float]

    @classmethod
    def from_file(cls, path: str | Path) -> "DesignContext":
        data = _load_mapping(Path(path))
        return cls.from_mapping(data)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "DesignContext":
        dbu_um = float(data["dbu_um"])
        raw_layers = data.get("layers", {})
        layers = {
            name: LayerSpec(
                name=name,
                layer=int(spec["layer"]),
                datatype=int(spec.get("datatype", 0)),
            )
            for name, spec in raw_layers.items()
        }
        return cls(
            dbu_um=dbu_um,
            layers=layers,
            parameters=dict(data.get("parameters", {})),
            rules={name: float(value) for name, value in data.get("rules", {}).items()},
        )

    def dbu(self, value_um: float) -> int:
        return int(round(float(value_um) / self.dbu_um))

    def um(self, value_dbu: int) -> float:
        return int(value_dbu) * self.dbu_um

    def layer(self, name: str) -> LayerSpec:
        try:
            return self.layers[name]
        except KeyError as exc:
            raise KeyError(f"Unknown layer '{name}'") from exc

    def parameter(self, name: str) -> Any:
        try:
            return self.parameters[name]
        except KeyError as exc:
            raise KeyError(f"Unknown design parameter '{name}'") from exc

    def rule(self, name: str) -> float:
        try:
            return self.rules[name]
        except KeyError as exc:
            raise KeyError(f"Unknown rule '{name}'") from exc


def _load_mapping(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)

    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Loading YAML context files requires PyYAML. "
            "Install with: python -m pip install -e ."
        ) from exc

    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"Context file must contain a mapping: {path}")
    return data

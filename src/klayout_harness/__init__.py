"""Harness layers for KLayout design agents."""

from .agent import DesignAgent, IterationResult
from .cad import CADHarness, KLayoutBackend, RecordingBackend
from .context import DesignContext, LayerSpec
from .design_request import ElectrodeRequest, build_electrode_layout, parse_electrode_request
from .feedback import FeedbackHarness, ValidationFinding, ValidationReport

__all__ = [
    "CADHarness",
    "DesignAgent",
    "DesignContext",
    "ElectrodeRequest",
    "FeedbackHarness",
    "IterationResult",
    "KLayoutBackend",
    "LayerSpec",
    "RecordingBackend",
    "ValidationFinding",
    "ValidationReport",
    "build_electrode_layout",
    "parse_electrode_request",
]

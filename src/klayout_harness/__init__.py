"""Harness layers for KLayout design agents."""

from .agent import DesignAgent, IterationResult
from .actuation import ToolActuationHarness
from .cad import CADHarness, KLayoutBackend, RecordingBackend
from .context import DesignContext, LayerSpec
from .design_request import ElectrodeRequest, build_electrode_layout, parse_electrode_request
from .feedback import FeedbackHarness, ValidationFinding, ValidationReport
from .semantic import (
    ElectrodeLayoutSpec,
    FabricationRules,
    HallBarLayoutSpec,
    MicroChannelLayoutSpec,
    NanoGapArrayLayoutSpec,
    SRRFeedlineLayoutSpec,
    SemanticHarness,
)

__all__ = [
    "CADHarness",
    "DesignAgent",
    "DesignContext",
    "ElectrodeLayoutSpec",
    "ElectrodeRequest",
    "FabricationRules",
    "FeedbackHarness",
    "HallBarLayoutSpec",
    "IterationResult",
    "KLayoutBackend",
    "LayerSpec",
    "MicroChannelLayoutSpec",
    "NanoGapArrayLayoutSpec",
    "RecordingBackend",
    "SRRFeedlineLayoutSpec",
    "SemanticHarness",
    "ToolActuationHarness",
    "ValidationFinding",
    "ValidationReport",
    "build_electrode_layout",
    "parse_electrode_request",
]

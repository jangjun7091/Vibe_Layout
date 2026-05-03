"""Harness layers for KLayout design agents."""

from .agent import DesignAgent, IterationResult
from .cad import CADHarness, KLayoutBackend, RecordingBackend
from .context import DesignContext, LayerSpec
from .feedback import FeedbackHarness, ValidationFinding, ValidationReport

__all__ = [
    "CADHarness",
    "DesignAgent",
    "DesignContext",
    "FeedbackHarness",
    "IterationResult",
    "KLayoutBackend",
    "LayerSpec",
    "RecordingBackend",
    "ValidationFinding",
    "ValidationReport",
]

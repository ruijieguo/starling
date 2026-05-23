"""Starling extractor package (M0.4)."""
from starling import _core
from starling.extractor._keys import compute_extraction_span_key

# Re-export bound types
Extractor             = _core.Extractor
FakeLLMAdapter        = _core.FakeLLMAdapter
LLMResponse           = _core.LLMResponse
ExtractionRunResult   = _core.ExtractionRunResult
Perspective           = _core.Perspective
Modality              = _core.Modality
Polarity              = _core.Polarity
ReviewStatus          = _core.ReviewStatus
StatementProvenance   = _core.StatementProvenance

__all__ = [
    "compute_extraction_span_key",
    "Extractor",
    "FakeLLMAdapter",
    "LLMResponse",
    "ExtractionRunResult",
    "Perspective",
    "Modality",
    "Polarity",
    "ReviewStatus",
    "StatementProvenance",
]

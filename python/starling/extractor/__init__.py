"""Starling extractor package (M0.4+).

Extractor-related Python helpers (LLM adapter constructors).

C++ binding lives in starling._core; this package wraps env-var-aware
convenience constructors that should not bypass the controller's
secret-handling rules (no key ever printed or returned).
"""
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

# M0.7: OpenAIAdapter binding
OpenAIAdapterConfig   = _core.OpenAIAdapterConfig
OpenAIAdapter         = _core.OpenAIAdapter

# P2.l: AnthropicAdapter binding (native Messages API)
AnthropicAdapterConfig = _core.AnthropicAdapterConfig
AnthropicAdapter       = _core.AnthropicAdapter

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
    "OpenAIAdapterConfig",
    "OpenAIAdapter",
    "AnthropicAdapterConfig",
    "AnthropicAdapter",
]

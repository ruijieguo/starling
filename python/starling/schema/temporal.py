"""Temporal anchor and confidence-event value objects (M0.1)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from starling.schema.enums import AnchorKind


@dataclass(frozen=True, slots=True, kw_only=True)
class TemporalAnchor:
    anchor_kind: AnchorKind
    anchor_time: datetime
    timezone_name: str | None = None
    confidence: float
    resolved_by: Literal["metadata", "adapter", "llm", "fallback"]


@dataclass(frozen=True, slots=True, kw_only=True)
class ConfidenceEvent:
    old_value: float
    timestamp: datetime
    evidence_hash: str

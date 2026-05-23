"""Source-span reference (M0.1).

P1 minimum: engram_ref + chunk_index + observed_at + source_hash.
span_start/span_end/segment_id arrive in P3 (§3.3); the fields exist
here so Statement can hold them without breakage when M0.2 wires up
persistence."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from starling.schema.refs import EngramRef, CognizerRef


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceSpanRef:
    engram_ref: EngramRef
    chunk_index: int
    span_start: int | None = None
    span_end: int | None = None
    segment_id: str | None = None
    source_role: Literal["user", "assistant", "tool", "system", "document"] | None = None
    source_speaker: CognizerRef | None = None
    observed_at: datetime
    source_hash: str

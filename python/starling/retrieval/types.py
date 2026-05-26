"""Typed Python dataclasses mirroring _core retrieval bindings.

These exist so callers don't depend on the pybind class layout directly.
The wrapping is intentionally thin — no semantic transformation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class FilterApplied:
    name: str
    value: str


@dataclass(frozen=True)
class CandidateCounts:
    fetched: int
    returned: int
    dropped_by_review: int
    dropped_by_state: int
    dropped_by_time_anchor: int
    dropped_by_evidence_erasure: int


@dataclass(frozen=True)
class RetrievalReceipt:
    trace_id: str
    query_id: str
    filters_applied: List[FilterApplied]
    candidate_counts: CandidateCounts
    evidence_erased_count: int
    frontier_masked_count: int  # P2.a: rows filtered by apply_frontier_filter
    sufficiency_status: str  # SUFFICIENT | MISSING_INFO | NEEDS_RAW | ABSTAINED


@dataclass(frozen=True)
class StatementRow:
    id: str
    tenant_id: str
    holder_id: str
    holder_perspective: str
    subject_kind: str
    subject_id: str
    predicate: str
    object_kind: str
    object_value: str
    canonical_object_hash: str
    modality: str
    polarity: str
    confidence: float
    observed_at: str
    valid_from: str
    valid_to: str
    consolidation_state: str
    review_status: str
    evidence_json: str


@dataclass(frozen=True)
class BasicRetrieveResult:
    rows: List[StatementRow]
    receipt: RetrievalReceipt

"""Starling retrieval public API.

P1 ships exactly one entrypoint: `basic_retrieve`. See
docs/design/subsystems_design/13_retrieval.md §"basic_retrieve（P1 闭环）".
Future milestones will add a `Retrieval` class for 7-step planning.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, Union

from starling import _core
from starling.retrieval.types import (
    BasicRetrieveResult,
    CandidateCounts,
    FilterApplied,
    RetrievalReceipt,
    StatementRow,
)

__all__ = ["basic_retrieve", "BasicRetrieveResult", "RetrievalReceipt",
           "StatementRow", "FilterApplied", "CandidateCounts"]


_SUFFICIENCY_NAME = {
    _core.Sufficiency.SUFFICIENT:   "SUFFICIENT",
    _core.Sufficiency.MISSING_INFO: "MISSING_INFO",
    _core.Sufficiency.NEEDS_RAW:    "NEEDS_RAW",
    _core.Sufficiency.ABSTAINED:    "ABSTAINED",
}


def basic_retrieve(
    adapter,
    *,
    tenant_id: str,
    holder: Union[str, list, tuple],     # accept list/tuple only to reject
    holder_perspective: Optional[str] = None,
    intent: str = "FACT_LOOKUP",
    subject: str,
    predicate: str,
    as_of: datetime,
    trace_id: Optional[str] = None,
    query_id: Optional[str] = None,
    apply_frontier_filter: bool = False,
) -> BasicRetrieveResult:
    """The P1 retrieval entrypoint.

    Returns the list of statements that match the predicate at `as_of`,
    filtered by:
      - consolidation_state in {consolidated, archived}
      - review_status not in {rejected, pending_review}
      - evidence not crypto-erased
      - valid_from <= as_of < valid_to
      - holder_perspective = <given> when supplied; otherwise unconstrained
      - (P2.a) when apply_frontier_filter=True: only statements whose
        evidence engrams are visible to holder per KnowledgeFrontier

    The receipt's `filters_applied` always records `holder_perspective`
    ("any" when unconstrained, the bound value otherwise) per
    13_retrieval.md:291.  Also records `frontier_applied` and
    `frontier_masked_count` (added in P2.a; always present).

    Multi-holder calls raise ValueError; intent other than FACT_LOOKUP raises
    ValueError. See 13_retrieval.md §"P1 basic_retrieve 闭环".
    """
    if isinstance(holder, (list, tuple)):
        raise ValueError(
            "basic_retrieve: multi-holder is not supported in P1; "
            "pass a single holder string. "
            "See 13_retrieval.md §'P1 basic_retrieve 闭环'."
        )
    if not isinstance(holder, str) or not holder:
        raise ValueError("basic_retrieve: holder must be a non-empty string")
    if not tenant_id:
        raise ValueError("basic_retrieve: tenant_id is required")
    if intent != "FACT_LOOKUP":
        raise ValueError(
            f"basic_retrieve: intent={intent} not supported in P1; "
            "only FACT_LOOKUP is implemented."
        )
    if not subject or not predicate:
        raise ValueError("basic_retrieve: subject and predicate are required")
    if as_of.tzinfo is None:
        raise ValueError("basic_retrieve: as_of must be timezone-aware")

    as_of_utc = as_of.astimezone(timezone.utc)
    as_of_iso = as_of_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    params = _core.BasicRetrieverParams()
    params.tenant_id              = tenant_id
    params.holder_id              = holder
    params.holder_perspective     = holder_perspective or ""
    params.intent                 = _core.QueryIntent.FACT_LOOKUP
    params.subject_id             = subject
    params.predicate              = predicate
    params.as_of_iso8601          = as_of_iso
    params.trace_id               = trace_id or str(uuid.uuid4())
    params.query_id               = query_id or str(uuid.uuid4())
    params.apply_frontier_filter  = apply_frontier_filter

    r = _core.BasicRetriever(adapter)
    raw = r.run(params)

    counts = CandidateCounts(
        fetched=raw.receipt.candidate_counts.fetched,
        returned=raw.receipt.candidate_counts.returned,
        dropped_by_review=raw.receipt.candidate_counts.dropped_by_review,
        dropped_by_state=raw.receipt.candidate_counts.dropped_by_state,
        dropped_by_time_anchor=raw.receipt.candidate_counts.dropped_by_time_anchor,
        dropped_by_evidence_erasure=raw.receipt.candidate_counts.dropped_by_evidence_erasure,
    )
    receipt = RetrievalReceipt(
        trace_id=raw.receipt.trace_id,
        query_id=raw.receipt.query_id,
        filters_applied=[FilterApplied(name=f.name, value=f.value)
                          for f in raw.receipt.filters_applied],
        candidate_counts=counts,
        evidence_erased_count=raw.receipt.evidence_erased_count,
        frontier_masked_count=raw.receipt.frontier_masked_count,
        sufficiency_status=_SUFFICIENCY_NAME[raw.receipt.sufficiency_status],
    )
    rows = [StatementRow(
        id=r_.id, tenant_id=r_.tenant_id, holder_id=r_.holder_id,
        holder_perspective=r_.holder_perspective,
        subject_kind=r_.subject_kind, subject_id=r_.subject_id,
        predicate=r_.predicate, object_kind=r_.object_kind,
        object_value=r_.object_value,
        canonical_object_hash=r_.canonical_object_hash,
        modality=r_.modality, polarity=r_.polarity,
        confidence=r_.confidence, observed_at=r_.observed_at,
        valid_from=r_.valid_from, valid_to=r_.valid_to,
        consolidation_state=r_.consolidation_state,
        review_status=r_.review_status,
        evidence_json=r_.evidence_json,
    ) for r_ in raw.rows]
    return BasicRetrieveResult(rows=rows, receipt=receipt)

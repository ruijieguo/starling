from datetime import datetime, timezone
import pytest
from starling.schema.temporal import TemporalAnchor, ConfidenceEvent
from starling.schema.enums import AnchorKind


def test_anchor_frozen():
    a = TemporalAnchor(
        anchor_kind=AnchorKind.SOURCE_SPAN,
        anchor_time=datetime(2026, 5, 23, tzinfo=timezone.utc),
        confidence=0.9,
        resolved_by="metadata",
    )
    with pytest.raises(Exception):
        a.confidence = 0.5  # type: ignore[misc]


def test_confidence_event_carries_old_value():
    ev = ConfidenceEvent(
        old_value=0.7,
        timestamp=datetime(2026, 5, 23, tzinfo=timezone.utc),
        evidence_hash="abc123",
    )
    assert ev.old_value == 0.7

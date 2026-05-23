from datetime import datetime, timezone
import uuid
from starling.schema.engram import Engram, SourceRef
from starling.schema.enums import (
    SourceKind, IngestPolicy, IngestMode, PrivacyClass, EngramRetentionMode,
)


def _make_engram(retention: EngramRetentionMode) -> Engram:
    return Engram(
        id=uuid.uuid4(),
        source=SourceRef(id=uuid.uuid4(), name="conversation:42"),
        source_kind=SourceKind.USER_INPUT,
        ingest_policy=IngestPolicy.STORE,
        ingest_mode=IngestMode.CHUNKED_CONTENT,
        privacy_class=PrivacyClass.INTERNAL,
        byte_preserving=False,
        content_hash="a" * 64,
        retention_mode=retention,
        chunk_index=0,
        timestamp=datetime(2026, 5, 23, tzinfo=timezone.utc),
    )


def test_engram_legal_hold_constructs():
    e = _make_engram(EngramRetentionMode.LEGAL_HOLD)
    assert e.retention_mode == EngramRetentionMode.LEGAL_HOLD


def test_engram_segment_map_empty_at_p1():
    e = _make_engram(EngramRetentionMode.AUDIT_RETAIN)
    assert e.segment_map == ()

from datetime import datetime, timezone

from starling._core import (
    SourceKind, IngestMode, PrivacyClass, EngramRetentionMode,
)
from starling.evidence import (
    for_user_input, for_system_internal, for_tool_observation,
)


def test_for_user_input_defaults():
    inp = for_user_input(
        tenant_id="t1", adapter_name="direct_api", adapter_version="1.0.0",
        source_item_id="msg-1", source_version="1",
        payload_bytes=b"hello",
        privacy_class=PrivacyClass.INTERNAL,
        retention_mode=EngramRetentionMode.AUDIT_RETAIN,
        created_at=datetime(2026, 5, 23, 10, 0, tzinfo=timezone.utc),
    )
    assert inp.source_kind == SourceKind.USER_INPUT
    assert inp.ingest_mode == IngestMode.WHOLE_RECORD
    assert inp.byte_preserving is True
    assert inp.source.chunk_index == 0
    assert inp.created_at_iso8601 == "2026-05-23T10:00:00Z"


def test_for_system_internal_uses_metadata_only_default():
    inp = for_system_internal(
        tenant_id="t1", adapter_name="retrieval_planner", adapter_version="0.1.0",
        source_item_id="receipt-1", source_version="1",
        payload_bytes=b"trace",
        privacy_class=PrivacyClass.INTERNAL,
        retention_mode=EngramRetentionMode.AUDIT_RETAIN,
        created_at=datetime(2026, 5, 23, 10, 0, tzinfo=timezone.utc),
    )
    assert inp.source_kind == SourceKind.SYSTEM_INTERNAL
    assert inp.ingest_mode == IngestMode.METADATA_ONLY
    assert inp.byte_preserving is False


def test_for_tool_observation_defaults():
    inp = for_tool_observation(
        tenant_id="t1", adapter_name="weather_api", adapter_version="2",
        source_item_id="q-1", source_version="1",
        payload_bytes=b'{"temp":72}',
        privacy_class=PrivacyClass.PUBLIC,
        retention_mode=EngramRetentionMode.AUDIT_RETAIN,
        created_at=datetime(2026, 5, 23, 10, 0, tzinfo=timezone.utc),
    )
    assert inp.source_kind == SourceKind.TOOL_OBSERVATION
    assert inp.ingest_mode == IngestMode.METADATA_ONLY

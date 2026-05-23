"""Confirm IngestPolicyResolver behavior is identical from Python and C++."""

from datetime import datetime, timezone

from starling._core import (
    IngestPolicy, IngestPolicyResolver, PrivacyClass, SourceKind,
)
from starling import _core
from starling.bus.append_evidence import BusFacade
from starling.evidence import (
    for_user_input, for_system_internal,
    PrivacyClass as EvidencePrivacyClass,
    EngramRetentionMode,
)


def test_system_internal_always_no_store_from_python():
    for privacy in PrivacyClass.__members__.values():
        for declared in IngestPolicy.__members__.values():
            assert IngestPolicyResolver.resolve(
                SourceKind.SYSTEM_INTERNAL, privacy, declared
            ) == IngestPolicy.NO_STORE


def test_user_input_regulated_downgrades():
    assert IngestPolicyResolver.resolve(
        SourceKind.USER_INPUT, PrivacyClass.REGULATED, IngestPolicy.STORE
    ) == IngestPolicy.REQUIRE_REVIEW


def test_tool_observation_always_metadata_only_on_store():
    assert IngestPolicyResolver.resolve(
        SourceKind.TOOL_OBSERVATION, PrivacyClass.PUBLIC, IngestPolicy.STORE
    ) == IngestPolicy.STORE_METADATA_ONLY


# ----- BusFacade end-to-end smoke -----

def test_bus_facade_accepted_path_returns_accepted_dict():
    adapter = _core.SqliteAdapter.open(":memory:")
    bus = BusFacade(adapter)
    inp = for_user_input(
        tenant_id="t1", adapter_name="direct_api", adapter_version="1.0.0",
        source_item_id="msg-1", source_version="1",
        payload_bytes=b"hello",
        privacy_class=EvidencePrivacyClass.INTERNAL,
        retention_mode=EngramRetentionMode.AUDIT_RETAIN,
        created_at=datetime(2026, 5, 23, 10, 0, tzinfo=timezone.utc),
    )
    outcome = bus.append_evidence(inp)
    assert outcome["kind"] == "accepted"
    assert outcome["engram_ref"].id  # non-empty UUIDv4
    assert outcome["outbox_sequence"] >= 1


def test_bus_facade_no_store_path_returns_no_store_dict():
    adapter = _core.SqliteAdapter.open(":memory:")
    bus = BusFacade(adapter)
    inp = for_system_internal(
        tenant_id="t1", adapter_name="retrieval_planner", adapter_version="0.1.0",
        source_item_id="receipt-1", source_version="1",
        payload_bytes=b"trace",
        privacy_class=EvidencePrivacyClass.INTERNAL,
        retention_mode=EngramRetentionMode.AUDIT_RETAIN,
        created_at=datetime(2026, 5, 23, 10, 0, tzinfo=timezone.utc),
    )
    outcome = bus.append_evidence(inp)
    assert outcome["kind"] == "no_store"
    assert outcome["audit_event_id"]

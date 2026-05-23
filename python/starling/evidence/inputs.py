"""EngramInput builder helpers (M0.3).

Construct EngramInput instances with the right source_kind preset. Callers
pass the adapter identity tuple + payload + retention; the helpers fill in
the rest with safe defaults.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from starling import _core


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _build(
    *,
    tenant_id: str,
    adapter_name: str,
    adapter_version: str,
    source_item_id: str,
    source_version: str,
    chunk_index: int,
    source_kind,
    ingest_mode,
    privacy_class,
    retention_mode,
    payload_bytes: bytes,
    declared_transformations: tuple[str, ...],
    byte_preserving: bool,
    redacted_content: Optional[str],
    created_at: datetime,
) -> "_core.EngramInput":
    inp = _core.EngramInput()
    inp.tenant_id = tenant_id
    src = _core.SourceIdentity()
    src.adapter_name = adapter_name
    src.adapter_version = adapter_version
    src.source_item_id = source_item_id
    src.source_version = source_version
    src.chunk_index = chunk_index
    inp.source = src
    inp.source_kind = source_kind
    inp.ingest_mode = ingest_mode
    inp.privacy_class = privacy_class
    inp.retention_mode = retention_mode
    inp.declared_transformations = list(declared_transformations)
    inp.byte_preserving = byte_preserving
    inp.payload_bytes = list(payload_bytes)
    inp.redacted_content = redacted_content
    inp.created_at_iso8601 = _iso(created_at)
    return inp


def for_user_input(*, tenant_id, adapter_name, adapter_version, source_item_id,
                   source_version, payload_bytes, privacy_class, retention_mode,
                   created_at, chunk_index=0, declared_transformations=(),
                   byte_preserving=True, redacted_content=None):
    return _build(
        tenant_id=tenant_id, adapter_name=adapter_name, adapter_version=adapter_version,
        source_item_id=source_item_id, source_version=source_version,
        chunk_index=chunk_index, source_kind=_core.SourceKind.USER_INPUT,
        ingest_mode=_core.IngestMode.WHOLE_RECORD, privacy_class=privacy_class,
        retention_mode=retention_mode, payload_bytes=payload_bytes,
        declared_transformations=declared_transformations,
        byte_preserving=byte_preserving, redacted_content=redacted_content,
        created_at=created_at,
    )


def for_external_doc(*, tenant_id, adapter_name, adapter_version, source_item_id,
                     source_version, payload_bytes, privacy_class, retention_mode,
                     created_at, chunk_index=0, declared_transformations=(),
                     byte_preserving=True, redacted_content=None):
    return _build(
        tenant_id=tenant_id, adapter_name=adapter_name, adapter_version=adapter_version,
        source_item_id=source_item_id, source_version=source_version,
        chunk_index=chunk_index, source_kind=_core.SourceKind.EXTERNAL_DOC,
        ingest_mode=_core.IngestMode.WHOLE_RECORD, privacy_class=privacy_class,
        retention_mode=retention_mode, payload_bytes=payload_bytes,
        declared_transformations=declared_transformations,
        byte_preserving=byte_preserving, redacted_content=redacted_content,
        created_at=created_at,
    )


def for_tool_observation(*, tenant_id, adapter_name, adapter_version, source_item_id,
                         source_version, payload_bytes, privacy_class, retention_mode,
                         created_at, chunk_index=0, declared_transformations=(),
                         byte_preserving=False, redacted_content=None):
    return _build(
        tenant_id=tenant_id, adapter_name=adapter_name, adapter_version=adapter_version,
        source_item_id=source_item_id, source_version=source_version,
        chunk_index=chunk_index, source_kind=_core.SourceKind.TOOL_OBSERVATION,
        ingest_mode=_core.IngestMode.METADATA_ONLY, privacy_class=privacy_class,
        retention_mode=retention_mode, payload_bytes=payload_bytes,
        declared_transformations=declared_transformations,
        byte_preserving=byte_preserving, redacted_content=redacted_content,
        created_at=created_at,
    )


def for_system_internal(*, tenant_id, adapter_name, adapter_version, source_item_id,
                        source_version, payload_bytes, privacy_class, retention_mode,
                        created_at, chunk_index=0, declared_transformations=(),
                        byte_preserving=False, redacted_content=None):
    return _build(
        tenant_id=tenant_id, adapter_name=adapter_name, adapter_version=adapter_version,
        source_item_id=source_item_id, source_version=source_version,
        chunk_index=chunk_index, source_kind=_core.SourceKind.SYSTEM_INTERNAL,
        ingest_mode=_core.IngestMode.METADATA_ONLY, privacy_class=privacy_class,
        retention_mode=retention_mode, payload_bytes=payload_bytes,
        declared_transformations=declared_transformations,
        byte_preserving=byte_preserving, redacted_content=redacted_content,
        created_at=created_at,
    )


def for_observer_agent(*, tenant_id, adapter_name, adapter_version, source_item_id,
                       source_version, payload_bytes, privacy_class, retention_mode,
                       created_at, chunk_index=0, declared_transformations=(),
                       byte_preserving=False, redacted_content=None):
    return _build(
        tenant_id=tenant_id, adapter_name=adapter_name, adapter_version=adapter_version,
        source_item_id=source_item_id, source_version=source_version,
        chunk_index=chunk_index, source_kind=_core.SourceKind.OBSERVER_AGENT,
        ingest_mode=_core.IngestMode.METADATA_ONLY, privacy_class=privacy_class,
        retention_mode=retention_mode, payload_bytes=payload_bytes,
        declared_transformations=declared_transformations,
        byte_preserving=byte_preserving, redacted_content=redacted_content,
        created_at=created_at,
    )


def for_replay_output(*, tenant_id, adapter_name, adapter_version, source_item_id,
                      source_version, payload_bytes, privacy_class, retention_mode,
                      created_at, chunk_index=0, declared_transformations=(),
                      byte_preserving=False, redacted_content=None):
    return _build(
        tenant_id=tenant_id, adapter_name=adapter_name, adapter_version=adapter_version,
        source_item_id=source_item_id, source_version=source_version,
        chunk_index=chunk_index, source_kind=_core.SourceKind.REPLAY_OUTPUT,
        ingest_mode=_core.IngestMode.METADATA_ONLY, privacy_class=privacy_class,
        retention_mode=retention_mode, payload_bytes=payload_bytes,
        declared_transformations=declared_transformations,
        byte_preserving=byte_preserving, redacted_content=redacted_content,
        created_at=created_at,
    )

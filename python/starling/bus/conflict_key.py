from __future__ import annotations
import hashlib
from typing import Any

from starling.bus.normalized_interval import normalize_interval
from starling.bus.canonical_scope import canonical_scope_bytes, scope_of

_SEP = b'\x1f'

# All-caps spelling of every Modality enum value. Mirrors the C++
# canonical_conflict_key.cpp modality_str() switch so the hashes match
# byte-for-byte. Locked parity is asserted by tests/python/test_conflict_key.py
# (PARITY_HEX) and tests/cpp/test_conflict_key.cpp.
_MODALITY_NAMES = frozenset({
    'BELIEVES', 'KNOWS', 'ASSUMES', 'DOUBTS', 'DESIRES', 'INTENDS',
    'COMMITS', 'PREFERS', 'NORM_OUGHT', 'NORM_FORBID', 'RECANTED',
    'OCCURRED',
})


def _modality_str(m: Any) -> str:
    # Accept either an Enum (with .name) or a plain string.
    name = m.name if hasattr(m, 'name') else str(m)
    return name if name in _MODALITY_NAMES else 'UNKNOWN_MODALITY'


def canonical_conflict_key_hex(stmt: Any) -> str:
    """sha256 hex of 7-tuple joined by \\x1f US separator. See header."""
    h = hashlib.sha256()

    def feed(s: str) -> None:
        h.update(s.encode('utf-8'))
        h.update(_SEP)

    feed(stmt.holder_id)
    feed(_modality_str(getattr(stmt, 'modality', 'BELIEVES')))
    feed(f"{stmt.subject_kind}:{stmt.subject_id}")
    feed(stmt.predicate)
    feed(stmt.canonical_object_hash)

    interval = normalize_interval(
        getattr(stmt, 'valid_from', None),
        getattr(stmt, 'valid_to', None),
        getattr(stmt, 'event_time_start', None),
    )
    feed(interval.canonical_bytes())
    feed(canonical_scope_bytes(scope_of(stmt)))
    return h.hexdigest()

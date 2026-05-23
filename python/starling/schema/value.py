"""canonicalize_object v1 — produces a (canonical_string, sha256_hex) pair.

Used by Statement.canonical_object_hash (set at write time, M0.5
ConflictProbe indexes it). Version field on Statement
(canonical_object_hash_version) lets us evolve the rules; this module
implements v1 only.
"""

import hashlib
import math
import re
import unicodedata
from datetime import datetime, timezone

from starling.schema.refs import (
    CognizerRef, EntityRef, StatementRef, EngramRef,
    PersonaRef, KnowledgeFrontierRef,
)

_REF_CLASSES = (
    CognizerRef, EntityRef, StatementRef,
    EngramRef, PersonaRef, KnowledgeFrontierRef,
)

_WHITESPACE_RUN = re.compile(r"\s+")


def canonicalize_object(value) -> tuple[str, str]:
    canonical = _to_canonical(value)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return canonical, digest


def _to_canonical(value) -> str:
    # IMPORTANT: bool must be checked before int because bool is a subclass of int.
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise ValueError("schema_invalid: NaN/Inf not canonicalizable")
        # Collapse -0.0 to 0.0 before formatting.
        if value == 0.0:
            value = 0.0
        return f"{value:.6f}"
    if isinstance(value, str):
        nfc = unicodedata.normalize("NFC", value)
        trimmed = nfc.strip()
        folded = _WHITESPACE_RUN.sub(" ", trimmed)
        return folded.lower()
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("schema_invalid: naive datetime not canonicalizable")
        utc = value.astimezone(timezone.utc)
        return utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(value, _REF_CLASSES):
        return f"{type(value).__name__}:{value.id.hex}"
    raise ValueError(f"schema_invalid: unsupported type {type(value).__name__}")

"""Python implementation of compute_extraction_span_key, for parity with the
C++ helper in src/extractor/extraction_span_key.cpp. The C++ side is the
canonical writer; this Python helper exists for prompt-input-hash construction
and for tests that round-trip canonical keys without crossing the C bridge."""
from __future__ import annotations

import hashlib

_SEP = b"\x1f"


def compute_extraction_span_key(
    engram_ref_id: str,
    chunk_index: int,
    predicate: str,
    canonical_object_hash: str,
) -> str:
    """Return the sha256 hex digest of the canonical span key.

    Mirror of starling::extractor::compute_extraction_span_key. The field
    order, separator, and chunk_index decimal encoding all match the C++
    implementation byte-for-byte.
    """
    canonical = (
        engram_ref_id.encode("utf-8")
        + _SEP
        + str(int(chunk_index)).encode("ascii")
        + _SEP
        + predicate.encode("utf-8")
        + _SEP
        + canonical_object_hash.encode("ascii")
    )
    return hashlib.sha256(canonical).hexdigest()

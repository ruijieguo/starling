"""Python ↔ C++ parity for compute_extraction_span_key. Covers the
locked fixture vector from tests/cpp/test_extraction_span_key.cpp."""
from __future__ import annotations

from starling.extractor import compute_extraction_span_key


def test_deterministic():
    a = compute_extraction_span_key("engram-aaa", 0, "responsible_for", "deadbeef")
    b = compute_extraction_span_key("engram-aaa", 0, "responsible_for", "deadbeef")
    assert a == b
    assert len(a) == 64
    assert all(c in "0123456789abcdef" for c in a)


def test_chunk_index_varies():
    a = compute_extraction_span_key("engram-x", 0, "p", "h")
    b = compute_extraction_span_key("engram-x", 1, "p", "h")
    assert a != b


def test_predicate_varies():
    a = compute_extraction_span_key("engram-x", 0, "responsible_for", "h")
    b = compute_extraction_span_key("engram-x", 0, "manages", "h")
    assert a != b


def test_canonical_object_hash_varies():
    a = compute_extraction_span_key("engram-x", 0, "p", "hash1")
    b = compute_extraction_span_key("engram-x", 0, "p", "hash2")
    assert a != b


def test_engram_ref_varies():
    a = compute_extraction_span_key("engram-1", 0, "p", "h")
    b = compute_extraction_span_key("engram-2", 0, "p", "h")
    assert a != b


def test_locked_fixture_vector():
    """Pinned by tests/cpp/test_extraction_span_key.cpp's LockedFixtureVector."""
    locked = compute_extraction_span_key(
        engram_ref_id="01HZK9PWQ4RXM2NJEAQS37VBFZ",
        chunk_index=0,
        predicate="responsible_for",
        canonical_object_hash=(
            "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8"
        ),
    )
    assert locked == "a1543d3a85b188c8709a168c861612738b9b1b0a7d6002ba1a5c0f0ce01097b5"

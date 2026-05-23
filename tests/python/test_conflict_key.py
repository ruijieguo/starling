import pytest
from starling.bus.conflict_key import canonical_conflict_key_hex

# Locked parity fixture -- IMPLEMENTER: paste hex from C++ ParityFixtureHex stdout.
PARITY_HEX = "128e262474462a27c39126dbfc4c3876cac63f6d11f53a0161a8b6c8b66f8790"


class ParityStmt:
    holder_id             = "holder-uuid-parity"
    holder_tenant_id      = "tenant-parity"
    subject_kind          = "entity"
    subject_id            = "entity-uuid-parity"
    predicate             = "responsible_for"
    object_kind           = "str"
    object_value          = "auth"
    canonical_object_hash = "aaaa1111bbbb2222cccc3333dddd4444eeee5555ffff6666aaaa1111bbbb2222"
    modality              = "BELIEVES"
    polarity              = "POS"
    confidence            = 0.9
    observed_at           = "2026-01-01T00:00:00Z"
    valid_from            = None
    valid_to              = None
    event_time_start      = None


def test_parity_hex_matches_cpp():
    assert PARITY_HEX != "REPLACE_WITH_CPP_OUTPUT", \
        "Implementer must run C++ test and paste PARITY_HEX value"
    assert canonical_conflict_key_hex(ParityStmt()) == PARITY_HEX


def test_different_holder_produces_different_key():
    class S(ParityStmt):
        holder_id = "different-holder"
    assert canonical_conflict_key_hex(S()) != canonical_conflict_key_hex(ParityStmt())


def test_different_modality_produces_different_key():
    class S(ParityStmt):
        modality = "KNOWS"
    assert canonical_conflict_key_hex(S()) != canonical_conflict_key_hex(ParityStmt())


def test_same_input_produces_same_key():
    assert canonical_conflict_key_hex(ParityStmt()) == canonical_conflict_key_hex(ParityStmt())


def test_interval_participates_in_key():
    class S(ParityStmt):
        valid_from = "2026-01-01T00:00:00Z"
    assert canonical_conflict_key_hex(S()) != canonical_conflict_key_hex(ParityStmt())

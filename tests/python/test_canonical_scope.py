import pytest
from starling.bus.canonical_scope import (
    CanonicalScopeNull, CanonicalScopeNorm, CanonicalScopeCommitment,
    CanonicalScopeCommonGround, canonical_scope_bytes, scope_of,
)


def test_scope_of_returns_null_for_extracted_statement():
    class FakeStmt:
        holder_id = "h1"
        subject_kind = "entity"
        predicate = "knows"
    scope = scope_of(FakeStmt())
    assert isinstance(scope, CanonicalScopeNull)


def test_null_canonical_bytes_is_empty():
    assert CanonicalScopeNull().canonical_bytes() == ""
    assert canonical_scope_bytes(CanonicalScopeNull()) == ""


def test_future_norm_arm_raises_in_m05():
    with pytest.raises(NotImplementedError):
        CanonicalScopeNorm(kind="obligation", members_sorted=("a", "b")).canonical_bytes()


def test_future_commitment_arm_raises_in_m05():
    with pytest.raises(NotImplementedError):
        CanonicalScopeCommitment(principal="alice", beneficiary="bob").canonical_bytes()


def test_future_common_ground_arm_raises_in_m05():
    with pytest.raises(NotImplementedError):
        CanonicalScopeCommonGround(parties_sorted=("alice", "bob")).canonical_bytes()

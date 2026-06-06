import pytest
from starling.bus.canonical_scope import (
    CanonicalScopeNull, CanonicalScopeNorm, CanonicalScopeCommitment,
    CanonicalScopeCommonGround, canonical_scope_bytes, scope_of,
)


class _Stmt:
    holder_id = "self"
    subject_kind = "cognizer"
    subject_id = "bob"
    predicate = "p"
    modality = "BELIEVES"
    scope_parties = ()


def test_plain_belief_is_null():
    assert isinstance(scope_of(_Stmt()), CanonicalScopeNull)


def test_commits_is_commitment():
    class S(_Stmt):
        modality = "COMMITS"
        scope_parties = ("bob", "self")
    sc = scope_of(S())
    assert isinstance(sc, CanonicalScopeCommitment)
    assert sc.principal == "self"
    assert sc.beneficiary == "bob"


def test_norm_ought_is_norm():
    class S(_Stmt):
        modality = "NORM_OUGHT"
    sc = scope_of(S())
    assert isinstance(sc, CanonicalScopeNorm)
    assert sc.kind == "obligation"
    assert sc.canonical_bytes() != ""


def test_two_parties_is_common_ground():
    class S(_Stmt):
        scope_parties = ("self", "bob")
    sc = scope_of(S())
    assert isinstance(sc, CanonicalScopeCommonGround)
    assert list(sc.parties_sorted) == ["bob", "self"]


def test_null_canonical_bytes_is_empty():
    assert CanonicalScopeNull().canonical_bytes() == ""
    assert canonical_scope_bytes(CanonicalScopeNull()) == ""


def test_norm_canonical_bytes():
    assert CanonicalScopeNorm(kind="obligation", members_sorted=("a", "b")).canonical_bytes() \
        == "obligation\x1fa\x1fb"


def test_commitment_canonical_bytes():
    assert CanonicalScopeCommitment(principal="alice", beneficiary="bob").canonical_bytes() \
        == "alice\x1fbob"


def test_common_ground_canonical_bytes():
    assert CanonicalScopeCommonGround(parties_sorted=("alice", "bob")).canonical_bytes() \
        == "alice\x1fbob"

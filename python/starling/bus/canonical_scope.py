from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, List, Union


@dataclass(frozen=True)
class CanonicalScopeNull:
    def canonical_bytes(self) -> str:
        return ""


@dataclass(frozen=True)
class CanonicalScopeNorm:
    kind: str = ""
    members_sorted: tuple = ()

    def canonical_bytes(self) -> str:
        raise NotImplementedError("CanonicalScopeNorm.canonical_bytes not implemented in M0.5")


@dataclass(frozen=True)
class CanonicalScopeCommitment:
    principal: str = ""
    beneficiary: str = ""

    def canonical_bytes(self) -> str:
        raise NotImplementedError("CanonicalScopeCommitment.canonical_bytes not implemented in M0.5")


@dataclass(frozen=True)
class CanonicalScopeCommonGround:
    parties_sorted: tuple = ()

    def canonical_bytes(self) -> str:
        raise NotImplementedError("CanonicalScopeCommonGround.canonical_bytes not implemented in M0.5")


CanonicalScope = Union[
    CanonicalScopeNull,
    CanonicalScopeNorm,
    CanonicalScopeCommitment,
    CanonicalScopeCommonGround,
]


def canonical_scope_bytes(scope: CanonicalScope) -> str:
    return scope.canonical_bytes()


def scope_of(stmt: Any) -> CanonicalScope:
    """M0.5: always returns CanonicalScopeNull. M0.5+1 will branch on stmt.statement_kind."""
    return CanonicalScopeNull()

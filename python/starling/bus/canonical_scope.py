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
        return self.kind + ''.join('\x1f' + m for m in self.members_sorted)


@dataclass(frozen=True)
class CanonicalScopeCommitment:
    principal: str = ""
    beneficiary: str = ""

    def canonical_bytes(self) -> str:
        return self.principal + '\x1f' + self.beneficiary


@dataclass(frozen=True)
class CanonicalScopeCommonGround:
    parties_sorted: tuple = ()

    def canonical_bytes(self) -> str:
        return '\x1f'.join(self.parties_sorted)


CanonicalScope = Union[
    CanonicalScopeNull,
    CanonicalScopeNorm,
    CanonicalScopeCommitment,
    CanonicalScopeCommonGround,
]


def canonical_scope_bytes(scope: CanonicalScope) -> str:
    return scope.canonical_bytes()


def scope_of(stmt: Any) -> CanonicalScope:
    """Derive the canonical scope from a statement (P2.j).

    Mirrors the C++ scope_of byte-for-byte: modality 优先（COMMITS→Commitment；
    NORM_*→Norm；else scope_parties≥2→CommonGround；else Null）。
    """
    mod = stmt.modality.name if hasattr(stmt.modality, 'name') else str(stmt.modality)
    parties = list(getattr(stmt, 'scope_parties', []) or [])
    holder = stmt.holder_id
    if mod == 'COMMITS':
        beneficiary = next((p for p in parties if p != holder), "")
        return CanonicalScopeCommitment(principal=holder, beneficiary=beneficiary)
    if mod in ('NORM_OUGHT', 'NORM_FORBID'):
        members = sorted([holder, stmt.subject_id])
        kind = 'obligation' if mod == 'NORM_OUGHT' else 'prohibition'
        return CanonicalScopeNorm(kind=kind, members_sorted=members)
    if len(parties) >= 2:
        return CanonicalScopeCommonGround(parties_sorted=sorted(parties))
    return CanonicalScopeNull()

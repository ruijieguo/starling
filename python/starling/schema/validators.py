"""Cross-field schema validators (M0.1).

Pure functions: return None on legality, raise SchemaInvalid on violation.
M0.4 LLM Extractor calls these pre-construction; M0.5 ConflictProbe calls
them post-merge."""

from starling.schema.cognizer import Cognizer
from starling.schema.enums import (
    ContainerKind, StatementProvenance, EvidenceStatus, Perspective,
)
from starling.schema.container import VALID_DIMENSIONS
from starling.schema.refs import StatementRef
from starling.schema.statement import Statement
from starling.schema.value import canonicalize_object


class SchemaInvalid(ValueError):
    """Raised when a Statement / Container fails a cross-field invariant."""


_PROVENANCE_NEEDS_EVIDENCE = frozenset({
    StatementProvenance.USER_INPUT,
})
_PROVENANCE_NEEDS_DERIVATION = frozenset({
    StatementProvenance.TOM_INFERRED,
    StatementProvenance.REPLAY_DERIVED,
    StatementProvenance.RECONSOLIDATION_DERIVED,
})


def validate_evidence_or_derivation(stmt: Statement) -> None:
    if stmt.provenance in _PROVENANCE_NEEDS_EVIDENCE:
        if not stmt.evidence:
            raise SchemaInvalid(
                f"provenance={stmt.provenance.value} requires non-empty evidence"
            )
    elif stmt.provenance in _PROVENANCE_NEEDS_DERIVATION:
        if not stmt.derived_from:
            raise SchemaInvalid(
                f"provenance={stmt.provenance.value} requires non-empty derived_from"
            )


def validate_subject_not_statement(stmt: Statement) -> None:
    if isinstance(stmt.subject, StatementRef):
        raise SchemaInvalid(
            "subject must not be StatementRef (§3.2 hash stability)"
        )


def validate_derived_depth(
    stmt: Statement, parent_depths: dict[StatementRef, int]
) -> None:
    if not stmt.derived_from:
        if stmt.derived_depth != 0:
            raise SchemaInvalid(
                "derived_depth must be 0 when derived_from is empty"
            )
        return
    expected = max(parent_depths[parent] for parent in stmt.derived_from) + 1
    if stmt.derived_depth != expected:
        raise SchemaInvalid(
            f"derived_depth {stmt.derived_depth} does not match max(parent)+1 = {expected}"
        )


def validate_tenant_derived(stmt: Statement, holder: Cognizer) -> None:
    if stmt.tenant_id != holder.tenant_id:
        raise SchemaInvalid(
            f"tenant_id={stmt.tenant_id} does not match holder.tenant_id={holder.tenant_id}"
        )


def validate_perspective_provenance(stmt: Statement) -> None:
    if stmt.provenance == StatementProvenance.TOM_INFERRED:
        if stmt.holder_perspective != Perspective.INFERRED:
            raise SchemaInvalid(
                "tom_inferred provenance requires holder_perspective=INFERRED"
            )


def validate_canonical_object_hash(stmt: Statement) -> None:
    _, expected_hash = canonicalize_object(stmt.object)
    if stmt.canonical_object_hash != expected_hash:
        raise SchemaInvalid(
            f"canonical_object_hash mismatch: expected {expected_hash}, got {stmt.canonical_object_hash}"
        )


def validate_evidence_status(stmt: Statement) -> None:
    for ref in stmt.evidence:
        active = ref.status == EvidenceStatus.ACTIVE
        erased = ref.status == EvidenceStatus.ERASED
        if active and ref.erased_at is not None:
            raise SchemaInvalid(
                "evidence_status ACTIVE must have erased_at=None"
            )
        if erased and ref.erased_at is None:
            raise SchemaInvalid(
                "evidence_status ERASED must have erased_at not None"
            )


def validate_container_dimension(
    container_kind: ContainerKind, dimension: str
) -> None:
    legal = VALID_DIMENSIONS.get(container_kind)
    if legal is None:
        raise SchemaInvalid(f"unknown container kind: {container_kind}")
    if dimension not in legal:
        raise SchemaInvalid(
            f"dimension {dimension!r} not legal for {container_kind.value}; "
            f"legal keys: {sorted(legal)}"
        )

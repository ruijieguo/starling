"""Container family + dimension-key sets (M0.1).

Per §3.7: Container is a materialized view (not a Statement). It holds
StatementRefs and a derived payload, rebuilt by Bus.rebuild_container
(M0.2+). M0.1 only exposes the dataclass + dimension-key constants;
runtime rebuilding is out of scope."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from starling.schema.enums import ContainerKind, BuildPolicy
from starling.schema.refs import (
    StatementRef, CognizerRef,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class Container:
    id: uuid.UUID
    kind: ContainerKind
    last_rebuilt_at: datetime
    source_refs: tuple[StatementRef, ...] = ()
    materialized_payload: tuple[tuple[str, object], ...] = ()
    version: int = 0
    dimension_versions: tuple[tuple[str, int], ...] = ()
    dimension_sequences: tuple[tuple[str, int], ...] = ()
    build_policy: BuildPolicy = BuildPolicy.ON_EVENT


@dataclass(frozen=True, slots=True, kw_only=True)
class Persona(Container):
    cognizer: CognizerRef


@dataclass(frozen=True, slots=True, kw_only=True)
class CommonGround(Container):
    parties: tuple[CognizerRef, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeFrontier(Container):
    cognizer: CognizerRef


# §3.7 dimension key tables (legal keys per Container kind)
PERSONA_DIMENSIONS = frozenset({
    "traits", "preferences", "competencies", "values",
    "self_model_anchor", "profile_anchor", "relationship_styles",
})
COMMON_GROUND_DIMENSIONS = frozenset({
    "grounded", "asserted_unack", "suspected_diverge", "establishment_evidence",
})
KNOWLEDGE_FRONTIER_DIMENSIONS = frozenset({
    "accessible_sources", "membership", "presence_log", "explicit_told", "explicit_not_told",
})

VALID_DIMENSIONS: dict[ContainerKind, frozenset[str]] = {
    ContainerKind.PERSONA: PERSONA_DIMENSIONS,
    ContainerKind.COMMON_GROUND: COMMON_GROUND_DIMENSIONS,
    ContainerKind.KNOWLEDGE_FRONTIER: KNOWLEDGE_FRONTIER_DIMENSIONS,
}

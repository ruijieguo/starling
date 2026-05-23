"""Cognizer + AccessPolicy placeholder (M0.1)."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from starling.schema.refs import (
    CognizerRef, PersonaRef, KnowledgeFrontierRef,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class AccessPolicy:
    """P1 placeholder. Real policy lands in P2+ Governance."""
    policy_name: str = "default"


@dataclass(frozen=True, slots=True, kw_only=True)
class Cognizer:
    id: uuid.UUID
    kind: Literal["self", "human", "agent", "group", "role", "external"]
    canonical_name: str
    external_id: str
    created_at: datetime
    last_seen_at: datetime
    tenant_id: str = "default"
    aliases: tuple[str, ...] = ()
    persona: PersonaRef | None = None
    knowledge_frontier: KnowledgeFrontierRef | None = None
    relations: tuple = ()
    trust_priors: tuple[tuple[CognizerRef, float], ...] = ()
    permissions: AccessPolicy | None = None

    @staticmethod
    def derive_id(kind: str, external_id: str) -> uuid.UUID:
        return uuid.uuid5(uuid.NAMESPACE_OID, f"cognizer:{kind}:{external_id}")

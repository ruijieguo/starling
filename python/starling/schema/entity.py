"""Entity (non-cognizer subject) (M0.1).

Per §3.2: Entity is a thing, not a cognitive subject. It has no persona,
no knowledge_frontier, no trust_priors. It can only appear as
Statement.subject or Statement.object — never as holder."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True, slots=True, kw_only=True)
class Entity:
    id: uuid.UUID
    kind: Literal["concept", "artifact", "place", "event", "organization", "project", "other"]
    canonical_name: str
    created_at: datetime
    aliases: tuple[str, ...] = ()
    type_tags: tuple[str, ...] = ()

    @staticmethod
    def derive_id(kind: str, canonical_name: str) -> uuid.UUID:
        return uuid.uuid5(uuid.NAMESPACE_OID, f"entity:{kind}:{canonical_name}")

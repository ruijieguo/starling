"""RelationEdge (M0.1).

Per §3.12: edges live in a (source_id, target_id, edge_kind) triple table.
M0.1 only exposes the dataclass; persistence + index work lands in M0.2+.
Source/target are UUIDs without ref-class type tagging because the legal
ref class depends on edge_kind — validators in T8 enforce per-kind shape."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from starling.schema.enums import EdgeKind


@dataclass(frozen=True, slots=True, kw_only=True)
class RelationEdge:
    source_id: uuid.UUID
    target_id: uuid.UUID
    edge_kind: EdgeKind
    created_at: datetime
    metadata: tuple[tuple[str, object], ...] = ()

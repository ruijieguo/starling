from datetime import datetime, timezone
import uuid
from starling.schema.edge import RelationEdge
from starling.schema.enums import EdgeKind


def test_edge_constructs():
    e = RelationEdge(
        source_id=uuid.uuid4(),
        target_id=uuid.uuid4(),
        edge_kind=EdgeKind.TRUSTS,
        created_at=datetime(2026, 5, 23, tzinfo=timezone.utc),
    )
    assert e.edge_kind == EdgeKind.TRUSTS


def test_all_14_edge_kinds_constructible():
    now = datetime(2026, 5, 23, tzinfo=timezone.utc)
    for k in EdgeKind:
        e = RelationEdge(
            source_id=uuid.uuid4(), target_id=uuid.uuid4(),
            edge_kind=k, created_at=now,
        )
        assert e.edge_kind == k

"""brain_map query — Phase 3 片 1 类脑 IA 落地页(9 脑区活体计数)。

Seeds 2 VOLATILE + 1 CONSOLIDATED statement via the runtime-built schema, then
asserts brain_map returns the 9 regions in memory-flow order, with the
consolidation_state-filtered counts correct, lens active (片 3 落地), 对话/配置 count=None.
"""
import sqlite3
from pathlib import Path

from starling.dashboard import queries

_STMT_COLS = (
    "id, tenant_id, holder_id, holder_perspective, subject_kind, subject_id, "
    "predicate, object_kind, object_value, canonical_object_hash, "
    "canonical_object_hash_version, modality, polarity, confidence, observed_at, "
    "salience, affect_json, activation, last_accessed, provenance, created_at, "
    "updated_at, consolidation_state"
)


def _stmt(conn, sid, tenant, state):
    conn.execute(
        f"INSERT INTO statements ({_STMT_COLS}) VALUES ({','.join('?' * 23)})",
        (sid, tenant, "self", "first_person", "cognizer", "Bob", "responsible_for",
         "str", "auth", f"h{sid}", "v1", "BELIEVES", "POS", 0.9, "2026-04-10T10:00:00Z",
         0.5, "{}", 0.0, "2026-04-10T10:00:00Z", "test", "2026-04-10T10:00:00Z",
         "2026-04-10T10:00:00Z", state),
    )


def _seed(db_path: str):
    from starling import runtime as rt
    from starling.testing import relax_preflight_for_m0_3
    relax_preflight_for_m0_3()
    r = rt._build_local_store_sqlite_runtime(Path(db_path))
    r.start()
    del r  # release the writer handle before raw seeding
    conn = sqlite3.connect(db_path)
    _stmt(conn, "s1", "default", "volatile")
    _stmt(conn, "s2", "default", "volatile")
    _stmt(conn, "s3", "default", "consolidated")
    _stmt(conn, "s4", "other", "volatile")   # other tenant — must be excluded
    conn.commit()
    conn.close()


def test_brain_map_nine_regions_in_flow_order(tmp_path):
    db = str(tmp_path / "bm.db")
    _seed(db)
    out = queries.brain_map(db, "default")
    keys = [r["key"] for r in out["regions"]]
    assert len(keys) == 9
    # memory-flow order (输入 → 快存 → 慢存 → 他者 → 意图 → 固化 → 内省 → 体征 → 配置)
    assert keys == ["converse", "short_term", "long_term", "theory_of_mind",
                    "prospective", "consolidation", "lens", "vitals", "config"]


def test_brain_map_counts_and_flags(tmp_path):
    db = str(tmp_path / "bm.db")
    _seed(db)
    regions = {r["key"]: r for r in queries.brain_map(db, "default")["regions"]}
    # consolidation_state-filtered, tenant-scoped (other-tenant s4 excluded)
    assert regions["short_term"]["count"] == 2 and regions["short_term"]["region"] == "海马"
    assert regions["long_term"]["count"] == 1 and regions["long_term"]["region"] == "新皮层"
    # lens landed (slice 3) → no longer dormant; still no count (a tool, not a store)
    assert regions["lens"]["dormant"] is False and regions["lens"]["count"] is None
    assert regions["converse"]["count"] is None and regions["converse"]["dormant"] is False
    assert regions["config"]["count"] is None
    # the remaining live counts are present integers (>=0), degrade-safe
    for k in ("theory_of_mind", "prospective", "consolidation", "vitals"):
        assert isinstance(regions[k]["count"], int) and regions[k]["count"] >= 0

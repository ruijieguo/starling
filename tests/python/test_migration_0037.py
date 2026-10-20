"""迁移 0037：source_unit_meta / source_unit_vectors / cognizer_group_membership 自检。

对应 design v4.3 的 §5.3（权威元数据与派生索引分离）与 §3.2b（带历史的组成员关系）。
"""
import json
import sqlite3

import pytest

from starling import runtime

TENANT = "default"


@pytest.fixture
def rt(tmp_path):
    r = runtime._build_local_store_sqlite_runtime(tmp_path / "starling.db")
    r.start()
    yield r


def _cols(rt, table):
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        return {r[1] for r in c.execute(f"PRAGMA table_info({table})")}


def _pk(rt, table):
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        rows = sorted((r[5], r[1]) for r in c.execute(f"PRAGMA table_info({table})") if r[5])
        return [name for _, name in rows]


def _make_engram(rt, engram_id="eng-1"):
    """插入一条最小 engram，供 source_unit_meta 的外键使用。"""
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        c.execute(
            "INSERT INTO engrams (id, tenant_id, content_hash, source_kind, ingest_policy,"
            " ingest_mode, privacy_class, retention_mode, refcount, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (engram_id, TENANT, "h" * 64, "user_input", "p", "whole_record",
             "INTERNAL", "audit_retain", 0, "2026-01-01T00:00:00Z"),
        )
        c.commit()


# ── 表结构 ────────────────────────────────────────────────────────────────

def test_source_unit_meta_columns(rt):
    assert {"tenant_id", "engram_ref", "clause_id", "speaker", "session_id",
            "audience_json", "turn_index", "observed_at", "provenance"} <= _cols(rt, "source_unit_meta")


def test_source_unit_meta_primary_key(rt):
    assert _pk(rt, "source_unit_meta") == ["tenant_id", "engram_ref", "clause_id"]


def test_source_unit_vectors_columns(rt):
    assert {"tenant_id", "engram_ref", "clause_id", "dim", "model", "index_vector",
            "raw_embedding", "status", "retry_count", "last_attempt_at",
            "embedded_at"} <= _cols(rt, "source_unit_vectors")


def test_source_unit_vectors_has_no_authoritative_metadata(rt):
    """派生表不得承载权威元数据（听众/场景/时间/来源）。"""
    cols = _cols(rt, "source_unit_vectors")
    assert not ({"audience_json", "session_id", "observed_at", "provenance"} & cols)


def test_group_membership_columns_and_pk(rt):
    assert {"tenant_id", "group_id", "cognizer_id", "joined_at", "left_at",
            "recorded_at"} <= _cols(rt, "cognizer_group_membership")
    assert _pk(rt, "cognizer_group_membership") == [
        "tenant_id", "group_id", "cognizer_id", "joined_at"]


# ── 约束 ──────────────────────────────────────────────────────────────────

def test_provenance_check_rejects_unknown(rt):
    _make_engram(rt)
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        with pytest.raises(sqlite3.IntegrityError):
            c.execute(
                "INSERT INTO source_unit_meta (tenant_id, engram_ref, clause_id, speaker,"
                " session_id, audience_json, provenance) VALUES (?,?,?,?,?,?,?)",
                (TENANT, "eng-1", "c0", "alice", "s1", "[]", "bogus"),
            )


def test_vector_status_check_rejects_unknown(rt):
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        with pytest.raises(sqlite3.IntegrityError):
            c.execute(
                "INSERT INTO source_unit_vectors (tenant_id, engram_ref, clause_id, dim,"
                " model, status) VALUES (?,?,?,?,?,?)",
                (TENANT, "eng-1", "c0", 8, "m", "bogus"),
            )


def test_dim_check_rejects_zero(rt):
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        with pytest.raises(sqlite3.IntegrityError):
            c.execute(
                "INSERT INTO source_unit_vectors (tenant_id, engram_ref, clause_id, dim,"
                " model, status) VALUES (?,?,?,?,?,?)",
                (TENANT, "eng-1", "c0", 0, "m", "pending"),
            )


def test_source_unit_meta_foreign_key_enforced(rt):
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        c.execute("PRAGMA foreign_keys = ON")
        with pytest.raises(sqlite3.IntegrityError):
            c.execute(
                "INSERT INTO source_unit_meta (tenant_id, engram_ref, clause_id, speaker,"
                " session_id, audience_json) VALUES (?,?,?,?,?,?)",
                (TENANT, "no-such-engram", "c0", "alice", "s1", "[]"),
            )


# ── 组成员关系：幂等与历史 ─────────────────────────────────────────────────

def test_membership_duplicate_same_joined_at_ignored(rt):
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        sql = ("INSERT OR IGNORE INTO cognizer_group_membership (tenant_id, group_id,"
               " cognizer_id, joined_at, recorded_at) VALUES (?,?,?,?,?)")
        c.execute(sql, (TENANT, "team", "alice", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"))
        c.execute(sql, (TENANT, "team", "alice", "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z"))
        n = c.execute("SELECT COUNT(*) FROM cognizer_group_membership").fetchone()[0]
    assert n == 1, "同一 (组,成员,生效时刻) 必须被 INSERT OR IGNORE 吸收"


def test_membership_history_preserved_across_joined_at(rt):
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        sql = ("INSERT INTO cognizer_group_membership (tenant_id, group_id, cognizer_id,"
               " joined_at, recorded_at) VALUES (?,?,?,?,?)")
        c.execute(sql, (TENANT, "team", "alice", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"))
        c.execute(sql, (TENANT, "team", "alice", "2026-03-01T00:00:00Z", "2026-03-01T00:00:00Z"))
        n = c.execute("SELECT COUNT(*) FROM cognizer_group_membership WHERE cognizer_id='alice'"
                      ).fetchone()[0]
    assert n == 2, "不同生效时刻的加入是不同历史行，不能被合并"


def test_membership_asof_query_shape(rt):
    """as-of 查询的语义：joined_at <= t 且 (left_at 为 NULL 或 > t)。"""
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        c.execute("INSERT INTO cognizer_group_membership (tenant_id, group_id, cognizer_id,"
                  " joined_at, left_at, recorded_at) VALUES (?,?,?,?,?,?)",
                  (TENANT, "team", "alice", "2026-01-01T00:00:00Z", "2026-02-01T00:00:00Z",
                   "2026-01-01T00:00:00Z"))
        c.execute("INSERT INTO cognizer_group_membership (tenant_id, group_id, cognizer_id,"
                  " joined_at, left_at, recorded_at) VALUES (?,?,?,?,?,?)",
                  (TENANT, "team", "bob", "2026-01-15T00:00:00Z", None,
                   "2026-01-15T00:00:00Z"))

        def members_at(t):
            return {r[0] for r in c.execute(
                "SELECT cognizer_id FROM cognizer_group_membership"
                " WHERE tenant_id=? AND group_id=? AND joined_at<=?"
                "   AND (left_at IS NULL OR left_at>?)", (TENANT, "team", t, t))}

        assert members_at("2026-01-05T00:00:00Z") == {"alice"}
        assert members_at("2026-01-20T00:00:00Z") == {"alice", "bob"}
        assert members_at("2026-03-01T00:00:00Z") == {"bob"}


def test_audience_json_roundtrip(rt):
    _make_engram(rt)
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        c.execute(
            "INSERT INTO source_unit_meta (tenant_id, engram_ref, clause_id, speaker,"
            " session_id, audience_json, turn_index, observed_at, provenance)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (TENANT, "eng-1", "c0", "alice", "scene-1",
             json.dumps(["alice", "bob"]), 0, "2026-01-01T00:00:00Z", "source_time"),
        )
        got = c.execute("SELECT audience_json, turn_index FROM source_unit_meta").fetchone()
    assert json.loads(got[0]) == ["alice", "bob"]
    assert got[1] == 0

"""P2.c migrations 0018/0019/0020 建表自检。"""
import sqlite3
import pytest
from starling import _core, runtime
from starling.testing import relax_preflight_for_m0_3


@pytest.fixture
def rt(tmp_path, monkeypatch):
    orig = relax_preflight_for_m0_3()
    r = runtime._build_local_store_sqlite_runtime(tmp_path / "starling.db")
    r.start()
    yield r
    monkeypatch.setattr(runtime, "LOCAL_STORE_REQUIRED", orig)


def _cols(rt, table):
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        return {r[1] for r in c.execute(f"PRAGMA table_info({table})")}


def test_commitments_table_exists(rt):
    assert {"stmt_id", "tenant_id", "state", "broken_count", "deadline",
            "created_at", "updated_at"} <= _cols(rt, "commitments")


def test_commitment_triggers_table_exists(rt):
    assert {"id", "commitment_stmt_id", "tenant_id", "kind", "spec_json",
            "status", "created_at"} <= _cols(rt, "commitment_triggers")
    # policy_engine_checkpoint singleton seeded
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        assert c.execute("SELECT seq FROM policy_engine_checkpoint WHERE id=1").fetchone()[0] == 0


def test_commitment_protection_table_exists(rt):
    assert {"commitment_stmt_id", "protected_stmt_id"} <= _cols(rt, "commitment_protection")

"""M0.9 migrations 0016/0017 建表自检。"""
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


def test_statement_vectors_table_exists(rt):
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        cols = {r[1] for r in c.execute("PRAGMA table_info(statement_vectors)")}
    assert {"stmt_id", "tenant_id", "index_vector", "raw_embedding", "dim", "model",
            "status", "retry_count", "last_attempt_at", "embedded_at"} <= cols


def test_proj_vector_payload_table_exists(rt):
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        cols = {r[1] for r in c.execute("PRAGMA table_info(proj_vector_payload)")}
    assert {"tenant_id", "holder_id", "consolidation_state", "modality",
            "review_status", "stmt_id"} <= cols

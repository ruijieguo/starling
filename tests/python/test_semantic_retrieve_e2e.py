"""M0.9 SemanticRetriever 端到端 (spec §7): vector_recall 按相似度排序.

经 pybind binding 验证: 嵌入 2 个可见 statement, 用与 s1 的 render_text
("bob knows cats") 完全一致的 query → s1 排第一; degraded=False。
另: 不跑 worker 时 runtime health 仍 READY — 向量子系统不影响 health。
"""
from __future__ import annotations
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


def _seed_statement(rt, stmt_id, obj):
    # render_text = "bob knows <obj>"; distinct obj → distinct stub embedding.
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        c.execute(
            "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
            "subject_kind,subject_id,predicate,object_kind,object_value,"
            "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
            "confidence,observed_at,salience,affect_json,activation,last_accessed,"
            "provenance,consolidation_state,review_status,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (stmt_id, "default", "alice", "first_person", "cognizer", "bob",
             "knows", "str", obj, "a"*64, "v1", "believes", "pos", 0.9,
             "2026-05-30T09:00:00Z", 0.5, "{}", 0.0, "2026-05-30T09:00:00Z",
             "user_input", "consolidated", "approved",
             "2026-05-30T09:00:00Z", "2026-05-30T09:00:00Z"))
        c.commit()


def test_vector_recall_ranks_by_similarity(rt):
    _seed_statement(rt, "s1", "cats")
    _seed_statement(rt, "s2", "stocks")

    # Hold embedder + index so keep_alive keeps the refs alive; reuse the SAME
    # emb/idx for worker and retriever for deterministic embeddings.
    emb = _core.StubEmbeddingAdapter(8)
    idx = _core.SqliteBlobVectorIndex()
    w = _core.EmbeddingWorker(rt.adapter, emb, idx)
    w.tick_one_batch("2026-05-30T10:00:00Z")

    sr = _core.SemanticRetriever(rt.adapter, emb, idx)
    res = sr.vector_recall(_core.SemanticRetrieverParams(
        tenant_id="default", holder_id="alice",
        query_text="bob knows cats", k=2))

    assert res.degraded is False
    assert len(res.rows) >= 1
    # s1's stored vector came from "bob knows cats" — exactly the query text.
    assert res.rows[0].row.id == "s1"


def test_runtime_ready_without_vectors(rt):
    # No worker run; the vector subsystem must not affect runtime health.
    assert rt.health() == _core.RuntimeHealth.READY

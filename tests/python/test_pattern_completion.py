"""P2.d PatternCompletor 端到端 smoke (经 pybind binding):

写 statements → EmbeddingWorker 嵌入 seed (StubEmbeddingAdapter) →
手工 overlap 边 seed→A (w=0.9) 与 A→B (w=0.8) → PatternCompletor.complete(cue)
返回连通子图: seed 激活 1.0 + 邻居 A (0.9*0.5=0.45) + 二跳 B (0.45*0.8*0.5=0.18)。
验证 completion_truncated is False。

种子数据经 raw sqlite3 写入 _core.SqliteAdapter 已打开的同一 db 文件 (迁移已建表)。
为避免 WAL 锁竞争: raw 写入与 C++ worker 写入严格顺序化 (raw commit+close 后再跑
worker), 且 raw 连接设 busy_timeout。
"""
from __future__ import annotations

import sqlite3

import pytest

from starling import _core, runtime


@pytest.fixture
def rt(tmp_path):
    r = runtime._build_local_store_sqlite_runtime(tmp_path / "pc.db")
    r.start()
    yield r


_STATEMENT_COLS = (
    "INSERT INTO statements("
    "id,tenant_id,holder_id,holder_perspective,subject_kind,subject_id,"
    "predicate,object_kind,object_value,canonical_object_hash,"
    "canonical_object_hash_version,modality,polarity,confidence,observed_at,"
    "salience,affect_json,activation,last_accessed,provenance,"
    "consolidation_state,review_status,created_at,updated_at) "
    "VALUES (?,?,?,?,'cognizer','bob','knows','str',?,?,'v1','believes','pos',"
    "0.9,'2026-05-31T09:00:00Z',0.5,'{}',0.0,'2026-05-31T09:00:00Z',"
    "'user_input','consolidated','approved','2026-05-31T09:00:00Z',"
    "'2026-05-31T09:00:00Z')"
)

_EDGE_SQL = (
    "INSERT INTO statement_edges("
    "id,tenant_id,src_id,dst_id,edge_kind,weight,created_at,metadata_json) "
    "VALUES (?,?,?,?,'MAY_OVERLAP_WITH',?,'2026-05-31T00:00:00Z',"
    "'{\"resolved\":false}')"
)


def _seed_statement(conn, stmt_id, obj):
    # render_text = "bob knows <obj>"; distinct obj → distinct stub embedding.
    conn.execute(
        _STATEMENT_COLS,
        (stmt_id, "default", "alice", "first_person", obj, "a" * 64),
    )


def _seed_edge(conn, edge_id, src, dst, weight):
    conn.execute(_EDGE_SQL, (edge_id, "default", src, dst, weight))


def test_pattern_completion_returns_connected_subgraph(rt):
    db_path = str(rt.adapter.db_path)

    # Seed all three statements + the two overlap edges in ONE raw transaction
    # BEFORE running the worker, then commit/close. This keeps raw writes and
    # the C++ worker write strictly sequential (no overlapping WAL writers) and
    # is the robust path against `database is locked`.
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        conn.execute("PRAGMA busy_timeout=30000")
        _seed_statement(conn, "seed", "cats")   # render_text "bob knows cats"
        _seed_statement(conn, "A", "dogs")
        _seed_statement(conn, "B", "birds")
        _seed_edge(conn, "e1", "seed", "A", 0.9)
        _seed_edge(conn, "e2", "A", "B", 0.8)
        conn.commit()
    finally:
        conn.close()

    # Hold emb+idx alive and reuse the SAME refs for worker and retriever so the
    # seed's stored vector matches the cue embedding deterministically.
    emb = _core.StubEmbeddingAdapter(8)
    idx = _core.SqliteBlobVectorIndex()
    worker = _core.EmbeddingWorker(rt.adapter, emb, idx)
    worker.tick_one_batch("2026-05-31T10:00:00Z")  # embeds seed, A, B

    sr = _core.SemanticRetriever(rt.adapter, emb, idx)
    pc = _core.PatternCompletor(rt.adapter, sr)

    # seed_k=1 so ONLY the exact-text match `seed` is recalled as a vector seed
    # (activation 1.0). A and B must then be reached purely via the overlap edges
    # (graph walk) — that is what this smoke proves. With a larger seed_k the
    # StubEmbeddingAdapter recalls A/B as seeds too and they'd be activated at 1.0
    # directly, hiding the walk rather than exercising it.
    params = _core.PatternCompletionParams(
        tenant_id="default",
        holder_id="alice",
        holder_perspective="first_person",
        cue_text="bob knows cats",  # exactly seed's render_text
        seed_k=1,
    )
    res = pc.complete(params)

    acts = {r.row.id: r.activation for r in res.rows}

    # seed: SemanticRetriever recalls the exact-text match at activation 1.0.
    assert "seed" in acts, f"seed missing from subgraph: {acts}"
    assert acts["seed"] == pytest.approx(1.0, abs=1e-6)

    # A: one hop over seed→A (w=0.9), decay 0.5 → 0.9 * 0.5 = 0.45.
    assert "A" in acts, f"neighbor A missing: {acts}"
    assert acts["A"] == pytest.approx(0.45, abs=1e-6)

    # B: two hops seed→A→B (w=0.8), 0.45 * 0.8 * 0.5 = 0.18 ≥ theta_propagate.
    assert "B" in acts, f"two-hop B missing: {acts}"
    assert acts["B"] == pytest.approx(0.18, abs=1e-6)

    assert res.completion_truncated is False

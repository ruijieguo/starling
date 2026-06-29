"""TC-VEC-REPAIR [CRITICAL]: proj_vector_payload rebuild 抽取 < ground truth → 不替换.

spec §16.3-3/-6: proj_vector_payload 是首个 ground_truth(已嵌入向量数) 与 rebuilt
(物化行数) 真正可能不同的投影 — 因此 truncation guard 能真正 fire。

经 pybind binding(EmbeddingWorker / ProjectionMaintainer.
rebuild_projection_with_injected_count) 验证: rebuilt(2) < ground_truth(3) 时
emit projection.rebuild_failed(truncation_suspected) 且 active projection 不被替换。
"""
from __future__ import annotations
import sqlite3
import pytest
from starling import _core, runtime


@pytest.fixture
def rt(tmp_path):
    r = runtime._build_local_store_sqlite_runtime(tmp_path / "starling.db")
    r.start()
    yield r


def _seed_statement(rt, stmt_id, obj):
    # object_value (obj) varies so each statement gets a distinct stub embedding.
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


def test_truncation_suspected_keeps_active(rt):
    # seed 3 statements with distinct object texts → embed → materialize 3 rows.
    for stmt_id, obj in [("s0", "a"), ("s1", "b"), ("s2", "c")]:
        _seed_statement(rt, stmt_id, obj)

    # Hold embedder + index in Python vars so keep_alive keeps the refs alive.
    emb = _core.StubEmbeddingAdapter(8)
    idx = _core.SqliteBlobVectorIndex()
    w = _core.EmbeddingWorker(rt.adapter, emb, idx)
    w.tick_one_batch("2026-05-30T10:00:00Z")

    pm = _core.ProjectionMaintainer(rt.adapter)
    pm.tick_one_batch("2026-05-30T10:01:00Z")

    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        before = c.execute(
            "SELECT COUNT(*) FROM proj_vector_payload").fetchone()[0]
    assert before == 3

    # Inject rebuilt=2 < ground_truth=3 → truncation guard fires.
    report = pm.rebuild_projection_with_injected_count(
        "proj_vector_payload", injected_rebuilt=2, now_iso="2026-05-30T11:00:00Z")
    assert report.truncation_suspected is True

    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        # active projection NOT replaced — still 3 rows.
        after = c.execute(
            "SELECT COUNT(*) FROM proj_vector_payload").fetchone()[0]
        status = c.execute(
            "SELECT status FROM projection_rebuild_state "
            "WHERE projection_name='proj_vector_payload'").fetchone()[0]
        ev = c.execute(
            "SELECT COUNT(*) FROM bus_events "
            "WHERE event_type='projection.rebuild_failed'").fetchone()[0]

    assert after == 3, "truncation_suspected 时 active projection 不被替换"
    assert status == "truncation_suspected"
    assert ev == 1, "应 emit projection.rebuild_failed 恰一次"

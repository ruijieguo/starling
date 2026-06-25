"""replay query — Phase 3 片 2 梦境日志:确认 ledger 现在带出 ops_applied_json
(批次做了什么)。前端 dream.ts 据此把 op 计数渲染成「固化 3 · 归档 1」。"""
import sqlite3
from pathlib import Path

from starling.dashboard import queries


def _seed(db_path: str):
    from starling import runtime as rt
    from starling.testing import relax_preflight_for_m0_3
    relax_preflight_for_m0_3()
    r = rt._build_local_store_sqlite_runtime(Path(db_path))
    r.start()
    del r
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO replay_ledger (replay_batch_id, mode, sampled_count, "
        "ops_applied_json, started_at, finished_at) VALUES (?,?,?,?,?,?)",
        ("b1", "online", 4, '{"op_compress":3,"op_archive":1}',
         "2026-04-10T10:00:00Z", "2026-04-10T10:00:05Z"),
    )
    conn.commit()
    conn.close()


def test_replay_ledger_carries_ops_applied_json(tmp_path):
    db = str(tmp_path / "r.db")
    _seed(db)
    out = queries.replay(db, "default")
    assert out["ledger"], "ledger should contain the seeded batch"
    row = out["ledger"][0]
    assert row["replay_batch_id"] == "b1"
    assert row["mode"] == "online"
    assert row["sampled_count"] == 4
    # the column added for the dream log — what the batch actually did
    assert row["ops_applied_json"] == '{"op_compress":3,"op_archive":1}'

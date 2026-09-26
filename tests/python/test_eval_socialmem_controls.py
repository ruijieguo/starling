"""Frozen-ingest controls use real SQLite/core operations without API calls."""
import hashlib
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import eval_ladder_pipeline as pipe
import eval_socialmem_controls as controls
from starling import _core, runtime


@pytest.mark.parametrize("variant,eligible", [("star_immediate", 0), ("star_sleep", 1)])
def test_frozen_extraction_is_copied_and_source_unchanged(tmp_path, variant, eligible):
    source = tmp_path / "source.db"
    rt = runtime._build_local_store_sqlite_runtime(source)
    rt.start()
    pipe.seed_gold_statements(str(source), "q", [
        {"holder": "Mei", "subject": "train", "predicate": "has_status", "object": "available"},
    ])
    with sqlite3.connect(source) as conn:
        conn.execute("UPDATE statements SET consolidation_state='volatile'")
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    # Hash the complete logical source, including any live WAL contents.
    def source_dump():
        with sqlite3.connect(source) as conn:
            return hashlib.sha256("\n".join(conn.iterdump()).encode()).hexdigest()

    before = source_dump()
    keepalive = []

    def make_pipeline(db_path):
        store = runtime._build_local_store_sqlite_runtime(Path(db_path))
        store.start()
        embedder = _core.StubEmbeddingAdapter(8)
        index = _core.SqliteBlobVectorIndex()
        keepalive.append((store, embedder, index))
        return store.adapter, embedder, index

    def forbidden_extract(*args):
        pytest.fail("frozen conditions must not re-extract")

    config = {"core": _core, "make_pipeline": make_pipeline, "extract": forbidden_extract,
              "answerer": lambda prompt, backbone: "0", "backbone": "stub", "k": 10,
              "now_iso": "2026-09-09T09:00:00Z"}
    record = {"item_id": "q", "question": "train has_status available",
              "options": ["available", "unknown"], "answer": 0, "history": []}
    row = controls.evaluate_variant(record, variant, source, config)
    assert row["ok"] is True
    assert row["before"]["state_review_eligible"] == 0
    assert row["after"]["state_review_eligible"] == eligible
    assert row["after"]["statement_count"] == 1
    assert row["trace"]["db_path"] != str(source)
    assert source_dump() == before


def test_backup_refuses_to_overwrite_source(tmp_path):
    source = tmp_path / "source.db"
    with sqlite3.connect(source) as conn:
        conn.execute("CREATE TABLE evidence (id INTEGER)")
    with pytest.raises(FileExistsError):
        controls.backup_database(source, source)


def test_frozen_fingerprint_rejects_uncheckpointed_wal(tmp_path):
    source = tmp_path / "source.db"
    with sqlite3.connect(source) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE evidence (id INTEGER)")
        conn.commit()
        with pytest.raises(ValueError, match="WAL"):
            controls.frozen_database_hash(source)
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        assert controls.frozen_database_hash(source) == controls.digest(source)

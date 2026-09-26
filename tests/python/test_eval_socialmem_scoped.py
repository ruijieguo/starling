"""Fresh reviewed ingestion is shared by both lifecycle variants."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import eval_ladder_pipeline as pipe
import eval_socialmem_scoped as scoped
from starling import _core, runtime


def test_scoped_run_extracts_once_and_freezes_before_both_queries(tmp_path):
    calls, alive = [], []

    def make(db_path):
        rt = runtime._build_local_store_sqlite_runtime(Path(db_path))
        rt.start()
        emb, index = _core.StubEmbeddingAdapter(8), _core.SqliteBlobVectorIndex()
        alive.append((rt, emb, index))
        return rt.adapter, emb, index

    def extract(adapter, record, backbone):
        calls.append(record["history"])
        pipe.seed_history_statements(str(adapter.db_path), record["item_id"], record["history"])

    rec = {"item_id": "q", "question": "what?", "answer_format": "long_form",
           "answer": "available", "options": [], "evaluation_protocol": {
               "status": "include", "sessions": [1], "id": "v1"},
           "history": [{"turn_id": "t1", "session_index": 1,
                        "speaker": "Mei", "text": "available"}]}
    config = {"core": _core, "make_pipeline": make, "extract": extract,
              "answerer": lambda *args: "available", "judge": lambda *args: True,
              "now_iso": "2099-01-01T00:00:00Z", "backbone": "stub"}
    rows = list(scoped.evaluate_record(rec, config, tmp_path))
    assert len(calls) == 1
    assert calls[0] == rec["history"]
    assert {r["variant"] for r in rows} == set(scoped.VARIANTS)
    pair = [r for r in rows if r["variant"].startswith("star_")]
    assert pair[0]["before"] == pair[1]["before"]
    rag = next(r for r in rows if r["variant"] == "rag_speakers")
    assert rag["source_turn_ids"] == ["t1"]
    assert all(r["ok"] for r in rows)
    assert all(Path(r["trace"]["db_path"]).is_file() for r in rows)


def test_unreviewed_and_out_of_scope_records_rejected_before_api(tmp_path):
    base = {"item_id": "q", "history": [{"session_index": 6}]}
    for rec in (base, {**base, "evaluation_protocol": {"status": "exclude"}},
                {**base, "evaluation_protocol": {"status": "include", "sessions": [1, 2]}}):
        with pytest.raises(ValueError):
            list(scoped.evaluate_record(rec, {}, tmp_path))


def test_repeat_judge_retains_disagreement_and_uses_fixed_majority():
    responses = iter(["NO", "YES", "YES"])
    receipts = []
    judge = scoped.repeated_judge(lambda *args, **kwargs: next(responses), receipts.append, 3)
    assert judge("question", "reference", "candidate", "stub") is True
    assert [r["accepted"] for r in receipts] == [False, True, True]
    assert len({r["prompt"] for r in receipts}) == 1


def test_empty_judge_result_is_an_error_not_a_negative():
    judge = scoped.repeated_judge(lambda *args, **kwargs: "", lambda row: None, 3)
    with pytest.raises(ValueError, match="verdict"):
        judge("question", "reference", "candidate", "stub")

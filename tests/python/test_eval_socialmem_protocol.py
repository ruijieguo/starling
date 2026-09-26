"""Reviewed session scope is applied before any evaluation stage sees history."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import eval_adapters as adapters
import eval_socialmem_protocol as protocol


def record():
    return {"item_id": "q", "question": "Based only on Sessions 1 through 2, what changed?",
            "answer_format": "long_form", "answer": "ready", "options": [],
            "source": {"network_id": "n"}, "history": [
                {"session_index": i, "message_index": 1, "turn_id": f"t{i}",
                 "speaker": "Mei", "text": f"SESSION_{i}", "observed_at": "2026-01-01T00:00:00Z"}
                for i in (1, 2, 3)],
            "gold_statements": [{"session_index": 2, "turn_id": "t2", "object": "SESSION_2"}]}


def decision():
    return {"item_id": "q", "question": record()["question"], "network_id": "n",
            "status": "include", "sessions": [1, 2], "reason": "Explicit question range."}


def test_reviewed_scope_filters_before_passthrough_without_mutation():
    source = record()
    before = deepcopy(source)
    scoped = protocol.apply_review(source, decision(), "v1")
    assert source == before
    assert [t["turn_id"] for t in scoped["history"]] == ["t1", "t2"]
    assert scoped["evaluation_protocol"]["omitted_turn_ids"] == ["t3"]
    assert scoped["question"] == source["question"]
    assert scoped["answer"] == source["answer"]
    assert adapters.adapt_passthrough([scoped], benchmark="socialmem")[0]["evaluation_protocol"] == scoped["evaluation_protocol"]


@pytest.mark.parametrize("change", [
    {"sessions": [1, 4]}, {"sessions": []}, {"sessions": [True]},
    {"question": "stale question"}, {"network_id": "other"}, {"status": "typo"},
])
def test_invalid_or_stale_review_fails(change):
    with pytest.raises(ValueError):
        protocol.apply_review(record(), {**decision(), **change}, "v1")


def test_out_of_scope_gold_requires_review_instead_of_leaking_to_oracle():
    source = record()
    source["gold_statements"][0].update(turn_id="t3", session_index=3)
    with pytest.raises(ValueError, match="gold"):
        protocol.apply_review(source, decision(), "v1")


def test_excluded_mc_keeps_original_answer_and_reason():
    source = {**record(), "answer_format": "multiple_choice", "answer": 1,
              "options": ["Mei", "Leon"]}
    excluded = protocol.apply_review(source, {**decision(), "status": "exclude",
                                              "reason": "Two roles but single-name options."}, "v1")
    assert excluded["answer"] == 1
    assert excluded["options"] == source["options"]
    assert excluded["evaluation_protocol"]["status"] == "exclude"


@pytest.mark.parametrize("stage", ["S_full", "S_rag", "S_star", "S_star_oracle"])
def test_out_of_scope_text_never_reaches_extraction_or_answer(stage, tmp_path):
    import eval_ladder as ladder
    import eval_ladder_pipeline as pipe
    from starling import _core, runtime

    rec = protocol.apply_review(record(), decision(), "v1")
    kept = []
    seen = []

    def pipeline(db_path):
        rt = runtime._build_local_store_sqlite_runtime(Path(db_path))
        rt.start()
        emb, index = _core.StubEmbeddingAdapter(8), _core.SqliteBlobVectorIndex()
        kept.append((rt, emb, index))
        return rt.adapter, emb, index

    def extract(adapter, item, backbone):
        assert [t["turn_id"] for t in item["history"]] == ["t1", "t2"]
        pipe.seed_history_statements(str(adapter.db_path), "q", item["history"])

    def answer(prompt, backbone):
        assert "SESSION_3" not in prompt
        seen.append(prompt)
        return "ready"

    config = {"core": _core, "make_pipeline": pipeline, "extract": extract,
              "answerer": answer, "judge": lambda *args: True}
    assert ladder._real_answer(stage, rec, 0, config) is True
    assert len(seen) == 1

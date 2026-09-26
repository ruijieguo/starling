"""Source-time diagnostics preserve scope without inventing statement times."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import eval_socialmem_temporal as temporal


@pytest.fixture
def record():
    return {"item_id": "q", "source": {"network_id": "n"},
            "evaluation_protocol": {"status": "include", "sessions": [1, 2]},
            "history": [
                {"turn_id": "n_s1_t0", "session_index": 1, "message_index": 0,
                 "speaker": "Claire", "text": "Ready to move?", "observed_at": "2025-01-01T09:00:00"},
                {"turn_id": "n_s1_t1", "session_index": 1, "message_index": 1,
                 "speaker": "Marcus", "text": "Not decided yet.", "observed_at": "2025-01-01T09:01:00"},
                {"turn_id": "n_s2_t0", "session_index": 2, "message_index": 0,
                 "speaker": "Marcus", "text": "A bit nervous.", "observed_at": "2025-02-01T09:00:00"},
            ]}


def test_session_units_keep_every_target_once_and_preserve_context(record):
    units = temporal.build_units(record, "Marcus", "session_context")
    assert [u["target_turn_ids"] for u in units] == [["n_s1_t1"], ["n_s2_t0"]]
    assert units[0]["turns"] == record["history"][:2]
    assert units[1]["turns"] == record["history"][2:]
    assert json.loads(units[0]["payload"])["turns"] == units[0]["turns"]
    assert units[0]["source_time_start"] == "2025-01-01T09:01:00"
    assert units[0]["source_time_end"] == "2025-01-01T09:01:00"


def test_session_target_units_exclude_other_speakers(record):
    units = temporal.build_units(record, "Marcus", "sessions")
    assert len(units) == 2
    assert all(t["speaker"] == "Marcus" for u in units for t in u["turns"])
    grouped = temporal.build_units(record, "Marcus", "grouped")
    assert grouped[0]["sessions"] == [1, 2]
    assert len(grouped[0]["target_turn_ids"]) == 2


def test_legacy_payload_is_byte_identical_to_existing_grouping(record):
    unit, = temporal.build_units(record, "Marcus", "legacy")
    assert unit["payload"] == "Marcus: Not decided yet.\nMarcus: A bit nervous."


@pytest.mark.parametrize("mutation", ["duplicate", "outside_scope", "reverse", "missing_time"])
def test_invalid_source_history_fails_before_extraction(record, mutation):
    changed = deepcopy(record)
    if mutation == "duplicate":
        changed["history"][1]["turn_id"] = changed["history"][0]["turn_id"]
    elif mutation == "outside_scope":
        changed["history"][2]["session_index"] = 3
    elif mutation == "reverse":
        changed["history"].reverse()
    else:
        changed["history"][1]["observed_at"] = ""
    with pytest.raises(ValueError):
        temporal.build_units(changed, "Marcus", "sessions")


def test_source_ranges_only_follow_selected_evidence(record):
    units = temporal.build_units(record, "Marcus", "sessions")
    receipt = {"engram_ref": "eng", "unit": units[0]}
    rows = {"s": {"tenant_id": "default", "evidence_json": '[{"engram_ref":"eng"}]'}}
    recall = {"statement_ids": ["s"], "labels": ["FACT"], "block": "[FACT] statement", "abstained": False}
    annotated = temporal.annotate_sources(recall, rows, [receipt])
    assert annotated[0]["statement_id"] == "s"
    assert annotated[0]["native_line"] == "[FACT] statement"
    assert "sessions=1" in annotated[0]["line"]
    assert "2025-02" not in annotated[0]["line"]
    assert "Not decided" not in annotated[0]["line"]
    rows["s"]["evidence_json"] = '[{"engram_ref":"unmapped"}]'
    with pytest.raises(ValueError, match="unmapped"):
        temporal.annotate_sources(recall, rows, [receipt])


def test_structured_prompt_cannot_receive_gold(record):
    record["answer"] = "SECRET GOLD"
    record["question"] = "SECRET QUESTION"
    unit, = temporal.build_units(record, "Marcus", "grouped")
    prompt = temporal.unit_prompt(unit, "{convo}")
    assert "SECRET" not in prompt
    assert "Marcus" in prompt and "target_turn_ids" in prompt


def test_paired_presentations_preserve_native_abstention():
    result = {"recall": {"abstained": True, "statement_ids": [],
                         "block": "[ABSTAIN] no eligible memories"}, "source_annotations": []}
    assert temporal.presentation_lines(result, "native") == ["[ABSTAIN] no eligible memories"]
    assert temporal.presentation_lines(result, "source_ranges") == ["[ABSTAIN] no eligible memories"]


@pytest.mark.parametrize("sessions", [[1, 2, 3, 4], [1, 2, 3, 4, 5, 6]])
def test_q9_diagnostic_refuses_different_reviewed_scope(record, sessions):
    record["item_id"] = "Q9_a0b1c2d3"
    record["source"]["network_id"] = "grp_f4a5b6c7"
    record["evaluation_protocol"]["sessions"] = sessions
    with pytest.raises(ValueError, match="Sessions 1-5"):
        temporal.validate_diagnostic_scope(record)


def test_native_unit_persistence_preserves_source_bytes_and_holder(record, tmp_path):
    from starling import _core, runtime

    rt = runtime._build_local_store_sqlite_runtime(tmp_path / "native.db")
    rt.start()
    unit = temporal.build_units(record, "Marcus", "session_context")[0]
    raw = json.dumps([{"holder": "Marcus", "holder_perspective": "FIRST_PERSON",
                       "subject": "Marcus", "subject_kind": "cognizer", "cognizer_kind": "human",
                       "predicate": "believes", "object": "not decided yet", "modality": "BELIEVES",
                       "polarity": "POS", "nesting_depth": 0}])
    receipt = temporal.persist_unit(_core, rt.adapter, unit, "Extract:\n{convo}", raw,
                                    "2026-09-09T16:00:00Z")
    assert not receipt["extraction_failed"] and len(receipt["statement_ids"]) == 1
    rows = temporal.statement_rows(tmp_path / "native.db")
    assert len(rows) == 1 and rows[0]["holder_id"] == "Marcus"
    assert rows[0]["object_value"] == "not decided yet"
    evidence = json.loads(rows[0]["evidence_json"])
    assert evidence[0]["engram_ref"] == receipt["engram_ref"]
    recall = {"statement_ids": [rows[0]["id"]], "labels": ["FACT"],
              "block": "[FACT] Marcus believes not decided yet", "abstained": False}
    annotated = temporal.annotate_sources(recall, {r["id"]: r for r in rows}, [receipt])
    assert annotated[0]["ranges"][0]["from"] == "2025-01-01T09:01:00"
    with temporal.sqlite3.connect(tmp_path / "native.db") as conn:
        payload, = conn.execute("SELECT payload_inline FROM engrams WHERE id=? AND tenant_id='default'",
                               (receipt["engram_ref"],)).fetchone()
    assert bytes(payload) == unit["payload"].encode()
    assert not rows[0]["observed_at"].startswith("2025-")


@pytest.mark.parametrize("variant", temporal.VARIANTS)
def test_native_variant_archives_retrieval_and_source_evidence(record, tmp_path, variant):
    from starling import _core

    # Identical text guarantees cosine=1 with the deterministic random-vector stub.
    record["question"] = "Marcus believes not decided on plan 0"
    units = temporal.build_units(record, "Marcus", variant)
    llm = _core.FakeLLMAdapter()
    for i, unit in enumerate(units):
        raw = json.dumps([{"holder": "Marcus", "holder_perspective": "FIRST_PERSON",
                           "subject": "Marcus", "subject_kind": "cognizer", "cognizer_kind": "human",
                           "predicate": "believes", "object": f"not decided on plan {i}",
                           "modality": "BELIEVES", "polarity": "POS", "nesting_depth": 0}])
        prompt = temporal.unit_prompt(unit, "Extract:\n{convo}")
        llm.set_response(_core.Extractor.compute_prompt_input_hash(prompt), raw)
    result = temporal.evaluate_variant(
        _core, llm, _core.StubEmbeddingAdapter(8), record, variant, units,
        "Extract:\n{convo}", tmp_path, "2099-01-01T00:00:00Z")
    assert len(result["before"]) == len(units)
    assert result["embedding"]["embedded"] == len(units)
    assert not result["recall"]["abstained"]
    assert result["recall"]["statement_ids"] == [
        row["statement_id"] for row in result["source_annotations"]]
    assert result["recall"]["block"].splitlines() == [
        row["native_line"] for row in result["source_annotations"]]
    assert temporal.controls.frozen_database_hash(tmp_path / f"{variant}.db") == result["database_sha256"]

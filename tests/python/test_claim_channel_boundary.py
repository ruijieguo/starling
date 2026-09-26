"""The native remember orchestrator isolates experimental and legacy formats."""
import json
import sqlite3

from starling import _core, runtime


def test_native_three_channel_remember_preserves_general_facts_with_claim_mode(tmp_path):
    assert hasattr(_core.ValidationPolicy(), "semantic_claim_contract")
    database = tmp_path / "channels.db"
    rt = runtime._build_local_store_sqlite_runtime(database)
    rt.start()
    source = "Mina: Water boils at 100 C."
    fake = _core.FakeLLMAdapter()
    fake.set_response(_core.Extractor.compute_prompt_input_hash(
        _core.claim_extraction_prompt(source, "Mina")),
        '{"schema_version":2,"statements":[]}', True, "")
    fake.set_response(_core.Extractor.compute_prompt_input_hash("GENERAL::Mina::" + source),
        json.dumps([dict(holder="Mina", holder_perspective="FIRST_PERSON", subject="water",
                        subject_kind="entity", predicate="has_value", object="boiling point 100 C",
                        modality="BELIEVES", polarity="POS", nesting_depth=0)]), True, "")
    fake.set_response(_core.Extractor.compute_prompt_input_hash("EPISODIC::" + source), "[]", True, "")
    policy = _core.ValidationPolicy()
    policy.semantic_claim_contract = policy.preserve_text_objects = True
    prepared = _core.memory_remember_prepare(rt.adapter, tenant_id="default", holder_id="Mina",
        interlocutor="", adapter_name="test", source_prefix="claims", created_at_iso8601="2026-09-11T10:00:00Z",
        payload=source.encode())
    extracted = _core.memory_remember_extract_all(rt.adapter, fake, "unused {convo}",
        "EPISODIC::{passage}", "GENERAL::{self}::{convo}", holder_id="Mina", payload=source.encode(), policy=policy)
    native_receipt = json.loads(_core.memory_remember_bundle_receipt(extracted))
    assert set(native_receipt["channels"]) == {"belief", "general_fact", "episodic"}
    assert native_receipt["channels"]["episodic"]["response"]["raw_response"] == "[]"
    receipt = _core.memory_remember_commit_all(rt.adapter, fake, tenant_id="default", holder_id="Mina",
        interlocutor="", prepared=prepared, extracted=extracted, policy=policy)
    assert not receipt["extraction_failed"]
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT predicate,object_value,semantic_claim_json FROM statements").fetchall() == [
            ("has_value", "boiling point 100 C", None)]

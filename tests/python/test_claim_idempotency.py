"""Equal object text must retain distinct source actors and clauses."""
import json
import sqlite3

from starling import _core, runtime


def test_native_claim_replay_key_distinguishes_actor_and_preserves_exact_noop(tmp_path):
    path = tmp_path / "identity.db"
    rt = runtime._build_local_store_sqlite_runtime(path)
    rt.start()
    source = "Mina: Jules said she feels sad about the move.\nMina: Nora said she feels sad about the move."
    policy = _core.ValidationPolicy()
    policy.semantic_claim_contract = policy.preserve_text_objects = True
    policy.extra_core_predicates = ["feels"]
    prepared = _core.memory_remember_prepare(rt.adapter, tenant_id="default", holder_id="Mina",
        interlocutor="", adapter_name="test", source_prefix="identity", created_at_iso8601="2026-09-11T10:00:00Z",
        payload=source.encode())

    def commit(actor, clause):
        row = dict(holder="Mina", holder_perspective="QUOTED", subject=actor,
            subject_kind="cognizer", predicate="feels", object="sad about the move",
            modality="BELIEVES", polarity="POS", nesting_depth=0,
            evidence=dict(actor=actor, attributed_to="Mina", clause_id=clause,
                assertion_scope="REPORTED", scope_markers=["REPORTED"], time_text="", event_time=None))
        raw = json.dumps(dict(schema_version=2, statements=[row]))
        parsed = json.loads(_core.claim_parse_response(raw, source, "Mina"))
        assert not parsed["errors"] and len(parsed["statements"]) == 1
        admission = _core.claim_admission_prompt(source, json.dumps(dict(schema_version=2, statements=parsed["statements"])))
        fake = _core.FakeLLMAdapter()
        fake.set_response(_core.Extractor.compute_prompt_input_hash(_core.claim_extraction_prompt(source, "Mina")), raw)
        fake.set_response(_core.Extractor.compute_prompt_input_hash(admission),
            '{"schema_version":1,"decisions":[{"index":0,"retain":true,"reason":"supported"}]}')
        extracted = _core.memory_extract_llm(rt.adapter, fake, "", "Mina", source.encode(), policy)
        return _core.memory_remember_commit(rt.adapter, fake, tenant_id="default", holder_id="Mina",
            interlocutor="", prepared=prepared, llm_result=extracted, policy=policy)

    first = commit("Jules", "c0")
    second = commit("Nora", "c1")
    assert len(first["statement_ids"]) == len(second["statement_ids"]) == 1
    assert first["statement_ids"] != second["statement_ids"]
    assert commit("Jules", "c0")["statement_ids"] == []
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT subject_id,review_status FROM statements ORDER BY subject_id").fetchall() == [
            ("Jules", "approved"), ("Nora", "approved")]

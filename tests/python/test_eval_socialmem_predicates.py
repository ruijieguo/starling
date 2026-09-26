"""Experimental predicate factors must stay isolated and use native policy."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import eval_socialmem_predicates as experiment


def test_prompt_factors_are_independent_and_baseline_is_exact():
    from starling.extractor.prompts import EXTRACTION_PROMPT

    prompts = experiment.belief_prompts(EXTRACTION_PROMPT)
    assert prompts["baseline"] == EXTRACTION_PROMPT
    assert experiment.with_fidelity(prompts["vocabulary"]) == prompts["combined"]
    assert experiment.with_vocabulary(prompts["fidelity"]) == prompts["combined"]
    assert all(p.count("{convo}") == 1 for p in prompts.values())
    assert "Drop hedges, modifiers, and elaborations" in prompts["vocabulary"]
    assert "Drop hedges, modifiers, and elaborations" not in prompts["fidelity"]
    assert "uncertain_about" not in prompts["fidelity"]


def test_factor_rewrite_rejects_a_drifted_prompt():
    with pytest.raises(ValueError):
        experiment.with_vocabulary("unrecognized template")
    with pytest.raises(ValueError):
        experiment.with_fidelity("unrecognized template")


def test_fixed_synthetic_cases_do_not_enter_extraction_with_gold():
    cases = experiment.synthetic_cases()
    assert len(cases) == len({c["id"] for c in cases}) == 16
    assert all("Marcus" not in c["passage"] and "Swindon" not in c["passage"] for c in cases)
    case = {**cases[0], "question": "SECRET QUESTION", "answer": "SECRET GOLD"}
    rendered = experiment.render_prompts({"belief": "Input: {convo}"}, case["holder"], case["passage"])
    assert rendered == {"belief": "Input: " + case["passage"]}


def raw_claim(predicate="feels", object_value="anxious about the examination"):
    return json.dumps([{"holder": "Nora", "holder_perspective": "FIRST_PERSON",
                        "subject": "Nora", "subject_kind": "cognizer", "cognizer_kind": "human",
                        "predicate": predicate, "object": object_value, "modality": "BELIEVES",
                        "polarity": "POS", "nesting_depth": 0}])


@pytest.mark.parametrize("arm,status", [("baseline", "review_requested"), ("combined", "approved")])
def test_native_replay_threads_additive_policy_without_rewriting_raw(tmp_path, arm, status):
    from starling import _core, runtime

    rt = runtime._build_local_store_sqlite_runtime(tmp_path / "native.db")
    rt.start()
    outcome = experiment.persist(
        _core, rt.adapter, "Nora", "Nora: I am anxious.", {"belief": "Extract {convo}"},
        {"belief": raw_claim()}, arm, "2099-01-01T00:00:00Z")
    assert not outcome["extraction_failed"] and len(outcome["statement_ids"]) == 1
    row, = experiment.temporal.statement_rows(tmp_path / "native.db")
    assert row["predicate"] == "feels" and row["review_status"] == status
    assert row["subject_id"] == row["holder_id"] == "Nora"


def test_three_channel_replay_uses_each_exact_response(tmp_path):
    from starling import _core, runtime

    rt = runtime._build_local_store_sqlite_runtime(tmp_path / "native.db")
    rt.start()
    templates = {"belief": "Belief: {convo}", "general_fact": "Fact {self}: {convo}",
                 "episodic": "Event: {passage}"}
    raw = {"belief": raw_claim(), "general_fact": raw_claim("has_property", "ready"),
           "episodic": '[{"actor":"Nora","actor_kind":"cognizer","action":"open",'
                       '"theme":"cabinet","location":null,"participants":["Nora"],"time":null}]'}
    result = experiment.persist(_core, rt.adapter, "Nora", "Nora opened the cabinet.",
                                templates, raw, "combined", "2099-01-01T00:00:00Z")
    assert not result["extraction_failed"]
    rows = experiment.temporal.statement_rows(tmp_path / "native.db")
    assert {r["predicate"] for r in rows} == {"feels", "has_property", "open"}
    assert len(result["statement_ids"]) == 3


def test_trial_policy_does_not_modify_core_defaults():
    from starling import _core

    assert list(experiment.policy(_core, "combined").extra_core_predicates) == list(experiment.EXTRA_PREDICATES)
    assert list(experiment.policy(_core, "baseline").extra_core_predicates) == []
    assert list(_core.ValidationPolicy().extra_core_predicates) == []


def test_native_case_judges_only_stored_semantics_and_archives(tmp_path):
    from starling import _core

    (tmp_path / "databases").mkdir()
    llm = _core.FakeLLMAdapter()
    case = {"track": "synthetic", "id": "test", "holder": "Nora", "passage": "Nora: I am anxious.",
            "question": "What is Nora feeling?", "answer": "Nora is anxious."}
    prompt = "Extract: {convo}"
    llm.set_response(_core.Extractor.compute_prompt_input_hash(prompt.replace("{convo}", case["passage"])), raw_claim())
    result = experiment.evaluate_case(_core, llm, lambda *a, **k: "YES", case, "combined", prompt,
                                      tmp_path, "2099-01-01T00:00:00Z")
    candidate, = json.loads(result["candidate"])
    assert candidate["predicate"] == "feels" and candidate["holder_id"] == "Nora"
    assert set(candidate) == set(experiment.SEMANTIC_FIELDS)
    assert result["fidelity_judgment"]["acceptances"] == 3
    assert experiment.controls.frozen_database_hash(tmp_path / result["database"]) == result["database_sha256"]


def test_three_channel_scoped_flow_retrieves_native_memory_before_answering(tmp_path):
    from starling import _core

    (tmp_path / "databases").mkdir()
    record = {"item_id": "test", "question": "Nora feels anxious about the examination",
              "answer": "Nora is anxious about the examination.", "source": {"network_id": "test"},
              "evaluation_protocol": {"status": "include", "sessions": [1]},
              "history": [{"speaker": "Nora", "text": "I am anxious about the examination.",
                           "turn_id": "t1", "session_index": 1, "message_index": 1,
                           "observed_at": "2025-01-01T10:00:00"}]}
    templates = {"belief": "Belief: {convo}", "general_fact": "Facts {self}: {convo}",
                 "episodic": "Events: {passage}"}
    units = experiment.source_units(record)
    llm = _core.FakeLLMAdapter()
    for channel, prompt in experiment.render_prompts(templates, "Nora", units[0]["payload"]).items():
        llm.set_response(_core.Extractor.compute_prompt_input_hash(prompt), raw_claim() if channel == "belief" else "[]")

    def chat(prompt, model, max_tokens):
        if max_tokens == 512:
            assert "Nora feels anxious about the examination" in prompt
            return "Nora is anxious about the examination."
        return "YES"

    result = experiment.evaluate_scoped(_core, llm, _core.StubEmbeddingAdapter(8), chat,
                                        record, units, "combined", templates, tmp_path, "2099-01-01T00:00:00Z")
    assert result["judgment"]["ok"]
    archived = experiment.extraction.load(tmp_path / "scoped_test_combined.json")
    assert len(archived["recall"]["statement_ids"]) == 1
    assert archived["embedding"]["embedded"] == 1
    assert len(archived["pipelines"]) == 2


def test_invalid_judge_response_is_archived_before_validation(tmp_path):
    with pytest.raises(ValueError, match="verdict"):
        experiment.judge(lambda *a, **k: "MAYBE", "question", "reference", "candidate",
                         {"track": "synthetic", "id": "q", "arm": "baseline"}, tmp_path)
    raw, = experiment.extraction.load_lines(tmp_path / "judge_responses.jsonl")
    assert raw["raw"] == "MAYBE" and raw["repeat"] == 0


def test_native_database_survives_downstream_failure(tmp_path, monkeypatch):
    from starling import _core

    (tmp_path / "databases").mkdir()
    llm = _core.FakeLLMAdapter()
    case = {"track": "synthetic", "id": "test", "holder": "Nora", "passage": "Nora: anxious",
            "question": "emotion?", "answer": "anxious"}
    llm.set_response(_core.Extractor.compute_prompt_input_hash("Extract: Nora: anxious"), raw_claim())

    def fail(path):
        raise RuntimeError("downstream failure")

    monkeypatch.setattr(experiment, "pipeline_rows", fail)
    with pytest.raises(RuntimeError, match="downstream failure"):
        experiment.evaluate_case(_core, llm, lambda *a, **k: "YES", case, "combined",
                                 "Extract: {convo}", tmp_path, "2099-01-01T00:00:00Z")
    db = tmp_path / "databases/synthetic_test_combined.db"
    row, = experiment.temporal.statement_rows(db)
    assert row["predicate"] == "feels"


def test_verifier_accepts_default_sleep_gists_and_rejects_broken_lineage(tmp_path):
    from starling import _core, runtime
    import verify_socialmem_predicates as verifier

    database = tmp_path / "native.db"
    rt = runtime._build_local_store_sqlite_runtime(database)
    rt.start()
    now = "2099-01-01T00:00:00Z"
    for holder in ("Alice", "Bob", "Carol"):
        claim = json.loads(raw_claim("prefers", "tea"))
        claim[0].update(holder=holder, subject=holder, modality="DESIRES")
        experiment.persist(_core, rt.adapter, holder, f"{holder}: I prefer tea.",
                           {"belief": "{convo}"}, {"belief": json.dumps(claim)}, "baseline", now)
    before = experiment.temporal.statement_rows(database)
    sleep = _core.ReplayScheduler(rt.adapter).run_sleep(now)
    after = experiment.temporal.statement_rows(database)
    assert sleep.abstracted == 1 and len(after) == len(before) + 1
    result = {"sleep": {"abstracted": sleep.abstracted}}
    verifier.check_sleep_rows(result, before, after)
    gist, = [r for r in after if r["provenance"] == "consolidation_abstract"]
    gist["derived_from_json"] = '["missing-parent"]'
    with pytest.raises(AssertionError):
        verifier.check_sleep_rows(result, before, after)


def test_verifier_checks_event_time_and_episodic_metadata(tmp_path):
    import sqlite3
    from starling import _core, runtime
    import verify_socialmem_predicates as verifier

    database = tmp_path / "events.db"
    rt = runtime._build_local_store_sqlite_runtime(database)
    rt.start()
    unit = {"holder": "Nora", "payload": "Nora opened the cabinet in the lab on 2026-01-01."}
    templates = {"belief": "B {convo}", "general_fact": "G {self} {convo}", "episodic": "E {passage}"}
    raw = {"belief": "[]", "general_fact": "[]", "episodic": json.dumps([
        {"actor": "Nora", "actor_kind": "cognizer", "action": "open", "theme": "cabinet",
         "location": "lab", "participants": ["Nora"], "time": "2026-01-01"}])}
    now = "2099-01-01T00:00:00Z"
    receipt = experiment.persist(_core, rt.adapter, unit["holder"], unit["payload"], templates, raw, "baseline", now)
    receipts = [{**receipt, "unit": unit}]
    before = experiment.temporal.statement_rows(database)

    def check():
        verifier.check_native_replay(_core, receipts, before, [raw], templates, "baseline", now, database)

    check()
    original_time = before[0]["event_time_start"]
    before[0]["event_time_start"] = "2027-12-31"
    with pytest.raises(AssertionError):
        check()
    before[0]["event_time_start"] = original_time
    with sqlite3.connect(database) as conn:
        conn.execute("UPDATE episodic_events SET location='elsewhere'")
    with pytest.raises(AssertionError):
        check()


def test_verifier_checks_native_empty_store_abstention(tmp_path):
    from starling import _core, runtime
    import verify_socialmem_predicates as verifier

    rt = runtime._build_local_store_sqlite_runtime(tmp_path / "empty.db")
    rt.start()
    now = "2099-01-01T00:00:00Z"
    recall = experiment.pipe.recall_block(
        _core, "S_star", adapter=rt.adapter, embedder=_core.StubEmbeddingAdapter(8),
        index=_core.SqliteBlobVectorIndex(), question="Where is the cabinet?", history=[], now_iso=now)
    result, manifest = {"after": [], "recall": recall}, {"query_time": now}
    assert verifier.check_recall(result, manifest) == 0
    recall["labels"] = ["FACT"]
    with pytest.raises(AssertionError):
        verifier.check_recall(result, manifest)
    recall["labels"] = []
    recall["block"] = "Injected candidate answer"
    with pytest.raises(AssertionError):
        verifier.check_recall(result, manifest)


def test_duplicate_arrays_are_preserved_as_native_channel_failure(tmp_path):
    from starling import _core, runtime

    raw = "[]\n```json\n[]\n```"
    with pytest.raises(json.JSONDecodeError, match="Extra data"):
        experiment.extraction.parse_response(raw)
    database = tmp_path / "native.db"
    rt = runtime._build_local_store_sqlite_runtime(database)
    rt.start()
    with pytest.raises(ValueError, match="native extraction persistence failed"):
        experiment.persist(_core, rt.adapter, "Nora", "Nora is anxious.",
                           {"belief": "B {convo}", "general_fact": "G {self} {convo}", "episodic": "E {passage}"},
                           {"belief": raw_claim(), "general_fact": raw, "episodic": "[]"},
                           "combined", "2099-01-01T00:00:00Z")
    assert len(experiment.temporal.statement_rows(database)) == 1

"""Diagnostic protocol integrity: fixed candidates, evidence and reproducible scores."""
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))


@pytest.fixture
def evaluation():
    return importlib.import_module("eval_socialmem_claim_contract")


def case(**changes):
    return {"id": "fixture", "track": "fixed_controls", "holder": "Mina",
            "passage": "Mina: 我很担心发布。", "expected_keep": True, **changes}


def row(**changes):
    return {"holder": "Mina", "holder_perspective": "FIRST_PERSON", "subject": "Mina",
            "subject_kind": "cognizer", "predicate": "feels", "object": "担心发布",
            "modality": "BELIEVES", "polarity": "POS", "nesting_depth": 0, **changes}


class PromptCore:
    @staticmethod
    def claim_source_units(source):
        return json.dumps([{"clause_id": "c0", "text": source, "byte_start": 0,
            "byte_end": len(source.encode()), "payload_hash": hashlib.sha256(source.encode()).hexdigest()}])

    @staticmethod
    def claim_extraction_prompt(source, holder):
        return json.dumps({"source": source, "holder": holder}, ensure_ascii=False)

    @staticmethod
    def claim_admission_prompt(source, candidates):
        return json.dumps({"source": source, "candidates": json.loads(candidates)}, ensure_ascii=False)


def test_fixed_schedule_counts_injection_separately(evaluation):
    inputs = {k: [{"id": str(i), "track": k} for i in range(n)]
              for k, n in (("p1", 50), ("synthetic", 16), ("scoped", 10), ("fixed_controls", 64))}
    assert evaluation.schedule_counts(inputs) == {
        "records": 140, "extraction": 76, "injected_controls": 64,
        "admission_max": 140, "answer": 8, "judge": 120}
    inputs["p1"].pop()
    with pytest.raises(ValueError, match="cohort"):
        evaluation.schedule_counts(inputs)


def test_judge_consistency_uses_only_valid_pairs_of_the_same_prompt(evaluation):
    def group(values, prompts=None):
        return {"judgment": {"votes": [
            {"repeat": i, "valid": value is not None, "accepted": value,
             "prompt": prompts[i] if prompts else "same prompt"}
            for i, value in enumerate(values)]}}
    result = evaluation.judge_consistency([
        group([True, True, False]), group([False, False, False]),
        group([True, None, True]), group([None, None, False]),
        group([True, True], ["prompt A", "prompt B"]),
    ])
    assert result == {"groups": 5, "comparable_groups": 3, "unanimous_groups": 2,
        "invalid_votes": 3, "mismatched_groups": 1, "valid_pairs": 7,
        "agreeing_pairs": 5, "pairwise_agreement": pytest.approx(5 / 7)}


def test_judge_consistency_empty_or_duplicate_votes_do_not_invent_agreement(evaluation):
    votes = [{"repeat": 0, "valid": True, "accepted": True, "prompt": "p"}] * 2
    result = evaluation.judge_consistency([{"judgment": {"votes": votes}}])
    assert result["mismatched_groups"] == 1
    assert result["valid_pairs"] == 0 and result["pairwise_agreement"] is None
    assert evaluation.judge_consistency([])["pairwise_agreement"] is None


def test_synthetic_semantic_denominator_excludes_pipeline_and_judge_failures(evaluation):
    def entry(native_ok=True, failed=0):
        return {"id": str(failed) + str(native_ok), "arm": "contract", "native_ok": native_ok,
                "judgment": {"ok": True, "failed": failed, "votes": []}}
    result = evaluation.summarize({"fixed_controls": []}, [],
        [entry(), entry(False), entry(failed=1)], [], [])
    metric = result["synthetic"]["contract"]
    assert metric["cases"] == 3 and metric["majority"] == 2  # original strict metric
    assert metric["valid_cases"] == 1 and metric["valid_majority"] == 1
    assert metric["semantic_accuracy"] == 1.0
    assert result["synthetic"]["frozen"]["semantic_accuracy"] is None


def test_source_prompts_do_not_include_qa_gold_or_control_labels(evaluation):
    c = case(question="SECRET QUESTION", answer="SECRET GOLD", record={"gold": "SECRET"})
    candidate = row(evidence={"clause_id": "c0", "actor": "Mina",
        "assertion_scope": "ASSERTED", "scope_markers": ["ASSERTED"], "time_text": "", "event_time": None})
    prompts = evaluation.source_prompts(PromptCore, c, [candidate])
    assert all("SECRET" not in p and "expected_keep" not in p for p in prompts.values())
    assert c["passage"] in prompts["extraction"]
    assert {k: v for k, v in candidate.items() if k != "evidence"} == row()
    assert candidate["evidence"]["event_time"] is None


def test_technical_failures_never_score_correct_negative(evaluation):
    cases = [case(id=str(i), expected_keep=False) for i in range(3)]
    results = [
        {"native_ok": False, "outcome": "technical_failure", "rows": []},
        {"native_ok": True, "outcome": "semantic_rejection", "rows": []},
        {"native_ok": True, "outcome": "admitted", "rows": [row()]},
    ]
    metrics = evaluation.control_scores(cases, results)
    assert metrics["cases"] == 3 and metrics["correct"] == 1
    assert metrics["technical_failures"] == 1 and metrics["false_accepts"] == 1
    assert metrics["true_negatives"] == 1


def test_judge_projection_preserves_duplicate_claims_but_ignores_uuid_order(evaluation):
    rename = {"holder": "holder_id", "subject": "subject_id", "object": "object_value"}
    stored = {rename.get(k, k): v for k, v in row().items()}
    rows = [{**stored, "id": "a"}, {**stored, "id": "b"},
            {**stored, "id": "c", "polarity": "NEG"}]
    assert evaluation.judge_candidate(rows) == evaluation.judge_candidate(list(reversed(rows)))
    assert evaluation.judge_candidate(rows) != evaluation.judge_candidate(rows[1:])


def test_evidence_exact_utf8_hash_time_and_tenant(evaluation):
    c = case()
    evidence = {"schema_version": 1, "actor": "Mina", "clause_id": "c0",
        "source_span": {"engram_ref": "e1", "span_start": 0,
                        "span_end": len(c["passage"].encode()),
                        "source_hash": hashlib.sha256(c["passage"].encode()).hexdigest()},
        "source_time": "2026-09-12T00:00:00Z", "event_time": None,
        "assertion_scope": "ASSERTED", "scope_markers": ["ASSERTED"],
        "relation_modality": "BELIEVES", "relation_polarity": "POS", "time_text": ""}
    stored = {"id": "s1", "tenant_id": "default", "holder_id": "Mina", "subject_id": "Mina",
              "holder_perspective": "first_person", "modality": "believes", "polarity": "pos",
              "semantic_claim_json": json.dumps(evidence)}
    engram = {"id": "e1", "tenant_id": "default", "holder_id": "Mina",
              "payload": c["passage"], "created_at": evidence["source_time"]}
    assert evaluation.check_evidence(PromptCore, c, stored, engram) == evidence
    for field, bad in (("tenant_id", "other"), ("holder_id", "Jules")):
        with pytest.raises(ValueError):
            evaluation.check_evidence(PromptCore, c, {**stored, field: bad}, engram)
    evidence["source_span"]["span_end"] -= 1
    with pytest.raises(ValueError, match="span"):
        evaluation.check_evidence(PromptCore, c, {**stored, "semantic_claim_json": json.dumps(evidence)}, engram)


def test_historical_verification_uses_frozen_artifacts_not_current_binary(evaluation, tmp_path):
    (tmp_path / "source_archive").mkdir()
    artifact = tmp_path / "inputs.json"
    artifact.write_text('{"fixture":true}')
    fingerprint = hashlib.sha256(artifact.read_bytes()).hexdigest()
    (tmp_path / "manifest.json").write_text(json.dumps({"status": "complete", "core_sha256": "old-core"}))
    (tmp_path / "verification.json").write_text(json.dumps({"status": "verified",
        "artifact_sha256": {"inputs.json": fingerprint}}))
    assert evaluation.verify_historical(tmp_path)["core_sha256"] == "old-core"
    artifact.write_text('{"fixture":false}')
    with pytest.raises(ValueError, match="artifact"):
        evaluation.verify_historical(tmp_path)


def test_artifact_verifier_rejects_tampering_and_path_escape(evaluation, tmp_path):
    file = tmp_path / "calls.jsonl"
    file.write_text('{}\n')
    manifest = {"calls.jsonl": hashlib.sha256(file.read_bytes()).hexdigest()}
    evaluation.verify_artifacts(tmp_path, manifest)
    file.write_text('{"changed":true}\n')
    with pytest.raises(ValueError, match="artifact"):
        evaluation.verify_artifacts(tmp_path, manifest)
    with pytest.raises(ValueError, match="path"):
        evaluation.verify_artifacts(tmp_path, {"../escape": "anything"})


def test_error_status_does_not_confuse_quality_rejection_with_technical_failure(evaluation):
    clean = [{"native_ok": True, "outcome": "semantic_rejection", "evidence_errors": [],
              "base_semantics_preserved": True}]
    counts = evaluation.failure_counts(clean, [], [])
    assert evaluation.completion_status(counts) == "complete"
    dirty = [{**clean[0], "native_ok": False, "outcome": "technical_failure"}]
    assert evaluation.completion_status(evaluation.failure_counts(dirty, [], [])) == "complete_with_errors"


def test_native_database_replay_and_verifier_reject_changed_claim(evaluation, tmp_path):
    from starling import _core

    assert hasattr(_core, "claim_extraction_receipt"), "native receipt binding is required for replay"
    assert importlib.util.find_spec("verify_socialmem_claim_contract"), "native archive verifier missing"
    verifier = importlib.import_module("verify_socialmem_claim_contract")
    c = case(track="synthetic")
    candidate = row(evidence={"clause_id": "c0", "actor": "Mina", "assertion_scope": "ASSERTED",
        "scope_markers": ["ASSERTED"], "time_text": "", "event_time": None})
    raw = json.dumps({"schema_version": 2, "statements": [candidate]})
    parsed = json.loads(_core.claim_parse_response(raw, c["passage"], c["holder"], True))
    assert not parsed["errors"]
    prompts = evaluation.source_prompts(_core, c, parsed["statements"])
    fake = _core.FakeLLMAdapter()
    fake.set_default_response("", False, "unrecorded request")
    fake.set_response(_core.Extractor.compute_prompt_input_hash(prompts["extraction"]), raw)
    fake.set_response(_core.Extractor.compute_prompt_input_hash(prompts["admission"]),
        '{"schema_version":1,"decisions":[{"index":0,"retain":true,"reason":"supported"}]}')
    (tmp_path / "databases").mkdir()
    result = evaluation.evaluate_case(_core, c, None, {"baseline": "{convo}"}, tmp_path, fake)
    assert result["native_ok"] and len(result["rows"]) == 1
    assert result["evidence_errors"] == []
    verifier.check_case(_core, tmp_path, c, None, {"baseline": "{convo}"}, result)
    result["rows"][0]["object_value"] = "invented claim"
    with pytest.raises(ValueError):
        verifier.check_case(_core, tmp_path, c, None, {"baseline": "{convo}"}, result)


def test_linked_context_uses_only_native_authorized_excerpts(evaluation):
    recall = {"block": "- feels: worried", "evidence_links": [
        {"statement_id": "s1", "clause_id": "c0", "source_excerpt": "Mina: I am worried."}]}
    assert "Mina: I am worried." in evaluation.linked_context(recall)
    del recall["evidence_links"][0]["source_excerpt"]
    with pytest.raises(ValueError, match="authorized"):
        evaluation.linked_context(recall)


def test_verifier_rejects_counter_reset_and_unobserved_request_counts(evaluation):
    verifier = importlib.import_module("verify_socialmem_claim_contract")
    zero = {"request_count": 0, "embed_calls": 0, "batch_calls": 0}
    first = {"request_count": 5, "embed_calls": 2, "batch_calls": 1}
    final = {"request_count": 8, "embed_calls": 3, "batch_calls": 2}
    qa = [{"embedding_counts_before": zero, "embedding_counts_after": first},
          {"embedding_counts_before": first, "embedding_counts_after": final}]
    assert hasattr(verifier, "check_embedding_counts"), "embedding counter audit missing"
    verifier.check_embedding_counts(qa, zero, final, "real")
    qa[1]["embedding_counts_after"] = zero
    with pytest.raises(ValueError, match="counter"):
        verifier.check_embedding_counts(qa, zero, final, "real")
    unavailable = {key: None for key in zero}
    with pytest.raises(ValueError, match="counter"):
        verifier.check_embedding_counts([], unavailable, unavailable, "real")


def test_replay_audit_includes_semantic_rejection_diagnostics(evaluation):
    verifier = importlib.import_module("verify_socialmem_claim_contract")
    attempt = {"errors": [], "candidates": {"schema_version": 2, "statements": []},
        "retained": [], "terminal": True, "semantic_rejected": 1,
        "semantic_rejections": [{"index": 0, "kind": "scope_failure", "detail": "wrong actor"}],
        "admission": {"called": False, "semantic_rejected": 0}}
    assert hasattr(verifier, "check_replay_attempt"), "semantic rejection audit missing"
    verifier.check_replay_attempt(attempt, attempt)
    changed = json.loads(json.dumps(attempt))
    changed["semantic_rejections"][0]["detail"] = "changed diagnostic"
    with pytest.raises(ValueError, match="semantic_rejections"):
        verifier.check_replay_attempt(changed, attempt)


def test_native_excerpt_truncation_metadata_is_verified(evaluation):
    verifier = importlib.import_module("verify_socialmem_claim_contract")
    source = "米娜：我担心发布。"
    cut = len("米娜：我担心".encode())
    claim = {"source_span": {"span_start": 0, "span_end": len(source.encode())}}
    link = {"source_excerpt": "米娜：我担心", "source_excerpt_span_start": 0,
            "source_excerpt_span_end": cut, "source_excerpt_truncated": True}
    assert hasattr(verifier, "check_link_excerpt"), "bounded native excerpt audit missing"
    verifier.check_link_excerpt(source, claim, link)
    link["source_excerpt_truncated"] = False
    with pytest.raises(ValueError, match="excerpt"):
        verifier.check_link_excerpt(source, claim, link)


def qa_fixture(evaluation, tmp_path, *, fail_query=False):
    """Real native ingestion/retrieval; only model/embedding services are offline."""
    from starling import _core

    source = tmp_path / "source.db"
    with evaluation.trial.archived_runtime(source) as (rt, _working):
        for holder in ("Mina", "Jules"):
            c = case(holder=holder, passage=f"{holder}: I prefer each of the six project topics.")
            rows = [row(holder=holder, subject=holder, predicate="prefers", object=f"project{i}") for i in range(6)]
            receipt = evaluation.supplement.persist(_core, rt.adapter, c, "{convo}",
                {"raw": json.dumps(rows), "ok": True, "error": ""}, evaluation.NOW, supplement=False)
            assert len(receipt["statement_ids"]) == 6
    record = {"item_id": "Q_fixture", "question": "Which project topics are preferred by these people?",
              "answer": "Mina and Jules prefer project topics.", "history": [], "answer_format": "free_form"}
    inputs = {"records": [record], "frozen_sources": [{"path": str(source), "sha256": evaluation.digest(source)}],
              "scoped": []}
    out = tmp_path / "run"
    (out / "databases").mkdir(parents=True)
    embedder = _core.StubEmbeddingAdapter(8)
    if fail_query:
        embedder.fail_next(record["question"])
    qa = evaluation.recall_case(_core, embedder, record, source, [], {}, "baseline", out)
    assert qa["embedding"]["failed"] == 0
    assert qa["recall"]["statement_ids"] and qa["recall"]["block"]
    return _core, out, qa, record, inputs


def test_query_embedding_degradation_retains_fallback_but_fails_answer_arm(evaluation, tmp_path):
    core, out, qa, record, _inputs = qa_fixture(evaluation, tmp_path, fail_query=True)
    assert "semantic_index" in qa["error"], "query embedding failure silently counted as normal retrieval"
    degraded = [d for r in qa["recall"]["receipts"] for d in r["degraded_paths"]]
    assert any(d["path"] == "semantic_index" and d["reason"] == "embedder_unavailable" for d in degraded)
    answer = evaluation.answer_case(lambda _prompt, _model, max_tokens: "YES", record, "baseline",
        qa["recall"]["block"], out, context_error=qa["error"])
    assert answer["judgment"]["ok"] and not answer["answer_ok"]
    assert answer["context_error"]


@pytest.mark.parametrize("tamper", ["block", "labels", "selected_id"])
def test_qa_verifier_rejects_context_and_selection_tampering(evaluation, tmp_path, tamper):
    verifier = importlib.import_module("verify_socialmem_claim_contract")
    core, out, qa, record, inputs = qa_fixture(evaluation, tmp_path)
    verifier.check_qa_database(core, out, qa, record, inputs, {})
    changed = json.loads(json.dumps(qa))
    recall = changed["recall"]
    if tamper == "block":
        recall["block"] = "[FACT] Jules decided_on cancel all projects."
    elif tamper == "labels":
        recall["labels"][0] = "HEARSAY" if recall["labels"][0] != "HEARSAY" else "FACT"
    else:
        unused = next(r["id"] for r in qa["after"] if r["id"] not in recall["statement_ids"])
        recall["statement_ids"][0] = unused
    # Making the downstream prompt agree with an altered context is insufficient.
    forged_answer_prompt = evaluation.trial.ladder._ladder_prompt_free(record, recall["block"].splitlines())
    assert record["question"] in forged_answer_prompt
    with pytest.raises(ValueError):
        verifier.check_qa_database(core, out, changed, record, inputs, {})


def test_qa_verifier_rejects_missing_selected_claim_link(evaluation, tmp_path):
    from starling import _core
    verifier = importlib.import_module("verify_socialmem_claim_contract")
    source = tmp_path / "source.db"
    c = case(passage="Mina: I feel sad about release.", track="synthetic")
    candidate = row(object="sad about release", evidence={"clause_id": "c0", "actor": "Mina",
        "assertion_scope": "ASSERTED", "scope_markers": ["ASSERTED"], "time_text": "", "event_time": None})
    raw = json.dumps({"schema_version": 2, "statements": [candidate]})
    fake = _core.FakeLLMAdapter()
    fake.set_default_response('{"schema_version":1,"decisions":[{"index":0,"retain":true,"reason":"supported"}]}')
    fake.set_response(_core.Extractor.compute_prompt_input_hash(
        _core.claim_extraction_prompt(c["passage"], c["holder"])), raw)
    with evaluation.trial.archived_runtime(source) as (rt, working):
        committed, _ = evaluation.native_persist(_core, rt.adapter, c, fake)
        assert len(committed["statement_ids"]) == 1
        import sqlite3
        with sqlite3.connect(working) as db:
            db.execute("UPDATE statements SET consolidation_state='consolidated',review_status='approved'")
    out = tmp_path / "run"
    (out / "databases").mkdir(parents=True)
    record = {"item_id": "Q_claim", "question": "Mina feels sad about release"}
    qa = evaluation.recall_case(_core, _core.StubEmbeddingAdapter(8), record, source, [], {}, "baseline", out)
    assert len(qa["recall"]["evidence_links"]) == 1
    verifier.check_observer_recall(_core, out / qa["database"], qa, record)
    qa["recall"]["evidence_links"] = []
    for scope in qa["recall"]["receipts"]:
        scope["evidence_links"] = []
        scope["source_time_fallback_count"] = 0
    with pytest.raises(ValueError, match="link"):
        verifier.check_observer_recall(_core, out / qa["database"], qa, record)


def test_cli_json_mode_reaches_native_transport_metadata(evaluation, monkeypatch, tmp_path):
    import sys

    monkeypatch.setenv("OPENAI_BASE_URL", "https://answer.example.test/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "local-test")
    monkeypatch.setenv("DASHSCOPE_BASE_URL", "https://extract.example.test/compatible-mode/v1")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "local-test")
    monkeypatch.setenv("EMBEDDING_MODEL", "local-test")
    monkeypatch.setenv("EMBEDDING_DIM", "8")
    captured = []
    # Construction and configuration are real; stop before the paid run.
    monkeypatch.setattr(evaluation, "run", lambda *args, **kwargs: captured.append(args))
    monkeypatch.setattr(sys, "argv", ["eval", "run", "--previous", str(tmp_path / "old"),
                                   "--out", str(tmp_path / "new"), "--json-object-output"])
    evaluation.main()
    assert len(captured) == 1
    assert captured[0][6]["response_format"] == {"type": "json_object"}
    assert captured[0][6]["response_content"] == "verbatim"
    assert captured[0][7] == "https://answer.example.test/v1"


def test_cli_selected_model_is_bound_to_capability_before_cohort(evaluation, monkeypatch, tmp_path):
    from starling import _core
    probe = importlib.import_module("probe_socialmem_output_capability")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "local-test")
    monkeypatch.setenv("DASHSCOPE_BASE_URL", "https://extract.example.test/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "local-test")
    cfg = _core.OpenAIAdapterConfig.from_env()
    cfg.base_url = "https://extract.example.test/v1"
    cfg.model = "deepseek-v3"
    cfg.timeout_ms = -1  # Native Unknown evidence with zero network requests.
    report = probe.collect_report(_core, _core.OpenAIAdapter(cfg), {"endpoint": cfg.base_url, "model": cfg.model})
    path = tmp_path / "capability.json"
    path.write_text(json.dumps(report))
    out = tmp_path / "must-not-run"
    monkeypatch.setattr(sys, "argv", ["eval", "run", "--previous", str(tmp_path / "old"),
        "--out", str(out), "--output-mode", "json_schema_strict", "--model", "qwen3.7-plus",
        "--capability-report", str(path)])
    monkeypatch.setattr(evaluation, "run", lambda *a, **kw: pytest.fail("mismatched model started cohort"))
    with pytest.raises(ValueError, match="endpoint/model drift"):
        evaluation.main()
    assert not out.exists()


def test_base_provenance_keeps_frozen_model_and_detects_relabeling(evaluation, tmp_path):
    parent = {"core_sha256": "old-core", "extract_transport": {
        "model": "deepseek-v3", "endpoint": "https://extract.example.test/v1"}}
    path = tmp_path / "parent"
    path.mkdir()
    evaluation.dump(path / "manifest.json", parent)
    provenance = evaluation.base_memory_provenance(path, parent)
    assert provenance["extract_transport"]["model"] == "deepseek-v3"
    assert provenance["source_manifest_sha256"] == evaluation.digest(path / "manifest.json")
    manifest = {"extract_transport": {"model": "qwen3.7-plus"}, "base_memory_provenance": provenance}
    verifier = importlib.import_module("verify_socialmem_claim_contract")
    verifier.check_base_memory_provenance(path, parent, manifest)
    manifest["base_memory_provenance"]["extract_transport"]["model"] = "qwen3.7-plus"
    # The archive helper must not expose aliases into the parent identity.
    assert parent["extract_transport"]["model"] == "deepseek-v3"
    with pytest.raises(ValueError, match="base memory provenance"):
        verifier.check_base_memory_provenance(path, parent, manifest)
    verifier.check_base_memory_provenance(path, parent, {})  # Historical archives lack this field.


def test_structured_run_without_capability_stops_before_any_cohort_work(evaluation, monkeypatch, tmp_path):
    from starling import _core

    def forbidden(*args, **kwargs):
        pytest.fail("capability-blocked run performed cohort work")

    monkeypatch.setattr(evaluation, "prepare", forbidden)
    monkeypatch.setattr(evaluation, "evaluate_case", forbidden)
    out = tmp_path / "blocked"
    result = evaluation.run(tmp_path / "parent", out, _core, None, forbidden, None,
        {"endpoint": "https://example.test/v1", "model": "local-test"}, "offline",
        output_mode="json_schema_strict")
    manifest = evaluation.load(out / "manifest.json")
    assert manifest["status"] == "capability_blocked"
    assert result["quality"] is None and result["promotion_ready"] is False
    assert manifest["actual"] == {"records": 0, "extraction": 0, "injected_controls": 0,
        "admission": 0, "answer": 0, "judge": 0, "probe": 0}
    assert not (out / "databases").exists()
    verifier = importlib.import_module("verify_socialmem_claim_contract")
    assert verifier.verify(out)["run_status"] == "capability_blocked"
    (out / "extraction_calls.jsonl").write_text('{"ok":true}\n')
    with pytest.raises(ValueError, match="blocked|artifact|cohort"):
        verifier.verify(out)


def test_structured_cli_does_not_require_answer_credentials_before_capability_gate(evaluation, monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    out = tmp_path / "blocked-cli"
    monkeypatch.setattr(sys, "argv", ["eval", "run", "--previous", str(tmp_path / "old"),
        "--out", str(out), "--output-mode", "json_schema_strict"])
    evaluation.main()
    assert evaluation.load(out / "manifest.json")["status"] == "capability_blocked"


def test_failed_completion_keeps_native_protocol_evidence_separate_from_success_body(evaluation):
    from types import SimpleNamespace

    native = {"raw_completion": '{"schema_version":', "raw_http_response": '{"choices":[]}',
        "finish_reason": "length", "output_mode": "json_schema_strict",
        "output_contract": "claim_extraction_v2", "http_attempts": [{"attempt": 1}],
        "attempt_count": 1}
    response = SimpleNamespace(raw_xml="", ok=False, error="completion_truncated",
        structured_metadata_json=lambda: json.dumps(native))
    record = evaluation.call_record(response)
    assert record["raw_response"] == "" and record["ok"] is False
    assert record["structured_output"] == native


@pytest.mark.parametrize("field,value", [("output_contract", "claim_extraction_v2"),
    ("schema_sha256", "bad"), ("attempt_count", 2), ("capability_evidence_id", "unrelated-probe")])
def test_protocol_verifier_rejects_modified_request_identity_and_attempts(evaluation, field, value):
    from starling import _core

    verifier = importlib.import_module("verify_socialmem_claim_contract")
    assert hasattr(verifier, "check_channel_protocol"), "structured request verification missing"
    channel = {"output_mode": "json_schema_strict", "output_contract": "claim_admission_v1",
        "schema_sha256": _core.structured_output_schema_sha256(_core.OutputContractKind.ClaimAdmissionV1),
        "capability_evidence_id": "native-probe", "attempt_count": 1,
        "http_attempts": [{"attempt": 1, "http_status": 200, "curl_code": 0,
            "response_body": "{}", "response_bytes": 2, "streamed_bytes": 0, "elapsed_ms": 1,
            "retry_policy": "connect_only", "execution_certainty": "response_received"}],
        "raw_response": "{}", "raw_completion": "{}", "raw_http_response": "{}", "ok": True}
    verifier.check_channel_protocol(_core, channel, "claim_admission_v1", "json_schema_strict",
        evidence_id="native-probe", real=True, max_retries=3)
    channel[field] = value
    with pytest.raises(ValueError, match="protocol|schema|capability|attempt"):
        verifier.check_channel_protocol(_core, channel, "claim_admission_v1", "json_schema_strict",
            evidence_id="native-probe", real=True, max_retries=3)


def test_chinese_trailing_text_archives_as_technical_failure(evaluation, tmp_path):
    from starling import _core

    c = case(track="synthetic")
    raw = '{"schema_version":2,"statements":[]}\n解释'
    fake = _core.FakeLLMAdapter()
    fake.set_default_response(raw)
    (tmp_path / "databases").mkdir()
    result = evaluation.evaluate_case(_core, c, None, {"baseline": "{convo}"}, tmp_path, fake)
    assert result["outcome"] == "technical_failure" and not result["native_ok"]
    assert result["rows"] == []
    assert evaluation.lines(tmp_path / "extraction_calls.jsonl")[0]["raw_response"] == raw
    assert evaluation.lines(tmp_path / "cases.jsonl")[0]["claim_receipt"]["attempts"][0]["errors"][0]["kind"] == "envelope_failure"
    errors = evaluation.failure_counts([result], [], [])
    assert errors["native_failures"] == 1
    assert evaluation.completion_status(errors) == "complete_with_errors"


def test_typed_fixed_candidate_persists_and_replays_with_external_admission_evidence(evaluation, tmp_path):
    from starling import _core

    c = case(candidate=row(evidence={"clause_id": "c0", "actor": "Mina",
        "assertion_scope": "ASSERTED", "scope_markers": ["ASSERTED"], "time_text": "", "event_time": None}))
    llm = _core.FakeLLMAdapter()
    llm.set_default_response('{"schema_version":1,"decisions":[{"index":0,"retain":true,"reason":"supported"}]}')
    (tmp_path / "databases").mkdir()
    result = evaluation.evaluate_case(_core, c, None, {"baseline": "{convo}"}, tmp_path, llm,
                                      output_mode="json_schema_strict")
    assert result["native_ok"] and len(result["rows"]) == 1
    receipt = result["claim_receipt"]
    assert receipt["schema_version"] == 2
    assert len(llm.structured_requests) == 1
    assert llm.structured_requests[0].contract == _core.OutputContractKind.ClaimAdmissionV1
    assert receipt["external_admission_call"]["structured_output"]["output_contract"] == "claim_admission_v1"
    assert receipt["attempts"][0]["extraction"]["structured_output"]["output_contract"] == "claim_extraction_v2"
    verifier = importlib.import_module("verify_socialmem_claim_contract")
    verifier.check_case(_core, tmp_path, c, None, {"baseline": "{convo}"}, result)
    receipt["attempts"][0]["extraction"]["structured_output"]["output_contract"] = "claim_admission_v1"
    with pytest.raises(ValueError, match="protocol"):
        verifier.check_case(_core, tmp_path, c, None, {"baseline": "{convo}"}, result)

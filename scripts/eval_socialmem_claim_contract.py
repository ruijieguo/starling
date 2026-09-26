#!/usr/bin/env python3
"""Frozen-cohort diagnostic of the native source-grounded claim contract.

Python schedules calls, records artifacts and computes evaluation statistics.
Parsing, scope validation, admission, persistence and evidence authorization are
performed by the C++ core. Historical helpers are used without invoking their
prepare/verify entry points, which intentionally pin an older native binary.
"""
from __future__ import annotations

import argparse
import copy
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
from urllib.parse import urlsplit, urlunsplit

import eval_socialmem_admission as admission
import eval_socialmem_supplement as supplement

ROOT = supplement.ROOT
trial, contracts = supplement.trial, supplement.contracts
load, digest, dump, journal = supplement.load, supplement.digest, supplement.dump, supplement.journal
judge_candidate = admission.judge_candidate
CONTROL_PATH = ROOT / "tests/data/eval_socialmem_claim_controls.json"
EXTENDED_LABEL_PATH = ROOT / "tests/data/eval_socialmem_extended_labels.json"
BEFORE_PATH = ROOT / "build/socialmem_claim_contract_before/manifest.json"
NOW = "2026-09-12T00:00:00Z"
EXPECTED = {"records": 140, "extraction": 76, "injected_controls": 64,
            "admission_max": 140, "answer": 8, "judge": 120}
TRACKS = ("p1", "synthetic", "scoped", "fixed_controls")
OUTPUT_MODES = ("legacy", "json_object", "json_schema_strict")
# Serialization of the already-bound native DTO; no Python row/parser logic.
NATIVE_ROW_FIELDS = ("id", "tenant_id", "holder_id", "holder_perspective", "subject_kind", "subject_id",
    "predicate", "object_kind", "object_value", "canonical_object_hash", "modality", "polarity", "confidence",
    "observed_at", "valid_from", "valid_to", "consolidation_state", "review_status", "evidence_json",
    "affect_json", "semantic_claim_json", "source_spans_json")
SCORE_FIELDS = ("statement_id", "base", "recency", "salience", "activation", "affect_consistency",
                "temporal_penalty", "final_score")
POLICY = {"semantic_claim_contract": True, "claim_allow_code_fence": True,
          "preserve_text_objects": True, "attribute_first_order_mental_to_holder": False,
          "extra_core_predicates": list(trial.EXTRA_PREDICATES)}


def lines(path):
    return supplement.lines(path) if path.exists() else []


def require(condition, message):
    if not condition:
        raise ValueError(message)


def schedule_counts(inputs):
    sizes = {track: len(inputs[track]) for track in TRACKS}
    require(sizes == {"p1": 50, "synthetic": 16, "scoped": 10, "fixed_controls": 64},
            f"unexpected diagnostic cohort: {sizes}")
    identities = [(track, c["id"]) for track in TRACKS for c in inputs[track]]
    require(len(set(identities)) == 140, "duplicate cohort identity")
    return dict(EXPECTED)


def source_prompts(core, case, candidates):
    # Construct the model boundary by allowlisting source fields. Neither case
    # labels nor question/gold fields are passed to native prompt generation.
    envelope = json.dumps({"schema_version": 2, "statements": candidates}, ensure_ascii=False)
    return {"extraction": core.claim_extraction_prompt(case["passage"], case["holder"]),
            "admission": core.claim_admission_prompt(case["passage"], envelope)}


def verify_artifacts(root, fingerprints):
    root = root.resolve()
    for name, fingerprint in fingerprints.items():
        path = (root / name).resolve()
        require(path.is_relative_to(root) and path != root, f"invalid artifact path: {name}")
        require(path.is_file() and digest(path) == fingerprint, f"artifact drift: {name}")


def verify_historical(previous):
    manifest = load(previous / "manifest.json")
    verification = load(previous / "verification.json")
    require(manifest["status"] in ("complete", "complete_with_errors") and
            verification["status"] == "verified", "historical parent is incomplete/unverified")
    verify_artifacts(previous, verification["artifact_sha256"])
    return manifest


def base_memory_provenance(previous, parent):
    return {"source_manifest_sha256": digest(previous / "manifest.json"),
            "core_sha256": parent["core_sha256"],
            "extract_transport": json.loads(json.dumps(parent["extract_transport"]))}


def prepare(previous):
    from starling.extractor.prompts import EXTRACTION_PROMPT

    parent = verify_historical(previous)
    old = load(previous / "inputs.json")
    templates = load(previous / "prompts.json")
    require(templates["baseline"] == EXTRACTION_PROMPT, "frozen baseline prompt changed")
    require([c["record"] for c in old["p1"]] == lines(ROOT / "tests/data/eval_p1_corpus.jsonl"),
            "P1 labels changed")
    previous_calls = lines(previous / "extraction_calls.jsonl")
    base_calls = dict(old["base_calls"])
    base_calls.update({c["id"]: c for c in previous_calls
                       if c["track"] == "synthetic" and c["channel"] == "baseline"})
    comparisons = {c["id"]: c for c in lines(previous / "cases.jsonl") if c["track"] == "synthetic"}
    controls = [{**c, "track": "fixed_controls"} for c in load(CONTROL_PATH)]
    require(len(controls) == 64 and sum(c["origin"] == "archived" for c in controls) == 32,
            "expected 32 archived and 32 new fixed controls")
    inputs = {k: old[k] for k in ("p1", "synthetic", "scoped", "records", "frozen_sources")}
    inputs.update(fixed_controls=controls, base_calls=base_calls, comparisons=comparisons)
    schedule_counts(inputs)
    require([r["item_id"] for r in inputs["records"]] == ["Q1_a5s1c1", "Q9_a0b1c2d3"],
            "reviewed QA scope changed")
    for source in inputs["frozen_sources"]:
        require(digest(Path(source["path"])) == source["sha256"], "frozen QA source drift")
    for c in inputs["p1"] + inputs["synthetic"]:
        require(base_calls[c["id"]]["prompt"] == supplement.render(templates["baseline"], c),
                "cached baseline prompt differs from source")
    return inputs, templates, parent


def policy(core, output_mode="legacy"):
    value = core.ValidationPolicy()
    for name, setting in POLICY.items():
        setattr(value, name, setting)
    if output_mode != "legacy":
        from probe_socialmem_output_capability import mode_value
        value.claim_output_mode = mode_value(core, output_mode)
    return value


def with_source_turns(core, inputs):
    """只映射已复核来源字段；版本协议、日期校验和字节定位交由 C++。"""
    result = copy.deepcopy(inputs)
    records = {r["item_id"]: r for r in inputs["records"]}
    for case in result["scoped"]:
        turns = [{"speaker": turn["speaker"], "text": turn["text"],
                  "session_id": turn.get("session_id"), "turn_id": turn.get("turn_id"),
                  "turn_index": turn.get("message_index"), "observed_at": turn.get("observed_at")}
                 for turn in records[case["item_id"]]["history"] if turn["speaker"] == case["holder"]]
        require(bool(turns), "reviewed holder has no source turns")
        case["passage"] = core.claim_source_turn_payload(json.dumps(turns, ensure_ascii=False))
    return result


def call_record(response):
    record = {"raw_response": response.raw_xml, "ok": response.ok, "error": response.error,
            **{name: getattr(response, name, None) for name in
               ("prompt_tokens", "completion_tokens", "total_tokens", "latency_ms")}}
    if hasattr(response, "structured_metadata_json"):
        record["structured_output"] = json.loads(response.structured_metadata_json())
    return record


def set_fake(core, fake, call):
    fake.set_response(core.Extractor.compute_prompt_input_hash(call["prompt"]),
                      call["raw_response"], call["ok"], call["error"])


def replay_adapter(core, receipt):
    fake = core.FakeLLMAdapter()
    fake.set_default_response("", False, "unrecorded native replay request")
    require(len(receipt["attempts"]) == 1, "contract attempted content retry")
    attempt = receipt["attempts"][0]
    set_fake(core, fake, attempt["extraction"])
    if attempt["admission"]["called"]:
        set_fake(core, fake, attempt["admission"])
    return fake


def fixed_adapter(core, adapter, llm, case, output_mode="legacy"):
    """Inject one authored candidate; C++ discovers/validates the admission call.

    The probe performs zero writes and zero model calls. The eventual native
    replay receives the same injection plus the one real admission response.
    """
    raw = json.dumps({"schema_version": 2, "statements": [case["candidate"]]}, ensure_ascii=False)
    prompt = core.claim_extraction_prompt(case["passage"], case["holder"])
    fake = core.FakeLLMAdapter()
    fake.set_default_response("", False, "admission response not supplied to probe")
    set_fake(core, fake, {"prompt": prompt, "raw_response": raw, "ok": True, "error": ""})
    probe = core.memory_extract_llm(adapter, fake, "", case["holder"], case["passage"].encode(), policy(core, output_mode))
    probe_receipt = json.loads(core.claim_extraction_receipt(probe))
    request = probe_receipt["attempts"][0]["admission"]
    actual = None
    if request["called"]:
        try:
            if output_mode == "legacy":
                response = llm.extract(request["prompt"], request["prompt_input_hash"])
            else:
                from probe_socialmem_output_capability import mode_value
                response = llm.extract_with_contract(request["prompt"], request["prompt_input_hash"],
                    core.StructuredOutputRequest(core.OutputContractKind.ClaimAdmissionV1, mode_value(core, output_mode)))
            actual = call_record(response)
        except Exception as exc:
            actual = {"raw_response": "", "ok": False, "error": f"{type(exc).__name__}: {exc}"}
        actual.update(prompt=request["prompt"], prompt_input_hash=request["prompt_input_hash"])
        set_fake(core, fake, actual)
    return fake, actual


def native_persist(core, adapter, case, llm, *, replay=None, output_mode="legacy"):
    prepared = core.memory_remember_prepare(adapter, tenant_id="default", holder_id=case["holder"],
        interlocutor="", adapter_name="socialmem-claim-contract", source_prefix="socialmem-claim-contract",
        created_at_iso8601=NOW, payload=case["passage"].encode())
    require(prepared.should_extract, "native source was not admitted")
    external = None
    if replay is not None:
        output_mode = replay["attempts"][0]["extraction"].get("structured_output", {}).get("output_mode", "legacy")
        llm = replay_adapter(core, replay)
    elif case["track"] == "fixed_controls":
        llm, external = fixed_adapter(core, adapter, llm, case, output_mode)
    extracted = core.memory_extract_llm(adapter, llm, "", case["holder"], case["passage"].encode(), policy(core, output_mode))
    committed = core.memory_remember_commit(adapter, llm, tenant_id="default", holder_id=case["holder"],
        interlocutor="", prepared=prepared, llm_result=extracted, policy=policy(core, output_mode))
    receipt = json.loads(core.claim_extraction_receipt(extracted))
    require(len(receipt["attempts"]) == 1, "contract performed a content retry")
    if external is not None:
        # Fake replay preserves model bytes. Real call usage lives separately,
        # because FakeLLMAdapter deliberately has no transport-token metadata.
        receipt["external_admission_call"] = external
    return committed, receipt


def database_rows(path):
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        require(conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "database integrity failure")
        return [dict(r) for r in conn.execute("SELECT * FROM statements ORDER BY id")]


def check_evidence(core, case, row, engram):
    """Independent archive integrity check, never a product admission decision."""
    claim = json.loads(row["semantic_claim_json"])
    span = claim["source_span"]
    require(row["tenant_id"] == engram["tenant_id"] == "default", "evidence tenant mismatch")
    require(row["holder_id"] == case["holder"] and engram.get("holder_id", case["holder"]) == case["holder"],
            "evidence holder mismatch")
    source = engram["payload"]
    require(source == case["passage"], "evidence source payload mismatch")
    require(span["engram_ref"] == engram["id"], "evidence engram mismatch")
    require(span["source_hash"] == hashlib.sha256(source.encode()).hexdigest(), "evidence source hash mismatch")
    units = {unit["clause_id"]: unit for unit in json.loads(core.claim_source_units(source))}
    require(claim["clause_id"] in units, "evidence source span clause mismatch")
    unit = units[claim["clause_id"]]
    require((span["span_start"], span["span_end"]) == (unit["byte_start"], unit["byte_end"]),
            "evidence source span mismatch")
    require(claim["source_time"] == engram["created_at"], "evidence source time mismatch")
    require(claim["actor"] == row["subject_id"], "evidence actor changed during persistence")
    require(claim["relation_modality"].upper() == row["modality"].upper() and
            claim["relation_polarity"].upper() == row["polarity"].upper(), "evidence relation changed")
    return claim


def evidence_errors(core, case, rows, database):
    errors = []
    with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        for row in rows:
            try:
                require(bool(row["semantic_claim_json"]), "persisted claim has no evidence")
                claim = json.loads(row["semantic_claim_json"])
                ref = claim["source_span"]["engram_ref"]
                source = conn.execute("SELECT * FROM engrams WHERE id=? AND tenant_id=?",
                                      (ref, row["tenant_id"])).fetchone()
                require(source is not None, "missing evidence engram")
                source = dict(source)
                source["payload"] = bytes(source["payload_inline"]).decode()
                check_evidence(core, case, row, source)
                refs = json.loads(row["source_spans_json"])
                require(any(all(r.get(k) == v for k, v in claim["source_span"].items()) for r in refs),
                        "compatibility source span mismatch")
            except (ValueError, KeyError, TypeError) as exc:
                errors.append({"statement_id": row["id"], "error": str(exc)})
    return errors


def outcome(receipt, committed):
    attempt = receipt["attempts"][0]
    if committed["extraction_failed"] or receipt.get("persistence_error") or attempt["errors"]:
        return "technical_failure"
    if attempt["retained"]:
        return "admitted"
    if attempt["admission"]["semantic_rejected"] or attempt.get("semantic_rejected", 0):
        return "semantic_rejection"
    return "empty"


def wire_rows(rows):
    mapping = {"holder_id": "holder", "subject_id": "subject", "object_value": "object"}
    return [{mapping.get(k, k): (row[k].upper() if k in ("holder_perspective", "modality", "polarity") else row[k])
             for k in trial.SEMANTIC_FIELDS} for row in rows]


def evaluate_case(core, case, base, templates, out, llm=None, *, replay=None, record=True, output_mode="legacy"):
    database = out / "databases" / f"{case['track']}_{case['id']}.db"
    with trial.archived_runtime(database) as (rt, working):
        base_receipt = None
        if base is not None:
            base_receipt = supplement.persist(core, rt.adapter, case, templates["baseline"], base, NOW, supplement=False)
        before = trial.temporal.statement_rows(working)
        committed, receipt = native_persist(core, rt.adapter, case, llm, replay=replay, output_mode=output_mode)
        after = trial.temporal.statement_rows(working)
        rows = [r for r in after if r["id"] in committed["statement_ids"]]
        by_id = {(r["id"], r["tenant_id"]): r for r in after}
        preserved = all(key in by_id and all(by_id[key][f] == r[f] for f in trial.SEMANTIC_FIELDS)
                        for r in before for key in [(r["id"], r["tenant_id"])])
        errors = evidence_errors(core, case, rows, working)
        with sqlite3.connect(working) as conn:
            pipelines = conn.execute("SELECT id,status FROM pipeline_run ORDER BY id").fetchall()
    stage = outcome(receipt, committed)
    result = {"id": case["id"], "track": case["track"], "before": before, "after": after, "rows": rows,
        "receipt": committed, "claim_receipt": receipt, "base_receipt": base_receipt,
        "base_semantics_preserved": preserved, "evidence_errors": errors, "outcome": stage,
        "native_ok": stage != "technical_failure", "pipelines": pipelines,
        "database": str(database.relative_to(out)), "database_sha256": digest(database)}
    if case["track"] == "p1":
        original = supplement.parsed(base["raw"], base["ok"])
        result["p1_baseline"] = trial.extraction.p1.evaluate_record(case["record"], original)
        result["p1_combined"] = trial.extraction.p1.evaluate_record(case["record"], original + wire_rows(rows))
    if record:
        journal(out / "cases.jsonl", result)
        attempt = receipt["attempts"][0]
        extraction = {"id": case["id"], "track": case["track"], **attempt["extraction"]}
        journal(out / ("injections.jsonl" if case["track"] == "fixed_controls" else "extraction_calls.jsonl"), extraction)
        if attempt["admission"]["called"]:
            actual = receipt.get("external_admission_call", attempt["admission"])
            journal(out / "admission_calls.jsonl", {"id": case["id"], "track": case["track"], **actual})
    return result


def control_scores(cases, results):
    require(len(cases) == len(results), "control/result denominator mismatch")
    counts = Counter(cases=len(cases), expected_positive=sum(c["expected_keep"] for c in cases),
                     correct=0, true_positives=0, true_negatives=0, false_accepts=0,
                     false_rejects=0, technical_failures=0)
    for case, result in zip(cases, results, strict=True):
        if not result["native_ok"] or result["outcome"] == "technical_failure":
            counts["technical_failures"] += 1
            continue
        keep, expected = bool(result["rows"]), case["expected_keep"]
        correct = keep == expected
        counts["correct"] += correct
        counts[("true_positives" if keep else "true_negatives") if correct else
               ("false_accepts" if keep else "false_rejects")] += 1
    return dict(counts)


def failure_counts(results, judgments, answers, qa=()):
    return {"native_failures": sum(not r["native_ok"] for r in results),
            "base_failures": sum(bool(r.get("base_receipt") and r["base_receipt"]["extraction_failed"]) for r in results),
            "evidence_failures": sum(len(r["evidence_errors"]) for r in results),
            "base_semantics_changed": sum(not r["base_semantics_preserved"] for r in results),
            "invalid_judge_votes": sum(j["judgment"]["failed"] for j in [*judgments, *answers]),
            "answer_failures": sum(not a["answer_ok"] for a in answers),
            "retrieval_failures": sum(bool(r.get("error")) for r in qa)}


def completion_status(errors):
    return "complete_with_errors" if any(errors.values()) else "complete"


def native_row_snapshot(row):
    return {name: getattr(row, name) for name in NATIVE_ROW_FIELDS}


def retrieval_degradation_error(recall):
    failures = [{"holder": r["holder"], **path} for r in recall["receipts"]
                for path in r["degraded_paths"] if path["path"] == "semantic_index"]
    return "native semantic_index degraded: " + json.dumps(failures, ensure_ascii=False, sort_keys=True) if failures else ""


def planner_recall(core, adapter, embedder, index, question):
    """Use each native holder scope, then the existing total-k observer protocol."""
    with sqlite3.connect(str(adapter.db_path)) as conn:
        holders = [r[0] for r in conn.execute("SELECT DISTINCT holder_id FROM statements WHERE tenant_id='default' ORDER BY holder_id")]
    sr = core.SemanticRetriever(adapter, embedder, index)
    planner = core.RetrievalPlanner(adapter, sr)
    candidates, receipts = [], []
    for scope_index, holder in enumerate(holders or ["alice"]):
        query = core.PlannerQuery()
        query.tenant_id, query.querier, query.perspective = "default", holder, ""
        query.intent, query.text, query.as_of_iso8601, query.k = core.QueryIntent.FACT_LOOKUP, question, NOW, 10
        query.trace_id, query.query_id = f"claim-{scope_index}", f"claim-{scope_index}-q"
        result = planner.run(query)
        receipt = result.receipt
        entries = [{"row": native_row_snapshot(entry.row), "score": entry.score, "label": entry.label.name,
                    "line": core.render_context_line(entry.row, entry.label)} for entry in result.entries]
        receipts.append({"holder": holder, "tenant_id": "default", "perspective": "", "k": 10,
            "intent": "FACT_LOOKUP", "query_text": question, "as_of_iso": NOW,
            "abstained": result.abstained, "entries": entries, "context_pack": result.context_pack,
            "filters_applied": [{"name": f.name, "value": f.value} for f in receipt.filters_applied],
            "scope_steps": [{"scope": step.scope, "holder_scope": step.holder_scope,
                             "filters": step.filters, "max_candidates": step.max_candidates}
                            for step in receipt.scope_plan.steps],
            "score_breakdown": [{name: getattr(score, name) for name in SCORE_FIELDS}
                                for score in receipt.score_breakdown],
            "degraded_paths": [{"path": path.path, "reason": path.reason, "fallback": path.fallback}
                               for path in receipt.degraded_paths],
            "abstention_reason": receipt.abstention_reason,
            "fetched": receipt.candidate_counts.fetched, "returned": receipt.candidate_counts.returned,
            "scores": {s.statement_id: s.final_score for s in receipt.score_breakdown},
            "evidence_links": json.loads(receipt.evidence_links_json),
            "claim_exclusion_counts": json.loads(receipt.claim_exclusion_counts_json),
            "source_time_fallback_count": receipt.source_time_fallback_count})
        if not result.abstained:
            candidates.extend((e.score, e.row.id, e) for e in result.entries)
    chosen = sorted(candidates, key=lambda c: (-c[0], c[1]))[:10]
    chosen_ids = {sid for _, sid, _ in chosen}
    links = [link for r in receipts for link in r["evidence_links"] if link["statement_id"] in chosen_ids]
    block = "\n".join(core.render_context_line(e.row, e.label) for _, _, e in chosen)
    return {"block": block, "abstained": not chosen, "statement_ids": [sid for _, sid, _ in chosen],
            "labels": [e.label.name for _, _, e in chosen], "receipts": receipts,
            "evidence_links": links, "as_of_iso": NOW}


def linked_context(recall):
    # Only source excerpts authorized and returned by the C++ retrieval receipt
    # may cross this boundary. Python never queries/slices raw Engrams for QA.
    excerpts = []
    for link in recall["evidence_links"]:
        require(isinstance(link.get("source_excerpt"), str) and bool(link["source_excerpt"]),
                "native evidence link lacks authorized source_excerpt")
        marker = " [source excerpt truncated]" if link.get("source_excerpt_truncated", False) else ""
        excerpts.append(f"[{link['statement_id']} | {link['clause_id']}] {link['source_excerpt']}{marker}")
    return recall["block"] + ("\n\nLinked source excerpts:\n" + "\n".join(excerpts) if excerpts else "")


def embedding_counts(embedder):
    # New native adapters may expose counters. Unknown transport request counts
    # must remain null; worker row/tick totals are not HTTP request counts.
    return {name: getattr(embedder, name, None) for name in ("request_count", "embed_calls", "batch_calls")}


def recall_case(core, embedder, record, source, cases, results, arm, out):
    database = out / "databases" / f"qa_{record['item_id']}_{arm}.db"
    result = {"id": record["item_id"], "arm": arm, "receipts": [], "error": ""}
    with supplement.copied_runtime(source, database) as (rt, working):
        result["base_rows"] = trial.temporal.statement_rows(working)
        if arm == "structured":
            for case in cases:
                committed, receipt = native_persist(core, rt.adapter, case, None,
                                                     replay=results[("scoped", case["id"])]["claim_receipt"])
                result["receipts"].append({"id": case["id"], **committed, "claim_receipt": receipt})
        result["before"] = trial.temporal.statement_rows(working)
        result["embedding_counts_before"] = embedding_counts(embedder)
        try:
            sleep = core.ReplayScheduler(rt.adapter).run_sleep(NOW)
            result["sleep"] = {k: getattr(sleep, k) for k in ("sampled", "compressed", "abstracted", "gist_failed")}
            index = core.SqliteBlobVectorIndex()
            result["embedding"] = trial.pipe.embed_seeded(core, rt.adapter, embedder, index, NOW)
            require(result["embedding"]["failed"] == 0, "native embedding failures")
            result["recall"] = planner_recall(core, rt.adapter, embedder, index, record["question"])
            # Preserve native fallback candidates/context for diagnosis while
            # preventing this technically degraded arm from counting as healthy.
            result["error"] = retrieval_degradation_error(result["recall"])
        except Exception as exc:
            result["error"] = f"{type(exc).__name__}: {exc}"
            result["recall"] = {"block": "", "abstained": True, "statement_ids": [], "labels": [],
                                "receipts": [], "evidence_links": [], "as_of_iso": NOW}
        result["embedding_counts_after"] = embedding_counts(embedder)
        result["after"] = trial.temporal.statement_rows(working)
        try:
            result["pipelines"] = trial.pipeline_rows(working)
            result["pipeline_failures"] = 0
        except ValueError as exc:
            if str(exc) != "unfinished native extraction pipeline":
                raise
            result["pipelines"], result["pipeline_failures"] = trial.pipeline_rows_with_failures(working)
    result.update(database=str(database.relative_to(out)), database_sha256=digest(database))
    dump(out / f"qa_{record['item_id']}_{arm}.json", result)
    return result


def answer_case(chat, record, arm, block, out, *, context_error=""):
    result = supplement.answer(chat, record, arm, block, out)
    # Preserve actual calls/votes even when the retrieval arm failed. Reporting
    # excludes apparent answer successes with unusable context provenance.
    result["context_error"] = context_error
    result["answer_ok"] = result["answer_ok"] and not context_error
    return result


def judge_consistency(entries):
    """Agreement of repeated votes, independent of semantic or pipeline scores."""
    counts = {"groups": len(entries), "comparable_groups": 0, "unanimous_groups": 0,
              "invalid_votes": 0, "mismatched_groups": 0, "valid_pairs": 0, "agreeing_pairs": 0}
    for entry in entries:
        votes = entry["judgment"]["votes"]
        counts["invalid_votes"] += sum(not v["valid"] for v in votes)
        if len({v["prompt"] for v in votes}) > 1 or len({v["repeat"] for v in votes}) != len(votes):
            counts["mismatched_groups"] += 1
            continue
        valid = [v["accepted"] for v in votes if v["valid"]]
        if len(valid) < 2:
            continue
        counts["comparable_groups"] += 1
        counts["unanimous_groups"] += len(set(valid)) == 1
        for i, first in enumerate(valid):
            for second in valid[i + 1:]:
                counts["valid_pairs"] += 1
                counts["agreeing_pairs"] += first == second
    return {**counts, "pairwise_agreement":
            counts["agreeing_pairs"] / counts["valid_pairs"] if counts["valid_pairs"] else None}


def summarize(inputs, results, judgments, answers, qa):
    controls = [r for r in results if r["track"] == "fixed_controls"]
    summary = {"records": len(results), "controls": control_scores(inputs["fixed_controls"][:len(controls)], controls),
               "tracks": {}, "p1": {}, "synthetic": {}, "answers": answers,
               "base_semantics_preserved": all(r["base_semantics_preserved"] for r in results),
               "errors": failure_counts(results, judgments, answers, qa)}
    for track in TRACKS:
        selected = [r for r in results if r["track"] == track]
        summary["tracks"][track] = {"records": len(selected), "stored": sum(len(r["rows"]) for r in selected),
            "outcomes": dict(Counter(r["outcome"] for r in selected)),
            "error_kinds": dict(Counter(e["kind"] for r in selected for a in r["claim_receipt"]["attempts"] for e in a["errors"])),
            "semantic_rejection_kinds": dict(Counter(e["kind"] for r in selected for a in r["claim_receipt"]["attempts"] for e in a["semantic_rejections"])),
            "deterministic_rejections": sum(len(a["semantic_rejections"]) for r in selected for a in r["claim_receipt"]["attempts"]),
            "model_rejections": sum(a["admission"]["semantic_rejected"] for r in selected for a in r["claim_receipt"]["attempts"])}
    for arm in ("baseline", "combined"):
        chosen = [r for r in results if r["track"] == "p1"]
        counts = {f: [sum(r["p1_" + arm][f][i] for r in chosen) for i in range(3)]
                  for f in trial.extraction.p1.P1_THRESHOLDS}
        summary["p1"][arm] = {"counts": counts, "f1": {k: trial.extraction.p1.f1_score(*v) for k, v in counts.items()}}
    for arm in ("frozen", "contract"):
        chosen = [j for j in judgments if j["arm"] == arm]
        valid = [j for j in chosen if j["native_ok"] and not j["judgment"]["failed"]]
        valid_majority = sum(j["judgment"]["ok"] for j in valid)
        summary["synthetic"][arm] = {"cases": len(chosen),
            "majority": sum(j["native_ok"] and j["judgment"]["ok"] for j in chosen),
            "invalid_votes": sum(j["judgment"]["failed"] for j in chosen),
            "valid_cases": len(valid), "valid_majority": valid_majority,
            "semantic_accuracy": valid_majority / len(valid) if valid else None}
    pairs = {arm: {j["id"]: j["native_ok"] and j["judgment"]["ok"] for j in judgments if j["arm"] == arm}
             for arm in ("frozen", "contract")}
    summary["synthetic"]["paired"] = {"gained": [i for i in pairs["contract"] if pairs["contract"][i] and not pairs["frozen"].get(i)],
        "lost": [i for i in pairs["frozen"] if pairs["frozen"][i] and not pairs["contract"].get(i)]}
    summary["judge_consistency"] = {
        "synthetic": {arm: judge_consistency([j for j in judgments if j["arm"] == arm])
                      for arm in ("frozen", "contract")},
        "qa": {arm: judge_consistency([a for a in answers if a["arm"] == arm])
               for arm in ("baseline", "structured", "linked", "full")}}
    summary["gates"] = {"controls": summary["controls"]["correct"] == 64 and not summary["controls"]["technical_failures"],
        "synthetic": len(judgments) == 32 and not summary["synthetic"]["paired"]["lost"],
        "p1": all(summary["p1"]["combined"]["f1"][f] >= summary["p1"]["baseline"]["f1"][f] for f in trial.extraction.p1.P1_THRESHOLDS),
        "technical": not any(summary["errors"].values()), "base_preserved": summary["base_semantics_preserved"]}
    summary["promotion_ready"] = False  # reviewed QA claim-by-claim analysis is a separate required artifact
    summary["qa_stage_counts"] = [{"id": q["id"], "arm": q["arm"], "error": q["error"],
        "stored_claims": sum(bool(r.get("semantic_claim_json")) for r in q["before"]),
        "retrieved": len(q["recall"]["statement_ids"]), "retrieved_claim_links": len(q["recall"]["evidence_links"]),
        "eligible_scope_totals": sum(r["returned"] for r in q["recall"]["receipts"])} for q in qa]
    return summary


def source_paths():
    paths = {"CMakeLists.txt", "tests/data/eval_socialmem_claim_controls.json", "tests/data/eval_socialmem_admission_controls.json",
             "tests/data/eval_p1_corpus.jsonl", "tests/data/eval_socialmem_extended_labels.json"}
    for folder, suffixes in (("scripts", {".py"}), ("src", {".cpp", ".hpp"}),
                             ("include", {".hpp", ".h"}), ("bindings", {".cpp", ".hpp"}),
                             ("migrations", {".sql"}), ("python/starling", {".py"})):
        paths.update(str(p.relative_to(ROOT)) for p in (ROOT / folder).rglob("*") if p.is_file() and p.suffix in suffixes)
    return sorted(paths)


def capability_blocked(out, core, output_mode, reason, *, report=None, transport=None):
    """归档前置条件失败；不创建候选数据库或质量分母。"""
    out.mkdir(parents=True, exist_ok=False)
    paths = source_paths()
    for name in paths:
        dest = out / "source_archive" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, dest)
    core_name = Path(core.__file__).name
    shutil.copyfile(core.__file__, out / "source_archive" / core_name)
    summary = {"status": "capability_blocked", "reason": reason, "quality": None,
               "promotion_ready": False}
    dump(out / "results.json", summary)
    if report is not None:
        dump(out / "capability_report.json", report)
    manifest = {"schema_version": 2, "status": "capability_blocked", "output_mode": output_mode,
        "created_at": datetime.now(timezone.utc).isoformat(), "reason": reason,
        "quality": None, "promotion_ready": False, "extract_transport": transport or {},
        "core_sha256": digest(Path(core.__file__)), "core_filename": core_name,
        "source_sha256": {p: digest(out / "source_archive" / p) for p in paths},
        "actual": {"records": 0, "extraction": 0, "injected_controls": 0,
                   "admission": 0, "answer": 0, "judge": 0,
                   "probe": report["request_count"] if report else 0}}
    manifest["artifact_sha256"] = {str(p.relative_to(out)): digest(p) for p in sorted(out.rglob("*"))
        if p.is_file() and p.name != "manifest.json"}
    dump(out / "manifest.json", manifest)
    return summary


def run(previous, out, core, llm, chat, embedder, transport, endpoint, *, execution_mode="real", source_turns=False,
        output_mode="legacy", capability_report=None):
    require(output_mode in OUTPUT_MODES, "unknown output mode")
    if output_mode != "legacy" and capability_report is None:
        return capability_blocked(out, core, output_mode, "missing_capability_report", transport=transport)
    capability_check = None
    if output_mode != "legacy":
        from probe_socialmem_output_capability import check_report
        if isinstance(capability_report, (str, Path)):
            capability_report = load(Path(capability_report))
        capability_check = check_report(core, capability_report, transport, output_mode)
        if not capability_check["ready"]:
            return capability_blocked(out, core, output_mode, ";".join(capability_check["reasons"]),
                                      report=capability_report, transport=transport)
    inputs, templates, parent = prepare(previous)
    if source_turns:
        inputs = with_source_turns(core, inputs)
    import eval_socialmem_extended as extended
    labels = load(EXTENDED_LABEL_PATH)
    extended.summarize(labels, inputs["synthetic"], [])  # Validate frozen source hashes before calls.
    require(execution_mode in ("real", "offline_smoke"), "unknown execution mode")
    initial_embedding_counts = embedding_counts(embedder)
    if execution_mode == "real":
        require(all(type(v) is int and v >= 0 for v in initial_embedding_counts.values()),
                "real evaluation requires native embedding request counters")
    out.mkdir(parents=True, exist_ok=False)
    (out / "databases").mkdir()
    dump(out / "inputs.json", inputs)
    dump(out / "policies.json", {**POLICY, **({"claim_output_mode": output_mode} if output_mode != "legacy" else {})})
    if capability_report is not None:
        dump(out / "capability_report.json", capability_report)
    dump(out / "baseline_prompts.json", templates)
    dump(out / "extended_labels.json", labels)
    dump(out / "source_units.json", {f"{c['track']}/{c['id']}": json.loads(core.claim_source_units(c["passage"]))
        for track in TRACKS for c in inputs[track]})
    paths = source_paths()
    for name in paths:
        dest = out / "source_archive" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, dest)
    core_name = Path(core.__file__).name
    shutil.copyfile(core.__file__, out / "source_archive" / core_name)
    require(BEFORE_PATH.is_file(), "before-build core manifest is required")
    shutil.copyfile(BEFORE_PATH, out / "before_core_manifest.json")
    manifest = {"schema_version": 1, "status": "running", "execution_mode": execution_mode,
        "started_at": datetime.now(timezone.utc).isoformat(), "query_time": NOW,
        "source_input_mode": "source_turn_v1" if source_turns else "legacy_text",
        "extended_labels_sha256": digest(EXTENDED_LABEL_PATH),
        "claim_level": "native_claim_contract_fixed_cohort_diagnostic", "planned": schedule_counts(inputs),
        "previous": str(previous.resolve()), "previous_verification_sha256": digest(previous / "verification.json"),
        "historical_core_sha256": parent["core_sha256"], "core_sha256": digest(Path(core.__file__)), "core_filename": core_name,
        "base_memory_provenance": base_memory_provenance(previous, parent),
        "before_core_manifest_sha256": digest(out / "before_core_manifest.json"),
        "source_sha256": {p: digest(out / "source_archive" / p) for p in paths},
        "extract_transport": transport, "answer_endpoint": endpoint, "answer_model": "gpt-5.5", "answer_max_tokens": 512,
        "judge_model": "gpt-5.5", "judge_max_tokens": 8, "judge_repeats": 3,
        "embedding_model": embedder.model(), "embedding_dim": embedder.dim(),
        "embedding_counts_initial": initial_embedding_counts,
        "protocol": "76 fresh native extractions; 64 fixed v2 injections; at most one admission per valid nonempty set. "
                    "Frozen P1/synthetic base and frozen synthetic comparison. 96 synthetic votes plus 8 QA answers/24 votes. "
                    "QA uses baseline, same fresh structured recall, that recall plus native-authorized excerpts, full dialogue. "
                    "Technical failures stay denominators. No production promotion or full 1031-question benchmark."}
    if output_mode != "legacy":
        manifest.update(schema_version=2, output_mode=output_mode,
            capability_binding="external_preflight_report", capability_check=capability_check,
            capability_checked_at=datetime.now(timezone.utc).isoformat(),
            capability_report_sha256=digest(out / "capability_report.json"))
    dump(out / "manifest.json", manifest)
    results, judgments, answers, qa = [], [], [], []
    try:
        for track in TRACKS:
            for case in inputs[track]:
                print(f"[claim] {track}/{case['id']}", flush=True)
                base = inputs["base_calls"].get(case["id"]) if track in ("p1", "synthetic") else None
                results.append(evaluate_case(core, case, base, templates, out, llm, output_mode=output_mode))
        by_key = {(r["track"], r["id"]): r for r in results}
        for i, case in enumerate(inputs["synthetic"]):
            for arm in (("frozen", "contract") if i % 2 == 0 else ("contract", "frozen")):
                memory = inputs["comparisons"][case["id"]] if arm == "frozen" else by_key[("synthetic", case["id"])]
                candidate = judge_candidate(memory["after"])
                judgment = contracts.judge(chat, case, arm, candidate, out)
                entry = {"id": case["id"], "arm": arm, "candidate": candidate,
                    "native_ok": memory["native_ok"] and not memory["base_receipt"]["extraction_failed"], "judgment": judgment}
                journal(out / "judgments.jsonl", entry)
                judgments.append(entry)
                print(f"[judge] {case['id']}/{arm}: {judgment['acceptances']}/3", flush=True)
        # Quality gates do not suppress the already-authorized reviewed QA diagnostic.
        for i, record in enumerate(inputs["records"]):
            selected = [c for c in inputs["scoped"] if c["item_id"] == record["item_id"]]
            recalls = {}
            for arm in (("baseline", "structured") if i % 2 == 0 else ("structured", "baseline")):
                q = recall_case(core, embedder, record, Path(inputs["frozen_sources"][i]["path"]), selected, by_key, arm, out)
                qa.append(q)
                recalls[arm] = q
            for arm in ("baseline", "structured", "linked", "full"):
                error = ""
                if arm == "full":
                    block = trial.pipe.recall_block(core, "S_full", adapter=None, embedder=None, index=None,
                        question=record["question"], history=record["history"])["block"]
                else:
                    q = recalls["structured" if arm == "linked" else arm]
                    error = q["error"]
                    try:
                        block = linked_context(q["recall"]) if arm == "linked" else q["recall"]["block"]
                    except ValueError as exc:
                        error, block = str(exc), ""
                a = answer_case(chat, record, arm, block, out, context_error=error)
                answers.append(a)
                print(f"[answer] {record['item_id']}/{arm}: {a['judgment']['acceptances']}/3", flush=True)
        manifest["status"] = completion_status(failure_counts(results, judgments, answers, qa))
        manifest["completed_at"] = datetime.now(timezone.utc).isoformat()
    except Exception as exc:
        manifest.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        # supplement.answer journals a minimal result. The final annotated list
        # preserves context failures in a separate authoritative artifact.
        dump(out / "answer_results.json", answers)
        summary = summarize(inputs, results, judgments, answers, qa)
        summary["extended_labels"] = extended.summarize(labels, inputs["synthetic"], results)
        dump(out / "results.json", summary)
        manifest["errors"] = summary["errors"]
        manifest["actual"] = {"records": len(results), "extraction": len(lines(out / "extraction_calls.jsonl")),
            "injected_controls": len(lines(out / "injections.jsonl")), "admission": len(lines(out / "admission_calls.jsonl")),
            "answer": len(lines(out / "answer_calls.jsonl")), "judge": len(lines(out / "judge_calls.jsonl")),
            "embedding_adapter_counts": embedding_counts(embedder)}
        if output_mode != "legacy":
            calls = lines(out / "extraction_calls.jsonl") + lines(out / "admission_calls.jsonl")
            manifest["actual"].update(probe=capability_report["request_count"],
                structured_http_attempts=sum(c.get("structured_output", {}).get("attempt_count", 0) for c in calls))
        manifest["artifact_sha256"] = {str(p.relative_to(out)): digest(p) for p in sorted(out.rglob("*"))
            if p.is_file() and p.name not in ("manifest.json", "verification.json")}
        dump(out / "manifest.json", manifest)
    return summary


def smoke_llm(core, inputs):
    fake = core.FakeLLMAdapter()
    fake.set_default_response('{"schema_version":2,"statements":[]}', True, "")
    for c in inputs["fixed_controls"]:
        raw = json.dumps({"schema_version": 2, "statements": [c["candidate"]]}, ensure_ascii=False)
        parsed = json.loads(core.claim_parse_response(raw, c["passage"], c["holder"], True))
        if not parsed["errors"] and parsed["statements"]:
            prompt = source_prompts(core, c, parsed["statements"])["admission"]
            fake.set_response(core.Extractor.compute_prompt_input_hash(prompt),
                '{"schema_version":1,"decisions":[{"index":0,"retain":true,"reason":"supported"}]}')
    # One fresh positive exercises source->extraction->admission->DB. All other
    # fresh outputs are valid empty envelopes; smoke scores are not model evidence.
    c = inputs["synthetic"][0]
    candidate = {"holder": c["holder"], "subject": c["holder"], "holder_perspective": "FIRST_PERSON",
        "subject_kind": "cognizer", "predicate": "feels", "object": "anxious about the certification exam",
        "modality": "BELIEVES", "polarity": "POS", "nesting_depth": 0,
        "evidence": {"clause_id": "c0", "actor": c["holder"], "assertion_scope": "ASSERTED",
                     "scope_markers": ["ASSERTED"], "event_time": None, "time_text": ""}}
    raw = json.dumps({"schema_version": 2, "statements": [candidate]})
    fake.set_response(core.Extractor.compute_prompt_input_hash(core.claim_extraction_prompt(c["passage"], c["holder"])), raw)
    parsed = json.loads(core.claim_parse_response(raw, c["passage"], c["holder"], True))
    require(not parsed["errors"], "smoke positive fixture rejected")
    prompt = source_prompts(core, c, parsed["statements"])["admission"]
    fake.set_response(core.Extractor.compute_prompt_input_hash(prompt),
        '{"schema_version":1,"decisions":[{"index":0,"retain":true,"reason":"supported"}]}')
    return fake


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    v = sub.add_parser("verify")
    v.add_argument("run", type=Path)
    for command in ("run", "smoke"):
        child = sub.add_parser(command)
        child.add_argument("--previous", type=Path, required=True)
        child.add_argument("--out", type=Path, required=True)
        child.add_argument("--source-turns", action="store_true", help="Use native versioned turns for reviewed scoped sources")
        child.add_argument("--output-mode", choices=OUTPUT_MODES, default="legacy")
        child.add_argument("--capability-report", type=Path)
        if command == "run":
            child.add_argument("--model", default="deepseek-v3", help="Explicit extraction/admission model; no fallback")
            child.add_argument("--json-object-output", action="store_true",
                               help="Request native JSON mode for fresh extraction/admission only")
    args = parser.parse_args()
    from starling import _core
    if args.command == "verify":
        from verify_socialmem_claim_contract import verify
        print(json.dumps(verify(args.run), indent=2))
        return
    if args.output_mode != "legacy" and args.capability_report is None:
        print(json.dumps(capability_blocked(args.out, _core, args.output_mode, "missing_capability_report")))
        return
    llm, transport = None, None
    if args.output_mode != "legacy":
        require(not getattr(args, "json_object_output", False), "legacy JSON flag conflicts with explicit output mode")
        from probe_socialmem_output_capability import check_report
        report = load(args.capability_report)
        if args.command == "run":
            llm, transport = trial.extraction.build_llm(_core, model=args.model)
        checked = check_report(_core, report, transport or report["transport"], args.output_mode)
        if not checked["ready"]:
            print(json.dumps(capability_blocked(args.out, _core, args.output_mode, ";".join(checked["reasons"]),
                                               report=report, transport=report["transport"])))
            return
    if args.command == "smoke":
        inputs, _, _ = prepare(args.previous)
        run(args.previous, args.out, _core, smoke_llm(_core, inputs),
            lambda _prompt, _model, max_tokens: "YES" if max_tokens == 8 else "Offline answer fixture.",
            _core.StubEmbeddingAdapter(8), {"model": "FakeLLMAdapter"}, "offline",
            execution_mode="offline_smoke", source_turns=args.source_turns,
            output_mode=args.output_mode, capability_report=args.capability_report)
        return
    url = urlsplit(os.environ["OPENAI_BASE_URL"])
    require(url.scheme == "https" and url.hostname and not any((url.username, url.password, url.query, url.fragment)),
            "answer endpoint must be HTTPS without credentials/query")
    endpoint = urlunsplit(url._replace(path="/v1"))
    os.environ["OPENAI_BASE_URL"] = endpoint
    os.environ["EMBEDDING_MODEL"], os.environ["EMBEDDING_DIM"] = "qwen3.7-text-embedding", "1024"
    if llm is None:
        llm, transport = trial.extraction.build_llm(_core, json_object_output=args.json_object_output, model=args.model)
    embedder = trial.ladder._build_real_embedder(_core)
    run(args.previous, args.out, _core, llm, trial.audit._chat_completion, embedder, transport, endpoint,
        source_turns=args.source_turns, output_mode=args.output_mode, capability_report=args.capability_report)


if __name__ == "__main__":
    main()

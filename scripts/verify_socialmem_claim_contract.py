#!/usr/bin/env python3
"""Verify archived model bytes, all native ingestion replays and QA provenance."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import tempfile

import eval_socialmem_claim_contract as evaluation

load, lines, dump, digest, require = (evaluation.load, evaluation.lines, evaluation.dump,
                                     evaluation.digest, evaluation.require)


def json_value(value):
    return json.loads(json.dumps(value))


def normalized_evidence(rows):
    claims = []
    for row in rows:
        if not row.get("semantic_claim_json"):
            continue
        claim = json.loads(row["semantic_claim_json"])
        claim["source_span"].pop("engram_ref", None)
        claims.append(json.dumps(claim, ensure_ascii=False, sort_keys=True))
    return sorted(claims)


def check_replay_attempt(replay, recorded):
    for key in ("errors", "candidates", "retained", "terminal", "semantic_rejected", "semantic_rejections"):
        require(replay[key] == recorded[key], f"native receipt replay mismatch: {key}")
    for key in ("called", "semantic_rejected"):
        require(replay["admission"][key] == recorded["admission"][key], f"native admission replay mismatch: {key}")


def check_channel_protocol(core, channel, contract, mode, *, evidence_id="", real=False, max_retries=0):
    from probe_socialmem_output_capability import contract_values

    require(channel["output_mode"] == mode and channel["output_contract"] == contract,
            "protocol request identity drift")
    require(channel["schema_sha256"] == core.structured_output_schema_sha256(contract_values(core)[contract]),
            "protocol schema drift")
    # 外部前置报告不冒充当前实例缓存；原生 ID 存在时必须与所用报告一致。
    require(not channel["capability_evidence_id"] or channel["capability_evidence_id"] == evidence_id,
            "protocol capability evidence drift")
    attempts = channel["http_attempts"]
    require(type(channel["attempt_count"]) is int and channel["attempt_count"] == len(attempts),
            "protocol attempt count drift")
    require(len(attempts) <= 1 + max_retries and (real or not attempts), "protocol attempt budget drift")
    if real and channel["ok"]:
        require(bool(attempts), "real protocol success lacks HTTP evidence")
    for index, attempt in enumerate(attempts, 1):
        require(attempt["attempt"] == index and attempt["retry_policy"] == "connect_only",
                "protocol attempt identity/retry drift")
        require(attempt["response_bytes"] == len(attempt["response_body"].encode()) and
                attempt["streamed_bytes"] == 0 and type(attempt["elapsed_ms"]) is int and attempt["elapsed_ms"] >= 0,
                "protocol attempt body/timing drift")
        if index < len(attempts):
            require(attempt["execution_certainty"] == "not_connected" and attempt["http_status"] == 0 and
                    attempt["response_bytes"] == 0, "protocol retried an uncertain POST")
    if attempts:
        require(channel["raw_http_response"] == attempts[-1]["response_body"], "protocol HTTP raw evidence drift")
    if channel["ok"]:
        require(channel["raw_response"] == channel["raw_completion"], "protocol completion was rewritten")
    else:
        require(channel["raw_response"] == "", "failed protocol changed success-only field")


def check_embedding_counts(qa, initial, final, mode):
    keys = {"request_count", "embed_calls", "batch_calls"}
    snapshots = [initial, *(s for q in qa for s in (q["embedding_counts_before"], q["embedding_counts_after"])), final]
    for snapshot in snapshots:
        require(set(snapshot) == keys, "embedding counter fields changed")
        if mode == "offline_smoke" and all(v is None for v in snapshot.values()):
            continue
        require(all(type(v) is int and v >= 0 for v in snapshot.values()), "embedding counter unavailable or invalid")
    previous = initial
    for item in qa:
        before, after = item["embedding_counts_before"], item["embedding_counts_after"]
        require(before == previous, "embedding counter snapshot gap")
        require(all((after[k] is None and before[k] is None and mode == "offline_smoke") or
                    (type(before[k]) is int and type(after[k]) is int and after[k] >= before[k]) for k in keys),
                "embedding counter decreased")
        previous = after
    require(previous == final, "embedding final counter snapshot mismatch")


def check_link_excerpt(source, claim, link):
    span = claim["source_span"]
    start, end = link["source_excerpt_span_start"], link["source_excerpt_span_end"]
    require(type(start) is int and type(end) is int and start == span["span_start"] and
            start < end <= span["span_end"], "QA native source excerpt interval altered")
    try:
        expected = source.encode()[start:end].decode()
    except UnicodeDecodeError as exc:
        raise ValueError("QA native source excerpt cuts UTF-8 character") from exc
    require(link["source_excerpt"] == expected, "QA native source excerpt altered")
    require(type(link["source_excerpt_truncated"]) is bool and
            link["source_excerpt_truncated"] == (end < span["span_end"]), "QA native source excerpt truncation altered")


def check_case(core, run, case, base, templates, result):
    require((result["track"], result["id"]) == (case["track"], case["id"]), "case identity mismatch")
    path = run / result["database"]
    require(path.resolve().is_relative_to(run.resolve()), "invalid database path")
    require(digest(path) == result["database_sha256"], "database artifact mismatch")
    require(evaluation.database_rows(path) == result["after"], "database rows differ from receipt")
    require(all(row["tenant_id"] == "default" for row in result["after"]), "unexpected statement tenant")
    expected_rows = [r for r in result["after"] if r["id"] in result["receipt"]["statement_ids"]]
    require(result["rows"] == expected_rows, "stored candidate rows differ from commit receipt")
    require({r["id"] for r in expected_rows} == set(result["receipt"]["statement_ids"]), "commit references missing row")
    require(evaluation.evidence_errors(core, case, result["rows"], path) == result["evidence_errors"],
            "evidence audit mismatch")
    receipt = result["claim_receipt"]
    require(receipt["schema_version"] in (1, 2) and receipt["semantic_claim_contract"], "wrong native receipt contract")
    require(receipt["source_payload_hash"] == hashlib.sha256(case["passage"].encode()).hexdigest(), "source hash mismatch")
    require(receipt["holder"] == case["holder"] and len(receipt["attempts"]) == 1, "holder/retry receipt mismatch")
    attempt = receipt["attempts"][0]
    if receipt["schema_version"] == 2:
        mode = attempt["extraction"]["structured_output"]["output_mode"]
        for name, kind in (("extraction", "claim_extraction_v2"), ("admission", "claim_admission_v1")):
            channel = attempt[name]
            if name == "admission" and not channel["called"]:
                continue
            metadata = channel["structured_output"]
            require(all(metadata[key] == channel[key] for key in ("raw_response", "ok", "error")),
                    "protocol metadata differs from channel")
            check_channel_protocol(core, metadata, kind, mode,
                evidence_id=metadata["capability_evidence_id"], real=bool(metadata["http_attempts"]),
                max_retries=max(0, metadata["attempt_count"] - 1))
    require(attempt["extraction"]["prompt"] == core.claim_extraction_prompt(case["passage"], case["holder"]),
            "extraction prompt differs from native source-only prompt")
    for name in ("extraction", "admission"):
        channel = attempt[name]
        if name == "admission" and not channel["called"]:
            continue
        require(channel["prompt_input_hash"] == core.Extractor.compute_prompt_input_hash(channel["prompt"]),
                "native channel prompt hash mismatch")
    if case["track"] == "fixed_controls":
        raw = json.dumps({"schema_version": 2, "statements": [case["candidate"]]}, ensure_ascii=False)
        require(attempt["extraction"]["raw_response"] == raw and attempt["extraction"]["ok"], "fixed candidate changed")
    if attempt["admission"]["called"]:
        expected = core.claim_admission_prompt(case["passage"], json.dumps(attempt["candidates"], ensure_ascii=False))
        require(attempt["admission"]["prompt"] == expected, "admission prompt differs from native candidates/source")
        if "external_admission_call" in receipt:
            require(all(receipt["external_admission_call"][k] == attempt["admission"][k]
                        for k in ("prompt", "prompt_input_hash", "raw_response", "ok", "error")),
                    "fixed candidate real admission differs from native replay")
    with tempfile.TemporaryDirectory(prefix="claim-native-replay-") as tmp:
        replay_out = Path(tmp)
        (replay_out / "databases").mkdir()
        replay = evaluation.evaluate_case(core, case, base, templates, replay_out, replay=receipt, record=False)
        for key in ("before", "after", "rows"):
            require(evaluation.judge_candidate(replay[key]) == evaluation.judge_candidate(result[key]),
                    f"native semantic replay mismatch: {case['id']}/{key}")
            require(normalized_evidence(replay[key]) == normalized_evidence(result[key]), "native evidence replay mismatch")
        for key in ("native_ok", "outcome", "base_semantics_preserved", "p1_baseline", "p1_combined"):
            if key in result:
                require(json_value(replay[key]) == result[key], f"native replay result mismatch: {key}")
        require(Counter(status for _, status in replay["pipelines"]) == Counter(status for _, status in result["pipelines"]),
                "native pipeline status replay mismatch")
        check_replay_attempt(replay["claim_receipt"]["attempts"][0], attempt)


def check_votes(group, case, candidate, track, votes, raw_votes):
    require(len(votes) == len(raw_votes) == 3, "judge vote denominator mismatch")
    require(group["judgment"]["votes"] == votes, "judge group votes differ")
    prompt = evaluation.trial.audit._judge_prompt(case["question"], case["answer"], candidate)
    for repeat, (vote, raw) in enumerate(zip(votes, raw_votes, strict=True)):
        require((raw["track"], raw["id"], raw["arm"], raw["repeat"]) ==
                (track, group["id"], group["arm"], repeat), "judge identity/order mismatch")
        require(raw["prompt"] == prompt, "judge source/reference/candidate mismatch")
        require(vote == {**raw, **evaluation.contracts.parse_vote(raw["raw"], raw["error"])}, "judge vote parsing mismatch")
    count = sum(v["accepted"] for v in votes)
    require(group["judgment"]["acceptances"] == count and group["judgment"]["ok"] == (count >= 2),
            "judge majority mismatch")
    require(group["judgment"]["failed"] == sum(not v["valid"] for v in votes), "judge technical failure count mismatch")


def check_observer_recall(core, path, qa, record):
    recall = qa["recall"]
    scopes = recall["receipts"]
    if not scopes:
        require(bool(qa["error"]) and recall["block"] == "" and recall["statement_ids"] == [] and
                recall["labels"] == [] and recall["evidence_links"] == [] and recall["abstained"],
                "QA missing native scopes without explicit technical failure")
        return
    expected_holders = sorted({r["holder_id"] for r in qa["after"] if r["tenant_id"] == "default"}) or ["alice"]
    require([r["holder"] for r in scopes] == expected_holders, "QA native holder scope inventory changed")
    require(qa["error"] == evaluation.retrieval_degradation_error(recall), "QA native degradation status changed")
    require(hasattr(core, "get_statement_row"), "native tenant-scoped statement getter required for QA verification")
    candidates = []
    with tempfile.TemporaryDirectory(prefix="claim-qa-render-verify-") as tmp:
        # The native getter and renderer operate on an isolated copy; no live
        # embedding request or Python eligibility/rendering implementation.
        with evaluation.supplement.copied_runtime(path, Path(tmp) / "verified.db") as (rt, _):
            for scope in scopes:
                require(scope["tenant_id"] == "default" and scope["perspective"] == "" and scope["k"] == 10 and
                        scope["intent"] == "FACT_LOOKUP" and scope["query_text"] == record["question"] and
                        scope["as_of_iso"] == evaluation.NOW, "QA native scope query changed")
                require(bool(scope["scope_steps"]), "QA native scope plan missing")
                for step in scope["scope_steps"]:
                    filters = dict(step["filters"])
                    require(step["holder_scope"] == scope["holder"] and
                            filters.get("tenant_id") == "default" and
                            filters.get("holder_scope") == scope["holder"] and
                            filters.get("perspective") == scope["holder"], "QA native scope plan crossed holder/tenant")
                require(all(set(d) == {"path", "reason", "fallback"} and
                            all(isinstance(v, str) for v in d.values()) for d in scope["degraded_paths"]),
                        "QA native degradation record malformed")
                breakdown = scope["score_breakdown"]
                require(all(set(score) == set(evaluation.SCORE_FIELDS) for score in breakdown), "QA score fields changed")
                require(len({score["statement_id"] for score in breakdown}) == len(breakdown), "QA duplicate score identity")
                require(all(type(v) in (int, float) and math.isfinite(v)
                            for score in breakdown for key, v in score.items() if key != "statement_id"),
                        "QA nonfinite native score")
                scores = {score["statement_id"]: score["final_score"] for score in breakdown}
                require(scope["scores"] == scores, "QA score receipt differs from breakdown")
                entries = scope["entries"]
                require(scope["returned"] == len(entries) <= scope["k"], "QA native scope entry count changed")
                require((not entries and bool(scope["abstention_reason"])) if scope["abstained"] else
                        ([e["row"]["id"] for e in entries] == [s["statement_id"] for s in breakdown]),
                        "QA native entries differ from scope outcome/breakdown")
                expected_links = {(e["row"]["tenant_id"], e["row"]["id"]) for e in entries
                                  if e["row"]["semantic_claim_json"]}
                actual_links = [(link["tenant_id"], link["statement_id"]) for link in scope["evidence_links"]]
                require(len(actual_links) == len(expected_links) and set(actual_links) == expected_links,
                        "QA native selected claim link inventory mismatch")
                native_lines = []
                for entry in entries:
                    row = entry["row"]
                    require(row["tenant_id"] == scope["tenant_id"] and row["holder_id"] == scope["holder"],
                            "QA native entry crossed holder/tenant")
                    native = core.get_statement_row(rt.adapter, scope["tenant_id"], row["id"])
                    require(native is not None and evaluation.native_row_snapshot(native) == row,
                            "QA native entry row differs from database")
                    require(entry["score"] == scores.get(row["id"]), "QA native entry score differs from receipt")
                    label = getattr(core.ContextPackLabel, entry["label"], None)
                    require(label is not None, "QA native label invalid")
                    line = core.render_context_line(native, label)
                    require(entry["line"] == line, "QA native entry rendering changed")
                    native_lines.append(line)
                    candidates.append(entry)
                if not scope["abstained"]:
                    require(scope["context_pack"] == "\n".join(native_lines), "QA scope context pack changed")
    require(len({e["row"]["id"] for e in candidates}) == len(candidates), "QA candidate appears in multiple holder scopes")
    selected = sorted(candidates, key=lambda e: (-e["score"], e["row"]["id"]))[:10]
    require(recall["statement_ids"] == [e["row"]["id"] for e in selected], "QA observer top-k selection changed")
    require(recall["labels"] == [e["label"] for e in selected], "QA observer labels differ from native entries")
    expected_links = {(e["row"]["tenant_id"], e["row"]["id"]) for e in selected if e["row"]["semantic_claim_json"]}
    actual_links = [(link["tenant_id"], link["statement_id"]) for link in recall["evidence_links"]]
    require(len(actual_links) == len(expected_links) and set(actual_links) == expected_links,
            "QA observer selected claim link inventory mismatch")
    require(recall["block"] == "\n".join(e["line"] for e in selected), "QA observer block differs from native rendering")
    require(recall["abstained"] == (not selected), "QA observer abstention changed")


def check_qa_database(core, run, qa, record, inputs, result_map):
    path = run / qa["database"]
    require(path.resolve().is_relative_to(run.resolve()) and digest(path) == qa["database_sha256"], "QA database artifact drift")
    require(evaluation.database_rows(path) == qa["after"], "QA database rows mismatch")
    require(all(r["tenant_id"] == "default" for r in qa["after"]), "QA tenant drift")
    check_observer_recall(core, path, qa, record)
    by_id = {r["id"]: r for r in qa["before"]}
    require(evaluation.judge_candidate([by_id[r["id"]] for r in qa["base_rows"]]) ==
            evaluation.judge_candidate(qa["base_rows"]), "QA baseline changed before sleep")
    source = inputs["frozen_sources"][inputs["records"].index(record)]
    original = evaluation.trial.temporal.statement_rows(Path(source["path"]))
    require(evaluation.judge_candidate(original) == evaluation.judge_candidate(qa["base_rows"]), "QA source semantics changed")
    selected = [c for c in inputs["scoped"] if c["item_id"] == record["item_id"]]
    expected_ids = [c["id"] for c in selected] if qa["arm"] == "structured" else []
    require([r["id"] for r in qa["receipts"]] == expected_ids, "QA source ingestion schedule changed")
    for receipt in qa["receipts"]:
        rows = [by_id[sid] for sid in receipt["statement_ids"]]
        prior = result_map[("scoped", receipt["id"])]
        require(evaluation.judge_candidate(rows) == evaluation.judge_candidate(prior["rows"]), "QA contract replay changed semantics")
        require(normalized_evidence(rows) == normalized_evidence(prior["rows"]), "QA evidence replay changed")
    after = {r["id"]: r for r in qa["after"]}
    recall = qa["recall"]
    require(len(recall["statement_ids"]) <= 10 and len(set(recall["statement_ids"])) == len(recall["statement_ids"]),
            "QA observer recall exceeds k or duplicates rows")
    require(all(sid in after for sid in recall["statement_ids"]), "QA recalled unknown row")
    require(recall["as_of_iso"] == evaluation.NOW, "QA query time changed")
    links = [link for r in recall["receipts"] for link in r["evidence_links"]
             if link["statement_id"] in recall["statement_ids"]]
    require(links == recall["evidence_links"], "QA evidence link selection changed")
    for link in links:
        stored = after[link["statement_id"]]
        claim = json.loads(stored["semantic_claim_json"])
        require(link["tenant_id"] == stored["tenant_id"] == "default", "QA evidence tenant mismatch")
        require(all(link.get(k) == v for k, v in claim.items()), "QA evidence annotation differs from stored claim")
        case = next(c for c in selected if c["holder"] == stored["holder_id"])
        errors = evaluation.evidence_errors(core, case, [stored], path)
        require(not errors, "QA evidence source integrity failed")
        if "source_excerpt" in link:
            check_link_excerpt(case["passage"], claim, link)
    # Native planner receipts supply the authorization proof. This check does not
    # make new eligibility decisions or call live embeddings during verification.
    for receipt in recall["receipts"]:
        require(receipt["source_time_fallback_count"] == sum(l["event_time"] is None for l in receipt["evidence_links"]),
                "QA source time fallback counter changed")


def verify_blocked(run, core, manifest):
    require(manifest["schema_version"] == 2 and manifest["output_mode"] in evaluation.OUTPUT_MODES[1:],
            "invalid capability-blocked contract")
    expected_paths = set(manifest["artifact_sha256"]) | {"manifest.json"}
    actual_paths = {str(p.relative_to(run)) for p in run.rglob("*") if p.is_file() and p.name != "verification.json"}
    require(actual_paths == expected_paths, "blocked artifact inventory changed")
    evaluation.verify_artifacts(run, manifest["artifact_sha256"])
    require(digest(Path(core.__file__)) == manifest["core_sha256"], "current native core differs from blocked core")
    require(digest(run / "source_archive" / manifest["core_filename"]) == manifest["core_sha256"], "archived core drift")
    evaluation.verify_artifacts(run / "source_archive", manifest["source_sha256"])
    for key in ("records", "extraction", "injected_controls", "admission", "answer", "judge"):
        require(type(manifest["actual"][key]) is int and manifest["actual"][key] == 0, "blocked cohort made calls")
    require(not (run / "databases").exists(), "blocked cohort created databases")
    require(manifest["quality"] is None and manifest["promotion_ready"] is False, "blocked run fabricated quality")
    summary = load(run / "results.json")
    require(summary == {"status": "capability_blocked", "reason": manifest["reason"], "quality": None,
                        "promotion_ready": False}, "blocked summary drift")
    if manifest["reason"] == "missing_capability_report":
        require(manifest["actual"]["probe"] == 0 and not (run / "capability_report.json").exists(),
                "missing capability report has probe calls")
    else:
        from probe_socialmem_output_capability import check_report
        report = load(run / "capability_report.json")
        checked = check_report(core, report, manifest["extract_transport"], manifest["output_mode"],
                               at=datetime.fromisoformat(manifest["created_at"]))
        require(not checked["ready"] and manifest["reason"] == ";".join(checked["reasons"]),
                "blocked capability reason drift")
        require(manifest["actual"]["probe"] == report["request_count"], "blocked probe count drift")
    receipt = {"status": "verified", "run_status": "capability_blocked", "native_ingestion_replays": 0,
        "quality": None, "manifest_sha256": digest(run / "manifest.json"),
        "artifact_sha256": {str(p.relative_to(run)): digest(p) for p in sorted(run.rglob("*"))
                            if p.is_file() and p.name != "verification.json"}}
    dump(run / "verification.json", receipt)
    return {k: v for k, v in receipt.items() if k != "artifact_sha256"}


def check_base_memory_provenance(previous, parent, manifest):
    if "base_memory_provenance" in manifest:
        require(manifest["base_memory_provenance"] == evaluation.base_memory_provenance(previous, parent),
                "base memory provenance drift")


def verify(run, core=None):
    if core is None:
        from starling import _core as core
    run = run.resolve()
    manifest = load(run / "manifest.json")
    if manifest["status"] == "capability_blocked":
        return verify_blocked(run, core, manifest)
    require(manifest["status"] in ("complete", "complete_with_errors"), "run not completed")
    require(manifest["execution_mode"] in ("real", "offline_smoke"), "unknown run mode")
    require(manifest["planned"] == evaluation.EXPECTED and manifest["query_time"] == evaluation.NOW, "run protocol drift")
    evaluation.verify_artifacts(run, manifest["artifact_sha256"])
    require(digest(Path(core.__file__)) == manifest["core_sha256"], "current native core differs from evaluated core")
    require(digest(run / "source_archive" / manifest["core_filename"]) == manifest["core_sha256"], "archived native core drift")
    evaluation.verify_artifacts(run / "source_archive", manifest["source_sha256"])
    evaluation.verify_artifacts(evaluation.ROOT, manifest["source_sha256"])
    require(digest(run / "before_core_manifest.json") == manifest["before_core_manifest_sha256"], "before-build lineage changed")
    previous = Path(manifest["previous"])
    require(digest(previous / "verification.json") == manifest["previous_verification_sha256"], "historical parent verification changed")
    inputs, templates, parent = evaluation.prepare(previous)
    check_base_memory_provenance(previous, parent, manifest)
    source_mode = manifest.get("source_input_mode", "legacy_text")
    require(source_mode in ("legacy_text", "source_turn_v1"), "unknown source input mode")
    if source_mode == "source_turn_v1":
        inputs = evaluation.with_source_turns(core, inputs)
    require(load(run / "inputs.json") == inputs and load(run / "baseline_prompts.json") == templates, "frozen cohort drift")
    require(parent["core_sha256"] == manifest["historical_core_sha256"], "historical core lineage mismatch")
    output_mode = manifest.get("output_mode", "legacy")
    expected_policy = {**evaluation.POLICY, **({"claim_output_mode": output_mode} if output_mode != "legacy" else {})}
    require(load(run / "policies.json") == expected_policy, "claim policy changed")
    capability_check = None
    if output_mode != "legacy":
        from probe_socialmem_output_capability import check_report
        require(manifest["schema_version"] == 2 and manifest["capability_binding"] == "external_preflight_report",
                "wrong structured archive version")
        require(digest(run / "capability_report.json") == manifest["capability_report_sha256"], "capability report drift")
        capability_check = check_report(core, load(run / "capability_report.json"), manifest["extract_transport"],
            output_mode, at=datetime.fromisoformat(manifest["capability_checked_at"]))
        require(capability_check["ready"] and capability_check == manifest["capability_check"], "capability preflight drift")
    source_units = {f"{c['track']}/{c['id']}": json.loads(core.claim_source_units(c["passage"]))
        for track in evaluation.TRACKS for c in inputs[track]}
    require(load(run / "source_units.json") == source_units, "native source inventory changed")
    results = lines(run / "cases.jsonl")
    schedule = [c for track in evaluation.TRACKS for c in inputs[track]]
    require(len(results) == len(schedule) == 140, "native record denominator mismatch")
    extraction, injections, admissions = (lines(run / f) for f in ("extraction_calls.jsonl", "injections.jsonl", "admission_calls.jsonl"))
    require(len(extraction) == 76 and len(injections) == 64 and len(admissions) <= 140, "model schedule denominator mismatch")
    expected_channels = {"extraction": [], "injections": [], "admissions": []}
    for case, result in zip(schedule, results, strict=True):
        base = inputs["base_calls"].get(case["id"]) if case["track"] in ("p1", "synthetic") else None
        check_case(core, run, case, base, templates, result)
        attempt = result["claim_receipt"]["attempts"][0]
        if output_mode != "legacy":
            for name, kind in (("extraction", "claim_extraction_v2"), ("admission", "claim_admission_v1")):
                if name == "admission" and not attempt[name]["called"]:
                    continue
                injected = case["track"] == "fixed_controls" and name == "extraction"
                channel = result["claim_receipt"].get("external_admission_call", attempt[name]) if name == "admission" else attempt[name]
                check_channel_protocol(core, channel["structured_output"], kind, output_mode,
                    evidence_id=capability_check["evidence_ids"][kind],
                    real=manifest["execution_mode"] == "real" and not injected,
                    max_retries=manifest["extract_transport"].get("max_retries", 0))
        target = "injections" if case["track"] == "fixed_controls" else "extraction"
        expected_channels[target].append({"id": case["id"], "track": case["track"], **attempt["extraction"]})
        if attempt["admission"]["called"]:
            actual = result["claim_receipt"].get("external_admission_call", attempt["admission"])
            expected_channels["admissions"].append({"id": case["id"], "track": case["track"], **actual})
    require(expected_channels == {"extraction": extraction, "injections": injections, "admissions": admissions},
            "model channel journal differs from native receipts")
    judgments, answers, votes, raw_votes = (lines(run / "judgments.jsonl"), load(run / "answer_results.json"),
                                            lines(run / "judge_calls.jsonl"), lines(run / "judge_responses.jsonl"))
    require(len(judgments) == 32 and len(answers) == 8 and len(votes) == len(raw_votes) == 120,
            "judge/answer denominator mismatch")
    result_map = {(r["track"], r["id"]): r for r in results}
    judge_schedule = []
    for i, case in enumerate(inputs["synthetic"]):
        for arm in (("frozen", "contract") if i % 2 == 0 else ("contract", "frozen")):
            memory = inputs["comparisons"][case["id"]] if arm == "frozen" else result_map[("synthetic", case["id"])]
            judge_schedule.append((case, arm, memory))
    for i, (entry, (case, arm, memory)) in enumerate(zip(judgments, judge_schedule, strict=True)):
        candidate = evaluation.judge_candidate(memory["after"])
        require((entry["id"], entry["arm"], entry["candidate"]) == (case["id"], arm, candidate), "synthetic judge arm changed")
        require(entry["native_ok"] == (memory["native_ok"] and not memory["base_receipt"]["extraction_failed"]), "synthetic native status changed")
        check_votes(entry, case, candidate, "synthetic", votes[i * 3:i * 3 + 3], raw_votes[i * 3:i * 3 + 3])
    qa = []
    for i, record in enumerate(inputs["records"]):
        for arm in (("baseline", "structured") if i % 2 == 0 else ("structured", "baseline")):
            item = load(run / f"qa_{record['item_id']}_{arm}.json")
            require((item["id"], item["arm"]) == (record["item_id"], arm), "QA archive identity changed")
            check_qa_database(core, run, item, record, inputs, result_map)
            qa.append(item)
    check_embedding_counts(qa, manifest["embedding_counts_initial"],
        manifest["actual"]["embedding_adapter_counts"], manifest["execution_mode"])
    answer_calls = lines(run / "answer_calls.jsonl")
    raw_answers = lines(run / "answers.jsonl")
    require(len(answer_calls) == len(raw_answers) == 8, "answer calls denominator mismatch")
    answer_schedule = [(record, arm) for record in inputs["records"] for arm in ("baseline", "structured", "linked", "full")]
    for i, (answer, call, raw_answer, (record, arm)) in enumerate(zip(answers, answer_calls, raw_answers, answer_schedule, strict=True)):
        require((answer["id"], answer["arm"]) == (record["item_id"], arm), "QA answer schedule changed")
        error = ""
        if arm == "full":
            block = evaluation.trial.pipe.recall_block(core, "S_full", adapter=None, embedder=None, index=None,
                question=record["question"], history=record["history"])["block"]
        else:
            q = next(q for q in qa if q["id"] == record["item_id"] and q["arm"] == ("structured" if arm == "linked" else arm))
            error = q["error"]
            try:
                block = evaluation.linked_context(q["recall"]) if arm == "linked" else q["recall"]["block"]
            except ValueError as exc:
                block, error = "", str(exc)
        require(call["prompt"] == evaluation.trial.ladder._ladder_prompt_free(record, block.splitlines()), "QA context/answer prompt changed")
        require(answer["response"] == call["raw"] and answer["error"] == call["error"], "QA answer raw bytes changed")
        require(answer["context_error"] == error and answer["answer_ok"] == bool(not error and not call["error"] and call["raw"].strip()),
                "QA error/answer status changed")
        require({k: v for k, v in answer.items() if k not in ("context_error", "answer_ok")} ==
                {k: v for k, v in raw_answer.items() if k != "answer_ok"}, "QA answer journal changed")
        offset = (32 + i) * 3
        check_votes(answer, record, call["raw"], "scoped", votes[offset:offset + 3], raw_votes[offset:offset + 3])
    expected_summary = evaluation.summarize(inputs, results, judgments, answers, qa)
    if "extended_labels_sha256" in manifest:
        import eval_socialmem_extended as extended
        require(digest(evaluation.EXTENDED_LABEL_PATH) == manifest["extended_labels_sha256"], "extended label drift")
        labels = load(run / "extended_labels.json")
        require(labels == load(evaluation.EXTENDED_LABEL_PATH), "archived extended label drift")
        expected_summary["extended_labels"] = extended.summarize(labels, inputs["synthetic"], results)
    require(load(run / "results.json") == expected_summary, "summary recomputation mismatch")
    require(manifest["errors"] == expected_summary["errors"] and manifest["status"] == evaluation.completion_status(manifest["errors"]),
            "run completion status mismatch")
    for key, expected in (("records", 140), ("extraction", 76), ("injected_controls", 64),
                          ("admission", len(admissions)), ("answer", 8), ("judge", 120)):
        require(manifest["actual"][key] == expected, f"actual {key} count changed")
    if output_mode != "legacy":
        require(manifest["actual"]["probe"] == load(run / "capability_report.json")["request_count"], "probe calls drift")
        require(manifest["actual"]["structured_http_attempts"] == sum(c["structured_output"]["attempt_count"] for c in extraction + admissions),
                "structured attempt total drift")
    require(len(list((run / "databases").glob("*.db"))) == 144, "database inventory mismatch")
    receipt = {"status": "verified", "run_status": manifest["status"], "execution_mode": manifest["execution_mode"],
        "verified_at": datetime.now(timezone.utc).isoformat(), "native_ingestion_replays": 140, "databases": 144,
        "extraction_calls": 76, "fixed_injections": 64, "admission_calls": len(admissions), "judge_votes": 120,
        "qa_validation": "archived native receipt, source, database and answer-context integrity; no live embedding rerun",
        "manifest_sha256": digest(run / "manifest.json"),
        "artifact_sha256": {str(p.relative_to(run)): digest(p) for p in sorted(run.rglob("*"))
                            if p.is_file() and p.name != "verification.json"}}
    dump(run / "verification.json", receipt)
    return {k: v for k, v in receipt.items() if k != "artifact_sha256"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.run), indent=2))


if __name__ == "__main__":
    main()

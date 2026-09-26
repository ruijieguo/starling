#!/usr/bin/env python3
"""Frozen-base diagnostic of a separate mental-state extraction pass."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
from urllib.parse import urlsplit, urlunsplit

import eval_socialmem_contracts as contracts

trial = contracts.trial
ROOT = trial.ROOT
load, lines, digest = contracts.load, contracts.lines, contracts.digest
dump, journal = trial.controls.dump, trial.ladder.append_journal
NOW = "2026-09-11T00:00:00Z"
EXPECTED = {"extraction": 100, "answer": 6, "judge": 114}
SUPPLEMENT_PROMPT = """Extract explicitly stated mental states from the source below.
This is a separate specialist pass. Allowed predicates ONLY:
feels, uncertain_about, decided_on, indifferent_to, trusts.

Return exactly one JSON array, without Markdown or commentary. Each row has:
holder, holder_perspective, subject, subject_kind, predicate, object, modality,
polarity, nesting_depth. Use holder={self}; subject_kind=cognizer; nesting_depth=0.
The subject is the actual named experiencer/decision maker/trusting person.
First-person I/my refers to the source speaker. A reported person's state has
that person as subject, with QUOTED perspective; direct self reports use
FIRST_PERSON. Do not turn another person's state into the source speaker's state.

feels: object contains the feeling AND its cause/topic, e.g. 'relieved that the
permit arrived'; modality BELIEVES. For 'I am not angry about the delay', use
object='angry about the delay', polarity=NEG. Do not duplicate the same denial
inside object. Preserve different scopes of negation when the source has them.
uncertain_about: an explicitly unresolved choice or doubt about an outcome;
object includes the issue and alternatives; modality BELIEVES, polarity POS
when the person explicitly says they are uncertain or have not decided.
decided_on: an explicit settled choice of action; modality INTENDS. Preserve
'not attend' as a POS choice to not attend; a possibility is not a decision.
indifferent_to: an explicit absence of concern/preference, modality BELIEVES.
trusts: object includes the trusted person AND task/scope, modality BELIEVES;
distrust uses NEG on the positive trust target.

Default polarity POS; UNKNOWN only when the truth of this relation is unknown.
Preserve temporal qualifiers such as 'last week', 'today', 'still', 'no longer'
in the corresponding object. Keep distinct times and feelings as distinct rows.
Resolve pronouns only when source context identifies the referent; preserve
the complete topic, alternatives, quantities and scope. Do not shorten objects
to nouns. No new facts from plausibility, questions, conditionals or politeness.
Do not extract ordinary preferences, responsibility, physical events or world
facts; other passes handle those. Return [] if no allowed explicit state exists.
If input is a JSON source record, only target_speaker's target_turn_ids authorize
claims. Other turns provide reference context only. Timestamps identify source
utterances, not necessarily when a state started. Do not assert metadata as facts.

Source:
{convo}
JSON array:
"""


def render(template, case):
    return contracts.followup.render(template, case)


def parsed(raw, ok=True):
    try:
        return trial.extraction.parse_response(raw) if ok else []
    except ValueError:
        return []


def check_supplement(case, raw, rows, receipt, ok):
    predictions = parsed(raw, ok)
    try:
        strict = isinstance(json.loads(raw), list)
    except ValueError:
        strict = False
    allowed = set(trial.EXTRA_PREDICATES)
    invalid_predicates = [i for i, r in enumerate(predictions)
                          if not isinstance(r.get("predicate"), str) or r["predicate"] not in allowed]
    actual = [{"subject": r["subject_id"], "subject_kind": r["subject_kind"],
               "predicate": r["predicate"], "object": r["object_value"],
               "modality": r["modality"].upper(), "polarity": r["polarity"].upper()} for r in rows]
    result = {"native_ok": bool(ok and not receipt["extraction_failed"]), "strict_json": strict,
              "invalid_predicates": invalid_predicates,
              "holder_mismatches": sum(r.get("holder") != case["holder"] for r in predictions),
              "raw_rules": contracts.relation_rules(predictions),
              "native_rules": contracts.relation_rules(actual),
              "raw_case_checks": contracts.case_checks(case["id"], predictions),
              "native_case_checks": contracts.case_checks(case["id"], actual),
              "raw_objects": [r.get("object") for r in predictions],
              "stored_objects": [r["object_value"] for r in rows]}
    # Exact object multiset catches native losses without depending on row UUIDs.
    from collections import Counter
    result["object_fidelity"] = (result["native_ok"] and
        all(isinstance(r.get("object"), str) for r in predictions) and
        Counter(result["raw_objects"]) == Counter(result["stored_objects"]))
    if "expected" in case:
        actual_tuples = sorted((r["subject_id"].casefold(), r["predicate"], r["object_value"].casefold(), r["polarity"])
                               for r in rows)
        expected = sorted(tuple(s.casefold() for s in r) for r in case["expected"])
        result["control_exact"] = bool(result["native_ok"] and strict and actual_tuples == expected)
    return result


def persist(core, adapter, case, template, call, now, *, supplement):
    policy = core.ValidationPolicy()
    if supplement:
        policy.extra_core_predicates = list(trial.EXTRA_PREDICATES)
        policy.preserve_text_objects = True
    payload = case["passage"].encode("utf-8")
    channel = "supplement" if supplement else "baseline"
    prepared = core.memory_remember_prepare(
        adapter, tenant_id="default", holder_id=case["holder"], interlocutor="",
        adapter_name="socialmem-supplement", source_prefix="socialmem-" + channel,
        created_at_iso8601=now, payload=payload)
    if not prepared.should_extract:
        raise ValueError("source was not admitted")
    fake = core.FakeLLMAdapter()
    fake.set_response(core.Extractor.compute_prompt_input_hash(render(template, case)),
                      call["raw"], call["ok"], call["error"])
    extracted = core.memory_extract_llm(adapter, fake, template.replace("{self}", case["holder"]),
                                        case["holder"], payload, policy)
    return core.memory_remember_commit(
        adapter, fake, tenant_id="default", holder_id=case["holder"], interlocutor="",
        prepared=prepared, llm_result=extracted, policy=policy)


def complete(core, llm, case, template, channel, out):
    prompt = render(template, case)
    try:
        response = llm.extract(prompt, core.Extractor.compute_prompt_input_hash(prompt))
        raw, ok, error = response.raw_xml, response.ok, response.error
    except Exception as exc:
        raw, ok, error = "", False, f"{type(exc).__name__}: {exc}"
    call = {"track": case["track"], "id": case["id"], "channel": channel,
            "prompt": prompt, "raw": raw, "ok": ok, "error": error}
    journal(out / "extraction_calls.jsonl", call)
    return call


def evaluate_case(core, case, base, extra, templates, out, now):
    database = out / "databases" / f"{case['track']}_{case['id']}.db"
    with trial.archived_runtime(database) as (rt, working):
        base_receipt = None
        if base is not None:
            base_receipt = persist(core, rt.adapter, case, templates["baseline"], base, now, supplement=False)
        before = trial.temporal.statement_rows(working)
        receipt = persist(core, rt.adapter, case, templates["supplement"], extra, now, supplement=True)
        after = trial.temporal.statement_rows(working)
        new_rows = [r for r in after if r["id"] in receipt["statement_ids"]]
        by_id = {r["id"]: r for r in after}
        preserved = all(all(by_id[r["id"]][f] == r[f] for f in trial.SEMANTIC_FIELDS) for r in before)
        with sqlite3.connect(working) as conn:
            pipelines = conn.execute("SELECT id,status FROM pipeline_run ORDER BY id").fetchall()
    result = {"track": case["track"], "id": case["id"], "before": before, "after": after,
              "base_receipt": base_receipt, "receipt": receipt, "rows": new_rows,
              "base_semantics_preserved": preserved, "pipelines": pipelines,
              "database": str(database.relative_to(out)), "database_sha256": digest(database),
              **check_supplement(case, extra["raw"], new_rows, receipt, extra["ok"])}
    if case["track"] == "p1":
        original, added = parsed(base["raw"], base["ok"]), parsed(extra["raw"], extra["ok"])
        result["p1_baseline"] = trial.extraction.p1.evaluate_record(case["record"], original)
        try:
            result["p1_combined"] = trial.extraction.p1.evaluate_record(case["record"], original + added)
            result["p1_error"] = None
        except (ValueError, TypeError) as exc:
            result["p1_error"] = str(exc)
            result["p1_combined"] = trial.extraction.p1.evaluate_record(case["record"], [])
    journal(out / "cases.jsonl", result)
    return result


def prepare(previous, scoped):
    from starling.extractor.prompts import EXTRACTION_PROMPT

    manifest, verification = load(previous / "manifest.json"), load(previous / "verification.json")
    if manifest["status"] != "complete" or verification["status"] != "verified":
        raise ValueError("parent run must be complete and verified")
    for name, fingerprint in verification["artifact_sha256"].items():
        if digest(previous / name) != fingerprint:
            raise ValueError("parent artifact drift")
    old_inputs, old_prompts = load(previous / "inputs.json"), load(previous / "prompts.json")
    if old_prompts["p1"]["baseline"] != EXTRACTION_PROMPT:
        raise ValueError("baseline prompt changed")
    if [c["record"] for c in old_inputs["p1"]] != lines(ROOT / "tests/data/eval_p1_corpus.jsonl"):
        raise ValueError("P1 corpus changed")
    base_calls = {r["id"]: r for r in lines(previous / "extraction_calls.jsonl")
                  if r["track"] == "p1" and r["arm"] == "baseline"}
    for case in old_inputs["p1"]:
        if base_calls[case["id"]]["prompt"] != render(EXTRACTION_PROMPT, case):
            raise ValueError("cached base prompt mismatch")
    records = [r for r in lines(scoped / "prepared_corpus.jsonl")
               if r["evaluation_protocol"]["status"] == "include"]
    if [r["item_id"] for r in records] != ["Q1_a5s1c1", "Q9_a0b1c2d3"]:
        raise ValueError("unexpected reviewed scope")
    trial.temporal.validate_diagnostic_scope(records[1])
    source_cases, sources = [], []
    for i, record in enumerate(records):
        ingestion = load(scoped / f"item_{i}" / "ingestion.json")
        source = scoped / f"item_{i}" / "frozen.db"
        if (ingestion["item_id"] != record["item_id"] or
                ingestion["record_hash"] != trial.ladder.corpus_hash([record]) or
                trial.controls.frozen_database_hash(source) != ingestion["frozen_sha256"]):
            raise ValueError("frozen scoped database mismatch")
        sources.append({"path": str(source.resolve()), "sha256": digest(source)})
        for unit in trial.source_units(record):
            # Same grouped source input as the previous predicate diagnostics.
            source_cases.append({"track": "scoped", "id": record["item_id"] + "_" + unit["holder"],
                                 "holder": unit["holder"], "passage": unit["payload"],
                                 "unit": unit, "item_id": record["item_id"]})
    controls = load(ROOT / "tests/data/eval_socialmem_supplement_controls.json")
    inputs = {"p1": old_inputs["p1"], "synthetic": old_inputs["synthetic"],
              "controls": controls, "scoped": source_cases, "records": records,
              "base_calls": base_calls, "frozen_sources": sources}
    if {k: len(inputs[k]) for k in ("p1", "synthetic", "controls", "scoped")} != {
            "p1": 50, "synthetic": 16, "controls": 8, "scoped": 10}:
        raise ValueError("unexpected diagnostic cohort size")
    return inputs, {"baseline": EXTRACTION_PROMPT, "supplement": SUPPLEMENT_PROMPT}


@contextmanager
def copied_runtime(source, database):
    from starling import runtime

    with tempfile.TemporaryDirectory(prefix="socialmem-supplement-qa-") as tmp:
        working = Path(tmp) / "working.db"
        trial.controls.backup_database(source, working)
        rt = runtime._build_local_store_sqlite_runtime(working)
        try:
            rt.start()
            yield rt, working
        finally:
            trial.controls.backup_database(working, database)


def recall_scoped(core, embedder, record, source, cases, calls, template, arm, out, now):
    database = out / "databases" / f"qa_{record['item_id']}_{arm}.db"
    receipts = []
    with copied_runtime(source, database) as (rt, working):
        base_rows = trial.temporal.statement_rows(working)
        if arm == "supplement":
            for case in cases:
                receipt = persist(core, rt.adapter, case, template, calls[case["id"]], now, supplement=True)
                receipts.append({"id": case["id"], **receipt})
        before = trial.temporal.statement_rows(working)
        if any(datetime.fromisoformat(r["created_at"]) > datetime.fromisoformat(now) for r in before):
            raise ValueError("query time precedes ingestion")
        sleep = core.ReplayScheduler(rt.adapter).run_sleep(now)
        index = core.SqliteBlobVectorIndex()
        embedding = trial.pipe.embed_seeded(core, rt.adapter, embedder, index, now)
        if embedding.get("final_health", {}).get("complete") is not True:
            raise ValueError("embedding failed")
        recall = trial.pipe.recall_block(core, "S_star", adapter=rt.adapter, embedder=embedder,
                                        index=index, question=record["question"], history=[], k=10, now_iso=now)
        after = trial.temporal.statement_rows(working)
        pipelines = trial.pipeline_rows(working)
    result = {"id": record["item_id"], "arm": arm, "base_rows": base_rows,
              "before": before, "after": after, "receipts": receipts, "embedding": embedding,
              "recall": recall, "pipelines": pipelines,
              "sleep": {k: getattr(sleep, k) for k in ("sampled", "compressed", "abstracted", "gist_failed")},
              "database": str(database.relative_to(out)), "database_sha256": digest(database)}
    dump(out / f"qa_{record['item_id']}_{arm}.json", result)
    return result


def summarize(results, judgments, answers):
    summary = {"cases": len(results), "native_failed": sum(not r["native_ok"] for r in results),
               "strict_json": sum(r["strict_json"] for r in results),
               "object_fidelity": sum(r["object_fidelity"] for r in results),
               "base_semantics_preserved": all(r["base_semantics_preserved"] for r in results),
               "invalid_predicates": sum(len(r["invalid_predicates"]) for r in results),
               "holder_mismatches": sum(r["holder_mismatches"] for r in results),
               "relation_violations": sum(len(r["native_rules"]["violations"]) for r in results),
               "controls_exact": sum(r.get("control_exact", False) for r in results),
               "p1": {}, "synthetic": {}, "answers": answers}
    for arm in ("baseline", "combined"):
        selected = [r for r in results if r["track"] == "p1"]
        counts = {field: [sum(r["p1_" + arm][field][i] for r in selected) for i in range(3)]
                  for field in trial.extraction.p1.P1_THRESHOLDS}
        summary["p1"][arm] = {"counts": counts,
                              "f1": {k: trial.extraction.p1.f1_score(*v) for k, v in counts.items()}}
    for arm in ("baseline", "supplement"):
        selected = [j for j in judgments if j["arm"] == arm]
        summary["synthetic"][arm] = {"cases": len(selected),
            "majority": sum(j["native_ok"] and j["judgment"]["ok"] for j in selected),
            "invalid_votes": sum(j["judgment"]["failed"] for j in selected)}
    return summary


def answer(chat, record, arm, block, out):
    case = {"track": "scoped", "id": record["item_id"],
            "question": record["question"], "answer": record["answer"]}
    prompt = trial.ladder._ladder_prompt_free(record, block.splitlines())
    try:
        raw, error = chat(prompt, "gpt-5.5", max_tokens=512), ""
    except Exception as exc:
        raw, error = "", f"{type(exc).__name__}: {exc}"
    journal(out / "answer_calls.jsonl", {"id": case["id"], "arm": arm, "prompt": prompt,
                                          "raw": raw, "error": error})
    judgment = contracts.judge(chat, case, arm, raw, out)
    result = {"id": case["id"], "arm": arm, "response": raw, "error": error,
              "answer_ok": bool(not error and raw.strip()), "judgment": judgment}
    journal(out / "answers.jsonl", result)
    return result


def run(previous, scoped, out, core, llm, chat, embedder, transport, endpoint, *, execution_mode="real"):
    inputs, templates = prepare(previous, scoped)
    out.mkdir(parents=True, exist_ok=False)
    (out / "databases").mkdir()
    (out / "source_archive").mkdir()
    dump(out / "inputs.json", inputs)
    dump(out / "prompts.json", templates)
    parent = load(previous / "manifest.json")
    source_paths = set(parent["source_sha256"]) | {
        "scripts/eval_socialmem_supplement.py", "scripts/verify_socialmem_supplement.py",
        "src/extractor/json_parser.cpp", "src/extractor/extractor.cpp",
        "include/starling/extractor/json_parser.hpp", "include/starling/extractor/statement_validator.hpp",
        "bindings/python/bind_06_extractor.cpp", "python/starling/_memory_core.py",
        "python/starling/extractor/config.py", "tests/data/eval_socialmem_supplement_controls.json"}
    for name in source_paths:
        target = out / "source_archive" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    shutil.copyfile(core.__file__, out / "source_archive" / Path(core.__file__).name)
    manifest = {"status": "running", "execution_mode": execution_mode,
                "started_at": datetime.now(timezone.utc).isoformat(), "query_time": NOW,
                "claim_level": "frozen_base_supplement_diagnostic", "expected_completions": EXPECTED,
                "previous": str(previous.resolve()), "previous_verification_sha256": digest(previous / "verification.json"),
                "core_sha256": digest(Path(core.__file__)), "extract_transport": transport,
                "answer_endpoint": endpoint, "answer_model": "gpt-5.5", "answer_max_tokens": 512,
                "judge_repeats": 3, "judge_max_tokens": 8,
                "embedding_model": "qwen3.7-text-embedding", "embedding_dim": 1024,
                "source_sha256": {n: digest(ROOT / n) for n in sorted(source_paths)},
                "inputs_sha256": digest(out / "inputs.json"), "prompts_sha256": digest(out / "prompts.json"),
                "protocol": "Independent five-relation supplement with verbatim native text objects. "
                "P1 uses 50 frozen baseline responses, synthetic uses 16 fresh baseline responses, "
                "eight new exact controls and ten unchanged reviewed speaker inputs. "
                "Two QA records compare archived frozen ingestion with the same ingestion plus supplement, "
                "native sleep/k=10 and full reviewed dialogue control. No gold in extraction, no quality retries. "
                "This does not measure a fresh full production ingestion or the full benchmark."}
    dump(out / "manifest.json", manifest)
    results, judgments, answers, calls = [], [], [], {}
    try:
        for track in ("p1", "synthetic", "controls", "scoped"):
            for i, case in enumerate(inputs[track]):
                print(f"[extract] {track}/{case['id']}", flush=True)
                base = inputs["base_calls"][case["id"]] if track == "p1" else None
                order = ("baseline", "supplement") if i % 2 == 0 else ("supplement", "baseline")
                for channel in order if track == "synthetic" else ("supplement",):
                    call = complete(core, llm, case, templates[channel], channel, out)
                    if channel == "baseline":
                        base = call
                    else:
                        extra = call
                calls[case["id"]] = extra
                results.append(evaluate_case(core, case, base, extra, templates, out, NOW))
        synthetic = {c["id"]: c for c in inputs["synthetic"]}
        for i, result in enumerate(r for r in results if r["track"] == "synthetic"):
            for arm in (("baseline", "supplement") if i % 2 == 0 else ("supplement", "baseline")):
                rows = result["before"] if arm == "baseline" else result["after"]
                candidate = json.dumps([{k: r[k] for k in trial.SEMANTIC_FIELDS} for r in rows], ensure_ascii=False)
                judgment = contracts.judge(chat, synthetic[result["id"]], arm, candidate, out)
                native_ok = not result["base_receipt"]["extraction_failed"]
                if arm == "supplement":
                    native_ok = native_ok and result["native_ok"]
                entry = {"id": result["id"], "arm": arm, "candidate": candidate,
                         "native_ok": native_ok, "judgment": judgment}
                journal(out / "judgments.jsonl", entry)
                judgments.append(entry)
                print(f"[judge] {result['id']}/{arm}: {judgment['acceptances']}/3", flush=True)
        for i, record in enumerate(inputs["records"]):
            for arm in (("baseline", "supplement") if i % 2 == 0 else ("supplement", "baseline")):
                selected = [c for c in inputs["scoped"] if c["item_id"] == record["item_id"]]
                recall = recall_scoped(core, embedder, record, Path(inputs["frozen_sources"][i]["path"]),
                                       selected, calls, templates["supplement"], arm, out, NOW)
                answers.append(answer(chat, record, arm, recall["recall"]["block"], out))
                print(f"[answer] {record['item_id']}/{arm}: {answers[-1]['judgment']['acceptances']}/3", flush=True)
            full = trial.pipe.recall_block(core, "S_full", adapter=None, embedder=None, index=None,
                                          question=record["question"], history=record["history"])
            answers.append(answer(chat, record, "full", full["block"], out))
        manifest.update(status="complete", completed_at=datetime.now(timezone.utc).isoformat())
    except Exception as exc:
        manifest.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        dump(out / "results.json", summarize(results, judgments, answers))
        dump(out / "manifest.json", manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--scoped", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    from starling import _core

    url = urlsplit(os.environ["OPENAI_BASE_URL"])
    if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError("endpoint must be HTTPS without credentials or query")
    endpoint = urlunsplit(url._replace(path="/v1"))
    os.environ["OPENAI_BASE_URL"] = endpoint
    os.environ["EMBEDDING_MODEL"], os.environ["EMBEDDING_DIM"] = "qwen3.7-text-embedding", "1024"
    llm, transport = trial.extraction.build_llm(_core)
    embedder = trial.ladder._build_real_embedder(_core)
    run(args.previous, args.scoped, args.out, _core, llm, trial.audit._chat_completion,
        embedder, transport, endpoint)


if __name__ == "__main__":
    main()

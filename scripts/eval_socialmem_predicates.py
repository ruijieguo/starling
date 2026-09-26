#!/usr/bin/env python3
"""Fixed predicate/fidelity factors with native replay and reviewed QA controls."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
from urllib.parse import urlsplit, urlunsplit

import eval_socialmem_temporal as temporal

extraction, controls, ladder, pipe, audit = (temporal.extraction, temporal.controls,
                                            temporal.ladder, temporal.pipe, temporal.audit)
ROOT = Path(__file__).resolve().parents[1]
ARMS = ("baseline", "fidelity", "vocabulary", "combined")
PRIMARY_ARMS = ("baseline", "combined")
EXTRA_PREDICATES = ("feels", "uncertain_about", "decided_on", "indifferent_to", "trusts")
VOCABULARY = (
    'predicate must be one of: responsible_for, knows, prefers, promises, forbids, requires, '
    'located_at, member_of, believes, doubts. Do NOT use free-form English '
    '("is responsible for", "thinks", "is handling") '
    '\u2014 pick the closest underscore form from the list above.')
VOCABULARY_EXTENSION = (
    "Additional controlled relations:\n"
    "- feels: a person's stated emotion or subjective feeling; object names that feeling and its target.\n"
    "- uncertain_about: a person's unresolved uncertainty; object names the proposition or choice at issue.\n"
    "- decided_on: a person's settled decision; object names the chosen action or option.\n"
    "- indifferent_to: a person's stated lack of preference; object names the alternatives or issue.\n"
    "- trusts: a person's trust in another; object names the trusted party and the stated scope of trust.\n"
    "For these relations, subject is the person whose state or relation is asserted. "
    "Holder still identifies the speaker asserting or reporting it. Use the existing modality, "
    "perspective and polarity schema; do not treat uncertainty as a settled decision.\n")
FIDELITY = (
    "OBJECT FIDELITY: preserve the proposition's meaning before shortening its wording. "
    "Keep emotional state, its target/cause, meaningful uncertainty, explicit lack of a decision, "
    "negation scope, and earlier-versus-current qualifiers. Keep contextual referents when needed "
    "to distinguish topics. Objects may be full clauses. Do not reinterpret an emotion, a fact, "
    "an unresolved choice, or indifference as a positive preference. "
    "When none of the allowed specific predicates accurately fits a stated claim, use believes "
    "with a complete proposition as object, preserving the subject and source perspective.\n\n")
SECOND_BREVITY = (
    "Other predicates (responsible_for, knows, requires, etc.) use the canonical short noun.")
SEMANTIC_FIELDS = ("holder_id", "holder_perspective", "subject_kind", "subject_id", "predicate",
                   "object_value", "modality", "polarity", "nesting_depth")


def with_vocabulary(template):
    if template.count(VOCABULARY) != 1:
        raise ValueError("belief vocabulary anchor drifted")
    expanded = VOCABULARY.replace("believes, doubts.", "believes, doubts, " + ", ".join(EXTRA_PREDICATES) + ".")
    return template.replace(VOCABULARY, expanded + "\n\n" + VOCABULARY_EXTENSION)


def with_fidelity(template):
    start, end = "OBJECT BREVITY:", "HOLDER vs SUBJECT (CRITICAL):"
    if template.count(start) != 1 or template.count(end) != 1 or template.count(SECOND_BREVITY) != 1:
        raise ValueError("belief fidelity anchors drifted")
    left, rest = template.split(start, 1)
    _, right = rest.split(end, 1)
    output = left + FIDELITY + end + right
    return output.replace(SECOND_BREVITY,
                          "All predicates keep enough object wording to preserve the asserted meaning.")


def belief_prompts(template):
    return {"baseline": template, "fidelity": with_fidelity(template),
            "vocabulary": with_vocabulary(template), "combined": with_vocabulary(with_fidelity(template))}


def policy(core, arm):
    if arm not in ARMS:
        raise ValueError("unknown experimental arm")
    result = core.ValidationPolicy()
    if arm in ("vocabulary", "combined"):
        result.extra_core_predicates = list(EXTRA_PREDICATES)
    return result


def synthetic_cases():
    return extraction.load(ROOT / "tests/data/eval_socialmem_predicate_cases.json")


def render_prompts(templates, holder, passage):
    expected = {"belief"} if len(templates) == 1 else {"belief", "general_fact", "episodic"}
    if set(templates) != expected:
        raise ValueError("expected belief-only or complete three-channel templates")
    return {channel: template.replace("{self}", holder).replace(
        "{passage}" if channel == "episodic" else "{convo}", passage)
        for channel, template in templates.items()}


def persist(core, adapter, holder, passage, templates, raw, arm, now):
    rendered = render_prompts(templates, holder, passage)
    if set(raw) != set(rendered):
        raise ValueError("raw response channels do not match templates")
    payload = passage.encode("utf-8")
    prepared = core.memory_remember_prepare(
        adapter, tenant_id="default", holder_id=holder, interlocutor="",
        adapter_name="socialmem-predicates", source_prefix="socialmem-predicates",
        created_at_iso8601=now, payload=payload)
    if not prepared.should_extract:
        raise ValueError("source input not admitted")
    fake = core.FakeLLMAdapter()
    for channel, prompt in rendered.items():
        fake.set_response(core.Extractor.compute_prompt_input_hash(prompt), raw[channel])
    trial_policy = policy(core, arm)
    if set(raw) == {"belief"}:
        result = core.memory_extract_llm(adapter, fake, templates["belief"], holder, payload, trial_policy)
        outcome = core.memory_remember_commit(
            adapter, fake, tenant_id="default", holder_id=holder, interlocutor="",
            prepared=prepared, llm_result=result, policy=trial_policy)
    else:
        result = core.memory_remember_extract_all(
            adapter, fake, templates["belief"], templates["episodic"], templates["general_fact"],
            holder, payload, trial_policy)
        outcome = core.memory_remember_commit_all(
            adapter, fake, tenant_id="default", holder_id=holder, interlocutor="",
            prepared=prepared, extracted=result, policy=trial_policy)
    if outcome["extraction_failed"]:
        raise ValueError("native extraction persistence failed")
    return outcome


def complete(core, llm, templates, holder, passage, identity, out):
    raw = {}
    for channel, prompt in render_prompts(templates, holder, passage).items():
        response = llm.extract(prompt, core.Extractor.compute_prompt_input_hash(prompt))
        ladder.append_journal(out / "extraction_calls.jsonl", {
            **identity, "channel": channel, "prompt": prompt, "raw": response.raw_xml,
            "ok": response.ok, "error": response.error})
        if not response.ok:
            raise ValueError(f"extraction transport failed: {response.error}")
        extraction.parse_response(response.raw_xml)
        raw[channel] = response.raw_xml
    return raw


def judge(chat, question, reference, candidate, identity, out):
    votes = []
    raw_count = 0

    def recorded_chat(prompt, model, max_tokens):
        nonlocal raw_count
        raw = chat(prompt, model, max_tokens=max_tokens)
        ladder.append_journal(out / "judge_responses.jsonl", {
            **identity, "repeat": raw_count, "prompt": prompt, "raw": raw})
        raw_count += 1
        return raw

    def sink(vote):
        votes.append(vote)
        ladder.append_journal(out / "judge_calls.jsonl", {**identity, **vote})

    ok = temporal.repeated_judge(recorded_chat, sink, 3)(question, reference, candidate, "gpt-5.5")
    return {"ok": ok, "acceptances": sum(v["accepted"] for v in votes), "votes": votes}


def pipeline_rows(path):
    with sqlite3.connect(path) as conn:
        rows = conn.execute("SELECT id,status FROM pipeline_run ORDER BY id").fetchall()
    if any(status != "finished" for _, status in rows):
        raise ValueError("unfinished native extraction pipeline")
    return rows


def pipeline_rows_with_failures(path):
    """读取原生 pipeline 状态；失败状态作为技术证据归档，不中断诊断。"""
    with sqlite3.connect(path) as conn:
        rows = conn.execute("SELECT id,status FROM pipeline_run ORDER BY id").fetchall()
    return rows, sum(status != "finished" for _, status in rows)


@contextmanager
def archived_runtime(database):
    from starling import runtime

    with tempfile.TemporaryDirectory(prefix="socialmem-predicates-") as tmp:
        working = Path(tmp) / "working.db"
        rt = runtime._build_local_store_sqlite_runtime(working)
        try:
            rt.start()
            yield rt, working
        finally:
            if working.exists():
                controls.backup_database(working, database)


def evaluate_case(core, llm, chat, case, arm, template, out, now):
    identity = {"track": case["track"], "id": case["id"], "arm": arm}
    templates = {"belief": template}
    raw = complete(core, llm, templates, case["holder"], case["passage"], identity, out)
    predicted = extraction.parse_response(raw["belief"])
    database = out / "databases" / f"{case['track']}_{case['id']}_{arm}.db"
    with archived_runtime(database) as (rt, working):
        receipt = persist(core, rt.adapter, case["holder"], case["passage"], templates, raw, arm, now)
        rows = temporal.statement_rows(working)
        try:
            pipelines = pipeline_rows(working)
            pipeline_failures = 0
        except ValueError as exc:
            if str(exc) != "unfinished native extraction pipeline":
                raise
            pipelines, pipeline_failures = pipeline_rows_with_failures(working)
    result = {**identity, "receipt": receipt, "rows": rows, "pipelines": pipelines,
              "pipeline_failures": pipeline_failures,
              "database": str(database.relative_to(out)), "database_sha256": controls.frozen_database_hash(database),
              "raw_holder_mismatches": sum(r.get("holder") != case["holder"] for r in predicted)}
    if case["track"] == "synthetic":
        by_id = {r["id"]: r for r in rows}
        candidate = json.dumps([{k: by_id[sid][k] for k in SEMANTIC_FIELDS}
                                for sid in receipt["statement_ids"]], ensure_ascii=False)
        result["candidate"] = candidate
        # No answer generation: assess the information in all stored statements.
        result["fidelity_judgment"] = judge(chat, case["question"], case["answer"], candidate, identity, out)
    else:
        result["p1_counts"] = extraction.p1.evaluate_record(case["record"], predicted)
    ladder.append_journal(out / "cases.jsonl", result)
    return result


def reviewed_records(prepared):
    corpus = extraction.load_lines(prepared / "corpus.jsonl")
    manifest = extraction.load(prepared / "manifest.json")
    if manifest["status"] != "complete" or ladder.corpus_hash(corpus) != manifest["corpus_hash"]:
        raise ValueError("reviewed corpus fingerprint mismatch")
    if {r["item_id"] for r in corpus} != {"Q1_a5s1c1", "Q9_a0b1c2d3"} or len(corpus) != 2:
        raise ValueError("expected the two reviewed diagnostic records")
    for record in corpus:
        if record["evaluation_protocol"]["status"] != "include" or record["evaluation_protocol"]["sessions"] != [1, 2, 3, 4, 5]:
            raise ValueError("expected reviewed Sessions 1-5")
        if record["item_id"] == "Q9_a0b1c2d3":
            temporal.validate_diagnostic_scope(record)
        for holder in dict.fromkeys(t["speaker"] for t in record["history"]):
            temporal.build_units(record, holder, "legacy")
    return corpus


def source_units(record):
    return [temporal.build_units(record, holder, "legacy")[0]
            for holder in sorted({t["speaker"] for t in record["history"]})]


def qa_answer(chat, record, arm, block, out):
    identity = {"track": "scoped", "id": record["item_id"], "arm": arm}
    prompt = ladder._ladder_prompt_free(record, block.splitlines())
    response = chat(prompt, "gpt-5.5", max_tokens=512)
    ladder.append_journal(out / "answer_calls.jsonl", {**identity, "prompt": prompt, "raw": response})
    if not response.strip():
        raise ValueError("empty QA answer")
    result = {**identity, "response": response,
              "judgment": judge(chat, record["question"], record["answer"], response, identity, out)}
    ladder.append_journal(out / "answers.jsonl", result)
    return result


def evaluate_scoped(core, llm, embedder, chat, record, units, arm, templates, out, now):
    identity = {"track": "scoped", "id": record["item_id"], "arm": arm}
    receipts = []
    database = out / "databases" / f"scoped_{record['item_id']}_{arm}.db"
    with archived_runtime(database) as (rt, working):
        for i, unit in enumerate(units):
            raw = complete(core, llm, templates, unit["holder"], unit["payload"],
                           {**identity, "unit_index": i}, out)
            receipt = persist(core, rt.adapter, unit["holder"], unit["payload"], templates, raw, arm, now)
            receipts.append({"unit": unit, **receipt})
            ladder.append_journal(out / "scoped_ingestion.jsonl", {**identity, "unit_index": i, **receipts[-1]})
        before = temporal.statement_rows(working)
        if any(datetime.fromisoformat(r["created_at"]) > datetime.fromisoformat(now) for r in before):
            raise ValueError("query clock precedes actual writes")
        try:
            pipelines = pipeline_rows(working)
            pipeline_failures = 0
        except ValueError as exc:
            if str(exc) != "unfinished native extraction pipeline":
                raise
            pipelines, pipeline_failures = pipeline_rows_with_failures(working)
        sleep = core.ReplayScheduler(rt.adapter).run_sleep(now)
        index = core.SqliteBlobVectorIndex()
        embedding = pipe.embed_seeded(core, rt.adapter, embedder, index, now)
        if embedding.get("final_health", {}).get("complete") is not True:
            raise ValueError("embedding failed")
        recall = pipe.recall_block(core, "S_star", adapter=rt.adapter, embedder=embedder,
                                   index=index, question=record["question"], history=[], k=10, now_iso=now)
        after = temporal.statement_rows(working)
    result = {**identity, "receipts": receipts, "before": before, "after": after,
              "pipeline_failures": pipeline_failures,
              "pipelines": pipelines, "embedding": embedding, "recall": recall,
              "sleep": {k: getattr(sleep, k) for k in ("sampled", "compressed", "abstracted", "gist_failed")},
              "database": str(database.relative_to(out)), "database_sha256": controls.frozen_database_hash(database)}
    controls.dump(out / f"scoped_{record['item_id']}_{arm}.json", result)
    return qa_answer(chat, record, arm, recall["block"], out)


def summarize(cases, answers):
    summary = {"synthetic": {}, "p1": {}, "scoped": answers}
    for arm in ARMS:
        selected = [r for r in cases if r["arm"] == arm and r["track"] == "synthetic"]
        summary["synthetic"][arm] = {
            "cases": len(selected), "majority_supported": sum(r["fidelity_judgment"]["ok"] for r in selected),
            "unanimous_supported": sum(r["fidelity_judgment"]["acceptances"] == 3 for r in selected),
            "raw_holder_mismatches": sum(r["raw_holder_mismatches"] for r in selected),
            "stored_predicates": dict(Counter(s["predicate"] for r in selected for s in r["rows"]))}
    for arm in PRIMARY_ARMS:
        counts = {field: [0, 0, 0] for field in extraction.p1.P1_THRESHOLDS}
        selected = [r for r in cases if r["arm"] == arm and r["track"] == "p1"]
        for row in selected:
            for field, values in row["p1_counts"].items():
                counts[field] = [a + b for a, b in zip(counts[field], values, strict=True)]
        summary["p1"][arm] = {"cases": len(selected), "counts": counts,
                               "f1": {field: extraction.p1.f1_score(*values) for field, values in counts.items()}}
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real-run", action="store_true", required=True)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--now-iso", required=True)
    args = parser.parse_args(argv)
    from starling import _core
    from starling.extractor.prompts import EXTRACTION_PROMPT
    from starling.extractor.episodic_prompt import EPISODIC_EXTRACTION_PROMPT
    from starling.extractor.general_fact_prompt import GENERAL_FACT_EXTRACTION_PROMPT

    now = ladder.normalize_eval_time(args.now_iso)
    prompts = belief_prompts(EXTRACTION_PROMPT)
    channels = {"general_fact": GENERAL_FACT_EXTRACTION_PROMPT, "episodic": EPISODIC_EXTRACTION_PROMPT}
    synthetic = [{**c, "track": "synthetic"} for c in synthetic_cases()]
    p1 = [{"id": r["id"], "track": "p1", "holder": r["conversation"][0]["speaker"],
           "passage": "\n".join(f"{t['speaker']}: {t['text']}" for t in r["conversation"]), "record": r}
          for r in extraction.load_lines(ROOT / "tests/data/eval_p1_corpus.jsonl")]
    records = reviewed_records(args.prepared)
    units = {r["item_id"]: source_units(r) for r in records}
    llm, transport = extraction.build_llm(_core)
    os.environ["EMBEDDING_MODEL"], os.environ["EMBEDDING_DIM"] = "qwen3.7-text-embedding", "1024"
    embedder = ladder._build_real_embedder(_core)
    url = urlsplit(os.environ["OPENAI_BASE_URL"])
    if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError("answer endpoint must be an HTTPS base without credentials or query")
    os.environ["OPENAI_BASE_URL"] = urlunsplit(url._replace(path="/v1"))
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "databases").mkdir()
    (args.out / "source_archive").mkdir()
    inputs = {"synthetic": synthetic, "p1": p1, "scoped": records, "scoped_units": units}
    controls.dump(args.out / "inputs.json", inputs)
    controls.dump(args.out / "prompts.json", {"belief": prompts, **channels})
    sources = [Path(__file__), Path(temporal.__file__), Path(extraction.__file__), Path(ladder.__file__),
               Path(pipe.__file__), Path(audit.__file__), Path(controls.__file__),
               ROOT / "scripts/eval_socialmem_scoped.py", ROOT / "scripts/eval_p1_extractor.py",
               ROOT / "python/starling/extractor/prompts.py", ROOT / "python/starling/extractor/episodic_prompt.py",
               ROOT / "python/starling/extractor/general_fact_prompt.py"]
    for source in sources:
        shutil.copyfile(source, args.out / "source_archive" / source.name)
    manifest = {"status": "running", "claim_level": "predicate_fidelity_diagnostic",
                "started_at": datetime.now(timezone.utc).isoformat(), "query_time": now,
                "extract_transport": transport, "answer_model": "gpt-5.5", "judge_repeats": 3,
                "answer_endpoint": os.environ["OPENAI_BASE_URL"], "embedding_model": "qwen3.7-text-embedding",
                "embedding_dim": 1024, "extra_predicates": list(EXTRA_PREDICATES),
                "core_sha256": controls.digest(Path(_core.__file__)),
                "inputs_sha256": controls.digest(args.out / "inputs.json"),
                "prompts_sha256": controls.digest(args.out / "prompts.json"),
                "prepared_manifest_sha256": controls.digest(args.prepared / "manifest.json"),
                "source_sha256": {str(p.relative_to(ROOT)): controls.digest(p) for p in sources},
                "expected_completions": {"extraction": len(synthetic) * 4 + len(p1) * 2 + sum(map(len, units.values())) * 6,
                                         "answer": len(records) * 3, "judge": len(synthetic) * 12 + len(records) * 9},
                "protocol": "Four factors on 16 synthetic cases; baseline/combined on unchanged 50-case P1. "
                            "Synthetic judges assess all stored statements directly, without an answerer. "
                            "Baseline/combined are preselected for reviewed two-item three-channel QA. "
                            "Same source grouping, native default sleep, k=10, one answer plus three votes. "
                            "No gold enters extraction. No production defaults changed. No quality retries."}
    controls.dump(args.out / "manifest.json", manifest)
    cases, answers = [], []
    try:
        for i, case in enumerate(synthetic + p1):
            arms = ARMS if case["track"] == "synthetic" else PRIMARY_ARMS
            offset = i % len(arms)
            for arm in arms[offset:] + arms[:offset]:
                print(f"[case] {case['track']}/{case['id']}/{arm}", flush=True)
                result = evaluate_case(_core, llm, audit._chat_completion, case, arm, prompts[arm], args.out, now)
                cases.append(result)
                if "fidelity_judgment" in result:
                    print(f"[fidelity] {result['fidelity_judgment']['acceptances']}/3", flush=True)
        for i, record in enumerate(records):
            for arm in (PRIMARY_ARMS if i % 2 == 0 else PRIMARY_ARMS[::-1]):
                print(f"[scoped] {record['item_id']}/{arm}", flush=True)
                answers.append(evaluate_scoped(_core, llm, embedder, audit._chat_completion, record,
                                               units[record["item_id"]], arm, {"belief": prompts[arm], **channels}, args.out, now))
            full = pipe.recall_block(_core, "S_full", adapter=None, embedder=None, index=None,
                                     question=record["question"], history=record["history"])
            answers.append(qa_answer(audit._chat_completion, record, "full", full["block"], args.out))
        controls.dump(args.out / "results.json", summarize(cases, answers))
        manifest.update(status="complete", completed_at=datetime.now(timezone.utc).isoformat())
    except Exception as exc:
        manifest.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        controls.dump(args.out / "manifest.json", manifest)


if __name__ == "__main__":
    main()

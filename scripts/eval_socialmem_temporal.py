#!/usr/bin/env python3
"""Compare source grouping and evidence-range presentation for reviewed Q9."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
from urllib.parse import urlsplit, urlunsplit

import eval_judge_audit as audit
import eval_ladder as ladder
import eval_ladder_pipeline as pipe
import eval_socialmem_controls as controls
import eval_socialmem_extraction as extraction
from eval_socialmem_scoped import repeated_judge

ROOT = Path(__file__).resolve().parents[1]
VARIANTS = ("legacy", "grouped", "sessions", "session_context")
TURN_FIELDS = ("turn_id", "session_index", "message_index", "speaker", "text", "observed_at")


def validate_diagnostic_scope(record):
    if (record["item_id"] != "Q9_a0b1c2d3" or
            record["source"]["network_id"] != "grp_f4a5b6c7" or
            record["evaluation_protocol"]["sessions"] != [1, 2, 3, 4, 5] or
            {t["session_index"] for t in record["history"]} != {1, 2, 3, 4, 5}):
        raise ValueError("this diagnostic requires reviewed Marcus Q9 Sessions 1-5")


def build_units(record, holder, variant):
    if variant not in VARIANTS:
        raise ValueError("unknown grouping variant")
    review = record["evaluation_protocol"]
    if review["status"] != "include":
        raise ValueError("record must be reviewed and included")
    turns = [{k: t[k] for k in TURN_FIELDS} for t in record["history"]]
    previous = None
    ids = set()
    for turn in turns:
        stamp = datetime.fromisoformat(turn["observed_at"])
        position = (turn["session_index"], turn["message_index"])
        if (turn["turn_id"] in ids or turn["session_index"] not in review["sessions"] or
                (previous is not None and (position <= previous[0] or stamp < previous[1]))):
            raise ValueError("duplicate, out-of-scope, or unordered source history")
        ids.add(turn["turn_id"])
        previous = position, stamp
    target = [t for t in turns if t["speaker"] == holder]
    if not target:
        raise ValueError("holder has no source turns")
    sessions = sorted({t["session_index"] for t in target})
    groups = [sessions] if variant in ("legacy", "grouped") else [[s] for s in sessions]
    units = []
    for selected_sessions in groups:
        targets = [t for t in target if t["session_index"] in selected_sessions]
        context = ([t for t in turns if t["session_index"] in selected_sessions]
                   if variant == "session_context" else targets)
        data = {"network_id": record["source"]["network_id"], "target_speaker": holder,
                "target_turn_ids": [t["turn_id"] for t in targets], "turns": context}
        payload = ("\n".join(f"{holder}: {t['text']}" for t in targets) if variant == "legacy"
                   else json.dumps(data, ensure_ascii=False, indent=2))
        units.append({"variant": variant, "holder": holder, "sessions": selected_sessions,
                      "target_turn_ids": data["target_turn_ids"], "turns": context,
                      "source_time_start": targets[0]["observed_at"],
                      "source_time_end": targets[-1]["observed_at"], "payload": payload})
    return units


def unit_prompt(unit, template):
    if unit["variant"] == "legacy":
        return template.replace("{convo}", unit["payload"])
    focus = (
        "INPUT SCOPE: The conversation below is a JSON source record. "
        "Extract only substantive claims voiced by target_speaker in target_turn_ids. "
        "Other turns are context for references and replies, not additional claims to store. "
        "For this input, target_speaker is the focal speaker even if another person speaks first. "
        "Set holder to target_speaker for every output. Preserve uncertainty and meaning. "
        "Source session/timestamp fields describe utterances, not necessarily event times. "
        "Follow the existing statement output schema; do not output metadata as statements.\n\n")
    return focus + template.replace("{convo}", unit["payload"])


def annotate_sources(recall, rows, receipts):
    if recall["abstained"]:
        if recall["statement_ids"]:
            raise ValueError("abstention has selected IDs")
        return []
    units = {r["engram_ref"]: r["unit"] for r in receipts}
    if len(units) != len(receipts):
        raise ValueError("duplicate source engram")
    lines = recall["block"].splitlines()
    if len(lines) != len(recall["statement_ids"]) or len(lines) != len(recall["labels"]):
        raise ValueError("recall lines do not match selected IDs")
    annotated = []
    for sid, line in zip(recall["statement_ids"], lines, strict=True):
        row = rows[sid]
        if row["tenant_id"] != "default":
            raise ValueError("unexpected tenant")
        evidence = json.loads(row["evidence_json"])
        if not evidence:
            raise ValueError("selected statement has no source evidence")
        ranges = []
        for ref in evidence:
            unit = units.get(ref["engram_ref"])
            if unit is None:
                raise ValueError("unmapped source evidence")
            ranges.append({"engram_ref": ref["engram_ref"], "sessions": unit["sessions"],
                           "from": unit["source_time_start"], "through": unit["source_time_end"]})
        prefix = " ".join(
            f"[SOURCE_RANGE sessions={','.join(map(str, r['sessions']))} "
            f"from={r['from']} through={r['through']}]" for r in ranges)
        annotated.append({"statement_id": sid, "native_line": line, "ranges": ranges,
                          "line": prefix + " " + line})
    return annotated


def presentation_lines(result, presentation):
    if presentation not in ("native", "source_ranges"):
        raise ValueError("unknown evidence presentation")
    if presentation == "native" or result["recall"]["abstained"]:
        return result["recall"]["block"].splitlines()
    return [entry["line"] for entry in result["source_annotations"]]


def statement_rows(path):
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(
            "SELECT * FROM statements WHERE tenant_id='default' ORDER BY id")]


def persist_unit(core, adapter, unit, template, raw, now):
    payload = unit["payload"].encode()
    prepared = core.memory_remember_prepare(
        adapter, tenant_id="default", holder_id=unit["holder"], interlocutor="",
        adapter_name="socialmem-temporal", source_prefix="socialmem-temporal",
        created_at_iso8601=now, payload=payload)
    if not prepared.should_extract:
        raise ValueError("source unit not admitted for extraction")
    fake = core.FakeLLMAdapter()
    prompt = unit_prompt(unit, template)
    fake.set_response(core.Extractor.compute_prompt_input_hash(prompt), raw)
    # The exact rendered prompt is supplied to native extract_llm. Its native
    # template builder appends payload when no placeholder is present, so retain
    # the placeholder here and apply the same focus prefix as the real call.
    native_template = (template if unit["variant"] == "legacy" else
                       unit_prompt({**unit, "payload": "{convo}"}, template))
    result = core.memory_extract_llm(adapter, fake, native_template, unit["holder"], payload)
    outcome = core.memory_remember_commit(
        adapter, fake, tenant_id="default", holder_id=unit["holder"], interlocutor="",
        prepared=prepared, llm_result=result)
    if outcome["extraction_failed"]:
        raise ValueError("native persistence failed")
    return {"unit": unit, **outcome}


def evaluate_variant(core, llm, embedder, record, variant, units, template, out, now):
    from starling import runtime

    receipts = []
    with tempfile.TemporaryDirectory(prefix="socialmem-temporal-") as tmp:
        working = Path(tmp) / "working.db"
        rt = runtime._build_local_store_sqlite_runtime(working)
        rt.start()
        for i, unit in enumerate(units):
            print(f"[temporal] {variant} extract {i+1}/{len(units)}", flush=True)
            prompt = unit_prompt(unit, template)
            resp = llm.extract(prompt, core.Extractor.compute_prompt_input_hash(prompt))
            ladder.append_journal(out / "extraction_calls.jsonl", {
                "variant": variant, "unit_index": i, "prompt": prompt,
                "raw": resp.raw_xml, "ok": resp.ok, "error": resp.error})
            if not resp.ok:
                raise ValueError(f"extraction transport failed: {resp.error}")
            parsed = extraction.parse_response(resp.raw_xml)
            if any(row.get("holder") != unit["holder"] for row in parsed):
                raise ValueError("model emitted a claim outside the target holder scope")
            receipt = persist_unit(core, rt.adapter, unit, template, resp.raw_xml, now)
            receipts.append(receipt)
            ladder.append_journal(out / "ingestion.jsonl", {"variant": variant, "unit_index": i, **receipt})
        before = statement_rows(working)
        with sqlite3.connect(working) as conn:
            pipelines = conn.execute("SELECT id,status FROM pipeline_run ORDER BY id").fetchall()
        if any(status != "finished" for _, status in pipelines):
            raise ValueError("unfinished extraction pipeline")
        if any(datetime.fromisoformat(r["created_at"]) > datetime.fromisoformat(now) for r in before):
            raise ValueError("query clock precedes actual writes")
        stats = core.ReplayScheduler(rt.adapter).run_sleep(now)
        index = core.SqliteBlobVectorIndex()
        embedding = pipe.embed_seeded(core, rt.adapter, embedder, index, now)
        if embedding.get("final_health", {}).get("complete") is not True:
            raise ValueError("embedding failed")
        recall = pipe.recall_block(core, "S_star", adapter=rt.adapter, embedder=embedder,
                                   index=index, question=record["question"], history=[],
                                   holder="Marcus", k=10, now_iso=now)
        after = statement_rows(working)
        annotations = annotate_sources(recall, {r["id"]: r for r in after}, receipts)
        database = out / f"{variant}.db"
        controls.backup_database(working, database)
        result = {"variant": variant, "before": before, "after": after, "recall": recall,
                  "source_annotations": annotations, "embedding": embedding,
                  "replay": {key: getattr(stats, key) for key in (
                      "sampled", "compressed", "abstracted", "gist_failed", "replay_batch_id")},
                  "database_sha256": controls.frozen_database_hash(database),
                  "pipelines": pipelines}
        del rt
    return result


def answer(chat, record, variant, presentation, lines, out):
    identity = {"variant": variant, "presentation": presentation}
    prompt = ladder._ladder_prompt_free(record, lines)
    if presentation == "source_ranges":
        prompt += ("\nSOURCE_RANGE identifies the source utterance window for each memory, "
                   "not the event time of its claim. A range is not an exact statement timestamp.")
    response = chat(prompt, "gpt-5.5", max_tokens=512)
    ladder.append_journal(out / "answer_calls.jsonl", {**identity, "prompt": prompt, "raw": response})
    if not response.strip():
        raise ValueError("empty answer")
    votes = []

    def sink(vote):
        votes.append(vote)
        ladder.append_journal(out / "judge_calls.jsonl", {**identity, **vote})

    ok = repeated_judge(chat, sink, 3)(record["question"], record["answer"], response, "gpt-5.5")
    result = {**identity, "response": response, "judge_calls": votes,
              "judge_acceptances": sum(v["accepted"] for v in votes), "ok": ok}
    ladder.append_journal(out / "answers.jsonl", result)
    print(f"[answer] {variant}/{presentation}: {result['judge_acceptances']}/3", flush=True)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real-run", action="store_true", required=True)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--now-iso", required=True)
    args = parser.parse_args(argv)
    from starling import _core
    from starling.extractor.prompts import EXTRACTION_PROMPT

    now = ladder.normalize_eval_time(args.now_iso)
    corpus = extraction.load_lines(args.prepared / "corpus.jsonl")
    prepared = extraction.load(args.prepared / "manifest.json")
    if prepared["status"] != "complete" or ladder.corpus_hash(corpus) != prepared["corpus_hash"]:
        raise ValueError("prepared corpus fingerprint mismatch")
    record, = [r for r in corpus if r["item_id"] == "Q9_a0b1c2d3"]
    validate_diagnostic_scope(record)
    inputs = {v: build_units(record, "Marcus", v) for v in VARIANTS}
    llm, transport = extraction.build_llm(_core)
    os.environ["EMBEDDING_MODEL"], os.environ["EMBEDDING_DIM"] = "qwen3.7-text-embedding", "1024"
    embedder = ladder._build_real_embedder(_core)
    url = urlsplit(os.environ["OPENAI_BASE_URL"])
    if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError("answer endpoint must be an HTTPS base without credentials or query")
    os.environ["OPENAI_BASE_URL"] = urlunsplit(url._replace(path="/v1"))
    args.out.mkdir(parents=True, exist_ok=False)
    controls.dump(args.out / "inputs.json", inputs)
    controls.dump(args.out / "record.json", record)
    sources = [Path(__file__), Path(extraction.__file__), Path(ladder.__file__), Path(pipe.__file__),
               Path(audit.__file__), Path(controls.__file__), ROOT / "scripts/eval_socialmem_scoped.py",
               ROOT / "python/starling/extractor/prompts.py"]
    (args.out / "source_archive").mkdir()
    for source in sources:
        shutil.copyfile(source, args.out / "source_archive" / source.name)
    manifest = {"status": "running", "claim_level": "one_item_target_holder_diagnostic",
                "prepared_manifest_sha256": controls.digest(args.prepared / "manifest.json"),
                "inputs_sha256": controls.digest(args.out / "inputs.json"),
                "record_sha256": controls.digest(args.out / "record.json"),
                "core_sha256": controls.digest(Path(_core.__file__)), "extract_transport": transport,
                "answer_model": "gpt-5.5", "judge_repeats": 3,
                "answer_endpoint": urlunsplit(url._replace(path="/v1", query="", fragment="")),
                "embedding_model": "qwen3.7-text-embedding", "embedding_dim": 1024,
                "query_time": now, "source_time_timezone": "unspecified; retain original strings",
                "variants": list(VARIANTS), "unit_counts": {k: len(v) for k,v in inputs.items()},
                "expected_completions": {"extraction": 12, "answer": 9, "judge": 27},
                "source_sha256": {str(p.relative_to(ROOT)): controls.digest(p) for p in sources},
                "protocol": "Fixed reviewed Sessions 1-5, target Marcus only, belief pass only. "
                            "One extraction per unit; native default sleep then k=10. "
                            "Native/source-range answers share selected IDs and order; range annotation "
                            "is application evidence presentation, not native event-time support. "
                            "Full-history control uses the complete reviewed dialogue. No gold in extraction.",
                "started_at": datetime.now(timezone.utc).isoformat()}
    controls.dump(args.out / "manifest.json", manifest)
    answers = []
    try:
        for i, variant in enumerate(VARIANTS):
            result = evaluate_variant(_core, llm, embedder, record, variant, inputs[variant],
                                      EXTRACTION_PROMPT, args.out, now)
            controls.dump(args.out / f"{variant}.json", result)
            presentations = ["native", "source_ranges"] if i % 2 == 0 else ["source_ranges", "native"]
            for presentation in presentations:
                lines = presentation_lines(result, presentation)
                answers.append(answer(audit._chat_completion, record, variant, presentation, lines, args.out))
        full = pipe.recall_block(_core, "S_full", adapter=None, embedder=None, index=None,
                                 question=record["question"], history=record["history"])
        answers.append(answer(audit._chat_completion, record, "full", "source_dialogue", full["block"].splitlines(), args.out))
        controls.dump(args.out / "results.json", {"claim_level": manifest["claim_level"], "answers": answers})
        manifest.update(status="complete", completed_at=datetime.now(timezone.utc).isoformat())
    except Exception as exc:
        manifest.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        controls.dump(args.out / "manifest.json", manifest)


if __name__ == "__main__":
    main()

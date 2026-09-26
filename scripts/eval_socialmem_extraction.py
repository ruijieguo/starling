#!/usr/bin/env python3
"""Paired preference-prompt diagnostics with raw outputs and native write replay."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import sqlite3
import tempfile
import time
from urllib.parse import urlsplit

import eval_ladder as ladder
import eval_p1_extractor as p1
import eval_socialmem_controls as controls

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads(path.read_text())


def load_lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def parse_response(raw):
    # Match the native parser's optional prose/fence envelope, then use JSON.
    start, end = raw.find("["), raw.rfind("]")
    if start < 0 or end < start:
        raise ValueError("response has no JSON array")
    rows = json.loads(raw[start:end + 1])
    if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
        raise ValueError("expected a JSON array of statement objects")
    return rows


def native_replay(raw: str, passage: str, holder: str, prompt: str, db: Path):
    if db.exists():
        raise ValueError("native replay database already exists")
    with tempfile.TemporaryDirectory(prefix="socialmem-extract-") as tmp:
        working = Path(tmp) / "working.db"
        result = _native_replay(raw, passage, holder, prompt, working)
        controls.backup_database(working, db)
    return result


def _native_replay(raw: str, passage: str, holder: str, prompt: str, db: Path):
    from starling import _core, runtime

    if db.exists():
        raise ValueError("native replay database already exists")
    rt = runtime._build_local_store_sqlite_runtime(db)
    rt.start()
    llm = _core.FakeLLMAdapter()
    llm.set_default_response(raw)
    payload = passage.encode("utf-8")
    prepared = _core.memory_remember_prepare(
        rt.adapter, tenant_id="default", holder_id=holder, interlocutor="",
        adapter_name="socialmem-extraction", source_prefix="socialmem-extraction",
        created_at_iso8601=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        payload=payload)
    if not prepared.should_extract:
        raise ValueError("native replay did not enter extraction")
    extracted = _core.memory_extract_llm(rt.adapter, llm, prompt, holder, payload)
    outcome = _core.memory_remember_commit(
        rt.adapter, llm, tenant_id="default", holder_id=holder, interlocutor="",
        prepared=prepared, llm_result=extracted)
    if outcome["extraction_failed"]:
        raise ValueError("native replay extraction failed")
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute(
            "SELECT id,tenant_id,holder_id,subject_id,subject_kind,predicate,"
            "object_value,modality,polarity,review_status,consolidation_state "
            "FROM statements WHERE tenant_id='default' ORDER BY id")]
        pipelines = [dict(r) for r in conn.execute("SELECT id,status FROM pipeline_run ORDER BY id")]
        if any(r["status"] != "finished" for r in pipelines):
            raise ValueError("native replay has unfinished extraction pipelines")
    return {"outcome": outcome, "rows": rows, "pipelines": pipelines}


def preference_score(record, rows):
    candidates = [r for r in rows if r["predicate"] == "prefers"]
    subject_ok = any(r["subject_id"] == record["subject"] and r["subject_kind"] == "cognizer"
                     for r in candidates)
    objects = {o.casefold() for o in record["objects"]}
    matches = [r for r in candidates if r["subject_id"] == record["subject"]
               and r["subject_kind"] == "cognizer" and r["holder_id"] == record["speaker"]
               and r["object_value"].casefold() in objects and r["polarity"] == record["polarity"]]
    return {"subject_ok": subject_ok, "relation_ok": len(candidates) == 1 and len(matches) == 1,
            "preference_rows": len(candidates)}


def cases():
    diagnostics = load(ROOT / "tests/data/eval_preference_polarity.json")
    result = [{"id": r["id"], "track": "preference", "holder": r["speaker"],
               "passage": f"{r['speaker']}: {r['text']}", "record": r} for r in diagnostics]
    corpus = {r["item_id"]: r for r in load_lines(
        ROOT / "build/socialmem_20260909_scoped_corpus/corpus.jsonl")}
    for item_id, holder in (("Q1_a5s1c1", "Claudette"), ("Q9_a0b1c2d3", "Marcus")):
        record = corpus[item_id]
        turns = [t for t in record["history"] if t["speaker"] == holder]
        result.append({"id": record["item_id"], "track": "source_group", "holder": holder,
                       "passage": "\n".join(f"{holder}: {t['text']}" for t in turns),
                       "source_turns": turns, "source_record_hash": ladder.corpus_hash([record])})
    for record in load_lines(ROOT / "tests/data/eval_p1_corpus.jsonl"):
        result.append({"id": record["id"], "track": "p1", "holder": record["conversation"][0]["speaker"],
                       "passage": "\n".join(f"{t['speaker']}: {t['text']}" for t in record["conversation"]),
                       "record": record})
    identities = [(r["track"], r["id"]) for r in result]
    if len(set(identities)) != len(identities):
        raise ValueError("duplicate evaluation case")
    return result


def summarize(rows):
    summary = {}
    for phase in ("before", "after"):
        phase_rows = [r for r in rows if r["phase"] == phase]
        pref = [r for r in phase_rows if r["track"] == "preference"]
        counts = {field: [0, 0, 0] for field in p1.P1_THRESHOLDS}
        for row in phase_rows:
            if row["track"] == "p1":
                for field, values in row["p1_counts"].items():
                    counts[field] = [a + b for a, b in zip(counts[field], values, strict=True)]
        summary[phase] = {
            "preference": {"scored": len(pref), **{
                field: sum(r["score"][field] for r in pref) for field in ("subject_ok", "relation_ok")}},
            "p1_scored": sum(r["track"] == "p1" for r in phase_rows),
            "p1_counts": counts, "p1_f1": {field: p1.f1_score(*values) for field, values in counts.items()},
        }
    return summary


def cached_calls(directory, inputs, prompts, core_hash, transport):
    if directory is None:
        return {}
    manifest = load(directory / "manifest.json")
    if (manifest.get("transport") != transport or
            manifest["core_sha256"] != core_hash or manifest["model"] != "deepseek-v3" or
            manifest["provider"] != "dashscope" or load(directory / "inputs.json") != inputs or
            load(directory / "prompts.json") != prompts):
        raise ValueError("raw cache configuration does not match")
    cache = {}
    for receipt in load_lines(directory / "raw_calls.jsonl"):
        key = (receipt["track"], receipt["id"], receipt["phase"])
        if key in cache:
            raise ValueError("duplicate cached completion")
        cache[key] = receipt
    return cache


def build_llm(core, *, json_object_output=False, model="deepseek-v3"):
    if not isinstance(model, str) or not model.strip() or model != model.strip():
        raise ValueError("model must be a nonempty name without surrounding whitespace")
    if not os.environ.get("DASHSCOPE_API_KEY"):
        raise ValueError("DASHSCOPE_API_KEY is required; provider fallback is not allowed")
    base = os.environ.get("DASHSCOPE_BASE_URL", "")
    url = urlsplit(base)
    if (url.scheme != "https" or not url.hostname or url.username or url.password or
            url.query or url.fragment or base.endswith("/")):
        raise ValueError("DASHSCOPE_BASE_URL must be an explicit HTTPS API base without credentials or query")
    saved = {key: os.environ.get(key) for key in ("OPENAI_API_KEY", "OPENAI_BASE_URL")}
    try:
        os.environ["OPENAI_API_KEY"] = os.environ["DASHSCOPE_API_KEY"]
        os.environ["OPENAI_BASE_URL"] = base
        config = core.OpenAIAdapterConfig.from_env()
        config.model = model
        config.json_object_output = json_object_output
        llm = core.OpenAIAdapter(config)
        transport = {"endpoint": config.base_url, "model": config.model, "temperature": 0,
                     "max_tokens": config.max_tokens, "timeout_ms": config.timeout_ms,
                     "max_retries": config.max_retries}
        if json_object_output:
            transport.update(response_format={"type": "json_object"}, response_content="verbatim")
        return llm, transport
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real-run", action="store_true", required=True)
    parser.add_argument("--before-prompt", type=Path, required=True,
                        help="Archived local Python prompt module from before the change")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--raw-cache", type=Path,
                        help="Reuse exact raw completions from an interrupted matching run")
    args = parser.parse_args(argv)
    from starling import _core
    from starling.extractor.prompts import EXTRACTION_PROMPT

    prompts = {"before": runpy.run_path(str(args.before_prompt))["EXTRACTION_PROMPT"],
               "after": EXTRACTION_PROMPT}
    if prompts["before"] == prompts["after"]:
        raise ValueError("before/after prompts must differ")
    inputs = cases()
    llm, transport = build_llm(_core)
    core_hash = controls.digest(Path(_core.__file__))
    cache = cached_calls(args.raw_cache, inputs, prompts, core_hash, transport)
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "databases").mkdir()
    (args.out / "source_archive").mkdir()
    controls.dump(args.out / "inputs.json", inputs)
    controls.dump(args.out / "prompts.json", prompts)
    shutil.copyfile(args.before_prompt, args.out / "source_archive/prompts_before.py")
    sources = [Path(__file__), Path(ladder.__file__), Path(p1.__file__), Path(controls.__file__),
               ROOT / "python/starling/extractor/prompts.py", ROOT / "src/extractor/json_parser.cpp",
               ROOT / "src/extractor/extractor.cpp"]
    for path in sources:
        shutil.copyfile(path, args.out / "source_archive" / path.name)
    manifest = {"status": "running", "claim_level": "extraction_diagnostic_only",
                "model": "deepseek-v3", "provider": "dashscope", "rounds": 1,
                "transport": transport,
                "core_sha256": core_hash,
                "inputs_sha256": controls.digest(args.out / "inputs.json"),
                "prompts_sha256": controls.digest(args.out / "prompts.json"),
                "source_sha256": {str(p.relative_to(ROOT)): controls.digest(p) for p in sources},
                "case_counts": dict(Counter(r["track"] for r in inputs)),
                "expected_completions": len(inputs) * 2,
                "raw_cache": None if args.raw_cache is None else {
                    "directory": str(args.raw_cache.resolve()),
                    "manifest_sha256": controls.digest(args.raw_cache / "manifest.json"),
                    "raw_calls_sha256": controls.digest(args.raw_cache / "raw_calls.jsonl")},
                "protocol": "One raw completion per case/phase; alternating phase order. "
                            "Replay the exact raw response through native belief prepare/extract/commit. "
                            "P1 uses original raw-output metrics; preference scores use stored rows. "
                            "Source groups are qualitative, unscored. No answer or judge calls.",
                "started_at": datetime.now(timezone.utc).isoformat()}
    controls.dump(args.out / "manifest.json", manifest)
    rows = []
    try:
        for i, case in enumerate(inputs):
            phases = ("before", "after") if i % 2 == 0 else ("after", "before")
            for phase in phases:
                identity = {"id": case["id"], "track": case["track"], "phase": phase}
                print(f"[{len(rows)+1}/{len(inputs)*2}] {identity}", flush=True)
                prompt = prompts[phase].replace("{convo}", case["passage"])
                started = time.perf_counter()
                cached = cache.get((case["track"], case["id"], phase))
                if cached is not None:
                    if cached["prompt"] != prompt:
                        raise ValueError("cached prompt mismatch")
                    receipt = {**cached, "reused_from": str(args.raw_cache.resolve())}
                else:
                    response = llm.extract(prompt, _core.Extractor.compute_prompt_input_hash(prompt))
                    receipt = {**identity, "prompt": prompt, "raw": response.raw_xml,
                               "ok": response.ok, "error": response.error,
                               "wall_seconds": time.perf_counter() - started}
                ladder.append_journal(args.out / "raw_calls.jsonl", receipt)
                if not receipt["ok"]:
                    raise ValueError(f"LLM failed: {receipt['error']}")
                predicted = parse_response(receipt["raw"])
                db = args.out / "databases" / f"{i}_{phase}.db"
                native = native_replay(receipt["raw"], case["passage"], case["holder"], prompts[phase], db)
                row = {**identity, "raw_sha256": hashlib.sha256(receipt["raw"].encode()).hexdigest(),
                       "predicted": predicted, "native": native, "db_path": str(db),
                       "database_sha256": controls.frozen_database_hash(db)}
                if case["track"] == "preference":
                    row["score"] = preference_score(case["record"], native["rows"])
                elif case["track"] == "p1":
                    row["p1_counts"] = p1.evaluate_record(case["record"], predicted)
                ladder.append_journal(args.out / "journal.jsonl", row)
                rows.append(row)
        controls.dump(args.out / "results.json", summarize(rows))
        manifest.update(status="complete", completed_at=datetime.now(timezone.utc).isoformat())
    except Exception as exc:
        manifest.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        controls.dump(args.out / "manifest.json", manifest)


if __name__ == "__main__":
    main()

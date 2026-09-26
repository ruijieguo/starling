#!/usr/bin/env python3
"""Fixed P1 vocabulary isolation and general-fact output-envelope diagnostics."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sqlite3

import eval_socialmem_predicates as trial

ROOT = trial.ROOT
EMPTY_EXPLANATION = ('(A voiced opinion ("I think...") belongs to the belief pass; '
                     '"put the report on the desk" is a physical event for the episodic pass. '
                     'Neither is a standalone declarative world-fact, so output [].)')
OUTPUT_CONTRACT = (
    "OUTPUT CONTRACT: Return exactly ONE JSON array and nothing else. "
    "Do not include Markdown fences, explanations, or a second copy of the array. "
    "If there are no eligible facts, the entire response is exactly [].\n\n")
GENERIC = [
    {"id": "empty_ack", "passage": "Lena: Thank you.\nOmar: You're welcome.", "expected": []},
    {"id": "empty_preference", "passage": "Lena: I prefer quiet mornings.", "expected": []},
    {"id": "empty_event", "passage": "Lena put the mug on the shelf.", "expected": []},
    {"id": "empty_uncertainty", "passage": "Lena: I have not decided whether to take the course.", "expected": []},
    {"id": "definition", "passage": "A thermistor is a temperature-sensitive resistor.",
     "expected": [["thermistor", "is_a", "temperature-sensitive resistor", "pos"]]},
    {"id": "quantity", "passage": "The budget is $40000.", "expected": [["budget", "has_value", "$40000", "pos"]]},
    {"id": "relation", "passage": "Nina reports to Pavel.", "expected": [["nina", "reports_to", "pavel", "pos"]]},
    {"id": "mixed", "passage": "Lena: The boiler is noisy. I want it inspected tomorrow.",
     "expected": [["boiler", "has_property", "noisy", "pos"]]},
]


def single_array_prompt(template):
    anchor = "JSON array:\n[]\n" + EMPTY_EXPLANATION
    if template.count(anchor) != 1 or template.count("\nPassage:\n{convo}") != 1:
        raise ValueError("general-fact output anchor drifted")
    return OUTPUT_CONTRACT + template.replace(anchor, EMPTY_EXPLANATION + "\nJSON array:\n[]")


def fact_cases(records):
    cases = [{"id": record["item_id"] + "_" + unit["holder"], "track": "general_fact",
              "holder": unit["holder"], "passage": unit["payload"], "unit": unit,
              "item_id": record["item_id"]}
             for record in records for unit in trial.source_units(record)]
    return cases + [{**case, "track": "general_fact", "holder": "Lena"} for case in GENERIC]


def render(template, case):
    return template.replace("{self}", case["holder"]).replace("{convo}", case["passage"])


def native(core, adapter, case, arm, template, raw, now, transport_ok=True, transport_error=""):
    payload = case["passage"].encode("utf-8")
    policy = trial.policy(core, "vocabulary" if case["track"] == "p1" and arm == "vocabulary" else "baseline")
    prepared = core.memory_remember_prepare(
        adapter, tenant_id="default", holder_id=case["holder"], interlocutor="",
        adapter_name="socialmem-followup", source_prefix="socialmem-followup", created_at_iso8601=now, payload=payload)
    if not prepared.should_extract:
        raise ValueError("input not admitted for extraction")
    llm = core.FakeLLMAdapter()
    llm.set_response(core.Extractor.compute_prompt_input_hash(render(template, case)), raw,
                     transport_ok, transport_error)
    extracted = core.memory_extract_llm(adapter, llm, template.replace("{self}", case["holder"]),
                                        case["holder"], payload, policy)
    return core.memory_remember_commit(adapter, llm, tenant_id="default", holder_id=case["holder"],
                                       interlocutor="", prepared=prepared, llm_result=extracted, policy=policy)


def score(case, raw, receipt, rows, transport_ok):
    error, predicted = None, []
    try:
        predicted = trial.extraction.parse_response(raw)
    except ValueError as exc:
        error = f"{type(exc).__name__}: {exc}"
    try:
        value = json.loads(raw)
        strict = isinstance(value, list) and all(isinstance(r, dict) for r in value)
    except ValueError:
        strict = False
    result = {"parse_error": error, "strict_json": strict,
              "native_ok": bool(transport_ok and not receipt["extraction_failed"]),
              "raw_holder_mismatches": sum(r.get("holder") != case.get("holder") for r in predicted)}
    if case["track"] == "p1":
        result["metric_error"] = None
        try:
            result["p1_counts"] = trial.extraction.p1.evaluate_record(case["record"], predicted if transport_ok else [])
        except (TypeError, ValueError) as exc:
            result["metric_error"] = f"{type(exc).__name__}: {exc}"
            result["p1_counts"] = trial.extraction.p1.evaluate_record(case["record"], [])
    elif "expected" in case:
        actual = Counter(tuple(str(r[k]).casefold() for k in ("subject_id", "predicate", "object_value", "polarity"))
                         for r in rows)
        expected = Counter(tuple(s.casefold() for s in e) for e in case["expected"])
        result["generic_exact"] = bool(result["native_ok"] and error is None and actual == expected
                                       and len(predicted) == len(rows))
    return result


def evaluate(core, llm, case, arm, template, out, now):
    identity = {"track": case["track"], "id": case["id"], "arm": arm}
    prompt = render(template, case)
    response = llm.extract(prompt, core.Extractor.compute_prompt_input_hash(prompt))
    trial.ladder.append_journal(out / "extraction_calls.jsonl", {
        **identity, "prompt": prompt, "raw": response.raw_xml, "ok": response.ok, "error": response.error})
    database = out / "databases" / f"{case['track']}_{case['id']}_{arm}.db"
    with trial.archived_runtime(database) as (rt, working):
        receipt = native(core, rt.adapter, case, arm, template, response.raw_xml, now, response.ok, response.error)
        rows = trial.temporal.statement_rows(working)
        with sqlite3.connect(working) as conn:
            pipelines = conn.execute("SELECT id,status FROM pipeline_run ORDER BY id").fetchall()
    result = {**identity, "ok": response.ok, "error": response.error, "receipt": receipt, "rows": rows,
              "pipelines": pipelines, "database": str(database.relative_to(out)),
              "database_sha256": trial.controls.frozen_database_hash(database),
              **score(case, response.raw_xml, receipt, rows, response.ok)}
    trial.ladder.append_journal(out / "cases.jsonl", result)
    return result


def summarize(results):
    output = {"p1": {}, "general_fact": {}}
    for arm in ("baseline", "vocabulary"):
        selected = [r for r in results if r["track"] == "p1" and r["arm"] == arm]
        counts = {field: [0, 0, 0] for field in trial.extraction.p1.P1_THRESHOLDS}
        for row in selected:
            for field, values in row["p1_counts"].items():
                counts[field] = [a + b for a, b in zip(counts[field], values, strict=True)]
        output["p1"][arm] = {"cases": len(selected), "counts": counts,
                             "f1": {k: trial.extraction.p1.f1_score(*v) for k, v in counts.items()},
                             "metric_failed": sum(r["metric_error"] is not None for r in selected),
                             "native_failed": sum(not r["native_ok"] for r in selected)}
    for arm in ("baseline", "single_array"):
        selected = [r for r in results if r["track"] == "general_fact" and r["arm"] == arm]
        output["general_fact"][arm] = {
            "cases": len(selected), "native_failed": sum(not r["native_ok"] for r in selected),
            "parse_failed": sum(r["parse_error"] is not None for r in selected),
            "strict_json": sum(r["strict_json"] for r in selected),
            "generic_cases": sum("generic_exact" in r for r in selected),
            "generic_exact": sum(r.get("generic_exact", False) for r in selected)}
    return output


def schedule(inputs):
    for track, arms in (("p1", ("baseline", "vocabulary")), ("general_fact", ("baseline", "single_array"))):
        for i, case in enumerate(inputs[track]):
            for arm in arms if i % 2 == 0 else arms[::-1]:
                yield case, arm


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--now-iso", required=True)
    args = parser.parse_args()
    from starling import _core
    from starling.extractor.prompts import EXTRACTION_PROMPT
    from starling.extractor.general_fact_prompt import GENERAL_FACT_EXTRACTION_PROMPT

    previous = trial.extraction.load(args.previous / "manifest.json")
    verification = trial.extraction.load(args.previous / "verification.json")
    assert verification["status"] == "verified" and previous["status"] == "complete_with_errors"
    assert previous["core_sha256"] == trial.controls.digest(Path(_core.__file__))
    for name, fingerprint in verification["artifact_sha256"].items():
        assert trial.controls.digest(args.previous / name) == fingerprint
    original_inputs = trial.extraction.load(args.previous / "inputs.json")
    original_prompts = trial.extraction.load(args.previous / "prompts.json")
    assert original_prompts["belief"]["baseline"] == EXTRACTION_PROMPT
    assert original_prompts["general_fact"] == GENERAL_FACT_EXTRACTION_PROMPT
    assert [c["record"] for c in original_inputs["p1"]] == trial.extraction.load_lines(ROOT / "tests/data/eval_p1_corpus.jsonl")
    inputs = {"p1": original_inputs["p1"], "general_fact": fact_cases(original_inputs["scoped"])}
    prompts = {"p1": {a: original_prompts["belief"][a] for a in ("baseline", "vocabulary")},
               "general_fact": {"baseline": GENERAL_FACT_EXTRACTION_PROMPT,
                                "single_array": single_array_prompt(GENERAL_FACT_EXTRACTION_PROMPT)}}
    assert len(inputs["p1"]) == 50 and len(inputs["general_fact"]) == 18
    llm, transport = trial.extraction.build_llm(_core)
    assert transport == previous["extract_transport"]
    now = trial.ladder.normalize_eval_time(args.now_iso)
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "databases").mkdir()
    (args.out / "source_archive").mkdir()
    trial.controls.dump(args.out / "inputs.json", inputs)
    trial.controls.dump(args.out / "prompts.json", prompts)
    sources = [ROOT / p for p in previous["source_sha256"]] + [Path(__file__).resolve()]
    for source in sources:
        shutil.copyfile(source, args.out / "source_archive" / source.name)
    manifest = {"status": "running", "started_at": datetime.now(timezone.utc).isoformat(),
                "query_time": now, "extract_transport": transport, "core_sha256": previous["core_sha256"],
                "previous": str(args.previous.resolve()), "previous_verification_sha256": trial.controls.digest(args.previous / "verification.json"),
                "inputs_sha256": trial.controls.digest(args.out / "inputs.json"),
                "prompts_sha256": trial.controls.digest(args.out / "prompts.json"),
                "source_sha256": {str(p.relative_to(ROOT)): trial.controls.digest(p) for p in sources},
                "expected_completions": {"extraction": 136, "answer": 0, "judge": 0},
                "protocol": "Fresh paired baseline/vocabulary on all unchanged 50 P1 records. "
                            "General-fact baseline/single-array on all ten reviewed speaker inputs plus eight generic controls. "
                            "One completion per condition, alternating arms, native single-channel persistence. "
                            "General-fact shares the native belief parser after literal self substitution. "
                            "Archive errors and continue fixed conditions; P1 scoring exceptions are explicit and use empty-prediction counts. "
                            "No quality retries, gold in extraction or production changes."}
    trial.controls.dump(args.out / "manifest.json", manifest)
    results = []
    try:
        for case, arm in schedule(inputs):
            print(f"[case] {case['track']}/{case['id']}/{arm}", flush=True)
            results.append(evaluate(_core, llm, case, arm, prompts[case["track"]][arm], args.out, now))
        trial.controls.dump(args.out / "results.json", summarize(results))
        manifest.update(status="complete", completed_at=datetime.now(timezone.utc).isoformat())
    except Exception as exc:
        manifest.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        trial.controls.dump(args.out / "manifest.json", manifest)


if __name__ == "__main__":
    main()

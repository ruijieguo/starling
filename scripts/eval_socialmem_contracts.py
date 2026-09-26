#!/usr/bin/env python3
"""Controlled relation semantics and clause-level general-fact coverage trial."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sqlite3
from urllib.parse import urlsplit, urlunsplit

import eval_socialmem_followup as followup

trial = followup.trial
ROOT = trial.ROOT
load, lines, digest = trial.extraction.load, trial.extraction.load_lines, trial.controls.digest
ARMS = {"p1": ("baseline", "vocabulary", "contract"),
        "synthetic": ("vocabulary", "contract"),
        "general_fact": ("baseline", "single_array", "clause_coverage")}
EXPECTED = {"extraction": 236, "answer": 0, "judge": 96}
RELATION_MODALITY = {p: "INTENDS" if p == "decided_on" else "BELIEVES" for p in trial.EXTRA_PREDICATES}
RELATION_CONTRACT = (
    "ADDITIONAL RELATION CONTRACT (only feels, uncertain_about, decided_on, indifferent_to, trusts):\n"
    "- subject is the named person experiencing the state or choosing the action; subject_kind=cognizer. "
    "Never use the topic, problem, event, alternative, or task as that subject. "
    "First-person subject is the speaker; reports retain the actual experiencer as subject. "
    "The existing holder and source-perspective rules still apply, including quotation authorship exceptions.\n"
    "- feels, uncertain_about, indifferent_to, and trusts use modality=BELIEVES: these assert a state or relation, "
    "not a desire for the target. A settled choice of future action uses decided_on with modality=INTENDS. "
    "An explicit promise continues to use promises/COMMITS under the original rules.\n"
    "- Polarity applies to the complete relation. Explicitly being undecided is uncertain_about with "
    "BELIEVES + POS, not UNKNOWN. Stated indifference is indifferent_to with BELIEVES + POS. "
    "A negative chosen action is still an affirmed decision: decided_on has POS and the rejected action "
    "stays negative inside its object. Denying a feeling or trust uses NEG without duplicating that same "
    "denial inside the object. UNKNOWN is only for an explicitly uncertain truth of the relation itself.\n"
    "- Do not emit decided_on for a possibility, a suggestion, a routing remark, or an unresolved choice. "
    "Uncertainty does not establish acceptance or rejection. Do not invent a preference from either "
    "uncertainty or indifference.\n"
    "- Objects for these five relations keep the feeling/action, its target, stated cause and qualifiers. "
    "Resolve pronouns from explicit context and retain all separately stated feelings. Preserve literal "
    "earlier/current time phrases on their respective objects as distinct claims. Never infer calendar "
    "dates from the import clock. These object exceptions do not change brevity or canonicalization for "
    "the original predicates, or change their holder, perspective and nesting rules.\n")
BREVITY = "OBJECT BREVITY: object MUST be the minimal canonical noun phrase."
SCOPED_BREVITY = (
    "OBJECT BREVITY: for the original predicates, object MUST be the minimal canonical noun phrase "
    "subject to their existing preference/promise exceptions. For the five additional relations, "
    "apply the ADDITIONAL RELATION CONTRACT instead.")
SCOPED_SECOND = (
    "Other ORIGINAL predicates (responsible_for, knows, requires, etc.) use the canonical short noun. "
    "The five additional relations keep their stated target, cause and temporal qualifiers.")
CLAUSE_COVERAGE = (
    "CLAUSE COVERAGE: Inspect each clause independently, including clauses inside speaker-labelled dialogue. "
    "A speaker label does not make a declarative property, definition, quantity or relationship an opinion. "
    "In a mixed utterance, keep each eligible fact even when a neighboring clause expresses an opinion, "
    "desire, plan, uncertainty or event. Exclude only the ineligible clause, not the whole utterance or passage. "
    "Preserve independently stated facts across the entire passage. Return [] only when no eligible clause "
    "remains after checking the entire passage. Keep each fact's actual subject and its stated qualifiers; "
    "do not turn an action by a person into an attribute of the action's target. A subjective evaluation "
    "remains an opinion even without the words 'I think'. All existing predicate/schema rules still apply.\n\n")


def belief_contract(vocabulary):
    replacements = ((trial.VOCABULARY_EXTENSION, trial.VOCABULARY_EXTENSION + "\n" + RELATION_CONTRACT),
                    (BREVITY, SCOPED_BREVITY), (trial.SECOND_BREVITY, SCOPED_SECOND))
    for before, after in replacements:
        if vocabulary.count(before) != 1:
            raise ValueError("belief contract anchor drifted")
        vocabulary = vocabulary.replace(before, after)
    return vocabulary


def fact_contract(single_array):
    anchor = "DO NOT extract ("
    if single_array.count(anchor) != 1:
        raise ValueError("general-fact clause anchor drifted")
    return single_array.replace(anchor, CLAUSE_COVERAGE + anchor)


def relation_rules(predicted):
    emitted, violations = 0, []
    for i, row in enumerate(predicted):
        predicate = row.get("predicate")
        if not isinstance(predicate, str) or predicate not in RELATION_MODALITY:
            continue
        emitted += 1
        fields = []
        if not isinstance(row.get("subject"), str) or not row["subject"].strip():
            fields.append("subject")
        if row.get("subject_kind") != "cognizer":
            fields.append("subject_kind")
        if row.get("modality") != RELATION_MODALITY[predicate]:
            fields.append("modality")
        if row.get("polarity") not in ("POS", "NEG", "UNKNOWN"):
            fields.append("polarity")
        if fields:
            violations.append({"index": i, "fields": fields})
    return {"emitted": emitted, "violations": violations}


def case_checks(case_id, predicted):
    if case_id in ("undecided", "possible_not_decided"):
        return {"affirmed_uncertainty": any(r.get("predicate") == "uncertain_about" and
                    r.get("polarity") == "POS" and r.get("modality") == "BELIEVES" for r in predicted),
                "no_settled_decision": not any(r.get("predicate") == "decided_on" for r in predicted)}
    if case_id == "decision_change":
        return {"temporal_qualifiers": all(any(r.get("predicate") == predicate and
                    isinstance(r.get("object"), str) and phrase in r["object"].casefold()
                    for r in predicted) for predicate, phrase in
                    (("uncertain_about", "last week"), ("decided_on", "today")))}
    return {}


def native(core, adapter, case, arm, template, raw, now, ok=True, error=""):
    belief = case["track"] in ("p1", "synthetic")
    policy_arm = "vocabulary" if belief and arm in ("vocabulary", "contract") else "baseline"
    native_case = {**case, "track": "p1" if belief else "general_fact"}
    return followup.native(core, adapter, native_case, policy_arm, template, raw, now, ok, error)


def score(case, raw, receipt, rows, ok):
    scores = followup.score(case, raw, receipt, rows, ok)
    if case["track"] in ("p1", "synthetic"):
        try:
            predicted = trial.extraction.parse_response(raw) if ok else []
        except ValueError:
            predicted = []
        normalized = [{"subject": r["subject_id"], "subject_kind": r["subject_kind"],
                       "predicate": r["predicate"], "object": r["object_value"],
                       "modality": r["modality"].upper(), "polarity": r["polarity"].upper()} for r in rows]
        scores.update(raw_rules=relation_rules(predicted), native_rules=relation_rules(normalized),
                      raw_case_checks=case_checks(case["id"], predicted),
                      native_case_checks=case_checks(case["id"], normalized))
    return scores


def evaluate(core, llm, case, arm, template, out, now):
    identity = {"track": case["track"], "id": case["id"], "arm": arm}
    prompt = followup.render(template, case)
    try:
        reply = llm.extract(prompt, core.Extractor.compute_prompt_input_hash(prompt))
        raw, ok, error = reply.raw_xml, reply.ok, reply.error
    except Exception as exc:
        raw, ok, error = "", False, f"{type(exc).__name__}: {exc}"
    trial.ladder.append_journal(out / "extraction_calls.jsonl", {
        **identity, "prompt": prompt, "raw": raw, "ok": ok, "error": error})
    database = out / "databases" / f"{case['track']}_{case['id']}_{arm}.db"
    with trial.archived_runtime(database) as (rt, working):
        receipt = native(core, rt.adapter, case, arm, template, raw, now, ok, error)
        rows = trial.temporal.statement_rows(working)
        with sqlite3.connect(working) as conn:
            pipelines = conn.execute("SELECT id,status FROM pipeline_run ORDER BY id").fetchall()
    result = {**identity, "ok": ok, "error": error, "receipt": receipt, "rows": rows,
              "pipelines": pipelines, "database": str(database.relative_to(out)),
              "database_sha256": trial.controls.frozen_database_hash(database),
              **score(case, raw, receipt, rows, ok)}
    trial.ladder.append_journal(out / "cases.jsonl", result)
    return result


def candidate(rows, receipt):
    by_id = {r["id"]: r for r in rows}
    return json.dumps([{k: by_id[sid][k] for k in trial.SEMANTIC_FIELDS}
                       for sid in receipt["statement_ids"]], ensure_ascii=False)


def parse_vote(raw, error):
    valid = not error and raw.strip().upper() in ("YES", "NO")
    return {"valid": bool(valid), "accepted": bool(valid and raw.strip().upper() == "YES")}


def judge(chat, case, arm, statements, out):
    prompt = trial.audit._judge_prompt(case["question"], case["answer"], statements)
    identity = {"track": case["track"], "id": case["id"], "arm": arm}
    votes = []
    for repeat in range(3):
        try:
            raw, error = chat(prompt, "gpt-5.5", max_tokens=8), ""
        except Exception as exc:
            raw, error = "", f"{type(exc).__name__}: {exc}"
        recorded = {**identity, "repeat": repeat, "prompt": prompt, "raw": raw, "error": error}
        trial.ladder.append_journal(out / "judge_responses.jsonl", recorded)
        vote = {**recorded, **parse_vote(raw, error)}
        trial.ladder.append_journal(out / "judge_calls.jsonl", vote)
        votes.append(vote)
    accepted = sum(v["accepted"] for v in votes)
    return {"ok": accepted >= 2, "acceptances": accepted, "failed": sum(not v["valid"] for v in votes),
            "votes": votes}


def schedule(inputs):
    for track, arms in ARMS.items():
        for i, case in enumerate(inputs[track]):
            offset = i % len(arms)
            for arm in arms[offset:] + arms[:offset]:
                yield case, arm


def summarize(results, judgments):
    summary = {track: {} for track in ARMS}
    for track, arms in ARMS.items():
        for arm in arms:
            selected = [r for r in results if r["track"] == track and r["arm"] == arm]
            value = {"cases": len(selected), "transport_failed": sum(not r["ok"] for r in selected),
                     "native_failed": sum(not r["native_ok"] for r in selected),
                     "parse_failed": sum(r["parse_error"] is not None for r in selected),
                     "strict_json": sum(r["strict_json"] for r in selected)}
            if track == "general_fact":
                value.update(generic_cases=sum("generic_exact" in r for r in selected),
                             generic_exact=sum(r.get("generic_exact", False) for r in selected))
            else:
                for name in ("raw_rules", "native_rules"):
                    value[name] = {"emitted": sum(r[name]["emitted"] for r in selected),
                                   "violations": sum(len(r[name]["violations"]) for r in selected)}
                value["case_checks"] = [{"id": r["id"], "raw": r["raw_case_checks"],
                                         "native": r["native_case_checks"]}
                                        for r in selected if r["raw_case_checks"]]
            if track == "p1":
                counts = {field: [sum(r["p1_counts"][field][i] for r in selected) for i in range(3)]
                          for field in trial.extraction.p1.P1_THRESHOLDS}
                value.update(counts=counts, f1={k: trial.extraction.p1.f1_score(*v) for k, v in counts.items()},
                             metric_failed=sum(r["metric_error"] is not None for r in selected))
            if track == "synthetic":
                votes = [j for j in judgments if j["arm"] == arm]
                value.update(judged=len(votes), majority_supported=sum(j["native_ok"] and j["judgment"]["ok"] for j in votes),
                             unanimous_supported=sum(j["native_ok"] and j["judgment"]["acceptances"] == 3 for j in votes),
                             invalid_judgments=sum(j["judgment"]["failed"] for j in votes))
            summary[track][arm] = value
    return summary


def prepare(previous):
    manifest, verification = load(previous / "manifest.json"), load(previous / "verification.json")
    assert manifest["status"] == "complete" and verification["status"] == "verified"
    for name, fingerprint in verification["artifact_sha256"].items():
        assert digest(previous / name) == fingerprint
    parent = Path(manifest["previous"])
    assert digest(parent / "verification.json") == manifest["previous_verification_sha256"]
    parent_verification = load(parent / "verification.json")
    for name, fingerprint in parent_verification["artifact_sha256"].items():
        assert digest(parent / name) == fingerprint
    old_inputs, old_prompts = load(previous / "inputs.json"), load(previous / "prompts.json")
    synthetic = load(parent / "inputs.json")["synthetic"]
    assert synthetic == [{**c, "track": "synthetic"} for c in trial.synthetic_cases()]
    assert [r["record"] for r in old_inputs["p1"]] == lines(ROOT / "tests/data/eval_p1_corpus.jsonl")
    inputs = {**old_inputs, "synthetic": synthetic}
    prompts = {"p1": {**old_prompts["p1"], "contract": belief_contract(old_prompts["p1"]["vocabulary"])},
               "general_fact": {**old_prompts["general_fact"],
                                "clause_coverage": fact_contract(old_prompts["general_fact"]["single_array"])}}
    prompts["synthetic"] = {a: prompts["p1"][a] for a in ARMS["synthetic"]}
    assert {k: len(v) for k, v in inputs.items()} == {"p1": 50, "synthetic": 16, "general_fact": 18}
    return inputs, prompts, manifest, load(parent / "manifest.json")


def run(previous, out, now, core, llm, chat, transport, judge_endpoint, *, execution_mode="real"):
    assert execution_mode in ("real", "offline_smoke")
    inputs, prompts, parent, grandparent = prepare(previous)
    assert digest(Path(core.__file__)) == parent["core_sha256"]
    assert transport == parent["extract_transport"] and judge_endpoint == grandparent["answer_endpoint"]
    for source, fingerprint in parent["source_sha256"].items():
        assert digest(ROOT / source) == fingerprint
    out.mkdir(parents=True, exist_ok=False)
    (out / "databases").mkdir()
    (out / "source_archive").mkdir()
    trial.controls.dump(out / "inputs.json", inputs)
    trial.controls.dump(out / "prompts.json", prompts)
    sources = [ROOT / p for p in parent["source_sha256"]] + [Path(__file__).resolve(),
               ROOT / "scripts/verify_socialmem_contracts.py", ROOT / "scripts/verify_socialmem_predicates.py"]
    for source in sources:
        shutil.copyfile(source, out / "source_archive" / source.name)
    manifest = {"status": "running", "claim_level": "relation_contract_diagnostic", "execution_mode": execution_mode,
                "started_at": datetime.now(timezone.utc).isoformat(), "query_time": now,
                "previous": str(previous.resolve()), "previous_verification_sha256": digest(previous / "verification.json"),
                "core_sha256": parent["core_sha256"], "extract_transport": transport,
                "judge_endpoint": judge_endpoint, "judge_model": "gpt-5.5", "judge_max_tokens": 8, "judge_repeats": 3,
                "expected_completions": EXPECTED, "arms": ARMS,
                "inputs_sha256": digest(out / "inputs.json"), "prompts_sha256": digest(out / "prompts.json"),
                "source_sha256": {str(p.relative_to(ROOT)): digest(p) for p in sources},
                "protocol": "Fresh P1 baseline/vocabulary/contract on 50 unchanged records; 16 original synthetic "
                            "records vocabulary/contract; 18 general-fact inputs baseline/single_array/clause_coverage. "
                            "Rotating arm order. One extraction per condition; archive raw replies before native parsing. "
                            "After all extraction calls, judge every synthetic native candidate three times, with "
                            "technical failures separate and invalid votes explicitly unsuccessful. No answers, "
                            "retrieval, embeddings, production changes, gold in extraction, or quality retries."}
    trial.controls.dump(out / "manifest.json", manifest)
    results, judgments = [], []
    try:
        for case, arm in schedule(inputs):
            print(f"[case] {case['track']}/{case['id']}/{arm}", flush=True)
            results.append(evaluate(core, llm, case, arm, prompts[case["track"]][arm], out, now))
        synthetic = {c["id"]: c for c in inputs["synthetic"]}
        for result in results:
            if result["track"] != "synthetic":
                continue
            case, arm = synthetic[result["id"]], result["arm"]
            statements = candidate(result["rows"], result["receipt"])
            judgment = judge(chat, case, arm, statements, out)
            entry = {"track": "synthetic", "id": case["id"], "arm": arm, "candidate": statements,
                     "native_ok": result["native_ok"], "judgment": judgment}
            judgments.append(entry)
            trial.ladder.append_journal(out / "judgments.jsonl", entry)
            print(f"[judge] {case['id']}/{arm}: {judgment['acceptances']}/3, {judgment['failed']} failed", flush=True)
        manifest.update(status="complete", completed_at=datetime.now(timezone.utc).isoformat())
    except Exception as exc:
        manifest.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        trial.controls.dump(out / "results.json", summarize(results, judgments))
        trial.controls.dump(out / "manifest.json", manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--now-iso", required=True)
    args = parser.parse_args()
    from starling import _core

    url = urlsplit(os.environ["OPENAI_BASE_URL"])
    if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError("judge endpoint must be HTTPS without credentials or query")
    endpoint = urlunsplit(url._replace(path="/v1"))
    os.environ["OPENAI_BASE_URL"] = endpoint
    llm, transport = trial.extraction.build_llm(_core)
    run(args.previous.resolve(), args.out, trial.ladder.normalize_eval_time(args.now_iso),
        _core, llm, trial.audit._chat_completion, transport, endpoint)


if __name__ == "__main__":
    main()

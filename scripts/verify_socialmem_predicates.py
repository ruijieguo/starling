#!/usr/bin/env python3
"""Verify a completed predicate trial offline, including native response replay."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import runpy
import sqlite3
import tempfile

import eval_socialmem_predicates as trial

ROOT = trial.ROOT
load, lines, digest = trial.extraction.load, trial.extraction.load_lines, trial.controls.digest
IDENTITY = ("track", "id", "arm")
REPLAY_FIELDS = (*trial.SEMANTIC_FIELDS, "object_kind", "canonical_object_hash",
                 "confidence", "review_status", "tenant_id", "valid_from", "valid_to",
                 "event_time_start", "event_time_end", "temporal_anchor_json", "perceived_by_json")
EVENT_FIELDS = ("seq", "event_time", "location", "participants_json", "action_raw")


def identity(row):
    return tuple(row[k] for k in IDENTITY)


def semantics(rows):
    return Counter(tuple(row[k] for k in REPLAY_FIELDS) for row in rows)


def check_sleep_rows(result, before, after):
    originals = {r["id"]: r for r in before}
    added = [r for r in after if r["id"] not in originals]
    assert set(originals) <= {r["id"] for r in after}
    assert len(added) == result["sleep"]["abstracted"]
    for row in added:
        parents = json.loads(row["derived_from_json"])
        assert parents and set(parents) <= set(originals)
        sources = [originals[sid] for sid in parents]
        assert len({r["holder_id"] for r in sources}) >= 3
        assert row["provenance"] == "consolidation_abstract"
        assert row["holder_id"] == "__common_ground__" and row["holder_perspective"] == "inferred"
        assert row["review_status"] in ("inferred_unreviewed", "review_requested")
        assert row["consolidation_state"] == "volatile" and row["confidence"] == 0.5
        assert row["modality"] == "believes" and row["polarity"] == "pos"
        assert row["derived_depth"] == max(r["derived_depth"] for r in sources) + 1
        assert all(r["tenant_id"] == row["tenant_id"] and r["predicate"] == row["predicate"]
                   and r["canonical_object_hash"] == row["canonical_object_hash"] for r in sources)
        assert row["subject_id"] == "__people__" or all(
            (r["subject_kind"], r["subject_id"]) == (row["subject_kind"], row["subject_id"]) for r in sources)
        assert all(not e["engram_ref"] and not e["content_hash"] for e in json.loads(row["evidence_json"]))


def check_database(run, result, receipts, before, after, manifest, vectors=False):
    database = run / result["database"]
    assert trial.controls.frozen_database_hash(database) == result["database_sha256"]
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        rows = [dict(r) for r in conn.execute("SELECT * FROM statements ORDER BY id")]
        assert rows == after
        assert all(r["tenant_id"] == "default" for r in rows)
        if vectors:
            check_sleep_rows(result, before, after)
        else:
            assert {r["id"] for r in rows} == {r["id"] for r in before}
        pipelines = [list(r) for r in conn.execute("SELECT id,status FROM pipeline_run ORDER BY id")]
        assert pipelines == result["pipelines"]
        assert all(status == "finished" for _, status in pipelines)
        assert all(datetime.fromisoformat(r["created_at"]) <= datetime.fromisoformat(manifest["query_time"])
                   for r in before)
        by_engram = {r["engram_ref"]: r for r in receipts}
        assert len(by_engram) == len(receipts)
        assert conn.execute("SELECT count(*) FROM engrams").fetchone()[0] == len(receipts)
        assert {sid for r in receipts for sid in r["statement_ids"]} == {r["id"] for r in before}
        for receipt in receipts:
            assert receipt["outcome"] == "accepted" and not receipt["extraction_failed"]
            row = conn.execute("SELECT payload_inline,content_hash,declared_transformations_json,"
                               "byte_preserving FROM engrams WHERE id=? AND tenant_id='default'",
                               (receipt["engram_ref"],)).fetchone()
            payload = receipt["unit"]["payload"].encode("utf-8")
            assert bytes(row[0]) == payload
            assert row[1] == hashlib.sha256(b"v1\x1f" + payload + b"\x1f").hexdigest()
            assert json.loads(row[2]) == [] and row[3] == 1
        for row in before:
            evidence = json.loads(row["evidence_json"])
            assert evidence
            for source in evidence:
                receipt = by_engram[source["engram_ref"]]
                assert row["id"] in receipt["statement_ids"]
                assert row["holder_id"] == receipt["unit"]["holder"]
                payload = receipt["unit"]["payload"].encode("utf-8")
                assert source["content_hash"] == hashlib.sha256(b"v1\x1f" + payload + b"\x1f").hexdigest()
                assert source["status"] == "active"
        stored_vectors = [dict(r) for r in conn.execute("SELECT * FROM statement_vectors")]
        if vectors:
            eligible = [r for r in rows if r["consolidation_state"] not in ("archived", "forgotten")]
            assert len(stored_vectors) == len(eligible) == result["embedding"]["embedded"]
            assert result["embedding"]["failed"] == 0
            assert {(v["tenant_id"], v["stmt_id"]) for v in stored_vectors} == {
                (r["tenant_id"], r["id"]) for r in eligible}
            for vector in stored_vectors:
                assert vector["model"] == manifest["embedding_model"]
                assert vector["dim"] == manifest["embedding_dim"] == 1024
                assert vector["status"] == "embedded"
                assert len(vector["raw_embedding"]) == len(vector["index_vector"]) == 4 * vector["dim"]
        else:
            assert not stored_vectors


def event_semantics(database, rows):
    by_id = {(r["id"], r["tenant_id"]): r for r in rows}
    with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        events = [dict(r) for r in conn.execute("SELECT * FROM episodic_events")]
    assert all((e["statement_id"], e["tenant_id"]) in by_id for e in events)
    return {sid: Counter(tuple(row[k] for k in REPLAY_FIELDS) + tuple(e[k] for k in EVENT_FIELDS)
                         for e in events if (e["statement_id"], e["tenant_id"]) == sid)
            for sid, row in by_id.items()}


def check_native_replay(core, receipts, before, raw_responses, templates, arm, now, original_database):
    from starling import runtime

    with tempfile.TemporaryDirectory(prefix="socialmem-predicate-verify-") as tmp:
        database = Path(tmp) / "replay.db"
        rt = runtime._build_local_store_sqlite_runtime(database)
        rt.start()
        replayed = []
        for receipt, raw in zip(receipts, raw_responses, strict=True):
            unit = receipt["unit"]
            replayed.append(trial.persist(core, rt.adapter, unit["holder"], unit["payload"],
                                          templates, raw, arm, now))
        rows = trial.temporal.statement_rows(database)
        original_events = event_semantics(original_database, before)
        replay_events = event_semantics(database, rows)
        for original, replay in zip(receipts, replayed, strict=True):
            expected = [r for r in before if r["id"] in original["statement_ids"]]
            actual = [r for r in rows if r["id"] in replay["statement_ids"]]
            assert semantics(actual) == semantics(expected), (arm, original["unit"]["holder"])
            expected_events, actual_events = Counter(), Counter()
            for sid in original["statement_ids"]:
                expected_events.update(original_events[(sid, "default")])
            for sid in replay["statement_ids"]:
                actual_events.update(replay_events[(sid, "default")])
            assert actual_events == expected_events
        assert semantics(rows) == semantics(before)
        del rt


def check_recall(result, manifest):
    recall = result["recall"]
    by_id = {r["id"]: r for r in result["after"]}
    assert recall["as_of_iso"] == manifest["query_time"]
    assert len(set(recall["statement_ids"])) == len(recall["statement_ids"]) <= 10
    assert set(recall["statement_ids"]) <= set(by_id)
    holders = sorted({r["holder_id"] for r in by_id.values()}) or ["alice"]
    assert [r["holder"] for r in recall["receipts"]] == holders
    scores = {}
    for scope in recall["receipts"]:
        assert set(scope["scores"]) <= set(by_id)
        assert all(by_id[sid]["holder_id"] == scope["holder"] for sid in scope["scores"])
        if not scope["abstained"]:
            scores.update(scope["scores"])
    assert recall["statement_ids"] == sorted(scores, key=lambda sid: (-scores[sid], sid))[:10]
    assert recall["abstained"] == (not recall["statement_ids"])
    if recall["abstained"]:
        assert recall["labels"] == []
        assert all(r["abstained"] and r["returned"] == 0 for r in recall["receipts"])
        reason = recall["receipts"][-1]["abstention_reason"]
        assert reason
        assert recall["block"] == "[ABSTAIN] \u65e0\u53ef\u9760\u8bb0\u5fc6,\u4e3b\u52a8\u62d2\u7b54(" + reason + ")"
    else:
        expected_lines = []
        for sid, label in zip(recall["statement_ids"], recall["labels"], strict=True):
            row = by_id[sid]
            relation = f"{row['subject_id']} {row['predicate']} {row['object_value']}"
            if row["polarity"] in ("neg", "unknown"):
                relation = f"{'NOT' if row['polarity'] == 'neg' else 'UNKNOWN'} ({relation})"
            expected_lines.append(f"[{label}] {relation} (conf {row['confidence']:.2f}, holder {row['holder_id']})")
        assert recall["block"] == "\n".join(expected_lines)
    return len(recall["statement_ids"])


def verify(run, prepared):
    from starling import _core

    manifest = load(run / "manifest.json")
    assert manifest["status"] in ("complete", "complete_with_errors")
    continued = manifest["status"] == "complete_with_errors"
    if continued:
        initial = Path(manifest["initial_run"])
        assert digest(initial / "manifest.json") == manifest["initial_manifest_sha256"]
        assert digest(run / "initial_manifest.json") == manifest["initial_manifest_sha256"]
        assert load(run / "initial_manifest.json")["status"] == "failed"
        append_only = {"extraction_calls.jsonl", "judge_calls.jsonl", "judge_responses.jsonl", "scoped_ingestion.jsonl"}
        for name, fingerprint in manifest["initial_artifact_sha256"].items():
            assert digest(initial / name) == fingerprint
            if name in append_only:
                assert (run / name).read_bytes().startswith((initial / name).read_bytes())
            elif name != "manifest.json":
                assert digest(run / name) == fingerprint
    assert manifest["core_sha256"] == digest(Path(_core.__file__))
    for source, fingerprint in manifest["source_sha256"].items():
        assert digest(run / "source_archive" / Path(source).name) == fingerprint
        assert digest(ROOT / source) == fingerprint
    for name in ("inputs", "prompts"):
        assert digest(run / f"{name}.json") == manifest[f"{name}_sha256"]
    assert digest(prepared / "manifest.json") == manifest["prepared_manifest_sha256"]
    inputs, prompts = load(run / "inputs.json"), load(run / "prompts.json")
    production = runpy.run_path(str(run / "source_archive/prompts.py"))["EXTRACTION_PROMPT"]
    assert prompts["belief"] == trial.belief_prompts(production)
    assert trial.with_fidelity(prompts["belief"]["vocabulary"]) == prompts["belief"]["combined"]
    for channel, filename, variable in (("general_fact", "general_fact_prompt.py", "GENERAL_FACT_EXTRACTION_PROMPT"),
                                        ("episodic", "episodic_prompt.py", "EPISODIC_EXTRACTION_PROMPT")):
        assert prompts[channel] == runpy.run_path(str(run / "source_archive" / filename))[variable]
    assert manifest["extra_predicates"] == list(trial.EXTRA_PREDICATES)
    assert inputs["synthetic"] == [{**r, "track": "synthetic"} for r in trial.synthetic_cases()]
    original_p1 = lines(ROOT / "tests/data/eval_p1_corpus.jsonl")
    assert len(inputs["synthetic"]) == 16 and len(original_p1) == len(inputs["p1"]) == 50
    for case, original in zip(inputs["p1"], original_p1, strict=True):
        assert case == {"id": original["id"], "track": "p1", "holder": original["conversation"][0]["speaker"],
                        "passage": "\n".join(f"{t['speaker']}: {t['text']}" for t in original["conversation"]),
                        "record": original}
    assert inputs["scoped"] == trial.reviewed_records(prepared)
    assert inputs["scoped_units"] == {r["item_id"]: trial.source_units(r) for r in inputs["scoped"]}
    assert all(len(units) == 5 for units in inputs["scoped_units"].values())
    assert [len(r["history"]) for r in inputs["scoped"]] == [50, 113]
    planned = {"extraction": 224, "answer": 6, "judge": 210}
    assert manifest["expected_completions"] == planned
    calls, cases = lines(run / "extraction_calls.jsonl"), lines(run / "cases.jsonl")
    ingestion = lines(run / "scoped_ingestion.jsonl")
    answers, answer_calls = lines(run / "answers.jsonl"), lines(run / "answer_calls.jsonl")
    votes, raw_votes = lines(run / "judge_calls.jsonl"), lines(run / "judge_responses.jsonl")
    failures = lines(run / "scoped_failures.jsonl") if continued else []
    failed_ids = {identity(r): r for r in failures}
    assert len(failed_ids) == len(failures)
    counts = {"extraction": len(calls), "answer": 6 - len(failures), "judge": 210 - 3 * len(failures)}
    if continued:
        assert manifest["observed_completions"] == counts
        assert manifest["planned_completions"] == planned
        assert ("scoped", "Q1_a5s1c1", "baseline") in failed_ids
    else:
        assert counts == planned
    assert len(cases) == 164 and len(ingestion) <= 20 and len(calls) <= planned["extraction"]
    assert len(answers) == len(answer_calls) == counts["answer"]
    assert len(votes) == len(raw_votes) == counts["judge"]
    assert len(list((run / "databases").glob("*.db"))) == 168
    expected_cases = []
    for i, case in enumerate(inputs["synthetic"] + inputs["p1"]):
        arms = trial.ARMS if case["track"] == "synthetic" else trial.PRIMARY_ARMS
        offset = i % len(arms)
        expected_cases.extend((case, arm) for arm in arms[offset:] + arms[:offset])
    judge_inputs, db_hashes = [], {}
    for result, call, (case, arm) in zip(cases, calls[:164], expected_cases, strict=True):
        expected_id = (case["track"], case["id"], arm)
        assert identity(result) == identity(call) == expected_id
        templates = {"belief": prompts["belief"][arm]}
        assert call["channel"] == "belief" and call["ok"] and not call["error"]
        assert call["prompt"] == trial.render_prompts(templates, case["holder"], case["passage"])["belief"]
        predicted = trial.extraction.parse_response(call["raw"])
        assert result["raw_holder_mismatches"] == sum(r.get("holder") != case["holder"] for r in predicted)
        receipt = {**result["receipt"], "unit": {"holder": case["holder"], "payload": case["passage"]}}
        check_database(run, result, [receipt], result["rows"], result["rows"], manifest)
        check_native_replay(_core, [receipt], result["rows"], [{"belief": call["raw"]}], templates,
                            arm, manifest["query_time"], run / result["database"])
        assert result["database"] not in db_hashes
        db_hashes[result["database"]] = result["database_sha256"]
        if case["track"] == "synthetic":
            by_id = {r["id"]: r for r in result["rows"]}
            candidate = json.dumps([{k: by_id[sid][k] for k in trial.SEMANTIC_FIELDS}
                                    for sid in receipt["statement_ids"]], ensure_ascii=False)
            assert candidate == result["candidate"]
            judge_inputs.append((expected_id, case["question"], case["answer"], candidate,
                                 result["fidelity_judgment"]))
        else:
            assert result["p1_counts"] == {k: list(v) for k, v in
                                          trial.extraction.p1.evaluate_record(case["record"], predicted).items()}
    scoped, expected_answers = {}, []
    scoped_order = [(record, arm) for i, record in enumerate(inputs["scoped"])
                    for arm in (trial.PRIMARY_ARMS if i % 2 == 0 else trial.PRIMARY_ARMS[::-1])]
    assert set(failed_ids) <= {("scoped", r["item_id"], a) for r, a in scoped_order}
    cursor, ingested, selected_lines, native_replays = 164, 0, 0, 164
    for record, arm in scoped_order:
        expected_id = ("scoped", record["item_id"], arm)
        result = load(run / f"scoped_{record['item_id']}_{arm}.json")
        scoped[expected_id] = result
        assert identity(result) == expected_id
        failed = expected_id in failed_ids
        assert (result.get("status") == "failed") == failed
        templates = {"belief": prompts["belief"][arm], "general_fact": prompts["general_fact"],
                     "episodic": prompts["episodic"]}
        units = inputs["scoped_units"][record["item_id"]]
        raw_responses = []
        count = len(result["receipts"])
        assert count < len(units) if failed else count == len(units)
        for unit_index, (unit, receipt) in enumerate(zip(units[:count], result["receipts"], strict=True)):
            journal = ingestion[ingested]
            ingested += 1
            assert identity(journal) == expected_id and journal["unit_index"] == unit_index
            assert receipt == {k: v for k, v in journal.items() if k not in (*IDENTITY, "unit_index")}
            assert receipt["unit"] == unit
            raw = {}
            for channel, prompt in trial.render_prompts(templates, unit["holder"], unit["payload"]).items():
                call = calls[cursor]
                cursor += 1
                assert identity(call) == expected_id and call["unit_index"] == unit_index
                assert call["channel"] == channel and call["prompt"] == prompt
                assert call["ok"] and not call["error"]
                trial.extraction.parse_response(call["raw"])
                raw[channel] = call["raw"]
            raw_responses.append(raw)
        if failed:
            assert result["error"] == failed_ids[expected_id]["error"]
            assert "embedding" not in result and "recall" not in result
            unit = units[count]
            parse_error = None
            for channel, prompt in trial.render_prompts(templates, unit["holder"], unit["payload"]).items():
                call = calls[cursor]
                cursor += 1
                assert identity(call) == expected_id and call["unit_index"] == count
                assert call["channel"] == channel and call["prompt"] == prompt
                if not call["ok"]:
                    parse_error = f"ValueError: extraction transport failed: {call['error']}"
                else:
                    assert not call["error"]
                    try:
                        trial.extraction.parse_response(call["raw"])
                    except ValueError as exc:
                        parse_error = f"{type(exc).__name__}: {exc}"
                if parse_error is not None:
                    break
            assert parse_error == result["error"]
        check_database(run, result, result["receipts"], result["before"], result["after"], manifest, vectors=not failed)
        check_native_replay(_core, result["receipts"], result["before"], raw_responses, templates,
                            arm, manifest["query_time"], run / result["database"])
        native_replays += count
        if not failed:
            selected_lines += check_recall(result, manifest)
        assert result["database"] not in db_hashes
        db_hashes[result["database"]] = result["database_sha256"]
    assert cursor == len(calls) and ingested == len(ingestion)
    assert set(db_hashes) == {str(p.relative_to(run)) for p in (run / "databases").glob("*.db")}
    for i, record in enumerate(inputs["scoped"]):
        arms = trial.PRIMARY_ARMS if i % 2 == 0 else trial.PRIMARY_ARMS[::-1]
        expected_answers.extend((record, arm) for arm in (*arms, "full")
                                if ("scoped", record["item_id"], arm) not in failed_ids)
    for result, call, (record, arm) in zip(answers, answer_calls, expected_answers, strict=True):
        expected_id = ("scoped", record["item_id"], arm)
        assert identity(result) == identity(call) == expected_id
        if arm == "full":
            memory = "\n".join(f"[{t['observed_at']}] {t['speaker']}: {t['text']}"
                               for t in record["history"]).splitlines()
        else:
            memory = scoped[expected_id]["recall"]["block"].splitlines()
        assert call["prompt"] == trial.ladder._ladder_prompt_free(record, memory)
        assert call["raw"] == result["response"] and result["response"].strip()
        judge_inputs.append((expected_id, record["question"], record["answer"], result["response"], result["judgment"]))
    for i, (expected_id, question, reference, candidate, judgment) in enumerate(judge_inputs):
        selected_votes = votes[i * 3:(i + 1) * 3]
        assert judgment["votes"] == [{k: v for k, v in r.items() if k not in IDENTITY} for r in selected_votes]
        for repeat, vote in enumerate(selected_votes):
            raw = raw_votes[i * 3 + repeat]
            assert raw == {k: v for k, v in vote.items() if k != "accepted"}
            assert identity(vote) == expected_id and vote["repeat"] == repeat
            assert vote["prompt"] == trial.audit._judge_prompt(question, reference, candidate)
            assert vote["raw"].strip().upper() in ("YES", "NO")
            assert vote["accepted"] == (vote["raw"].strip().upper() == "YES")
        accepted = sum(v["accepted"] for v in selected_votes)
        assert judgment["acceptances"] == accepted and judgment["ok"] == (accepted >= 2)
    expected_result = trial.summarize(cases, answers)
    if continued:
        expected_result["scoped_failures"] = failures
    assert load(run / "results.json") == expected_result
    receipt = {"status": "verified", "verified_at": datetime.now(timezone.utc).isoformat(),
               "counts": counts, "scoped_failure_count": len(failures),
               "database_count": len(db_hashes), "offline_native_replays": native_replays,
               "selected_lines_checked_against_rows": selected_lines,
               "verification_script_sha256": digest(Path(__file__)), "database_sha256": db_hashes,
               "artifact_sha256": {p.name: digest(p) for p in run.iterdir()
                                   if p.is_file() and p.name != "verification.json"}}
    trial.controls.dump(run / "verification.json", receipt)
    return {k: v for k, v in receipt.items() if k not in ("artifact_sha256", "database_sha256")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--prepared", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.run.resolve(), args.prepared.resolve()), indent=2))


if __name__ == "__main__":
    main()

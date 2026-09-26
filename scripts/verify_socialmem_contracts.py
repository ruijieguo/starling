#!/usr/bin/env python3
"""Verify frozen contract-trial artifacts, including failed calls and native replay."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile

import eval_socialmem_contracts as experiment
import verify_socialmem_predicates as prior

load, lines, digest = experiment.load, experiment.lines, experiment.digest
trial = experiment.trial


def check_case(core, run, manifest, case, arm, template, result, call):
    assert prior.identity(call) == prior.identity(result) == (case["track"], case["id"], arm)
    assert call["prompt"] == experiment.followup.render(template, case)
    assert (call["ok"], call["error"]) == (result["ok"], result["error"])
    scores = experiment.score(case, call["raw"], result["receipt"], result["rows"], call["ok"])
    assert all(json.loads(json.dumps(value)) == result[key] for key, value in scores.items())
    expected = f"databases/{case['track']}_{case['id']}_{arm}.db"
    assert result["database"] == expected
    database = run / expected
    assert trial.controls.frozen_database_hash(database) == result["database_sha256"]
    with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        rows = [dict(r) for r in conn.execute("SELECT * FROM statements ORDER BY id")]
        assert rows == result["rows"]
        assert all(r["tenant_id"] == "default" and r["holder_id"] == case["holder"] for r in rows)
        assert all(datetime.fromisoformat(r["created_at"]) <= datetime.fromisoformat(manifest["query_time"]) for r in rows)
        receipt = result["receipt"]
        assert receipt["outcome"] == "accepted"
        assert set(receipt["statement_ids"]) == {r["id"] for r in rows}
        assert len(receipt["statement_ids"]) == len(rows)
        engram, = conn.execute("SELECT id,tenant_id,payload_inline,content_hash,declared_transformations_json,byte_preserving FROM engrams").fetchall()
        payload = case["passage"].encode("utf-8")
        fingerprint = hashlib.sha256(b"v1\x1f" + payload + b"\x1f").hexdigest()
        assert (engram["id"], engram["tenant_id"]) == (receipt["engram_ref"], "default")
        assert bytes(engram["payload_inline"]) == payload and engram["content_hash"] == fingerprint
        assert json.loads(engram["declared_transformations_json"]) == [] and engram["byte_preserving"] == 1
        for row in rows:
            evidence = json.loads(row["evidence_json"])
            assert evidence and all(e["engram_ref"] == engram["id"] and e["content_hash"] == fingerprint
                                    and e["status"] == "active" for e in evidence)
        assert conn.execute("SELECT count(*) FROM statement_vectors").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM episodic_events").fetchone()[0] == 0
        pipelines = [list(r) for r in conn.execute("SELECT id,status FROM pipeline_run ORDER BY id")]
        assert pipelines == result["pipelines"] and len(pipelines) == 1
        assert pipelines[0][1] == ("failed" if receipt["extraction_failed"] else "finished")
    from starling import runtime

    with tempfile.TemporaryDirectory(prefix="socialmem-contract-replay-") as tmp:
        replay_db = Path(tmp) / "replay.db"
        rt = runtime._build_local_store_sqlite_runtime(replay_db)
        rt.start()
        replay = experiment.native(core, rt.adapter, case, arm, template, call["raw"],
                                   manifest["query_time"], call["ok"], call["error"])
        actual = trial.temporal.statement_rows(replay_db)
        assert replay["extraction_failed"] == receipt["extraction_failed"]
        assert replay["outcome"] == receipt["outcome"]
        assert len(replay["statement_ids"]) == len(receipt["statement_ids"])
        assert prior.semantics(actual) == prior.semantics(rows)
        del rt


def verify(run):
    from starling import _core

    manifest = load(run / "manifest.json")
    assert manifest["status"] == "complete"
    assert manifest["execution_mode"] in ("real", "offline_smoke")
    assert manifest["core_sha256"] == digest(Path(_core.__file__))
    for source, fingerprint in manifest["source_sha256"].items():
        assert digest(run / "source_archive" / Path(source).name) == fingerprint
        assert digest(experiment.ROOT / source) == fingerprint
    previous = Path(manifest["previous"])
    assert digest(previous / "verification.json") == manifest["previous_verification_sha256"]
    inputs, prompts, parent, grandparent = experiment.prepare(previous)
    assert manifest["extract_transport"] == parent["extract_transport"]
    assert manifest["judge_endpoint"] == grandparent["answer_endpoint"]
    assert (manifest["judge_model"], manifest["judge_max_tokens"], manifest["judge_repeats"]) == ("gpt-5.5", 8, 3)
    assert manifest["expected_completions"] == experiment.EXPECTED
    assert manifest["arms"] == json.loads(json.dumps(experiment.ARMS))
    assert load(run / "inputs.json") == inputs and load(run / "prompts.json") == prompts
    for name in ("inputs", "prompts"):
        assert digest(run / f"{name}.json") == manifest[f"{name}_sha256"]
    calls, results = lines(run / "extraction_calls.jsonl"), lines(run / "cases.jsonl")
    assert len(calls) == len(results) == 236
    assert len({prior.identity(r) for r in results}) == 236
    assert len({r["database"] for r in results}) == 236
    assert not list(run.glob("*answer*.jsonl"))
    for (case, arm), result, call in zip(experiment.schedule(inputs), results, calls, strict=True):
        check_case(_core, run, manifest, case, arm, prompts[case["track"]][arm], result, call)
    assert {str(p.relative_to(run)) for p in (run / "databases").glob("*.db")} == {r["database"] for r in results}
    judgments, votes, raw_votes = (lines(run / name) for name in
                                  ("judgments.jsonl", "judge_calls.jsonl", "judge_responses.jsonl"))
    assert len(judgments) == 32 and len(votes) == len(raw_votes) == 96
    selected = [r for r in results if r["track"] == "synthetic"]
    cases = {c["id"]: c for c in inputs["synthetic"]}
    for i, (result, entry) in enumerate(zip(selected, judgments, strict=True)):
        assert prior.identity(entry) == prior.identity(result)
        assert entry["native_ok"] == result["native_ok"]
        assert entry["candidate"] == experiment.candidate(result["rows"], result["receipt"])
        case = cases[result["id"]]
        prompt = trial.audit._judge_prompt(case["question"], case["answer"], entry["candidate"])
        selected_votes = votes[i * 3:(i + 1) * 3]
        for repeat, vote in enumerate(selected_votes):
            raw = raw_votes[i * 3 + repeat]
            assert prior.identity(raw) == prior.identity(vote) == prior.identity(result)
            assert raw["repeat"] == repeat and raw["prompt"] == prompt
            assert vote == {**raw, **experiment.parse_vote(raw["raw"], raw["error"])}
        accepted = sum(v["accepted"] for v in selected_votes)
        assert entry["judgment"] == {"ok": accepted >= 2, "acceptances": accepted,
            "failed": sum(not v["valid"] for v in selected_votes), "votes": selected_votes}
    assert load(run / "results.json") == experiment.summarize(results, judgments)
    receipt = {"status": "verified", "execution_mode": manifest["execution_mode"],
               "verified_at": datetime.now(timezone.utc).isoformat(),
               "database_count": 236, "offline_native_replays": 236, "judge_responses": 96,
               "native_failed": sum(not r["native_ok"] for r in results),
               "invalid_judgments": sum(not v["valid"] for v in votes),
               "verification_script_sha256": digest(Path(__file__)),
               "artifact_sha256": {p.name: digest(p) for p in run.iterdir() if p.is_file() and p.name != "verification.json"},
               "database_sha256": {r["database"]: r["database_sha256"] for r in results}}
    trial.controls.dump(run / "verification.json", receipt)
    return {k: v for k, v in receipt.items() if k not in ("artifact_sha256", "database_sha256")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.run.resolve()), indent=2))

#!/usr/bin/env python3
"""Verify the fixed follow-up offline, replaying both successes and failures."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile

import eval_socialmem_followup as followup
import verify_socialmem_predicates as prior

trial = followup.trial
load, lines, digest = trial.extraction.load, trial.extraction.load_lines, trial.controls.digest


def check_case(core, run, manifest, case, arm, template, result, call):
    wanted = (case["track"], case["id"], arm)
    assert prior.identity(result) == prior.identity(call) == wanted
    assert call["prompt"] == followup.render(template, case)
    assert (result["ok"], result["error"]) == (call["ok"], call["error"])
    scores = followup.score(case, call["raw"], result["receipt"], result["rows"], call["ok"])
    assert all(json.loads(json.dumps(value)) == result[key] for key, value in scores.items())
    expected_database = f"databases/{case['track']}_{case['id']}_{arm}.db"
    assert result["database"] == expected_database
    database = run / expected_database
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
        engrams = conn.execute("SELECT id,tenant_id,payload_inline,content_hash,declared_transformations_json,byte_preserving FROM engrams").fetchall()
        engram, = engrams
        payload = case["passage"].encode("utf-8")
        content_hash = hashlib.sha256(b"v1\x1f" + payload + b"\x1f").hexdigest()
        assert engram["id"] == receipt["engram_ref"] and engram["tenant_id"] == "default"
        assert bytes(engram["payload_inline"]) == payload and engram["content_hash"] == content_hash
        assert json.loads(engram["declared_transformations_json"]) == [] and engram["byte_preserving"] == 1
        for row in rows:
            evidence = json.loads(row["evidence_json"])
            assert evidence
            assert all(e["engram_ref"] == engram["id"] and e["content_hash"] == content_hash
                       and e["status"] == "active" for e in evidence)
        assert conn.execute("SELECT count(*) FROM statement_vectors").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM episodic_events").fetchone()[0] == 0
        pipelines = [list(r) for r in conn.execute("SELECT id,status FROM pipeline_run ORDER BY id")]
        assert pipelines == result["pipelines"]
        assert len(pipelines) == 1
        assert pipelines[0][1] == ("failed" if receipt["extraction_failed"] else "finished")
    from starling import runtime

    with tempfile.TemporaryDirectory(prefix="socialmem-followup-verify-") as tmp:
        replay_db = Path(tmp) / "replay.db"
        rt = runtime._build_local_store_sqlite_runtime(replay_db)
        rt.start()
        replay = followup.native(core, rt.adapter, case, arm, template, call["raw"], manifest["query_time"],
                                 call["ok"], call["error"])
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
    assert manifest["core_sha256"] == digest(Path(_core.__file__))
    for source, fingerprint in manifest["source_sha256"].items():
        assert digest(run / "source_archive" / Path(source).name) == fingerprint
        assert digest(followup.ROOT / source) == fingerprint
    for name in ("inputs", "prompts"):
        assert digest(run / f"{name}.json") == manifest[f"{name}_sha256"]
    previous = Path(manifest["previous"])
    assert digest(previous / "verification.json") == manifest["previous_verification_sha256"]
    parent_verification = load(previous / "verification.json")
    for name, fingerprint in parent_verification["artifact_sha256"].items():
        assert digest(previous / name) == fingerprint
    original_inputs, original_prompts = load(previous / "inputs.json"), load(previous / "prompts.json")
    inputs, prompts = load(run / "inputs.json"), load(run / "prompts.json")
    assert inputs["p1"] == original_inputs["p1"]
    assert [c["record"] for c in inputs["p1"]] == lines(followup.ROOT / "tests/data/eval_p1_corpus.jsonl")
    assert inputs["general_fact"] == followup.fact_cases(original_inputs["scoped"])
    assert prompts["p1"] == {arm: original_prompts["belief"][arm] for arm in ("baseline", "vocabulary")}
    assert prompts["general_fact"] == {"baseline": original_prompts["general_fact"],
                                       "single_array": followup.single_array_prompt(original_prompts["general_fact"])}
    assert manifest["extract_transport"] == load(previous / "manifest.json")["extract_transport"]
    assert manifest["expected_completions"] == {"extraction": 136, "answer": 0, "judge": 0}
    assert len(inputs["p1"]) == 50 and len(inputs["general_fact"]) == 18
    calls, results = lines(run / "extraction_calls.jsonl"), lines(run / "cases.jsonl")
    assert len(calls) == len(results) == 136
    assert len({prior.identity(r) for r in results}) == len(results)
    assert not list(run.glob("*judge*.jsonl")) and not list(run.glob("*answer*.jsonl"))
    for (case, arm), result, call in zip(followup.schedule(inputs), results, calls, strict=True):
        check_case(_core, run, manifest, case, arm, prompts[case["track"]][arm], result, call)
    assert {str(p.relative_to(run)) for p in (run / "databases").glob("*.db")} == {r["database"] for r in results}
    assert len({r["database"] for r in results}) == 136
    assert load(run / "results.json") == followup.summarize(results)
    receipt = {"status": "verified", "verified_at": datetime.now(timezone.utc).isoformat(),
               "database_count": 136, "offline_native_replays": 136,
               "native_failed": sum(not r["native_ok"] for r in results),
               "verification_script_sha256": digest(Path(__file__)),
               "verification_helper_sha256": digest(Path(prior.__file__)),
               "artifact_sha256": {p.name: digest(p) for p in run.iterdir() if p.is_file() and p.name != "verification.json"},
               "database_sha256": {r["database"]: r["database_sha256"] for r in results}}
    trial.controls.dump(run / "verification.json", receipt)
    return {k: v for k, v in receipt.items() if k not in ("artifact_sha256", "database_sha256")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.run.resolve()), indent=2))

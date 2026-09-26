#!/usr/bin/env python3
"""Verify supplemental extraction, native replay and frozen-base QA evidence."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile

import eval_socialmem_supplement as experiment
import verify_socialmem_predicates as prior

trial = experiment.trial
load, lines, digest = experiment.load, experiment.lines, experiment.digest


def database_rows(run, result, expected):
    path = run / result["database"]
    assert digest(path) == result["database_sha256"]
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        rows = [dict(r) for r in conn.execute("SELECT * FROM statements ORDER BY id")]
        assert rows == expected
        assert all(r["tenant_id"] == "default" for r in rows)
        pipelines = [list(r) for r in conn.execute("SELECT id,status FROM pipeline_run ORDER BY id")]
        assert pipelines == result["pipelines"]
    return path


def check_case(core, run, case, base, extra, templates, result, now):
    path = database_rows(run, result, result["after"])
    assert result["track"] == case["track"] and result["id"] == case["id"]
    assert extra["prompt"] == experiment.render(templates["supplement"], case)
    if base is not None:
        assert base["prompt"] == experiment.render(templates["baseline"], case)
    assert {r["id"] for r in result["rows"]} == set(result["receipt"]["statement_ids"])
    assert result["rows"] == [r for r in result["after"] if r["id"] in result["receipt"]["statement_ids"]]
    if base is not None:
        assert {r["id"] for r in result["before"]} == set(result["base_receipt"]["statement_ids"])
    else:
        assert result["before"] == [] and result["base_receipt"] is None
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as conn:
        payload = case["passage"].encode("utf-8")
        fingerprint = hashlib.sha256(b"v1\x1f" + payload + b"\x1f").hexdigest()
        receipts = [r for r in (result["base_receipt"], result["receipt"]) if r is not None]
        for receipt in receipts:
            row = conn.execute("SELECT payload_inline,content_hash FROM engrams WHERE id=? AND tenant_id='default'",
                               (receipt["engram_ref"],)).fetchone()
            assert bytes(row[0]) == payload and row[1] == fingerprint
        for row in result["after"]:
            assert row["holder_id"] == case["holder"]
            evidence = json.loads(row["evidence_json"])
            assert evidence and all(e["engram_ref"] in {r["engram_ref"] for r in receipts}
                                    and e["content_hash"] == fingerprint and e["status"] == "active" for e in evidence)
        assert conn.execute("SELECT count(*) FROM statement_vectors").fetchone()[0] == 0
    with tempfile.TemporaryDirectory(prefix="socialmem-supplement-verify-") as tmp:
        replay_out = Path(tmp)
        (replay_out / "databases").mkdir()
        replay = experiment.evaluate_case(core, case, base, extra, templates, replay_out, now)
        for key in ("before", "after", "rows"):
            assert prior.semantics(replay[key]) == prior.semantics(result[key])
        skipped = {"before", "after", "rows", "base_receipt", "receipt", "pipelines", "database", "database_sha256"}
        for key in result.keys() - skipped:
            if key == "stored_objects":
                assert sorted(replay[key]) == sorted(result[key]), (case["id"], key)
            else:
                assert json.loads(json.dumps(replay[key])) == result[key], (case["id"], key)
        # Fresh replay UUIDs change ORDER BY id; status multiplicity is stable.
        assert sorted(r[1] for r in replay["pipelines"]) == sorted(r[1] for r in result["pipelines"])
        for key in ("base_receipt", "receipt"):
            if result[key] is not None:
                assert replay[key]["extraction_failed"] == result[key]["extraction_failed"]


def verify(run, *, allow_verifier_update=False):
    from starling import _core

    run = run.resolve()
    manifest, inputs, templates = (load(run / name) for name in ("manifest.json", "inputs.json", "prompts.json"))
    assert manifest["status"] == "complete" and manifest["execution_mode"] in ("real", "offline_smoke")
    assert manifest["core_sha256"] == digest(Path(_core.__file__))
    assert digest(run / "source_archive" / Path(_core.__file__).name) == manifest["core_sha256"]
    assert manifest["expected_completions"] == experiment.EXPECTED
    assert manifest["query_time"] == experiment.NOW
    verifier_path = "scripts/verify_socialmem_supplement.py"
    verifier_updates = {}
    for name, fingerprint in manifest["source_sha256"].items():
        assert digest(run / "source_archive" / name) == fingerprint
        current = digest(experiment.ROOT / name)
        if name == verifier_path and allow_verifier_update and current != fingerprint:
            verifier_updates[name] = {"archived": fingerprint, "verification": current}
        else:
            assert current == fingerprint
    for name in ("inputs", "prompts"):
        assert digest(run / f"{name}.json") == manifest[f"{name}_sha256"]
    previous = Path(manifest["previous"])
    assert digest(previous / "verification.json") == manifest["previous_verification_sha256"]
    scoped = Path(inputs["frozen_sources"][0]["path"]).parents[1]
    expected_inputs, expected_templates = experiment.prepare(previous, scoped)
    assert inputs == expected_inputs and templates == expected_templates
    calls, results = lines(run / "extraction_calls.jsonl"), lines(run / "cases.jsonl")
    assert len(calls) == 100 and len(results) == 84
    assert len({(r["track"], r["id"]) for r in results}) == 84
    assert len({r["database"] for r in results}) == 84
    call_map = {(r["track"], r["id"], r["channel"]): r for r in calls}
    result_map = {(r["track"], r["id"]): r for r in results}
    assert len(call_map) == 100
    expected_order = []
    for track in ("p1", "synthetic", "controls", "scoped"):
        for i, case in enumerate(inputs[track]):
            order = ("baseline", "supplement") if i % 2 == 0 else ("supplement", "baseline")
            expected_order.extend((track, case["id"], c) for c in (order if track == "synthetic" else ("supplement",)))
            base = (inputs["base_calls"][case["id"]] if track == "p1" else
                    call_map[(track, case["id"], "baseline")] if track == "synthetic" else None)
            extra = call_map[(track, case["id"], "supplement")]
            check_case(_core, run, case, base, extra, templates, result_map[(track, case["id"])], manifest["query_time"])
    assert [(r["track"], r["id"], r["channel"]) for r in calls] == expected_order

    judgments, answers = lines(run / "judgments.jsonl"), lines(run / "answers.jsonl")
    answer_calls = lines(run / "answer_calls.jsonl")
    assert len(judgments) == 32 and len(answers) == len(answer_calls) == 6
    assert len({(r["id"], r["arm"]) for r in judgments}) == 32
    assert len({(r["id"], r["arm"]) for r in answers}) == 6
    groups = []
    for j in judgments:
        case, = [c for c in inputs["synthetic"] if c["id"] == j["id"]]
        result = result_map[("synthetic", j["id"])]
        selected = result["before"] if j["arm"] == "baseline" else result["after"]
        candidate = json.dumps([{k: r[k] for k in trial.SEMANTIC_FIELDS} for r in selected], ensure_ascii=False)
        assert j["candidate"] == candidate
        assert j["native_ok"] == (not result["base_receipt"]["extraction_failed"] and
                                    (j["arm"] == "baseline" or result["native_ok"]))
        groups.append(("synthetic", j, trial.audit._judge_prompt(case["question"], case["answer"], candidate)))
    for answer, call in zip(answers, answer_calls, strict=True):
        record, = [r for r in inputs["records"] if r["item_id"] == answer["id"]]
        assert (call["id"], call["arm"]) == (answer["id"], answer["arm"])
        assert call["raw"] == answer["response"] and call["error"] == answer["error"]
        assert answer["answer_ok"] == bool(not call["error"] and call["raw"].strip())
        if answer["arm"] == "full":
            block = trial.pipe.recall_block(_core, "S_full", adapter=None, embedder=None, index=None,
                                           question=record["question"], history=record["history"])["block"]
        else:
            result = load(run / f"qa_{answer['id']}_{answer['arm']}.json")
            database_rows(run, result, result["after"])
            source = inputs["frozen_sources"][inputs["records"].index(record)]
            assert digest(Path(source["path"])) == source["sha256"]
            assert trial.temporal.statement_rows(Path(source["path"])) == result["base_rows"]
            by_id = {r["id"]: r for r in result["before"]}
            assert prior.semantics([by_id[r["id"]] for r in result["base_rows"]]) == prior.semantics(result["base_rows"])
            for receipt in result["receipts"]:
                expected = result_map[("scoped", receipt["id"])]
                assert prior.semantics([by_id[sid] for sid in receipt["statement_ids"]]) == prior.semantics(expected["rows"])
            expected_sources = [c["id"] for c in inputs["scoped"] if c["item_id"] == answer["id"]]
            assert [r["id"] for r in result["receipts"]] == (expected_sources if answer["arm"] == "supplement" else [])
            prior.check_sleep_rows(result, result["before"], result["after"])
            prior.check_recall(result, manifest)
            assert result["embedding"]["failed"] == 0
            block = result["recall"]["block"]
        assert call["prompt"] == trial.ladder._ladder_prompt_free(record, block.splitlines())
        groups.append(("scoped", answer, trial.audit._judge_prompt(record["question"], record["answer"], call["raw"])))
    votes, raw_votes = lines(run / "judge_calls.jsonl"), lines(run / "judge_responses.jsonl")
    assert len(votes) == len(raw_votes) == 114
    for i, (track, result, prompt) in enumerate(groups):
        selected = votes[i * 3:(i + 1) * 3]
        assert result["judgment"]["votes"] == selected
        for repeat, vote in enumerate(selected):
            raw = raw_votes[i * 3 + repeat]
            assert (raw["track"], raw["id"], raw["arm"], raw["repeat"], raw["prompt"]) == (
                track, result["id"], result["arm"], repeat, prompt)
            assert vote == {**raw, **experiment.contracts.parse_vote(raw["raw"], raw["error"])}
        accepts = sum(v["accepted"] for v in selected)
        assert result["judgment"]["acceptances"] == accepts
        assert result["judgment"]["failed"] == sum(not v["valid"] for v in selected)
        assert result["judgment"]["ok"] == (accepts >= 2)
    assert load(run / "results.json") == experiment.summarize(results, judgments, answers)
    databases = list((run / "databases").glob("*.db"))
    assert len(databases) == 88
    receipt = {"status": "verified", "execution_mode": manifest["execution_mode"],
               "verifier_updates": verifier_updates,
               "verified_at": datetime.now(timezone.utc).isoformat(), "databases": 88,
               "native_case_replays": 84, "extraction_calls": 100, "answers": 6, "judge_votes": 114,
               "artifact_sha256": {str(p.relative_to(run)): digest(p) for p in sorted(run.rglob("*"))
                                   if p.is_file() and p.name != "verification.json"}}
    experiment.dump(run / "verification.json", receipt)
    return {k: v for k, v in receipt.items() if k != "artifact_sha256"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--allow-verifier-update", action="store_true",
                        help="Allow only this verifier's code to differ; record both hashes. Executed sources stay frozen.")
    args = parser.parse_args()
    print(json.dumps(verify(args.run, allow_verifier_update=args.allow_verifier_update), indent=2))

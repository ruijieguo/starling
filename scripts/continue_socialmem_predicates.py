#!/usr/bin/env python3
"""Continue the fixed scoped trial after an archived first-cell parse failure."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
from urllib.parse import urlsplit, urlunsplit

import eval_socialmem_predicates as trial


def failed_scope(out, record, arm, error):
    identity = {"track": "scoped", "id": record["item_id"], "arm": arm}
    destination = out / f"scoped_{record['item_id']}_{arm}.json"
    if destination.exists():
        raise RuntimeError("failure after native retrieval; preserve its existing result")
    receipts = [r for r in trial.extraction.load_lines(out / "scoped_ingestion.jsonl")
                if all(r[k] == value for k, value in identity.items())]
    receipts = [{k: v for k, v in r.items() if k not in (*identity, "unit_index")} for r in receipts]
    database = out / "databases" / f"scoped_{record['item_id']}_{arm}.db"
    rows = trial.temporal.statement_rows(database)
    result = {**identity, "status": "failed", "error": error, "receipts": receipts,
              "before": rows, "after": rows, "pipelines": trial.pipeline_rows(database),
              "database": str(database.relative_to(out)),
              "database_sha256": trial.controls.frozen_database_hash(database)}
    trial.controls.dump(destination, result)
    trial.ladder.append_journal(out / "scoped_failures.jsonl", identity | {"error": error})


def prepare_continuation(initial, out):
    from starling import _core

    manifest = trial.extraction.load(initial / "manifest.json")
    assert manifest["status"] == "failed" and manifest["error"].startswith("JSONDecodeError: Extra data")
    assert manifest["core_sha256"] == trial.controls.digest(Path(_core.__file__))
    for name in ("inputs", "prompts"):
        assert manifest[f"{name}_sha256"] == trial.controls.digest(initial / f"{name}.json")
    for source, fingerprint in manifest["source_sha256"].items():
        assert trial.controls.digest(trial.ROOT / source) == fingerprint
        assert trial.controls.digest(initial / "source_archive" / Path(source).name) == fingerprint
    cases = trial.extraction.load_lines(initial / "cases.jsonl")
    calls = trial.extraction.load_lines(initial / "extraction_calls.jsonl")
    assert len(cases) == 164 and len(calls) == 169
    assert {k: calls[-1][k] for k in ("track", "id", "arm", "unit_index", "channel")} == {
        "track": "scoped", "id": "Q1_a5s1c1", "arm": "baseline", "unit_index": 1, "channel": "general_fact"}
    assert not (initial / "answer_calls.jsonl").exists()
    shutil.copytree(initial, out)
    shutil.copyfile(initial / "manifest.json", out / "initial_manifest.json")
    manifest.update(status="running", continued_at=datetime.now(timezone.utc).isoformat(),
                    initial_run=str(initial.resolve()), initial_manifest_sha256=trial.controls.digest(initial / "manifest.json"),
                    initial_artifact_sha256={str(p.relative_to(initial)): trial.controls.digest(p)
                                             for p in initial.rglob("*") if p.is_file()},
                    planned_completions=manifest["expected_completions"],
                    continuation_protocol="Keep all 164 completed cases and votes byte-identical. "
                    "Retain the first scoped cell as a technical failure and do not repeat any call. "
                    "Continue the remaining three memory cells and both full-dialogue controls. "
                    "Any further scoped failure stays in the denominator without a fabricated answer or vote.")
    source = Path(__file__).resolve()
    shutil.copyfile(source, out / "source_archive" / source.name)
    manifest["source_sha256"][str(source.relative_to(trial.ROOT))] = trial.controls.digest(source)
    trial.controls.dump(out / "manifest.json", manifest)
    return manifest, cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--initial", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    from starling import _core

    manifest, cases = prepare_continuation(args.initial, args.out)
    inputs, prompts = (trial.extraction.load(args.out / f"{name}.json") for name in ("inputs", "prompts"))
    now = manifest["query_time"]
    llm, transport = trial.extraction.build_llm(_core)
    assert transport == manifest["extract_transport"]
    os.environ["EMBEDDING_MODEL"], os.environ["EMBEDDING_DIM"] = manifest["embedding_model"], str(manifest["embedding_dim"])
    embedder = trial.ladder._build_real_embedder(_core)
    url = urlsplit(os.environ["OPENAI_BASE_URL"])
    assert url.scheme == "https" and url.hostname and not any((url.username, url.password, url.query, url.fragment))
    os.environ["OPENAI_BASE_URL"] = urlunsplit(url._replace(path="/v1"))
    assert os.environ["OPENAI_BASE_URL"] == manifest["answer_endpoint"]
    answers = []
    try:
        for i, record in enumerate(inputs["scoped"]):
            arms = trial.PRIMARY_ARMS if i % 2 == 0 else trial.PRIMARY_ARMS[::-1]
            for arm in arms:
                if i == 0 and arm == "baseline":
                    failed_scope(args.out, record, arm, manifest["error"])
                    continue
                print(f"[scoped] {record['item_id']}/{arm}", flush=True)
                templates = {"belief": prompts["belief"][arm], "general_fact": prompts["general_fact"],
                             "episodic": prompts["episodic"]}
                try:
                    answers.append(trial.evaluate_scoped(
                        _core, llm, embedder, trial.audit._chat_completion, record,
                        inputs["scoped_units"][record["item_id"]], arm, templates, args.out, now))
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"
                    failed_scope(args.out, record, arm, error)
                    print(f"[scoped-failed] {record['item_id']}/{arm}: {error}", flush=True)
            full = trial.pipe.recall_block(_core, "S_full", adapter=None, embedder=None, index=None,
                                            question=record["question"], history=record["history"])
            answers.append(trial.qa_answer(trial.audit._chat_completion, record, "full", full["block"], args.out))
        result = trial.summarize(cases, answers)
        result["scoped_failures"] = trial.extraction.load_lines(args.out / "scoped_failures.jsonl")
        trial.controls.dump(args.out / "results.json", result)
        manifest.update(status="complete_with_errors", completed_at=datetime.now(timezone.utc).isoformat(),
                        observed_completions={key: len(trial.extraction.load_lines(args.out / f"{name}.jsonl"))
                                              for key, name in (("extraction", "extraction_calls"),
                                                                ("answer", "answer_calls"), ("judge", "judge_calls"))})
    except Exception as exc:
        manifest.update(status="failed", continuation_error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        trial.controls.dump(args.out / "manifest.json", manifest)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Export native renderings and compare answers for fixed SocialMemBench entries."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import time
from urllib.parse import urlsplit, urlunsplit

import eval_judge_audit as audit
import eval_ladder as ladder
import eval_socialmem_controls as controls
from eval_socialmem_scoped import repeated_judge

ROOT = Path(__file__).resolve().parents[1]
VARIANTS = ("star_immediate", "star_sleep")
ROW_FIELDS = (
    "id", "tenant_id", "holder_id", "holder_perspective", "subject_kind",
    "subject_id", "predicate", "object_kind", "object_value",
    "canonical_object_hash", "modality", "polarity", "confidence", "observed_at",
    "valid_from", "valid_to", "consolidation_state", "review_status",
    "evidence_json", "affect_json",
)


def read_json(path):
    return json.loads(path.read_text())


def export_renderings(parent: Path, out: Path, phase: str) -> None:
    from starling import _core, runtime

    manifest = read_json(parent / "manifest.json")
    if manifest["status"] != "complete":
        raise ValueError("parent evaluation is incomplete")
    core_path = Path(_core.__file__)
    if phase == "before" and controls.digest(core_path) != manifest["core_sha256"]:
        raise ValueError("before export requires the actual parent core")
    corpus = audit.load_corpus(parent / "prepared_corpus.jsonl")
    if ladder.corpus_hash(corpus) != manifest["corpus_hash"]:
        raise ValueError("parent corpus fingerprint mismatch")
    by_id = {r["item_id"]: r for r in corpus}
    journal = audit.load_corpus(parent / "journal.jsonl")
    selected = [r for r in journal if r["variant"] in VARIANTS]
    expected = {(r["item_id"], v) for r in corpus for v in VARIANTS}
    if len(selected) != len(expected) or {(r["item_id"], r["variant"]) for r in selected} != expected:
        raise ValueError("parent journal has missing or duplicate cells")
    out.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(core_path, out / core_path.name)
    sources = [Path(__file__), ROOT / "src/retrieval/context_pack.cpp",
               ROOT / "bindings/python/bind_05_retrieval.cpp",
               Path(ladder.__file__), Path(audit.__file__), Path(controls.__file__),
               ROOT / "scripts/eval_socialmem_scoped.py"]
    (out / "source_archive").mkdir()
    for path in sources:
        shutil.copyfile(path, out / "source_archive" / path.name)
    rows = []
    for cell in selected:
        source = Path(cell["trace"]["db_path"])
        if not source.is_absolute():
            source = ROOT / source
        fingerprint = controls.frozen_database_hash(source)
        if fingerprint != cell["database_sha256"]:
            raise ValueError("parent database fingerprint mismatch")
        recall = cell["trace"]["recall"]
        ids, labels = recall["statement_ids"], recall["labels"]
        if not ids or len(ids) != len(labels) or len(ids) != len(set(ids)):
            raise ValueError("invalid parent selection")
        with sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("parent database integrity failure")
            stored = {r["id"]: dict(r) for r in conn.execute(
                "SELECT * FROM statements WHERE tenant_id='default'")}
        entries = []
        with tempfile.TemporaryDirectory(prefix="socialmem-render-") as tmp:
            db = Path(tmp) / "copy.db"
            controls.backup_database(source, db)
            rt = runtime._build_local_store_sqlite_runtime(db)
            rt.start()
            emb, index = _core.StubEmbeddingAdapter(8), _core.SqliteBlobVectorIndex()
            semantic = _core.SemanticRetriever(rt.adapter, emb, index)
            planner = _core.RetrievalPlanner(rt.adapter, semantic)
            for sid, label in zip(ids, labels, strict=True):
                raw = stored[sid]
                q = _core.PlannerQuery()
                q.tenant_id, q.querier = raw["tenant_id"], raw["holder_id"]
                q.subject_id, q.predicate = raw["subject_id"], raw["predicate"]
                q.as_of_iso8601 = recall["as_of_iso"]
                q.k = len(stored)
                q.trace_id, q.query_id = "render-export", sid
                # Empty query text disables embeddings. This only materializes
                # native rows; the archived ID list defines the answer context.
                result = planner.run(q)
                matches = [e.row for e in result.entries if e.row.id == sid]
                if len(matches) != 1:
                    raise ValueError(f"cannot materialize selected statement: {sid}")
                native = matches[0]
                fields = {key: getattr(native, key) for key in ROW_FIELDS}
                if any(fields[key] != (raw[key] if raw[key] is not None else "")
                       for key in ROW_FIELDS):
                    raise ValueError("native row differs from archived database")
                entries.append({"row": fields, "stored_row": raw, "label": label,
                                "line": _core.render_context_line(
                                    native, getattr(_core.ContextPackLabel, label))})
            del planner, semantic, rt
        block = "\n".join(e["line"] for e in entries)
        record = by_id[cell["item_id"]]
        if ladder._ladder_prompt_free(record, recall["block"].splitlines()) != cell["trace"]["prompt"]:
            raise ValueError("parent prompt cannot be reproduced")
        if phase == "before" and block != recall["block"]:
            raise ValueError("old native rendering does not reproduce parent context")
        if controls.frozen_database_hash(source) != fingerprint:
            raise ValueError("archived source was modified")
        rows.append({"item_id": cell["item_id"], "variant": cell["variant"],
                     "record": record, "database_sha256": fingerprint,
                     "recall": recall, "entries": entries, "block": block,
                     "prompt": ladder._ladder_prompt_free(record, block.splitlines())})
    controls.dump(out / "renderings.json", {
        "status": "complete", "phase": phase, "core_sha256": controls.digest(core_path),
        "parent_manifest_sha256": controls.digest(parent / "manifest.json"),
        "parent_journal_sha256": controls.digest(parent / "journal.jsonl"),
        "source_sha256": {str(p.relative_to(ROOT)): controls.digest(p) for p in sources},
        "rows": rows,
    })
    print(f"Exported {phase}: {len(rows)} fixed selections", flush=True)


def validate_pair(before: dict, after: dict) -> list[dict]:
    if (before["status"], after["status"], before["phase"], after["phase"]) != (
            "complete", "complete", "before", "after"):
        raise ValueError("expected completed before/after exports")
    for key in ("parent_manifest_sha256", "parent_journal_sha256"):
        if before[key] != after[key]:
            raise ValueError(f"paired provenance mismatch: {key}")
    if before["core_sha256"] == after["core_sha256"]:
        raise ValueError("paired exports use the same core")
    if len(before["rows"]) != len(after["rows"]) or not before["rows"]:
        raise ValueError("paired cell count mismatch")
    changes = []
    for old, new in zip(before["rows"], after["rows"], strict=True):
        for key in ("item_id", "variant", "record", "database_sha256", "recall"):
            if old[key] != new[key]:
                raise ValueError(f"paired input mismatch: {key}")
        for export in (old, new):
            entries = export["entries"]
            if ([e["row"]["id"] for e in entries] != export["recall"]["statement_ids"] or
                    [e["label"] for e in entries] != export["recall"]["labels"]):
                raise ValueError("entry selection differs from archived recall")
            if export["block"] != "\n".join(e["line"] for e in entries):
                raise ValueError("block does not match entries")
            if export["prompt"] != ladder._ladder_prompt_free(export["record"], export["block"].splitlines()):
                raise ValueError("prompt does not match context")
        if old["block"] != old["recall"]["block"]:
            raise ValueError("before context differs from parent recall")
        changed = []
        for a, b in zip(old["entries"], new["entries"], strict=True):
            if {k: v for k, v in a.items() if k != "line"} != {k: v for k, v in b.items() if k != "line"}:
                raise ValueError("selected row or label changed")
            row = a["row"]
            prefix = f"[{a['label']}] "
            relation = f"{row['subject_id']} {row['predicate']} {row['object_value']}"
            if not a["line"].startswith(prefix + relation):
                raise ValueError("unexpected old relation rendering")
            suffix = a["line"][len(prefix + relation):]
            marker = {"neg": "NOT", "unknown": "UNKNOWN"}.get(row["polarity"])
            expected = prefix + marker + " (" + relation + ")" + suffix if marker else a["line"]
            if b["line"] != expected:
                raise ValueError("render change exceeds stored polarity")
            if a["line"] != b["line"]:
                changed.append(row["id"])
        changes.append({"item_id": old["item_id"], "variant": old["variant"],
                        "selected": len(old["entries"]), "changed_ids": changed})
    return changes


def compare(before_path: Path, after_path: Path, out: Path) -> None:
    from starling import _core

    before, after = read_json(before_path), read_json(after_path)
    changes = validate_pair(before, after)
    if controls.digest(Path(_core.__file__)) != after["core_sha256"]:
        raise ValueError("installed core does not match after export")
    out.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(before_path, out / "before.json")
    shutil.copyfile(after_path, out / "after.json")
    sources = [Path(__file__), Path(ladder.__file__), Path(audit.__file__),
               Path(controls.__file__), ROOT / "scripts/eval_socialmem_scoped.py"]
    (out / "source_archive").mkdir()
    for path in sources:
        shutil.copyfile(path, out / "source_archive" / path.name)
    url = urlsplit(os.environ["OPENAI_BASE_URL"])
    os.environ["OPENAI_BASE_URL"] = urlunsplit(url._replace(path="/v1"))
    backbone = "gpt-5.5"
    probe_question = "Does Claudette prefer permanence? Answer YES, NO, or UNKNOWN."
    manifest = {
        "status": "running", "claim_level": "diagnostic_only", "backbone": backbone,
        "temperature": 0, "answer_max_tokens": 512, "judge_repeats": 3,
        "before_sha256": controls.digest(before_path), "after_sha256": controls.digest(after_path),
        "source_sha256": {str(p.relative_to(ROOT)): controls.digest(p) for p in sources},
        "changes": changes, "order": "alternate before/after order by cell index",
        "probe": {"item_id": "Q1_a5s1c1", "question": probe_question, "expected": "NO",
                  "basis": "Source: Permanence is what irritates me; not a benchmark item."},
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    controls.dump(out / "manifest.json", manifest)
    results = []
    try:
        for i, (old, new) in enumerate(zip(before["rows"], after["rows"], strict=True)):
            pair = [("before", old), ("after", new)]
            for phase, cell in pair if i % 2 == 0 else reversed(pair):
                identity = {"item_id": cell["item_id"], "variant": cell["variant"], "phase": phase}
                print(f"[polarity] {identity}", flush=True)
                answer = audit._chat_completion(cell["prompt"], backbone, max_tokens=512)
                if not answer.strip():
                    raise ValueError("empty answer")
                ladder.append_journal(out / "answer_calls.jsonl", {**identity, "kind": "benchmark",
                                      "prompt": cell["prompt"], "raw": answer})
                votes = []

                def sink(vote):
                    votes.append(vote)
                    ladder.append_journal(out / "judge_calls.jsonl", {**identity, **vote})

                judge = repeated_judge(audit._chat_completion, sink, 3)
                record = cell["record"]
                ok = judge(record["question"], str(record["answer"]), answer, backbone)
                result = {**identity, "response": answer, "ok": ok, "judge_calls": votes,
                          "judge_acceptances": sum(v["accepted"] for v in votes)}
                if cell["item_id"] == "Q1_a5s1c1":
                    prompt = ladder._ladder_prompt_free({"question": probe_question}, cell["block"].splitlines())
                    raw = audit._chat_completion(prompt, backbone, max_tokens=512)
                    ladder.append_journal(out / "answer_calls.jsonl", {**identity, "kind": "polarity_probe",
                                          "prompt": prompt, "raw": raw})
                    result["polarity_probe"] = {"raw": raw, "expected": "NO", "ok": raw.strip().upper() == "NO"}
                ladder.append_journal(out / "journal.jsonl", result)
                results.append(result)
                print(f"  accepted={result['judge_acceptances']}/3", flush=True)
        controls.dump(out / "results.json", {"claim_level": "diagnostic_only", "rows": results})
        manifest.update(status="complete", completed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    except Exception as exc:
        manifest.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        controls.dump(out / "manifest.json", manifest)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser("export")
    export.add_argument("--parent", type=Path, required=True)
    export.add_argument("--out", type=Path, required=True)
    export.add_argument("--phase", choices=("before", "after"), required=True)
    run = sub.add_parser("compare")
    run.add_argument("--real-run", action="store_true", required=True)
    run.add_argument("--before", type=Path, required=True)
    run.add_argument("--after", type=Path, required=True)
    run.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "export":
        export_renderings(args.parent, args.out, args.phase)
    else:
        compare(args.before, args.after, args.out)


if __name__ == "__main__":
    main()

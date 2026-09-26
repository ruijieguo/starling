"""零模型请求：按冻结 scope、数据库和逐题回执诊断结构化覆盖。"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def analyze_run(run: Path) -> dict:
    run = Path(run).resolve()
    hashes: dict[str, str] = {}

    def track(path: Path) -> Path:
        if not path.is_file():
            raise ValueError(f"missing artifact: {path.relative_to(run)}")
        hashes[str(path.relative_to(run))] = sha(path)
        return path

    def read(path: Path):
        return json.loads(track(path).read_text())

    summary = read(run / "summary.json")
    for name in ("identity.json", "config.json", "execution-plan.json", "selected-summary.json"):
        if (run / name).is_file():
            track(run / name)
    groups = summary["groups"]
    if not groups or len({g["group"] for g in groups}) != len(groups):
        raise ValueError("missing or duplicate scope")
    totals = Counter()
    scopes, all_ids = [], set()
    qa = {key: {"questions": 0, "correct": 0}
          for key in ("with_structured", "legacy_only", "no_statements")}
    predicate_totals, family_totals = Counter(), Counter()
    for group in groups:
        gid = group["group"]
        if not isinstance(gid, str) or gid in ("", ".", "..") or Path(gid).name != gid:
            raise ValueError("invalid scope path")
        base = run / "runs" / gid
        failure_artifact = base / "scope.failure.json"
        metadata = read(failure_artifact) if failure_artifact.is_file() else read(base / "scope.json")
        ingestion = read(base / "ingestion.json")
        if metadata.get("group") != gid:
            raise ValueError("scope identity mismatch")
        records = ingestion["records"]
        if not records:
            raise ValueError("scope has no input records")
        history = records[0]["history"]
        if any(row["history"] != history for row in records):
            raise ValueError("scope histories differ")
        expected = {str(t["speaker"]) for t in history}
        extraction = metadata.get("extraction", [])
        holders = [e["holder"] for e in extraction]
        if len(holders) != len(set(holders)) or set(holders) - expected:
            raise ValueError("duplicate or unexpected extraction holder")
        db_path = base / "frozen.db"
        if not db_path.is_file():
            # A terminal extraction failure has no frozen.db; network.db is
            # still the immutable request/attempt ledger for that scope.
            db_path = base / "network.db"
        wal = Path(str(db_path) + "-wal")
        if wal.exists() and wal.stat().st_size:
            raise ValueError("nonempty WAL is not a frozen database")
        track(db_path)
        db = sqlite3.connect(db_path.as_uri() + "?mode=ro&immutable=1", uri=True)
        db.row_factory = sqlite3.Row
        try:
            statements = list(db.execute("SELECT id,tenant_id,predicate,semantic_claim_json FROM statements"))
            attempts = list(db.execute("SELECT raw_output,error FROM extraction_attempt"))
        finally:
            db.close()
        if any(s["tenant_id"] != "default" for s in statements):
            raise ValueError("unexpected tenant in evaluation database")
        by_id = {s["id"]: s for s in statements}
        if len(by_id) != len(statements):
            raise ValueError("duplicate statement id")
        claims = {s["id"]: json.loads(s["semantic_claim_json"]) for s in statements
                  if s["semantic_claim_json"]}
        predicates = Counter(by_id[sid]["predicate"] for sid in claims)
        families = Counter(e.get("semantic_family", "__unknown__") for e in claims.values())
        missing_time = {
            key: sum((e.get("source_turn") or {}).get(field) is None for e in claims.values())
            for key, field in (("structured_missing_session", "session_id"),
                               ("structured_missing_turn_id", "turn_id"),
                               ("structured_missing_observed_at", "observed_at"))}
        rejection_counts = Counter()
        for e in extraction:
            rejection_counts.update(e.get("rejected_by_predicate", {}))
        scope_state = metadata.get("scope_state", "complete")
        holder_failures = metadata.get("holder_failures", [])
        scope = {
            "group": gid, "network_id": ingestion["network_id"],
            "evaluation_scope": ingestion["evaluation_scope"],
            "source_turns": len(history), "expected_holders": len(expected),
            "extracted_holders": len(holders), "missing_holders": sorted(expected - set(holders)),
            "scope_state": scope_state,
            "holder_failures": holder_failures,
            "holder_failure_count": len(holder_failures),
            "structured_scope_complete": not failure_artifact.is_file()
                and scope_state == "complete"
                and metadata.get("ingestion_mode") != "source_only"
                and set(holders) == expected
                and all(e.get("extraction_failed") is False and e.get("catalog_version")
                        for e in extraction),
            "statements": len(statements), "structured_claims": len(claims),
            "legacy_statements": len(statements) - len(claims),
            "predicates": dict(predicates), "families": dict(families), **missing_time,
            "failure_categories": dict(Counter(e.get("failure_category") or "none" for e in extraction)),
            "rejected_by_predicate": dict(rejection_counts),
            "admission_reason_details": None,
            "admission_reason_status": "not_recorded_in_scope_summary",
            "attempt_ledger_rows": len(attempts),
            "attempt_rows_with_raw_output": sum(a["raw_output"] is not None for a in attempts),
            "attempt_errors": dict(Counter(a["error"] for a in attempts if a["error"])),
        }
        # Attempt ledger rows can be per statement; never label them model calls.
        on_disk = {}
        for path in sorted((base / "questions").glob("*.json")):
            row = read(path)
            item_id = row["item_id"]
            if item_id in on_disk:
                raise ValueError("duplicate question artifact")
            on_disk[item_id] = row
        result_ids = [r["item_id"] for r in group["results"]]
        if (len(set(result_ids)) != len(result_ids) or set(result_ids) & all_ids
                or set(result_ids) != set(on_disk)):
            raise ValueError("duplicate or missing question artifact")
        all_ids.update(result_ids)
        questions, retrieved = [], Counter()
        for row in group["results"]:
            if on_disk[row["item_id"]] != row:
                raise ValueError("question receipt differs from summary")
            if row.get("terminal") is not True or type(row.get("correct")) is not bool:
                raise ValueError("question has no complete terminal verdict")
            ids = row.get("recall", {}).get("statement_ids", [])
            if len(ids) != len(set(ids)) or any(sid not in by_id for sid in ids):
                raise ValueError("question refers to missing or duplicate statements")
            structured_ids = [sid for sid in ids if sid in claims]
            retrieved.update(structured_ids)
            key = "with_structured" if structured_ids else "legacy_only" if ids else "no_statements"
            qa[key]["questions"] += 1
            qa[key]["correct"] += int(row["correct"])
            questions.append({"item_id": row["item_id"], "correct": row["correct"],
                "status": row["status"], "context_group": key,
                "structured_statement_ids": structured_ids, "statement_count": len(ids)})
        scope.update(questions=questions, question_count=len(questions),
            correct=sum(q["correct"] for q in questions),
            technical_failures=sum(q["status"] != "ok" for q in questions),
            retrieved_structured_distinct=len(retrieved),
            retrieved_structured_instances=sum(retrieved.values()))
        for key in ("source_turns", "expected_holders", "extracted_holders", "statements",
                    "structured_claims", "legacy_statements", "structured_missing_session",
                    "structured_missing_turn_id", "structured_missing_observed_at", "correct",
                    "technical_failures", "retrieved_structured_distinct", "retrieved_structured_instances"):
            totals[key] += scope[key]
        totals["questions"] += len(questions)
        totals["scopes"] += 1
        totals["complete_structured_scopes"] += int(scope["structured_scope_complete"])
        totals["partial_structured_scopes"] += int(scope_state == "partial")
        totals["holder_failures"] += len(holder_failures)
        predicate_totals.update(predicates)
        family_totals.update(families)
        scopes.append(scope)
    for name, expected_hash in hashes.items():
        if sha(run / name) != expected_hash:
            raise ValueError(f"artifact changed while reading: {name}")
    return {"schema_version": 1, "status": "offline_artifact_diagnosis", "external_requests": 0,
        "new_qa_score": None, "semantic_recall": None, "run": str(run),
        "totals": dict(totals), "predicates": dict(predicate_totals), "families": dict(family_totals),
        "qa_by_context": qa, "scopes": scopes, "input_hashes": hashes,
        "limitations": ["retrieval_groups_are_descriptive_not_causal",
                        "missing_raw_or_admission_details_cannot_be_reconstructed",
                        "ledger_rows_are_not_request_counts"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = analyze_run(args.run)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps(report["totals"], ensure_ascii=False))


if __name__ == "__main__":
    main()

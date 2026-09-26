#!/usr/bin/env python3
"""生成 R3.2 结构化信封专项的零请求配对诊断。"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sqlite3
from typing import Any


def read(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def has_duplicate_object_key(raw: str) -> bool:
    duplicate = False

    def hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        nonlocal duplicate
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                duplicate = True
            result[key] = value
        return result

    try:
        json.loads(raw, object_pairs_hook=hook)
    except json.JSONDecodeError:
        return False
    return duplicate


def flatten_results(run: pathlib.Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for group in read(run / "summary.json")["groups"]:
        for row in group["results"]:
            item = str(row["item_id"])
            if item in rows:
                raise ValueError(f"duplicate item_id: {item}")
            rows[item] = row
    return rows


def scope_diagnostics(run: pathlib.Path) -> dict[str, Any]:
    scopes: list[dict[str, Any]] = []
    extraction_status = collections.Counter()
    attempt_status = collections.Counter()
    predicates = collections.Counter()
    families = collections.Counter()
    duplicate_key_raw = 0
    raw_nonempty = 0
    attempt_count = 0
    statements = 0
    expected_holders = 0
    extracted_holders = 0
    for group in read(run / "summary.json")["groups"]:
        gid = group["group"]
        base = run / "runs" / gid
        ingestion = read(base / "ingestion.json")
        history = ingestion["records"][0]["history"]
        expected = {str(turn["speaker"]) for turn in history}
        metadata = read(base / "scope.json") if (base / "scope.json").is_file() else None
        extracted = metadata.get("extraction", []) if metadata else []
        actual = {str(row.get("holder")) for row in extracted}
        expected_holders += len(expected)
        extracted_holders += len(actual)
        categories = collections.Counter(
            row.get("failure_category") or "none" for row in extracted
        )
        scope = {
            "group": gid,
            "network_id": ingestion["network_id"],
            "questions": len(group["results"]),
            "expected_holders": len(expected),
            "extracted_holders": len(actual),
            "missing_holders": sorted(expected - actual),
            "scope_complete": metadata is not None and expected == actual and all(
                row.get("extraction_failed") is False for row in extracted
            ),
            "failure_categories": dict(categories),
        }
        scopes.append(scope)
        extraction_status.update(categories)
        db = sqlite3.connect(base / "network.db")
        try:
            attempt_count += db.execute("select count(*) from extraction_attempt").fetchone()[0]
            statements += db.execute("select count(*) from statements").fetchone()[0]
            for status, error, count in db.execute(
                "select status, coalesce(error,''), count(*) from extraction_attempt group by status,error"
            ):
                attempt_status[f"{status}:{error}"] += count
            rows = db.execute(
                "select raw_output, error from extraction_attempt where raw_output is not null"
            ).fetchall()
        finally:
            db.close()
        for raw, error in rows:
            if raw and len(raw) > 2:
                raw_nonempty += 1
                if has_duplicate_object_key(raw):
                    duplicate_key_raw += 1
        db = sqlite3.connect(base / "network.db")
        try:
            for predicate, semantic in db.execute(
                "select predicate, semantic_claim_json from statements where semantic_claim_json is not null"
            ):
                predicates[predicate] += 1
                try:
                    families[json.loads(semantic).get("semantic_family", "__unknown__")] += 1
                except json.JSONDecodeError:
                    families["__invalid__"] += 1
        finally:
            db.close()
    return {
        "scopes": scopes,
        "scope_count": len(scopes),
        "complete_scopes": sum(int(row["scope_complete"]) for row in scopes),
        "expected_holders": expected_holders,
        "extracted_holders": extracted_holders,
        "holder_coverage": extracted_holders / expected_holders if expected_holders else 0.0,
        "extraction_failure_categories": dict(extraction_status),
        "attempt_status": dict(attempt_status),
        "attempt_count": attempt_count,
        "raw_nonempty_attempts": raw_nonempty,
        "raw_with_duplicate_time_or_topic_key": duplicate_key_raw,
        "statements": statements,
        "predicates": dict(predicates),
        "families": dict(families),
    }


def paired(left: dict[str, dict[str, Any]], right: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ids = sorted(set(left) & set(right))
    transitions = collections.Counter()
    for item in ids:
        a, b = left[item], right[item]
        transitions[
            (
                a.get("status") == "ok",
                b.get("status") == "ok",
                a.get("correct") is True,
                b.get("correct") is True,
            )
        ] += 1
    both_ok = [item for item in ids if left[item].get("status") == "ok" and right[item].get("status") == "ok"]
    rescued = [item for item in ids if left[item].get("status") != "ok" and right[item].get("status") == "ok"]
    return {
        "common_questions": len(ids),
        "transitions": {"|".join(map(str, key)): value for key, value in transitions.items()},
        "both_ok_questions": len(both_ok),
        "both_ok_correct_left": sum(left[item].get("correct") is True for item in both_ok),
        "both_ok_correct_right": sum(right[item].get("correct") is True for item in both_ok),
        "rescued_questions": len(rescued),
        "rescued_correct_right": sum(right[item].get("correct") is True for item in rescued),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--r32", type=pathlib.Path, required=True)
    parser.add_argument("--r31", type=pathlib.Path, required=True)
    parser.add_argument("--r23", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()
    r32, r31, r23 = map(pathlib.Path, (args.r32, args.r31, args.r23))
    report = {
        "schema_version": 1,
        "r32": {"summary": read(r32 / "selected-summary.json")["summary"], "diagnostics": scope_diagnostics(r32)},
        "r31": {"summary": read(r31 / "selected-summary.json")["summary"]},
        "r23": {"summary": read(r23 / "selected-summary.json")["summary"]},
        "paired": {
            "r31_to_r32": paired(flatten_results(r31), flatten_results(r32)),
            "r23_to_r32": paired(flatten_results(r23), flatten_results(r32)),
        },
        "limitations": [
            "不同真实请求的模型采样并非同一 completion，配对结果只能描述观察到的转移，不能单独证明提示因果。",
            "scope 失败会使其余 holder 和题目没有结构化证据，技术完成率与成功子集准确率必须分开解释。",
            "谓词和声明数量受完成 scope 集合影响，不能跨轮直接当作语义召回率。",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "r32": report["r32"]["diagnostics"], "paired": report["paired"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""否定范围真实模型探针：固定小样本重复抽取，经原生持久化后按声明标签字面打分。

只做评测编排。抽取提示、解析、校验、提交均由 C++ 核心完成；本脚本不实现语义判断，
只对落库行的声明字段做字面匹配。使用生产默认 belief 提示，不改任何默认值，不重试，
gold 答案不进入抽取。标签在独立文件中，冻结的扩展标签及其哈希不受影响。
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import eval_ladder as ladder
import eval_socialmem_controls as controls
import eval_socialmem_extended as extended
import eval_socialmem_predicates as pred
import eval_socialmem_temporal as temporal
import run_socialmem_baseline as baseline

ROOT = Path(__file__).resolve().parents[1]
LABEL_PATH = ROOT / "tests/data/eval_socialmem_negation_scope_labels.json"
DEFAULT_MODEL = "qwen3.8-27b"
DEFAULT_NOW = "2026-10-01T00:00:00Z"
ARM = "baseline"


def sha256_text(text):
    return hashlib.sha256(text.encode()).hexdigest()


def load_labels(path=None):
    """标签必须逐条绑定源句哈希；源句或标签任一漂移都拒绝运行。"""
    labels = json.loads((path or LABEL_PATH).read_text())
    sources = {case["id"]: case for case in pred.synthetic_cases()}
    seen = set()
    for case in labels["cases"]:
        name = case["id"]
        if name in seen:
            raise ValueError(f"duplicate label id: {name}")
        seen.add(name)
        if name not in sources:
            raise ValueError(f"label for unknown source case: {name}")
        if sha256_text(sources[name]["passage"]) != case["source_sha256"]:
            raise ValueError(f"label source drifted: {name}")
        if not case["targets"]:
            raise ValueError(f"label without targets: {name}")
    return labels, sources


def covers(target, row):
    value = row.get("object_value")
    return (row.get("subject_id") == target["actor"] and row.get("predicate") == target["predicate"]
            and str(row.get("polarity", "")).upper() == target["polarity"]
            and str(row.get("modality", "")).upper() == target["modality"]
            and isinstance(value, str)
            and all(any(fragment.casefold() in value.casefold() for fragment in alternatives)
                    for alternatives in target["object_all"]))


def score_rep(targets, rows, persisted):
    edges = [[index for index, row in enumerate(rows) if persisted and covers(target, row)]
             for target in targets]
    # 复用冻结打分器的一对一最大匹配：一条落库行至多覆盖一个目标。
    assignment = extended._maximum_matching(edges)
    return {"targets": len(targets), "covered": len(assignment), "covered_targets": sorted(assignment),
            "unmatched_rows": len(rows) - len(assignment), "technical_failed": not persisted}


def build_llm(core, model, *, json_object=False):
    """显式 DashScope 环境；密钥只在 from_env 快照，不写入任何归档。"""
    if not os.environ.get("DASHSCOPE_API_KEY"):
        raise ValueError("DASHSCOPE_API_KEY is required; provider fallback is not allowed")
    endpoint = os.environ.get("DASHSCOPE_BASE_URL", "")
    url = urlsplit(endpoint)
    if (url.scheme != "https" or not url.hostname or url.username or url.password
            or url.query or url.fragment or endpoint.endswith("/")):
        raise ValueError("DASHSCOPE_BASE_URL must be an explicit HTTPS API base without credentials or query")
    with baseline._provider_environment("DASHSCOPE_API_KEY", endpoint):
        cfg = core.OpenAIAdapterConfig.from_env()
        cfg.model = model
        cfg.max_tokens, cfg.timeout_ms, cfg.max_retries = 8192, 120000, 0
        cfg.json_object_output, cfg.enable_thinking = json_object, False
        llm = core.OpenAIAdapter(cfg)
    return llm, {"endpoint": cfg.base_url, "model": cfg.model, "temperature": 0,
                 "max_tokens": cfg.max_tokens, "timeout_ms": cfg.timeout_ms,
                 "max_retries": cfg.max_retries, "enable_thinking": False,
                 "json_object_output": json_object}


def evaluate(core, llm, source, case, template, out, now, repeat):
    prompt = pred.render_prompts({"belief": template}, source["holder"], source["passage"])["belief"]
    response = llm.extract(prompt, core.Extractor.compute_prompt_input_hash(prompt))
    record = {"id": case["id"], "repeat": repeat, "prompt_sha256": sha256_text(prompt),
              "transport_ok": bool(response.ok), "error": response.error,
              "finish_reason": response.finish_reason, "total_tokens": response.total_tokens,
              "raw": response.raw_xml, "rows": [], "persisted": False, "persist_error": ""}
    if response.ok:
        database = out / "databases" / f"{case['id']}_{repeat}.db"
        try:
            with pred.archived_runtime(database) as (rt, working):
                record["receipt"] = pred.persist(core, rt.adapter, source["holder"], source["passage"],
                                                 {"belief": template}, {"belief": response.raw_xml}, ARM, now)
                rows = temporal.statement_rows(working)
            record.update(persisted=True, database=str(database.relative_to(out)),
                          database_sha256=controls.frozen_database_hash(database),
                          rows=[{key: row[key] for key in pred.SEMANTIC_FIELDS} for row in rows])
        except (ValueError, RuntimeError) as exc:
            record["persist_error"] = f"{type(exc).__name__}: {exc}"
    record["score"] = score_rep(case["targets"], record["rows"], record["persisted"])
    ladder.append_journal(out / "runs.jsonl", record)
    return record


def summarize(labels, records):
    cases = {}
    for case in labels["cases"]:
        mine = [r for r in records if r["id"] == case["id"]]
        targets = [{"actor": t["actor"], "polarity": t["polarity"], "object_all": t["object_all"],
                    "reps": len(mine), "valid": sum(r["persisted"] for r in mine),
                    "covered": sum(index in r["score"]["covered_targets"] for r in mine)}
                   for index, t in enumerate(case["targets"])]
        shapes = {json.dumps([(x["predicate"], x["object_value"], x["polarity"], x["modality"])
                              for x in r["rows"]], ensure_ascii=False) for r in mine}
        cases[case["id"]] = {"repeats": len(mine), "technical_failures": sum(not r["persisted"] for r in mine),
                             "unmatched_rows": sum(r["score"]["unmatched_rows"] for r in mine),
                             "distinct_row_sets": len(shapes), "targets": targets}
    flat = [t for c in cases.values() for t in c["targets"]]
    return {"cases": cases, "strict": {"targets": sum(t["reps"] for t in flat),
                                       "valid": sum(t["valid"] for t in flat),
                                       "covered": sum(t["covered"] for t in flat)}}


def run(core, llm, transport, out, *, repeats=5, now=DEFAULT_NOW, labels_path=None):
    from starling.extractor.prompts import EXTRACTION_PROMPT

    if repeats < 1:
        raise ValueError("repeats must be positive")
    now = ladder.normalize_eval_time(now)
    labels, sources = load_labels(labels_path)
    out.mkdir(parents=True, exist_ok=False)
    (out / "databases").mkdir()
    manifest = {"status": "running", "claim_level": "negation_scope_probe",
                "started_at": datetime.now(timezone.utc).isoformat(), "query_time": now,
                "transport": transport, "repeats": repeats, "arm": ARM,
                "prompt": "EXTRACTION_PROMPT, production default belief prompt, unmodified",
                "labels_sha256": controls.digest(labels_path or LABEL_PATH),
                "label_origin": labels["label_origin"],
                "core_sha256": controls.digest(Path(core.__file__)),
                "expected_requests": repeats * len(labels["cases"]),
                "protocol": "Repeat-major, case-minor order. One extraction per cell, no retries, "
                            "no gold in the prompt. Technical failures stay in the strict denominator."}
    controls.dump(out / "manifest.json", manifest)
    records = []
    try:
        for repeat in range(repeats):
            for case in labels["cases"]:
                records.append(evaluate(core, llm, sources[case["id"]], case, EXTRACTION_PROMPT,
                                        out, now, repeat))
        summary = summarize(labels, records)
        controls.dump(out / "results.json", summary)
        manifest.update(status="complete", completed_at=datetime.now(timezone.utc).isoformat())
    except Exception as exc:
        manifest.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        controls.dump(out / "manifest.json", manifest)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--now-iso", default=DEFAULT_NOW)
    args = parser.parse_args(argv)
    from starling import _core

    llm, transport = build_llm(_core, args.model)
    print(json.dumps(run(_core, llm, transport, args.out, repeats=args.repeats, now=args.now_iso),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

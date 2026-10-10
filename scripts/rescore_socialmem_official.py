#!/usr/bin/env python3
"""WP0.2:九月已存的开放题回答按官方口径重判(只付裁判费,不重新作答)。

读逐题文件(每题一个 json,含回答回执与严格裁判结论),取出回答正文,用官方 0 到 1 分项裁判重判,
逐行追加到输出文件、按题号续跑,汇总严格口径与官方口径的差。

只重判开放题:九月选择题的回答是 0 起下标整数,官方字母口径不适用,选择题只保留严格口径读数。
状态不是 ok 或回答为空的题跳过并计数;裁判请求失败的题不写行(续跑会重试),不记 0 分。
本脚本只读逐题目录,输出文件必须在该目录之外。真跑需要显式 --real-run。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import eval_official_protocol as proto  # noqa: E402


def answer_text(question: dict) -> str:
    """回答正文:优先顶层 raw_completion,其次回执里的 raw_completion,最后从 HTTP 回执取。"""
    answer = question.get("answer") or {}
    text = answer.get("raw_completion")
    if isinstance(text, str) and text.strip():
        return text
    response = answer.get("response") or {}
    text = response.get("raw_completion")
    if isinstance(text, str) and text.strip():
        return text
    for attempt in reversed(response.get("http_attempts") or []):
        body = attempt.get("response_body")
        if not isinstance(body, str):
            continue
        try:
            content = json.loads(body)["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            continue
        if isinstance(content, str) and content.strip():
            return content
    return ""


def iter_question_files(root) -> list[Path]:
    return sorted(Path(root).rglob("questions/*.json"))


def load_corpus(path) -> dict[str, dict]:
    records: dict[str, dict] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            records[record["item_id"]] = record
    return records


def _read_rows(path: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue                              # 坏行跳过,不让一行损坏毁掉续跑
        if isinstance(row.get("item_id"), str):
            rows[row["item_id"]] = row
    return rows


def _append(path: Path, row: dict) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def summarize(rows: dict[str, dict]) -> dict:
    def block(items: list[dict]) -> dict:
        n = len(items)
        return {"n": n,
                "strict_correct": sum(1 for r in items if r["strict_correct"]),
                "official_correct": sum(1 for r in items if r["official_correct"]),
                "mean_score": (sum(r["official_score"] for r in items) / n) if n else None}

    values = list(rows.values())
    by_type: dict[str, list[dict]] = {}
    for row in values:
        by_type.setdefault(str(row.get("query_type") or "unknown"), []).append(row)
    out = block(values)
    out["by_query_type"] = {qt: block(items) for qt, items in sorted(by_type.items())}
    out["judge_status"] = {s: sum(1 for r in values if r.get("judge_status") == s)
                           for s in sorted({r.get("judge_status") for r in values if r.get("judge_status")})}
    return out


def rescore(root, corpus: dict[str, dict], out, judge, *, backbone: str = "") -> dict:
    """judge(question, reference, candidate, backbone) -> {score, rationale, raw, status}。"""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.touch(exist_ok=True)
    done = _read_rows(out)
    counts = {"already_done": 0, "skipped_missing_record": 0, "skipped_multiple_choice": 0,
              "skipped_not_ok": 0, "skipped_unreadable": 0, "judge_errors": 0}
    for path in iter_question_files(root):
        try:
            question = json.loads(path.read_text(encoding="utf-8"))
            item_id = question["item_id"]
        except (OSError, ValueError, KeyError, TypeError):
            counts["skipped_unreadable"] += 1
            continue
        if item_id in done:
            counts["already_done"] += 1
            continue
        record = corpus.get(item_id)
        if record is None:
            counts["skipped_missing_record"] += 1
            continue
        if record.get("answer_format", "multiple_choice") == "multiple_choice":
            counts["skipped_multiple_choice"] += 1
            continue
        candidate = answer_text(question)
        if question.get("status") != "ok" or not candidate.strip():
            counts["skipped_not_ok"] += 1
            continue
        try:
            result = judge(record["question"], str(record["answer"]), candidate, backbone)
        except Exception as exc:                  # noqa: BLE001 — 单题失败不毁整轮,下次续跑重试
            counts["judge_errors"] += 1
            print(f"  ! {item_id} judge failed: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
            continue
        row = {"item_id": item_id, "query_type": record.get("query_type"),
               "strict_correct": bool(question.get("correct")),
               "official_score": result["score"],
               "official_correct": proto.official_is_correct(result["score"]),
               "judge_status": result["status"], "judge_rationale": result["rationale"],
               "judge_raw": result["raw"]}
        _append(out, row)
        done[item_id] = row
    return {**summarize(_read_rows(out)), **counts}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="九月已存开放题回答的官方口径重判(WP0.2)。")
    p.add_argument("--root", type=Path, required=True, help="含 questions/*.json 的逐题目录(只读)")
    p.add_argument("--corpus", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True, help="逐行输出 JSONL,必须在 --root 之外")
    p.add_argument("--prompts", type=Path, required=True)
    p.add_argument("--prompts-sha256", required=True)
    p.add_argument("--judge-model", required=True)
    p.add_argument("--summary", type=Path, default=None)
    p.add_argument("--real-run", action="store_true", help="显式行使真跑(发裁判请求,花 API)")
    args = p.parse_args(argv)
    if not args.real_run:
        print("ERROR: 未指定 --real-run;本脚本只做真实裁判请求,拒绝误触网络。", file=sys.stderr)
        return 1
    root = args.root.resolve()
    if root == args.out.resolve().parent or root in args.out.resolve().parents:
        print("ERROR: --out 必须在 --root 之外(逐题目录只读)。", file=sys.stderr)
        return 1
    prompts = proto.load_official_prompts(args.prompts, args.prompts_sha256)
    import eval_judge_audit as audit_mod
    judge = proto.make_official_judge_fn(audit_mod._chat_completion, prompts)
    summary = rescore(root, load_corpus(args.corpus), args.out, judge, backbone=args.judge_model)
    text = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.summary is not None:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

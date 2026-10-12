#!/usr/bin/env python3
"""WP2.B 登记修订五:附加声明侧栏的零请求后处理。只读 journal,不发请求,不设读法。

统计 st_hyb 每题的声明条数(分题型),并只在声明条数大于 0 的题上单列 st_hyb 减 st_ctrl 的配对差。
Q2+Q6 选择题里声明条数大于 0 的题不到四分之一时标记「侧栏几乎为空」。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import eval_socialmem_source_answer as ans  # noqa: E402

EMPTY_SHARE_LIMIT = 0.25


def _is_mc(rec: dict) -> bool:
    return rec.get("answer_format", "multiple_choice") == "multiple_choice"


def _mean_pair(ids: list[str], ctrl: dict, hyb: dict):
    if not ids:
        return None
    c = sum(float(ctrl[i]["score"]) for i in ids) / len(ids)
    h = sum(float(hyb[i]["score"]) for i in ids) / len(ids)
    return {"n": len(ids), "ctrl": c, "hyb": h, "delta": h - c}


def sidecar_stats(records: list[dict], ctrl: dict, hyb: dict) -> dict:
    by_type: dict[str, dict] = {}
    for rec in records:
        row = hyb.get(rec["item_id"])
        if row is None:
            continue
        cell = by_type.setdefault(rec["query_type"], {"questions": 0, "with_statements": 0, "statements_total": 0})
        count = int(row.get("statement_count") or 0)
        cell["questions"] += 1
        cell["with_statements"] += int(count > 0)
        cell["statements_total"] += count
    mc_ids = [r["item_id"] for r in records if r["query_type"] in ("Q2", "Q6") and _is_mc(r) and r["item_id"] in hyb]
    with_statements = [i for i in mc_ids if int(hyb[i].get("statement_count") or 0) > 0]
    share = (len(with_statements) / len(mc_ids)) if mc_ids else 0.0
    mc_summary = {"questions": len(mc_ids), "with_statements": len(with_statements), "share": share,
                  "sidecar_mostly_empty": share < EMPTY_SHARE_LIMIT - 1e-9}

    def nonempty(i: str) -> bool:
        return int(hyb[i].get("statement_count") or 0) > 0 and i in ctrl

    q2q6 = [i for i in with_statements if nonempty(i)]
    q4 = [r["item_id"] for r in records if r["query_type"] == "Q4" and _is_mc(r) and r["item_id"] in hyb and nonempty(r["item_id"])]
    opened = [r["item_id"] for r in records if r["query_type"] in ans.PRIMARY_TYPES and not _is_mc(r)
              and r["item_id"] in hyb and nonempty(r["item_id"])
              and ctrl[r["item_id"]].get("judge_status") not in ans.BAD_JUDGE_STATUSES
              and hyb[r["item_id"]].get("judge_status") not in ans.BAD_JUDGE_STATUSES]
    paired = {"mc_q2q6": _mean_pair(q2q6, ctrl, hyb), "mc_q4": _mean_pair(q4, ctrl, hyb),
              "open_q5q9": _mean_pair(opened, ctrl, hyb)}
    return {"by_type": by_type, "mc_q2q6": mc_summary, "paired": paired}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, default=Path("build/socialmem_pilot110_corpus.jsonl"))
    parser.add_argument("--result", type=Path, default=None)
    args = parser.parse_args(argv)
    journals = {arm: args.out / f"{arm}_journal.jsonl" for arm in ("st_ctrl", "st_hyb")}
    missing = [f"{arm}: {path}" for arm, path in journals.items() if not path.exists()]
    if missing:
        print("ERROR: 缺 journal: " + "；".join(missing), file=sys.stderr)
        return 1
    records = ans._load_corpus(args.corpus)
    stats = sidecar_stats(records, ans.load_rows(journals["st_ctrl"], "st_ctrl"), ans.load_rows(journals["st_hyb"], "st_hyb"))
    text = json.dumps(stats, ensure_ascii=False, indent=2)
    if args.result is not None:
        args.result.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""开发集单变量对照的离线统计及评分审阅材料；不调用模型、不改变分数。"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random
import re
import statistics

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / "build/socialmem_20260917_baseline_recovered"
DIAGNOSIS = ROOT / "build/socialmem_20260917_baseline_diagnosis"


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def receipts(folder):
    return [read(p) for p in folder.glob("runs/*/questions/*.json")]


def paired_outcomes(records, parent, candidate):
    ids = {r["item_id"] for r in records}
    if len(ids) != len(records) or not ids:
        raise ValueError("paired records missing or duplicated")
    maps = []
    for rows in [parent, candidate]:
        if len(rows) != len(ids) or {r["item_id"] for r in rows} != ids:
            raise ValueError("paired receipts missing, duplicated or outside selected set")
        if any(type(r["correct"]) is not bool for r in rows):
            raise ValueError("paired correctness must be boolean")
        maps.append({r["item_id"]: r for r in rows})
    old, new = maps
    nets = defaultdict(lambda: [0, 0])
    for r in records:
        pair = nets[r["source"]["network_id"]]
        pair[0] += int(new[r["item_id"]]["correct"]) - int(old[r["item_id"]]["correct"])
        pair[1] += 1
    clusters = [nets[k] for k in sorted(nets)]
    rng = random.Random(20260917)
    deltas = []
    for _ in range(5000):
        draw = [rng.choice(clusters) for _ in clusters]
        deltas.append(sum(v[0] for v in draw) / sum(v[1] for v in draw))
    deltas.sort()
    previous = sum(x["correct"] for x in parent)
    current = sum(x["correct"] for x in candidate)
    return {"n": len(ids), "parent_correct": previous, "candidate_correct": current,
            "parent_accuracy": previous / len(ids), "candidate_accuracy": current / len(ids),
            "delta": (current - previous) / len(ids),
            "new_correct": sum(not old[i]["correct"] and new[i]["correct"] for i in ids),
            "regressed": sum(old[i]["correct"] and not new[i]["correct"] for i in ids),
            "networks": len(clusters), "network_bootstrap_delta_95ci": [deltas[124], deltas[4874]],
            "parent_status": dict(Counter(r["status"] for r in parent)),
            "candidate_status": dict(Counter(r["status"] for r in candidate))}


def distribution(values):
    xs = sorted(values)
    if not xs:
        return None
    def q(p):
        pos = p * (len(xs) - 1)
        i = int(pos)
        return xs[i] + (xs[min(i + 1, len(xs) - 1)] - xs[i]) * (pos - i)
    return {"n": len(xs), "sum": sum(xs), "median": q(.5), "p95": q(.95),
            "max": xs[-1], "mean": statistics.mean(xs)}


def resources(rows):
    result = {"actual_http": sum(r["native_attempt_count"] for r in rows),
              "embedding_http": sum(r["embedding_request_delta"] for r in rows),
              "contexts": distribution([r["recall"]["context_bytes"] for r in rows]),
              "sources": distribution([r["recall"]["source_count"] for r in rows]),
              "idk_phrase": sum(bool(re.search(r"\bi (?:do not|don't|don’t) know\b", r.get("answer", {}).get("raw_xml", ""), re.I)) for r in rows)}
    for phase in ["answer", "judge"]:
        responses = [r[phase]["response"] for r in rows if phase in r]
        result[phase] = {"success": sum(bool(r.get("ok")) for r in responses),
                         "recorded_responses": len(responses),
                         "finish_reasons": dict(Counter(r.get("finish_reason", "") for r in responses)),
                         "completion_distribution": distribution([r["completion_tokens"] for r in responses]),
                         "prompt_tokens": sum(r["prompt_tokens"] for r in responses),
                         "completion_tokens": sum(r["completion_tokens"] for r in responses),
                         "total_tokens": sum(r["total_tokens"] for r in responses),
                         "seconds": distribution([r["stages"][phase]["seconds"] for r in rows if phase in r["stages"]])}
    return result


def development():
    records = [json.loads(s) for s in (PARENT / "corpus.jsonl").read_text().splitlines()]
    dev = set(read(PARENT / "network-split.json")["development_networks"])
    selected = [r for r in records if r["source"]["network_id"] in dev]
    assert len(selected) == 733
    return selected


def analyze(work):
    records = development()
    ids = {r["item_id"] for r in records}
    parent = [x for x in receipts(PARENT) if x["item_id"] in ids]
    candidate = receipts(work)
    report = {"overall": paired_outcomes(records, parent, candidate),
              "limits": "开发集单次配对；不是全量成绩；区间不包含模型与裁判复跑波动；不改原协议分数"}
    old = {r["item_id"]: r for r in parent}
    new = {r["item_id"]: r for r in candidate}
    for key in ["answer_format", "query_type"]:
        report[key] = {}
        for value in sorted({r[key] for r in records}):
            rs = [r for r in records if r[key] == value]
            report[key][value] = paired_outcomes(rs, [old[r["item_id"]] for r in rs], [new[r["item_id"]] for r in rs])
    report["by_network"] = {}
    for network in sorted({r["source"]["network_id"] for r in records}):
        rs = [r for r in records if r["source"]["network_id"] == network]
        report["by_network"][network] = {"n": len(rs), "parent_correct": sum(old[r["item_id"]]["correct"] for r in rs), "candidate_correct": sum(new[r["item_id"]]["correct"] for r in rs)}
    report["resources"] = {"parent": resources(parent), "candidate": resources(candidate)}
    expected = {r["item_id"]: r for r in read(ROOT / "build/socialmem_k30_controlled_checks/native-preflight.json")["rows"]}
    transitions = defaultdict(lambda: {"n": 0, "new_correct": 0, "regressed": 0, "parent_correct": 0, "candidate_correct": 0})
    detail = []
    den = old_hits = new_hits = 0
    for r in records:
        key = r["item_id"]
        recall = new[key]["recall"]
        assert hashlib.sha256(recall["block"].encode()).hexdigest() == expected[key]["block_sha256"], key
        assert recall["source_refs"] == expected[key]["source_refs"], key
        gold = {a["turn_id"] for a in r["source"]["evidence_anchors"]}
        before = len(gold & {x["turn_id"] for x in old[key]["recall"]["source_refs"]})
        after = len(gold & {x["turn_id"] for x in recall["source_refs"]})
        coverage = lambda n: "all" if n == len(gold) else "partial" if n else "none"
        bucket = transitions[coverage(before) + "->" + coverage(after)]
        bucket["n"] += 1
        bucket["new_correct"] += not old[key]["correct"] and new[key]["correct"]
        bucket["regressed"] += old[key]["correct"] and not new[key]["correct"]
        bucket["parent_correct"] += old[key]["correct"]
        bucket["candidate_correct"] += new[key]["correct"]
        den += len(gold)
        old_hits += before
        new_hits += after
        detail.append({"item_id": key, "format": r["answer_format"], "query_type": r["query_type"],
                       "parent_correct": old[key]["correct"], "candidate_correct": new[key]["correct"],
                       "old_hits": before, "new_hits": after, "anchor_count": len(gold)})
    report["anchor_recall"] = {"denominator": den, "parent_hits": old_hits, "candidate_hits": new_hits,
                               "parent_recall": old_hits / den, "candidate_recall": new_hits / den,
                               "coverage_transitions": dict(transitions)}
    report["all_contexts_match_native_preflight"] = len(detail)
    write(work / "paired-analysis.json", report)
    write(work / "paired-details.json", detail)
    return report


def audit(work):
    folder = work / "audit"
    folder.mkdir(exist_ok=False)
    blind, reference = folder / "blind", folder / "reference-review"
    blind.mkdir()
    reference.mkdir()
    free = [r for r in development() if r["answer_format"] != "multiple_choice"]
    free.sort(key=lambda r: hashlib.sha256(("judge-audit-20260917|" + r["item_id"]).encode()).hexdigest())
    chosen = free[:60]
    selected_ids = {r["item_id"] for r in chosen}
    originals = {x["item_id"]: x for x in receipts(PARENT) if x["item_id"] in selected_ids}
    mapping = []
    for i, r in enumerate(chosen, 1):
        key = f"audit-{i:02d}"
        x = originals[r["item_id"]]
        body = f"# {key} 第一阶段来源审阅\n\n问题：{r['question']}\n\n候选：{x['answer']['raw_xml']}\n\n## 候选实际获得的上下文\n\n{x['recall']['block']}\n\n## 允许范围的完整来源（用于核验，不是候选实际输入）\n\n"
        body += "\n".join(json.dumps(t, ensure_ascii=False) for t in r["history"])
        body += "\n\n## 待独立审阅\n\n- 候选核心结论是否有来源支持？\n- 是否把不同主体、会话或事件混接？\n- 问题要求的必要要点是否遗漏？\n- 是否存在矛盾、过度确定或有据附加事实？\n- 请记录结论与对应话轮，再打开第二阶段参考材料。\n"
        (blind / f"{key}.md").write_text(body)
        (reference / f"{key}.md").write_text(f"# {key} 第二阶段参考复核\n\n参考答案：{r['answer']}\n\n公开锚点：\n{json.dumps(r['source']['evidence_anchors'], ensure_ascii=False, indent=2)}\n\n请复核参考是否穷尽、歧义或与原文冲突；不因参考未写某细节即断言无依据。\n")
        mapping.append({"audit_id": key, "item_id": r["item_id"], "format": r["answer_format"],
                        "network": r["source"]["network_id"], "original_correct": x["correct"],
                        "original_status": x["status"]})
    write(folder / "selection-and-original-labels.json", {"method": "581道开发自由题按固定SHA排序取60；不按分数选样", "seed": "judge-audit-20260917", "review_status": "待独立审阅；不是校正评分", "items": mapping})
    cases = read(DIAGNOSIS / "case-audit.json")["cases"]
    issue_ids = {"Q1_51789817", "Q2_a4b5c6d70c", "Q6_b3c50065", "Q4_a4b5c6d70f", "Q7_e6f7a8ba", "Q5_b3c50072"}
    write(folder / "known-issues.json", {"source": "上一轮开发机制样本；不代表缺陷总体比例", "original_score_changed": False,
                                          "issues": [c for c in cases if c["item_id"] in issue_ids]})
    (folder / "README.md").write_text("# 独立评分审阅准备包\n\n60题来自冻结开发集，选样不依据判分。先审阅blind目录，再审阅reference-review；selection-and-original-labels.json供汇总者保管，含原判分。候选均来自原k10 baseline，未按本轮k30结果选样。\n\n当前仅完成材料准备，没有独立审阅结论、误拒率或校正分数。known-issues.json记录已知案例及证据强度，不进入主评分。\n")
    return {"cases": len(mapping), "development_only": True, "review_status": "pending_independent_review"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=["audit", "analyze"])
    p.add_argument("--work", type=Path, required=True)
    args = p.parse_args()
    result = audit(args.work) if args.mode == "audit" else analyze(args.work)
    print(json.dumps(result if args.mode == "audit" else result["overall"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

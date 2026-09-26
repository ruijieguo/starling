#!/usr/bin/env python3
"""生成 R1/B 有界计划；真实 HTTP worker 由调用方显式逐样本执行。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval_socialmem_r1b import Budget, capability_gate, schedule_samples


def build_plan(capabilities, cases, *, repetitions=2):
    """在能力门槛和 48 请求预算内生成可审计计划。"""
    ready = capability_gate(capabilities)
    budget = Budget()
    probe_count = sum(int(capabilities.get(a, {}).get("request_count", 0))
                      for a in ("D0", "D1"))
    budget.consume("probe", probe_count)
    samples = schedule_samples(cases, repetitions=repetitions,
                                capabilities=capabilities)
    if not ready:
        return {"status": "blocked_capability", "schedule": [],
                "budget": budget.snapshot()}
    budget.consume("extract", len(samples))
    # admission is a maximum reservation; worker consumes one only if C++ emits a request.
    return {"status": "ready", "schedule": samples,
            "budget": budget.snapshot(), "admission_max": len(samples)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capabilities", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.out.exists():
        raise ValueError(f"output already exists: {args.out}")
    capabilities = json.loads(args.capabilities.read_text())
    cases = json.loads(args.cases.read_text())
    plan = build_plan(capabilities, cases)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()

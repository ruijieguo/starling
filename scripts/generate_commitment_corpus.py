#!/usr/bin/env python3
"""Deterministically generate the 100-item commitment eval corpus (NO LLM)."""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path

# 固定分布(合计 100): 30 fulfill + 25 deadline_break + 20 chronic_withdraw + 15 withdraw + 10 active_pending
_PLAN = (["fulfill"]*30 + ["deadline_break"]*25 + ["chronic_withdraw"]*20
         + ["withdraw"]*15 + ["active_pending"]*10)

def _base_times(i: int):
    day = 1 + (i % 27)
    obs = f"2026-06-{day:02d}T08:00:00Z"
    deadline = f"2026-06-{day:02d}T12:00:00Z"
    return obs, deadline

def build_scenario(i: int, category: str) -> dict:
    sid = f"cm-{i:03d}"
    cstmt = f"{sid}-c"
    obs, deadline = _base_times(i)
    commit = {"stmt_id": cstmt, "holder": "alice", "subject": "bob",
              "object": f"task-{i}", "deadline": deadline, "observed_at": obs}
    day = obs[:10]
    if category == "fulfill":
        actions = [{"turn":0,"op":"tick","now":f"{day}T09:00:00Z"},
                   {"turn":1,"op":"fulfill","now":f"{day}T10:00:00Z"}]
        expected = {"final_state":"FULFILLED","detect_by_turn":1}
    elif category == "deadline_break":
        actions = [{"turn":0,"op":"tick","now":f"{day}T11:00:00Z"},
                   {"turn":1,"op":"expire","now":f"{day}T13:00:00Z"}]
        expected = {"final_state":"BROKEN","detect_by_turn":1}
    elif category == "chronic_withdraw":
        actions = [{"turn":0,"op":"expire","now":f"{day}T13:00:00Z"},
                   {"turn":1,"op":"expire","now":f"{day}T14:00:00Z"},
                   {"turn":2,"op":"expire","now":f"{day}T15:00:00Z"}]
        expected = {"final_state":"WITHDRAWN","detect_by_turn":2}
    elif category == "withdraw":
        actions = [{"turn":0,"op":"tick","now":f"{day}T09:00:00Z"},
                   {"turn":1,"op":"withdraw","now":f"{day}T10:00:00Z"}]
        expected = {"final_state":"WITHDRAWN","detect_by_turn":1}
    else:  # active_pending
        actions = [{"turn":0,"op":"tick","now":f"{day}T09:00:00Z"}]
        expected = {"final_state":"ACTIVE","detect_by_turn":0}
    return {"scenario_id": sid, "category": category, "commit": commit,
            "actions": actions, "expected": expected}

def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Generate commitment eval corpus (deterministic, no LLM).")
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args(argv)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w") as f:
        for i, cat in enumerate(_PLAN):
            f.write(json.dumps(build_scenario(i, cat), ensure_ascii=False) + "\n")
            f.flush(); os.fsync(f.fileno())
    print(f"Wrote {len(_PLAN)} scenarios to {args.out}", file=sys.stderr)
    return 0

if __name__ == "__main__":
    sys.exit(main())

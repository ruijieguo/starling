#!/usr/bin/env python3
"""Deterministically generate the 100-item commitment eval corpus (NO LLM)."""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path

# 固定分布(合计 100): 30 fulfill + 25 deadline_break + 20 renegotiate + 15 withdraw + 10 active_pending
#
# NOTE on the `renegotiate` category (was `chronic_withdraw`): the real engine
# guards on_deadline_expired against re-expiring a non-ACTIVE commitment, so 3×
# expire on one stmt ends at BROKEN (broken_count=1), never WITHDRAWN. Chronic
# auto-WITHDRAWN requires broken_count>=3 on an ACTIVE row, which means breaking
# AND renegotiating back to ACTIVE three times — but the renegotiation chain caps
# at 3 (kMaxRenegotiationChain), so the path is blocked before the 4th expire can
# fire the auto-withdraw. That transition is therefore UNREACHABLE through the
# public engine API (the C++ TC-A2-001 only reaches it by forcing the row back to
# ACTIVE with raw SQL between expires — not a legitimate engine operation). We
# instead exercise a real, deterministic renegotiation transition: expire→BROKEN
# then renegotiate onto a fresh statement, leaving the tracked (old) stmt
# RENEGOTIATED.
_PLAN = (["fulfill"]*30 + ["deadline_break"]*25 + ["renegotiate"]*20
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
    elif category == "renegotiate":
        # expire → BROKEN, then renegotiate onto a fresh statement; the tracked
        # (old) commitment lands in RENEGOTIATED. new_stmt_id is seeded by the
        # harness before the renegotiate call.
        actions = [{"turn":0,"op":"expire","now":f"{day}T13:00:00Z"},
                   {"turn":1,"op":"renegotiate","new_stmt_id":f"{cstmt}-r",
                    "now":f"{day}T13:30:00Z"}]
        expected = {"final_state":"RENEGOTIATED","detect_by_turn":1}
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

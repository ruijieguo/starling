#!/usr/bin/env python3
"""Gated real-LLM extraction smoke test (needs OPENAI_API_KEY; not in CI).

Builds a real Memory with a real OpenAI-compatible LLM and asserts remember()
extracts >=1 statement from real text — the end-to-end path the dashboard QA
found broken (stub-prompt extractor yielded 0). Run e.g.:

  OPENAI_BASE_URL=$DASHSCOPE_BASE_URL OPENAI_API_KEY=$DASHSCOPE_API_KEY \\
    python scripts/eval_extractor_smoke.py --model deepseek-v4-flash
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="deepseek-v4-flash")
    ap.add_argument("--text", default="Alice: I believe Bob is responsible for auth.")
    args = ap.parse_args()
    if not os.environ.get("OPENAI_API_KEY"):
        print("SKIP: OPENAI_API_KEY not set", file=sys.stderr)
        return 0
    from starling.memory import Memory, make_openai_llm
    fd, db = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        mem = Memory.open(db, agent="self", tenant_id="default",
                          llm=make_openai_llm(model=args.model))
        r = mem.remember(args.text)
        n = len(r.statement_ids)
        print(f"remember outcome={r.outcome} statements={n}")
        if n >= 1:
            print("PASS — real-LLM extraction produced statements")
            return 0
        print("BLOCKED — real-LLM extraction produced 0 statements")
        return 1
    finally:
        for path in (db, db + "-wal", db + "-shm"):
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass


if __name__ == "__main__":
    sys.exit(main())

"""P3.c scale-baseline harness — offline (FakeLLM) load test + baseline report.

Seeds the memory machinery to scale, measures the maintenance tick (per-stage)
and retrieval latency, and emits a baseline report. Application-layer tooling:
seeds + measures through the public Memory API; adds no core semantics. See
docs/superpowers/specs/2026-07-01-p3-c-scale-baseline-harness-design.md.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

from starling import Memory, make_stub_llm


def open_memory(db_path: str):
    """Open an offline Memory over db_path; return (mem, fake_llm).

    The FakeLLMAdapter is returned so the caller can set a unique canned
    response before each remember (the adapter ignores the prompt).
    """
    fake = make_stub_llm(default_response=unique_statement_json(0, 1))
    mem = Memory.open(db_path, agent="self", tenant_id="default", llm=fake)
    return mem, fake


def unique_statement_json(idx: int, cognizers: int) -> str:
    """A canned extraction response (JSON array of ONE statement).

    holder=self (the agent owns it — the querier that can retrieve it);
    subject=cog-{idx % cognizers} is the COGNIZER the fact is ABOUT (decision A:
    cognizers are subjects, not holders); object=obj_{idx} is unique per idx.
    """
    return (
        '[{"holder":"self","holder_perspective":"FIRST_PERSON",'
        f'"subject":"cog-{idx % cognizers}","predicate":"pred_{idx % 131}",'
        f'"object":"obj_{idx}","modality":"BELIEVES","polarity":"POS",'
        '"nesting_depth":0}]'
    )


def run_seed(mem, fake, *, cognizers: int, statements: int,
             rng: random.Random) -> dict:
    """Seed `statements` statements under holder=self, spanning N cognizer-subjects."""
    start = time.perf_counter()
    seeded = 0
    for idx in range(statements):
        fake.set_default_response(unique_statement_json(idx, cognizers), True, "")
        # holder defaults to the agent ("self") — the querier that can retrieve
        # these (decision A). Distinct payload → distinct engram (no dedup).
        mem.remember(f"seed statement {idx} topic {rng.randint(0, 1_000_000)}",
                     now="2026-07-01T00:00:00Z")
        seeded += 1
    elapsed = time.perf_counter() - start
    return {
        "seeded": seeded,
        "elapsed_s": round(elapsed, 4),
        "throughput_per_s": round(seeded / elapsed, 2) if elapsed > 0 else 0.0,
    }


def _percentile(sorted_vals: list[float], pct: float) -> float:
    """Nearest-rank percentile (pct in [0,100]) over a non-empty sorted list."""
    if not sorted_vals:
        return 0.0
    rank = max(1, int(round(pct / 100.0 * len(sorted_vals))))
    return sorted_vals[min(rank, len(sorted_vals)) - 1]


def run_tick_drain(mem, *, max_ticks: int = 1000) -> dict:
    """Run tick() until the embed queue TRULY drains (or max_ticks); sum stage costs."""
    start = time.perf_counter()
    stage_ms_total: dict[str, float] = {}
    ticks = 0
    embed_shed_ticks = 0
    for _ in range(max_ticks):
        stats = mem.tick("2026-07-01T00:05:00Z")
        ticks += 1
        if "embed" in stats.stages_skipped:
            embed_shed_ticks += 1
        for entry in stats.stage_timings_ms:
            stage_ms_total[entry["stage"]] = (
                stage_ms_total.get(entry["stage"], 0.0) + float(entry["ms"]))
        # LOW-6 guard: `embed` is a Soft stage shed under DEGRADED, so
        # embedded==0 while embed was SKIPPED is NOT a real drain — keep ticking.
        if stats.embedded == 0 and "embed" not in stats.stages_skipped:
            break
    elapsed = time.perf_counter() - start
    top_stage = max(stage_ms_total, key=stage_ms_total.get) if stage_ms_total else ""
    return {
        "ticks": ticks,
        "elapsed_s": round(elapsed, 4),
        "stage_ms_total": {k: round(v, 3) for k, v in stage_ms_total.items()},
        "top_stage": top_stage,
        "embed_shed_ticks": embed_shed_ticks,
    }


def run_retrieval(mem, *, queries: int, statements: int,
                  rng: random.Random) -> dict:
    """Issue `queries` retrieval calls for EXISTING objects; report percentiles."""
    latencies_ms: list[float] = []
    abstained_count = 0
    hi = max(0, statements - 1)
    start = time.perf_counter()
    for _ in range(queries):
        text = f"obj_{rng.randint(0, hi)}"   # an object that was seeded (BLOCKER-2)
        t0 = time.perf_counter()
        result = mem.query(text, intent="FACT_LOOKUP", k=10)
        latencies_ms.append((time.perf_counter() - t0) * 1000.0)
        if result.get("abstained"):
            abstained_count += 1
    elapsed = time.perf_counter() - start
    latencies_ms.sort()
    return {
        "queries": queries,
        "p50_ms": round(_percentile(latencies_ms, 50), 3),
        "p95_ms": round(_percentile(latencies_ms, 95), 3),
        "p99_ms": round(_percentile(latencies_ms, 99), 3),
        "throughput_per_s": round(queries / elapsed, 2) if elapsed > 0 else 0.0,
        "abstained_count": abstained_count,
    }

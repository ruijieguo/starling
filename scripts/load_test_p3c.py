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


# Validity caveats — printed + embedded in the report so the baseline is never
# mistaken for a production profile (eng-review MAJOR-3).
_CAVEATS = [
    "FakeLLM + StubEmbedding(8-dim): extraction-LLM and embedding-network cost "
    "are EXCLUDED. A real embedder is ~1536-dim, so the O(n) cosine scan cost is "
    "under-measured (~190x). top_stage reflects the SQLite/scan machinery, NOT "
    "the production embedding/LLM hotspot — do not pick an optimization target "
    "from this alone without an LLM-in-the-loop cross-check.",
    "Retrieval is single-holder (holder=self owns all rows) and SEQUENTIAL; "
    "sustained-concurrent 100 QPS is deferred (out of scope for this baseline).",
    "If retrieval.abstained_count > 0, those queries hit the abstain path, not "
    "the scan — their latencies are not retrieval-scan latency.",
    "If tick.embed_shed_ticks > 0, the drain tripped DEGRADED load-shedding and "
    "may be incomplete (some statements left un-embedded).",
]


def build_report(params: dict, seed: dict, tick: dict, retrieval: dict) -> dict:
    return {"params": params, "seed": seed, "tick": tick,
            "retrieval": retrieval, "caveats": _CAVEATS}


def write_report(report: dict, out_dir: str) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    p = report["params"]
    path = out / f"p3c_baseline_{p['cognizers']}c_{p['statements']}s.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True))
    return path


def format_summary(report: dict) -> str:
    seed, tick, ret = report["seed"], report["tick"], report["retrieval"]
    lines = [
        "=== P3.c scale-baseline ===",
        f"seed:      {seed['seeded']} stmts in {seed['elapsed_s']}s "
        f"({seed['throughput_per_s']}/s)",
        f"tick:      {tick['ticks']} ticks, {tick['elapsed_s']}s; "
        f"top stage = {tick['top_stage']}; embed_shed_ticks={tick['embed_shed_ticks']}",
        "  stage_ms_total: " + ", ".join(
            f"{k}={v}" for k, v in sorted(
                tick["stage_ms_total"].items(), key=lambda kv: -kv[1])),
        f"retrieval: {ret['queries']} q; p50={ret['p50_ms']}ms "
        f"p95={ret['p95_ms']}ms p99={ret['p99_ms']}ms "
        f"({ret['throughput_per_s']}/s); abstained={ret['abstained_count']}/{ret['queries']}",
        "caveats:",
        *(f"  - {c}" for c in report.get("caveats", [])),
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="P3.c scale-baseline load-test harness.")
    ap.add_argument("--db", required=True, help="SQLite path to seed into")
    ap.add_argument("--cognizers", type=int, default=1000)
    ap.add_argument("--statements", type=int, default=10000, help="total statements")
    ap.add_argument("--queries", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out-dir", default="bench")
    ap.add_argument("--max-ticks", type=int, default=100000)
    args = ap.parse_args(argv)

    rng = random.Random(args.seed)
    mem, fake = open_memory(args.db)
    params = {"cognizers": args.cognizers, "statements": args.statements,
              "queries": args.queries, "seed": args.seed}
    print(f"seeding {args.statements} stmts across {args.cognizers} cognizers ...")
    seed = run_seed(mem, fake, cognizers=args.cognizers,
                    statements=args.statements, rng=rng)
    print(f"draining tick queue (max {args.max_ticks}) ...")
    tick = run_tick_drain(mem, max_ticks=args.max_ticks)
    print(f"retrieval x{args.queries} (existing objects, holder=self) ...")
    retrieval = run_retrieval(mem, queries=args.queries,
                              statements=args.statements, rng=rng)

    report = build_report(params, seed, tick, retrieval)
    path = write_report(report, args.out_dir)
    print(format_summary(report))
    print(f"report: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

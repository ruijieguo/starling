# P3.c Scale-Baseline Harness — Design

**Date:** 2026-07-01
**Status:** design approved (brainstorming); pending writing-plans → /plan-eng-review → subagent-driven
**Slice:** P3.c "规模化优化" — the measurement prelude to the c2/c3 optimization sub-slices

## Why this slice (the honest re-scoping)

P3.c's admission gate is a scale load test (`system_design.md:1705`): **1000 Cognizer ×
10000 Statement × 100 QPS retrieval**. The roadmap lists optimization items under P3.c
(dimension-level Container CAS, Retrieval fan-out latency budget, …), but a scoping +
brainstorming pass found that the first-guessed item — **c2.1 dimension-level Container
CAS** — optimizes an **inert code path**: `PersonaContainer::rebuild` (the only container
rebuild with a "dimension" structure) has **no live production caller** (invoked only in
`tests/python/test_m0_8_bindings.py`); the one live container rebuild (CommonGround,
`common_ground_subscriber.cpp:238`) stores status-keyed ID lists, **not dimensions**. So
there is no live persona-rebuild "stampede" to relieve — optimizing it now would be inert
theater, the pattern this project consistently defers (ScopedWorkGate, segment_map, the
live-wiring L1 deferrals).

The honest correction: **you cannot optimize scale without measuring it.** This slice
builds the measurement harness first. It is non-inert by construction (it produces real
measurements), it directly serves the P3 admission gate, and it turns every subsequent
c2/c3 optimization from *speculative* into *measured* — including empirically confirming
whether persona-rebuild is truly inert.

## Goal

A parameterized harness that loads the memory machinery to P3 scale with a **FakeLLM**
(deterministic, no network — we measure the *memory* machinery, not the LLM) and reports
**where time goes**, producing a **baseline report** that (a) establishes the
P3-admission numbers and (b) fingers the real bottleneck for the next slice.

## Scope & data (parameterized)

A CLI with flags:
- `--cognizers N` (target 1000), `--statements M` (**total** statements, distributed
  across the N cognizers — target 10000; NOT per-cognizer, which would be 10M remembers,
  infeasible under FakeLLM), `--queries Q`, `--seed S`.
- Interpretation of the acceptance "1000 Cognizer × 10000 Statement × 100 QPS": 1000
  distinct cognizers, 10000 statements **total**, 100 QPS retrieval. (Flagged to confirm in
  /plan-eng-review — the "×" is a listing of scale dimensions, not a literal product.)
- Synthetic but realistic data via a **fixed-seed RNG** (deterministic reproducibility):
  varied subjects / predicates / dimensions / perspectives so retrieval and consolidation
  exercise real branches, not a single hot row.
- The baseline run targets spec scale (1000 × 10000) if tractable under FakeLLM; otherwise
  a **documented fraction** with an explicit extrapolation note (no silent under-scaling).

## What it measures — three phases

1. **Seed.** `remember()` calls with FakeLLM until **M statements total** exist (spread
   across the N cognizers) → ingest throughput (statements/sec), total wall-clock, DB file
   size / row counts (footprint proxy). (One `remember` may yield ≥1 statements via
   extraction; the harness seeds to the target statement count, not a fixed remember count.)
2. **Maintenance tick.** Run `tick()` at the loaded scale → per-stage wall-clock **reusing
   the existing Phase-3b `StageTimer` / `TickOutcome.stage_timings_ms`** (no new C++
   instrumentation) → which of the 8 stages dominates at scale. *This is the empirical
   bottleneck finder;* it will also show that persona-rebuild never appears (confirming
   inert).
3. **Retrieval.** Drive Q queries (`Memory.query`) against the loaded DB → **p50 / p95 /
   p99 latency + achieved sequential throughput**. Baseline is **sequential**
   latency-at-scale; **sustained-concurrent 100 QPS is explicitly deferred** (the write
   path is single-writer and Python holds the GIL — whether the read path can sustain 100
   concurrent QPS is itself a finding the baseline surfaces, not an assumption this slice
   bakes in).

## Output

A structured report written under `bench/`:
- **JSON** (machine-readable, for trend tracking across runs): the params, per-phase
  metrics, percentile arrays, per-stage tick breakdown, footprint.
- **Human-readable summary** to stdout: a percentile table, the per-stage tick breakdown
  (sorted by cost), throughput, footprint, and a one-line "top bottleneck" call-out.

## Shape & location

- A standalone Python CLI **`scripts/load_test_p3c.py`** driving the **public API**
  (`Memory` / `DashboardEngine`) end-to-end + FakeLLM. (Chosen over a C++ micro-benchmark
  so it measures the real end-to-end path a real deployment runs, not an isolated inner
  loop.)
- A tiny-scale **pytest smoke** `tests/python/test_load_test_p3c_smoke.py` runs in CI to
  prove the harness executes + produces a well-formed report + all three phases run. The
  **full-scale run is manual / gated** (too slow for CI).

## Architecture boundary (CLAUDE.md)

The harness is **application-layer tooling**: it seeds and measures through the public API
and consumes the existing C++ `StageTimer` outputs. It adds **no core memory semantics** —
"switching the binding language would not require rewriting a benchmark script." Python is
the correct home. No algorithm, budget/trimming policy, state machine, or pipeline
orchestration is added here.

## Testing

- The **smoke pytest** (tiny deterministic config) asserts: the harness runs end-to-end,
  all three phases execute, and the report is well-formed (expected keys, sane types,
  non-negative metrics). FakeLLM keeps it deterministic and network-free.
- Correctness of the measurement = it exercises **real operations** (`remember`/`tick`/
  `query` against a real SQLite DB), not mocks; the only fake is the LLM (by design, to
  isolate the memory machinery).

## Honest deliverable & non-goals

**Delivers:** the harness + a measured baseline report at scale + the identified top
bottleneck(s), + an empirical note on whether persona-rebuild is inert.

**Deferred (explicitly, to the next now-measured slices):**
- pass/fail **admission thresholds** — set *from* this baseline, not guessed now;
- **sustained-concurrent 100 QPS** retrieval load (needs a read-path concurrency analysis);
- **optimizing** whatever the baseline fingers (dimension CAS / retrieval fan-out / etc.) —
  that becomes the next slice, now driven by a measured hotspot rather than a guess.

## Open questions for /plan-eng-review

- The exact tractable baseline scale under FakeLLM (full 1000×10000 vs a documented
  fraction) — decide from a quick feasibility probe during implementation.
- Whether the smoke pytest belongs in the default CI job or a separate opt-in marker (it
  must be fast; a few-cognizer config).
- Report location/format conventions (`bench/` dir, JSON schema) — align with any existing
  eval-report conventions (`scripts/eval_*`).

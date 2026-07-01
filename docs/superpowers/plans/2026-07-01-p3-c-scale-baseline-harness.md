# P3.c Scale-Baseline Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** A parameterized, offline (FakeLLM) load-test harness that seeds the memory machinery to P3 scale, measures the maintenance tick (per-stage) and retrieval latency, and emits a baseline report that fingers the real bottleneck — the measurement prelude to P3.c optimization.

**Architecture:** A standalone Python CLI `scripts/load_test_p3c.py` driving the public `Memory` facade + a `FakeLLMAdapter` end-to-end. Three phases — seed / tick / retrieval — each timed; results written as JSON + a human summary under `bench/`. A tiny-scale pytest smoke guards the harness mechanics in CI. Application-layer tooling: **no core memory semantics added** (Python is the correct home; it only seeds + measures through the public API and consumes the existing C++ `StageTimer` output).

**Tech Stack:** Python 3 (stdlib: `argparse`, `time.perf_counter`, `statistics`, `json`, `random`), the `starling` package (`Memory`, `make_stub_llm`, `TickStats`), pytest.

## Global Constraints

- **Design spec (authoritative):** `docs/superpowers/specs/2026-07-01-p3-c-scale-baseline-harness-design.md`. Scale interpretation: `--cognizers N` (target 1000), `--statements M` = **total** statements distributed across N cognizers (target 10000; NOT per-cognizer), `--queries Q`, `--seed S`.
- **Offline determinism:** use `starling.make_stub_llm(default_response=...)` (a `_core.FakeLLMAdapter`) — no network. The FakeLLMAdapter **ignores the prompt** and returns the canned response, so to seed M **distinct** statements the harness MUST set a **unique canned response per remember** (`fake.set_default_response(unique_json, True, "")`) — otherwise statement idempotency-dedup collapses the corpus to 1 row. Vary `holder` across `cog-0..cog-(N-1)` to distribute across cognizers.
- **Architecture boundary (CLAUDE.md):** this is tooling. Add NO algorithm / budget / state-machine / pipeline logic. Seed + measure through the public API only; consume `TickStats.stage_timings_ms` (already built in Phase 3b) for the per-stage breakdown.
- **Phase order:** seed → tick-to-drain (embeds the corpus so retrieval has vectors) → retrieval. Retrieval runs after the tick so statements are embedded (the facade uses `StubEmbeddingAdapter(8)`).
- **Build/test:** no C++ change → NO rebuild needed. Run tests with `.venv/bin/python -m pytest` (tools in `.venv/bin`, NOT system PATH). The harness itself runs as `.venv/bin/python scripts/load_test_p3c.py ...`.
- **Test design (benchmark):** the smoke test asserts **structural** properties (corpus size, report keys, percentiles computed, all phases ran) — NOT specific latency numbers (those are environment-dependent). A benchmark test that pins a wall-clock number is a flaky test.
- **git:** explicit-path `git add`; no `-A`/`--no-verify`/`--amend`. Footer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

## File structure

- **Create** `scripts/load_test_p3c.py` — the CLI harness: data generation, the 3 phase functions (`run_seed`, `run_tick_drain`, `run_retrieval`), report assembly (`build_report` / `write_report`), and `main(argv)`.
- **Create** `tests/python/test_load_test_p3c_smoke.py` — tiny-scale smoke of `main()` + the phase functions.
- **Create** `bench/.gitignore` — ignore transient report outputs (`*.json`) but keep the dir tracked.

---

## Task 1: Harness skeleton + deterministic data generation + seed phase

**Files:**
- Create: `scripts/load_test_p3c.py`
- Create: `bench/.gitignore`
- Test: `tests/python/test_load_test_p3c_smoke.py`

**Interfaces (Produces):**
- `open_memory(db_path: str) -> tuple[Memory, FakeLLMAdapter]` — opens an offline `Memory` over `db_path`, returns it + the mutable fake so callers can set per-remember responses.
- `unique_statement_json(idx: int) -> str` — a canned extraction response (JSON array of ONE statement) whose `subject`/`predicate`/`object` are unique per `idx` (so the seeded statement is distinct).
- `run_seed(mem, fake, *, cognizers: int, statements: int, rng: random.Random) -> dict` — seeds `statements` distinct statements across `cognizers` holders; returns `{"seeded": int, "elapsed_s": float, "throughput_per_s": float}`.

- [ ] **Step 1: Write the failing smoke test (seed portion)**

```python
# tests/python/test_load_test_p3c_smoke.py
import random
import importlib.util
from pathlib import Path

# Load the script module by path (it lives in scripts/, not the package).
_SPEC = importlib.util.spec_from_file_location(
    "load_test_p3c",
    Path(__file__).resolve().parents[2] / "scripts" / "load_test_p3c.py",
)
lt = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(lt)


def test_seed_produces_distinct_statements(tmp_path):
    mem, fake = lt.open_memory(str(tmp_path / "seed.db"))
    rng = random.Random(1234)
    res = lt.run_seed(mem, fake, cognizers=3, statements=12, rng=rng)
    assert res["seeded"] == 12
    assert res["throughput_per_s"] > 0
    # Distinctness: 12 remembers each set a unique canned response, so the
    # corpus holds 12 statements, not 1 dedup'd row.
    rows = mem.query("", intent="FACT_LOOKUP", k=100)["entries"]
    assert len(rows) >= 12
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/python/test_load_test_p3c_smoke.py::test_seed_produces_distinct_statements -v`
Expected: FAIL (module `scripts/load_test_p3c.py` does not exist yet).

- [ ] **Step 3: Implement the skeleton + seed phase**

```python
# scripts/load_test_p3c.py
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
import statistics
import time
from pathlib import Path

from starling import Memory, make_stub_llm


def open_memory(db_path: str):
    """Open an offline Memory over db_path; return (mem, fake_llm).

    The FakeLLMAdapter is returned so the caller can set a unique canned
    response before each remember (the adapter ignores the prompt).
    """
    fake = make_stub_llm(default_response=unique_statement_json(0))
    mem = Memory.open(db_path, agent="self", tenant_id="default", llm=fake)
    return mem, fake


def unique_statement_json(idx: int) -> str:
    """A canned extraction response (JSON array of ONE distinct statement)."""
    return (
        '[{"holder":"self","holder_perspective":"FIRST_PERSON",'
        f'"subject":"cog-{idx % 997}","predicate":"pred_{idx % 131}",'
        f'"object":"obj_{idx}","modality":"BELIEVES","polarity":"POS",'
        '"nesting_depth":0}]'
    )


def run_seed(mem, fake, *, cognizers: int, statements: int,
             rng: random.Random) -> dict:
    """Seed `statements` distinct statements across `cognizers` holders."""
    start = time.perf_counter()
    seeded = 0
    for idx in range(statements):
        fake.set_default_response(unique_statement_json(idx), True, "")
        holder = f"cog-{idx % cognizers}"
        # Distinct evidence payload (idempotency key is content-derived) +
        # distinct extracted statement (unique canned response above).
        mem.remember(f"seed statement {idx} topic {rng.randint(0, 1_000_000)}",
                     holder=holder, now="2026-07-01T00:00:00Z")
        seeded += 1
    elapsed = time.perf_counter() - start
    return {
        "seeded": seeded,
        "elapsed_s": round(elapsed, 4),
        "throughput_per_s": round(seeded / elapsed, 2) if elapsed > 0 else 0.0,
    }
```

Also create `bench/.gitignore` with:

```
# transient baseline reports
*.json
!.gitignore
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/python/test_load_test_p3c_smoke.py::test_seed_produces_distinct_statements -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/load_test_p3c.py tests/python/test_load_test_p3c_smoke.py bench/.gitignore
git commit -m "feat(P3.c/bench): harness skeleton + deterministic seed phase"
```

---

## Task 2: Tick-to-drain + retrieval measurement phases

**Files:**
- Modify: `scripts/load_test_p3c.py`
- Test: `tests/python/test_load_test_p3c_smoke.py`

**Interfaces:**
- Consumes: `open_memory`, `run_seed` (Task 1); `Memory.tick(now) -> TickStats` (`.embedded`, `.stage_timings_ms` = list of `{"stage": str, "ms": int}`); `Memory.query(text, *, intent, k) -> dict` (`["entries"]`).
- Produces:
  - `run_tick_drain(mem, *, max_ticks: int = 1000) -> dict` — runs `tick()` until the embed queue drains (`TickStats.embedded == 0`) or `max_ticks`; returns `{"ticks": int, "elapsed_s": float, "stage_ms_total": dict[str, float], "top_stage": str}` (per-stage ms summed across ticks; `top_stage` = the costliest).
  - `run_retrieval(mem, *, queries: int, rng: random.Random) -> dict` — issues `queries` `Memory.query` calls, times each; returns `{"queries": int, "p50_ms": float, "p95_ms": float, "p99_ms": float, "throughput_per_s": float}`.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/python/test_load_test_p3c_smoke.py
def test_tick_drain_reports_stage_breakdown(tmp_path):
    mem, fake = lt.open_memory(str(tmp_path / "tick.db"))
    rng = random.Random(7)
    lt.run_seed(mem, fake, cognizers=3, statements=12, rng=rng)
    res = lt.run_tick_drain(mem, max_ticks=50)
    assert res["ticks"] >= 1
    assert isinstance(res["stage_ms_total"], dict) and res["stage_ms_total"]
    # The 8 known stages are the only keys; top_stage is one of them.
    assert res["top_stage"] in res["stage_ms_total"]


def test_retrieval_reports_percentiles(tmp_path):
    mem, fake = lt.open_memory(str(tmp_path / "ret.db"))
    rng = random.Random(9)
    lt.run_seed(mem, fake, cognizers=3, statements=12, rng=rng)
    lt.run_tick_drain(mem, max_ticks=50)   # embed before retrieval
    res = lt.run_retrieval(mem, queries=20, rng=rng)
    assert res["queries"] == 20
    for key in ("p50_ms", "p95_ms", "p99_ms"):
        assert res[key] >= 0.0
    assert res["p99_ms"] >= res["p50_ms"]   # monotone percentiles
    assert res["throughput_per_s"] > 0
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/python/test_load_test_p3c_smoke.py -k "tick_drain or retrieval" -v`
Expected: FAIL (`run_tick_drain` / `run_retrieval` not defined).

- [ ] **Step 3: Implement the two phases**

```python
# add to scripts/load_test_p3c.py

def _percentile(sorted_vals: list[float], pct: float) -> float:
    """Nearest-rank percentile (pct in [0,100]) over a non-empty sorted list."""
    if not sorted_vals:
        return 0.0
    rank = max(1, int(round(pct / 100.0 * len(sorted_vals))))
    return sorted_vals[min(rank, len(sorted_vals)) - 1]


def run_tick_drain(mem, *, max_ticks: int = 1000) -> dict:
    """Run tick() until the embed queue drains (or max_ticks); sum stage costs."""
    start = time.perf_counter()
    stage_ms_total: dict[str, float] = {}
    ticks = 0
    for _ in range(max_ticks):
        stats = mem.tick("2026-07-01T00:05:00Z")
        ticks += 1
        for entry in stats.stage_timings_ms:
            stage_ms_total[entry["stage"]] = (
                stage_ms_total.get(entry["stage"], 0.0) + float(entry["ms"]))
        if stats.embedded == 0:   # queue drained
            break
    elapsed = time.perf_counter() - start
    top_stage = max(stage_ms_total, key=stage_ms_total.get) if stage_ms_total else ""
    return {
        "ticks": ticks,
        "elapsed_s": round(elapsed, 4),
        "stage_ms_total": {k: round(v, 3) for k, v in stage_ms_total.items()},
        "top_stage": top_stage,
    }


def run_retrieval(mem, *, queries: int, rng: random.Random) -> dict:
    """Issue `queries` retrieval calls; report latency percentiles + throughput."""
    latencies_ms: list[float] = []
    start = time.perf_counter()
    for _ in range(queries):
        text = f"obj_{rng.randint(0, 1_000_000)}"
        t0 = time.perf_counter()
        mem.query(text, intent="FACT_LOOKUP", k=10)
        latencies_ms.append((time.perf_counter() - t0) * 1000.0)
    elapsed = time.perf_counter() - start
    latencies_ms.sort()
    return {
        "queries": queries,
        "p50_ms": round(_percentile(latencies_ms, 50), 3),
        "p95_ms": round(_percentile(latencies_ms, 95), 3),
        "p99_ms": round(_percentile(latencies_ms, 99), 3),
        "throughput_per_s": round(queries / elapsed, 2) if elapsed > 0 else 0.0,
    }
```

- [ ] **Step 4: Run to verify they pass**

Run: `.venv/bin/python -m pytest tests/python/test_load_test_p3c_smoke.py -k "tick_drain or retrieval" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/load_test_p3c.py tests/python/test_load_test_p3c_smoke.py
git commit -m "feat(P3.c/bench): tick-drain stage breakdown + retrieval percentiles"
```

---

## Task 3: Report assembly + CLI + end-to-end smoke

**Files:**
- Modify: `scripts/load_test_p3c.py`
- Test: `tests/python/test_load_test_p3c_smoke.py`

**Interfaces:**
- Consumes: `open_memory`, `run_seed`, `run_tick_drain`, `run_retrieval`.
- Produces:
  - `build_report(params: dict, seed: dict, tick: dict, retrieval: dict) -> dict` — assembles the full report dict.
  - `write_report(report: dict, out_dir: str) -> Path` — writes `<out_dir>/p3c_baseline_<cognizers>c_<statements>s.json`, returns the path.
  - `format_summary(report: dict) -> str` — the human-readable summary string.
  - `main(argv: list[str] | None = None) -> int` — argparse CLI running all phases; exit 0.

- [ ] **Step 1: Write the failing end-to-end test**

```python
# append to tests/python/test_load_test_p3c_smoke.py
def test_main_end_to_end_writes_report(tmp_path):
    out = tmp_path / "bench"
    rc = lt.main([
        "--db", str(tmp_path / "e2e.db"),
        "--cognizers", "3", "--statements", "12", "--queries", "10",
        "--seed", "42", "--out-dir", str(out),
    ])
    assert rc == 0
    reports = list(out.glob("p3c_baseline_*.json"))
    assert len(reports) == 1
    import json as _json
    report = _json.loads(reports[0].read_text())
    for key in ("params", "seed", "tick", "retrieval"):
        assert key in report
    assert report["seed"]["seeded"] == 12
    assert report["retrieval"]["queries"] == 10
    assert report["tick"]["top_stage"]           # non-empty bottleneck call-out
    # persona-rebuild is inert: it must NOT appear among tick stages.
    assert "persona" not in " ".join(report["tick"]["stage_ms_total"]).lower()
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/python/test_load_test_p3c_smoke.py::test_main_end_to_end_writes_report -v`
Expected: FAIL (`main` not defined).

- [ ] **Step 3: Implement report + CLI**

```python
# add to scripts/load_test_p3c.py

def build_report(params: dict, seed: dict, tick: dict, retrieval: dict) -> dict:
    return {"params": params, "seed": seed, "tick": tick, "retrieval": retrieval}


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
        f"top stage = {tick['top_stage']}",
        "  stage_ms_total: " + ", ".join(
            f"{k}={v}" for k, v in sorted(
                tick["stage_ms_total"].items(), key=lambda kv: -kv[1])),
        f"retrieval: {ret['queries']} q; p50={ret['p50_ms']}ms "
        f"p95={ret['p95_ms']}ms p99={ret['p99_ms']}ms "
        f"({ret['throughput_per_s']}/s)",
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
    print(f"retrieval x{args.queries} ...")
    retrieval = run_retrieval(mem, queries=args.queries, rng=rng)

    report = build_report(params, seed, tick, retrieval)
    path = write_report(report, args.out_dir)
    print(format_summary(report))
    print(f"report: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the full smoke suite to verify pass**

Run: `.venv/bin/python -m pytest tests/python/test_load_test_p3c_smoke.py -v`
Expected: PASS (all 4 tests).

- [ ] **Step 5: Run the harness at a small real scale (sanity) + full pytest gate**

Run: `.venv/bin/python scripts/load_test_p3c.py --db /tmp/p3c.db --cognizers 20 --statements 200 --queries 50 --seed 1`
Expected: prints the summary + writes `bench/p3c_baseline_20c_200s.json`. Then:
Run: `.venv/bin/python -m pytest tests/python -q`
Expected: full suite green (harness adds only the smoke tests; no existing test touched).

- [ ] **Step 6: Commit**

```bash
git add scripts/load_test_p3c.py tests/python/test_load_test_p3c_smoke.py
git commit -m "feat(P3.c/bench): baseline report + CLI + end-to-end smoke"
```

---

## Slice acceptance

The harness runs offline (FakeLLM) end-to-end: seeds M distinct statements across N cognizers (deterministic via `--seed`), drains the maintenance tick (per-stage breakdown from the 3b `StageTimer`), drives Q retrieval queries (p50/p95/p99 + throughput), and writes a JSON + human-readable baseline report under `bench/`, naming the top tick-stage bottleneck. The smoke pytest asserts harness mechanics (corpus size, report keys, percentile monotonicity, all phases ran, persona-rebuild absent) — no wall-clock thresholds. Full pytest green. **Deferred (next, now-measured slices):** admission thresholds set from the baseline; sustained-concurrent 100 QPS; optimizing the fingered bottleneck.

## Self-review

**Spec coverage:** parameterized scale (Task 1/3 CLI) ✅; FakeLLM offline + unique-canned-response distinct seeding (Task 1) ✅; 3 phases seed/tick/retrieval (Tasks 1-2) ✅; per-stage breakdown reusing StageTimer (Task 2) ✅; p50/p95/p99 + throughput (Task 2) ✅; JSON + human report under bench/ (Task 3) ✅; smoke pytest (Tasks 1-3) ✅; architecture boundary = tooling, no core logic ✅; empirical persona-inert check (Task 3 assertion) ✅. Deferred items are explicitly out of scope.

**Placeholder scan:** every step has real code + exact run commands + expected output. No TBD/TODO.

**Type consistency:** `open_memory→(mem,fake)`, `run_seed(...)->dict{seeded,elapsed_s,throughput_per_s}`, `run_tick_drain(...)->dict{ticks,elapsed_s,stage_ms_total,top_stage}`, `run_retrieval(...)->dict{queries,p50_ms,p95_ms,p99_ms,throughput_per_s}`, `build_report(params,seed,tick,retrieval)`, `write_report->Path`, `main(argv)->int` — consistent across tasks. `TickStats.stage_timings_ms` entries are `{"stage","ms"}` (3b/LW.3), consumed in Task 2.

## Open questions for /plan-eng-review
- Baseline scale feasibility under FakeLLM (full 1000×10000 wall-clock) — probe during impl; the `--statements`/`--cognizers` params make it tunable.
- Should the smoke pytest carry a marker to keep CI fast (it uses 3 cognizers × 12 statements — already tiny)?
- `bench/` vs `build/` for report output (eval scripts use `build/`, git-ignored) — align conventions.
- Does `run_tick_drain`'s "drain when `embedded==0`" correctly terminate given a single embed batch per tick? (Verify the embed batch size vs statement count; `--max-ticks` caps runaway.)

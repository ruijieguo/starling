# P3.c Live Wiring — Close the Backpressure Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make the single-threaded maintenance tick **read `RuntimeSupervisor::health()` and shed load** — DEGRADED skips the soft (droppable, high-cost) stages and keeps the critical ones; DRAINING sheds new background work. This closes the backpressure loop c1 left open (c1 built sense: sampler → `note_health`; this builds act: tick reads health → load-sheds), delivering the "自动背压调度" the roadmap names for P3.c Governance.

**Architecture:** A pure C++ stage-gating policy (`should_run_stage(stage, health) -> bool`, plus a soft/critical lane classification of the 8 tick stages) in `src/governance/`; `tick_all` takes the current `RuntimeHealth` and gates each stage through it; the Python host (`engine.py`) passes `supervisor.health()` into the tick. No new threads, no gate-quota, no worker pool.

**Tech Stack:** C++20 core (`include/starling/governance/`, `src/governance/`, `src/memory/memory_ops.cpp`), pybind11, GoogleTest, Python host (`engine.py`), pytest, optional SvelteKit panel.

## Global Constraints

- **Architecture boundary (CLAUDE.md):** the load-shedding DECISION (which stages run given health) is core semantics → C++ (`tick_all` gates stages via a pure policy). Python only passes `supervisor.health()` in. "换一种绑定语言是否需要重写" → yes → core.
- **CI clang-tidy (changed-LINES) gate** on `.cpp`/`.hpp` under `src/|bindings/`, WarningsAsErrors `*`, DISABLES `bugprone-easily-swappable-parameters`. Write clean by construction: `enum class : std::uint8_t`; `[[nodiscard]]`; ≥3-char ids (incl. iterators — `found` not `it`); `std::ranges`/`std::erase_if`; braces; designated initializers; a stateless member fn that can be `static` → NOLINT with justification (the `metrics_gatherer`/`pipeline_run_store` precedent) or make it a free function. clang-tidy un-runnable locally — the IDE's full-file lint surfaces it pre-push; CI is the gate. See `[[clang-tidy-ci-only-gate-gotchas]]`.
- **`tick_all` signature change → binding + Python consumers.** `tick_all` is called via `_core` from `engine.py`/`memory.py`. Any new param (the health) flows through the binding; watch the `TickOutcome`/`TickStats` consumers (`[[tickoutcome-dict-field-breaks-python-consumers]]` — adding a tick-dict field broke `TickStats(**dict)` + the `any(stats.values())` heartbeat in 3b; if this slice adds a "stages_skipped" field, the SAME two consumers + the 2 exact-key-set tests must be updated).
- **Replay/write reentrancy:** the gating is read-only (reads health, skips a stage) — no writes added, no `BEGIN` nesting (`[[replay-write-reentrancy-offline-only]]`).
- **Binding rebuild:** `tick_all`/binding change → `python scripts/configure_build.py --build --python-editable`. Build tools in `.venv/bin/{cmake,ctest,ninja}` (NOT system PATH — the recurring gotcha); test binary `build-macos/tests/cpp/starling_tests`.
- **Commit gate:** full `.venv/bin/ctest --test-dir build-macos` + `.venv/bin/python -m pytest tests/python` green; frontend (if touched) `npm run check`/`npx vitest run`/`npm run build` in `dashboard/web/`.
- **git:** explicit-path `git add`; no `--no-verify`/`--amend`. Footer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

## RESOLVED DECISIONS (LOCKED by /plan-eng-review + codex outside-voice, 2026-06-30)

The OQ analysis below is the rationale record. **The LOCKED block after it is AUTHORITATIVE — implementers apply it OVER any conflicting task text.**

## OPEN DECISIONS — analysis (rationale record; superseded by the LOCKED block)

### OQ-LW.1 (CENTRAL) — scope: close-the-loop vs wire-the-gate

The Explore confirmed the tick is single-threaded; the gate's quota/admission is **correct-but-inert** (no contention with one worker — soft-drop never triggers, leases never leak). The c1 substrates split into:
- **REAL even single-threaded:** the tick reading `health()` to load-shed (DEGRADED → skip soft stages, keep critical; DRAINING → shed background). Genuine behavior, observable, testable.
- **INERT single-threaded (theater until a worker pool = P3+):** ScopedWorkGate quota/`acquire`/`release`/`sweep_leaked`, worker-claiming, PipelineRun lease lifecycle.

**Baseline (recommended): scope = CLOSE THE BACKPRESSURE LOOP.** Wire the tick to read `health()` and load-shed. **DEFER (flagged, not dropped) to P3+/worker-pool:** the gate-quota wiring, worker-claiming, PipelineRunStore population for runs (R3 observability — its own slice), and the `BusWriteResponse{retry_after}` write-path change (Phase-5-deferred, coupled to the DRAINING write contract). This makes the slice deliver real backpressure behavior without shipping inert gate theater — same honesty as Phase 5's zero≠healthy.

### Sub-decisions (baselines; eng-review locks)
- **OQ-LW.2 — mechanism = a DIRECT tick-level `health()` guard, NOT the gate's soft-drop.** The c1-plan assumed "route pumps through gate admission" pauses soft lanes; that's inert single-threaded. Pause soft lanes by a pure `should_run_stage(stage, health)` check in `tick_all`. (This supersedes the c1-plan's assumed mechanism — flag it.)
- **OQ-LW.3 — lane classification of the 8 tick stages.** Baseline (spec `05_governance.md` DEGRADED row: pause Replay/Projection non-critical batch + defer high-cost side-effects; keep Compliance/Commitment + outbox delivery):
  - **Soft (skip under DEGRADED):** `embed` (high-cost embedding side-effect), `common_ground` (non-critical grounding batch), `replay` (3 sub-stages — non-critical consolidation), `projection` (non-critical projection batch).
  - **Critical (always run):** `policy` (commitment fire), `outbox` (delivery convergence must not stall).
  - Eng-review confirms each classification (esp. `embed`, `common_ground`).
- **OQ-LW.4 — where the guard lives = C++ `tick_all` takes `RuntimeHealth health`** (a new param) and gates each stage via the pure policy. Architecture boundary: the decision is core. The host passes `supervisor.health()`. (Alternative — host calls per-stage entrypoints + gates in Python — REJECTED: scatters core semantics into the binding layer + `tick_all` is one C++ call.)
- **OQ-LW.5 — DRAINING behavior in scope = the tick sheds ALL background stages** (no new background work) but the write path is OUT of scope here. (Does `RuntimeSupervisor::check_write()` already gate DRAINING writes from Phase 1? VERIFY — if yes, DRAINING write-refusal partly exists; the `retry_after` surfacing via `BusWriteResponse` is the deferred part.) Under DRAINING the tick may still run `outbox` to drain in-flight delivery — eng-review decides drain-outbox vs full-stop.
- **OQ-LW.6 — observability of shedding.** When a stage is skipped, record it (a `stages_skipped` set in `TickOutcome`, or a counter) so the dashboard shows load-shedding. If added to the tick dict, update the `[[tickoutcome-dict-field-breaks-python-consumers]]` consumers. Baseline: include a minimal skipped-stage signal (it's the observable proof the loop closed); the dashboard render is optional (OQ-LW.7).
- **OQ-LW.7 — dashboard.** Optional: show "load-shedding active (N stages skipped)" on the runtime-health panel when DEGRADED. Baseline: defer unless cheap (the panel already shows the DEGRADED status from Phase 5).

### LOCKED eng-review decisions (2026-06-30) — AUTHORITATIVE; apply OVER task text

/plan-eng-review (FULL + codex outside-voice; 10 codex findings, all folded). Where these conflict with task text below, THESE win.

- **L1 — OQ-LW.1 = A (close-the-loop only).** Wire tick→read `health()`→load-shed. **DEFER to P3+/worker-pool:** the gate quota/`acquire`/`release`/worker-claiming/lease lifecycle (inert single-threaded), PipelineRunStore run-population, `BusWriteResponse{retry_after}`. NO inert gate wiring. [user-locked D1]
- **L2 — mechanism = a DIRECT tick-level health guard** (pure `should_run_stage(stage, health)`), NOT the gate's soft-drop (inert single-threaded). Corrects the c1-plan's assumed mechanism. [OQ-LW.2]
- **L3 — HONEST framing (codex #1/#4 — the key correction):** the slice delivers health-driven **LOAD-SHEDDING** (defer expensive background under backpressure — spec "高成本副作用延后"). It does **NOT** claim shedding *drives recovery*: `outbox_lag` recovery is driven by **`outbox` (critical, always-run)**; shedding is **load-relief** (frees the one thread, stops adding background load), not the drainer. The effectiveness test proves **CAUSALITY** — under DEGRADED the soft-stage effects are absent / tick cost measurably drops — NOT "lag recovers" (which `outbox` alone achieves). Do not oversell "closes the loop → recovers lag."
- **L4 — lane classification (codex #2):**
  - **SOFT (skip under DEGRADED):** `embed`, `common_ground`, `projection`, `replay:run_idle`.
  - **CRITICAL (always run):** `policy` (commitment fire), `outbox` (the lag drainer), **`replay:enforce_oscillation_guard` + `replay:sweep_volatile_ttl`** (safety/retention — NOT droppable). → replay is **SPLIT**: 2 safety substages critical, `run_idle` soft. So `TickStage` enumerates the replay substages separately (or the gating is per-substage).
- **L5 — TRIGGER-AWARENESS invariant (codex #3):** the static lane map is valid ONLY for c1's currently-enabled sampler triggers (`outbox_lag` + `runtime_event_loop_lag_ms`; `outbox` is critical so shedding the soft stages is safe). **Document the invariant:** enabling a new trigger whose drainer is a SOFT stage (e.g. `projection_lag`→`projection`) requires making the shedding **trigger-aware FIRST**, else DEGRADED skips the very stage that would recover it (self-deadlock). Not built now; a guard-comment + a plan note.
- **L6 — wiring point (codex #5):** wire the health read at **`MemoryCore.tick()`** (`python/starling/_memory_core.py` — the shared choke point both `DashboardEngine.tick()` and the public `Memory.tick()` delegate to), NOT only `engine.py`. VERIFY how `MemoryCore` reaches the supervisor's health (it may need a health-supplier ref / the Runtime passes it). Every `memory_tick_all` caller gated, or none.
- **L7 — DRAINING (codex #7/#8 — resolves OQ-LW.5):** `check_write()` ALREADY rejects DRAINING/UNREADY writes (`runtime_supervisor.cpp:86`, Phase 1) — DRAINING write-refusal EXISTS. The DRAINING tick **KEEPS `outbox`** (drain in-flight; writes already rejected so no new work admitted), sheds the rest. Best-effort drain (NOT guaranteed if the host kills the process — don't claim guaranteed). `retry_after` surfacing via `BusWriteResponse` stays DEFERRED (P3+).
- **L8 — TickOutcome contract (codex #6/#10):** timings recorded ONLY for **executed** stages + a `stages_skipped` field (set/list). Update the `TickStats` dataclass (`memory.py`); **EXCLUDE `stages_skipped` from the `any(stats.values())` idle-heartbeat predicate** (`engine.py` — else a non-empty skip list falsely counts as work, the 3b trap); update the exact-key-set tests + the "8 timing entries in order" tests (now ≤8, only executed). [[tickoutcome-dict-field-breaks-python-consumers]]
- **L9 — health read once-per-tick, sample-after-tick (codex #9):** acceptable; the first overloaded tick acts on the PRIOR health (can't shed yet); shedding starts next-tick + debounce. The pytest drives REAL ticks and asserts the one-tick+debounce latency (not just direct `note_health()`).

---

## What this delivers (spec linkage)
- Spec: `05_governance.md` DEGRADED row ("暂停 Replay / Projection 非关键批处理,保留 Compliance / Commitment"; "高成本副作用延后") + DRAINING row ("拒绝新后台 run"). Roadmap `2026-05-23-roadmap.md:143` P3.c Governance: "RuntimeHealth 完整仪表盘 + DEGRADED/DRAINING 状态置入与自动背压".
- Reuses: `RuntimeSupervisor::health()` (Phase 1/2), the 8-stage `tick_all` (3b StageTimer), the Phase-5 sampler that drives `note_health`. NEW: the stage-gating policy + the `tick_all` health param.
- **Closes the loop:** sampler (Phase 5) → `note_health` → health state → (NEW) tick reads health → sheds soft stages. End-to-end observable: seed backpressure → sampler DEGRADED → next tick skips soft stages → dashboard shows it.

---

## File structure
- **Create** `include/starling/governance/tick_load_shedding.hpp` (+ maybe `.cpp`) — the `TickStage` enum (sized) + `lane_of(TickStage)` + `should_run_stage(TickStage, RuntimeHealth) -> bool`, pure.
- **Modify** `include/starling/memory/memory_ops.hpp` + `src/memory/memory_ops.cpp` — `tick_all` takes `RuntimeHealth health`; each stage guarded by `should_run_stage`; skipped stages recorded in `TickOutcome`.
- **Modify** `bindings/python/bind_*` (the `tick_all`/`memory_tick_all` binding) — pass health through.
- **Modify** `python/starling/dashboard/engine.py` (+ `memory.py` if it calls tick) — pass `self._rt.health()` (or the supervisor's health) into the tick; handle the new skipped-stage field in `TickStats`/the heartbeat gate.
- **Create** `tests/cpp/test_tick_load_shedding.cpp` + extend `tests/cpp/test_memory_ops*`/the tick test; **Create** `tests/python/test_backpressure_loadshed.py`.
- **Possibly modify** `dashboard/web/src/routes/runtime-health/+page.svelte` (OQ-LW.7, likely deferred).

---

## Task LW.1: the pure stage-gating policy

**Files:** Create `include/starling/governance/tick_load_shedding.hpp` (+ `.cpp` if non-inline) + `tests/cpp/test_tick_load_shedding.cpp`; Modify CMake.

**Interfaces (Produces):**
```cpp
namespace starling::governance {
enum class TickStage : std::uint8_t { Embed, Policy, CommonGround, Replay, Projection, Outbox };
enum class TickLane  : std::uint8_t { Soft, Critical };
[[nodiscard]] TickLane lane_of(TickStage stage);            // OQ-LW.3 classification
// READY → all true; DEGRADED → Critical only; DRAINING → (OQ-LW.5: all background shed,
// possibly Outbox kept to drain); UNREADY → all false (fail-closed, never ticks anyway).
[[nodiscard]] bool should_run_stage(TickStage stage, RuntimeHealth health);
}
```

- [ ] **Step 1: Write failing tests** — `lane_of` classifies each of the 6 stages per OQ-LW.3; `should_run_stage`: READY→all run; DEGRADED→Policy+Outbox run, Embed/CommonGround/Replay/Projection skipped; DRAINING→(locked behavior); each stage×each health pinned. [Exact table at impl time.]
- [ ] **Step 2: Register + verify fail** — add to `CMakeLists.txt` `target_sources` + the test to `tests/cpp/CMakeLists.txt`; build; `--gtest_filter='TickLoadShedding*'` FAILs.
- [ ] **Step 3: Implement** — pure, no I/O, `[[nodiscard]]`, sized enums, ≥3-char ids.
- [ ] **Step 4: Verify pass.**
- [ ] **Step 5: Full gate + commit** — `feat(P3.c/lw): tick load-shedding policy — soft/critical lanes vs RuntimeHealth`.

## Task LW.2: gate `tick_all` by health

**Files:** Modify `include/starling/memory/memory_ops.hpp` + `src/memory/memory_ops.cpp` + the tick ctest.

**Interfaces:** `tick_all(..., RuntimeHealth health)` (new last param); each of the 8 stage blocks wrapped in `if (should_run_stage(STAGE, health)) { ... }`; skipped stages recorded in `TickOutcome` (a `stages_skipped` set/bitset — OQ-LW.6). The 3 replay sub-stages all gate under `Replay`.

- [ ] **Step 1: Write a failing ctest** — drive `tick_all` with `health=DEGRADED` on a seeded DB; assert the soft-stage effects DON'T happen (e.g. no embedding rows produced / no projection upsert) while critical (outbox) DOES; `health=READY` runs all; the skipped set is recorded. (Mirror the existing tick_all test fixture.)
- [ ] **Step 2: Verify fail** (signature/gating absent).
- [ ] **Step 3: Implement** — add the param, guard each stage, record skips. Keep StageTimer timing only the stages that run. clang-tidy-clean.
- [ ] **Step 4: Verify pass + the existing tick_all tests** (update them for the new param).
- [ ] **Step 5: Full gate + commit** — `feat(P3.c/lw): tick_all sheds soft stages under DEGRADED/DRAINING`.

## Task LW.3: binding + host wiring (pass health into the tick)

**Files:** Modify the `tick_all`/`memory_tick_all` binding + `python/starling/dashboard/engine.py` (+ `memory.py`); Create `tests/python/test_backpressure_loadshed.py`.

**Interfaces (per L6 — wire at the choke point):** the binding passes the health enum through `memory_tick_all`; **`MemoryCore.tick()`** (`python/starling/_memory_core.py` — the shared path `DashboardEngine.tick()` AND `Memory.tick()` delegate to) reads the live supervisor's health and passes it into the core tick (VERIFY how `MemoryCore` reaches the supervisor — likely a health-supplier ref the Runtime injects); the `stages_skipped` field is added to `TickStats` (dataclass) + EXCLUDED from the `any(stats.values())` idle-heartbeat gate (L8, [[tickoutcome-dict-field-breaks-python-consumers]]) + the exact-key-set tests + the "8 timing entries" tests updated (timings only for executed stages).

- [ ] **Step 1: Write a failing pytest** — build a DashboardEngine; force DEGRADED (drive the sampler with seeded lag, or `note_health(degraded)` directly); run a tick; assert the soft-stage work did NOT occur + critical did + `engine`'s tick stats report the skipped stages; recovery to READY → all stages run again. Mirror `test_backpressure_sampler.py` + `test_dashboard_engine.py`.
- [ ] **Step 2: Verify fail.**
- [ ] **Step 3: Implement** the binding + engine wiring; rebuild `--python-editable`; fix the `TickStats`/heartbeat/exact-key-set consumers.
- [ ] **Step 4: Verify** the new pytest + `test_dashboard_engine.py` + `test_dashboard_commands.py` + `test_backpressure_sampler.py` green.
- [ ] **Step 5: Full gate + commit** — `feat(P3.c/lw): host passes RuntimeHealth into the tick — observable load-shedding`.

**Slice acceptance (L3 — honest):** the maintenance tick reads `health()` (wired at `MemoryCore.tick()` per L6) and **load-sheds** — DEGRADED skips soft (embed/common_ground/projection/replay:run_idle), keeps critical (policy/outbox + replay safety substages per L4); DRAINING keeps outbox to drain + sheds the rest (L7); READY runs all; skipped stages observable (timings only for executed + `stages_skipped`, L8). The effectiveness test proves **CAUSALITY** — under DEGRADED the soft-stage effects are absent / tick cost drops (NOT "lag recovers", which `outbox` alone achieves, L3) — driven through REAL ticks asserting the one-tick+debounce latency (L9). Full ctest + pytest green. **DEFERRED to P3+/worker-pool (L1):** gate-quota/acquire/worker-claiming/lease, PipelineRunStore run population, `BusWriteResponse{retry_after}`. **Invariant (L5):** the static lane map is valid only for c1's enabled triggers (outbox_lag+loop_lag); new triggers need trigger-aware shedding first.

---

## Self-review

**Spec coverage** (`05_governance.md` DEGRADED/DRAINING + roadmap P3.c):
- "DEGRADED 暂停 Replay/Projection 非关键批处理,保留 Compliance/Commitment" → LW.1 lane classification + LW.2 gating. ✅ (the honest mechanism — direct health guard, OQ-LW.2, NOT the inert gate.)
- "高成本副作用延后" → `embed` classified Soft. ✅
- "DRAINING 拒绝新后台 run" → LW.2 DRAINING sheds background (OQ-LW.5). ✅ partial — the write-path `retry_after` is DEFERRED (BusWriteResponse, P3+).
- "自动背压调度" (roadmap) → the closed loop (sampler→note_health→tick load-sheds). ✅
- The gate-quota/worker-claiming → **DEFERRED to P3+** (OQ-LW.1; inert single-threaded — flagged honestly, the spec's `05_governance.md:155-169` ScopedWorkGate section assumes concurrency the code lacks).

**Placeholder scan:** the stage classification (OQ-LW.3) + the DRAINING behavior (OQ-LW.5) + whether `check_write` already gates DRAINING writes are the genuinely-open spots — surfaced for eng-review, baselines stated.

**Type consistency:** `TickStage`/`TickLane`/`should_run_stage` (LW.1) consumed by `tick_all` (LW.2) + the binding/host (LW.3); `RuntimeHealth` reused from Phase 1/2 (`runtime_health.hpp`); `health()` from `RuntimeSupervisor`. The `tick_all` signature change is the main blast radius (binding + `TickStats` + 2 heartbeat/key-set consumers — pinned by the 3b lesson).

**clang-tidy pre-flight:** sized enums (`: std::uint8_t`); `[[nodiscard]]` on the policy fns; ≥3-char ids; a stateless free function (not a member) avoids the convert-to-static gotcha, or NOLINT it. The `memory_ops.cpp` changed lines (the stage guards) linted — watch loop/var names.

---

## Implementation Tasks
Synthesized from this review (all FOLDED into the LOCKED block + tasks).

- [ ] **T1 (P1, human: ~2h / CC: ~20min)** — `should_run_stage` policy + `TickStage` enum (replay split)
  - Surfaced by: L2 (direct guard) + L4 (replay split — `run_idle` soft, `oscillation_guard`+`ttl_sweep` critical) + L5 (trigger-awareness guard-comment)
  - Files: `include/starling/governance/tick_load_shedding.hpp`(+`.cpp`), `tests/cpp/test_tick_load_shedding.cpp`
  - Verify: `--gtest_filter='TickLoadShedding*'` (each stage×health; replay substages classified separately)
- [ ] **T2 (P1, human: ~2h / CC: ~25min)** — gate `tick_all` by health (replay split + executed-only timings)
  - Surfaced by: L4 + L7 (DRAINING keeps outbox) + L8 (timings only executed + `stages_skipped`) + L3 (causality)
  - Files: `include/starling/memory/memory_ops.hpp`, `src/memory/memory_ops.cpp`, the tick ctest
  - Verify: `.venv/bin/ctest --test-dir build-macos -R 'tick'` (DEGRADED soft-effects absent + outbox runs; ≤8 timings only for executed; skipped recorded)
- [ ] **T3 (P1, human: ~2h / CC: ~25min)** — wire health at `MemoryCore.tick()` + host pytest
  - Surfaced by: L6 (choke point, NOT engine.py) + L8 (TickStats/heartbeat exclude) + L9 (one-tick+debounce latency via real ticks)
  - Files: `bindings/python/bind_*` (memory_tick_all), `python/starling/_memory_core.py`, `python/starling/memory.py` (TickStats), `python/starling/dashboard/engine.py` (heartbeat), `python/starling/runtime.py` (health supplier if needed), `tests/python/test_backpressure_loadshed.py`
  - Verify: `.venv/bin/python -m pytest tests/python/test_backpressure_loadshed.py tests/python/test_dashboard_engine.py tests/python/test_dashboard_commands.py tests/python/test_backpressure_sampler.py` then full `pytest tests/python`

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 1 | issues_found | 10 findings, ALL folded (honesty reframe + replay split + wrong wiring point + trigger-awareness) |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | clean | OQ-LW.1=A locked; 0 critical gaps; codex caught 3 real corrections |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

Step 0 scope: ACCEPTED — ~8 files, **0 new classes** (enums + free functions), test-driven; not overbuilt (the plan already defers everything inert). Locked **OQ-LW.1=A** (close-the-backpressure-loop; DEFER the inert gate-quota/worker-claiming/run-ledger/`BusWriteResponse` to P3+) — consistent with Phase-4 OQ-4.1=B + Phase-5 zero≠healthy honesty. Architecture: the loop's effectiveness rests on the lane classification (drainer=critical, expensive-producer=soft) — honestly reframed as **load-shedding** (recovery driven by outbox, not shedding — L3). Code Quality: the `tick_all` signature + `stages_skipped` blast radius (the 3b trap) — locked L8. Tests strong; the "lag recovers" smoke is replaced by a CAUSALITY test (L3). Performance: gating is cheap; under DEGRADED the tick does less work (the feature).

- **CODEX (outside voice):** 10 findings, ALL folded. Caught **3 real corrections the inline-review missed**: **#1/#4** (the "closes the loop → recovers lag" claim is overstated — recovery is driven by `outbox` (critical); shedding is load-relief; the test must prove CAUSALITY, not lag-recovery → L3) + **#5** (the wiring point is `MemoryCore.tick()`, NOT `engine.py` — `Memory.tick()` would stay ungated → L6) + **#2** (replay is 3 substages; `oscillation_guard`+`ttl_sweep` are safety/retention, NOT droppable → split, L4). **#3** (projection self-deadlock if `projection_lag` becomes a trigger → trigger-awareness invariant L5). #6/#10 (TickStats/timing contract → L8), #7 (DRAINING writes already gated — resolved OQ-LW.5), #8 (DRAINING keeps outbox → L7), #9 (stale-health latency test → L9) folded.
- **CROSS-MODEL:** codex's bottom line — "directionally right as 'make health affect tick behavior' but not proven to relieve the trigger; split replay, make projection trigger-compatible, write a causality test" — accepted in full (L3/L4/L5). The honesty reframe (#1/#4) is the highest-value: a single-model pass would have shipped a plan claiming load-shedding "closes the loop and recovers lag," which `outbox`-stays-critical achieves regardless.
- **VERDICT:** ENG CLEARED — close-the-backpressure-loop, honestly framed as **health-driven load-shedding** (real behavior; recovery driven by outbox), implement subagent-driven. 1 user decision (OQ-LW.1=A) + 10 codex folds in the LOCKED block.

NO UNRESOLVED DECISIONS

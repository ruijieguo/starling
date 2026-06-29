# P3.c1 — Runtime Governance Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Relocate runtime governance semantics from the Python `runtime.py` stub into a real C++ governance subsystem and build the four-state RuntimeHealth machine, PipelineRun long-task ledger, ScopedWorkGate, RestartGuard, stage timing, and health-driven backpressure — the Governance slice of P3.c.

**Architecture:** Create a greenfield `src/governance/` + `include/starling/governance/` C++ subsystem owning the governance CORE (capability policy, preflight, READY/DEGRADED/DRAINING/UNREADY state machine, PipelineRun ledger, ScopedWorkGate, RestartGuard, backpressure decisions). The HOST process (FastAPI/uvicorn for the dashboard, or embedded `Memory.open`) keeps only lifecycle EMBEDDING: signal handling, the tick thread, and feeding host-side metrics (event-loop lag) into the core. `python/starling/runtime.py` collapses to a thin pybind forwarder over the C++ `RuntimeSupervisor`, so the [CRITICAL] `TC-NEW-PREFLIGHT` test keeps driving the same Python facade and stays green.

**Tech Stack:** C++20 core (`src/` + `include/starling/`), pybind11 bindings (`bindings/python/`), SQLite persistence (`src/store/`, single-writer discipline), Python adapters (`python/starling/`), SvelteKit/FastAPI dashboard read path (`dashboard/web/`, `python/starling/dashboard/`).

## Global Constraints

- **Architecture boundary (hard rule, CLAUDE.md):** core semantics in C++ (`src/` + `include/starling/`); Python only adapter/config/read-only. The cross-language test: *would another binding language need to rewrite this logic? → it's core → C++.* Governance state machine, capability policy, preflight, ledger, gate, restart, backpressure decisions are all CORE.
- **Write discipline (CLAUDE.md):** idempotent-dedup invariant lives in the WRITER. Audit/notification writes (`OutboxWriter::append_already_delivered`, `PipelineLedger::record_attempt`) `INSERT OR IGNORE` silently on dup-key; business events `append` fail-loud on dup-key. The new `governance_pipeline_run` writer follows the same rule (find-active-run dedup is INSERT-then-detect, never a caller-side set).
- **Post-write / subscriber paths use SAVEPOINT, not BEGIN** (`src/bus/subscriber_pump.cpp`). Any governance write triggered from a subscriber/online-replay path must use SAVEPOINT (see `[[replay-write-reentrancy-offline-only]]`: `Bus::write` opens BEGIN + re-runs the post-write pump; nesting BEGIN silently aborts).
- **Statements writes go through `SqliteStatementStore`** — raw INSERT/UPDATE of `statements` outside `src/store` + `statement_writer` fails the CI static-scan gate. Governance owns its OWN tables, not `statements`.
- **Canonical build:** `python scripts/configure_build.py --build --test` (C++ + ctest). After ANY C++/binding/migration change, re-run with `--python-editable` to reinstall `_core` (a bare `pip install -e .` is insufficient).
- **Commit gate:** full ctest + `pytest tests/python` green. Dashboard front-end (only if touched) also `npm run check` / `npx vitest run` / `npm run build` in `dashboard/web/`.
- **git:** explicit-path `git add` only (no `git add .` / `-A`); no `--no-verify` / `--amend`.
- **CI clang-tidy (changed-LINES) gate** (`scripts/ci_clang_tidy_diff.py`): WarningsAsErrors `*` but DISABLES `bugprone-easily-swappable-parameters`. Use designated initializers for multi-field aggregates, `contains()` over `count()!=0`, `std::ranges::any_of` over manual loops, identifiers ≥3 chars, braces around all statements, and keep new functions under cognitive-complexity 25 (extract helpers). See `[[ci-clang-tidy-changed-files-leaks-headers]]`.
- **EX_CONFIG = 78** (POSIX `sysexits.h` `EX_CONFIG`) is the fail-closed exit code; defined once in C++ (today it lives in `runtime.py:15`).

---

## Background — current state (gap-map, 2026-06-28)

Authoritative target spec: `docs/design/subsystems_design/05_governance.md` (190 lines). Current implementation vs target:

| Target (05_governance.md) | Current state | Anchor |
|---|---|---|
| RuntimeHealth 4-state machine + `runtime.health_changed` events | PARTIAL — enum has 4 states; only READY/UNREADY reachable; DEGRADED/DRAINING declared-but-dead; `RuntimeHealthMonitor` class **not bound to Python, no C++ caller** (dead scaffolding) | `include/starling/runtime_health.hpp:10,13-18`; `src/runtime_health.cpp:11-25`; `bind_01_core.cpp:96-100` (enum only) |
| Supervisor: preflight → state → workers; signals; drain | STUB — Python `Runtime` is the real supervisor (preflight + READY/UNREADY + worker-start booleans + exit 78); no C++ `int main()`; real lifecycle in FastAPI `lifespan`; no signals, no drain | `python/starling/runtime.py:120-193`; `python/starling/dashboard/app.py:42-69` |
| Capability policy LOCAL_STORE_REQUIRED + embedded exemption + exit 78 + idx preflight + READY write-gate — **in C++ [CRITICAL]** | In PYTHON (boundary violation). `relax_preflight_for_embedded()` **mutates a module global**; idx preflight does a **raw `sqlite3` read in Python** | `runtime.py:19-27,36,39-52,15,159-160,220-227,67-117` |
| `preflight()` matcher + `ProfileCapability` | FULL, already C++ + bound — reuse | `src/preflight.cpp`; `include/starling/preflight.hpp`; `include/starling/profile_capability.hpp`; `bind_01_core.cpp:110` |
| PipelineRun governance ledger (claim/confirm/reclaim/find_active_run, lease, checkpoint, watermark, stage_timings_ms, 9-state, DEAD_LETTERED) | ABSENT — the existing `pipeline_run` table is the **M0.4 extraction-cost ledger** (Started/Finished/Failed + extraction_attempt), a different thing | `include/starling/bus/pipeline_ledger.hpp`; `src/bus/pipeline_ledger.cpp:149` |
| ScopedWorkGate `(tenant, holder_scope, aggregate_id, lane)` reentrant gate, critical/soft quota, soft-drop accounting, leaked-lease sweep | ABSENT — background work gated only by global engine `RLock` + inline single-threaded `tick_all` | design-only `05_governance.md:53-169`; `dashboard/engine.py:114`; `src/memory/memory_ops.cpp:191-230` |
| RestartGuard dual-threshold → pause lane + emit DEGRADED | ABSENT | design-only `05_governance.md:34` |
| stage_timing (per-stage on PipelineRun.stage_timings_ms) | ABSENT — only incidental LLM round-trip latency | design-only `05_governance.md:47,85`; `src/extractor/openai_adapter.cpp:38-45` |
| Backpressure: sample 7 metrics → threshold → DEGRADED + `BusWriteResponse{runtime_degraded, projection_stale, retry_after}` | ABSENT | design-only `05_governance.md:31,108-109,171-179` |
| `TC-NEW-PREFLIGHT` [CRITICAL] — 4 fail-closed triggers + 6 post-conditions, drives the Python `Runtime` supervisor | GREEN today against Python supervisor; must stay green after relocation | `tests/python/test_tc_new_preflight.py` |

**Tick loop:** `memoryops::tick_all` (`src/memory/memory_ops.cpp:191-230`) runs the whole offline half-cycle inline, single-threaded: embed → policy → CommonGround → replay (oscillation-guard + ttl-sweep + run_idle) → projection → outbox. Driven by one daemon thread `start_background_tick` (`dashboard/engine.py:386-427`) under the global `RLock`. Replay background-thread mode is explicitly deferred (`replay_scheduler.cpp:397` "M0.9+").

---

## Target contracts (locked from 05_governance.md)

These are the contracts the C++ subsystem must realize. Field names/types are copied verbatim from the spec; C++ uses the obvious equivalents (`std::string`, `std::optional`, `std::int64_t`, `std::vector`, enums).

**RuntimeHealth state machine** (`05_governance.md:103-110`):
- `READY`: all hard caps preflight pass + lag/queue within SLA. Foreground r/w normal; background normal.
- `DEGRADED`: any of {outbox lag, projection lag, extraction queue depth, event-loop lag, subscriber failure rate} over threshold but main table available. Foreground writes continue, high-cost side-effects deferred, retrieval may downgrade to main-table / skip rerank; background pauses non-critical Replay/Projection, keeps Compliance/Commitment.
- `DRAINING`: process close / migration / profile switch / admin drain. Reject new background runs; foreground reads continue; writes return `retry_after`; workers stop claiming, finish leased tasks, exit when all leases released.
- `UNREADY`: capability preflight fail / main table unavailable / outbox uncommittable / tenant isolation missing → fail-closed, nothing starts.
- Event: `RuntimeHealthEvent{event_type="runtime.health_changed", previous_status, current_status, trigger, metrics_snapshot}`.

**PreflightResult** (`05_governance.md:133-137`): `{passed: bool, missing_capabilities: list[str], warnings: list[str]}`.

**PipelineRun** (`05_governance.md:64-91`): `kind ∈ {extraction, replay, projection_rebuild, container_rebuild, compliance_erase, retrieval_eval, migration}`, `aggregate_id`, `input_hash`, `idempotency_key`, `status ∈ {QUEUED, RUNNING, PAUSED, COMPLETED, PARTIAL_SUCCESS, DEGRADED_COMPLETED, FAILED, CANCELLED, DEAD_LETTERED}`, `checkpoint_sequence`, `watermark{last_outbox_sequence, last_sqlite_id, last_engram_cursor}`, `progress`, `counters`, `warnings`, `stage_timings_ms: list[dict]`, `retry_count`, `lease_until`, `started_at`, `updated_at`. (`step_contracts: list[dict] = []` — opaque in c1, validated in c2; see seam below.)

**PipelineRun operations** (`05_governance.md:141-153`): `claim(run_id, worker_id, lease_until)`, `confirm(run_id, checkpoint)`, `reclaim(run_id, worker_id, lease_until)`, `find_active_run(kind, aggregate_id, input_hash) -> Optional`.

**ScopedWorkGate** (`05_governance.md:155-169`): `gate_key = (tenant_id, holder_scope, aggregate_id, lane)`, `lane ∈ {"critical","soft"}`; `acquire(gate_key, task_id) -> int` (depth, reentrant same key); `release(gate_key, task_id)`; `sweep_leaked(now) -> list[run_id]`.

**Foreground degradation response** (`05_governance.md:171-179`): `BusWriteResponse{run_id?, runtime_degraded=false, projection_stale=false, retry_after?}`.

**Invariants** (`05_governance.md:181-190`) — must be enforced by the writers:
1. No two active runs (QUEUED|RUNNING) for the same `(kind, aggregate_id, input_hash)`.
2. Compliance erase / outbox delivery / commitment fire `failure_policy` is fixed `critical`, never overridable.
3. Projection rebuild uses shadow table + atomic swap (no in-place replace of active projection). *(Projection internals are c2/existing; c1 enforces the run-status contract only.)*
4. `DEAD_LETTERED` Compliance-lane run must alarm + hold RuntimeHealth at DEGRADED/UNREADY, never silent.
5. soft-lane drop must retain outbox/watermark rebuild basis + increment `dropped_soft_work_count`.
6. full/redacted_debug trace not persisted as EngramStore evidence; on compliance erase, trace raw payload redacted/crypto-erased. *(Trace retention is the deferred slice — see seam.)*
7. `business_task_id`-aggregated multi-item runs: ≥1 success & ≥1 fail → PARTIAL_SUCCESS; all NOOP → NOOP, never SUCCESS.
8. Pipeline mutation produces a new revision only; `step_contracts` validation (upstream produces ⊇ downstream requires; profile caps ⊇ step caps) gates run start. *(step_contracts validation is c2; see seam.)*

**Seams explicitly deferred out of c1** (justified, not placeholders):
- **PipelineStepContract complete step-graph validation (invariant 8)** → **c2** (Substrate). c1's `PipelineRun.step_contracts` is an opaque `list[dict]` field present in the schema but unvalidated, exactly as the spec annotates ("P3 启用；P1 不启用通用 step graph", `05_governance.md:77`).
- **Trace retention 分级 (invariant 6, `05_governance.md:112-119`)** → deferred to a c1.5 / P3+ follow-up; c1 ships the production default `metadata_only` (step name, duration, status, hash, counts — which `stage_timings_ms` already provides) and does NOT build hash_only/redacted_debug/full_debug tiers. Flagged for eng-review.
- **True multi-lane worker concurrency** → the tick loop stays single-threaded in c1 (`replay_scheduler.cpp:397` already defers background-thread mode). ScopedWorkGate is built as an admission-control + reentrancy + leaked-lease layer whose quotas are *correct under concurrency* but trivially satisfied while single-threaded. Real concurrent lanes are P3+. Flagged for eng-review.

---

## Architecture & file structure

New C++ subsystem `src/governance/` + `include/starling/governance/`. Files (one clear responsibility each):

- `include/starling/governance/capability_policy.hpp` + `src/governance/capability_policy.cpp` — `kLocalStoreRequired` (7 caps), `kEmbeddedDeferredCaps` (2 caps), and a **pure** `required_capabilities(bool embedded) -> std::vector<std::string>` (replaces `relax_preflight_for_embedded()`'s global mutation).
- `include/starling/governance/runtime_supervisor.hpp` + `src/governance/runtime_supervisor.cpp` — the supervisor: owns policy + `RuntimeHealthMonitor`, runs preflight (reuse `preflight()` + index check), drives state transitions, owns `exit_code()` (EX_CONFIG on fail-closed), the READY write-gate, signal-free drain entry (`begin_drain()`), and event log. **No threads, no signal handling** (host owns those).
- Reuse + extend `include/starling/runtime_health.hpp` + `src/runtime_health.cpp` — add `set_degraded(trigger, snapshot)` / `set_draining(trigger)` / transition validation + event emission; make the monitor's mutators safe for the single supervisor caller.
- `include/starling/governance/pipeline_run.hpp` — the `PipelineRun` struct + `PipelineRunStatus` / `PipelineKind` enums + `Watermark` struct.
- `include/starling/governance/pipeline_run_store.hpp` + `src/governance/pipeline_run_store.cpp` — single-writer store over a **new** SQLite table `governance_pipeline_run` (distinct from M0.4 `pipeline_run`). `claim/confirm/reclaim/find_active_run` + `record_stage_timing` + `dead_letter`. find-active-run dedup via the writer (invariant 1), not a caller set.
- `include/starling/governance/scoped_work_gate.hpp` + `src/governance/scoped_work_gate.cpp` — in-memory reentrant gate keyed by `(tenant_id, holder_scope, aggregate_id, lane)`; critical/soft quota; `dropped_soft_work_count`; `sweep_leaked(now)`.
- `include/starling/governance/restart_guard.hpp` + `src/governance/restart_guard.cpp` — dual-threshold (sliding-window restart count + consecutive no-success) per worker lane → `should_pause_lane()` + emits DEGRADED via the supervisor.
- `include/starling/governance/stage_timer.hpp` — RAII `StageTimer` that records `{stage, ms}` into a `PipelineRun` on scope exit (uses `steady_clock` like the existing latency capture).
- `include/starling/governance/health_sampler.hpp` + `src/governance/health_sampler.cpp` — takes a `MetricsSnapshot{outbox_lag_sequence, subscriber_failure_rate, extraction_queue_depth, projection_lag_seconds, runtime_event_loop_lag_ms, vector_delete_lag, erased_evidence_visible_count}` + threshold table → `HealthDecision{target_status, trigger}`. Host feeds `runtime_event_loop_lag_ms`; C++ stores feed the rest.
- `bindings/python/bind_14_governance.cpp` — bind `RuntimeSupervisor`, `RuntimeHealthMonitor`, `PreflightResult`, `MetricsSnapshot`, `PipelineRunStore`, `ScopedWorkGate` (follows the numbered bind-unit pattern from the 12-unit `module.cpp` split).
- **Migration:** new migration adding `governance_pipeline_run` (+ indices) under the existing migration dir; bump schema version.

Python adapter (thin):
- `python/starling/runtime.py` — collapses from the M0.0 supervisor to a thin forwarder: `Runtime` becomes a shim whose `start()/health()/exit_code/state` delegate to `_core` `RuntimeSupervisor`; keeps `RuntimeUnreadyError`, `EX_CONFIG` re-export, and the `bus` READY-gate facade shape so `TC-NEW-PREFLIGHT` changes minimally. `relax_preflight_for_embedded()` becomes `required_capabilities(embedded=True)` forwarding (no global mutation).
- `python/starling/dashboard/app.py` + `engine.py` — host embedding: register SIGTERM/SIGINT → `supervisor.begin_drain()`; feed `runtime_event_loop_lag_ms` into the sampler; surface health to the dashboard read path.

Dashboard read path (read-only, allowed in Python/TS):
- `python/starling/dashboard/routes/` — extend `GET /health` (or new `GET /api/runtime/health`) to return the 4-state status + last event + metrics snapshot.
- `dashboard/web/src/routes/` — a read-only RuntimeHealth panel (status badge + metrics + recent transitions), mirroring the existing vitals page pattern (`de11c05`).

---

## Internal phasing

c1 is sequenced contracts-first; each phase ends green (ctest + pytest). Per roadmap cascade rule (line 176), Phase 1 is detailed to TDD-task level now; Phases 2–5 are specified at file/interface/acceptance level and get their bite-sized steps detailed once the prior phase's schema lands.

- **Phase 1 — Governance core relocation [CRITICAL].** `capability_policy` + `RuntimeSupervisor` + index preflight in C++; `runtime.py` → thin forwarder; `TC-NEW-PREFLIGHT` green against the relocated core. Clears the one boundary violation. *(Detailed below.)*
- **Phase 2 — RuntimeHealth full state machine.** Extend the monitor with DEGRADED/DRAINING + transition validation + `runtime.health_changed` events; `begin_drain()`; host signal wiring; read-only dashboard health panel.
- **Phase 3 — PipelineRun governance ledger + stage_timing.** `governance_pipeline_run` table + store (claim/confirm/reclaim/find_active_run/dead_letter), `StageTimer`, wire stage timings into the tick/replay stages; enforce invariants 1, 2, 4, 7.
- **Phase 4 — ScopedWorkGate + RestartGuard.** Build the gate + restart guard; route the existing background pumps (replay/embedding/consolidation/projection/outbox) through gate admission; critical/soft quota; soft-drop accounting; leaked-lease sweep; RestartGuard → pause lane + DEGRADED.
- **Phase 5 — Backpressure + drain integration.** `health_sampler` 7-metric thresholds → DEGRADED; `BusWriteResponse` degradation fields; DRAINING `retry_after`; end-to-end: DEGRADED pauses soft lanes, DRAINING refuses new runs + finishes leases.

**Admission gate (规模化负载测试)** is phase-level for all of P3.c, run after c1+c2+c3; it exercises c1's backpressure/health/gate under load. Not a c1-internal task; noted here so the c1 surfaces (metrics snapshot, gate counters, health events) are observable for that test.

---

## Phase 1 — Governance core relocation [CRITICAL]

**Outcome:** C++ owns capability policy + preflight (incl. index check) + READY/UNREADY + exit-78 + READY write-gate; `python/starling/runtime.py` is a thin forwarder; `TC-NEW-PREFLIGHT` and `test_preflight` green; no governance algorithm remains in Python.

### LOCKED eng-review amendments (2026-06-28) — these SUPERSEDE the Task code below where they conflict

The /plan-eng-review pass (codex outside-voice, cross-model consensus) locked four decisions (D1–D4) and absorbed 10 codex findings. Apply ALL of these when implementing Phase 1:

- **[D1] Phase 1 ships as its own milestone/PR.** Phases 2–5 stay in this doc as the c1 roadmap, each detailed + executed as a sequenced follow-up once its predecessor's schema lands.
- **[D2] idx preflight = C++ IndexProbe, not a Python-supplied callable.** `RuntimeSupervisor`'s PRODUCTION constructor takes a C++ probe — a reference to the `starling::persistence::SqliteAdapter` (or a narrow `IndexProbe` interface it implements) — and calls `adapter.has_index("idx_statement_id_tenant")`. The `std::function<bool()>` constructor is kept ONLY as a C++ unit-test seam. The Python forwarder passes the bound adapter handle, NOT a Python lambda — so no governance decision routes through Python.
- **[codex #4] Adapter path/namespace (VERIFIED).** It is `include/starling/persistence/sqlite_adapter.hpp` / `src/persistence/sqlite_adapter.cpp`, namespace `starling::persistence` — NOT `include/starling/store/...`. `has_index` does not exist yet; add it (`:13` comment already claims the open path guarantees `idx_statement_id_tenant`). Fix every `store/sqlite_adapter` reference in the tasks below.
- **[codex #6] Reuse the existing `PreflightResult` (VERIFIED).** `include/starling/preflight.hpp:24` already defines `struct PreflightResult { PreflightStatus status; std::vector<std::string> missing; }`. Do NOT redefine it. The supervisor may expose a thin `PreflightReport{passed, missing_capabilities, warnings}` that WRAPS/maps the existing `PreflightResult` (passed = status==OK; missing_capabilities = missing; warnings = its own additions like the index name) — and the wrapper must be justified as a supervisor-level view, not a parallel core type.
- **[codex #5] Bindings are flat `_core` (VERIFIED — `module.cpp` has no governance submodule).** Bind the supervisor as `_core.RuntimeSupervisor` (flat, matching every existing class), NOT `_core.governance.RuntimeSupervisor`. Do not introduce a new pybind submodule in Phase 1.
- **[codex #2] The READY write-gate must delegate to C++.** The current Python `_StubBus`/`_SqliteBackedBus` enforce the gate by checking `health()==READY` in Python (`runtime.py:72-117`). The rewritten forwarder bus must call the C++ `RuntimeSupervisor::check_write()` (returns accept / PRECONDITION_FAILED) — it must NOT re-implement the READY check in Python, or governance stays in Python. (Note: this is the readiness write-gate only; the full DEGRADED/DRAINING write semantics + `retry_after` on the real C++ `Bus::write` path are Phase 5 — see NOT-in-scope.)
- **[codex #7 + #9] Trim Phase 1 — do NOT revive `RuntimeHealthMonitor` or build an event log.** For Phase 1 the supervisor holds its OWN internal `RuntimeHealth` state (READY/UNREADY only) as a plain member. The dead `RuntimeHealthMonitor` revival, the `RuntimeHealthEvent` struct/log, and `events()` are Phase 2 (full state machine). **DELETE the `EmitsExactlyOneHealthChanged` test from Task 1.3** — Phase 1 does not test `events()`. Minimal Phase 1 = capability policy + adapter `has_index` + supervisor readiness/exit-78/write-gate + Python forwarder.
- **[codex #10] Label the index check a legacy compat check, not a tenant-isolation proof.** A comment must state: `has_index("idx_statement_id_tenant")` proves a named index EXISTS; it does not prove tenant-isolation semantics (codex memory flags prior tenant-scoping bugs `(id, tenant_id)`). It is kept because `TC-NEW-PREFLIGHT` pins it.
- **[D3 + D4] Eliminate the boundary violation now via inert forwarders; sweep the legacy NAMES in a separate follow-up.** The actual violation = C++ governance reading a *mutable Python global*. Once C++ owns `required_capabilities()` + preflight, the Python `LOCAL_STORE_REQUIRED` becomes a read-only forwarder (`= tuple(required_capabilities(embedded=False))`) that NO governance code reads; `relax_preflight_for_embedded()` / `relax_preflight_for_m0_*()` return `tuple(required_capabilities(embedded=True))` with no global mutation; `idx_statement_id_tenant_present` stays as the injectable test-seam forwarding to the bound `has_index`. Result: the ~41 test files that mutate/restore `LOCAL_STORE_REQUIRED` and the 3 that use the idx attribute all stay GREEN UNCHANGED in this PR, and the violation is gone.
  - **Follow-up F1 (separate PR, registered):** mechanical sweep removing the legacy `LOCAL_STORE_REQUIRED` mutate/restore pattern from the ~41 test files + the `relax_*` helper names, replacing them with a non-mutating test fixture. Not in the Phase-1 PR (keeps the relocation diff clean + reviewable).
- **[Section-3 test adds]** Add two C++ supervisor unit tests to Task 1.3: `UnreadyWhenCapabilityMissing` (UNREADY triggered by a missing CAPABILITY, e.g. `transactional_outbox=false`, not just a missing index) and `EmbeddedStartReadyWithoutDeferredCaps` (`embedded=true` start reaches READY with the 2 deferred caps dropped).

### Task 1.1: Capability policy in C++ (pure, no global mutation)

**Files:**
- Create: `include/starling/governance/capability_policy.hpp`
- Create: `src/governance/capability_policy.cpp`
- Test: `tests/cpp/test_capability_policy.cpp`
- Modify: `CMakeLists.txt` (add `src/governance/capability_policy.cpp` to the core lib; add the test target)

**Interfaces:**
- Produces: `starling::governance::required_capabilities(bool embedded) -> std::vector<std::string>`; constants `kLocalStoreRequired` (7), `kEmbeddedDeferredCaps` (2).

- [ ] **Step 1: Write the failing test** — `tests/cpp/test_capability_policy.cpp`

```cpp
#include "starling/governance/capability_policy.hpp"
#include <gtest/gtest.h>
#include <algorithm>

namespace {
using starling::governance::required_capabilities;

TEST(CapabilityPolicy, FullProfileRequiresAllSeven) {
  const auto req = required_capabilities(/*embedded=*/false);
  EXPECT_EQ(req.size(), 7U);
  EXPECT_NE(std::find(req.begin(), req.end(), "engram_per_record_key"), req.end());
  EXPECT_NE(std::find(req.begin(), req.end(), "testing_helper_marker"), req.end());
}

TEST(CapabilityPolicy, EmbeddedDropsDeferredCapsButKeepsHardCaps) {
  const auto req = required_capabilities(/*embedded=*/true);
  EXPECT_EQ(req.size(), 5U);
  EXPECT_EQ(std::find(req.begin(), req.end(), "engram_per_record_key"), req.end());
  EXPECT_EQ(std::find(req.begin(), req.end(), "testing_helper_marker"), req.end());
  EXPECT_NE(std::find(req.begin(), req.end(), "transactional_outbox"), req.end());
  EXPECT_NE(std::find(req.begin(), req.end(), "cross_partition_transaction"), req.end());
}

TEST(CapabilityPolicy, RepeatedCallsDoNotMutateState) {
  const auto a = required_capabilities(true);
  const auto b = required_capabilities(false);
  EXPECT_EQ(a.size(), 5U);
  EXPECT_EQ(b.size(), 7U);  // calling embedded first must not have shrunk the full list
}
}  // namespace
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python scripts/configure_build.py --build` then `ctest --test-dir build-macos -R CapabilityPolicy`
Expected: FAIL — `capability_policy.hpp` not found / target missing.

- [ ] **Step 3: Write minimal implementation**

`include/starling/governance/capability_policy.hpp`:
```cpp
#ifndef STARLING_GOVERNANCE_CAPABILITY_POLICY_HPP
#define STARLING_GOVERNANCE_CAPABILITY_POLICY_HPP

#include <array>
#include <string>
#include <string_view>
#include <vector>

namespace starling::governance {

// The 7 hard capabilities required by the local-store profile (was runtime.py:19-27).
inline constexpr std::array<std::string_view, 7> kLocalStoreRequired = {
    "transactional_outbox", "consumer_checkpoint", "engram_per_record_key",
    "c_plus_plus_core", "cross_partition_transaction",
    "tenant_isolation_storage_enforced", "testing_helper_marker"};

// Capabilities waived in embedded mode (was runtime.py:36 _EMBEDDED_DEFERRED_CAPS).
inline constexpr std::array<std::string_view, 2> kEmbeddedDeferredCaps = {
    "engram_per_record_key", "testing_helper_marker"};

// Effective required-list for a profile. Pure: no global mutation
// (replaces runtime.py:39-52 relax_preflight_for_embedded's global rewrite).
std::vector<std::string> required_capabilities(bool embedded);

}  // namespace starling::governance

#endif
```

`src/governance/capability_policy.cpp`:
```cpp
#include "starling/governance/capability_policy.hpp"

#include <algorithm>

namespace starling::governance {

std::vector<std::string> required_capabilities(bool embedded) {
  std::vector<std::string> result;
  result.reserve(kLocalStoreRequired.size());
  for (const auto cap : kLocalStoreRequired) {
    const bool deferred = std::find(kEmbeddedDeferredCaps.begin(),
                                    kEmbeddedDeferredCaps.end(), cap) !=
                          kEmbeddedDeferredCaps.end();
    if (embedded && deferred) {
      continue;
    }
    result.emplace_back(cap);
  }
  return result;
}

}  // namespace starling::governance
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python scripts/configure_build.py --build` then `ctest --test-dir build-macos -R CapabilityPolicy`
Expected: PASS (3/3).

- [ ] **Step 5: Commit**

```bash
git add include/starling/governance/capability_policy.hpp src/governance/capability_policy.cpp tests/cpp/test_capability_policy.cpp CMakeLists.txt
git commit -m "feat(P3/c1): C++ capability policy — pure required_capabilities, no global mutation"
```

### Task 1.2: Index preflight folded into the SQLite adapter

**Files:**
- Modify: `include/starling/persistence/sqlite_adapter.hpp` (ns `starling::persistence`; `:13` comment already claims the open path guarantees `idx_statement_id_tenant`)
- Modify: `src/persistence/sqlite_adapter.cpp`
- Test: `tests/cpp/test_sqlite_adapter_index_preflight.cpp`

**Interfaces:**
- Produces: `bool SqliteAdapter::has_index(std::string_view name) const;` — queries `sqlite_master WHERE type='index' AND name=?` (relocates the raw `sqlite3` read from `runtime.py:220-227`).

- [ ] **Step 1: Write the failing test** — open an adapter on a temp DB, assert `has_index("idx_statement_id_tenant")` is true after schema init; assert false for a bogus name. (Use the existing C++ test DB fixture pattern from `tests/cpp/`.)

```cpp
#include "starling/store/sqlite_adapter.hpp"
#include <gtest/gtest.h>

TEST(SqliteAdapterIndexPreflight, ReportsSchemaIndexPresence) {
  // <use existing temp-DB + schema-init fixture>
  auto adapter = /* open temp adapter with schema applied */;
  EXPECT_TRUE(adapter.has_index("idx_statement_id_tenant"));
  EXPECT_FALSE(adapter.has_index("idx_does_not_exist"));
}
```

- [ ] **Step 2: Run test to verify it fails** — Run: `ctest --test-dir build-macos -R SqliteAdapterIndexPreflight`; Expected: FAIL (`has_index` undefined).
- [ ] **Step 3: Implement `has_index`** — prepared statement `SELECT 1 FROM sqlite_master WHERE type='index' AND name=?1 LIMIT 1`, return whether a row exists. Reuse the adapter's existing prepared-statement helper; no raw `sqlite3_*` if a wrapper exists.
- [ ] **Step 4: Run test to verify it passes** — Expected: PASS.
- [ ] **Step 5: Commit** — `git add` the three paths; `feat(P3/c1): SqliteAdapter::has_index — relocate idx preflight read from Python`.

### Task 1.3: RuntimeSupervisor — preflight → READY/UNREADY + exit 78 + write-gate (C++)

**Files:**
- Create: `include/starling/governance/runtime_supervisor.hpp`
- Create: `src/governance/runtime_supervisor.cpp`
- Test: `tests/cpp/test_runtime_supervisor.cpp`
- Modify: `CMakeLists.txt`

**Interfaces:**
- Consumes: `required_capabilities(bool)` (1.1); `preflight(ProfileCapability, required)` → `PreflightResult{passed, missing, warnings}` (`include/starling/preflight.hpp`); `SqliteAdapter::has_index` (1.2) via an injected `std::function<bool()> idx_present`; `RuntimeHealth` enum (`include/starling/runtime_health.hpp`).
- Produces:
```cpp
namespace starling::governance {
inline constexpr int kExConfig = 78;  // EX_CONFIG, was runtime.py:15

enum class StartOutcome { kReady, kUnready };

struct PreflightReport {           // mirrors PreflightResult (05_governance.md:133-137)
  bool passed = false;
  std::vector<std::string> missing_capabilities;
  std::vector<std::string> warnings;
};

enum class WriteGateDecision { kAccept, kPreconditionFailed };

class RuntimeSupervisor {
 public:
  RuntimeSupervisor(ProfileCapability caps, bool embedded,
                    std::function<bool()> idx_present);
  PreflightReport run_preflight() const;   // caps + index → missing list
  StartOutcome start();                    // preflight → READY or UNREADY(+exit 78)
  RuntimeHealth health() const;
  int exit_code() const;                   // kExConfig on fail-closed, else 0
  WriteGateDecision check_write() const;   // kPreconditionFailed unless READY
  const std::vector<RuntimeHealthEvent>& events() const;
};
}  // namespace starling::governance
```

- [ ] **Step 1: Write the failing test** — `tests/cpp/test_runtime_supervisor.cpp`, mirroring `TC-NEW-PREFLIGHT`'s C++-side equivalents:

```cpp
#include "starling/governance/runtime_supervisor.hpp"
#include <gtest/gtest.h>

namespace {
using namespace starling;
using governance::RuntimeSupervisor;
using governance::StartOutcome;
using governance::WriteGateDecision;

ProfileCapability all_present() {
  ProfileCapability c;          // set every hard cap true / storage-enforced
  // <fill per profile_capability.hpp fields>
  return c;
}

TEST(RuntimeSupervisor, UnreadyWhenIndexMissingSetsExit78) {
  RuntimeSupervisor sup(all_present(), /*embedded=*/false, [] { return false; });
  EXPECT_EQ(sup.start(), StartOutcome::kUnready);
  EXPECT_EQ(sup.health(), RuntimeHealth::UNREADY);
  EXPECT_EQ(sup.exit_code(), governance::kExConfig);
  const auto report = sup.run_preflight();
  EXPECT_NE(std::find(report.missing_capabilities.begin(),
                      report.missing_capabilities.end(),
                      "idx_statement_id_tenant"),
            report.missing_capabilities.end());
}

TEST(RuntimeSupervisor, ReadyWhenAllPresentAcceptsWrites) {
  RuntimeSupervisor sup(all_present(), /*embedded=*/false, [] { return true; });
  EXPECT_EQ(sup.start(), StartOutcome::kReady);
  EXPECT_EQ(sup.health(), RuntimeHealth::READY);
  EXPECT_EQ(sup.exit_code(), 0);
  EXPECT_EQ(sup.check_write(), WriteGateDecision::kAccept);
}

TEST(RuntimeSupervisor, WriteGateFailsClosedBeforeReady) {
  RuntimeSupervisor sup(all_present(), false, [] { return false; });
  EXPECT_EQ(sup.check_write(), WriteGateDecision::kPreconditionFailed);  // before start()
  sup.start();
  EXPECT_EQ(sup.check_write(), WriteGateDecision::kPreconditionFailed);  // UNREADY
}

TEST(RuntimeSupervisor, EmitsExactlyOneHealthChangedOnUnready) {
  RuntimeSupervisor sup(all_present(), false, [] { return false; });
  sup.start();
  ASSERT_EQ(sup.events().size(), 1U);
  EXPECT_EQ(sup.events().front().current_status, RuntimeHealth::UNREADY);
}
}  // namespace
```

- [ ] **Step 2: Run test to verify it fails** — Run: `ctest --test-dir build-macos -R RuntimeSupervisor`; Expected: FAIL (header missing).
- [ ] **Step 3: Implement `RuntimeSupervisor`** — `run_preflight()`: build `required_capabilities(embedded_)`, call `preflight(caps_, required)`, then append `"idx_statement_id_tenant"` to `missing` when `!idx_present_()`. `start()`: if `run_preflight().passed` → set READY (push READY event), else set UNREADY (set `exit_code_ = kExConfig`, push UNREADY event). `exit_code_` is set once and never cleared (fail-closed, mirrors `runtime.py:170-171`). `check_write()`: `kAccept` iff `health_ == READY`. Keep `start()` under cognitive-complexity 25 (extract `compute_missing()` helper if needed).
- [ ] **Step 4: Run test to verify it passes** — Expected: PASS (4/4).
- [ ] **Step 5: Commit** — `feat(P3/c1): RuntimeSupervisor — C++ preflight/readiness/exit-78/write-gate`.

### Task 1.4: Bind the supervisor + relocate `runtime.py` to a thin forwarder

**Files:**
- Create: `bindings/python/bind_14_governance.cpp` (bind `RuntimeSupervisor`, `PreflightReport`, `StartOutcome`, `WriteGateDecision`, `kExConfig`)
- Modify: `bindings/python/module.cpp` (register the new bind unit)
- Modify: `python/starling/runtime.py` (collapse `Runtime` to a forwarder; `required_capabilities` forwarding; keep `RuntimeUnreadyError`, `EX_CONFIG`, READY-gate `bus` facade shape)
- Modify: `python/starling/testing/__init__.py` (`relax_preflight_for_*` → forward to `required_capabilities(embedded=True)`)
- Test: `tests/python/test_tc_new_preflight.py` (keep behavior; update only construction wiring if needed), `tests/python/test_preflight.py`

**Interfaces:**
- Consumes: `_core.governance.RuntimeSupervisor` (from 1.3).
- Produces: Python `Runtime` facade with unchanged public surface: `start()` raises `RuntimeUnreadyError(missing_capabilities)` on UNREADY and sets `.exit_code == EX_CONFIG`; `.health()`; `.state`; `foreground_workers_started` / `background_workers_started`; `bus.write/append_evidence` return `"PRECONDITION_FAILED"` until READY.

- [ ] **Step 1: Run `TC-NEW-PREFLIGHT` against current Python supervisor to capture the green baseline** — Run: `pytest tests/python/test_tc_new_preflight.py -v`; Expected: PASS (baseline before relocation).
- [ ] **Step 2: Write/extend the failing binding test** — a small `tests/python/test_governance_binding.py` asserting `from starling._core.governance import RuntimeSupervisor` imports and an all-caps + `idx_present=True` instance starts READY; Expected: FAIL (module absent).
- [ ] **Step 3: Implement `bind_14_governance.cpp`** — expose the supervisor; map `StartOutcome`/`WriteGateDecision` to Python enums or strings; expose `events()` as a list of dicts `{previous_status, current_status, trigger}`. Register in `module.cpp`. Rebuild: `python scripts/configure_build.py --build --python-editable`.
- [ ] **Step 4: Rewrite `runtime.py` `Runtime` as a forwarder** — construct `_core.governance.RuntimeSupervisor(caps, embedded, idx_present)`; `start()` calls `sup.start()`, on `kUnready` raises `RuntimeUnreadyError(sup.run_preflight().missing_capabilities)` and sets `self.exit_code = EX_CONFIG`, on `kReady` flips `foreground/background_workers_started = True`; emit the `runtime.health_changed` event from `sup.events()`. Delete `LOCAL_STORE_REQUIRED` global + `_EMBEDDED_DEFERRED_CAPS` + `relax_preflight_for_embedded` mutation + the nested `_idx_present` raw-sqlite read (now `SqliteAdapter::has_index` via the bound supervisor's `idx_present`); keep a `required_capabilities(embedded)` thin wrapper for callers/tests.
- [ ] **Step 5: Run `TC-NEW-PREFLIGHT` + `test_preflight` + binding test** — Run: `pytest tests/python/test_tc_new_preflight.py tests/python/test_preflight.py tests/python/test_governance_binding.py -v`; Expected: PASS. Fix wiring (not assertions) until green.
- [ ] **Step 6: Full gate + commit** — Run: `python scripts/configure_build.py --build --test --python-editable` then `pytest tests/python`; Expected: all green. Commit:

```bash
git add bindings/python/bind_14_governance.cpp bindings/python/module.cpp python/starling/runtime.py python/starling/testing/__init__.py tests/python/test_governance_binding.py
git commit -m "feat(P3/c1): relocate runtime governance to C++ supervisor; runtime.py thin forwarder"
```

### Task 1.5: Boundary-audit sweep + roadmap/docs sync

**Files:**
- Modify: `python/starling/memory.py:137-139`, `python/starling/dashboard/engine.py:108-118` (bootstrap calls → forward to the C++-backed `Runtime`; confirm no governance algorithm remains)
- Modify: `docs/design/subsystems_design/05_governance.md` (mark preflight/capability-policy/index-preflight/write-gate as C++-owned; note Python is forwarder)
- Modify: `docs/superpowers/plans/2026-05-23-roadmap.md` (P3.c row: mark c1 Phase 1 [CRITICAL relocation] done with commit refs; clear "runtime.py 治理语义唯一遗留")

- [ ] **Step 1:** grep Python tree for residual governance logic — `rg -n "LOCAL_STORE_REQUIRED|relax_preflight|sqlite_master|EX_CONFIG|idx_statement_id_tenant" python/` — confirm only thin forwarders / re-exports remain (no required-list, no global mutation, no raw index read).
- [ ] **Step 2:** Update the two bootstrap callers to use the forwarder; rerun `pytest tests/python` green.
- [ ] **Step 3:** Sync `05_governance.md` + roadmap; `git add` the doc paths + the two Python paths; commit `docs(P3/c1): sync governance boundary relocation; runtime.py governance leftover cleared`.

**Phase 1 acceptance:** `TC-NEW-PREFLIGHT` + `test_preflight` green against the C++-backed forwarder; no capability list / preflight algorithm / exit-78 / raw index read remains in Python; full ctest + pytest green; the roadmap "runtime.py 治理语义唯一遗留" line is cleared.

---

## Phase 2 — RuntimeHealth full state machine (file/interface level; TDD detailed after Phase 1 lands)

**Deliverable:** the 4-state machine fully reachable with validated transitions + events + drain entry, plus a read-only dashboard surface.

**Files:** extend `include/starling/runtime_health.hpp` + `src/runtime_health.cpp` (add `set_degraded(trigger, MetricsSnapshot)`, `set_draining(trigger)`, transition guards); `runtime_supervisor.{hpp,cpp}` (`begin_drain()`, `note_health(HealthDecision)`); `bind_14_governance.cpp` (bind new mutators + `MetricsSnapshot`); `python/starling/dashboard/app.py` (SIGTERM/SIGINT → `begin_drain()`) + a read route; `dashboard/web/src/routes/` health panel.

**Interfaces:** `RuntimeHealthMonitor::set_degraded(std::string trigger, MetricsSnapshot)`, `set_draining(std::string trigger)`, `set_ready()`, `set_unready(missing)`; legal transitions only (READY↔DEGRADED, READY/DEGRADED→DRAINING→exit, any→UNREADY); each transition pushes a `RuntimeHealthEvent{previous_status, current_status, trigger, metrics_snapshot}`. Illegal transitions are rejected (assert/no-op + warning).

**Acceptance:** C++ tests for every legal/illegal transition + event payload; `GET /api/runtime/health` returns status + last event + snapshot; dashboard panel renders the badge; ctest + pytest + (front-end) check/vitest/build green.

**Cascade note:** `MetricsSnapshot` fields are finalized here and consumed by Phase 5's sampler; this phase ships the transition mechanics with manual/test triggers, Phase 5 wires real metric sampling.

---

## Phase 3 — PipelineRun governance ledger + stage_timing (file/interface level; TDD detailed after Phase 2 lands)

**Deliverable:** the governance long-task ledger with lease/checkpoint/reclaim + per-stage timing, distinct from the M0.4 extraction ledger.

**Files:** `include/starling/governance/pipeline_run.hpp`, `pipeline_run_store.{hpp,cpp}`, `stage_timer.hpp`; a migration adding `governance_pipeline_run`; `bind_14_governance.cpp`; wire `StageTimer` into `src/memory/memory_ops.cpp` tick stages + `src/replay/replay_scheduler.cpp`.

**Interfaces:** `PipelineRunStore::claim(run_id, worker_id, lease_until) -> PipelineRun`, `confirm(run_id, checkpoint) -> PipelineRun`, `reclaim(run_id, worker_id, lease_until) -> PipelineRun`, `find_active_run(kind, aggregate_id, input_hash) -> std::optional<PipelineRun>`, `dead_letter(run_id, error_kind)`, `record_stage_timing(run_id, stage, ms)`. Writer enforces invariant 1 (INSERT-then-detect dup-active), invariant 7 (NOOP vs PARTIAL_SUCCESS roll-up), invariant 2/4 (critical `failure_policy` fixed; DEAD_LETTERED compliance run holds DEGRADED).

**Acceptance:** C++ tests for claim/lease-expiry/reclaim-resume, find-active dedup, dead-letter→DEGRADED hold, NOOP roll-up; stage timings recorded for a tick cycle; ctest + pytest green.

**Cascade note:** `step_contracts` is an opaque `list[dict]` field here; its validation (invariant 8) is c2.

---

## Phase 4 — ScopedWorkGate + RestartGuard (file/interface level; TDD detailed after Phase 3 lands)

**Deliverable:** scoped admission/reentrancy gate + crash-loop guard, with the existing pumps routed through admission.

**Files:** `include/starling/governance/scoped_work_gate.{hpp,cpp}`, `restart_guard.{hpp,cpp}`; `bind_14_governance.cpp`; gate-acquire wrapping in `src/memory/memory_ops.cpp` pump calls.

**Interfaces:** `ScopedWorkGate::acquire(GateKey, task_id) -> int`, `release(GateKey, task_id)`, `sweep_leaked(now) -> std::vector<std::string>`, `dropped_soft_work_count()`; `GateKey{tenant_id, holder_scope, aggregate_id, lane}` with `lane ∈ {kCritical, kSoft}`; `RestartGuard::record_restart()/record_no_success()/record_success()`, `should_pause_lane() -> bool`. Critical lane has reserved quota; soft-lane over-quota drops a rebuildable task + increments `dropped_soft_work_count` (invariant 5); never drops outbox/compliance-erase/commitment-fire/extraction-terminal.

**Acceptance:** C++ tests for reentrant depth, cross-aggregate slot consumption, critical-quota protection, soft-drop accounting, leaked-lease sweep emitting DEGRADED, RestartGuard dual-threshold pause; pumps still complete a tick cycle under the gate; ctest + pytest green.

---

## Phase 5 — Backpressure + drain integration (file/interface level; TDD detailed after Phase 4 lands)

**Deliverable:** metric-driven DEGRADED + DRAINING `retry_after`, wired end-to-end.

**Files:** `include/starling/governance/health_sampler.{hpp,cpp}`; `bind_14_governance.cpp`; `python/starling/dashboard/{app.py,engine.py}` (feed `runtime_event_loop_lag_ms`, drive `sample → note_health` on the tick); `BusWriteResponse` degradation fields on the write path.

**Interfaces:** `HealthSampler::evaluate(MetricsSnapshot) -> HealthDecision{target_status, trigger}` per the `05_governance.md:108` threshold table; supervisor `note_health(HealthDecision)` applies the transition; `BusWriteResponse{run_id?, runtime_degraded, projection_stale, retry_after}` populated from current health.

**Acceptance:** each of the 7 metrics over threshold drives READY→DEGRADED with the right trigger; recovery returns to READY; DRAINING write returns `retry_after` and refuses new background runs while finishing leases; DEGRADED pauses soft lanes but keeps critical; end-to-end ctest + pytest green. (Surfaces are then exercised by the P3.c phase-level 规模化负载测试.)

---

## Open questions — eng-review resolution (2026-06-28)

**Resolved this review (Phase-1-relevant):**
- **Q5 Host/core split — RESOLVED by [D2].** Governance DECISION logic is C++ (the supervisor owns policy + preflight + readiness + the index probe via a C++ `IndexProbe`); the host (FastAPI / `Memory.open`) owns only embedding (signals + tick thread + host-side metrics), which land in Phase 2/5. The "治理内核 C++ vs 宿主进程嵌入" cut is confirmed: no governance input crosses through Python.
- **Q6 TC-NEW-PREFLIGHT — CONFIRMED.** Keep it driving the Python `Runtime` forwarder as the [CRITICAL] end-to-end behavioral pin; add C++ supervisor unit tests separately (Task 1.3). No rewrite.

**Deferred to their owning phase (NOT Phase-1 questions):**
1. **Concurrency scope** (ScopedWorkGate admission-only vs real multi-lane concurrency) → decide in the **Phase 4** plan.
2. **PipelineStepContract / invariant 8** (opaque `step_contracts` in c1) → the c1→c2 seam, decide in the **c2** plan.
3. **Trace retention 分级 (invariant 6)** (`metadata_only` default vs full tier set) → decide in the **Phase 5 / c1.5** plan.
4. **`governance_pipeline_run` new table** vs extending the M0.4 `pipeline_run` → decide in the **Phase 3** plan (plan proposes a NEW table to avoid colliding with the extraction-cost ledger).

---

## Self-review

**Spec coverage** (against `05_governance.md`): preflight + UNREADY fail-closed → Phase 1; READY/DEGRADED/DRAINING/UNREADY machine + events → Phase 2; PipelineRun lifecycle + ops + invariants 1/2/4/7 + stage_timings → Phase 3; ScopedWorkGate + critical quota + soft-drop + leaked sweep (invariant 5) + RestartGuard → Phase 4; backpressure 7-metric sampling + DEGRADED/DRAINING foreground response fields → Phase 5. Deferred-with-justification: PipelineStepContract/invariant 8 (→c2), trace retention/invariant 6 (→c1.5/P3+), projection shadow-swap/invariant 3 (existing projection internals; c1 enforces run-status only), true concurrency (→P3+). No silent gaps.

**Placeholder scan:** Phase 1 carries complete code (capability policy, supervisor, binding, forwarder) + exact commands + expected output. Phases 2–5 are intentionally at file/interface/acceptance grain per the roadmap cascade rule (line 176: a later phase's bite-sized steps are written once the prior phase's schema lands, because `MetricsSnapshot`/`PipelineRun`/`GateKey` field shapes cascade) — this is the repo's documented planning discipline, not a "fill-in-later" placeholder.

**Type consistency:** `required_capabilities(bool)` (1.1) consumed by `RuntimeSupervisor` ctor (1.3); `PreflightReport` WRAPS the existing `PreflightResult{status, missing}` (per LOCKED amendment codex #6 — not a redefinition); `kExConfig=78` single definition; `RuntimeHealth` enum reused (not redefined; monitor revival deferred to Phase 2 per amendment #7/#9); `MetricsSnapshot` defined in Phase 2, consumed in Phase 5; `PipelineRun` defined in Phase 3, status/kind enums used consistently; `GateKey{tenant_id, holder_scope, aggregate_id, lane}` matches the `05_governance.md:158` gate_key tuple.

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 1 | issues_found | 10 findings (outside-voice), all folded or scoped |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | clean | 4 decisions locked (D1–D4); 10 codex findings absorbed; 0 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

Step 0 scope: REDUCED — c1 split into c1/Phase-1-first (D1); review targeted Phase 1 (CRITICAL relocation). Sections: Architecture 1 finding (D2), Code Quality 0 (1 minor folded: double-preflight recompute), Test 2 gaps added (capability-missing UNREADY, embedded READY), Performance 0. NOT in scope: full RuntimeHealth DEGRADED/DRAINING machine, PipelineRun ledger, ScopedWorkGate, RestartGuard, backpressure, real `Bus::write` gating, trace-retention tiers, step-contract validation, legacy-name test sweep (F1) — all sequenced (Phases 2–5 / c2 / follow-up). Parallelization: Phase 1 is sequential (Tasks 1.1→1.5 dependency chain), no worktree split.

- **CODEX:** 10 findings; cross-model consensus on D2 (IndexProbe). Folds applied: forwarder bus → C++ `check_write()`; adapter path `persistence/` (verified); flat `_core` binding; reuse existing `PreflightResult{status, missing}`; trim Phase-1 monitor/`events()` to Phase 2; label index check a legacy compat check. Codex's blast-radius probe surfaced D4 (41-file legacy coupling → inert forwarders now + separate sweep).
- **CROSS-MODEL:** both reviewers agree; no contradictions. Codex extended the review with 6 concrete corrections, all absorbed into the LOCKED amendments block.
- **VERDICT:** ENG CLEARED — Phase 1 (CRITICAL relocation) ready to implement. Phases 2–5 are sequenced follow-ups (each plan written as its predecessor lands, per roadmap cascade rule).

NO UNRESOLVED DECISIONS

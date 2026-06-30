# P3.c1 Phase 5 — Backpressure (HealthSampler) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `HealthSampler` (a pure threshold function over the 7-metric `MetricsSnapshot` → a `HealthDecision`), a C++ `MetricsGatherer` that fills the *cheaply-readable* metrics from the live DB, and wire them into the host tick so the runtime drives **observable READY↔DEGRADED** from real backpressure (surfaced on the merged 2b dashboard panel, which currently shows zeros). The last c1 phase of the Governance slice; Phases 1-4 merged.

**Architecture:** A pure `HealthSampler::evaluate(MetricsSnapshot) -> HealthDecision` (config thresholds, no I/O) + a `MetricsGatherer::gather(Connection&) -> MetricsSnapshot` (reads the readable metrics from existing tables) in `src/governance/`; bound to Python (`bind_14_governance.cpp` — the host drives them). The Python host (`dashboard/engine.py`) gathers a snapshot each tick (C++ gatherer + the host-only `runtime_event_loop_lag_ms`), calls `sampler.evaluate`, and applies `supervisor.note_health(decision)` — Phase 2's `note_health` already transitions + emits the event the 2b route/panel read. **The deeper integrations are deferred to M0.9+** (see OQ-5.1).

**Tech Stack:** C++20 core (`include/starling/governance/`, `src/governance/`), pybind11 (`bind_14_governance.cpp`), GoogleTest, Python host (`python/starling/dashboard/engine.py`), pytest, and (if needed) the SvelteKit panel (`dashboard/web/`).

## Global Constraints

- **Architecture boundary (CLAUDE.md):** the threshold logic + the metric COMPUTATION (queries, lag math) are core → C++ (`HealthSampler` + `MetricsGatherer`). Python only gathers the host-only `runtime_event_loop_lag_ms`, calls the bound C++, and forwards to `note_health` (host embedding).
- **CI clang-tidy (changed-LINES) gate:** lints `.cpp` under `src/|bindings/` + included headers, WarningsAsErrors `*`, DISABLES `bugprone-easily-swappable-parameters`. Write clean by construction (≥3-char ids — incl. iterator names like `found` not `it` [4.1 lesson]; `std::ranges`/`std::erase_if` not manual loops/erase-remove; sized enums; `[[nodiscard]]`; designated initializers; braces). clang-tidy un-runnable locally — the IDE's full-file lint surfaces header/`.cpp` issues pre-push; CI is the gate. See `[[clang-tidy-ci-only-gate-gotchas]]`.
- **Binding rebuild:** any `bind_14` change → `python scripts/configure_build.py --build --python-editable` (a bare `pip install -e .` is insufficient). Build tools in `.venv/bin/{cmake,ninja}` (not system PATH); test binary `build-macos/tests/cpp/starling_tests`.
- **Adding a tick-dict / TickStats consumer?** Not here — Phase 5 drives `note_health` (not the tick dict). But if any host change touches the tick path, recall `[[tickoutcome-dict-field-breaks-python-consumers]]`.
- **Commit gate:** full ctest + `pytest tests/python` green; if the panel is touched, `npm run check` / `npx vitest run` / `npm run build` in `dashboard/web/`.
- **git:** explicit-path `git add`; no `--no-verify`/`--amend`. Footer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

## RESOLVED DECISIONS (LOCKED by /plan-eng-review + codex outside-voice, 2026-06-30)

The OQ analysis below is the rationale record. **The LOCKED block after it is AUTHORITATIVE — implementers apply it OVER any conflicting task text.**

## OPEN DECISIONS — analysis (rationale record; superseded by the LOCKED block)

### OQ-5.1 (CENTRAL) — c1 scope vs M0.9+ deferral, bounded by metric-readability

The seam map shows the 7 metrics split sharply: **3 cheaply readable** (`outbox_lag_sequence` — an existing query pattern at `retrieval_planner.cpp:436`; `projection_lag_seconds` — needs a timestamp-join + events→seconds calibration; `erased_evidence_visible_count` — needs a compliance-erase backlog query, table TBD), **1 host-fed** (`runtime_event_loop_lag_ms` — only the Python loop can measure it), **3 need new cross-subsystem instrumentation** (`subscriber_failure_rate` — pump counters; `extraction_queue_depth` — pending-extraction count; `vector_delete_lag` — vector-store/erase-ledger counter). The spec's deeper backpressure behaviors (`BusWriteResponse{runtime_degraded, projection_stale, retry_after}`, "DEGRADED pauses soft lanes", "DRAINING refuses runs + finishes leases") depend on M0.9+ substrate (the gate routing 4 deferred, the run lifecycle, and Phase 2's deferred DRAINING write contract).

**Baseline (recommended): build the sampler (all 7 metrics) + gather the cleanly-readable metrics + drive observable DEGRADED; defer the rest.**
- **IN c1:** `HealthSampler::evaluate` (evaluates ALL 7 against config thresholds — the pure function is complete); `MetricsGatherer` fills the readable metrics (start with `outbox_lag_sequence`, the one with a clear existing query; `projection_lag_seconds` + `erased_evidence_visible_count` IF their queries are pinnable, else stub them 0 with a flag); host feeds `runtime_event_loop_lag_ms`; wire `gather → evaluate → note_health` on the tick → observable READY↔DEGRADED on the 2b panel. The 3 un-instrumented metrics stay 0 (the sampler simply never trips on them — honest partial).
- **DEFER to M0.9+ (flagged, not dropped):** the 3 un-instrumented metrics (each its own subsystem-counter effort); `BusWriteResponse` degradation fields + `retry_after` (coupled to the deferred DRAINING write contract); "DEGRADED pauses soft lanes" (needs 4's gate routing); "DRAINING refuses runs + finishes leases" (needs run lifecycle).

This makes Phase 5 a **real, observable, non-inert** feature (the dashboard shows real outbox/event-loop backpressure → DEGRADED), unlike 3b/4's inert substrate, while staying bounded. **Eng-review locks exactly which metrics ship gathered in c1** (the readability spread is the scope lever).

### Sub-decisions (baselines; eng-review locks)
- **OQ-5.2 — thresholds = injected config, no magic numbers.** `HealthSamplerConfig{...threshold per metric}` (bound, def_readwrite); documented defaults. The spec gives NO concrete numbers ("任一超阈值"), so the values are a config choice.
- **OQ-5.3 — metric COMPUTATION is C++ (`MetricsGatherer::gather(Connection&) -> MetricsSnapshot`), driven from Python.** Architecture boundary: the queries + lag math are core. Python supplies only `runtime_event_loop_lag_ms` (merges it into the gathered snapshot) + calls evaluate/note_health.
- **OQ-5.4 — `erased_evidence_visible_count > 0` drives DEGRADED** (per spec `05_governance.md:33,110`, it's in the DEGRADED list). FLAG for eng-review: a compliance leak driving only DEGRADED (not UNREADY/alarm) is arguably weak (invariant 4/6) — but the spec says DEGRADED; honor it unless eng-review escalates.
- **OQ-5.5 — `BusWriteResponse` degradation fields: DEFER to M0.9+** (coupled to the deferred DRAINING write contract + `retry_after`). The current write returns `AppendEvidenceOutcome` (variant); extending it for degradation is M0.9+ when DRAINING write semantics land.
- **OQ-5.6 — dashboard metrics rendering.** The route already maps metrics (`inspect.py:_metrics_to_dict`); VERIFY whether the 2b panel renders `metrics_snapshot` (2b's D1 deferred "don't render zeros" to Phase 5). If the panel already renders them, they auto-appear once real (no frontend change); if D1-deferred, add a small render. Baseline: render the now-real metrics (small frontend task) — confirm during Task 5.5.
- **OQ-5.7 — binding IS required (NOT deferred, unlike 3a/4 D1).** The host drives the sampler from Python, so `HealthSampler` + `HealthSamplerConfig` + `MetricsGatherer` MUST be bound in `bind_14_governance.cpp`.

### LOCKED eng-review decisions (2026-06-30) — AUTHORITATIVE; apply OVER task text

/plan-eng-review (FULL_REVIEW + codex outside-voice; 9 codex findings, 8 folded + 1 escalated-and-locked). Where these conflict with task code below, THESE win.

- **L1 — OQ-5.1 = A, RE-FRAMED HONESTLY (D1 + codex #1 + bottom-line).** c1 ships a **PARTIAL backpressure sampler (outbox_lag + background-tick-delay)**, NOT "runtime health over 7 metrics". `HealthSampler` evaluates ONLY **ENABLED** metrics; the un-gathered 5 are **DISABLED** in `HealthSamplerConfig` (per-metric enable flag / sentinel) so they are NOT evaluated — **READY honestly means "the measured (enabled) metrics are within SLA", NOT "all 7 healthy"** (zero ≠ healthy). c1 enables `outbox_lag` + `runtime_event_loop_lag_ms`. Defer projection_lag + erased_evidence (query-pinning follow-up); the 3 instrumentation metrics + BusWriteResponse + lane-pause + DRAINING-refuse → M0.9+ (consistent with Phase-4 OQ-4.1=B + 3b OQ-2=A).
- **L2 — thresholds = injected `HealthSamplerConfig`** with a per-metric **enable** + threshold; documented defaults; disabled metrics skipped (OQ-5.2 + L1).
- **L3 — flapping damping = HOST-SIDE DEBOUNCE (D2 + codex #3).** `HealthSampler::evaluate` stays a PURE function; the HOST (`engine.py`) tracks the last N sampler verdicts + calls `note_health` ONLY when N consecutive agree (config `debounce_ticks`). Pure sampler = ctest; debounce = pytest.
- **L4 — trigger contract (codex #4):** `HealthDecision.trigger` lists ALL over-threshold metrics in a deterministic order (stable string); the recovery (→READY) trigger = `"backpressure_recovered"` (NEVER empty).
- **L5 — outbox_lag query: PIN THE REAL SCHEMA (codex #5 — REAL catch).** The cited `consumer_checkpoints.last_dispatched_sequence` is WRONG; the schema has `consumer_checkpoint.last_delivered_sequence` (`migrations/0001:143`) + separate pump checkpoints. The MetricsGatherer implementer MUST verify the actual schema first (`migrations/`, `python/starling/dashboard/queries.py:300`) + LOCK which consumer set defines `outbox_lag_sequence` (start with the `in_process` consumer's delivered-sequence) BEFORE writing the query. No assumed column names.
- **L6 — `runtime_event_loop_lag_ms` host value = the background-tick-delay** (actual minus scheduled `interval_s` of the `threading.Event` tick), NOT an asyncio loop lag (codex #6). The MetricsSnapshot FIELD name is frozen (Phase-2 bound), so document the value as tick-delay (host-overload proxy); a true loop heartbeat is a refinement.
- **L7 — DRAINING/UNREADY suppression (codex #9):** the host SKIPS the sampler (no `note_health`) UNLESS the supervisor is READY or DEGRADED (don't fight the state machine — DRAINING→READY is illegal). gather failures (DB busy/missing table) are caught by the existing tick exception handler → leave health unchanged (no spurious transition). Test these.
- **L8 — locking (codex #7):** sampler + gatherer are mutex-free, but `note_health` takes the supervisor mutex; lock order = engine-RLock → supervisor-mutex (consistent; no reverse path — `transition_to_locked` calls no callback under the mutex, OV-1). Self-review corrected (NOT "no mutex"). A comment/test forbids the reverse order.
- **L9 — dashboard (codex #2 — REAL correction):** the 2b panel does NOT currently render `metrics_snapshot` (only status/events). Task 5.5 is **REAL frontend**: render the over-threshold metrics on the DEGRADED event (the route already maps `event.metrics_snapshot`). A "current snapshot when steady READY" route is DEFERRED (events are transition-only).
- **L10 — erased_evidence (codex #8):** NOT gathered in c1 (A defers) + DISABLED in the sampler → not live. When gathered (follow-up), its semantics (DEGRADED-per-spec vs alarm/UNREADY-per-invariant-4/6 for a compliance leak) need a compliance-specific ruling — flagged, not decided now.
- **L11 — binding REQUIRED (OQ-5.7):** bind HealthSampler/HealthSamplerConfig/MetricsGatherer.

---

## What Phase 5 delivers (spec linkage)
- Spec: governance-core.md §473-481 (Phase 5) + `05_governance.md` (健康降级 :31-36, state table :105-112, BusWriteResponse :175-181).
- 2b (merged) built the dashboard panel + the route (`inspect.py` maps all 7 metrics) but with Phase-2 zeros (2b D1). Phase 5 fills real values → the panel shows real backpressure.
- `MetricsSnapshot` (bound) + `note_health` (Phase 2) are reused; `HealthSampler` + `MetricsGatherer` are new.

---

## File structure
- **Create** `include/starling/governance/health_sampler.hpp` + `src/governance/health_sampler.cpp` — `HealthSamplerConfig`, `HealthSampler::evaluate(MetricsSnapshot) -> HealthDecision`.
- **Create** `include/starling/governance/metrics_gatherer.hpp` + `src/governance/metrics_gatherer.cpp` — `MetricsGatherer::gather(persistence::Connection&) -> MetricsSnapshot` (readable metrics; un-instrumented left 0).
- **Modify** `bindings/python/bind_14_governance.cpp` — bind `HealthSamplerConfig`, `HealthSampler`, `MetricsGatherer`.
- **Modify** `python/starling/dashboard/engine.py` — gather (C++ gatherer + host `runtime_event_loop_lag_ms`) → `evaluate` → `_sup.note_health` on the tick.
- **Modify** `CMakeLists.txt` + `tests/cpp/CMakeLists.txt`; **Create** `tests/cpp/test_health_sampler.cpp`, `tests/cpp/test_metrics_gatherer.cpp`, `tests/python/test_backpressure_sampler.py`.
- **Possibly modify** `dashboard/web/src/routes/runtime-health/+page.svelte` (+ `.test.ts`) — render the now-real metrics (OQ-5.6, confirm).

---

## Task 5.1: `HealthSampler::evaluate` — the pure threshold function

**Files:** Create `include/starling/governance/health_sampler.hpp` + `src/governance/health_sampler.cpp` + `tests/cpp/test_health_sampler.cpp`; Modify `CMakeLists.txt` + `tests/cpp/CMakeLists.txt`.

**Interfaces (Produces):**
```cpp
namespace starling::governance {
struct HealthSamplerConfig {           // injected thresholds (OQ-5.2; no magic numbers)
  std::int64_t outbox_lag_threshold = 0;
  double subscriber_failure_rate_threshold = 0.0;
  std::int64_t extraction_queue_depth_threshold = 0;
  double projection_lag_seconds_threshold = 0.0;
  double runtime_event_loop_lag_ms_threshold = 0.0;
  std::int64_t vector_delete_lag_threshold = 0;
  // erased_evidence_visible_count: spec = ">0 trips" (OQ-5.4), no numeric threshold.
};
class HealthSampler {
 public:
  explicit HealthSampler(HealthSamplerConfig config);
  // Pure: READY if every metric within SLA; else DEGRADED with a trigger naming the
  // first/over metric(s). NEVER UNREADY (UNREADY = preflight/fail-closed, not backpressure).
  [[nodiscard]] HealthDecision evaluate(const MetricsSnapshot& snapshot) const;
 private:
  HealthSamplerConfig config_;
};
}  // namespace starling::governance
```

- [ ] **Step 1: Write failing tests** — all-within-SLA → `{READY, ""}` (or a "healthy" trigger); each of the 7 metrics ALONE over its threshold → `{DEGRADED, trigger}` with a trigger naming that metric; `erased_evidence_visible_count > 0` → DEGRADED (OQ-5.4); multiple-over → DEGRADED with a trigger listing them (or the first); the snapshot's metrics_snapshot is carried into the HealthDecision. [Full bodies at impl time; exact inputs → exact assertions.]
- [ ] **Step 2: Register + verify fail** — add src to `CMakeLists.txt` `target_sources(starling_core ...)` (after `restart_guard.cpp`); test to `tests/cpp/CMakeLists.txt`. `python scripts/configure_build.py --build` then `build-macos/tests/cpp/starling_tests --gtest_filter='HealthSampler*'`; FAIL (header missing).
- [ ] **Step 3: Implement** — `evaluate`: build the over-threshold list (each metric vs its config threshold; erased_evidence > 0), if empty → READY, else DEGRADED + a trigger string + carry the snapshot. Pure, no I/O, no mutex. `[[nodiscard]]`, ≥3-char, braces, `: std::uint8_t` if any new enum.
- [ ] **Step 4: Verify pass.**
- [ ] **Step 5: Full gate + commit** — `feat(P3.c1/5): HealthSampler — 7-metric threshold → DEGRADED decision`.

## Task 5.2: `MetricsGatherer::gather` — read the cleanly-readable metrics from the DB

**Files:** Create `include/starling/governance/metrics_gatherer.hpp` + `src/governance/metrics_gatherer.cpp` + `tests/cpp/test_metrics_gatherer.cpp`; Modify CMake.

**Interfaces (Produces):** `[[nodiscard]] MetricsSnapshot gather(persistence::Connection& conn) const;` — fills the metrics whose queries are pinned (baseline: `outbox_lag_sequence` via the `retrieval_planner.cpp:436` pattern; `projection_lag_seconds` + `erased_evidence_visible_count` IF eng-review confirms their queries, else left 0). `runtime_event_loop_lag_ms` + the 3 un-instrumented metrics are left 0 (the host merges event_loop_lag; the rest are M0.9+).

- [ ] **Step 1: Write failing tests** — on a fresh DB + a few seeded outbox events with an un-advanced consumer checkpoint, `gather()` returns a snapshot whose `outbox_lag_sequence` equals the seeded lag; an empty DB → 0 lag; the un-instrumented metrics are 0. [Mirror the store-test DB fixture; exact seeded inputs → exact lag.]
- [ ] **Step 2: Register + verify fail.**
- [ ] **Step 3: Implement** — the `outbox_lag_sequence` query (MAX(outbox_sequence) - MIN(last_dispatched per consumer), mirroring `retrieval_planner.cpp:436`), using the store's prepared-statement idiom; leave the deferred metrics 0. (If eng-review pins the projection_lag / erased_evidence queries, add them; else this task is outbox-lag-only + the rest 0.) clang-tidy-clean.
- [ ] **Step 4: Verify pass.**
- [ ] **Step 5: Full gate + commit** — `feat(P3.c1/5): MetricsGatherer — readable backpressure metrics from the DB`.

## Task 5.3: bind `HealthSampler` + `HealthSamplerConfig` + `MetricsGatherer`

**Files:** Modify `bindings/python/bind_14_governance.cpp`.

**Interfaces:** bind `HealthSamplerConfig` (init + def_readwrite all thresholds), `HealthSampler` (init(config) + `evaluate`), `MetricsGatherer` (init + `gather(adapter/connection)`). Mirror the existing bind_14 pattern (the `RuntimeSupervisor`/`MetricsSnapshot` bindings). Rebuild `--python-editable`.

- [ ] **Step 1: Write a failing pytest** — `from starling._core import HealthSampler, HealthSamplerConfig, MetricsSnapshot`; construct a config + sampler; `evaluate(MetricsSnapshot())` → a READY decision; set one metric over → DEGRADED. (Mirror `test_governance_binding.py`.) FAIL (classes absent).
- [ ] **Step 2: Implement the bindings** + rebuild `python scripts/configure_build.py --build --python-editable`.
- [ ] **Step 3: Verify the pytest passes.**
- [ ] **Step 4: Commit** — `feat(P3.c1/5): bind HealthSampler/Config/MetricsGatherer to _core`.

## Task 5.4: host wiring — drive `gather → evaluate → note_health` on the tick

**Files:** Modify `python/starling/dashboard/engine.py`; Create `tests/python/test_backpressure_sampler.py`.

**Interfaces:** in `start_background_tick`'s `_loop` (after `self.tick(...)`, under `self._lock`): gather a `MetricsSnapshot` (C++ `MetricsGatherer.gather(adapter)` + set `runtime_event_loop_lag_ms` from a host loop-lag measurement = actual-tick-interval minus scheduled `interval_s`), `decision = self._sampler.evaluate(snapshot)`, `self._rt._sup.note_health(decision)` (or via a `Runtime.note_health` passthrough mirroring 2a's `begin_drain`). The sampler+gatherer are constructed once in `DashboardEngine.__init__` (process-lifetime, alongside `_rt`).

- [ ] **Step 1: Write a failing pytest** — `test_backpressure_sampler.py`: build a DashboardEngine (mirror `test_dashboard_engine.py`); seed enough outbox lag to exceed a low `outbox_lag_threshold`; run one tick; assert `engine.health() == DEGRADED` and the last event's trigger names outbox lag + the metrics_snapshot carries the real lag. A recovery case: clear the lag → next tick → READY.
- [ ] **Step 2: Run to verify it fails** (sampler not wired yet).
- [ ] **Step 3: Implement** the engine wiring (construct sampler+gatherer in `__init__`; the gather/evaluate/note_health block in `_loop`; a `Runtime.note_health` passthrough if cleaner than `_rt._sup`). Rebuild if any binding/Runtime change. Watch `[[replay-write-reentrancy-offline-only]]` — `gather` is read-only (no writes), so no BEGIN nesting.
- [ ] **Step 4: Verify the pytest + the dashboard regression** (`test_dashboard_engine.py`, `test_dashboard_runtime_health_route.py`) pass.
- [ ] **Step 5: Full gate + commit** — `feat(P3.c1/5): wire HealthSampler into the host tick — observable DEGRADED from backpressure`.

## Task 5.5: dashboard — render the now-real metrics (OQ-5.6; confirm first)

**Files:** Possibly Modify `dashboard/web/src/routes/runtime-health/+page.svelte` (+ `runtime_health.ts` / `.test.ts`).

- [ ] **Step 1: Confirm** whether `+page.svelte` already renders `event.metrics_snapshot` (the route maps it). If YES (renders, just zeros today) → metrics auto-appear once real; **this task is a no-op + a vitest asserting a non-zero metric renders.** If NO (2b D1 deferred the render) → add a compact metrics display on the DEGRADED event (the 7 values), mirroring the vitals/health card style.
- [ ] **Step 2:** (if a render is added) frontend tests + gate: `npm run check` / `npx vitest run` / `npm run build` in `dashboard/web/`.
- [ ] **Step 3: Commit** — `feat(P3.c1/5): render real backpressure metrics on the runtime-health panel` (or `test(...)` if no-op).

**Phase 5 acceptance (L1 — PARTIAL backpressure sampler, NOT 7-metric health):** `HealthSampler` (pure threshold over the **ENABLED** metrics; disabled metrics skipped so READY = "measured metrics within SLA" [L1]) + `MetricsGatherer` (the locked outbox_lag query against the REAL schema [L5]) built + unit-tested; bound to `_core` [L11]; the host gathers (+ background-tick-delay [L6]) + evaluates + **debounces N consecutive verdicts** [L3] + drives `note_health` ONLY in READY/DEGRADED [L7], so real outbox/tick-delay backpressure produces an **observable READY↔DEGRADED** with a deterministic trigger [L4] / `backpressure_recovered`; the 2b panel renders the over-threshold metrics on the DEGRADED event [L9]; full ctest + pytest + frontend (`check`/`vitest`/`build`) green. **DEFERRED to M0.9+/follow-up (L1):** the un-gathered 5 metrics, `BusWriteResponse` + `retry_after`, DEGRADED-pauses-soft-lanes, DRAINING-refuses-runs. core + host-embedding + dashboard render.

---

## Self-review

**Spec coverage** (governance-core.md §473-481 + 05_governance.md):
- `HealthSampler::evaluate(MetricsSnapshot) -> HealthDecision` per the threshold table → Task 5.1. ✅ (all 7 metrics evaluated; thresholds = config, OQ-5.2.)
- "sample 7 metrics → threshold → DEGRADED" → Tasks 5.2 (gather readable) + 5.4 (host drive). ✅ partial: the readable metrics ship gathered; the 3 un-instrumented are M0.9+ (OQ-5.1, flagged — the sampler still evaluates them, they're just 0 until instrumented).
- `note_health` applies the transition → reused from Phase 2 (Task 5.4). ✅
- "DEGRADED pauses soft lanes / DRAINING retry_after / BusWriteResponse fields" → **DEFERRED to M0.9+** (OQ-5.1/5.5; depend on 4's gate routing + run lifecycle + the deferred DRAINING write contract). Flagged, not dropped.
- erased_evidence_visible_count → DEGRADED (OQ-5.4, per spec; flagged as arguably-weak for a compliance leak).

**Placeholder scan:** the sampler + gatherer interfaces + test scenarios are pinned; the gatherer's exact projection_lag/erased_evidence queries are the one genuinely-uncertain spot (the seam map found outbox_lag has a clear pattern but the other two need pinning) — surfaced honestly for eng-review (Task 5.2 ships outbox-lag baseline, adds the others only if their queries are confirmed).

**Type consistency:** `HealthSamplerConfig`/`HealthSampler` (5.1) + `MetricsGatherer` (5.2) consumed by the binding (5.3) + the host (5.4); `MetricsSnapshot`/`HealthDecision`/`note_health` reused unchanged from Phase 2 (seam-verified: `runtime_health_event.hpp:14`, `runtime_supervisor.cpp:64`, bind_14:47). **Locking (L8 — NOT "no mutex"):** the sampler + gatherer are mutex-free, but `note_health` takes the supervisor mutex; lock order = engine-RLock → supervisor-mutex (consistent, no reverse path). The sampler NEVER returns UNREADY (backpressure ≠ fail-closed); the host suppresses sampling outside READY/DEGRADED (L7).

**clang-tidy pre-flight:** new headers gated; `[[nodiscard]]` on evaluate/gather; ≥3-char ids (incl. iterator names — `found` not `it`, per 4.1); `std::ranges`/`std::erase_if`; sized enums; designated initializers. bind_14 changed lines linted (loop vars ≥3-char). Python/frontend not clang-tidy-gated.

---

## Implementation Tasks
Synthesized from this review (all FOLDED into the LOCKED block + tasks).

- [ ] **T1 (P1, human: ~2h / CC: ~20min)** — HealthSampler — pure evaluate over ENABLED metrics + deterministic trigger
  - Surfaced by: codex #1 (zero≠healthy → per-metric enable; READY = measured-within-SLA) + #4 (trigger lists all over-metrics; recovery = `backpressure_recovered`)
  - Files: `include/starling/governance/health_sampler.{hpp,cpp}`, `tests/cpp/test_health_sampler.cpp`
  - Verify: `--gtest_filter='HealthSampler*'` (disabled-metric skip; multi-over trigger; recovery)
- [ ] **T2 (P1, human: ~2h / CC: ~20min)** — MetricsGatherer — outbox_lag against the REAL schema
  - Surfaced by: codex #5 — verify `consumer_checkpoint.last_delivered_sequence` (migrations/0001, queries.py:300); lock which consumer set; NO assumed names
  - Files: `include/starling/governance/metrics_gatherer.{hpp,cpp}`, `tests/cpp/test_metrics_gatherer.cpp`
  - Verify: `--gtest_filter='MetricsGatherer*'` (seeded lag from real tables; empty→0; DB-error handled)
- [ ] **T3 (P1, human: ~1.5h / CC: ~15min)** — host wiring — debounce + DRAINING-suppress + tick-delay
  - Surfaced by: D2/codex #3 (host N-consecutive debounce) + codex #9 (skip sampler unless READY/DEGRADED; gather-fail no spurious transition) + #6 (background-tick-delay into the lag field)
  - Files: `python/starling/dashboard/engine.py`, `tests/python/test_backpressure_sampler.py`
  - Verify: `.venv/bin/python -m pytest tests/python/test_backpressure_sampler.py tests/python/test_dashboard_engine.py` (DEGRADED + recovery + no-flap + DRAINING-suppress)
- [ ] **T4 (P2, human: ~1h / CC: ~10min)** — dashboard — render the over-threshold metrics on the DEGRADED event
  - Surfaced by: codex #2 — the panel does NOT render metrics today (real frontend, not a no-op)
  - Files: `dashboard/web/src/routes/runtime-health/+page.svelte` (+ `.test.ts`)
  - Verify: `npm run check` / `npx vitest run` / `npm run build`

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 1 | issues_found | 9 findings; 8 folded + 1 escalated→locked (D2) |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | clean | 2 decisions locked (OQ-5.1=A, debounce); 0 critical gaps; codex caught 3 real corrections |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

Step 0 scope: ACCEPTED, re-framed — ~12 files is a genuine end-to-end feature (C++ sampler/gatherer → bind → host → dashboard), test-driven; 2 new classes. Locked: **OQ-5.1=A** (gather `outbox_lag` + `background-tick-delay` live; the other 5 metrics DISABLED — READY = "measured within SLA", not 7-metric health — codex #1) + **D2 host-side debounce** (flapping damping, sampler stays pure). Architecture 1 finding (flapping → D2); Code Quality 1 (multi-metric trigger, locked L4); Tests strong (+ codex's DRAINING/DB-error/no-flap gaps folded L7); Performance 1 minor (outbox query rides the index).

- **CODEX (outside voice):** 9 findings. Caught **3 real corrections the C++ review missed**: **#5** (the cited outbox-lag schema `consumer_checkpoints.last_dispatched_sequence` is WRONG — it's `consumer_checkpoint.last_delivered_sequence`; verify-first now) + **#2** (the 2b panel does NOT render metrics — Task 5.5 is real frontend, not a no-op) + **#1** (zero ≠ healthy — disable the un-gathered metrics so READY is honest; re-frame as "partial backpressure sampler"). **#3** (flapping) → D2 debounce (cross-model agreement with the architecture review). #4 (trigger) / #6 (lag-label) / #7 (lock-wording) / #8 (erased-evidence-flag) / #9 (DRAINING-suppress + DB-error) folded.
- **CROSS-MODEL:** codex's bottom line — "ship A only if scoped as a PARTIAL sampler (outbox + tick-delay), not 7-metric health" — accepted (L1 re-frames it exactly so). Its schema catch (#5) is the highest-value: a C++-only review would have written the gatherer against a non-existent column.
- **VERDICT:** ENG CLEARED — Phase 5 ready to implement subagent-driven, as a PARTIAL backpressure sampler (2 live metrics, debounced, honest READY). 2 decisions + 8 codex folds in the LOCKED block.

NO UNRESOLVED DECISIONS

# P3.c1 Phase 2 — RuntimeHealth Full State Machine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.
>
> **STATUS (2026-06-28):** DRAFT — pending /plan-eng-review lock. **EXECUTION IS GATED on PR #30 (Phase 1) merging to main** (Phase 2 extends Phase 1's `RuntimeSupervisor`). This plan is held as an untracked draft until then; it commits on the Phase-2 branch cut from main post-#30-merge. Predecessor: `2026-06-28-p3-c1-governance-core.md` (Phase 1, PR #30).

**Goal:** Make the `RuntimeHealth` 4-state machine (READY/DEGRADED/DRAINING/UNREADY) fully reachable with validated transitions, each emitting a `RuntimeHealthEvent`, plus drain entry (`begin_drain()`) and a metric-decision intake (`note_health()`); surface it read-only on the dashboard. Transition *mechanics* ship here with manual/test triggers; real metric *sampling* that drives DEGRADED is Phase 5.

**Architecture:** Phase 1's `RuntimeSupervisor` already owns `RuntimeHealth health_` as a plain member and is the single owner of the health decision. Phase 2 **absorbs the state-machine + event log directly into `RuntimeSupervisor`** (transition methods + a `std::vector<RuntimeHealthEvent>` + `events()`), rather than reviving the dead `RuntimeHealthMonitor`. The host (FastAPI lifespan) drives drain on shutdown; the dashboard reads health live off the engine's supervisor.

**Tech Stack:** C++20 core (`src/governance/`, `include/starling/governance/`), pybind11 (`bindings/python/bind_14_governance.cpp`), FastAPI host (`python/starling/dashboard/`), SvelteKit read panel (`dashboard/web/`).

## Global Constraints
(inherited verbatim from the c1 plan — `2026-06-28-p3-c1-governance-core.md` §Global Constraints)
- Architecture boundary: governance state-machine + transition validation + event emission are CORE → C++. Python/TS only host-glue + read-only surface.
- Canonical build: `python scripts/configure_build.py --build --test`; after C++/binding/migration change re-run with `--python-editable`. Dashboard front-end (touched here): `npm run check` / `npx vitest run` / `npm run build` in `dashboard/web/`.
- Commit gate: full ctest + `pytest tests/python` green; front-end checks green.
- CI clang-tidy (changed-LINES) gate, `WarningsAsErrors '*'`, checks incl. `modernize-*`/`performance-*`/`readability-*`/`cppcoreguidelines-*`/`bugprone-*`, header filter `include/starling/.*`: designated initializers, `contains()` over `count()!=0`, `std::ranges::*`, identifiers ≥3 chars, braces on all statements, `[[nodiscard]]` on const value-returning accessors, **sized enum bases (`: std::uint8_t`) on NEW enums**, cognitive-complexity < 25. (The standalone clang-tidy CLI is un-runnable locally — write clean by construction; CI is the gate.)
- git: explicit-path `git add`; no `--no-verify`/`--amend`. Commit footer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- **`TC-NEW-PREFLIGHT` [CRITICAL] must stay green** — it asserts the `runtime.health_changed` event dict shape (`{event, state, missing_capabilities}`) on UNREADY/READY. Any change to event sourcing must preserve that exact Python-facing shape.

---

## Background — what Phase 1 landed (verified, branch feat/p3-c1-governance-core @ 69be9e0)
- `include/starling/governance/runtime_supervisor.hpp`: `RuntimeSupervisor` holds `RuntimeHealth health_ = UNREADY` + `int exit_code_ = 0`; methods `run_preflight()/start()/health()/exit_code()/check_write()`; **no events, no DEGRADED/DRAINING, no monitor**. Two ctors (production `SqliteAdapter&` / test-seam `std::function<bool()>`). `kExConfig=78`; enums `StartOutcome`/`WriteGateDecision : std::uint8_t`; `PreflightReport{passed, missing_capabilities, warnings}`.
- `check_write()` currently: `kAccept` iff `health_==READY`, else `kPreconditionFailed`.
- `include/starling/runtime_health.hpp`: `enum class RuntimeHealth {UNREADY=0,READY=1,DEGRADED=2,DRAINING=3}` (already 4 values, bound at `bind_01_core.cpp:96`). `RuntimeHealthMonitor` (set_ready/set_unready/on_change) is **DEAD** — only `tests/cpp/test_runtime_health.cpp` uses it; zero production callers; not bound to Python. **Phase 2 does NOT revive it** (see D-P2-1); leave it + its tests untouched (its eventual removal is a separate cleanup).
- `python/starling/runtime.py`: `Runtime` forwarder; `Runtime._emit_health(state, missing)` emits the `runtime.health_changed` dict to `on_health_change`. Bus delegates to C++ `check_write()`.
- Dashboard: FastAPI `app.py` lifespan (`:43-69`) starts/stops the background tick; **no signal handling** (uvicorn owns SIGTERM→lifespan-shutdown). Read routes under `python/starling/dashboard/routes/` (`inspect.py` read-only SQL; `commands.py` reaches the live engine via `_engine(request)=request.app.state.engine`). Vitals pattern (de11c05): `GET /api/vitals` (`inspect.py:86`) → `queries.vitals()` dict → `dashboard/web/src/lib/vitals.ts` types → `dashboard/web/src/routes/vitals/+page.svelte` (`createQuery(()=>api.get<VitalsResponse>('/api/vitals'))`, refetch on WS `tick`) → nav `dashboard/web/src/lib/nav.ts:60` group `生命体征 · 脑干`.

---

## Phase 2 design decisions — FOR /plan-eng-review TO LOCK
Recommendations below; eng-review confirms or amends (will become a LOCKED-amendments block like Phase 1's D1–D4).

- **D-P2-1 — State machine location.** *Recommend:* absorb transitions + event log directly into `RuntimeSupervisor` (it already owns `health_`); leave `RuntimeHealthMonitor` dead/untouched. *Alt:* revive `RuntimeHealthMonitor` and make it a supervisor member. Rationale for recommend: single owner of health state; no redundant indirection; the monitor's listener model (single listener, throws-propagate) doesn't fit the event-log need.
- **D-P2-2 — Event sourcing for `runtime.health_changed`.** Phase 1 emitted the event dict from Python (`Runtime._emit_health`) because the C++ supervisor had no event log. Phase 2 gives C++ the log. *Recommend:* C++ becomes the source of truth (`events()` returns the log); the Python forwarder MAPS the latest C++ event(s) to the existing dict shape `{event:"runtime.health_changed", state, missing_capabilities}` so `TC-NEW-PREFLIGHT` stays green unchanged. (`missing_capabilities` only meaningful for UNREADY; DEGRADED/DRAINING events carry `trigger`+`metrics_snapshot` instead, surfaced on the dashboard, not asserted by TC-NEW-PREFLIGHT.)
- **D-P2-3 — Event log retention.** *Recommend:* keep the last N=64 events (ring/cap) — transitions are infrequent; an unbounded vector is a slow leak over a long-lived process. *Alt:* unbounded (transitions rare). eng-review picks N or unbounded.
- **D-P2-4 — `MetricsSnapshot` now vs defer.** *Recommend:* define the full 7-field struct now (Phase 2 owns the type; Phase 5 consumes it), all fields default 0/sentinel; Phase 2 transitions are driven by manual/test triggers + `note_health(HealthDecision)`, NOT by real sampling. Fields (verbatim from `05_governance.md:33`): `outbox_lag_sequence`, `subscriber_failure_rate`, `extraction_queue_depth`, `projection_lag_seconds`, `runtime_event_loop_lag_ms`, `vector_delete_lag`, `erased_evidence_visible_count`.
- **D-P2-5 — `check_write()` in DEGRADED/DRAINING.** *Recommend:* Phase 2 `check_write()` returns `kAccept` for READY **and DEGRADED** (state table: DEGRADED keeps foreground writes), `kPreconditionFailed` for UNREADY and DRAINING. The DRAINING `retry_after` payload + full `Bus::write` degradation fields are Phase 5 (a binary gate suffices here). Additive — no Phase-1 test breaks.
- **D-P2-6 — SIGTERM/drain wiring (host).** *Recommend:* call `begin_drain()` in the lifespan **post-`yield` shutdown block** (not a separate `add_signal_handler`), to avoid racing uvicorn's own SIGTERM handler (Explore-flagged). Phase 2 ships drain-entry mechanics; full worker-lease draining is Phase 4/5.
- **D-P2-7 — Transition legality matrix.** *Recommend:* legal = `UNREADY→READY`, `READY↔DEGRADED`, `READY→DRAINING`, `DEGRADED→DRAINING`, `any→UNREADY` (fail-closed always reachable), `DRAINING→` (terminal except `→UNREADY`). Illegal (e.g. `DRAINING→READY`, `UNREADY→DEGRADED`) = rejected: no-op + a warning, no event pushed, no state change. eng-review confirms the matrix.

### LOCKED eng-review amendments (2026-06-28) — these SUPERSEDE the task text above where they conflict

- **[D2 — execution split]** Phase 2 ships as **two sequenced PRs**: **2a** = the C++ governance core + host drain (Tasks 2.1–2.4); **2b** = the read-only dashboard panel (Tasks 2.5–2.6), as a fast follow-up after 2a merges. Mirrors Phase 1's core-first/dashboard-deferred pattern (D1). Both PRs gated on PR #30 (Phase 1) merging first.
- **[D3 — thread safety, P1]** The `RuntimeSupervisor` must be **self-synchronizing**: add a `std::mutex` (private member) guarding `health_`, `exit_code_`, and the event log; every transition method and every read (`health()`, `exit_code()`, `check_write()`, `run_preflight()`, `events()`) locks it. **`events()` returns a `std::vector<RuntimeHealthEvent>` BY VALUE (a snapshot copy), NOT `const&`** — a const-ref to a vector another thread mutates under lock is itself a race. Rationale: the dashboard route (2b) reads `health()`/`events()` from an anyio worker thread while `begin_drain()` (lifespan/event-loop thread) and `note_health()` (Phase 5 tick thread) mutate — concurrent read+write on an unsynchronized `std::vector`/enum is a data race (`runtime_health.hpp:20-21` documents the current "not thread-safe" assumption). Core invariant lives in C++ (project boundary rule). **Lock discipline:** never invoke an external callback while holding the lock (Phase 1 has no callbacks in the supervisor; keep it that way — the event log is internal, the Python forwarder reads the snapshot AFTER the call returns). Take the lock at the top of each public method, do the work, release; transitions do not re-enter.
- **[locked as recommended]** D-P2-1 (supervisor absorbs the state machine + now owns the mutex; `RuntimeHealthMonitor` stays dead/untouched), D-P2-2 (C++ is the event source; Python forwarder maps the latest event to the existing `{event,state,missing_capabilities}` dict so TC-NEW-PREFLIGHT stays green), D-P2-3 (cap the event log at N=64), D-P2-4 (define the full 7-field `MetricsSnapshot` now, 0/sentinel defaults, real population is Phase 5), D-P2-5 (`check_write()` accepts READY||DEGRADED, rejects UNREADY||DRAINING), D-P2-6 (drain via the lifespan post-`yield` shutdown block, NOT a separate signal handler — avoids the uvicorn SIGTERM race), D-P2-7 (the transition matrix above). eng-review confirmed each per its recommendation.

### Outside-voice corrections (2026-06-28, opus subagent — codex timed out) — ALL folded, these SUPERSEDE conflicting task text

- **[OV-1 / was P1-BLOCKING — locking re-entrancy] PUBLIC-locks / PRIVATE-`_locked` split is MANDATORY.** Phase 1 `start()` (`src/governance/runtime_supervisor.cpp:43-44`) calls `run_preflight()` internally. With D3's non-recursive `std::mutex` and "every public method locks at top", `start()`→`run_preflight()` self-deadlocks on the hottest path (every engine boot). **Rule (global, applies to the whole supervisor):** each PUBLIC method takes `mtx_` at the top and immediately delegates to a PRIVATE `*_locked` helper that assumes the lock is held and does the real work. Internal call paths use ONLY the `_locked` helpers, NEVER the public locked overloads. Concretely: public `run_preflight()` { lock; return run_preflight_locked(); }; public `start()` { lock; … uses run_preflight_locked() + transition_to_locked() …; }; `transition_to` is already lock-assuming (rename `transition_to_locked` for clarity). No public method calls another public method.
- **[OV-2 / was P1-2 — value semantics] `events()` and the bound structs are deep copies.** `events()` returns `std::vector<RuntimeHealthEvent>` BY VALUE; bind it (and `last_event()`, see OV-6) with the DEFAULT (copy) return_value_policy — NEVER `reference_internal`/`reference` (that re-introduces the race D3 kills). `RuntimeHealthEvent`/`MetricsSnapshot` exposed via `def_readonly` is safe ONLY because the elements are value copies; state this in the Task 2.3 binding.
- **[OV-3 / was P2-3 — self-transition emit rule] `transition_to` emits iff `from != to` OR `target == UNREADY`.** TC-NEW-PREFLIGHT needs `UNREADY→UNREADY` (failing `start()` from the initial UNREADY state) to PUSH an event (so the forwarder has exactly one event to map; `test_tc_new_preflight.py:90` `len(events)==1`). But `READY→READY` (a Phase-5 sampler re-affirming READY every tick) must NOT emit, or the N=64 log floods with identical READY events and evicts real transition history (breaks the 2b panel). Defense-in-depth: the Phase-5 sampler SHOULD also call `note_health` only on an actual change. Document this rule on `transition_to`.
- **[OV-4 / was P3-1 — exit_code under lock] `start()` sets `exit_code_ = kExConfig` on the UNREADY path INSIDE the held lock, OUTSIDE `transition_to_locked` (which only touches `health_`/`events_`).** Preserves the Phase-1 fail-closed contract (`test_tc_new_preflight.py:47` `rt.exit_code == EX_CONFIG`; `test_runtime_supervisor.cpp` exit-78 pin).
- **[OV-5 / was P3-3 — engine passthrough MANDATORY, the bare path is broken] Add `DashboardEngine.health()` / `events()` / `begin_drain()` passthroughs (and they acquire NOTHING extra — the supervisor self-locks per D3).** The plan's `engine._runtime._sup` path is WRONG: `engine.py:28` does `from starling import runtime as _runtime`, so `engine._runtime` resolves to the MODULE (no `_sup`). The supervisor handle lives on the `Runtime` instance built in `_build_local_store_sqlite_runtime` and held by the engine — the engine must expose explicit passthroughs. This is a REQUIRED 2a deliverable (Task 2.4 builds the `begin_drain` passthrough; the 2b route + lifespan call the passthroughs, never a raw attribute chain).
- **[OV-6 / was P3-2 — last_event accessor] Add `[[nodiscard]] std::optional<RuntimeHealthEvent> last_event() const` (snapshot copy under lock)** so the Python forwarder reads the just-emitted event without copying the whole ≤64 vector on every health change. The forwarder maps `last_event()` (not `events()[-1]`).
- **[OV-7 / was P2-1 — verify D3, don't just assert it] Task 2.2 MUST add a concurrent stress test** (one thread loops `note_health`/`begin_drain`, another loops `health()`/`events()`; assert no crash/torn read). Run the C++ test suite under ThreadSanitizer if the toolchain supports it (`-fsanitize=thread`); otherwise the two-thread loop test is the floor. Without this, D3's machinery ships asserted-but-unverified (single-threaded ctest can't exercise the race — though it WILL catch the OV-1 deadlock by hanging).
- **[OV-8 / was P2-2 + P3-4 — binding + dict + disclosure]** Task 2.3 binds `begin_drain` with `py::arg("trigger") = "admin_drain"` (wire the default). Task 2.5's route maps `MetricsSnapshot` to a PLAIN dict (mirror `queries.vitals()`'s plain-dict return — add a `to_dict()` or explicit field mapping; do not return the bound struct raw). **Disclosure:** Phase 2 models DRAINING's WRITE gate only (`check_write` rejects); DRAINING's full behavioral contract (`05_governance.md:42`: reads continue, new background runs refused, `retry_after` on writes) is DEFERRED to Phase 5 — the Self-review's "DRAINING covered" is the drain-ENTRY mechanic only.

---

## File structure (Phase 2)
- `include/starling/governance/runtime_health_event.hpp` (NEW) — `MetricsSnapshot`, `RuntimeHealthEvent`, `HealthDecision` structs + `is_legal_transition(from,to)` pure helper.
- `include/starling/governance/runtime_supervisor.hpp` + `src/governance/runtime_supervisor.cpp` (EXTEND) — transition methods, event log, `begin_drain()`, `note_health()`, updated `check_write()`, `events()`.
- `bindings/python/bind_14_governance.cpp` (EXTEND) — bind the new structs + supervisor methods.
- `python/starling/runtime.py` (EXTEND) — forwarder maps C++ events to the dict shape; expose `begin_drain()`/`events()`/health transitions.
- `python/starling/dashboard/app.py` (EXTEND) — lifespan post-yield `begin_drain()`.
- `python/starling/dashboard/routes/inspect.py` + `queries.py` (EXTEND) — `GET /api/runtime_health`.
- `dashboard/web/src/lib/runtime_health.ts` (NEW) + `dashboard/web/src/routes/runtime-health/+page.svelte` (NEW) + `dashboard/web/src/lib/nav.ts` (EXTEND) — read-only panel.
- Tests: `tests/cpp/test_runtime_supervisor_transitions.cpp` (NEW), extend `tests/python/test_governance_binding.py`, a dashboard route test, a vitest for the panel.

---

## Tasks

### Task 2.1: Health-event value types (C++ structs + transition helper)
**Files:** Create `include/starling/governance/runtime_health_event.hpp`; Test `tests/cpp/test_runtime_health_event.cpp`; Modify `tests/cpp/CMakeLists.txt`. (Header-only structs + a pure `is_legal_transition` — no .cpp unless the helper is non-trivial; if so add `src/governance/runtime_health_event.cpp` + root `CMakeLists.txt`.)

**Interfaces (Produces):**
```cpp
namespace starling::governance {
struct MetricsSnapshot {          // 05_governance.md:33; Phase 5 populates for real
  std::int64_t outbox_lag_sequence = 0;
  double subscriber_failure_rate = 0.0;
  std::int64_t extraction_queue_depth = 0;
  double projection_lag_seconds = 0.0;
  double runtime_event_loop_lag_ms = 0.0;
  std::int64_t vector_delete_lag = 0;
  std::int64_t erased_evidence_visible_count = 0;
};
struct RuntimeHealthEvent {
  RuntimeHealth previous_status = RuntimeHealth::UNREADY;
  RuntimeHealth current_status = RuntimeHealth::UNREADY;
  std::string trigger;
  MetricsSnapshot metrics_snapshot;
  std::vector<std::string> missing_capabilities;  // populated only for →UNREADY
};
struct HealthDecision {           // Phase 5's sampler produces this; Phase 2 accepts it
  RuntimeHealth target_status = RuntimeHealth::READY;
  std::string trigger;
  MetricsSnapshot metrics_snapshot;
};
[[nodiscard]] bool is_legal_transition(RuntimeHealth from, RuntimeHealth to);  // D-P2-7 matrix
}
```
**TDD outline:** test `is_legal_transition` for the full matrix (legal pairs true, illegal pairs false: `DRAINING→READY`=false, `UNREADY→DEGRADED`=false, `any→UNREADY`=true). Structs are POD defaults. → build, RED, implement, GREEN, commit.

### Task 2.2: RuntimeSupervisor state machine + event log (C++ core — the heart)
**Files:** Modify `include/starling/governance/runtime_supervisor.hpp` + `src/governance/runtime_supervisor.cpp`; Test `tests/cpp/test_runtime_supervisor_transitions.cpp`; Modify `tests/cpp/CMakeLists.txt`.

**Interfaces (Produces) — add to `RuntimeSupervisor`:**
```cpp
void note_health(const HealthDecision& decision);  // apply a (Phase-5-sourced) decision: transition to target if legal
void begin_drain(std::string trigger = "admin_drain");  // → DRAINING if legal
[[nodiscard]] std::vector<RuntimeHealthEvent> events() const;  // SNAPSHOT COPY under lock (D3) — NOT const& (race)
// private: std::mutex mtx_; guards health_/exit_code_/events_ (D3). EVERY public method locks at top.
// private: bool transition_to(RuntimeHealth target, std::string trigger, MetricsSnapshot, missing);  // caller already holds mtx_
//   - if !is_legal_transition(health_, target): no-op + return false (no event)
//   - else: push RuntimeHealthEvent{health_, target, trigger, snapshot, missing}; health_ = target; (cap log to D-P2-3 N=64); return true
//   - MUST NOT invoke any external callback while holding mtx_ (Phase 1 supervisor has none — keep it internal).
```
`start()` (existing) now routes its READY/UNREADY sets through `transition_to` so they emit events too (preserving the UNREADY missing_capabilities + the exit-78 set). `check_write()` updated per D-P2-5 (accept READY||DEGRADED).

**TDD outline (the legal/illegal matrix + event payloads):**
- `StartEmitsReadyEvent` / `StartUnreadyEmitsUnreadyEventWithMissing` (start() now emits via the log; assert `events().back()` shape + missing list; exit-78 still set).
- `ReadyToDegradedAndBack` (`note_health({DEGRADED,...})` → DEGRADED + event with trigger/snapshot; back to READY).
- `DegradedAcceptsWrites` (`check_write()==kAccept` in DEGRADED), `DrainingRejectsWrites` (`kPreconditionFailed`), `UnreadyRejectsWrites`.
- `BeginDrainFromReady` / `BeginDrainFromDegraded` → DRAINING + event; `IllegalDrainingToReadyIsNoOp` (no event, state unchanged).
- `AnyStateToUnready` (fail-closed reachable from DEGRADED/DRAINING).
- `EventLogCapsAtN` (push > N transitions, assert size cap per D-P2-3).
- → build (RED), implement `transition_to` + the public methods + `check_write` update, GREEN, commit.

**Note (Phase-1 review carry-over):** the double-probe / fail-closed-default behaviors from Phase 1 are unchanged; do not regress them.

### Task 2.3: Bind the new surface + Python forwarder maps C++ events
**Files:** Modify `bindings/python/bind_14_governance.cpp` (bind `MetricsSnapshot`, `RuntimeHealthEvent`, `HealthDecision`, `RuntimeHealth` already bound; supervisor `events()`/`begin_drain()`/`note_health()`); Modify `python/starling/runtime.py` (forwarder sources events from C++); Test extend `tests/python/test_governance_binding.py`.

**Key (D-P2-2):** `events()` returns `list[RuntimeHealthEvent]` to Python (bind the struct with `def_readonly` fields; expose `current_status`/`previous_status` as `_core.RuntimeHealth`, `trigger`, `metrics_snapshot` as the bound struct or a dict). `Runtime._emit_health` (or `start()`) now derives the `runtime.health_changed` dict from the C++ event instead of constructing it Python-side — **mapping to the EXACT existing shape `{event:"runtime.health_changed", state:<NAME>, missing_capabilities:[...]}`** so `TC-NEW-PREFLIGHT` passes unchanged. (Map `current_status` enum → its name string; `missing_capabilities` from the event.)
**Acceptance:** `TC-NEW-PREFLIGHT` + `test_preflight` + binding test green; rebuild `--python-editable`.

### Task 2.4: Host drain wiring (FastAPI lifespan)
**Files:** Modify `python/starling/dashboard/app.py` (lifespan post-`yield`: `engine`'s supervisor `begin_drain()`).
**Detail (D-P2-6):** in the lifespan shutdown half (after `yield`, before/around `stop_background_tick()`), call `begin_drain()` on the live supervisor (reach via `app.state.engine._runtime._sup` or a `DashboardEngine.begin_drain()` passthrough — add the passthrough to `engine.py` for encapsulation). NO separate signal handler (avoid uvicorn race). `runtime_event_loop_lag_ms` real feed is Phase 5 (leave 0).
**TDD outline:** a test that drives the lifespan shutdown (or calls the engine drain passthrough) and asserts the supervisor reaches DRAINING + an event is logged. → pytest green.

### Task 2.5: Dashboard read route `GET /api/runtime_health`
**Files:** Modify `python/starling/dashboard/routes/inspect.py` (new route) + possibly `queries.py` (if any SQL-derived metric is included); Test `tests/python/test_dashboard_runtime_health_route.py` (NEW).
**Detail:** mirror the vitals route shape. Reach the LIVE supervisor via the engine (not SQL — health/events are in-memory): `_engine(request)._runtime._sup` → return `{status: <RuntimeHealth name>, events: [...recent mapped events...], metrics_snapshot: {...}}`. Read-only.
**Acceptance:** route test asserts the JSON shape + status string; pytest green.

### Task 2.6: Dashboard RuntimeHealth panel (SvelteKit, read-only)
**Files:** Create `dashboard/web/src/lib/runtime_health.ts` (types mirroring the route JSON); Create `dashboard/web/src/routes/runtime-health/+page.svelte` (mirror `vitals/+page.svelte`: `createQuery(()=>api.get<RuntimeHealthResponse>('/api/runtime_health'))`, refetch on WS `tick`, render status Badge + StatusDot + metrics StatCards + a recent-transitions list); Modify `dashboard/web/src/lib/nav.ts` (add entry under `生命体征 · 脑干`, beside `/vitals`).
**Acceptance:** `npm run check` (svelte-check/tsc) + `npx vitest run` + `npm run build` green in `dashboard/web/`. (A small vitest for the status→tone mapping mirrors `vitals.ts`'s `lagTone` test if one exists.)

---

## Phase 2 acceptance
Full 4-state machine reachable with validated transitions + per-transition `RuntimeHealthEvent`; `begin_drain()` + `note_health()` work; `check_write()` accepts READY||DEGRADED; `TC-NEW-PREFLIGHT` + full ctest + full `pytest tests/python` green; dashboard `/api/runtime_health` returns status+events+snapshot and the panel renders (front-end check/vitest/build green). Real metric *sampling* that drives DEGRADED automatically remains Phase 5 (Phase 2 uses manual/test/`note_health` triggers).

## Self-review
- **Spec coverage** (05_governance.md:103-110 state machine + :128-133 event/PreflightResult shapes): READY/DEGRADED/DRAINING/UNREADY reachable (2.2), validated transitions (2.1 matrix + 2.2), `RuntimeHealthEvent` payload (2.1/2.2), drain entry (2.2/2.4), read surface (2.5/2.6). Deferred-with-justification: real 7-metric sampling → Phase 5; worker-lease draining → Phase 4/5; `Bus::write` retry_after fields → Phase 5.
- **Type consistency:** `RuntimeHealth` reused (not redefined); `MetricsSnapshot`/`RuntimeHealthEvent`/`HealthDecision` defined in 2.1, consumed 2.2/2.3; the `runtime.health_changed` dict shape preserved for TC-NEW-PREFLIGHT (D-P2-2).
- **Boundary:** all transition/validation/event logic is C++; Python/TS are host-glue + read-only.
- **Placeholder note:** dashboard tasks (2.5/2.6) are at interface+pattern-ref grain (mirror the verified vitals pattern) — exact code written in the implementer briefs at execution time; C++ core (2.1/2.2) carries concrete signatures + the transition matrix. This matches Phase 1's brief-driven execution.

## Test coverage (2a — Tasks 2.1-2.4)

```
C++ CORE (2a)                                          COVERAGE
[+] runtime_health_event.hpp (2.1)
  └── is_legal_transition(from,to)
      ├── [★★★ planned] full matrix: legal pairs + illegal pairs (DRAINING→READY=F, UNREADY→DEGRADED=F, any→UNREADY=T)
[+] runtime_supervisor.{hpp,cpp} (2.2)
  ├── start() → READY / UNREADY(+exit-78)              [★★★ planned] StartEmits{Ready,Unready}Event (OV-3 self-loop + OV-4 exit-code)
  ├── note_health(decision) → transition               [★★★ planned] ReadyToDegradedAndBack
  ├── begin_drain() → DRAINING                          [★★★ planned] BeginDrainFrom{Ready,Degraded} + IllegalDrainingToReadyIsNoOp
  ├── check_write() READY||DEGRADED / else              [★★★ planned] Degraded accepts / Draining + Unready reject
  ├── transition_to_locked (emit iff from!=to|→UNREADY) [★★★ planned] EventLogCapsAtN=64 ; self-loop emit rule
  └── mutex discipline (D3 + OV-1)                       [★★★ planned] OV-7 two-thread stress (TSan if available) — verifies no deadlock + no torn read
[+] bind_14_governance.cpp (2.3) + runtime.py (2.3)
  ├── events()/last_event() copy semantics (OV-2/6)     [★★ planned] test_governance_binding: events list shape + last_event
  └── forwarder maps last_event→dict (D-P2-2)           [★★★ CRITICAL] TC-NEW-PREFLIGHT stays green UNCHANGED (1 event, {event,state,missing})
[+] dashboard/engine.py passthrough (2.4, OV-5)
  └── DashboardEngine.begin_drain()                      [★★ planned] lifespan-drain test → supervisor DRAINING + event

COVERAGE: all 2a code paths have planned tests. CRITICAL pin: TC-NEW-PREFLIGHT unchanged.
GAPS CLOSED BY REVIEW: OV-1 deadlock (caught by OV-7 concurrent test + single-thread hang), OV-3 self-loop emit, OV-5 broken engine path.
```

Failure modes (2a): (1) self-deadlock on `start()` → FIXED by OV-1 public/`_locked` split, verified by OV-7. (2) torn read of `events_`/`health_` from the dashboard thread → FIXED by D3 mutex + OV-2 copy semantics. (3) event-log flood from a READY-reaffirming sampler → FIXED by OV-3 emit rule. No remaining critical gap (no untested + unhandled + silent failure path).

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 1 | timed_out | Codex timed out (5m) → Claude-subagent outside-voice fallback ran |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | clean | 1 arch finding (thread-safety, locked D3); scope reduced to 2a/2b (D2); D-P2-1..7 locked; 8 outside-voice corrections (OV-1..8) all folded; 0 unresolved |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — (2b dashboard panel → run /plan-design-review when 2b is detailed) |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

Step 0 scope: REDUCED — Phase 2 split into 2a (C++ core, Tasks 2.1-2.4) + 2b (dashboard panel, Tasks 2.5-2.6) per D2; this review targets 2a. Boring tech [Layer 1] (state machine + health monitoring, no new infra, established pybind patterns; 0 innovation tokens). Architecture: 1 finding (D3 supervisor self-mutex + `events()` snapshot). Code Quality: 0 new (transition_to centralizes — DRY; corrections folded). Tests: coverage diagram produced; OV-7 concurrent/TSan test added to verify D3. Performance: 0 (in-memory state machine, capped log, `last_event()` avoids full-vector copy). NOT in scope: real 7-metric sampling → Phase 5; DRAINING read/background-reject behavioral contract + `retry_after` → Phase 5; worker-lease draining → Phase 4/5; the 2b dashboard panel → its own follow-up PR. What already exists (reused): the dead `RuntimeHealthMonitor` (left dead — supervisor absorbs the machine per D-P2-1), the `RuntimeHealth` 4-value enum (already bound), the vitals route→type→panel→nav pattern (2b mirrors it), the engine RLock (supervisor self-locks instead, per D3). Parallelization: 2a is SEQUENTIAL (2.1 structs → 2.2 state machine → 2.3 binding → 2.4 host passthrough; dependency chain); no worktree split.

- **CODEX:** timed out after 5 minutes (`model_reasoning_effort=high` on the plan + Phase-1 code read). Fell back to a fresh-context Claude opus subagent for the outside voice — it caught the OV-1 `start()`→`run_preflight()` self-deadlock (a real bug in the locked D3), the OV-3 self-transition emit rule, and the OV-5 broken `engine._runtime._sup` path, plus 5 refinements. All 8 folded (user-approved).
- **CROSS-MODEL:** only one independent voice ran (Claude subagent; codex unavailable). No tension — the outside voice agreed with the review's architecture direction (thread-safety needed, state machine in the supervisor) and strengthened it by finding implementation-level defects the section review missed.
- **VERDICT:** ENG CLEARED — Phase 2 **2a** (C++ governance core) ready to implement once **PR #30 (Phase 1) merges**. 2b (dashboard panel) is a sequenced follow-up; run /plan-design-review when 2b is detailed.

NO UNRESOLVED DECISIONS

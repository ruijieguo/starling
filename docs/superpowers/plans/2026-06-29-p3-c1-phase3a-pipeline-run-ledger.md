# P3.c1 Phase 3a — Governance PipelineRun Ledger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the governance long-task ledger core — a new SQLite table `governance_pipeline_run` plus a single-writer C++ `PipelineRunStore` (enqueue/claim/confirm/reclaim/find_active_run/dead_letter/record_stage_timing) with the lifecycle state machine and the active-run dedup invariant — distinct from the M0.4 extraction-cost ledger.

**Architecture:** A new core governance store under `src/governance/` + `include/starling/governance/`, mirroring the existing `bus::PipelineLedger` write discipline (`INSERT`-then-detect dedup in the writer, never a caller-side set) and the `store::PerceptionStateStore` shape (`struct` row + `class`(`Connection&`) with `SELECT→struct` read-back). The ledger persists the PipelineRun lifecycle defined in `docs/design/subsystems_design/05_governance.md` §数据模型 / §PipelineRun 生命周期 / §不变式. Scalars are first-class columns; the structured sub-fields are JSON text (SQLite JSON1). **This is Phase 3a (the ledger substrate). Phase 3b (StageTimer RAII + wiring stage timings into the `memory_ops` tick + `replay_scheduler`) is a cascade follow-up planned after 3a's schema lands.**

**Tech Stack:** C++20, SQLite (raw `sqlite3_*` via `starling::persistence` helpers), pybind11 (binding, scope TBD by eng-review), ctest. No new third-party deps.

## Global Constraints

- **Architecture boundary (hard rule, CLAUDE.md / governance-core.md:13):** core semantics in C++ (`src/` + `include/starling/`); Python only adapter/config/read-only. The whole `PipelineRunStore` + struct + enums + migration + invariant enforcement is CORE C++. Cross-language test: *would another binding language need to rewrite this logic? → yes → core.*
- **Single-writer / table ownership:** `governance_pipeline_run`'s sole writer is `src/governance/pipeline_run_store.cpp`. No raw `INSERT`/`UPDATE` into this table anywhere else; all writes go through `PipelineRunStore` methods (mirrors the `statements`-table → `SqliteStatementStore` rule the CI static-scan enforces).
- **Idempotent dedup invariant lives in the WRITER (CLAUDE.md 写入纪律):** invariant 1 (no two active runs per `(kind, aggregate_id, input_hash)`) is enforced by the writer via `INSERT`-then-detect against a partial UNIQUE index — never a caller-maintained set. Mirrors `PipelineLedger::record_attempt`'s `INSERT OR IGNORE` (first-write-wins, returns existing on conflict).
- **Status / kind string forms are CONTRACT (frozen by the migration's partial index):** `status` stored as the spec's UPPERCASE names verbatim — `QUEUED RUNNING PAUSED COMPLETED PARTIAL_SUCCESS DEGRADED_COMPLETED FAILED CANCELLED DEAD_LETTERED`; `kind` as the spec literals — `extraction replay projection_rebuild container_rebuild compliance_erase retrieval_eval migration`. The partial index's `WHERE status IN ('QUEUED','RUNNING')` depends on these exact bytes; `status_to_string` MUST emit them.
- **Migration SQL is checksum-frozen once applied (`migration_runner.cpp` drift check):** `0029_*.sql` must be correct the first time — a later edit throws `MigrationDriftError` on any DB that already applied it. Get the schema right before merge.
- **clang-tidy is a CI-only gate (un-runnable locally, macOS 26 SDK) — write clean by construction.** Known gotchas: scoped enums need `: std::uint8_t` (performance-enum-size); identifiers ≥3 chars (readability-identifier-length); `[[nodiscard]]` on pure queries (modernize-use-nodiscard); always-brace; **no `bugprone-branch-clone`** (no two byte-identical consecutive `case` bodies — merge via fall-through); prefer `std::ranges`. New files: every line is a changed-line, so all of the above bite.
- **Build / gates:** `python scripts/configure_build.py --build --test` (C++ + ctest); after any binding/migration change also `--python-editable` to reinstall `_core`. `pytest tests/python` via `.venv/bin/python`. git: explicit-path `git add` only (no `git add .`/`-A`); no `--no-verify`/`--amend`. Commit footer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

## Phase 3 context + the 3a/3b split

Phase 3 of the P3.c1 governance roadmap = **"PipelineRun governance ledger + stage_timing"** (`docs/superpowers/plans/2026-06-28-p3-c1-governance-core.md:117,448-456`). It is **core-only** — no dashboard route/panel (acceptance = "ctest + pytest green", governance-core.md:456). It splits cleanly along a dependency seam, mirroring Phase 2's 2a-core / 2b-surface split:

- **3a (THIS PLAN) — ledger substrate.** The table + store + lifecycle + invariant 1. No live consumer beyond C++ tests; this is the durable substrate later phases/P3+ multi-lane consume. Spec mandates building + testing the full machinery now (governance-core.md:454-456) even though c1's eventual live consumer (the inline tick) exercises only a trivial slice.
- **3b (cascade follow-up) — stage_timing instrumentation.** `include/starling/governance/stage_timer.hpp` (RAII, records `{stage, ms}` into a run on scope exit via `record_stage_timing`) + the **run-creation seam** for the inline single-threaded `memoryops::tick_all` (which today creates NO PipelineRun) + wiring into the 6 tick stages (embed → policy → CommonGround → replay → projection → outbox, governance-core.md:43) + `replay_scheduler.cpp`. 3b carries open-question #2 (where/when a tick-cycle run is created) — deferred to the 3b plan, written after 3a's schema lands (cascade rule, governance-core.md:113).

3a has **no ambiguity blocker** — it is "build the table + writer the spec specifies." The genuine forks below are scope-depth decisions for `/plan-eng-review`, not blockers.

## OPEN DECISIONS for `/plan-eng-review` (lock these; implementers apply over task text)

The spec leaves these to the Phase 3 plan (governance-core.md:496 + open questions). Baseline proposals are folded into the tasks below; eng-review confirms or amends.

> **SUPERSEDED 2026-06-29 — all 7 forks resolved + Codex outside-voice (14 findings) folded. The LOCKED block immediately below is AUTHORITATIVE; implementers apply IT over the task text. The D1–D7 bullets that follow are retained as rationale only.**

### LOCKED eng-review decisions (2026-06-29) — apply OVER task text

**Forks:**
- **D1 → DEFER the binding.** No `bind_14_governance.cpp` edit in 3a; **drop Task 3a.7** (re-add when a Python/dashboard consumer lands). 3a = C++ core + ctest only.
- **D2 → DEFER invariant-4 health coupling.** `dead_letter` records terminal status + `error_kind` only; NO `RuntimeSupervisor` dependency. (Reconciled by CX-10.)
- **D3 → pure roll-up helper only; defer aggregation.** Per **CX-14**, name it `partial_terminal_rollup(std::span<const PipelineRunStatus>) → PipelineRunStatus` (NOT `roll_up_status`); it realizes only success/fail → PARTIAL_SUCCESS / COMPLETED / FAILED. Document it is NOT full invariant 7 — all-NOOP→NOOP is unrepresentable (9-state enum has no NOOP; flagged for c2).
- **D5 → opaque JSON strings.** 7 sub-fields = TEXT columns (default `'{}'`/`'[]'`); no typed structs. `record_stage_timing` appends via `json_insert(stage_timings_ms,'$[#]',json_object('stage',?,'ms',?))`.
- **D6 → `enqueue(NewRun)→PipelineRun` + fail-loud throw.** Mutators throw when their status-guarded UPDATE matches 0 rows. (Refined by CX-3/CX-4.)
- **D4 (folded):** invariant-2 deferred to c2 (`step_contracts` opaque). **D7 (folded):** all 7 kinds in the enum; tests exercise `replay`/`projection_rebuild`.
- **Tx + locking (folded):** store methods are statement-only (NO `BEGIN`); the caller owns the transaction (mirror `PipelineLedger` + the extractor's `TransactionGuard`). **NO `std::mutex`** in the store (mirror `PipelineLedger`/`PerceptionStateStore`; offline single-threaded tick + SQLite + caller tx handle concurrency).

**Codex outside-voice amendments (all folded):**
- **CX-1 → add `tenant_id`.** `PipelineRun` + `NewRun` gain `std::string tenant_id`; migration adds `tenant_id TEXT NOT NULL`; active UNIQUE index becomes `(kind, tenant_id, aggregate_id, input_hash)`; signature `find_active_run(kind, tenant_id, aggregate_id, input_hash)`. Closes cross-tenant run suppression (matches M0.4 `pipeline_run` + the ScopedWorkGate gate_key). **Migration SQL corrected in-place in Task 3a.2.**
- **CX-2 → CHECK constraints (frozen).** `kind TEXT NOT NULL CHECK(kind IN (…7…))`, `status TEXT NOT NULL CHECK(status IN (…9…))` — a typo status would otherwise bypass the partial index → violate invariant 1. **In-place in Task 3a.2.**
- **CX-3 → `enqueue` uses plain `INSERT` (NOT `INSERT OR IGNORE`).** With CHECK present, `OR IGNORE` masks CHECK violations as "lost a race." Logic: `find_active_run` fast path → return if found; else plain `INSERT`; on a UNIQUE conflict (partial active index) → re-`find_active_run` + return the winner; ANY other constraint failure (CHECK) → propagate as throw.
- **CX-4 → `dead_letter` status-guarded.** `UPDATE … SET status='DEAD_LETTERED', error_kind=?, updated_at=? WHERE id=? AND status='RUNNING'`; 0 rows → throw (rejects QUEUED→/terminal→/double dead-letter). Does **NOT** touch `retry_count` (CX-9).
- **CX-5/6/7 → add `record_checkpoint` + `cancel`; defer FAILED/PAUSED.** `record_checkpoint(run_id, checkpoint_sequence, watermark_json)` (`WHERE id=? AND status='RUNNING'`; makes reclaim-resume real, spec:49) + `cancel(run_id)` (`→CANCELLED`, `WHERE id=? AND status IN ('QUEUED','RUNNING')`). FAILED (transient retry-state, murky + no c1 producer) + PAUSED (DRAINING-coordination, no c1 semantics) stay enum-only, **documented as unreachable-in-c1** (header comment).
- **CX-8 → lease canonicalization.** `claim`/`reclaim`/`record_checkpoint` require `lease_until` as canonical `iso8601_utc` (`YYYY-MM-DDTHH:MM:SSZ`) — `reclaim`'s lexicographic `lease_until < now` only holds for that exact form. Document the caller-contract in the header; tests use `iso8601_utc`.
- **CX-9 → `retry_count` = reclaim count.** ONLY `reclaim` increments it; `dead_letter`/`cancel`/`confirm` do not. Document in the header.
- **CX-10 → `enqueue` rejects `ComplianceErase` (fail-closed).** Until the invariant-4 coupling lands (D2), `enqueue` throws on `kind==PipelineKind::ComplianceErase`. Document the re-enable condition.
- **CX-11 → JSON1 probe test.** Assert `SELECT json_insert('[]','$[#]',1)` works (repo's `find_package(SQLite3 3.46)` ships JSON1 by default; the probe makes it explicit; a fail means `record_stage_timing` needs a real-parse fallback).
- **CX-12 → harden frozen-migration tests (T1).** Migration test asserts the partial-index DEFINITION (`sql` from `sqlite_master` incl. the columns + `WHERE`), the CHECK constraints (illegal status/kind INSERT → `SQLITE_CONSTRAINT`), and real duplicate-rejection (2nd active row same key → `SQLITE_CONSTRAINT`). `record_stage_timing` test PARSES the JSON array (count + values), not substring-match.
- **CX-13 → recheck migration number before merge.** `0029` is next NOW; immediately before implementation AND before merge re-run `ls migrations/ | sort | tail -1`; if a collision landed, rename to the next free number (runner keys by the filename numeric prefix → collision = `MigrationDriftError`).

**T1 → add all 6 negative/edge tests** (invariant-1 DB-constraint backstop; reclaim-when-lease-VALID → refused; confirm non-RUNNING / illegal-terminal → throw; every mutator on missing run → throw; get missing-id → nullopt; `partial_terminal_rollup` all-fail + empty-span). **CQ1 → 4th local `random_id` copy** in `pipeline_run_store.cpp` + a one-line TODO that it joins the documented `starling/util/uuid.hpp` consolidation (M0.4+1).

**Net store API after amendments:** `enqueue` · `find_active_run(kind,tenant_id,aggregate_id,input_hash)` · `get` · `claim` · `reclaim` · `confirm` · `record_checkpoint` · `cancel` · `dead_letter` · `record_stage_timing` · `static partial_terminal_rollup(span)`. Reachable states: QUEUED · RUNNING · COMPLETED · PARTIAL_SUCCESS · DEGRADED_COMPLETED · CANCELLED · DEAD_LETTERED (7/9). Enum-only deferred: FAILED · PAUSED.

- **D1 — Binding scope.** governance-core.md:452 lists `bind_14_governance.cpp` in Phase 3 files, but Phase 3 is core-only and **nothing in c1 consumes `PipelineRunStore` from Python** (no dashboard route; the 3b tick wiring is C++-internal). Proposal: **DEFER the binding** (YAGNI — don't bind what nothing calls; add it when a Python/dashboard consumer lands, e.g. a future "pipeline runs" read view). Task 3a.7 is written but gated on this decision. *Alt:* bind a minimal read-only surface (`get`, `find_active_run`) now for forward symmetry with 2b.
- **D2 — Invariant 4 (DEAD_LETTERED compliance → hold RuntimeHealth DEGRADED + alert).** This couples `dead_letter` to `RuntimeSupervisor::note_health`. Proposal: **3a stores the terminal status + `error_kind` only; the health-coupling is a CONSUMER concern** (the caller inspects `kind ∈ compliance lane` and calls `supervisor.note_health(DEGRADED)`), deferred to the phase that wires a real compliance run. 3a exposes enough (the run's `kind`) for that caller. *Alt:* inject a `RuntimeSupervisor*` hook into `dead_letter` now.
- **D3 — Invariant 7 (NOOP vs PARTIAL_SUCCESS roll-up for `business_task_id` aggregation).** Needs multi-item runs (`item_run_ids`), which have no producer in c1. Proposal: ship a **pure, unit-tested `roll_up_status(span of item statuses) → PipelineRunStatus`** helper (testable in isolation, no DB), but **defer the aggregation wiring** (no consumer). *Alt:* full `business_task_id` aggregation now.
- **D4 — Invariant 2 (failure_policy fixed `critical` for compliance/outbox/commitment).** Lives on `step_contracts`, which are **opaque in c1** (step-graph validation = invariant 8, deferred to c2/Substrate). Proposal: **3a stores `step_contracts` as opaque JSON; invariant 2 enforcement deferred to c2.** Confirm.
- **D5 — JSON-modeling depth.** `watermark / progress / counters / warnings / stage_timings_ms / item_run_ids / step_contracts` are dict/list fields. Proposal: **store as opaque JSON `std::string`** columns (default `'{}'`/`'[]'`); the store only structurally manipulates `stage_timings_ms` (append via SQLite `json_insert`) and accepts `checkpoint`/`watermark` as caller-supplied JSON in `confirm`. No typed C++ structs for these in 3a (YAGNI until a consumer needs to read them field-wise). *Alt:* typed `Watermark`/`StageTiming` structs + (de)serialization now.
- **D6 — The create/enqueue method.** The spec's operations block (05_governance.md:144-154) names claim/confirm/reclaim/find_active_run but **not the method that mints a QUEUED run** (lifecycle step 1-2 implies one). Proposal: **`enqueue(NewRun spec) → PipelineRun`** that does find-active-dedup + `INSERT`-then-detect (the invariant-1 site), returning the existing active run on dup. Confirm the name/shape.
- **D7 — `kind` coverage in c1 tests.** 7 kinds enumerated; c1 only ever runs `extraction`(separate ledger)/`replay`/`projection_rebuild` via the tick. Proposal: **enum carries all 7; tests exercise the lifecycle with `replay`/`projection_rebuild`; the rest are enum-only.** Confirm.

---

## File Structure

- **Create** `include/starling/governance/pipeline_run.hpp` — value types: `PipelineKind` + `PipelineRunStatus` scoped enums (`: std::uint8_t`) with `*_to_string`/`*_from_string` + `is_active(status)`; `PipelineRun` read-back struct (scalars typed, JSON sub-fields as `std::string`); `NewRun` input struct for `enqueue`. Header-only (no .cpp) where trivial; free functions `inline`.
- **Create** `migrations/0029_governance_pipeline_run.sql` — `CREATE TABLE governance_pipeline_run` + partial UNIQUE active index + lease index. Auto-embedded by the CMake `migrations/*.sql` glob (`CMakeLists.txt:201`), auto-applied as version 29 by `MigrationRunner`.
- **Create** `include/starling/governance/pipeline_run_store.hpp` — `class PipelineRunStore { explicit PipelineRunStore(persistence::Connection&); ... };` interface (mirrors `PerceptionStateStore` / `PipelineLedger`).
- **Create** `src/governance/pipeline_run_store.cpp` — the implementation.
- **Modify** `CMakeLists.txt` — add `src/governance/pipeline_run_store.cpp` to the same library target that already compiles `src/governance/runtime_supervisor.cpp` + `capability_policy.cpp` (follow the existing entry; if that target uses a `src/governance/*.cpp` glob, no edit needed — verify).
- **Create** `tests/cpp/test_pipeline_run_store.cpp` (or the repo's ctest convention — mirror `tests/cpp/test_runtime_supervisor*`) — the lifecycle + invariant tests; register with ctest like the sibling governance tests.
- **(D1-gated) Modify** `bindings/python/bind_14_governance.cpp` — bind `PipelineRunStore` + `PipelineRun` + enums, only if eng-review keeps the binding in 3a.

**Interfaces (Produces — what 3b + later consume):**
- `starling::governance::PipelineKind`, `PipelineRunStatus` (+ `to_string`/`from_string`/`is_active`)
- `starling::governance::PipelineRun` (read-back struct), `NewRun` (enqueue input)
- `PipelineRunStore(persistence::Connection&)` with:
  - `PipelineRun enqueue(const NewRun&)` — create QUEUED + invariant-1 dedup (returns existing active run on dup)
  - `std::optional<PipelineRun> find_active_run(kind, aggregate_id, input_hash)`
  - `std::optional<PipelineRun> get(run_id)` — read by id
  - `PipelineRun claim(run_id, worker_id, lease_until)` — QUEUED→RUNNING + lease
  - `PipelineRun reclaim(run_id, worker_id, lease_until)` — expired-lease RUNNING → re-claim, `retry_count++`
  - `PipelineRun confirm(run_id, checkpoint_json, PipelineRunStatus terminal)` — RUNNING→COMPLETED/PARTIAL_SUCCESS/DEGRADED_COMPLETED + checkpoint/watermark
  - `void dead_letter(run_id, error_kind)` — →DEAD_LETTERED
  - `void record_stage_timing(run_id, stage, ms)` — append `{stage,ms}` to `stage_timings_ms`
  - `static PipelineRunStatus roll_up_status(std::span<const PipelineRunStatus> items)` — invariant-7 pure helper (D3)

---

## Task 3a.1: PipelineRun value types header

**Files:**
- Create: `include/starling/governance/pipeline_run.hpp`
- Test: add `tests/cpp/test_pipeline_run_types.cpp` (or fold into `test_pipeline_run_store.cpp` — match repo ctest convention; mirror Task 2.1's `runtime_health_event` header test)

**Interfaces:**
- Produces: `PipelineKind`, `PipelineRunStatus`, `kind_to_string`/`kind_from_string`, `status_to_string`/`status_from_string`, `is_active(PipelineRunStatus)`, `struct PipelineRun`, `struct NewRun`.

- [ ] **Step 1: Write the failing test** (enum↔string round-trip + is_active + the frozen string forms)

```cpp
#include "starling/governance/pipeline_run.hpp"
#include <cassert>
namespace gov = starling::governance;

static void test_status_string_forms_are_frozen_contract() {
    // These exact bytes are referenced by the migration's partial index.
    assert(gov::status_to_string(gov::PipelineRunStatus::Queued) == std::string("QUEUED"));
    assert(gov::status_to_string(gov::PipelineRunStatus::Running) == std::string("RUNNING"));
    assert(gov::status_to_string(gov::PipelineRunStatus::PartialSuccess) == std::string("PARTIAL_SUCCESS"));
    assert(gov::status_to_string(gov::PipelineRunStatus::DegradedCompleted) == std::string("DEGRADED_COMPLETED"));
    assert(gov::status_to_string(gov::PipelineRunStatus::DeadLettered) == std::string("DEAD_LETTERED"));
    // round-trip every status
    for (auto s : {gov::PipelineRunStatus::Queued, gov::PipelineRunStatus::Running,
                   gov::PipelineRunStatus::Paused, gov::PipelineRunStatus::Completed,
                   gov::PipelineRunStatus::PartialSuccess, gov::PipelineRunStatus::DegradedCompleted,
                   gov::PipelineRunStatus::Failed, gov::PipelineRunStatus::Cancelled,
                   gov::PipelineRunStatus::DeadLettered}) {
        assert(gov::status_from_string(gov::status_to_string(s)) == s);
    }
}

static void test_kind_string_forms() {
    assert(gov::kind_to_string(gov::PipelineKind::ProjectionRebuild) == std::string("projection_rebuild"));
    assert(gov::kind_to_string(gov::PipelineKind::ComplianceErase) == std::string("compliance_erase"));
    for (auto k : {gov::PipelineKind::Extraction, gov::PipelineKind::Replay,
                   gov::PipelineKind::ProjectionRebuild, gov::PipelineKind::ContainerRebuild,
                   gov::PipelineKind::ComplianceErase, gov::PipelineKind::RetrievalEval,
                   gov::PipelineKind::Migration}) {
        assert(gov::kind_from_string(gov::kind_to_string(k)) == k);
    }
}

static void test_is_active() {
    assert(gov::is_active(gov::PipelineRunStatus::Queued));
    assert(gov::is_active(gov::PipelineRunStatus::Running));
    assert(!gov::is_active(gov::PipelineRunStatus::Completed));
    assert(!gov::is_active(gov::PipelineRunStatus::DeadLettered));
    assert(!gov::is_active(gov::PipelineRunStatus::Paused));  // PAUSED is NOT active for invariant 1
}
```

- [ ] **Step 2: Run to verify it fails** — `ctest --test-dir build-macos -R pipeline_run` → FAIL (header missing). (Build first via `configure_build.py --build`.)

- [ ] **Step 3: Write the header**

```cpp
#pragma once
#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace starling::governance {

// 7 kinds (05_governance.md:68). String forms are the spec literals (stored in
// the kind column). : std::uint8_t for performance-enum-size (clang-tidy).
enum class PipelineKind : std::uint8_t {
    Extraction, Replay, ProjectionRebuild, ContainerRebuild,
    ComplianceErase, RetrievalEval, Migration
};

// 9-state lifecycle (05_governance.md:80). String forms are the spec UPPERCASE
// names — FROZEN: the migration's partial active index references 'QUEUED'/'RUNNING'.
enum class PipelineRunStatus : std::uint8_t {
    Queued, Running, Paused, Completed, PartialSuccess,
    DegradedCompleted, Failed, Cancelled, DeadLettered
};

[[nodiscard]] std::string_view kind_to_string(PipelineKind kind);
[[nodiscard]] PipelineKind kind_from_string(std::string_view str);  // throws std::invalid_argument on unknown
[[nodiscard]] std::string_view status_to_string(PipelineRunStatus status);
[[nodiscard]] PipelineRunStatus status_from_string(std::string_view str);

// Invariant 1's "active" predicate: a run blocks a duplicate iff QUEUED or RUNNING
// (PAUSED does NOT block — it has released its claim). Matches the partial index WHERE.
[[nodiscard]] constexpr bool is_active(PipelineRunStatus status) {
    return status == PipelineRunStatus::Queued || status == PipelineRunStatus::Running;
}

// Read-back row. Scalars typed; structured sub-fields are opaque JSON text (D5).
struct PipelineRun {
    std::string id;
    PipelineKind kind{};
    std::string aggregate_id;
    std::optional<std::string> business_task_id;
    std::optional<std::string> parent_run_id;
    std::string profile_name;
    std::string input_hash;
    std::string idempotency_key;
    std::string pipeline_name;
    std::string pipeline_version;
    PipelineRunStatus status{};
    std::optional<long long> checkpoint_sequence;
    std::optional<std::string> error_kind;
    long long retry_count = 0;
    std::optional<std::string> worker_id;
    std::optional<std::string> lease_until;     // ISO-8601 UTC
    std::string item_run_ids   = "[]";          // JSON
    std::string step_contracts = "[]";          // JSON (opaque in c1, D4)
    std::string watermark      = "{}";          // JSON
    std::string progress       = "{}";          // JSON
    std::string counters       = "{}";          // JSON
    std::string warnings       = "[]";          // JSON
    std::string stage_timings_ms = "[]";        // JSON array of {stage, ms}
    std::string started_at;                      // ISO-8601 UTC
    std::string updated_at;                      // ISO-8601 UTC
};

// enqueue() input — the caller-supplied identity of a new run. Optional fields
// default per the table DEFAULTs.
struct NewRun {
    PipelineKind kind{};
    std::string aggregate_id;
    std::string profile_name;
    std::string input_hash;
    std::string idempotency_key;
    std::string pipeline_name;
    std::string pipeline_version;
    std::optional<std::string> business_task_id;
    std::optional<std::string> parent_run_id;
    std::string step_contracts = "[]";  // opaque JSON (D4)
};

}  // namespace starling::governance
```

Note the string-mapping free functions need a .cpp OR `inline` definitions in the header. Header-only `inline` keeps Task 3a.1 self-contained (no new .cpp/CMake edit yet) — define `kind_to_string` etc. as `inline` with a `switch` (NO two identical consecutive `case` bodies — each returns a distinct literal, so `bugprone-branch-clone` does not fire; keep the trailing `throw`/`return` after the switch for `-Wreturn-type`). `from_string` does the reverse lookup (if/else chain or a small lookup); throw `std::invalid_argument` on unknown.

- [ ] **Step 4: Run to verify it passes** — `ctest --test-dir build-macos -R pipeline_run` → PASS.

- [ ] **Step 5: Commit** — `git add include/starling/governance/pipeline_run.hpp tests/cpp/test_pipeline_run_types.cpp <CMake/test-registration files>` + commit.

---

## Task 3a.2: Migration — `governance_pipeline_run` table + indices

**Files:**
- Create: `migrations/0029_governance_pipeline_run.sql`
- Test: `tests/cpp/test_pipeline_run_store.cpp` — a migration-applied assertion (open a fresh in-memory/temp DB, run `MigrationRunner::migrate_to_latest()`, assert the table + both indices exist via `sqlite_master`). Mirror how existing tests obtain a migrated `Connection` (reuse the test fixture/helper other store tests use — find it; do NOT hand-roll a second migration path).

- [ ] **Step 1: Write the failing test**

```cpp
// In the store test's fixture: a migrated temp-file Connection (mirror the helper
// the sibling store/extractor tests use — e.g. a make_migrated_connection()).
static void test_migration_creates_governance_pipeline_run() {
    auto conn = make_migrated_connection();  // applies all migrations incl. 0029
    sqlite3* db = conn->raw();
    auto exists = [&](const char* sql, const char* name) {
        sqlite3_stmt* st = nullptr;
        sqlite3_prepare_v2(db, sql, -1, &st, nullptr);
        sqlite3_bind_text(st, 1, name, -1, SQLITE_STATIC);
        bool found = (sqlite3_step(st) == SQLITE_ROW) && sqlite3_column_int(st, 0) == 1;
        sqlite3_finalize(st);
        return found;
    };
    assert(exists("SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?",
                  "governance_pipeline_run"));
    assert(exists("SELECT count(*) FROM sqlite_master WHERE type='index' AND name=?",
                  "idx_governance_pipeline_run_active"));
    assert(exists("SELECT count(*) FROM sqlite_master WHERE type='index' AND name=?",
                  "idx_governance_pipeline_run_lease"));
}
```

- [ ] **Step 2: Run to verify it fails** — table absent → assertion fails.

- [ ] **Step 3: Write the migration** (`migrations/0029_governance_pipeline_run.sql`)

```sql
-- P3.c1 Phase 3a: governance PipelineRun ledger — the long-task lifecycle account
-- (enqueue/claim/confirm/reclaim/find_active_run/dead_letter + per-stage timing),
-- DISTINCT from the M0.4 extraction-cost ledger (pipeline_run + extraction_attempt).
-- Sole writer: src/governance/pipeline_run_store.cpp. Scalars are first-class
-- columns; structured sub-fields are JSON text (SQLite JSON1). See
-- docs/design/subsystems_design/05_governance.md §数据模型.
CREATE TABLE governance_pipeline_run (
    id                  TEXT PRIMARY KEY,
    kind                TEXT NOT NULL CHECK(kind IN ('extraction','replay','projection_rebuild','container_rebuild','compliance_erase','retrieval_eval','migration')),
    aggregate_id        TEXT NOT NULL,
    tenant_id           TEXT NOT NULL,
    business_task_id    TEXT,
    parent_run_id       TEXT,
    profile_name        TEXT NOT NULL,
    input_hash          TEXT NOT NULL,
    idempotency_key     TEXT NOT NULL,
    pipeline_name       TEXT NOT NULL,
    pipeline_version    TEXT NOT NULL,
    status              TEXT NOT NULL CHECK(status IN ('QUEUED','RUNNING','PAUSED','COMPLETED','PARTIAL_SUCCESS','DEGRADED_COMPLETED','FAILED','CANCELLED','DEAD_LETTERED')),
    checkpoint_sequence INTEGER,
    error_kind          TEXT,
    retry_count         INTEGER NOT NULL DEFAULT 0,
    worker_id           TEXT,
    lease_until         TEXT,
    item_run_ids        TEXT NOT NULL DEFAULT '[]',
    step_contracts      TEXT NOT NULL DEFAULT '[]',
    watermark           TEXT NOT NULL DEFAULT '{}',
    progress            TEXT NOT NULL DEFAULT '{}',
    counters            TEXT NOT NULL DEFAULT '{}',
    warnings            TEXT NOT NULL DEFAULT '[]',
    stage_timings_ms    TEXT NOT NULL DEFAULT '[]',
    started_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

-- Invariant 1 (05_governance.md:185): at most one ACTIVE run (QUEUED|RUNNING) per
-- (kind, aggregate_id, input_hash). Partial UNIQUE index enforces it at the DB
-- level so the writer can INSERT-then-detect (mirrors PipelineLedger's
-- INSERT OR IGNORE first-write-wins) instead of a caller-side set.
CREATE UNIQUE INDEX idx_governance_pipeline_run_active
    ON governance_pipeline_run(kind, tenant_id, aggregate_id, input_hash)
    WHERE status IN ('QUEUED', 'RUNNING');

-- Lease-sweep + status scans (reclaim of expired leases; find_active_run).
CREATE INDEX idx_governance_pipeline_run_lease
    ON governance_pipeline_run(status, lease_until);
```

- [ ] **Step 4: Run to verify it passes** — rebuild (`configure_build.py --build` re-globs migrations → regenerates `migrations.inc`), then the migration test PASSES. **Also run `--python-editable`** (migration set changed → `_core` must re-embed it) and a quick `pytest tests/python -k migration` smoke if one exists, to confirm no drift on the Python-side DB bootstrap.

- [ ] **Step 5: Commit** — `git add migrations/0029_governance_pipeline_run.sql tests/cpp/test_pipeline_run_store.cpp` + commit.

---

## Task 3a.3: PipelineRunStore — `enqueue` (invariant 1) + `find_active_run` + `get`

**Files:**
- Create: `include/starling/governance/pipeline_run_store.hpp`, `src/governance/pipeline_run_store.cpp`
- Modify: `CMakeLists.txt` (add the .cpp to the governance target — verify glob first)
- Test: `tests/cpp/test_pipeline_run_store.cpp`

**Interfaces:**
- Consumes: Task 3a.1 types; `persistence::Connection` + the `bind_sv`/`iso8601_utc`/`make_sqlite_error`/`StmtHandle` helpers used by `pipeline_ledger.cpp`; `random_id()` (replicate the local `pipeline_ledger.cpp` helper or its shared successor).
- Produces: `enqueue`, `find_active_run`, `get`.

- [ ] **Step 1: Write the failing tests**

```cpp
static void test_enqueue_creates_queued_run() {
    auto conn = make_migrated_connection();
    gov::PipelineRunStore store(*conn);
    gov::NewRun spec{ .kind = gov::PipelineKind::Replay, .aggregate_id = "agg-1",
        .profile_name = "default", .input_hash = "h1", .idempotency_key = "k1",
        .pipeline_name = "replay", .pipeline_version = "1" };
    gov::PipelineRun run = store.enqueue(spec);
    assert(!run.id.empty());
    assert(run.status == gov::PipelineRunStatus::Queued);
    assert(run.kind == gov::PipelineKind::Replay);
    assert(run.aggregate_id == "agg-1");
    assert(run.retry_count == 0);
    // round-trips through get()
    auto got = store.get(run.id);
    assert(got.has_value() && got->id == run.id && got->status == gov::PipelineRunStatus::Queued);
    assert(got->item_run_ids == "[]" && got->watermark == "{}");  // DEFAULTs
}

static void test_enqueue_dedups_active_run_invariant1() {
    auto conn = make_migrated_connection();
    gov::PipelineRunStore store(*conn);
    gov::NewRun spec{ .kind = gov::PipelineKind::Replay, .aggregate_id = "agg-1",
        .profile_name = "default", .input_hash = "h1", .idempotency_key = "k1",
        .pipeline_name = "replay", .pipeline_version = "1" };
    gov::PipelineRun first = store.enqueue(spec);
    gov::PipelineRun again = store.enqueue(spec);   // same (kind, aggregate_id, input_hash)
    assert(again.id == first.id);                    // dedup → SAME run, not a 2nd row
    // a DIFFERENT input_hash is a different run
    spec.input_hash = "h2";
    gov::PipelineRun other = store.enqueue(spec);
    assert(other.id != first.id);
}

static void test_find_active_run() {
    auto conn = make_migrated_connection();
    gov::PipelineRunStore store(*conn);
    assert(!store.find_active_run(gov::PipelineKind::Replay, "agg-1", "h1").has_value());
    gov::PipelineRun run = store.enqueue({ .kind = gov::PipelineKind::Replay,
        .aggregate_id = "agg-1", .profile_name = "default", .input_hash = "h1",
        .idempotency_key = "k1", .pipeline_name = "replay", .pipeline_version = "1" });
    auto found = store.find_active_run(gov::PipelineKind::Replay, "agg-1", "h1");
    assert(found.has_value() && found->id == run.id);
}
```

- [ ] **Step 2: Run to verify it fails** — store class missing → compile/link fail.

- [ ] **Step 3: Write the store header + `enqueue`/`find_active_run`/`get`**

Header `pipeline_run_store.hpp`:

```cpp
#pragma once
#include "starling/governance/pipeline_run.hpp"
#include "starling/persistence/connection.hpp"
#include <optional>
#include <span>
#include <string>
#include <string_view>

namespace starling::governance {

// Sole sanctioned write path into governance_pipeline_run. The active-run dedup
// (invariant 1) lives HERE (INSERT-then-detect), not in callers.
class PipelineRunStore {
public:
    explicit PipelineRunStore(persistence::Connection& conn) : conn_(conn) {}

    // Create a QUEUED run. If an ACTIVE run (QUEUED|RUNNING) already exists for
    // (kind, aggregate_id, input_hash), returns it WITHOUT inserting (invariant 1).
    PipelineRun enqueue(const NewRun& spec);

    [[nodiscard]] std::optional<PipelineRun> find_active_run(
        PipelineKind kind, std::string_view aggregate_id, std::string_view input_hash);
    [[nodiscard]] std::optional<PipelineRun> get(std::string_view run_id);

    PipelineRun claim(std::string_view run_id, std::string_view worker_id,
                      std::string_view lease_until);                       // Task 3a.4
    PipelineRun reclaim(std::string_view run_id, std::string_view worker_id,
                        std::string_view lease_until);                     // Task 3a.5
    PipelineRun confirm(std::string_view run_id, std::string_view checkpoint_json,
                        PipelineRunStatus terminal);                       // Task 3a.5
    void dead_letter(std::string_view run_id, std::string_view error_kind); // Task 3a.6
    void record_stage_timing(std::string_view run_id,
                             std::string_view stage, long long ms);        // Task 3a.6

    // Invariant 7 (05_governance.md:191) pure roll-up (D3): ≥1 success & ≥1 fail →
    // PartialSuccess; all NOOP → (NOOP/Completed per D3 ruling); else terminal rule.
    [[nodiscard]] static PipelineRunStatus roll_up_status(
        std::span<const PipelineRunStatus> item_statuses);                 // Task 3a.6

private:
    [[nodiscard]] PipelineRun read_row_(std::string_view run_id);  // SELECT→struct; throws if absent
    persistence::Connection& conn_;
};

}  // namespace starling::governance
```

`enqueue` logic (`.cpp`):
1. `auto active = find_active_run(spec.kind, spec.aggregate_id, spec.input_hash); if (active) return *active;` (fast path).
2. Else `INSERT OR IGNORE INTO governance_pipeline_run(... 26 cols ...) VALUES(...)` with `id = random_id()`, `status='QUEUED'`, `started_at = updated_at = iso8601_utc(now)`, JSON fields from defaults/`spec.step_contracts`, optionals bound NULL when `nullopt`.
3. If `sqlite3_changes(db) == 0` (lost a race to the partial-unique index) → re-`find_active_run` and return the winner (INSERT-then-detect; never surface the UNIQUE violation). Else `return read_row_(id)`.

`find_active_run`: `SELECT <cols> FROM governance_pipeline_run WHERE kind=? AND aggregate_id=? AND input_hash=? AND status IN ('QUEUED','RUNNING') LIMIT 1` → map to `PipelineRun` or `nullopt`.

`get` / `read_row_`: `SELECT <cols> FROM governance_pipeline_run WHERE id=?`. Factor the row→struct mapping into one private `map_row_(sqlite3_stmt*)` reused by every read. Bind enums via `kind_from_string`/`status_from_string` on the text columns; NULL text → `nullopt`.

- [ ] **Step 4: Run to verify it passes** — `ctest -R pipeline_run` green.

- [ ] **Step 5: Commit** — explicit-path add header + cpp + CMake + test.

---

## Task 3a.4: `claim` + lease semantics

**Files:** Modify `pipeline_run_store.cpp`; extend `test_pipeline_run_store.cpp`.

- [ ] **Step 1: Failing tests**

```cpp
static void test_claim_transitions_queued_to_running() {
    auto conn = make_migrated_connection(); gov::PipelineRunStore store(*conn);
    auto run = store.enqueue({ .kind = gov::PipelineKind::Replay, .aggregate_id="a",
        .profile_name="default", .input_hash="h", .idempotency_key="k",
        .pipeline_name="replay", .pipeline_version="1" });
    auto claimed = store.claim(run.id, "worker-A", "2026-06-29T12:00:00Z");
    assert(claimed.status == gov::PipelineRunStatus::Running);
    assert(claimed.worker_id.has_value() && *claimed.worker_id == "worker-A");
    assert(claimed.lease_until.has_value() && *claimed.lease_until == "2026-06-29T12:00:00Z");
    // still the active run after claim (RUNNING is active)
    assert(store.find_active_run(gov::PipelineKind::Replay, "a", "h").has_value());
}

static void test_claim_only_from_queued() {
    auto conn = make_migrated_connection(); gov::PipelineRunStore store(*conn);
    auto run = store.enqueue({ .kind = gov::PipelineKind::Replay, .aggregate_id="a",
        .profile_name="default", .input_hash="h", .idempotency_key="k",
        .pipeline_name="replay", .pipeline_version="1" });
    store.claim(run.id, "worker-A", "2026-06-29T12:00:00Z");
    // a second claim on an already-RUNNING run is rejected (guard the WHERE on status)
    bool threw = false;
    try { store.claim(run.id, "worker-B", "2026-06-29T13:00:00Z"); }
    catch (const std::exception&) { threw = true; }
    assert(threw);   // OR: returns unchanged run — eng-review locks the contract (see note)
}
```

- [ ] **Step 2: Verify fails.**
- [ ] **Step 3: Implement `claim`** — `UPDATE governance_pipeline_run SET status='RUNNING', worker_id=?, lease_until=?, updated_at=? WHERE id=? AND status='QUEUED'`. If `sqlite3_changes(db)==0` → the run was not QUEUED (already claimed / terminal / absent) → throw a typed error (e.g. `make_sqlite_error`-style or a `std::runtime_error("claim: run not QUEUED")`). **NOTE for eng-review:** lock the not-QUEUED contract — throw vs return-unchanged. Proposal: throw (a claim race is a real concurrency signal, not a silent no-op). Then `return read_row_(run_id)`.
- [ ] **Step 4: Verify passes.**
- [ ] **Step 5: Commit.**

---

## Task 3a.5: `confirm` + `reclaim`

**Files:** Modify `pipeline_run_store.cpp`; extend the test.

- [ ] **Step 1: Failing tests**

```cpp
static void test_confirm_sets_terminal_and_checkpoint() {
    auto conn = make_migrated_connection(); gov::PipelineRunStore store(*conn);
    auto run = store.enqueue({ .kind=gov::PipelineKind::Replay, .aggregate_id="a",
        .profile_name="default", .input_hash="h", .idempotency_key="k",
        .pipeline_name="replay", .pipeline_version="1" });
    store.claim(run.id, "w", "2026-06-29T12:00:00Z");
    auto done = store.confirm(run.id, R"({"last_sqlite_id": 42})", gov::PipelineRunStatus::Completed);
    assert(done.status == gov::PipelineRunStatus::Completed);
    assert(done.watermark == R"({"last_sqlite_id": 42})");
    // terminal run is no longer active → a fresh enqueue makes a NEW run
    assert(!store.find_active_run(gov::PipelineKind::Replay, "a", "h").has_value());
}

static void test_reclaim_only_when_lease_expired() {
    auto conn = make_migrated_connection(); gov::PipelineRunStore store(*conn);
    auto run = store.enqueue({ .kind=gov::PipelineKind::Replay, .aggregate_id="a",
        .profile_name="default", .input_hash="h", .idempotency_key="k",
        .pipeline_name="replay", .pipeline_version="1" });
    store.claim(run.id, "worker-A", "2000-01-01T00:00:00Z");  // already-expired lease
    auto reclaimed = store.reclaim(run.id, "worker-B", "2030-01-01T00:00:00Z");
    assert(reclaimed.status == gov::PipelineRunStatus::Running);
    assert(*reclaimed.worker_id == "worker-B");
    assert(reclaimed.retry_count == 1);   // reclaim increments retry_count
}
```

- [ ] **Step 2: Verify fails.**
- [ ] **Step 3: Implement.**
  - `confirm`: the `terminal` arg must be one of `Completed|PartialSuccess|DegradedCompleted` — guard (throw on a non-terminal/illegal arg; reuse `is_active` to reject active states; reject Failed/Cancelled/DeadLettered here — those have their own paths). `UPDATE ... SET status=?, watermark=?, checkpoint_sequence=<derived-or-kept>, updated_at=? WHERE id=? AND status='RUNNING'`. D5: `checkpoint_json` is stored into `watermark` (caller-supplied JSON) — confirm the checkpoint↔watermark field mapping with eng-review (the spec's `confirm(checkpoint)` writes "checkpoint_sequence / watermark"). `changes==0` → throw (not RUNNING).
  - `reclaim`: `UPDATE ... SET worker_id=?, lease_until=?, retry_count=retry_count+1, status='RUNNING', updated_at=? WHERE id=? AND status='RUNNING' AND lease_until < ?` (bind `now` as the expiry comparison; ISO-8601 UTC strings compare lexicographically == chronologically). `changes==0` → lease still valid or not RUNNING → throw.
- [ ] **Step 4: Verify passes.**
- [ ] **Step 5: Commit.**

---

## Task 3a.6: `dead_letter` + `record_stage_timing` + `roll_up_status`

**Files:** Modify `pipeline_run_store.cpp`; extend the test.

- [ ] **Step 1: Failing tests**

```cpp
static void test_dead_letter() {
    auto conn = make_migrated_connection(); gov::PipelineRunStore store(*conn);
    auto run = store.enqueue({ .kind=gov::PipelineKind::Replay, .aggregate_id="a",
        .profile_name="default", .input_hash="h", .idempotency_key="k",
        .pipeline_name="replay", .pipeline_version="1" });
    store.claim(run.id, "w", "2030-01-01T00:00:00Z");
    store.dead_letter(run.id, "max_retries_exceeded");
    auto got = store.get(run.id).value();
    assert(got.status == gov::PipelineRunStatus::DeadLettered);
    assert(got.error_kind.has_value() && *got.error_kind == "max_retries_exceeded");
    assert(!store.find_active_run(gov::PipelineKind::Replay, "a", "h").has_value());
}

static void test_record_stage_timing_appends() {
    auto conn = make_migrated_connection(); gov::PipelineRunStore store(*conn);
    auto run = store.enqueue({ .kind=gov::PipelineKind::Replay, .aggregate_id="a",
        .profile_name="default", .input_hash="h", .idempotency_key="k",
        .pipeline_name="replay", .pipeline_version="1" });
    store.record_stage_timing(run.id, "embed", 12);
    store.record_stage_timing(run.id, "replay", 30);
    auto got = store.get(run.id).value();
    // stage_timings_ms is a JSON array of {stage, ms} in insertion order.
    assert(got.stage_timings_ms.find("\"embed\"") != std::string::npos);
    assert(got.stage_timings_ms.find("\"replay\"") != std::string::npos);
    assert(got.stage_timings_ms.find("12") != std::string::npos);
    assert(got.stage_timings_ms.find("30") != std::string::npos);
    // order: embed before replay
    assert(got.stage_timings_ms.find("embed") < got.stage_timings_ms.find("replay"));
}

static void test_roll_up_status_invariant7() {
    using S = gov::PipelineRunStatus;
    // ≥1 success & ≥1 failure → PARTIAL_SUCCESS
    std::array<S,2> mixed{ S::Completed, S::Failed };
    assert(gov::PipelineRunStore::roll_up_status(mixed) == S::PartialSuccess);
    // all-success → COMPLETED
    std::array<S,2> allok{ S::Completed, S::Completed };
    assert(gov::PipelineRunStore::roll_up_status(allok) == S::Completed);
    // NOTE: all-NOOP handling — see D3. The spec (invariant 7) says all-NOOP must
    // NOT report SUCCESS. Our 9-state enum has no NOOP member; eng-review locks
    // whether all-NOOP maps to Completed-with-noop-counters or a distinct state.
}
```

- [ ] **Step 2: Verify fails.**
- [ ] **Step 3: Implement.**
  - `dead_letter`: `UPDATE ... SET status='DEAD_LETTERED', error_kind=?, retry_count=retry_count+1, updated_at=? WHERE id=?`. **D2:** no `RuntimeSupervisor` coupling here — the compliance-lane health hold is a consumer concern (flagged). `changes==0` → run absent → throw.
  - `record_stage_timing`: append `{stage, ms}` to the `stage_timings_ms` JSON array atomically with SQLite JSON1: `UPDATE governance_pipeline_run SET stage_timings_ms = json_insert(stage_timings_ms, '$[#]', json_object('stage', ?, 'ms', ?)), updated_at=? WHERE id=?`. (`'$[#]'` appends to a JSON array.) Verify SQLite is built with JSON1 (default in the bundled/amalgamation build — confirm at build; if absent, fall back to read-modify-write of the JSON string under the connection's txn). `changes==0` → throw.
  - `roll_up_status` (D3): pure function over the span — count terminal successes (`Completed`,`DegradedCompleted`) vs failures (`Failed`,`DeadLettered`,`Cancelled`); `≥1 && ≥1` → `PartialSuccess`; all-success → `Completed`; all-fail → `Failed`. all-NOOP per D3.
- [ ] **Step 4: Verify passes** — full `ctest -R pipeline_run` green; run the **whole** ctest suite once (`configure_build.py --build --test`) to confirm no regression in the migrated-DB fixtures other suites share.
- [ ] **Step 5: Commit.**

---

## Task 3a.7: (D1-GATED) pybind surface for PipelineRunStore

**Skip unless eng-review (D1) keeps the binding in 3a.** If kept:

**Files:** Modify `bindings/python/bind_14_governance.cpp`; add `tests/python/test_pipeline_run_binding.py`.

- [ ] Bind `PipelineKind` + `PipelineRunStatus` enums (`.value(...)` per member, names matching `*_to_string`), `PipelineRun` (def_readonly, output struct), `NewRun` (def(init) + def_readwrite, input), and `PipelineRunStore` (ctor from the bound adapter's `Connection` — verify how Python reaches a `Connection&`: `RuntimeSupervisor` took `SqliteAdapter&`; check whether the adapter exposes a `Connection&` for the store ctor, or bind a thin factory). Mirror Task 2.3's bind ordering (value types before the class) + default copy return policy for `get`/`find_active_run` (no `reference_internal`).
- [ ] pytest smoke: enqueue→claim→confirm round-trip through `_core`, asserting status strings. Rebuild `--python-editable`.
- [ ] Commit.

---

## Self-Review (run before dispatching execution)

1. **Spec coverage:** enqueue(invariant 1)/claim/confirm/reclaim/find_active_run/dead_letter/record_stage_timing + roll_up(invariant 7 helper) ↔ governance-core.md:454 + 05_governance.md:144-154 — covered (with D2/D3/D4 scope flagged). Migration + table ↔ governance-core.md:93,99,452 — covered. StageTimer + tick wiring = **3b (out of 3a scope by design)**.
2. **Placeholder scan:** SQL + signatures + representative TDD tests are concrete. The `.cpp` method bodies are specified by SQL + logic + tests (TDD-complete for a subagent); exact row→struct mapping is "one `map_row_` helper reused" — concrete enough. No "TBD/handle errors appropriately".
3. **Type consistency:** `PipelineRun`/`NewRun`/enum names + `*_to_string`/`from_string`/`is_active` used identically across 3a.1→3a.7. Store method signatures in the header match their call sites in the tests. Status string literals in the migration (`'QUEUED'`,`'RUNNING'`) == `status_to_string` outputs (frozen-contract constraint).
4. **Open decisions** D1-D7 are surfaced for eng-review, with baseline proposals folded into task text — implementers apply the locked amendments over this text (the 2b convention).

## Execution Handoff

After `/plan-eng-review` locks D1-D7: **subagent-driven** (fresh implementer per task → review-package → task reviewer spec+quality → fix loop → whole-branch opus review → PR → CI green → user merges). Branch off `main@c7ce3f7`. Durable ledger: `.superpowers/sdd/progress.md`.

---

## Eng-review required outputs (2026-06-29)

### NOT in scope (deferred — rationale)
- **pybind binding for `PipelineRunStore`** (D1) — no c1 Python consumer; add with a future dashboard "pipeline runs" view.
- **StageTimer RAII + tick/replay wiring + run-creation seam** — Phase 3b cascade (after 3a schema lands).
- **invariant-4 RuntimeHealth coupling** (D2) — deferred to the compliance-run consumer; 3a is fail-closed (CX-10 rejects `ComplianceErase` at enqueue).
- **invariant-2 step-contract `failure_policy` validation** (D4) — `step_contracts` opaque until the c2 step-graph (invariant 8).
- **`business_task_id` multi-item aggregation + all-NOOP→NOOP** (D3/CX-14) — no c1 producer; NOOP unrepresentable in the 9-state enum; c2.
- **FAILED + PAUSED transitions** (CX-5/6/7) — no c1 producer; FAILED retry-semantics murky; PAUSED = DRAINING-coordination.
- **multi-lane lease contention** — spec defers to P3+; c1 tick is single-threaded (lease/reclaim built + tested, trivially exercised).
- **typed C++ structs for the JSON sub-fields** (D5) — opaque until a field-wise consumer.
- **`starling/util/uuid.hpp` consolidation** of the now-4 `random_id` copies (CQ1) — tracked to the existing M0.4+1 item.
- **trace-retention tiers beyond `metadata_only`** — spec defers to c1.5/P3+.

### What already exists (reused vs rebuilt)
- **`bus::PipelineLedger`** (`src/bus/pipeline_ledger.cpp`) — the M0.4 extraction-cost ledger. **Reused as the SQLite-writer PATTERN** (helpers, INSERT-then-detect dedup, `random_id`); **NOT extended** (spec mandates a distinct governance table).
- **`store::PerceptionStateStore`** — **reused as the struct-row + `Connection&`-store + SELECT→struct SHAPE.**
- **`persistence::MigrationRunner` + `migrations/*.sql` glob + `schema_migrations` checksum tracking** — reused as-is (`0029` drops into the existing pipeline; no runner change).
- **`governance::RuntimeSupervisor`** (Phase 1/2) — sibling governance component; `PipelineRunStore` is the long-task half. NOT coupled in 3a (D2).

### Failure modes (per new codepath)
| Codepath | Realistic prod failure | Test | Error handling | Silent? |
|---|---|---|---|---|
| enqueue dedup | 2 concurrent enqueues, same active key | T1 invariant-1 DB backstop | partial-unique index + re-find (CX-3) | no (correct dedup) |
| claim/reclaim lease | stale / malformed `lease_until` | CX-8 canonical-form test | canonical contract + lexicographic compare; throw | no (throw) |
| dead_letter | terminal→/double dead-letter | CX-4 guard test | status-guarded UPDATE → throw | no (fail-loud) |
| record_stage_timing | SQLite built without JSON1 | CX-11 probe test | probe asserts JSON1 | no (fail-fast at test) |
| migration | another branch lands `0029` | — (process) | CX-13 recheck before merge | no (MigrationDriftError at startup) |
| compliance run | `ComplianceErase` enqueued unprotected | CX-10 reject test | enqueue throws (fail-closed) | no (throw) |

**No critical gap** — every failure mode has a test + error handling + is loud (not silent).

### Worktree parallelization
**Sequential implementation, no parallelization opportunity.** All tasks touch the same primary module (`pipeline_run_store.{hpp,cpp}` + the one migration + one test file): 3a.1 types → 3a.2 migration → 3a.3-3a.6 store methods (same `.cpp`). Task 3a.7 dropped (D1).

### Implementation Tasks
Synthesized from this review's findings. P1 blocks ship; P2 same branch; P3 follow-up.
- [ ] **T1 (P1, human ~20min / CC ~6min)** — migration — frozen-schema correctness: `tenant_id` + `kind`/`status` CHECK + active index `(kind,tenant_id,aggregate_id,input_hash)`. Surfaced by: CX-1/CX-2. Files: `migrations/0029_governance_pipeline_run.sql`. Verify: ctest migration test (CX-12: index SQL + CHECK + dup-reject).
- [ ] **T2 (P1, human ~25min / CC ~7min)** — store — `enqueue` plain-INSERT + dedup re-find + reject `ComplianceErase`. Surfaced by: CX-3/CX-10. Files: `src/governance/pipeline_run_store.cpp`. Verify: enqueue dedup + ComplianceErase-reject tests.
- [ ] **T3 (P1, human ~15min / CC ~4min)** — store — `dead_letter` status guard + `retry_count`=reclaim-count semantics. Surfaced by: CX-4/CX-9. Files: same `.cpp`. Verify: dead_letter guard + retry_count tests.
- [ ] **T4 (P2, human ~20min / CC ~6min)** — store — add `record_checkpoint` + `cancel`; document FAILED/PAUSED deferred. Surfaced by: CX-5/6/7. Files: `pipeline_run_store.{hpp,cpp}`. Verify: checkpoint + cancel tests.
- [ ] **T5 (P2, human ~30min / CC ~8min)** — tests — all 6 negative/edge + JSON1 probe + JSON-parse assertions. Surfaced by: T1/CX-11/CX-12. Files: `tests/cpp/test_pipeline_run_store.cpp`. Verify: full ctest green.
- [ ] **T6 (P3, human ~3min / CC ~1min)** — process — recheck `ls migrations/ | sort | tail -1` before implementation + before merge; rename `0029` on collision. Surfaced by: CX-13.

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | not required (no product-scope change) |
| Codex Review | `/codex review` | Independent 2nd opinion | 1 | issues_found | 14 findings, all folded |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | clean | 21 findings, 0 critical gaps, all folded |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | not applicable (core-only, no UI) |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | not run |

- **CODEX:** 14 outside-voice findings, ALL folded — tenant_id in the active-dedup key (cross-tenant suppression); kind/status CHECK constraints (frozen migration); plain-INSERT not OR-IGNORE (CHECK-masking); status-guarded `dead_letter`; `record_checkpoint`+`cancel` (reachable state machine + real reclaim-resume); `retry_count`=reclaim-count; JSON1 probe; hardened migration/JSON-parse tests; migration-number recheck; honest `partial_terminal_rollup` naming.
- **CROSS-MODEL:** CX-10 vs locked D2 — **reconciled**, not overridden: keep D2's deferred health-coupling AND make `enqueue` fail-closed reject `ComplianceErase`. Otherwise the two reviewers aligned (no standoff).
- **VERDICT:** **ENG CLEARED — ready to implement.** Subagent-driven, branch off `main@c7ce3f7`. Design + CEO reviews not required (core-only C++; no UI; no product-scope change). 11 decisions locked (D1/D2/D3/D5/D6 + CQ1 + T1 + CX-1/CX-10/CX-5-6-7 + CXbatch); the frozen migration SQL (tenant_id + CHECK + active index) is corrected in-place in Task 3a.2.

NO UNRESOLVED DECISIONS

# P3.c1 Phase 3b — StageTimer + tick/replay stage_timing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the `StageTimer` RAII wall-clock instrument and wire per-stage timing into the offline `memoryops::tick_all` half-cycle, producing observable `{stage, ms}` records for each of the 8 tick stages (L3: replay split into 3 sub-stages) — the instrumentation half of Phase 3 (the `governance_pipeline_run` ledger substrate landed in 3a, merged main@5e71dbe).

**Architecture:** A header-only `starling::governance::StageTimer` measures one stage's elapsed milliseconds (mirroring the `steady_clock` idiom in `extractor/openai_adapter.cpp`) and, on scope exit, reports `{stage, ms}` to a **sink** (`std::function`). The sink is the seam that resolves open-Q #2: in 3b the tick's sink accumulates into `TickOutcome.stage_timings_ms` (no PipelineRun created in the inline tick — see OQ-2 below), while a unit test proves the *same* StageTimer drives `PipelineRunStore::record_stage_timing` into a real claimed run, so the persistence path is wired and ready for a future run owner (Phase 4). Pure C++ core; no new Python governance surface (PipelineRunStore stays unbound, per 3a's D1).

**Tech Stack:** C++20 core (`include/starling/governance/`, `src/memory/`), GoogleTest (`tests/cpp/`), pybind11 read-only dict surface (`bindings/python/bind_13_memory_ops.cpp`), SQLite JSON1 (already used by `record_stage_timing`).

## Global Constraints

- **Architecture boundary (CLAUDE.md hard rule):** core semantics in C++; Python only adapter/config/read-only. StageTimer + tick instrumentation are core → C++. The only Python touch (Task 3b.4) is a **read-only** dict field on the already-bound `memory_tick_all` surface (allowed: 只读检视查询).
- **Write discipline:** `record_stage_timing` is a statement-only autocommit `UPDATE` (no BEGIN; the store mirrors `bus::PipelineLedger`). `tick_all` is the **offline** path (the background daemon, not inside `Bus::write`), so governance writes from it do not nest BEGIN (`[[replay-write-reentrancy-offline-only]]` does not apply — that rule is about online/subscriber paths).
- **CI clang-tidy (changed-LINES) gate** (`scripts/ci_clang_tidy_diff.py`) lints **only `.cpp` TUs under `src/|bindings/`** — `tests/cpp/*.cpp` is NOT linted. But **headers ARE gated** via `HeaderFilterRegex` once a linted `src/` TU includes them: `memory_ops.cpp` will include `stage_timer.hpp`, so **`stage_timer.hpp` must be clang-tidy-clean by construction**. Known gotchas that apply here: identifiers ≥3 chars (NO `ms` as a C++ identifier — use `duration_ms`/`elapsed_ms`; the JSON key `'ms'` is a string literal, fine); `bugprone-empty-catch` (the dtor's swallow needs a justified `// NOLINT(bugprone-empty-catch)`); designated initializers for multi-field aggregates; braces around all statements; the gate DISABLES `bugprone-easily-swappable-parameters`. clang-tidy is **un-runnable locally** (macOS 26 SDK) — write clean, CI is the gate.
- **Canonical build:** `python scripts/configure_build.py --build --test` (C++ + ctest). Task 3b.4 changes a binding → must also re-run `--python-editable` to reinstall `_core` (a bare `pip install -e .` is insufficient).
- **Commit gate:** full ctest + `pytest tests/python` green.
- **git:** explicit-path `git add` only (no `git add .` / `-A`); no `--no-verify` / `--amend`. Commit footer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

## RESOLVED DECISION — OQ-2: the tick run-creation seam (LOCKED = A, /plan-eng-review 2026-06-30)

**The problem.** `PipelineRunStore::record_stage_timing(run_id, stage, ms)` is **run-exists-guarded** — it `UPDATE ... WHERE id=run_id` and throws `"run not found"` when `sqlite3_changes()==0` (`src/governance/pipeline_run_store.cpp:508-510`). So a stage timing can only be persisted against a PipelineRun row that already exists. But the inline `memoryops::tick_all` (`src/memory/memory_ops.cpp:191-230`) creates **no** PipelineRun, and **none of the 7 `PipelineKind` values** (`extraction, replay, projection_rebuild, container_rebuild, compliance_erase, retrieval_eval, migration`) honestly names "the whole inline offline half-cycle." The 6 tick stages are `embed → policy → common_ground → replay → projection → outbox`.

**Options.**

| # | Approach | Cost |
|---|---|---|
| **A (RECOMMENDED)** | StageTimer measures all 6 stages; the tick's sink accumulates into a new `TickOutcome.stage_timings_ms` field (surfaced read-only to Python). **No PipelineRun created in the tick.** A unit test proves the StageTimer sink CAN persist into a real claimed run via `record_stage_timing` — so the seam is wired and ready, but the run owner lands in Phase 4. | "recorded for a tick cycle" means recorded in `TickOutcome` + observable, not persisted to `governance_pipeline_run`. The 3a ledger has no live writer until Phase 4 (already true after 3a). |
| **B** | `tick_all` `enqueue(kind=Replay)` → `claim` → 6 StageTimers persist into it → `confirm(COMPLETED)` each cycle. | `kind=Replay` is a semantic lie for embed/policy/projection/outbox; one ledger row **per tick interval** (volume); `aggregate_id`/`input_hash` are synthetic (no natural identity for "the maintenance cycle at time T"). Front-runs Phase 4's run/lane lifecycle. |
| **C** | Only the `replay` stage is wrapped in a real `kind=Replay` run (honest kind); its sub-steps persist timings; the other 5 stages measure-into-`TickOutcome`. | `run_idle` produces its `replay_batch_id` *inside* the call, so an enqueue-before-run identity is awkward; only 1 of 6 stages persists; mixed model. Still front-runs Phase 4. |

**Recommendation: Option A.** Rationale: (1) no `PipelineKind` honestly covers the inline half-cycle, and per-tick ledger rows are premature before **Phase 4 (ScopedWorkGate)** gives background work a real claim/confirm run/lane lifecycle — the spec itself defers true concurrency + background-thread replay to P3+ (`replay_scheduler.cpp:397` "M0.9+", governance-core.md:80). (2) `record_stage_timing` was built + unit-tested in 3a; 3b's job is the *instrument* (StageTimer) + making the 6 durations observable (the `metadata_only` trace tier the spec ships in c1 — "step name, duration, status… which `stage_timings_ms` already provides", governance-core.md:79). (3) The sink abstraction makes StageTimer agnostic to this decision: **if eng-review picks B or C, only Task 3b.3's sink wiring changes — StageTimer (3b.1) and the persistence-proof test (3b.2) are unchanged.**

**OQ-2 is LOCKED = A.** The A/B/C analysis above is retained as the rationale record.

### LOCKED eng-review decisions (2026-06-30) — implementers apply these OVER the task text below

/plan-eng-review (FULL_REVIEW + codex outside-voice; 10 codex findings triaged, 6 folded). Where a LOCKED decision conflicts with task code below, the LOCKED decision wins. The canonical task code below has ALSO been updated to match (no stale 6-stage code remains).

- **L1 — OQ-2 = A (measure-only in tick).** No PipelineRun created in `tick_all`; StageTimer accumulates into `TickOutcome.stage_timings_ms`. Run-creation deferred to Phase 4 (ScopedWorkGate). Reinforced by `[[soft-reject-broken-by-replay]]` (`tick_all` runs every background tick → B/C would write a ledger row per tick) + `[[governance-ledger-active-dedup-needs-tenant]]` (a synthetic tick run would need a `tenant_id` in its dedup key).
- **L2 — 3b.4 INCLUDED** (read-only Python surface) — with the L5 integration fix.
- **L3 — Replay timed as 3 sub-stages, not one (codex #7).** `tick_all` emits **8** stage timings in order: `embed, policy, common_ground, replay_oscillation_guard, replay_ttl_sweep, replay_idle, projection, outbox`. The 3 replay sub-calls are already separate statements in `tick_all`; wrap each in its own `StageTimer` (NO `replay_scheduler.cpp` edit). Keep all 8 names in lockstep across production (3b.3) + the ctest (3b.3) + the pytest (3b.4). **Supersedes every "6 stages" reference in this plan.**
- **L4 — Header: keep one (codex #8 rejected).** `StageTiming` + `StageTimer` stay together in `governance/stage_timer.hpp`; `memory_ops.hpp` includes it. Marginal `<functional>`/`<chrono>` cost is ~zero (`memory_ops.hpp` already pulls `embedding_worker.hpp`/`policy_engine.hpp`/`semantic_retriever.hpp`).
- **L5 — Python integration fix for 3b.4 (codex #1 + #2, BOTH verified against code).** Adding `stage_timings_ms` to the tick dict is NOT a one-line binding change — it has two downstream breaks:
  - **(a) `TickStats` dataclass** (`python/starling/memory.py:105`) MUST gain `stage_timings_ms: list = field(default_factory=list)`, or `Memory.tick()`'s `return TickStats(**self._core.tick(now))` (memory.py:190) throws `TypeError: unexpected keyword argument 'stage_timings_ms'`.
  - **(b) background-tick broadcast** (`python/starling/dashboard/engine.py:412`, `if on_tick is not None and any(stats.values())`) MUST exclude the always-non-empty `stage_timings_ms` from the work-check, or **every idle tick fires a WS heartbeat**. Use `any(v for k, v in stats.items() if k != "stage_timings_ms")`.
  - **(c) the 3b.4 pytest** drives `Memory.tick()`, which returns a `TickStats` **dataclass** (not a dict) → assert via **attribute access** `out.stage_timings_ms` (a list of `{stage, ms}` dicts), NOT `out["stage_timings_ms"]`.
- **L6 — Doc honesty (codex #10 + #4 + #3).** The 3b.2 test proves the StageTimer→`record_stage_timing` **wiring** (a dtor can drive a persist against a claimed run), NOT full Phase-4 lifecycle — describe it as "wiring proof," not "Phase-4-ready." The `tick_all` sink comment must NOT claim "never throws" (`std::string(stage)` can throw `bad_alloc`; the dtor swallows it — best-effort). The dtor's silent-drop of a *store-sink* failure is a **Phase-4 forward-flag**: when Phase 4 wires a store-sink, decide guard-run-validity vs best-effort-drop + a dropped-timing counter.
- **Documented rejections:** microseconds (codex #6 — 3a's frozen `record_stage_timing(.., long long duration_ms)` + JSON `'ms'` key fix the unit; the heavy stages are ≫1ms; 0ms for a genuinely idle stage is honest information); per-stage status field (codex #5 — the c1 tick is all-or-nothing, a partial-success-per-stage model is out of c1 scope).

---

## What 3b delivers (spec linkage)

- Spec: governance-core.md (`docs/superpowers/plans/2026-06-28-p3-c1-governance-core.md`) Phase 3 §447-457 — "`stage_timer.hpp`; wire `StageTimer` into `src/memory/memory_ops.cpp` tick stages + `src/replay/replay_scheduler.cpp`"; design spec `docs/design/subsystems_design/05_governance.md:49,87` (`stage_timings_ms` 逐阶段记录), trace tier `:114-119`.
- 3a (merged, main@5e71dbe) already provides: `governance_pipeline_run` table (migration 0029), `PipelineRunStore` with `enqueue/claim/confirm/record_stage_timing/...`, `PipelineRun`/`NewRun`/enums. 3b **consumes** `record_stage_timing` only (the rest is exercised by the persistence-proof test's `enqueue`+`claim`).
- **replay_scheduler.cpp:** under Option A the `replay` stage is timed as one unit **from `tick_all`** (the scheduler is invoked there) — `ReplayScheduler` stays untouched (it is a pure `statements` worker that creates no run, confirmed). Pushing finer timers *inside* `run_idle` is deferred (finer than the c1 `metadata_only` grain needs).

---

## File structure

- **Create** `include/starling/governance/stage_timer.hpp` — header-only: `struct StageTiming{stage, duration_ms}` + `class StageTimer` (RAII, `steady_clock`, sink-on-scope-exit). Header-only → **no CMakeLists change for the header**.
- **Create** `tests/cpp/test_stage_timer.cpp` — pure-mechanism unit tests (no DB). Registered in `tests/cpp/CMakeLists.txt`.
- **Modify** `tests/cpp/test_pipeline_run_store.cpp` — add ONE case proving the StageTimer sink persists via `record_stage_timing` (reuses the file's existing `fresh_db`/`enqueue_and_claim`/`eval_json_*` helpers).
- **Modify** `include/starling/memory/memory_ops.hpp` — add `std::vector<governance::StageTiming> stage_timings_ms;` to `TickOutcome`; `#include "starling/governance/stage_timer.hpp"`.
- **Modify** `src/memory/memory_ops.cpp` — wrap the 8 stages of `tick_all` (replay split into 3, L3) in `StageTimer` scopes feeding a local accumulator sink; move into `t.stage_timings_ms`.
- **Modify** `tests/cpp/test_memory_ops.cpp` — add a `TickAllRecordsStageTimings` case mirroring `TickAllAdvancesEmbeddingAndReturnsShape`.
- **Modify** `bindings/python/bind_13_memory_ops.cpp` — (Task 3b.4) add a read-only `stage_timings_ms` list to the `memory_tick_all` dict.
- **Modify** `python/starling/memory.py` — (Task 3b.4, L5a) add `stage_timings_ms` to the `TickStats` dataclass so `Memory.tick()` round-trips the new key.
- **Modify** `python/starling/dashboard/engine.py` — (Task 3b.4, L5b) exclude `stage_timings_ms` from the background-tick broadcast work-check.
- **Create** `tests/python/test_tick_stage_timings.py` — (Task 3b.4) assert a real tick returns the 8 ordered stages.

---

## Task 3b.1: `StageTimer` RAII + pure-mechanism unit tests

**Files:**
- Create: `include/starling/governance/stage_timer.hpp`
- Create: `tests/cpp/test_stage_timer.cpp`
- Modify: `tests/cpp/CMakeLists.txt` (add `test_stage_timer.cpp` to the `add_executable(starling_tests ...)` list, near `test_pipeline_run_store.cpp`)

**Interfaces:**
- Produces:
  - `struct starling::governance::StageTiming { std::string stage; long long duration_ms = 0; };`
  - `class starling::governance::StageTimer` with `using Sink = std::function<void(std::string_view, long long)>;`, ctor `StageTimer(std::string stage, Sink sink)`, RAII dtor that reports `{stage, elapsed_ms}` to `sink` (swallowing sink exceptions). Non-copyable, non-movable.

- [ ] **Step 1: Write the failing test** — `tests/cpp/test_stage_timer.cpp` (test TUs are NOT clang-tidy-linted, so short names/`ms` are fine here):

```cpp
#include "starling/governance/stage_timer.hpp"

#include <gtest/gtest.h>

#include <chrono>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

using starling::governance::StageTimer;
using starling::governance::StageTiming;

namespace {

TEST(StageTimer, ReportsStageAndNonNegativeMsExactlyOnceOnScopeExit) {
    std::vector<StageTiming> sink_calls;
    {
        StageTimer timer("embed", [&](std::string_view stage, long long ms) {
            sink_calls.push_back(StageTiming{std::string(stage), ms});
        });
        // work happens in this scope; dtor fires the sink at the closing brace
    }
    ASSERT_EQ(sink_calls.size(), 1U);
    EXPECT_EQ(sink_calls.front().stage, "embed");
    EXPECT_GE(sink_calls.front().duration_ms, 0);
}

TEST(StageTimer, MeasuresElapsedWallClock) {
    long long measured = -1;
    {
        StageTimer timer("slow", [&](std::string_view, long long ms) { measured = ms; });
        std::this_thread::sleep_for(std::chrono::milliseconds(12));
    }
    EXPECT_GE(measured, 1);  // generous lower bound on a 12ms sleep — non-flaky
}

TEST(StageTimer, DestructorSwallowsSinkException) {
    bool reached_next_line = false;
    {
        StageTimer timer("boom", [](std::string_view, long long) {
            throw std::runtime_error("sink failed");
        });
    }  // dtor invokes the throwing sink; must NOT propagate
    reached_next_line = true;
    EXPECT_TRUE(reached_next_line);
}

TEST(StageTimer, EmptySinkIsANoOp) {
    StageTimer::Sink none;  // empty std::function
    {
        StageTimer timer("noop", none);
    }
    SUCCEED();  // reaching here proves the dtor guarded the empty sink
}

}  // namespace
```

- [ ] **Step 2: Register the test target + run to verify it fails** — add to `tests/cpp/CMakeLists.txt` in the `add_executable(starling_tests ...)` source list:

```cmake
    test_stage_timer.cpp
```

Run: `python scripts/configure_build.py --build` then `ctest --test-dir build-macos -R StageTimer`
Expected: FAIL — `stage_timer.hpp` not found.

- [ ] **Step 3: Write the implementation** — `include/starling/governance/stage_timer.hpp` (this header IS clang-tidy-gated once `memory_ops.cpp` includes it — keep it clean):

```cpp
#pragma once
#include <chrono>
#include <functional>
#include <string>
#include <string_view>
#include <utility>

namespace starling::governance {

// One {stage, ms} entry — mirrors a single element of the JSON array stored in
// PipelineRun.stage_timings_ms (the persisted form uses the JSON key 'ms').
struct StageTiming {
    std::string stage;
    long long duration_ms = 0;
};

// RAII wall-clock timer for one pipeline stage. Measures with steady_clock
// (mirror of the latency idiom in src/extractor/openai_adapter.cpp:39,44-46) and,
// on scope exit, reports {stage, elapsed_ms} to a sink. The sink decides the
// destination: accumulate into TickOutcome (P3.c1 Phase 3b), or persist via
// PipelineRunStore::record_stage_timing once a run owns the cycle (Phase 4+).
//
// The destructor swallows any sink exception: a StageTimer must never throw
// during stack unwinding, and stage timing is best-effort observability
// (the metadata_only trace tier, 05_governance.md:114-119), never a correctness path.
class StageTimer {
public:
    using Sink = std::function<void(std::string_view stage, long long duration_ms)>;

    StageTimer(std::string stage, Sink sink)
        : stage_(std::move(stage)),
          sink_(std::move(sink)),
          start_(std::chrono::steady_clock::now()) {}

    ~StageTimer() {
        if (!sink_) {
            return;
        }
        const auto elapsed = std::chrono::steady_clock::now() - start_;
        const auto elapsed_ms =
            std::chrono::duration_cast<std::chrono::milliseconds>(elapsed).count();
        try {
            sink_(stage_, static_cast<long long>(elapsed_ms));
        } catch (...) {  // NOLINT(bugprone-empty-catch): dtor must not throw; timing is best-effort
        }
    }

    StageTimer(const StageTimer&) = delete;
    StageTimer& operator=(const StageTimer&) = delete;
    StageTimer(StageTimer&&) = delete;
    StageTimer& operator=(StageTimer&&) = delete;

private:
    std::string stage_;
    Sink sink_;
    std::chrono::steady_clock::time_point start_;
};

}  // namespace starling::governance
```

- [ ] **Step 4: Run test to verify it passes** — Run: `python scripts/configure_build.py --build` then `ctest --test-dir build-macos -R StageTimer`; Expected: PASS (4/4).

- [ ] **Step 5: Commit**

```bash
git add include/starling/governance/stage_timer.hpp tests/cpp/test_stage_timer.cpp tests/cpp/CMakeLists.txt
git commit -m "feat(P3.c1/3b): StageTimer RAII — steady_clock stage timing with sink-on-scope-exit"
```

## Task 3b.2: prove the StageTimer→PipelineRunStore persistence seam

**Files:**
- Modify: `tests/cpp/test_pipeline_run_store.cpp` (add ONE test case + `#include "starling/governance/stage_timer.hpp"`)

**Interfaces:**
- Consumes: `StageTimer` (3b.1); the file's existing helpers `fresh_db()`, `enqueue_and_claim(store)`, `eval_json_int(raw, "json_array_length", json)`, `eval_json_extract_str(raw, json, "$[0].stage")`, `eval_json_extract_int(raw, json, "$[0].ms")`; `PipelineRunStore::record_stage_timing` / `get`.
- This is the evidence that OQ-2's deferred persistence path works the moment a run owner exists (Phase 4) — the StageTimer sink calls `record_stage_timing` against a real claimed run.

- [ ] **Step 1: Add the `#include`** near the other governance includes at the top of `tests/cpp/test_pipeline_run_store.cpp`:

```cpp
#include "starling/governance/stage_timer.hpp"
```

- [ ] **Step 2: Write the failing test** — append (after the existing `RecordStageTimingAppendsEntries` case so the helpers are in scope):

```cpp
TEST(PipelineRunStore, StageTimerSinkPersistsViaRecordStageTiming) {
    auto conn = fresh_db();
    PipelineRunStore store(conn);
    const PipelineRun running = enqueue_and_claim(store);  // RUNNING run to attach to

    {
        // The SAME StageTimer as the tick path — here its sink writes to the store
        // instead of accumulating, proving the Phase-4 run-owner seam is wired.
        starling::governance::StageTimer timer(
            "embed", [&](std::string_view stage, long long ms) {
                store.record_stage_timing(running.id, stage, ms);
            });
    }  // scope exit -> record_stage_timing(running.id, "embed", <elapsed>)

    const auto after = store.get(running.id);
    ASSERT_TRUE(after.has_value());
    EXPECT_EQ(eval_json_int(conn.raw(), "json_array_length", after->stage_timings_ms), 1);
    EXPECT_EQ(eval_json_extract_str(conn.raw(), after->stage_timings_ms, "$[0].stage"), "embed");
    EXPECT_GE(eval_json_extract_int(conn.raw(), after->stage_timings_ms, "$[0].ms"), 0LL);
}
```

- [ ] **Step 3: Run to verify it passes** (the implementation already exists from 3a + 3b.1; this is a wiring proof, not new production code) — Run: `python scripts/configure_build.py --build` then `ctest --test-dir build-macos -R PipelineRunStore`; Expected: PASS (all existing store cases + the new one).
  - If `enqueue_and_claim`'s exact name/signature differs in the file, adapt the call to the file's actual helper (it enqueues then claims a run, returning the RUNNING `PipelineRun`). Do NOT change the helper.

- [ ] **Step 4: Commit**

```bash
git add tests/cpp/test_pipeline_run_store.cpp
git commit -m "test(P3.c1/3b): prove StageTimer sink persists via PipelineRunStore::record_stage_timing"
```

## Task 3b.3: wire `StageTimer` into `tick_all` (Option A — measure into `TickOutcome`)

> **If /plan-eng-review locks OQ-2 = B or C, this task is amended (enqueue/claim/confirm a run + swap the sink to `record_stage_timing`); StageTimer (3b.1) and the persistence proof (3b.2) are unchanged.**

**Files:**
- Modify: `include/starling/memory/memory_ops.hpp` (add include + `TickOutcome.stage_timings_ms`)
- Modify: `src/memory/memory_ops.cpp` (`tick_all` — 6 timed scopes)
- Modify: `tests/cpp/test_memory_ops.cpp` (add `TickAllRecordsStageTimings`)

**Interfaces:**
- Consumes: `StageTimer`, `StageTiming` (3b.1).
- Produces: `TickOutcome.stage_timings_ms` — a `std::vector<governance::StageTiming>` with exactly 6 entries in order `embed, policy, common_ground, replay, projection, outbox`.

- [ ] **Step 1: Write the failing test** — add to `tests/cpp/test_memory_ops.cpp` (mirror `TickAllAdvancesEmbeddingAndReturnsShape:74-91` verbatim for setup; the only new assertions are the stage-timing ones):

```cpp
TEST(MemoryOps, TickAllRecordsStageTimings) {
    auto a = make_adapter();
    extractor::FakeLLMAdapter llm;
    llm.set_default_response(extractor::LLMResponse{.raw_xml = kCannedJson, .ok = true});
    ASSERT_EQ(remember(*a, llm, "", params("Bob owns auth")).outcome, "accepted");

    embedding::StubEmbeddingAdapter emb(8);
    vector::SqliteBlobVectorIndex idx;
    embedding::EmbeddingWorker worker(*a, emb, idx);
    prospective::PolicyEngine policy(*a);

    const auto t = tick_all(*a, worker, policy, "2026-06-11T10:05:00Z");

    ASSERT_EQ(t.stage_timings_ms.size(), 8U);
    EXPECT_EQ(t.stage_timings_ms[0].stage, "embed");
    EXPECT_EQ(t.stage_timings_ms[1].stage, "policy");
    EXPECT_EQ(t.stage_timings_ms[2].stage, "common_ground");
    EXPECT_EQ(t.stage_timings_ms[3].stage, "replay_oscillation_guard");
    EXPECT_EQ(t.stage_timings_ms[4].stage, "replay_ttl_sweep");
    EXPECT_EQ(t.stage_timings_ms[5].stage, "replay_idle");
    EXPECT_EQ(t.stage_timings_ms[6].stage, "projection");
    EXPECT_EQ(t.stage_timings_ms[7].stage, "outbox");
    for (const auto& timing : t.stage_timings_ms) {
        EXPECT_GE(timing.duration_ms, 0);
    }
}
```

- [ ] **Step 2: Run test to verify it fails** — Run: `python scripts/configure_build.py --build` then `ctest --test-dir build-macos -R "MemoryOps.TickAllRecordsStageTimings"`; Expected: FAIL — `stage_timings_ms` is not a member of `TickOutcome`.

- [ ] **Step 3a: Add the field** — in `include/starling/memory/memory_ops.hpp`, add the include after the existing `#include "starling/persistence/sqlite_adapter.hpp"` block:

```cpp
#include "starling/governance/stage_timer.hpp"
```

and add the field to `struct TickOutcome` (after `int dispatched = 0;`, line ~120):

```cpp
    // P3.c1 Phase 3b: per-stage wall-clock timings (embed/policy/common_ground/
    // replay/projection/outbox), in execution order. metadata_only trace tier.
    std::vector<governance::StageTiming> stage_timings_ms;
```

- [ ] **Step 3b: Rewrite `tick_all`** — in `src/memory/memory_ops.cpp`, replace the body of `tick_all` (lines 191-230) with the timed version. This brace-wraps each existing stage with a `StageTimer`; behavior is unchanged except the new timings (designated initializers per the clang-tidy global constraint — `memory_ops.cpp` IS a linted TU):

```cpp
TickOutcome tick_all(persistence::SqliteAdapter& adapter,
                     embedding::EmbeddingWorker& worker,
                     prospective::PolicyEngine& policy,
                     std::string_view now_iso) {
    auto& conn = adapter.connection();
    TickOutcome t;

    // Accumulate each stage's {stage, ms} (Option A — no PipelineRun in the inline
    // tick; OQ-2/L1). The sink allocates a small SSO string + push_back; any
    // allocation failure is swallowed by the StageTimer dtor (best-effort, L6).
    std::vector<governance::StageTiming> timings;
    timings.reserve(8);  // 8 stages (L3: replay split into 3 sub-stages)
    const governance::StageTimer::Sink sink =
        [&timings](std::string_view stage, long long duration_ms) {
            timings.push_back(governance::StageTiming{
                .stage = std::string(stage), .duration_ms = duration_ms});
        };

    {
        governance::StageTimer timer("embed", sink);
        t.embedded = worker.tick_one_batch(conn, now_iso).embedded;
    }
    {
        governance::StageTimer timer("policy", sink);
        const auto ps = policy.tick(conn, now_iso);
        t.fired          = ps.fired;
        t.broken         = ps.broken;
        t.auto_withdrawn = ps.auto_withdrawn;
    }
    {
        // P2.j: grounding 滞后事件冲账(与原 Memory.tick/MemoryCore.tick 对称)。
        governance::StageTimer timer("common_ground", sink);
        tom::CommonGroundSubscriber::tick_one_batch(adapter, conn, std::string(now_iso));
    }
    // P2.o 回放维护:防护先行(振荡强制巩固、TTL 归档),再跑 idle 批做正常巩固。
    // L3 (codex #7): the 3 replay sub-calls are timed SEPARATELY so the Phase-5
    // sampler can attribute cost to oscillation-guard vs TTL-sweep vs idle-replay.
    // ReplayScheduler is a cheap borrowed-handle wrapper, constructed once outside.
    replay::ReplayScheduler replay(adapter);
    int forced = 0;
    {
        governance::StageTimer timer("replay_oscillation_guard", sink);
        forced = replay.enforce_oscillation_guard(conn);
    }
    {
        governance::StageTimer timer("replay_ttl_sweep", sink);
        t.ttl_archived = replay.sweep_volatile_ttl(conn, now_iso);
    }
    {
        governance::StageTimer timer("replay_idle", sink);
        const auto rs    = replay.run_idle(conn, now_iso);
        t.replay_sampled = rs.sampled;
        t.consolidated   = rs.compressed + forced;
    }
    {
        // 投影兜底批:泵覆盖 remember 路径,这里追平其余写入。
        governance::StageTimer timer("projection", sink);
        t.projected = projection::ProjectionMaintainer(adapter)
                          .tick_one_batch(conn, now_iso).events_processed;
    }
    {
        // 出箱收敛:进程内五消费者按 consumer_checkpoints 推进,Accept-all 标记 delivered。
        governance::StageTimer timer("outbox", sink);
        bus::DispatchOptions opts;
        opts.consumer_id = "in_process";
        bus::OutboxDispatcher dispatcher(
            conn, [](const bus::BusEvent&) { return bus::ConsumerDecision::Accept; },
            opts);
        t.dispatched = dispatcher.run_once().delivered;
    }

    t.stage_timings_ms = std::move(timings);
    return t;
}
```

- [ ] **Step 4: Run the new test + the existing tick tests to verify green** — Run: `python scripts/configure_build.py --build` then `ctest --test-dir build-macos -R MemoryOps`; Expected: PASS — `TickAllRecordsStageTimings` plus the unchanged `TickAllAdvancesEmbeddingAndReturnsShape` / `TickAllConsolidatesProjectsAndDispatches` (behavior-neutral wrap).

- [ ] **Step 5: Full C++ gate + commit**

Run: `python scripts/configure_build.py --build --test`; Expected: all ctest green.

```bash
git add include/starling/memory/memory_ops.hpp src/memory/memory_ops.cpp tests/cpp/test_memory_ops.cpp
git commit -m "feat(P3.c1/3b): wire StageTimer into tick_all — 8-stage timings in TickOutcome"
```

## Task 3b.4: surface `stage_timings_ms` read-only to Python (LOCKED = INCLUDED; L2 + L5)

> Read-only observability on the already-bound `memory_tick_all` dict. **L5: this is NOT a one-line binding change.** Adding `stage_timings_ms` to the dict breaks two downstream Python consumers (both verified against code in eng-review), so this task touches the binding, the `TickStats` dataclass, AND the dashboard tick-broadcast — all in one commit so the build never goes red.

**Files:**
- Modify: `bindings/python/bind_13_memory_ops.cpp` (`memory_tick_all` lambda — add the list to the returned dict)
- Modify: `python/starling/memory.py` (`TickStats` dataclass — add the field; **L5a**)
- Modify: `python/starling/dashboard/engine.py` (background-tick broadcast work-check; **L5b**)
- Create: `tests/python/test_tick_stage_timings.py`

**Interfaces:**
- Consumes: `TickOutcome.stage_timings_ms` (3b.3).
- Produces: `memory_tick_all` dict gains `"stage_timings_ms"` → a list of `{"stage": str, "ms": int}` in execution order (8 entries); `Memory.tick().stage_timings_ms` (a `TickStats` attribute) exposes the same.

- [ ] **Step 1: Write the failing pytest** — `tests/python/test_tick_stage_timings.py`. Mirrors `tests/python/test_memory_facade.py:94 test_recall_and_tick` (`make_stub_llm → Memory.open → remember → mem.tick()`). `Memory.tick()` returns a `TickStats` **dataclass**, so assert via **attribute access**, NOT dict subscript (**L5c**):

```python
"""P3.c1 Phase 3b — a real offline tick surfaces per-stage timings (8 stages, L3)."""
from __future__ import annotations

import starling

# Minimal canned extraction (mirrors test_memory_facade.py:CANNED_JSON).
CANNED_JSON = (
    '[{"holder":"alice","holder_perspective":"FIRST_PERSON",'
    '"subject":"cog-bob","predicate":"responsible_for","object":"auth",'
    '"modality":"BELIEVES","polarity":"POS","nesting_depth":0}]'
)

# Keep in lockstep with tick_all's StageTimer labels (L3) + the 3b.3 ctest.
EXPECTED_STAGES = [
    "embed", "policy", "common_ground",
    "replay_oscillation_guard", "replay_ttl_sweep", "replay_idle",
    "projection", "outbox",
]


def test_tick_returns_ordered_stage_timings(tmp_path):
    llm = starling.make_stub_llm(default_response=CANNED_JSON)
    mem = starling.Memory.open(str(tmp_path / "m.db"), agent="alice", llm=llm)
    mem.remember("Bob owns the auth module")

    stats = mem.tick()  # TickStats dataclass; the facade supplies `now`

    timings = stats.stage_timings_ms  # attribute access (L5c) — list of {stage, ms} dicts
    assert [entry["stage"] for entry in timings] == EXPECTED_STAGES
    assert all(isinstance(entry["ms"], int) and entry["ms"] >= 0 for entry in timings)
    mem.close()
```

- [ ] **Step 2: Run to verify it fails** — Run: `.venv/bin/python -m pytest tests/python/test_tick_stage_timings.py -v`; Expected: FAIL — `AttributeError: 'TickStats' object has no attribute 'stage_timings_ms'`.

- [ ] **Step 3: Add the binding field** — in `bindings/python/bind_13_memory_ops.cpp`, inside the `memory_tick_all` lambda, build the list before the `return py::dict(...)` (lines ~153-159) and add it as the last kwarg (`bind_13` IS clang-tidy-linted — loop var ≥3 chars):

```cpp
              py::list stages;
              for (const auto& timing : t.stage_timings_ms) {
                  stages.append(py::dict("stage"_a = timing.stage,
                                         "ms"_a = timing.duration_ms));
              }
              return py::dict("embedded"_a = t.embedded, "fired"_a = t.fired,
                              "broken"_a = t.broken, "auto_withdrawn"_a = t.auto_withdrawn,
                              "replay_sampled"_a = t.replay_sampled,
                              "consolidated"_a = t.consolidated,
                              "ttl_archived"_a = t.ttl_archived,
                              "projected"_a = t.projected,
                              "dispatched"_a = t.dispatched,
                              "stage_timings_ms"_a = stages);
```

- [ ] **Step 4: Fix the two downstream Python consumers (L5a + L5b)** — WITHOUT these, `Memory.tick()` raises `TypeError` and idle ticks spam WS broadcasts.

  **(a) `python/starling/memory.py`** — add the field to the `TickStats` dataclass (after `dispatched: int = 0`, ~line 113) so `TickStats(**self._core.tick(now))` (memory.py:190) accepts the new key. `field` is already imported (the file uses `field(default_factory=list)` for `RememberResult.statement_ids`):

```python
    dispatched: int = 0
    # P3.c1 Phase 3b: per-stage wall-clock timings — list of {"stage": str, "ms": int}.
    stage_timings_ms: list = field(default_factory=list)
```

  **(b) `python/starling/dashboard/engine.py:412`** — exclude the always-non-empty `stage_timings_ms` from the "did any work happen?" broadcast gate, so an idle tick stays silent:

```python
                # stage_timings_ms is always present (8 entries) — exclude it from the
                # work-check, else every idle tick fires a WS heartbeat (3b L5b).
                did_work = any(v for k, v in stats.items() if k != "stage_timings_ms")
                if on_tick is not None and did_work:
```

- [ ] **Step 5: Rebuild `_core` + run the new test + the dashboard regression** — Run: `python scripts/configure_build.py --build --python-editable` then `.venv/bin/python -m pytest tests/python/test_tick_stage_timings.py tests/python/test_dashboard_engine.py -v`; Expected: PASS (new test + the existing dashboard-engine tests that exercise the tick-broadcast path — the L5b regression guard).

- [ ] **Step 6: Full gate + commit**

Run: `python scripts/configure_build.py --build --test --python-editable` then `.venv/bin/python -m pytest tests/python`; Expected: all green (the full suite surfaces any other `TickStats(**...)` / tick-dict consumer).

```bash
git add bindings/python/bind_13_memory_ops.cpp python/starling/memory.py python/starling/dashboard/engine.py tests/python/test_tick_stage_timings.py
git commit -m "feat(P3.c1/3b): surface tick stage_timings_ms to Python (TickStats + dict + broadcast-gate fix)"
```

**Phase 3b acceptance:** `StageTimer` shipped + unit-tested; the **8** tick stages (L3) emit ordered `{stage, ms}` into `TickOutcome.stage_timings_ms`; a unit test proves the StageTimer sink can drive `record_stage_timing` against a real claimed run (the **wiring** — full Phase-4 lifecycle deferred, L6); (3b.4) the durations are observable read-only from Python (`Memory.tick().stage_timings_ms`) with the `TickStats` + broadcast-gate fixes (L5); full ctest + `pytest tests/python` green; clang-tidy CI green (watch `stage_timer.hpp` header gating + the `bind_13` loop var).

---

## Self-review

**Spec coverage** (governance-core.md §447-457 + 05_governance.md:49,87,114-119):
- "`stage_timer.hpp` RAII" → Task 3b.1 ✅
- "wire `StageTimer` into `src/memory/memory_ops.cpp` tick stages" → Task 3b.3 (all 8 stages — replay split into 3 per L3) ✅
- "+ `src/replay/replay_scheduler.cpp`" → the 3 replay sub-calls (`oscillation_guard`/`ttl_sweep`/`run_idle`) are timed **separately** from `tick_all` (L3 / codex #7), so the scheduler's distinct operations each get a timing without editing `replay_scheduler.cpp` (it is a pure `statements` worker that creates no run). Pushing timers *inside* `run_idle` (sample vs compress vs decay) is the truly-deferred finer grain.
- "stage timings recorded for a tick cycle" (acceptance) → recorded in `TickOutcome.stage_timings_ms` + observable (Python, 3b.4); **persistence to `governance_pipeline_run` is OQ-2, LOCKED = A** (deferred to Phase 4's run owner).
- Invariants 1/2/4/7 (governance-core.md:453) are the **3a store's** concern (already merged + tested); 3b adds no new invariant logic.

**Placeholder scan:** all code steps carry complete, compilable code grounded in verified line refs (`test_memory_ops.cpp:74`, `test_memory_facade.py:94`, `memory.py:105/190`, `engine.py:412`). The only "adapt" note (3b.2 `enqueue_and_claim` exact helper name) points at a helper in the same test file the implementer is editing. No `TODO`/`handle edge cases`/`similar to Task N`.

**Type consistency:** `StageTiming{stage: std::string, duration_ms: long long}` defined in 3b.1, consumed by `TickOutcome.stage_timings_ms` (3b.3) and the bind list (3b.4) — field name `duration_ms` consistent throughout (the JSON/dict key is the string literal `"ms"`, matching `record_stage_timing`'s persisted `json_object('stage', ?, 'ms', ?)`). `StageTimer::Sink = std::function<void(std::string_view, long long)>` — the 3b.3 accumulator sink and the 3b.2 store sink both match. `record_stage_timing(std::string_view, std::string_view, long long)` consumed unchanged from 3a. The **8** stage-name string literals are identical across Task 3b.3 production, the 3b.3 ctest, and the 3b.4 `EXPECTED_STAGES` (L3 lockstep). Python: `TickStats` gains `stage_timings_ms: list` (L5a) so `TickStats(**dict)` round-trips; `engine.py` work-check excludes the key (L5b).

**clang-tidy pre-flight (CI-only gate):** `stage_timer.hpp` — sized members fine (no enum), no `<3`-char identifiers (`duration_ms`/`elapsed_ms`/`stage_`/`sink_`/`start_`), the empty-catch carries a justified `// NOLINT(bugprone-empty-catch)`, all bodies braced, rule-of-5 complete (dtor + 4 deleted). `memory_ops.cpp` — designated initializers for `StageTiming`; all locals ≥3 chars (`timings`, `timer`, `forced`, `replay` — the 8 stage timers are all named `timer`, NOT `st`, in the canonical code above, to satisfy `readability-identifier-length`; note `forced` is declared once outside the 3 replay sub-scopes to thread from `oscillation_guard` into `replay_idle`). `bind_13` — loop var `timing` (6 chars). Python edits (`memory.py`, `engine.py`) are not clang-tidy-gated.

---

## Implementation Tasks
Synthesized from this review's findings. Each derives from a specific finding above.

- [ ] **T1 (P1, human: ~30min / CC: ~5min)** — 3b.4 Python integration — make `stage_timings_ms` not break `Memory.tick()` or spam WS
  - Surfaced by: Outside voice codex #1+#2 (verified) — `TickStats(**dict)` TypeError (memory.py:190) + `any(stats.values())` heartbeat (engine.py:412)
  - Files: `python/starling/memory.py`, `python/starling/dashboard/engine.py`, `bindings/python/bind_13_memory_ops.cpp`, `tests/python/test_tick_stage_timings.py`
  - Verify: `.venv/bin/python -m pytest tests/python/test_tick_stage_timings.py tests/python/test_dashboard_engine.py`
- [ ] **T2 (P2, human: ~20min / CC: ~5min)** — 3b.3 replay split — emit 8 stage timings (replay → 3 sub-stages)
  - Surfaced by: Outside voice codex #7 / decision D3 — coarse "replay" can't attribute consolidation vs sweep cost
  - Files: `src/memory/memory_ops.cpp`, `tests/cpp/test_memory_ops.cpp`
  - Verify: `ctest --test-dir build-macos -R "MemoryOps.TickAllRecordsStageTimings"`
- [ ] **T3 (P3, human: ~15min / CC: ~3min)** — Phase-4 forward-flag — record the store-sink silent-drop decision in the SDD ledger
  - Surfaced by: Failure mode #2 + codex #3 — a Phase-4 store-sink with a stale run_id drops the timing silently (dtor-swallow)
  - Files: `.superpowers/sdd/progress.md` (Phase-4 note), plan NOT-in-scope
  - Verify: n/a (documentation)

_T1 + T2 are P1/P2 (same branch); T3 is a P3 forward-note._

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 1 | issues_found | 10 findings; 6 folded (2 verified Python bugs + 2 doc fixes + replay-granularity + 1 forward-flag), 4 documented-rejections |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | clean | 4 decisions locked; 0 critical gaps; codex #1/#2 (Python breakage) folded into 3b.4 |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

Step 0 scope: ACCEPTED — 9 files is test-driven (4 test files + CMake + the read-only Python surface), not overbuild; 1 new class (`StageTimer`) + 1 POD (`StageTiming`). 4 sections: Architecture 0 change-worthy beyond OQ-2 (locked) + 2 considered-and-rejected (header split, microseconds); Code Quality 0; Tests strong (90% paths ★★★, 1 accepted pre-existing gap = throwing-stage fail-loud); Performance 0 (zero new DB writes on the tick). 4 decisions locked: **OQ-2=A** (measure-only, defer run-creation to Phase 4), **3b.4=Include** (read-only Python surface), **replay=8 sub-stages** (D3), **header=keep-one** (D4).

- **CODEX (outside voice):** 10 findings. **#1** (`engine.py:412 any(stats.values())` → idle-tick WS heartbeat) and **#2** (`memory.py:190 TickStats(**dict)` → `TypeError`) were CONCRETE Python-integration bugs the C++-focused review missed — both **verified against the exact code** and folded into 3b.4 (L5a/b/c). #7 (replay granularity) → 8 sub-stages (D3/L3); #8 (header split) → rejected (D4/L4). #4 (false "never throws" comment) + #10 ("Phase-4-ready" overstated) folded as doc fixes (L6). #3 (store-sink silent-drop) → Phase-4 forward-flag. #5 (per-stage status) / #6 (microseconds) / #9 (commit sequencing) documented-rejected with rationale.
- **CROSS-MODEL:** complementary, not contradictory — the Claude review cleared the C++ (StageTimer RAII, clang-tidy, tests); codex caught the binding's downstream Python blast radius. No tension requiring adjudication; both open choices (#7, #8) resolved by the user.
- **VERDICT:** ENG CLEARED — Phase 3b ready to implement subagent-driven. All 4 decisions locked + folded into the plan's LOCKED block; the canonical task code is updated (no stale 6-stage code).

NO UNRESOLVED DECISIONS

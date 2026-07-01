# PersonaSubscriber Implementation Plan (v2 — tick_all stage)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.
> **v2 supersedes the pump-slot v1** (eng-review found v1 inert — 3 blockers; see the spec REVISION + git history). Persona rebuild is now a `tick_all` STAGE.

**Goal:** Wire persona materialization live — `PersonaSubscriber` runs as a `tick_all` stage (after replay, where consolidation emits `statement.derived`) and rebuilds each affected subject's persona from its consolidated anchor statements, so `working_set`'s `## About me` block (empty in prod today) populates.

**Architecture:** `PersonaSubscriber::tick_one_batch` (checkpoint-driven, mirrors `common_ground_subscriber.cpp`) is invoked as a NEW `tick_all` stage inserted after `replay_idle` (mirrors how `tick_all` already calls the common_ground/replay subscribers as stages). It's a 9th `TickStage` (Soft lane — load-shed under DEGRADED). Core semantics → C++; Python only benefits + the e2e reads `render_working_set`. Spec: `docs/superpowers/specs/2026-07-01-persona-subscriber-materialization-design.md` (see the REVISION section).

**Tech Stack:** C++20, SQLite (migration 0030), GoogleTest, pybind11 (no binding change), pytest.

## Global Constraints

- **Trigger = `statement.derived` + `statement.consolidated` + `statement.superseded`** (exact strings). BLOCKER-1 fix: normal volatile→consolidated (replay `op_compress`) emits `statement.derived` (`replay_scheduler.cpp:376`); `statement.consolidated` fires ONLY on reconsolidation (`arbitration.cpp:213/281`); `statement.superseded` on correction (`:432`). The old v1 trigger (`statement.consolidated` alone) never fired on the primary path.
- **Invocation = a `tick_all` STAGE after `replay_idle`** (BLOCKER-2 fix: the post-write `SubscriberPump` does NOT run in `tick_all`; consolidation happens in tick's replay). Confirmed: `run_idle`→`op_compress`→`emit_event("statement.derived",...)` writes into `bus_events` on the same `conn` in the same tick, so a persona stage right after `replay_idle` sees them via a checkpoint read.
- **anchor `review_status IN ('approved','review_requested')`** (BLOCKER-3 fix: remembered self-facts default `review_requested` and never auto-reach `approved`). Exclude `rejected`/`pending_review`. Scope: `subject_id=holder AND consolidation_state='consolidated' AND review_status IN ('approved','review_requested')`. Classify `holder_id==subject_id`→`self_model_anchor` else `profile_anchor`; `predicate→dimension`, `object_value→value`, `confidence→confidence`.
- **Persona = 9th `TickStage::Persona`, SOFT lane** — add to `include/starling/governance/tick_load_shedding.hpp` (Soft group in `lane_of`; `should_run_stage` unchanged, delegates to `lane_of`). Gate the stage via `should_run_stage(TickStage::Persona, health)`.
- **Write discipline (eng-review fold — tick-stage ≠ v1 pump slot):** the persona stage calls `PersonaContainer(adapter).rebuild(conn, …)` DIRECTLY inside `tick_all`'s transaction — it must write on `conn` with **NO `BEGIN`/`SAVEPOINT`** (matching the `projection` stage's `ProjectionMaintainer(adapter).tick_one_batch(conn,…)` precedent). v1's SAVEPOINT-via-`run_isolated` reasoning does NOT apply here (there's no pump wrapper). VERIFY at impl: confirm `PersonaContainer::rebuild` writes on `conn` without opening `BEGIN` (read `src/neocortex/persona_container.cpp`); if it opens `BEGIN`, that nests in the tick and hits the offline-only reentrancy trap → the stage is wrong until rebuild is conn-direct.
- **Subject resolution (eng-review fold — confirmed correct):** the 3 trigger events do NOT uniformly carry `subject_id`, and their `aggregate_id` differs (`derived`=holder, `consolidated`=stmt, `superseded`=new_id). So resolve subject ONLY via `primary_id`→`SELECT subject_id FROM statements WHERE id=primary_id` (which the plan already does) — NEVER read subject from `aggregate_id`.
- **Persona QUALITY is out of this slice (eng-review fold):** the anchor mapping is the spec's locked trivial `dimension=predicate, value=object_value` (no allowlist). The empirical outside voice flagged this yields raw `predicate: object` lines (not curated dimensions) and multi-valued predicates collide on the `dimension` key. DECISION (user, D2=A): ship the proven wiring + MVP mapping now; **persona quality is explicitly validated by the queued real-LLM baseline run (item A)** — add a curation/dimension-normalization layer ONLY if real LLM output warrants it. Do NOT build curation blind in this slice.
- **Scope (eng-review fold — keep all-subjects):** the stage rebuilds every affected subject's persona; only `self`'s is read today (`working_set` reads `subject==agent_id`). Non-self personas are latent/harmless rows — kept because the system-level subscriber cannot know "self" (a read-side notion). Not over-engineering; the uniform mechanism is simpler than threading `agent_id` into `tick_all`.
- **P3.c smoke FLIPS** (persona is now a tick stage): `tests/python/test_load_test_p3c_smoke.py` must add `"persona"` to the expected 9-stage set + flip `"persona" not in` → `in`.
- **e2e consumer-proof = `mem.render_working_set(...).render()`'s `## About me` block** (MAJOR-4 fix), distinct from `## Relevant memories`. NOT `Memory.query`'s `context_pack`.
- **Build:** `python scripts/configure_build.py --build --python-editable` (C++ + migration + binding). Tools in `.venv/bin/{cmake,ctest,ninja}` (NOT system PATH). **clang-tidy CI-only gate** on `src/|bindings/` — write clean by construction (≥3-char ids on new lines, braces, no branch-clone, `reinterpret_cast` NOLINT mirroring CG). **Commit gate:** full ctest + pytest green.
- **git:** explicit-path `git add`; no `-A`/`--no-verify`/`--amend`. Footer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

## Task 1: PersonaSubscriber unit (migration + subscriber + isolated ctest)

**Files:** Create `migrations/0030_persona_subscriber_checkpoint.sql`, `include/starling/tom/persona_subscriber.hpp`, `src/tom/persona_subscriber.cpp`, `tests/cpp/test_persona_subscriber.cpp`; Modify root `CMakeLists.txt` (add src after line 120, next to `common_ground_subscriber.cpp`) + `tests/cpp/CMakeLists.txt` (add test after line 114).

**Interfaces (Produces):**
```cpp
namespace starling::tom {
class PersonaSubscriber {
public:
    [[nodiscard]] static int tick_one_batch(persistence::SqliteAdapter& adapter,
                                            persistence::Connection& conn,
                                            std::string_view now_iso,
                                            int batch_size = 100);
};
}
```

- [ ] **Step 1: Migration** `migrations/0030_persona_subscriber_checkpoint.sql`:
```sql
-- E (persona 物化接线): PersonaSubscriber outbox checkpoint (singleton, 仿 0022).
-- Drives persona rebuild as a tick_all stage on statement.derived/consolidated/superseded.
CREATE TABLE persona_subscriber_checkpoint (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_processed_outbox_sequence INTEGER NOT NULL DEFAULT 0,
    last_updated_at TEXT NOT NULL
);
INSERT INTO persona_subscriber_checkpoint (id, last_processed_outbox_sequence, last_updated_at)
    VALUES (1, 0, '2026-07-01T00:00:00Z');
```

- [ ] **Step 2: Header** `include/starling/tom/persona_subscriber.hpp` — exactly the Interfaces block above, with `#pragma once` + includes `starling/persistence/sqlite_adapter.hpp`, `starling/persistence/connection.hpp`, `<string_view>`.

- [ ] **Step 3: Write the failing ctest** `tests/cpp/test_persona_subscriber.cpp`. Write PURPOSE-BUILT helpers (the CG helpers are incompatible — MAJOR-5). The `statements` INSERT has 25 columns (order: id,tenant_id,holder_id,holder_perspective,subject_kind,subject_id,predicate,object_kind,object_value,canonical_object_hash,canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,affect_json,activation,last_accessed,provenance,consolidation_state,review_status,scope_parties_json,created_at,updated_at); `bus_events` INSERT has 9 (event_id,tenant_id,event_type,primary_id,aggregate_id,outbox_sequence,idempotency_key,payload_json,created_at):

```cpp
namespace {
// Purpose-built seed helpers (explicit object_value / consolidation_state /
// review_status / event_type — the CG helpers hardcode these).
void seed_statement(persistence::Connection& conn, const std::string& sid,
                    const std::string& holder, const std::string& subject,
                    const std::string& predicate, const std::string& object_value,
                    const std::string& consolidation_state,
                    const std::string& review_status) {
    sqlite3_stmt* raw = nullptr;
    sqlite3_prepare_v2(conn.raw(),
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
        "subject_kind,subject_id,predicate,object_kind,object_value,"
        "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
        "confidence,observed_at,salience,affect_json,activation,last_accessed,"
        "provenance,consolidation_state,review_status,scope_parties_json,"
        "created_at,updated_at) VALUES "
        "(?,'default',?,'first_person','entity',?,?,'str',?,'h','v1','believes',"
        "'pos',0.8,'2026-01-01T00:00:00Z',0.5,'{}',1.0,'2026-01-01T00:00:00Z',"
        "'user_input',?,?,'[]','2026-01-01T00:00:00Z','2026-01-01T00:00:00Z')",
        -1, &raw, nullptr);
    persistence::StmtHandle h(raw);
    persistence::detail::bind_sv(h.get(), 1, sid);
    persistence::detail::bind_sv(h.get(), 2, holder);
    persistence::detail::bind_sv(h.get(), 3, subject);
    persistence::detail::bind_sv(h.get(), 4, predicate);
    persistence::detail::bind_sv(h.get(), 5, object_value);
    persistence::detail::bind_sv(h.get(), 6, consolidation_state);
    persistence::detail::bind_sv(h.get(), 7, review_status);
    sqlite3_step(h.get());
}
void seed_event(persistence::Connection& conn, const std::string& eid,
                const std::string& event_type, const std::string& primary_id, int seq) {
    sqlite3_stmt* raw = nullptr;
    sqlite3_prepare_v2(conn.raw(),
        "INSERT INTO bus_events(event_id,tenant_id,event_type,primary_id,aggregate_id,"
        "outbox_sequence,idempotency_key,payload_json,created_at) VALUES "
        "(?,'default',?,?,?,?,?,'{}','2026-07-01T00:00:00Z')", -1, &raw, nullptr);
    persistence::StmtHandle h(raw);
    persistence::detail::bind_sv(h.get(), 1, eid);
    persistence::detail::bind_sv(h.get(), 2, event_type);
    persistence::detail::bind_sv(h.get(), 3, primary_id);
    persistence::detail::bind_sv(h.get(), 4, primary_id);
    sqlite3_bind_int(h.get(), 5, seq);
    persistence::detail::bind_sv(h.get(), 6, std::string("ik-") + eid);
    sqlite3_step(h.get());
}
}  // namespace

// statement.derived (normal consolidation) on a self-anchor → persona materializes.
TEST(PersonaSubscriber, DerivedSelfAnchorMaterializes) {
    auto adapter = persistence::SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    // review_requested is the DEFAULT for a remembered self-fact (BLOCKER-3):
    seed_statement(conn, "S1", "self", "self", "trait_curiosity", "high",
                   "consolidated", "review_requested");
    seed_event(conn, "E1", "statement.derived", "S1", 1);
    EXPECT_EQ(tom::PersonaSubscriber::tick_one_batch(*adapter, conn, "2026-07-01T10:00:00Z"), 1);
    const auto view = neocortex::PersonaContainer(*adapter).read(conn, "default", "self");
    EXPECT_TRUE(view.found);
    EXPECT_EQ(view.dimensions.at("trait_curiosity"), "high");
}

// profile anchor (holder != subject) classified; checkpoint advances; idempotent.
TEST(PersonaSubscriber, ProfileAnchorAndCheckpoint) {
    auto adapter = persistence::SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_statement(conn, "S2", "alice", "bob", "role", "engineer",
                   "consolidated", "approved");
    seed_event(conn, "E2", "statement.derived", "S2", 5);
    EXPECT_EQ(tom::PersonaSubscriber::tick_one_batch(*adapter, conn, "2026-07-01T10:00:00Z"), 1);
    EXPECT_EQ(neocortex::PersonaContainer(*adapter).read(conn, "default", "bob")
                  .dimensions.at("role"), "engineer");
    EXPECT_EQ(tom::PersonaSubscriber::tick_one_batch(*adapter, conn, "2026-07-01T10:05:00Z"), 0);
}

// volatile / rejected are excluded → no materialization.
TEST(PersonaSubscriber, IgnoresVolatileAndRejected) {
    auto adapter = persistence::SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_statement(conn, "S3", "self", "self", "trait_x", "y", "volatile", "review_requested");
    seed_event(conn, "E3", "statement.derived", "S3", 2);
    tom::PersonaSubscriber::tick_one_batch(*adapter, conn, "2026-07-01T10:00:00Z");
    EXPECT_FALSE(neocortex::PersonaContainer(*adapter).read(conn, "default", "self").found);
}

// statement.superseded (correction) also triggers rebuild — the primary_id is
// the NEW (forked) row, which carries the subject (Global Constraint: subject
// via primary_id, never aggregate_id).
TEST(PersonaSubscriber, SupersededTriggersRebuild) {
    auto adapter = persistence::SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_statement(conn, "S4new", "self", "self", "role", "staff_engineer",
                   "consolidated", "review_requested");
    seed_event(conn, "E4", "statement.superseded", "S4new", 7);
    EXPECT_EQ(tom::PersonaSubscriber::tick_one_batch(*adapter, conn, "2026-07-01T10:00:00Z"), 1);
    EXPECT_EQ(neocortex::PersonaContainer(*adapter).read(conn, "default", "self")
                  .dimensions.at("role"), "staff_engineer");
}
```
(Adapt include paths / `StmtHandle`/`bind_sv` qualification to the repo's helpers — read `common_ground_subscriber.cpp` for the exact `persistence::detail::` names.)

- [ ] **Step 4: Register in CMake, build, confirm FAIL.** `python scripts/configure_build.py --build`; `.venv/bin/ctest --test-dir build-macos -R 'PersonaSubscriber'` → FAIL (unimplemented).

- [ ] **Step 5: Implement** `src/tom/persona_subscriber.cpp` — the checkpoint-driven `tick_one_batch` (mirror `common_ground_subscriber.cpp`'s `sqlite3_stmt*`+`StmtHandle`+`bind_sv`+`col` idiom). Key differences from the v1 draft: the event-type `IN` list is **`('statement.derived','statement.consolidated','statement.superseded')`**, and the anchor query's filter is **`review_status IN ('approved','review_requested')`**:
  1. read `persona_subscriber_checkpoint.last_processed_outbox_sequence`;
  2. `SELECT primary_id, tenant_id, outbox_sequence FROM bus_events WHERE outbox_sequence > ? AND event_type IN ('statement.derived','statement.consolidated','statement.superseded') ORDER BY outbox_sequence LIMIT ?` (track `max_seq`);
  3. per event, `SELECT subject_id FROM statements WHERE id=? AND tenant_id=?` → dedup `(tenant, subject_id)` into a `std::set`;
  4. per affected `(tenant, subject)`: `SELECT id, holder_id, predicate, object_value, confidence FROM statements WHERE tenant_id=? AND subject_id=? AND consolidation_state='consolidated' AND review_status IN ('approved','review_requested')` → build `vector<neocortex::AnchorStatement>` (`.anchor_type = (holder==subject)?"self_model_anchor":"profile_anchor"`, `.dimension=predicate`, `.value=object_value`, `.confidence=col_double`); if empty `continue`; else `PersonaContainer(adapter).rebuild(conn, tenant, subject, sources, now_iso)` inside `try{}catch(const neocortex::ConcurrentRebuildError&){}`;
  5. if any events seen, `UPDATE persona_subscriber_checkpoint SET last_processed_outbox_sequence=?, last_updated_at=? WHERE id=1` (bind `max_seq`, `now_iso`);
  6. `return static_cast<int>(events.size())`.
  (Write the body fresh from steps 1-6 above + the `common_ground_subscriber.cpp` idiom as the template — there is NO prior persona_subscriber.cpp in git (v1 was a plan only, never implemented). Use ≥3-char identifiers on all new lines; NOLINT the `reinterpret_cast` in the `col` helper mirroring CG.)

- [ ] **Step 6: Build + verify PASS** (`-R 'PersonaSubscriber'` 3/3) + full ctest green.

- [ ] **Step 7: Full gate + commit.** `.venv/bin/python -m pytest tests/python -q` green. Commit: `feat(persona): PersonaSubscriber unit — rebuild on statement.derived/consolidated/superseded`.

---

## Task 2: TickStage::Persona (Soft lane) + tick_all persona stage + C++ tests

**Files:** Modify `include/starling/governance/tick_load_shedding.hpp`, `tests/cpp/test_tick_load_shedding.cpp`, `src/memory/memory_ops.cpp`, `tests/cpp/test_memory_ops.cpp`.

**Interfaces:**
- Consumes: `PersonaSubscriber::tick_one_batch` (Task 1); `should_run_stage`/`StageTimer` (existing).
- Produces: `TickStage::Persona` (Soft); a `"persona"` tick stage in `tick_all` after `replay_idle`.

- [ ] **Step 1: Extend the load-shedding tests (RED)** in `tests/cpp/test_tick_load_shedding.cpp`: add `TEST(TickLoadShedding_LaneOf, PersonaIsSoft){ EXPECT_EQ(lane_of(TickStage::Persona), TickLane::Soft); }`; add `EXPECT_TRUE(should_run_stage(TickStage::Persona, RuntimeHealth::READY))` to `ReadyRunsAllStages`; add `EXPECT_FALSE(should_run_stage(TickStage::Persona, RuntimeHealth::DEGRADED))` to `DegradedSkipsSoftStages`; add `EXPECT_FALSE(...DRAINING)` to `DrainingRunsOutboxOnly`; add `EXPECT_FALSE(...UNREADY)` to `UnreadyRunsNoStages`. Build → FAIL (`Persona` undefined).

- [ ] **Step 2: Add `TickStage::Persona`** to `include/starling/governance/tick_load_shedding.hpp` — insert into the enum after `ReplayIdle` and before `Projection`:
```cpp
    ReplayIdle,               // soft   — non-critical consolidation (replay.run_idle)
    Persona,                  // soft   — non-critical persona rebuild (after replay)
    Projection,               // soft   — non-critical projection batch
```
and add `case TickStage::Persona:` to the **Soft** arm of `lane_of` (alongside `ReplayIdle`/`Projection`). `should_run_stage` needs NO change. Build → `TickLoadShedding*` tests PASS.

- [ ] **Step 3: Insert the persona tick stage (RED first via test in Step 5).** In `src/memory/memory_ops.cpp`: add `#include "starling/tom/persona_subscriber.hpp"`; change `timings.reserve(8)` → `timings.reserve(9)`; insert BETWEEN the `replay_idle` block and the `projection` block:
```cpp
    if (governance::should_run_stage(governance::TickStage::Persona, health)) {
        governance::StageTimer timer("persona", sink);
        tom::PersonaSubscriber::tick_one_batch(adapter, conn, now_iso);
    } else {
        t.stages_skipped.emplace_back("persona");
    }
```

- [ ] **Step 4: Update the tick_all stage-timing/gating tests** in `tests/cpp/test_memory_ops.cpp`: in `TickAllRecordsStageTimings` change `size()` `8U`→`9U`, insert `EXPECT_EQ(t.stage_timings_ms[6].stage, "persona");` and bump `projection`→index 7, `outbox`→index 8. In the DEGRADED gating test bump soft-skip count `4U`→`5U` (persona joins embed/common_ground/replay_idle/projection); DRAINING skip `7U`→`8U`; UNREADY `8U`→`9U`. (Read the file for the exact assertion lines — the research cited ~161-186 for timings, ~253/289/323 for the gating tests.)

- [ ] **Step 5: Build + verify** `.venv/bin/ctest --test-dir build-macos -R 'MemoryOps|TickLoadShedding'` PASS + full ctest green. (The persona stage runs after replay_idle; with a seeded consolidated self-fact + a `statement.derived` event from replay, it materializes — but `TickAllRecordsStageTimings` only pins the stage LABELS/order, which is what changed.)

- [ ] **Step 6: Full gate + commit.** Full ctest + `.venv/bin/python -m pytest tests/python -q` (Python unaffected so far). Commit: `feat(persona): TickStage::Persona (soft lane) + tick_all persona stage after replay`.

---

## Task 3: P3.c smoke flip + Python full-journey e2e

**Files:** Modify `tests/python/test_load_test_p3c_smoke.py`; Create `tests/python/test_persona_materialization.py`.

- [ ] **Step 1: Write the failing e2e** `tests/python/test_persona_materialization.py` (real-consumer proof via `render_working_set`, MAJOR-4 fix):
```python
def test_remember_then_tick_populates_about_me(tmp_path):
    from starling import Memory, make_stub_llm
    fake = make_stub_llm(default_response=(
        '[{"holder":"self","holder_perspective":"FIRST_PERSON",'
        '"subject":"self","predicate":"trait_curiosity","object":"high",'
        '"modality":"BELIEVES","polarity":"POS","nesting_depth":0}]'))
    mem = Memory.open(str(tmp_path / "persona.db"), agent="self",
                      tenant_id="default", llm=fake)
    mem.remember("I am deeply curious.", now="2026-07-01T00:00:00Z")
    # Ticks drive replay consolidation → statement.derived → the persona tick
    # stage (after replay) rebuilds self's persona in the SAME tick.
    for _ in range(30):
        mem.tick("2026-07-01T00:05:00Z")
    cb = mem.render_working_set(interlocutor="other", goal="who am I")
    rendered = cb.render()
    # The persona ## About me block populated (empty before this slice) —
    # assert the About-me section specifically, distinct from Relevant memories.
    assert "## About me" in rendered
    assert "trait_curiosity" in rendered
    labels = [b.label for b in cb.blocks]
    assert "persona" in labels
    persona_block = next(b for b in cb.blocks if b.label == "persona")
    assert persona_block.content   # non-empty
```
**VERIFY at impl:** that 30 ticks reliably consolidate the self-fact (replay online-consolidation cadence) so `statement.derived` fires + the persona stage materializes. If not, drive consolidation explicitly (e.g. `mem.run_replay("idle")` if exposed) — do NOT weaken the About-me assertion.

- [ ] **Step 2: Run → verify FAIL.** With Tasks 1-2 already committed on this branch (they precede Task 3 in execution order), the persona stage IS wired — so this asserts GREEN, proving the full journey (remember → tick consolidates → persona stage rebuilds → About-me populated). If it FAILS, the wiring is broken: debug before proceeding (do NOT weaken the About-me assertion). The empirical outside voice already confirmed each leg holds (derived fires in 1 tick; render_working_set surfaces About-me), so a failure here points to an integration defect, not a bad assumption.

- [ ] **Step 3: Flip the P3.c smoke** `tests/python/test_load_test_p3c_smoke.py`: add `"persona"` to the expected stage set (now 9: embed/policy/common_ground/replay_oscillation_guard/replay_ttl_sweep/replay_idle/**persona**/projection/outbox) and flip `assert "persona" not in ...` → `assert "persona" in report["tick"]["stage_ms_total"]`. Update the "8 known stages" comment → 9.

- [ ] **Step 4: Rebuild + verify.** `python scripts/configure_build.py --build --python-editable` (migration + C++). Run `test_persona_materialization.py` (PASS) + `test_load_test_p3c_smoke.py` (PASS, now expects persona) + full `.venv/bin/python -m pytest tests/python` + full ctest green.

- [ ] **Step 5: Full gate + commit.** Commit: `feat(persona): e2e About-me materialization + P3.c smoke expects the persona tick stage`.

---

## Slice acceptance
`PersonaSubscriber::tick_one_batch` runs as a `tick_all` stage after `replay_idle` (Soft lane, load-shed under DEGRADED), triggered by the `statement.derived` events replay emits in the same tick; rebuilds each affected subject's persona from consolidated statements (`review_status IN ('approved','review_requested')`), self/profile classified. `working_set`'s `## About me` block populates in production (empty before) — proven by a full-journey pytest reading `render_working_set().render()`. The P3.c smoke now expects persona as the 9th tick stage. Full ctest + pytest green. **All 3 v1 blockers fixed:** trigger fires (derived), runs where consolidation happens (tick stage), filter includes self-facts (review_requested).

## Self-review
**Spec coverage (REVISION):** tick-stage invocation (T2) ✓; trigger derived+consolidated+superseded (T1 query) ✓; review_status incl review_requested (T1 anchor query) ✓; TickStage::Persona Soft + gating (T2) ✓; P3.c smoke flip (T3) ✓; render_working_set e2e (T3) ✓; fresh test helpers (T1) ✓. **Placeholder scan:** real code/SQL/commands; the e2e has a VERIFY (consolidation cadence) with a no-weakening guard. **Type consistency:** `tick_one_batch(SqliteAdapter&,Connection&,string_view,int)->int`; `AnchorStatement{stmt_id,anchor_type,dimension,value,confidence}`; `TickStage::Persona` Soft; `render_working_set(interlocutor,*,goal,token_budget)->ContextBlock{.blocks[.label/.content],.render()->str}`.

## Open questions for /plan-eng-review (v2 re-verify)
- Re-verify (the v1 review's method): does a `tick_all` persona stage AFTER `replay_idle` actually see the `statement.derived` events replay emits in the SAME tick (via the checkpoint read on the same `conn`)? Empirically run the T3 e2e.
- Does 30 ticks reliably consolidate one self-fact (so `statement.derived` fires)? Confirm the online/idle consolidation cadence; if not, the e2e must drive replay explicitly.
- Confirm `render_working_set().render()` surfaces `## About me` for `subject=self` (persona keyed by `agent_id`), distinct from `## Relevant memories`.
- Confirm the persona stage's position (after replay_idle, before projection) is correct — replay must have emitted derived BEFORE persona reads them (same tick).

**ALL FOUR RESOLVED (empirical outside voice, 2026-07-01):** (1) yes — same `conn`, same tick, before projection/outbox (`replay_scheduler.cpp:376` emit + `memory_ops.cpp:198-283` stage order); (2) **1 tick** consolidates (30 is far more than enough, no explicit replay); (3) confirmed — `render_working_set().render()` prints a distinct `## About me` block with the anchor value, separate from `## Relevant memories`; (4) confirmed correct. Bonus: fresh self-fact is `review_requested` → the anchor filter includes it.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 1 | issues_found | timed out at 5 min (exit 124) → Opus empirical subagent ran instead |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 2 | **CLEAN (v2)** | v1 NOT CLEARED (3 blockers); v2: 4 assumptions empirically VERIFIED, 1 quality decision (D2=A), 4 folds applied |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

Step 0 scope: ACCEPTED (~12 files trips the 8-file smell, but 5 are tests + 2 CMake + 1 migration; real new logic = 1 class + 1 tick stage + 1-line enum; the load-shedding cascade is required, not optional; user chose this scope via A). Sections 1-4: Architecture sound (Soft-lane persona sheds with replay_idle, no stranding); Code Quality DRY; Tests strong; Performance fine (per-tick cost bounded by consolidations/tick, Soft-shed under pressure).

- **OUTSIDE VOICE (Opus empirical subagent — built + ran the pipeline, 604s):** all 4 load-bearing assumptions VERIFIED against the running `_core` — v1's 3 blockers are genuinely fixed (trigger `statement.derived` fires; runs in tick where consolidation happens; `review_requested` filter includes self-facts) + the e2e surface (`render_working_set` About-me) is correct. It surfaced ONE deeper issue: the statement→anchor mapping is the spec's trivial `dimension=predicate/value=object` (raw `predicate:object` lines, possible dimension collisions) — persona *quality*, not wiring.
- **CODEX:** timed out at 5 min (exit 124, same as v1's session) → fell back to the Opus subagent, which is the stronger check here (read-only codex can't build+run the empirical verification that caught v1's blockers).
- **CROSS-MODEL:** tension on the anchor mapping — the inline review treated it as the spec's locked MVP; the empirical outside voice called it under-designed. Resolved **D2=A**: ship the empirically-proven wiring + MVP mapping now; persona quality is explicitly validated by the queued real-LLM baseline run (item A); add curation only if real output warrants. Consistent with the project's measure-first / no-premature-abstraction discipline.
- **FOLDS APPLIED (4):** write-discipline (rebuild writes on `conn`, no BEGIN — tick-stage ≠ v1 pump slot; must-verify `persona_container.cpp`); subject-resolution (via `primary_id`→statements, never `aggregate_id` — plan already correct, now explicit); scope (keep all-subjects, non-self rows latent/harmless); + 3 plan-polish minors (2 misleading-text fixes + an explicit `statement.superseded` ctest).
- **VERDICT: ENG CLEARED (v2) — ready to implement.** The re-design is empirically validated; the one quality concern is a decided deferral (D2=A → item A), not a blocker.

NO UNRESOLVED DECISIONS

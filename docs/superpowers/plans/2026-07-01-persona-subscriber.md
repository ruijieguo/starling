# PersonaSubscriber Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Wire persona materialization into the live dataflow — a new `PersonaSubscriber` (SubscriberPump slot #8) rebuilds a subject's persona container from consolidated+approved anchor statements on `statement.consolidated`/`statement.superseded`, so the Working Set's `## About me` block (empty in prod today) populates.

**Architecture:** Mirror `src/tom/common_ground_subscriber.cpp`. A checkpoint-driven subscriber reads new `bus_events`, resolves affected `(tenant, subject_id)` holders, and calls the existing `PersonaContainer::rebuild` per holder. Registered as pump slot #8 (SAVEPOINT-isolated). Core semantics → C++; Python only benefits (working_set reads self's persona). Design spec: `docs/superpowers/specs/2026-07-01-persona-subscriber-materialization-design.md`.

**Tech Stack:** C++20 (`src/tom/`, `include/starling/tom/`), SQLite (migration), GoogleTest, pybind11 (no binding change), pytest.

## Global Constraints

- **Trigger = `statement.consolidated` + `statement.superseded`** (exact strings, `arbitration.cpp:213,281,432`). NOT `statement.written` (spec slow-channel; avoids per-write stampede → keeps c2.1 deferred).
- **Anchor scope = `subject_id = holder AND consolidation_state = 'consolidated' AND review_status = 'approved'`** (exact enum strings, `statement_enums.cpp`). Classify `holder_id == subject_id` → `"self_model_anchor"`, else `"profile_anchor"`; `predicate → dimension`, `object_value → value`, `confidence → confidence`.
- **Persona keyed by `subject_id`** — `rebuild`'s `holder_id` param receives the `subject_id`. Rebuild per affected subject (the subscriber cannot know "self" — that's `working_set`'s read-side `agent_id`).
- **Do NOT add a `tick_all` stage for persona** — pump slots don't appear in `TickStats.stage_timings_ms`, so the P3.c smoke `"persona" not in stage_timings_ms` (`tests/python/test_load_test_p3c_smoke.py`) stays valid. Pump-slot only.
- **Swallow `ConcurrentRebuildError`** (move on; CommonGround precedent). SAVEPOINT isolation via `run_isolated` (no `BEGIN` nesting — the write-discipline invariant).
- **Build (C++ + migration + binding rebuild):** `python scripts/configure_build.py --build --python-editable`. Build tools in `.venv/bin/{cmake,ctest,ninja}` (NOT system PATH). Test binary `build-macos/tests/cpp/starling_tests`.
- **clang-tidy CI-only gate** on `.cpp`/`.hpp` under `src/|bindings/`, changed-lines, `WarningsAsErrors *`. Write clean by construction: `[[nodiscard]]` where returning a value; identifiers ≥3 chars (loop vars: `found`/`evt`, not `it`/`ev`... note the CG template uses `ev`/`col`/`h` — those are pre-existing; NEW changed lines must be ≥3-char); braces; no `bugprone-branch-clone`. clang-tidy un-runnable locally — the IDE surfaces it; CI is the gate.
- **Commit gate:** full `.venv/bin/ctest --test-dir build-macos` + `.venv/bin/python -m pytest tests/python` green.
- **git:** explicit-path `git add`; no `-A`/`--no-verify`/`--amend`. Footer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

## File structure
- **Create** `migrations/0030_persona_subscriber_checkpoint.sql` — singleton checkpoint table (mirrors 0022).
- **Create** `include/starling/tom/persona_subscriber.hpp` + `src/tom/persona_subscriber.cpp` — the subscriber.
- **Create** `tests/cpp/test_persona_subscriber.cpp` — isolated ctest.
- **Modify** root `CMakeLists.txt` (add the src after line 120) + `tests/cpp/CMakeLists.txt` (add the test after line 114).
- **Modify** `src/bus/subscriber_pump.cpp` — add slot #8 + the include.
- **Create** `tests/python/test_persona_materialization.py` — full-journey e2e (the real-consumer proof).

---

## Task 1: PersonaSubscriber + migration + isolated ctest

**Files:** Create `migrations/0030_persona_subscriber_checkpoint.sql`, `include/starling/tom/persona_subscriber.hpp`, `src/tom/persona_subscriber.cpp`, `tests/cpp/test_persona_subscriber.cpp`; Modify root `CMakeLists.txt` + `tests/cpp/CMakeLists.txt`.

**Interfaces (Produces):**
```cpp
namespace starling::tom {
class PersonaSubscriber {
public:
    // Reads new statement.consolidated/.superseded bus_events since the checkpoint,
    // rebuilds each affected subject's persona from its consolidated+approved anchor
    // statements, advances the checkpoint. Returns the number of events processed.
    [[nodiscard]] static int tick_one_batch(persistence::SqliteAdapter& adapter,
                                            persistence::Connection& conn,
                                            std::string_view now_iso,
                                            int batch_size = 100);
};
}
```

- [ ] **Step 1: Write the migration** `migrations/0030_persona_subscriber_checkpoint.sql`:

```sql
-- E (persona 物化接线): PersonaSubscriber outbox checkpoint (singleton, 仿 0022
-- common_ground_subscriber_checkpoint). Drives slow-channel persona rebuild on
-- statement.consolidated / statement.superseded.
CREATE TABLE persona_subscriber_checkpoint (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_processed_outbox_sequence INTEGER NOT NULL DEFAULT 0,
    last_updated_at TEXT NOT NULL
);
INSERT INTO persona_subscriber_checkpoint (id, last_processed_outbox_sequence, last_updated_at)
    VALUES (1, 0, '2026-07-01T00:00:00Z');
```

- [ ] **Step 2: Write the header** `include/starling/tom/persona_subscriber.hpp` (mirror common_ground_subscriber.hpp):

```cpp
#pragma once
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/connection.hpp"
#include <string_view>

namespace starling::tom {
class PersonaSubscriber {
public:
    [[nodiscard]] static int tick_one_batch(persistence::SqliteAdapter& adapter,
                                            persistence::Connection& conn,
                                            std::string_view now_iso,
                                            int batch_size = 100);
};
}  // namespace starling::tom
```

- [ ] **Step 3: Write the failing ctest** `tests/cpp/test_persona_subscriber.cpp`. Copy the `insert_statement` (25-column) + `insert_bus_event` helpers from `tests/cpp/test_common_ground_subscriber.cpp` (read that file for the exact helper bodies + column order). Then:

```cpp
// Seeds a consolidated+approved self-model anchor (holder==subject=="self"),
// a bus_events row event_type='statement.consolidated' primary_id=that stmt,
// runs the subscriber, asserts the persona materialized with the dimension.
TEST(PersonaSubscriber, ConsolidatedSelfAnchorMaterializesPersona) {
    auto adapter = persistence::SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    // holder==subject=="self", predicate="trait_curiosity", object="high",
    // consolidation_state="consolidated", review_status="approved":
    insert_statement(conn, /*id=*/"S1", /*tenant=*/"default", /*holder=*/"self",
                     /*subject=*/"self", /*predicate=*/"trait_curiosity",
                     /*object_value=*/"high", /*consolidation_state=*/"consolidated",
                     /*review_status=*/"approved");
    insert_bus_event(conn, /*event_type=*/"statement.consolidated",
                     /*primary_id=*/"S1", /*tenant=*/"default", /*seq=*/1);

    const int n = tom::PersonaSubscriber::tick_one_batch(*adapter, conn,
                                                         "2026-07-01T10:00:00Z");
    EXPECT_EQ(n, 1);

    const auto view = neocortex::PersonaContainer(*adapter)
                          .read(conn, "default", "self");
    EXPECT_TRUE(view.found);
    ASSERT_TRUE(view.dimensions.count("trait_curiosity"));
    EXPECT_EQ(view.dimensions.at("trait_curiosity"), "high");
}

TEST(PersonaSubscriber, ProfileAnchorClassifiedAndCheckpointAdvances) {
    auto adapter = persistence::SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    // holder="alice" != subject="bob" → profile_anchor about bob:
    insert_statement(conn, "S2", "default", "alice", "bob", "role", "engineer",
                     "consolidated", "approved");
    insert_bus_event(conn, "statement.consolidated", "S2", "default", 5);
    EXPECT_EQ(tom::PersonaSubscriber::tick_one_batch(*adapter, conn, "2026-07-01T10:00:00Z"), 1);
    // bob's persona materialized from the profile anchor:
    const auto view = neocortex::PersonaContainer(*adapter).read(conn, "default", "bob");
    EXPECT_TRUE(view.found);
    EXPECT_EQ(view.dimensions.at("role"), "engineer");
    // checkpoint advanced to 5; a second tick processes 0 new events:
    EXPECT_EQ(tom::PersonaSubscriber::tick_one_batch(*adapter, conn, "2026-07-01T10:05:00Z"), 0);
}

TEST(PersonaSubscriber, IgnoresUnconsolidatedAndUnapproved) {
    auto adapter = persistence::SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    // volatile (not consolidated) → not fed to persona even though the event fires:
    insert_statement(conn, "S3", "default", "self", "self", "trait_x", "y",
                     "volatile", "approved");
    insert_bus_event(conn, "statement.consolidated", "S3", "default", 2);
    tom::PersonaSubscriber::tick_one_batch(*adapter, conn, "2026-07-01T10:00:00Z");
    const auto view = neocortex::PersonaContainer(*adapter).read(conn, "default", "self");
    EXPECT_FALSE(view.found);  // no consolidated+approved anchor → nothing materialized
}
```

(If the CG test's `insert_statement` signature differs, adapt these calls to it — the point is: seed a consolidated+approved statement + a matching bus_events row, run the subscriber, assert the persona view. Match the real helper.)

- [ ] **Step 4: Register in CMake + build to confirm the test FAILS** (subscriber absent). Add `src/tom/persona_subscriber.cpp` to root `CMakeLists.txt` after line 120 (next to `src/tom/common_ground_subscriber.cpp`); add `test_persona_subscriber.cpp` to `tests/cpp/CMakeLists.txt` after line 114. Run `python scripts/configure_build.py --build`; then `.venv/bin/ctest --test-dir build-macos -R 'PersonaSubscriber'` → FAIL (link error / not implemented).

- [ ] **Step 5: Implement** `src/tom/persona_subscriber.cpp` (mirror common_ground_subscriber.cpp's idiom — `sqlite3_stmt* raw` + `StmtHandle` + `bind_sv`/`sqlite3_bind_int` + a `col` helper; identifiers ≥3 chars on new lines):

```cpp
#include "starling/tom/persona_subscriber.hpp"
#include "starling/neocortex/persona_container.hpp"
#include "starling/persistence/sqlite_helpers.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include <sqlite3.h>
#include <set>
#include <string>
#include <vector>

namespace starling::tom {
namespace {
using persistence::detail::bind_sv;
using persistence::detail::make_sqlite_error;
using persistence::StmtHandle;

std::string col_text(sqlite3_stmt* stmt, int idx) {
    const char* txt = reinterpret_cast<const char*>(sqlite3_column_text(stmt, idx));  // NOLINT(cppcoreguidelines-pro-type-reinterpret-cast) — mirrors common_ground_subscriber.cpp
    return txt ? txt : "";
}
}  // namespace

int PersonaSubscriber::tick_one_batch(persistence::SqliteAdapter& adapter,
                                      persistence::Connection& conn,
                                      std::string_view now_iso, int batch_size) {
    sqlite3* database = conn.raw();

    int last_seq = 0;
    {
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(database,
            "SELECT last_processed_outbox_sequence FROM persona_subscriber_checkpoint WHERE id=1",
            -1, &raw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(database, "persona_subscriber: read checkpoint");
        StmtHandle chk(raw);
        if (sqlite3_step(chk.get()) == SQLITE_ROW) last_seq = sqlite3_column_int(chk.get(), 0);
    }

    // New consolidation/supersession events since the checkpoint.
    struct Evt { std::string primary_id, tenant; int seq; };
    std::vector<Evt> events;
    int max_seq = last_seq;
    {
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(database,
            "SELECT primary_id, tenant_id, outbox_sequence FROM bus_events "
            "WHERE outbox_sequence > ? AND event_type IN "
            "('statement.consolidated','statement.superseded') "
            "ORDER BY outbox_sequence LIMIT ?", -1, &raw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(database, "persona_subscriber: read events");
        StmtHandle evq(raw);
        sqlite3_bind_int(evq.get(), 1, last_seq);
        sqlite3_bind_int(evq.get(), 2, batch_size);
        while (sqlite3_step(evq.get()) == SQLITE_ROW) {
            events.push_back({col_text(evq.get(), 0), col_text(evq.get(), 1),
                              sqlite3_column_int(evq.get(), 2)});
            max_seq = sqlite3_column_int(evq.get(), 2);
        }
    }

    // Resolve each event's statement → the SUBJECT it describes (the persona key).
    // Dedup affected (tenant, subject_id) so each persona rebuilds once per batch.
    std::set<std::pair<std::string, std::string>> affected;
    for (const auto& evt : events) {
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(database,
            "SELECT subject_id FROM statements WHERE id=? AND tenant_id=?",
            -1, &raw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(database, "persona_subscriber: resolve subject");
        StmtHandle sub(raw);
        bind_sv(sub.get(), 1, evt.primary_id);
        bind_sv(sub.get(), 2, evt.tenant);
        if (sqlite3_step(sub.get()) == SQLITE_ROW)
            affected.insert({evt.tenant, col_text(sub.get(), 0)});
    }

    // Rebuild each affected subject's persona from its consolidated+approved anchors.
    neocortex::PersonaContainer container(adapter);
    for (const auto& [tenant, subject] : affected) {
        std::vector<neocortex::AnchorStatement> sources;
        {
            sqlite3_stmt* raw = nullptr;
            if (sqlite3_prepare_v2(database,
                "SELECT id, holder_id, predicate, object_value, confidence FROM statements "
                "WHERE tenant_id=? AND subject_id=? AND consolidation_state='consolidated' "
                "AND review_status='approved'", -1, &raw, nullptr) != SQLITE_OK)
                throw make_sqlite_error(database, "persona_subscriber: read anchors");
            StmtHandle anc(raw);
            bind_sv(anc.get(), 1, tenant);
            bind_sv(anc.get(), 2, subject);
            while (sqlite3_step(anc.get()) == SQLITE_ROW) {
                const std::string holder = col_text(anc.get(), 1);
                sources.push_back(neocortex::AnchorStatement{
                    .stmt_id = col_text(anc.get(), 0),
                    .anchor_type = (holder == subject) ? "self_model_anchor" : "profile_anchor",
                    .dimension = col_text(anc.get(), 2),
                    .value = col_text(anc.get(), 3),
                    .confidence = sqlite3_column_double(anc.get(), 4),
                });
            }
        }
        if (sources.empty()) continue;  // event fired but no consolidated+approved anchor yet
        try {
            container.rebuild(conn, tenant, subject, sources, now_iso);
        } catch (const neocortex::ConcurrentRebuildError&) {
            // CAS lost to a concurrent rebuild; skip (CommonGround precedent).
        }
    }

    // Advance checkpoint (only if we saw events).
    if (!events.empty()) {
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(database,
            "UPDATE persona_subscriber_checkpoint SET last_processed_outbox_sequence=?, "
            "last_updated_at=? WHERE id=1", -1, &raw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(database, "persona_subscriber: advance checkpoint");
        StmtHandle upd(raw);
        sqlite3_bind_int(upd.get(), 1, max_seq);
        bind_sv(upd.get(), 2, now_iso);
        sqlite3_step(upd.get());
    }
    return static_cast<int>(events.size());
}
}  // namespace starling::tom
```

- [ ] **Step 6: Build + verify the ctest PASSES.** `python scripts/configure_build.py --build` then `.venv/bin/ctest --test-dir build-macos -R 'PersonaSubscriber' -V` → 3/3 pass. Then full `.venv/bin/ctest --test-dir build-macos` green.

- [ ] **Step 7: Full gate + commit.** `.venv/bin/python -m pytest tests/python -q` green. Commit:
  `feat(persona): PersonaSubscriber — rebuild persona on statement.consolidated/superseded`

---

## Task 2: SubscriberPump slot #8 + Python full-journey e2e

**Files:** Modify `src/bus/subscriber_pump.cpp`; Create `tests/python/test_persona_materialization.py`.

**Interfaces:**
- Consumes: `PersonaSubscriber::tick_one_batch` (Task 1); `run_isolated(conn, name, fn)` (SAVEPOINT-isolated); the public `Memory` API + `working_set`.

- [ ] **Step 1: Write the failing pytest** `tests/python/test_persona_materialization.py` (mirror `tests/python/test_dashboard_engine.py` fixtures + `test_m0_8_bindings.py` for how personas are read). The real-consumer proof:

```python
# Full journey: remember self-facts → tick (consolidates → emits statement.consolidated
# → the pump's PersonaSubscriber rebuilds self's persona) → working_set / recall shows
# the "## About me" block populated (empty before this slice).
def test_remember_then_tick_materializes_persona(tmp_path):
    from starling import Memory, make_stub_llm
    # canned self-model anchor: holder=self, subject=self (cog-self), a trait predicate:
    fake = make_stub_llm(default_response=(
        '[{"holder":"self","holder_perspective":"FIRST_PERSON",'
        '"subject":"self","predicate":"trait_curiosity","object":"high",'
        '"modality":"BELIEVES","polarity":"POS","nesting_depth":0}]'))
    mem = Memory.open(str(tmp_path / "persona.db"), agent="self",
                      tenant_id="default", llm=fake)
    mem.remember("I am deeply curious.", now="2026-07-01T00:00:00Z")
    # Drive ticks until consolidation happens + the persona subscriber runs:
    for _ in range(20):
        mem.tick("2026-07-01T00:05:00Z")
    # The persona is now materialized; recall context should carry the About-me block.
    # (Read via the public path the app uses — plan_query's context_pack, or a persona
    #  read helper if exposed. Assert the persona dimension shows up.)
    out = mem.query("what am I like", intent="FACT_LOOKUP", k=10)
    assert "trait_curiosity" in out["context_pack"] or "curious" in out["context_pack"].lower()
```

**VERIFY at impl time:** the exact public read path that surfaces the persona (the `## About me` block is built in `working_set.cpp`; confirm whether `Memory.query`/`recall`'s `context_pack` includes the working-set persona section, or whether a dedicated persona-read is needed — adjust the assertion to the real surfaced field). The non-negotiable proof: **before this slice the persona block is empty; after remember+tick it is populated.** If `context_pack` doesn't carry it, assert via whatever public API reads the working set / persona (do not weaken to a trivially-true assertion).

- [ ] **Step 2: Run it → verify it FAILS** (persona never materializes without the pump slot). `.venv/bin/python -m pytest tests/python/test_persona_materialization.py -v`.

- [ ] **Step 3: Register slot #8** in `src/bus/subscriber_pump.cpp`. Add the include after line 8 (`#include "starling/tom/common_ground_subscriber.hpp"`):

```cpp
#include "starling/tom/persona_subscriber.hpp"
```
Add slot #8 after the common_ground slot (after line 74, before the closing `}`):

```cpp
    // 8. persona — rebuild a subject's persona container on consolidation/supersession
    //    (slow channel; pump-slot only, NOT a tick_all stage — see plan Global Constraints).
    run_isolated(conn, "persona", [&]{
        starling::tom::PersonaSubscriber::tick_one_batch(adapter, conn, now_iso);
    });
```

- [ ] **Step 4: Rebuild + verify.** Binding surface unchanged, but the migration + C++ changed → `python scripts/configure_build.py --build --python-editable`. Run the new pytest → PASS. Then `.venv/bin/python -m pytest tests/python/test_load_test_p3c_smoke.py -v` → still green (persona is a pump slot, NOT a tick stage → `"persona" not in stage_timings_ms` holds). Then full `.venv/bin/python -m pytest tests/python` + full `.venv/bin/ctest --test-dir build-macos` green.

- [ ] **Step 5: Full gate + commit.**
  `feat(persona): wire PersonaSubscriber as SubscriberPump slot #8 — About-me populates live`

---

## Slice acceptance
`PersonaSubscriber` (SubscriberPump slot #8) rebuilds each affected subject's persona from consolidated+approved anchor statements on `statement.consolidated`/`statement.superseded` (spec slow channel), checkpoint-driven, SAVEPOINT-isolated, `ConcurrentRebuildError` swallowed. Migration 0030 adds the checkpoint. `working_set.read(agent_id)`'s `## About me` block populates in production (empty before). Isolated ctest (consolidated self-anchor materializes; profile-anchor classified; unconsolidated/unapproved ignored; checkpoint advances/idempotent) + Python full-journey e2e (remember→tick→persona populated). P3.c smoke unaffected (pump slot ≠ tick stage). Full ctest + pytest green. **c2.1 dimension-CAS stays deferred** (slow channel = low volume).

## Self-review
**Spec coverage:** trigger statement.consolidated+superseded (T1 event query) ✓; anchor scope consolidated+approved + classify (T1 anchor query) ✓; per-subject keying (T1 dedup by subject) ✓; migration 0030 (T1) ✓; pump slot #8 not tick stage (T2 + smoke re-check) ✓; swallow CAS (T1) ✓; real-consumer e2e (T2) ✓. **Placeholder scan:** real code + exact SQL + commands throughout; the T2 assertion has an explicit VERIFY (the surfaced persona field) with a no-weakening guard. **Type consistency:** `tick_one_batch(SqliteAdapter&, Connection&, string_view, int)->int`; `AnchorStatement{stmt_id,anchor_type,dimension,value,confidence}`; `PersonaView{found,dimensions}`; `rebuild(conn,tenant,holder,vector<AnchorStatement>,now_iso)` — all match the reference.

## Open questions for /plan-eng-review
- Confirm the T2 e2e's surfaced-persona assertion path (does `query`/`recall`'s `context_pack` include the working-set persona block, or is a dedicated read needed?). The outside-voice should empirically verify the About-me block populates end-to-end (this is the real-consumer proof — the same class of bug the last two eng-reviews caught).
- Confirm `insert_statement`/`insert_bus_event` helper signatures in `test_common_ground_subscriber.cpp` so the T1 test calls match.
- Confirm `statement.consolidated` fires at the volume the e2e's 20-tick loop assumes (online consolidation cadence) — else drive consolidation explicitly.
- Should PersonaSubscriber also process `statement.written` for faster self-model population, or strictly the slow channel? (Spec says slow; locked to consolidated+superseded.)

# Perception & Knowledge Tracking (sub-project B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn A's episodic events into per-cognizer perception → knowledge → (possibly stale) belief over one ledger, and expose a `what_does_X_think` query that answers ToMBench False-Belief and Knowledge end-to-end.

**Architecture:** A dedicated post-pass C++ `PerceptionReconstructor` scans all of a tenant's `OCCURRED` events on one `(observed_at, seq)` timeline, reconstructs a scene-global presence timeline (default-present; `enter`/`leave` override; tell recipients excluded from physical presence), and materialises, per cognizer, an append-only `perception_state` row per perceived state-event (single-owner `PerceptionStateStore`). A new 8th mentalizing primitive `what_does_X_think` reads the highest-position perceived state (vs `EpisodicEventStore::latest_event_location` for `is_stale`), with an `observer` path that intersects two cognizers' perceived sets for second-order. Four channels (presence / told / unexpected-contents / information-access) unify under "X's last-perceived state of theme T". B is purely additive on A — it does not touch A's `episodic_events`/`EpisodicEventStore`, the belief/ToM/conflict machinery, or `perceived_by_json`.

**Tech Stack:** C++20 (`src/cognizer/`, `src/tom/`, store in `src/store/`, `include/starling/`), SQLite migration (auto-registered by GLOB), pybind11, GoogleTest (one aggregated `starling_tests` exe + `gtest_discover_tests`), pytest. Spec: `docs/superpowers/specs/2026-06-18-perception-knowledge-tracking-design.md` (commit `fc56b8f`).

**Build/test (repo root `/Users/jaredguo-mini/develop/memory/starling`):**
- Build: `PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build`
- Single C++ test: `.venv/bin/ctest --test-dir build -R <Name> --output-on-failure`
- Full ctest: `.venv/bin/ctest --test-dir build --output-on-failure` (baseline **623**)
- Editable rebuild before pytest: add `--python-editable` to the configure_build line
- pytest: `.venv/bin/python -m pytest <file> -v` (baseline **619**)

**Hard constraints (apply to every task):** core logic C++ (Python only forwards/binds); new storage via migration (GLOB auto-register — no runner edit); reconstructor uses its own top-level `TransactionGuard` (post-pass; events already committed, so a failure can't roll them back) and `_memory_core` calls it best-effort (try/except); `perceived_by_json` immutable (never UPDATE; B uses append-only `perception_state`); **do not modify A's `episodic_events`/`EpisodicEventStore`**; reuse `KnowledgeFrontier`/`does_X_know`/`EpisodicEventStore`/the mentalizing-primitive pattern; every phase exit keeps ctest 623 / pytest 619 green (B is additive — new table + new reconstructor + new primitive + additive vocab; it must not touch A's OCCURRED-exclusion guards, the six-state machine, conflict arbitration, holder isolation, or belief/multi-order-ToM pins); TDD red→green→commit; explicit-path `git add` (never `.`/`-A`); no `--no-verify`/`--amend`; rebuild editable `_core` after C++/binding changes.

---

## File Structure

| File | Responsibility | Phase |
|------|----------------|-------|
| `migrations/0026_perception_state.sql` | `perception_state` append-only table (auto-registered) | 1 |
| `include/starling/store/perception_state_store.hpp` + `src/store/perception_state_store.cpp` | single-owner store: `upsert` (idempotent), `last_known`, `perceived_for_theme` | 1, 3 |
| `include/starling/cognizer/perception_reconstructor.hpp` + `src/cognizer/perception_reconstructor.cpp` | scan events → presence timeline → per-kind rules → write `perception_state` | 1, 2, 4, 5 |
| `include/starling/tom/mentalizing.hpp` (modify) + `src/tom/mentalizing_think.cpp` (create) | `StateBelief` POD + `what_does_X_think` primitive (1st/2nd order, location/content) | 1, 3, 4 |
| `bindings/python/bind_08_tom.cpp` (modify) | bind `StateBelief` + `what_does_X_think` | 1 |
| `bindings/python/bind_06_extractor.cpp` (modify — grep for `EpisodicExtractor` binding to confirm file) | bind `PerceptionReconstructor` | 1 |
| `python/starling/tom/primitives.py` + `python/starling/tom/__init__.py` (modify) | Pythonic wrapper + re-export of `what_does_X_think` | 1 |
| `python/starling/_memory_core.py` (modify) | forward to `PerceptionReconstructor` after the episodic pass (best-effort) | 1 |
| `include/starling/extractor/predicate_registry.hpp` (modify) | additive `kPerceptionPredicates` {tell, inform, see, look} + 3rd loop | 2, 4 |
| `python/starling/extractor/episodic_prompt.py` (modify) | additive tell (2) then see/open (4) extraction | 2, 4 |
| `tests/cpp/test_perception_state_store.cpp` | store CRUD + `last_known` | 1 |
| `tests/cpp/test_perception_reconstructor.cpp` | presence timeline + per-kind rules (Sally-Anne, tell, Smarties) | 1, 2, 4 |
| `tests/cpp/test_mentalizing_think.cpp` | `what_does_X_think` 1st/2nd order, `is_stale`, `has_belief` | 1, 3, 4 |
| `tests/cpp/CMakeLists.txt` (modify) | add the three test sources to `starling_tests` | 1 |
| `CMakeLists.txt` (modify) | add `perception_state_store.cpp` + `perception_reconstructor.cpp` + `mentalizing_think.cpp` to `starling_core` | 1 |
| `tests/python/test_perception_e2e.py` | stub-LLM deterministic + gated real-LLM e2e (Sally-Anne) | 1, 5 |
| `scripts/eval_perception_starling.py` | ToMBench False-Belief + Knowledge subset, Starling-in-the-loop | 5 |

**Module/namespace placement:** `PerceptionStateStore` → `starling::store` (mirrors `EpisodicEventStore`); `PerceptionReconstructor` → `starling::cognizer`; `what_does_X_think`/`StateBelief` → `starling::tom::mentalizing`.

---

## Phase 1 — Core first-order (location false belief)

Goal: Sally-Anne passes. `what_does_X_think(Sally, ball) = basket` (`is_stale=true`), `(Anne, ball) = box`, outsider `has_belief=false`.

### Task 1.1: migration `0026_perception_state.sql` + `PerceptionStateStore`

**Files:**
- Create: `migrations/0026_perception_state.sql`
- Create: `include/starling/store/perception_state_store.hpp`, `src/store/perception_state_store.cpp`
- Modify: `CMakeLists.txt` (add `src/store/perception_state_store.cpp` to the `starling_core` source list, next to `src/store/episodic_event_store.cpp` at line ~85)
- Test: `tests/cpp/test_perception_state_store.cpp`; `tests/cpp/CMakeLists.txt` (add the test source to `add_executable(starling_tests ...)`)

- [ ] **Step 1: Write the failing test** — `tests/cpp/test_perception_state_store.cpp`. Mirror how `tests/cpp/test_episodic_event_store.cpp` opens an in-memory adapter + runs migrations (read it for the exact `SqliteAdapter::open(":memory:")` + migration-apply boilerplate).

```cpp
#include "starling/store/perception_state_store.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>

using starling::store::PerceptionStateStore;
using starling::store::PerceptionStateRow;

namespace {
// Open an in-memory adapter with all migrations applied. Mirror the exact
// helper used at the top of tests/cpp/test_episodic_event_store.cpp.
starling::persistence::SqliteAdapter open_migrated();  // (copy the A-test helper)

PerceptionStateRow mk(const char* cog, const char* theme, const char* dim,
                      const char* val, const char* obs, long long pos, const char* ev) {
    PerceptionStateRow r;
    r.tenant_id = "t1"; r.cognizer_id = cog; r.theme_id = theme;
    r.state_dim = dim; r.state_value = val; r.observed_at = obs;
    r.position = pos; r.source_event_id = ev;
    return r;
}
}  // namespace

TEST(PerceptionStateStore, LastKnownPicksHighestPositionWithinAsOf) {
    auto adapter = open_migrated();
    PerceptionStateStore store(adapter.connection());
    store.upsert(mk("Sally", "ball", "location", "basket", "2026-01-01T00:00:00Z", 0, "e0"));
    store.upsert(mk("Sally", "ball", "location", "box",    "2026-01-02T00:00:00Z", 2, "e2"));

    auto now = store.last_known("t1", "Sally", "ball", "location", "2026-01-03T00:00:00Z");
    ASSERT_TRUE(now.has_value());
    EXPECT_EQ(now->state_value, "box");          // highest position
    EXPECT_EQ(now->source_event_id, "e2");

    // as_of in the past excludes the later row.
    auto past = store.last_known("t1", "Sally", "ball", "location", "2026-01-01T12:00:00Z");
    ASSERT_TRUE(past.has_value());
    EXPECT_EQ(past->state_value, "basket");

    // unknown cognizer → nullopt.
    EXPECT_FALSE(store.last_known("t1", "Nobody", "ball", "location", "2026-01-03T00:00:00Z").has_value());
}

TEST(PerceptionStateStore, UpsertIsIdempotentOnCognizerSourceEvent) {
    auto adapter = open_migrated();
    PerceptionStateStore store(adapter.connection());
    store.upsert(mk("Sally", "ball", "location", "basket", "2026-01-01T00:00:00Z", 0, "e0"));
    store.upsert(mk("Sally", "ball", "location", "basket", "2026-01-01T00:00:00Z", 0, "e0"));  // re-run
    auto r = store.last_known("t1", "Sally", "ball", "location", "2026-01-03T00:00:00Z");
    ASSERT_TRUE(r.has_value());
    EXPECT_EQ(r->state_value, "basket");  // one row, not two; no error
}
```

Add `test_perception_state_store.cpp` to the `add_executable(starling_tests ...)` source list in `tests/cpp/CMakeLists.txt` (alongside `test_episodic_event_store.cpp` at line ~144).

- [ ] **Step 2: Run → FAIL** (`no such file` / `PerceptionStateStore` undefined).

Run: `PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build` → expect compile error.

- [ ] **Step 3: Migration** — `migrations/0026_perception_state.sql` (mirror the `0025_episodic_events.sql` header/idempotency style; auto-registered by the CMake GLOB, no runner edit):

```sql
-- 0026: perception_state — per-cognizer last-known state of a theme (sub-project B).
-- Append-only: one row per (cognizer, perceived state-event). The PerceptionReconstructor
-- is the single writer; what_does_X_think reads the highest-position row with
-- observed_at <= as_of per (cognizer, theme, state_dim). observed_at (ingest time, the
-- as_of/order key) is used because A's episodic_events.event_time is nullable.
CREATE TABLE IF NOT EXISTS perception_state (
    tenant_id        TEXT NOT NULL,
    cognizer_id      TEXT NOT NULL,
    theme_id         TEXT NOT NULL,        -- statements.object_value (theme)
    state_dim        TEXT NOT NULL,        -- 'location' | 'content'
    state_value      TEXT NOT NULL,        -- e.g. 'basket'
    observed_at      TEXT NOT NULL,        -- ingest time; the as_of/order key
    position         INTEGER NOT NULL,     -- global event order index (tie-break within observed_at)
    source_event_id  TEXT NOT NULL,        -- the OCCURRED statement id this perception came from
    PRIMARY KEY (tenant_id, cognizer_id, source_event_id)
);
CREATE INDEX IF NOT EXISTS idx_perception_state_query
    ON perception_state(tenant_id, cognizer_id, theme_id, state_dim, position);
```

- [ ] **Step 4: Store header** — `include/starling/store/perception_state_store.hpp` (mirror `episodic_event_store.hpp` exactly — ctor takes `persistence::Connection&`):

```cpp
#pragma once
#include "starling/persistence/connection.hpp"
#include <optional>
#include <string>
#include <string_view>
#include <vector>
namespace starling::store {
struct PerceptionStateRow {
    std::string tenant_id, cognizer_id, theme_id, state_dim, state_value, observed_at;
    long long position = 0;
    std::string source_event_id;
};
class PerceptionStateStore {
public:
    explicit PerceptionStateStore(persistence::Connection& conn);
    // Idempotent on (tenant_id, cognizer_id, source_event_id).
    void upsert(const PerceptionStateRow& row);
    // Highest-position row with observed_at <= as_of for (cognizer, theme, dim); nullopt if none.
    std::optional<PerceptionStateRow> last_known(
        std::string_view tenant, std::string_view cognizer,
        std::string_view theme, std::string_view state_dim, std::string_view as_of);
    // All rows a cognizer perceived for a theme (any dim) with observed_at <= as_of, ordered by position.
    // (Used by the phase-3 observer intersection.)
    std::vector<PerceptionStateRow> perceived_for_theme(
        std::string_view tenant, std::string_view cognizer,
        std::string_view theme, std::string_view as_of);
private:
    persistence::Connection& conn_;
};
}  // namespace starling::store
```

- [ ] **Step 5: Store impl** — `src/store/perception_state_store.cpp` (mirror `episodic_event_store.cpp`: `StmtHandle`, `bind_sv`, `make_sqlite_error`, `read_row` helper):

```cpp
#include "starling/store/perception_state_store.hpp"
#include <sqlite3.h>
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/persistence/sqlite_helpers.hpp"
namespace starling::store {
using persistence::StmtHandle;
using persistence::detail::bind_sv;
using persistence::detail::make_sqlite_error;
namespace {
std::string col_text(sqlite3_stmt* s, int idx) {
    const auto* t = sqlite3_column_text(s, idx);
    return t ? reinterpret_cast<const char*>(t) : "";
}
// Column order aligns with the SELECT lists below.
PerceptionStateRow read_row(sqlite3_stmt* s) {
    PerceptionStateRow r;
    r.tenant_id = col_text(s, 0); r.cognizer_id = col_text(s, 1);
    r.theme_id = col_text(s, 2);  r.state_dim = col_text(s, 3);
    r.state_value = col_text(s, 4); r.observed_at = col_text(s, 5);
    r.position = sqlite3_column_int64(s, 6); r.source_event_id = col_text(s, 7);
    return r;
}
constexpr const char* kCols =
    "tenant_id,cognizer_id,theme_id,state_dim,state_value,observed_at,position,source_event_id";
}  // namespace

PerceptionStateStore::PerceptionStateStore(persistence::Connection& conn) : conn_(conn) {}

void PerceptionStateStore::upsert(const PerceptionStateRow& row) {
    sqlite3* db = conn_.raw();
    const char* sql =
        "INSERT INTO perception_state("
        "tenant_id,cognizer_id,theme_id,state_dim,state_value,observed_at,position,source_event_id"
        ") VALUES(?,?,?,?,?,?,?,?) "
        "ON CONFLICT(tenant_id,cognizer_id,source_event_id) DO UPDATE SET "
        "theme_id=excluded.theme_id, state_dim=excluded.state_dim, "
        "state_value=excluded.state_value, observed_at=excluded.observed_at, "
        "position=excluded.position";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "PerceptionStateStore::upsert prepare");
    StmtHandle h(raw);
    bind_sv(h.get(), 1, row.tenant_id);  bind_sv(h.get(), 2, row.cognizer_id);
    bind_sv(h.get(), 3, row.theme_id);   bind_sv(h.get(), 4, row.state_dim);
    bind_sv(h.get(), 5, row.state_value); bind_sv(h.get(), 6, row.observed_at);
    sqlite3_bind_int64(h.get(), 7, row.position);
    bind_sv(h.get(), 8, row.source_event_id);
    if (sqlite3_step(h.get()) != SQLITE_DONE)
        throw make_sqlite_error(db, "PerceptionStateStore::upsert step");
}

std::optional<PerceptionStateRow> PerceptionStateStore::last_known(
    std::string_view tenant, std::string_view cognizer,
    std::string_view theme, std::string_view state_dim, std::string_view as_of) {
    sqlite3* db = conn_.raw();
    const std::string sql = std::string("SELECT ") + kCols +
        " FROM perception_state WHERE tenant_id=? AND cognizer_id=? AND theme_id=? "
        "AND state_dim=? AND observed_at<=? ORDER BY position DESC LIMIT 1";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql.c_str(), -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "PerceptionStateStore::last_known prepare");
    StmtHandle h(raw);
    bind_sv(h.get(), 1, tenant); bind_sv(h.get(), 2, cognizer);
    bind_sv(h.get(), 3, theme);  bind_sv(h.get(), 4, state_dim); bind_sv(h.get(), 5, as_of);
    const int rc = sqlite3_step(h.get());
    if (rc == SQLITE_ROW) return read_row(h.get());
    if (rc == SQLITE_DONE) return std::nullopt;
    throw make_sqlite_error(db, "PerceptionStateStore::last_known step");
}

std::vector<PerceptionStateRow> PerceptionStateStore::perceived_for_theme(
    std::string_view tenant, std::string_view cognizer,
    std::string_view theme, std::string_view as_of) {
    sqlite3* db = conn_.raw();
    const std::string sql = std::string("SELECT ") + kCols +
        " FROM perception_state WHERE tenant_id=? AND cognizer_id=? AND theme_id=? "
        "AND observed_at<=? ORDER BY position";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql.c_str(), -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "PerceptionStateStore::perceived_for_theme prepare");
    StmtHandle h(raw);
    bind_sv(h.get(), 1, tenant); bind_sv(h.get(), 2, cognizer);
    bind_sv(h.get(), 3, theme);  bind_sv(h.get(), 4, as_of);
    std::vector<PerceptionStateRow> out;
    int rc;
    while ((rc = sqlite3_step(h.get())) == SQLITE_ROW) out.push_back(read_row(h.get()));
    if (rc != SQLITE_DONE)
        throw make_sqlite_error(db, "PerceptionStateStore::perceived_for_theme step");
    return out;
}
}  // namespace starling::store
```

Add `src/store/perception_state_store.cpp` to the `starling_core` `add_library` list in `CMakeLists.txt` (one line beside `src/store/episodic_event_store.cpp`).

- [ ] **Step 6: Run → PASS** (build + `ctest -R PerceptionStateStore`), then **full ctest 623** stays green.

Run: `PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build && .venv/bin/ctest --test-dir build -R PerceptionStateStore --output-on-failure`

- [ ] **Step 7: Commit**

```bash
git add migrations/0026_perception_state.sql include/starling/store/perception_state_store.hpp src/store/perception_state_store.cpp CMakeLists.txt tests/cpp/test_perception_state_store.cpp tests/cpp/CMakeLists.txt
git commit -F - <<'EOF'
feat(store): perception_state table + PerceptionStateStore (sub-project B)

Append-only per-cognizer last-known state; observed_at as_of key (A's
event_time is nullable); idempotent on (tenant,cognizer,source_event_id).

EOF
```

### Task 1.2: `PerceptionReconstructor` (presence timeline → location perception)

**Files:**
- Create: `include/starling/cognizer/perception_reconstructor.hpp`, `src/cognizer/perception_reconstructor.cpp`
- Modify: `CMakeLists.txt` (add `src/cognizer/perception_reconstructor.cpp` near `src/cognizer/knowledge_frontier.cpp` line ~111)
- Test: `tests/cpp/test_perception_reconstructor.cpp` (+ add to `tests/cpp/CMakeLists.txt`)

- [ ] **Step 1: Write the failing test** — seed 3 OCCURRED events (put/leave/move) **by mirroring the seed pattern in `tests/cpp/test_episodic_extractor.cpp`** (it already writes OCCURRED statements via `StatementWriter` + `EpisodicEventStore::upsert`; read it and copy its seed helper). Then run the reconstructor and assert `perception_state` via `PerceptionStateStore`:

```cpp
#include "starling/cognizer/perception_reconstructor.hpp"
#include "starling/store/perception_state_store.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>

using starling::cognizer::PerceptionReconstructor;
using starling::store::PerceptionStateStore;

namespace {
// Seed an OCCURRED event = one statements row (modality='occurred', subject_id=actor,
// predicate=action, object_value=theme, observed_at) + one episodic_events row
// (seq, location, participants_json). COPY the exact seeding helper from
// tests/cpp/test_episodic_extractor.cpp (StatementWriter + EpisodicEventStore::upsert).
void seed_event(starling::persistence::SqliteAdapter& a, const char* tenant,
                const char* stmt_id, const char* actor, const char* action,
                const char* theme, const char* location, const char* participants_json,
                long long seq, const char* observed_at);  // (copy from A test)
}  // namespace

TEST(PerceptionReconstructor, SallyAnneLocationPresence) {
    auto a = /* open_migrated() — copy the A-test helper */;
    const char* T = "t1";
    seed_event(a, T, "e0", "Sally", "put",  "ball", "basket", R"(["Sally"])", 1, "2026-01-01T00:00:01Z");
    seed_event(a, T, "e1", "Sally", "leave", "room", "",       R"(["Sally"])", 2, "2026-01-01T00:00:02Z");
    seed_event(a, T, "e2", "Anne",  "move", "ball", "box",    R"(["Anne"])",  3, "2026-01-01T00:00:03Z");

    PerceptionReconstructor recon(a.connection());
    recon.reconstruct(T);

    PerceptionStateStore ps(a.connection());
    const char* AS_OF = "2026-01-02T00:00:00Z";
    // Sally saw the put (default-present) but LEFT before the move → basket.
    auto sally = ps.last_known(T, "Sally", "ball", "location", AS_OF);
    ASSERT_TRUE(sally.has_value());
    EXPECT_EQ(sally->state_value, "basket");
    // Anne was present throughout → box (and earlier basket, but box is later).
    auto anne = ps.last_known(T, "Anne", "ball", "location", AS_OF);
    ASSERT_TRUE(anne.has_value());
    EXPECT_EQ(anne->state_value, "box");
}
```

- [ ] **Step 2: Run → FAIL** (`PerceptionReconstructor` undefined).

- [ ] **Step 3: Header** — `include/starling/cognizer/perception_reconstructor.hpp`:

```cpp
#pragma once
#include "starling/persistence/connection.hpp"
#include <string_view>
namespace starling::cognizer {
// Post-pass: recompute per-cognizer perception for a tenant from ALL its OCCURRED
// events. Idempotent (upserts). Runs in its own transaction after the episodic pass.
class PerceptionReconstructor {
public:
    explicit PerceptionReconstructor(persistence::Connection& conn);
    void reconstruct(std::string_view tenant);
private:
    persistence::Connection& conn_;
};
}  // namespace starling::cognizer
```

- [ ] **Step 4: Impl** — `src/cognizer/perception_reconstructor.cpp`. Scene-wide scan (NOT `events_for_theme` — presence needs the `leave`, which is not a ball event); default-present cast; `enter`/`leave` override; actor+participants present at their own event; physical witnesses learn the resulting location. Mirror `episodic_extractor.cpp:95`'s `persistence::TransactionGuard tx(conn_)` usage (same RAII commit semantics — read it to match `.commit()` if explicit):

```cpp
#include "starling/cognizer/perception_reconstructor.hpp"
#include "starling/store/perception_state_store.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/persistence/sqlite_helpers.hpp"
#include "starling/persistence/transaction_guard.hpp"
#include <sqlite3.h>
#include <nlohmann/json.hpp>
#include <set>
#include <string>
#include <vector>
namespace starling::cognizer {
namespace {
struct ScanEvent {
    std::string stmt_id, actor, predicate, theme, observed_at, location, participants_json;
    long long seq = 0;
};
bool is_leave(const std::string& p) { return p == "leave" || p == "exit" || p == "depart"; }
bool is_enter(const std::string& p) { return p == "enter" || p == "return" || p == "arrive"; }
bool is_presence_change(const std::string& p) { return is_leave(p) || is_enter(p); }
// phase 2 will add: is_tell(p) → excluded from the physical cast.
std::vector<std::string> participants_of(const ScanEvent& ev) {
    std::vector<std::string> ps;
    if (!ev.actor.empty()) ps.push_back(ev.actor);
    if (!ev.participants_json.empty()) {
        auto j = nlohmann::json::parse(ev.participants_json, nullptr, /*allow_exceptions=*/false);
        if (j.is_array()) for (auto& p : j) if (p.is_string()) ps.push_back(p.get<std::string>());
    }
    return ps;
}
}  // namespace

PerceptionReconstructor::PerceptionReconstructor(persistence::Connection& conn) : conn_(conn) {}

void PerceptionReconstructor::reconstruct(std::string_view tenant) {
    sqlite3* db = conn_.raw();
    // 1. Scan ALL OCCURRED events for the tenant on one timeline (observed_at, seq).
    const char* sql =
        "SELECT s.id, s.subject_id, s.predicate, s.object_value, s.observed_at, "
        "e.seq, e.location, e.participants_json "
        "FROM statements s JOIN episodic_events e "
        "ON e.statement_id=s.id AND e.tenant_id=s.tenant_id "
        "WHERE s.tenant_id=? AND s.modality='occurred' "
        "ORDER BY s.observed_at, e.seq";
    std::vector<ScanEvent> events;
    {
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK)
            throw persistence::detail::make_sqlite_error(db, "PerceptionReconstructor scan prepare");
        persistence::StmtHandle h(raw);
        persistence::detail::bind_sv(h.get(), 1, tenant);
        auto col = [&](int i) {
            const auto* t = sqlite3_column_text(h.get(), i);
            return t ? std::string(reinterpret_cast<const char*>(t)) : std::string();
        };
        int rc;
        while ((rc = sqlite3_step(h.get())) == SQLITE_ROW) {
            ScanEvent ev;
            ev.stmt_id = col(0); ev.actor = col(1); ev.predicate = col(2); ev.theme = col(3);
            ev.observed_at = col(4); ev.seq = sqlite3_column_int64(h.get(), 5);
            ev.location = col(6); ev.participants_json = col(7);
            events.push_back(std::move(ev));
        }
        if (rc != SQLITE_DONE)
            throw persistence::detail::make_sqlite_error(db, "PerceptionReconstructor scan step");
    }
    if (events.empty()) return;

    // 2. Physical cast = everyone named in a physical / presence-change event.
    //    (phase 2 will skip tell-only cognizers here.)
    std::set<std::string> cast;
    for (const auto& ev : events) for (const auto& p : participants_of(ev)) cast.insert(p);

    // 3. Walk events; present set defaults to the whole cast; enter/leave override;
    //    physical witnesses (present ∪ this event's actor/participants) learn the location.
    store::PerceptionStateStore ps(conn_);
    persistence::TransactionGuard tx(conn_);  // own top-level tx (events already committed)
    std::set<std::string> present(cast.begin(), cast.end());
    long long position = 0;
    for (const auto& ev : events) {
        const auto evp = participants_of(ev);
        std::set<std::string> witnesses(present.begin(), present.end());
        for (const auto& p : evp) witnesses.insert(p);  // actor/participants present at their event
        if (is_presence_change(ev.predicate)) {
            if (is_leave(ev.predicate)) for (const auto& p : evp) present.erase(p);   // gone AFTER this
            else                        for (const auto& p : evp) present.insert(p);  // here from now
        } else if (!ev.location.empty()) {  // physical location event
            for (const auto& w : witnesses) {
                store::PerceptionStateRow row;
                row.tenant_id = std::string(tenant); row.cognizer_id = w;
                row.theme_id = ev.theme; row.state_dim = "location"; row.state_value = ev.location;
                row.observed_at = ev.observed_at; row.position = position; row.source_event_id = ev.stmt_id;
                ps.upsert(row);
            }
        }
        ++position;
    }
    tx.commit();  // (omit if TransactionGuard auto-commits on dtor — match episodic_extractor.cpp)
}
}  // namespace starling::cognizer
```

Add `src/cognizer/perception_reconstructor.cpp` to `starling_core` in `CMakeLists.txt`.

- [ ] **Step 5: Run → PASS** (`ctest -R PerceptionReconstructor`), full ctest 623 green.

- [ ] **Step 6: Commit**

```bash
git add include/starling/cognizer/perception_reconstructor.hpp src/cognizer/perception_reconstructor.cpp CMakeLists.txt tests/cpp/test_perception_reconstructor.cpp tests/cpp/CMakeLists.txt
git commit -F - <<'EOF'
feat(cognizer): PerceptionReconstructor — scene presence → location perception (B)

Scene-wide scan over all tenant OCCURRED events ordered (observed_at, seq);
default-present cast with enter/leave override; physical witnesses learn the
resulting location into perception_state.

EOF
```

### Task 1.3: `what_does_X_think` primitive + binding + Python wrapper

**Files:**
- Modify: `include/starling/tom/mentalizing.hpp` (add `StateBelief` + `what_does_X_think` decl)
- Create: `src/tom/mentalizing_think.cpp`; Modify: `CMakeLists.txt` (add to `starling_core` near `src/tom/mentalizing_know.cpp` ~line 124)
- Modify: `bindings/python/bind_08_tom.cpp`, `python/starling/tom/primitives.py`, `python/starling/tom/__init__.py`
- Test: `tests/cpp/test_mentalizing_think.cpp` (+ `tests/cpp/CMakeLists.txt`)

- [ ] **Step 1: Write the failing test** — `tests/cpp/test_mentalizing_think.cpp`: seed `perception_state` (via `PerceptionStateStore`) + the ground-truth `episodic_events`/`statements` (so `latest_event_location` returns box), call `what_does_X_think`, assert. (Seed events with the same helper as Task 1.2.)

```cpp
TEST(WhatDoesXThink, FirstOrderStaleAndFresh) {
    auto a = /* open_migrated() */;
    const char* T = "t1";
    // ground truth: ball ends in box (seed put@basket then move@box like Task 1.2)
    // + perception_state: Sally saw basket(pos0), Anne saw basket(pos0)+box(pos2).
    /* seed via seed_event + PerceptionReconstructor.reconstruct(T), or directly */
    starling::cognizer::KnowledgeFrontier frontier(a);

    auto sally = starling::tom::mentalizing::what_does_X_think(
        a, frontier, "Sally", "ball", T, "2026-01-02T00:00:00Z");
    EXPECT_TRUE(sally.has_belief);
    EXPECT_EQ(sally.state_value, "basket");
    EXPECT_TRUE(sally.is_stale);            // basket != ground-truth box

    auto anne = starling::tom::mentalizing::what_does_X_think(
        a, frontier, "Anne", "ball", T, "2026-01-02T00:00:00Z");
    EXPECT_EQ(anne.state_value, "box");
    EXPECT_FALSE(anne.is_stale);

    auto nobody = starling::tom::mentalizing::what_does_X_think(
        a, frontier, "Charlie", "ball", T, "2026-01-02T00:00:00Z");
    EXPECT_FALSE(nobody.has_belief);        // never perceived → unknown
}
```

- [ ] **Step 2: Run → FAIL**.

- [ ] **Step 3: Header** — add to `include/starling/tom/mentalizing.hpp` (after the existing PODs):

```cpp
// X's last-perceived state of a theme (sub-project B). has_belief=false → X never
// perceived any state-event for the theme.
struct StateBelief {
    bool has_belief = false;
    std::string state_dim;       // "location" | "content"
    std::string state_value;
    std::string source_event_id;
    bool is_stale = false;       // state_value != global latest actual state
};

// 8. First/second-order: X's last-perceived state of `theme`. observer="" → first
//    order; observer set → restrict to events both observer and x perceived.
StateBelief what_does_X_think(
    persistence::SqliteAdapter& adapter,
    cognizer::KnowledgeFrontier& frontier,
    std::string_view x,
    std::string_view theme,
    std::string_view tenant,
    std::string_view as_of,
    std::string_view observer = "");
```

- [ ] **Step 4: Impl** — `src/tom/mentalizing_think.cpp` (phase 1: location dim, first-order only; phase 3 adds the `observer` branch, phase 4 adds dim inference):

```cpp
#include "starling/tom/mentalizing.hpp"
#include "starling/store/perception_state_store.hpp"
#include "starling/store/episodic_event_store.hpp"
namespace starling::tom::mentalizing {
StateBelief what_does_X_think(
    persistence::SqliteAdapter& adapter,
    cognizer::KnowledgeFrontier& frontier,
    std::string_view x, std::string_view theme,
    std::string_view tenant, std::string_view as_of,
    std::string_view observer) {
    (void)frontier;  // reserved for does_X_know-aligned access checks (phase 5)
    auto& conn = adapter.connection();
    store::PerceptionStateStore ps(conn);
    StateBelief out;
    // phase 1: location dimension only (phase 4 infers content vs location from the theme's events).
    const std::string dim = "location";
    std::optional<store::PerceptionStateRow> row;
    if (observer.empty()) {
        row = ps.last_known(tenant, x, theme, dim, as_of);   // first-order
    } else {
        // phase 3 replaces this with the observer∩x intersection.
        row = ps.last_known(tenant, x, theme, dim, as_of);
    }
    if (!row) return out;  // has_belief stays false
    out.has_belief = true;
    out.state_dim = row->state_dim;
    out.state_value = row->state_value;
    out.source_event_id = row->source_event_id;
    store::EpisodicEventStore ep(conn);
    const std::string truth = ep.latest_event_location(tenant, theme);
    out.is_stale = (!truth.empty() && truth != out.state_value);
    return out;
}
}  // namespace starling::tom::mentalizing
```

Add `src/tom/mentalizing_think.cpp` to `starling_core` in `CMakeLists.txt`.

- [ ] **Step 5: Binding** — in `bindings/python/bind_08_tom.cpp`, add the `StateBelief` class (mirror the `NestedBelief` read-only pattern) and the `what_does_X_think` free function (mirror the `does_X_know` lambda):

```cpp
    py::class_<starling::tom::mentalizing::StateBelief>(m, "StateBelief")
        .def_readonly("has_belief",      &starling::tom::mentalizing::StateBelief::has_belief)
        .def_readonly("state_dim",       &starling::tom::mentalizing::StateBelief::state_dim)
        .def_readonly("state_value",     &starling::tom::mentalizing::StateBelief::state_value)
        .def_readonly("source_event_id", &starling::tom::mentalizing::StateBelief::source_event_id)
        .def_readonly("is_stale",        &starling::tom::mentalizing::StateBelief::is_stale);

    m.def("what_does_X_think",
        [](starling::persistence::SqliteAdapter& adapter,
           starling::cognizer::KnowledgeFrontier& frontier,
           const std::string& x, const std::string& theme,
           const std::string& tenant, const std::string& as_of,
           const std::string& observer) {
            return starling::tom::mentalizing::what_does_X_think(
                adapter, frontier, x, theme, tenant, as_of, observer);
        },
        py::arg("adapter"), py::arg("frontier"), py::arg("x"), py::arg("theme"),
        py::arg("tenant"), py::arg("as_of"), py::arg("observer") = "",
        "First/second-order: X's last-perceived state of a theme (possibly stale).");
```

- [ ] **Step 6: Python wrapper + re-export** — add to `python/starling/tom/primitives.py` (mirror the `does_X_know` shim) and `python/starling/tom/__init__.py` (`StateBelief` from `starling._core`; `what_does_X_think` from `starling.tom.primitives`; add both to `__all__`):

```python
# primitives.py
def what_does_X_think(adapter, frontier, *, x, theme, tenant_id="default",
                      as_of=None, observer=""):
    as_of_iso = _iso_now_or_convert(as_of)
    return _core.what_does_X_think(adapter, frontier, x, theme, tenant_id, as_of_iso, observer)
```

- [ ] **Step 7: Rebuild editable + run** — `… configure_build.py --build --python-editable --build-dir build`, then `ctest -R WhatDoesXThink` (C++) PASS; full ctest 623 green.

- [ ] **Step 8: Commit**

```bash
git add include/starling/tom/mentalizing.hpp src/tom/mentalizing_think.cpp CMakeLists.txt bindings/python/bind_08_tom.cpp python/starling/tom/primitives.py python/starling/tom/__init__.py tests/cpp/test_mentalizing_think.cpp tests/cpp/CMakeLists.txt
git commit -F - <<'EOF'
feat(tom): what_does_X_think — 8th mentalizing primitive (B, first-order)

StateBelief{has_belief,state_dim,state_value,source_event_id,is_stale}; reads
perception_state last_known vs EpisodicEventStore.latest_event_location for
is_stale; has_belief=false when X never perceived the theme.

EOF
```

### Task 1.4: wire `PerceptionReconstructor` into `remember` + deterministic pytest e2e

**Files:**
- Modify: `bindings/python/bind_06_extractor.cpp` (grep for the `EpisodicExtractor` `py::class_` to confirm the file; bind `PerceptionReconstructor` next to it)
- Modify: `python/starling/_memory_core.py` (forward to the reconstructor after the episodic pass, best-effort)
- Test: `tests/python/test_perception_e2e.py`

- [ ] **Step 1: Bind `PerceptionReconstructor`** — mirror the `EpisodicExtractor` binding (ctor over `Connection&` + `keep_alive`):

```cpp
    py::class_<starling::cognizer::PerceptionReconstructor>(m, "PerceptionReconstructor")
        .def(py::init<starling::persistence::Connection&>(), py::arg("conn"), py::keep_alive<1, 2>())
        .def("reconstruct",
            [](starling::cognizer::PerceptionReconstructor& self, const std::string& tenant) {
                self.reconstruct(tenant);
            },
            py::arg("tenant"));
```

- [ ] **Step 2: Write the failing pytest** — `tests/python/test_perception_e2e.py`. A stub LLM returning the canned 3-event JSON drives a deterministic remember→A→B (the claim pass gets the event-JSON and extracts nothing — graceful — while the episodic pass extracts the 3 events):

```python
import json, starling
from starling.tom import what_does_X_think

_CANNED = json.dumps([
    {"actor":"Sally","action":"put","theme":"ball","location":"basket","participants":["Sally"],"time":None},
    {"actor":"Sally","action":"leave","theme":"room","location":None,"participants":["Sally"],"time":None},
    {"actor":"Anne","action":"move","theme":"ball","location":"box","participants":["Anne"],"time":None},
])

def test_sally_anne_false_belief_deterministic(tmp_path):
    mem = starling.Memory.open(str(tmp_path/"m.db"), agent="narrator",
                               llm=starling.make_stub_llm(default_response=_CANNED))
    mem.remember("Sally puts her ball in the basket and leaves. Anne moves it to the box.")
    frontier = starling.KnowledgeFrontier(mem.rt.adapter)  # confirm exact accessor
    sally = what_does_X_think(mem.rt.adapter, frontier, x="Sally", theme="ball", tenant_id=mem.tenant)
    assert sally.has_belief and sally.state_value == "basket" and sally.is_stale
    anne = what_does_X_think(mem.rt.adapter, frontier, x="Anne", theme="ball", tenant_id=mem.tenant)
    assert anne.state_value == "box" and not anne.is_stale
```

- [ ] **Step 3: Run → FAIL** (reconstructor not wired → no `perception_state` → `has_belief=false`).

- [ ] **Step 4: Wire `remember`** — in `python/starling/_memory_core.py`, inside the existing `if engram_ref:` block, after the `EpisodicExtractor` `event_ids` are written, forward to the reconstructor best-effort (failure must never fail `remember`):

```python
            if event_ids:
                out["statement_ids"] = list(out.get("statement_ids", [])) + list(event_ids)
                # sub-project B: rebuild per-cognizer perception from the events (best-effort).
                try:
                    _core.PerceptionReconstructor(self.conn).reconstruct(tenant=self.tenant)
                except Exception:  # noqa: BLE001 — perception is best-effort; never fail remember
                    pass
```

- [ ] **Step 5: Rebuild editable + run → PASS** — `… --python-editable …`, then `.venv/bin/python -m pytest tests/python/test_perception_e2e.py -v`; full pytest 619 + ctest 623 green.

- [ ] **Step 6: Commit**

```bash
git add bindings/python/bind_06_extractor.cpp python/starling/_memory_core.py tests/python/test_perception_e2e.py
git commit -F - <<'EOF'
feat(memory): wire PerceptionReconstructor into remember (B, best-effort)

Deterministic stub-LLM e2e: Sally-Anne false belief end-to-end
(what_does_X_think(Sally,ball)=basket/stale, (Anne,ball)=box).

EOF
```

---

## Phase 2 — Told channel (`tell`/`inform`)

Goal: "Sally tells Anne the ball is in the box" → Anne's last-known = box without Anne being physically present; tell does NOT add Anne/Sally to the physical-presence cast (fixes N1).

### Task 2.1: action vocab + episodic prompt for `tell`

**Files:** Modify `include/starling/extractor/predicate_registry.hpp`; `python/starling/extractor/episodic_prompt.py`.

- [ ] **Step 1:** `predicate_registry.hpp` — the existing arrays are fixed-size `std::array<…, 10>`; **add a new array** (do not resize the others) + a third loop in `is_core_predicate`:

```cpp
// Informational/perception predicate class (sub-project B): speech + perception
// verbs that update a cognizer's knowledge. tell/inform convey a state to a
// recipient; see/look (phase 4) read a container's apparent content.
inline constexpr std::array<std::string_view, 4> kPerceptionPredicates = {
    "tell", "inform", "see", "look",
};
```
Add to `is_core_predicate`: `for (const auto p : kPerceptionPredicates) if (p == predicate) return true;`.

- [ ] **Step 2:** `episodic_prompt.py` — additive: extend the `action` PREFER list with `tell, inform`, add a tell field convention (the conveyed state goes in `theme` + `location`; the recipient is the non-actor participant), and add a WORKED EXAMPLE:

```
WORKED EXAMPLE 3 (being told):
Passage:
  Anne is in the kitchen. Sally calls Anne and tells her the ball is now in the box.
JSON array:
[
  {"actor":"Sally","action":"tell","theme":"ball","location":"box","participants":["Sally","Anne"],"time":null}
]
(A "tell" conveys a state about a theme: theme=ball, location=box. participants lists
the teller first then the recipient(s). The recipient learns the state WITHOUT being
in the room — tell does not imply physical co-location.)
```

- [ ] **Step 3:** Document the convention in the prompt's RULES: "for tell/inform, participants = [teller, recipient...]; theme+location carry the conveyed state." Commit (prompt is `str.replace` of `{passage}` — no format escaping).

### Task 2.2: reconstructor `tell` rule + exclude tell from physical cast

**Files:** Modify `src/cognizer/perception_reconstructor.cpp`; Test `tests/cpp/test_perception_reconstructor.cpp` (add a tell case).

- [ ] **Step 1: Failing test** — seed put(basket)@Sally, move(box)@Anne, then `tell(ball,box)` actor=Carol participants=[Carol,Dave] where **Dave is named only in the tell**. Assert: `what_does_X_think(Dave, ball)` via `last_known` = box (told), and Dave is NOT credited as a physical witness of the put/move (he has exactly one perception row, from the tell). Also assert a physical-only outsider stays `has_belief=false`.

- [ ] **Step 2: Impl** — add `is_tell(p)` (`tell`/`inform`); (a) exclude tell-only cognizers from the physical cast: when building `cast`, skip participants contributed *solely* by tell events (compute the physical cast from non-tell events; track tell recipients separately); (b) add a tell branch in the walk: recipient(s) = `participants_of(ev)` minus the teller (`ev.actor`) → write `perception_state(recipient, theme=ev.theme, dim="location", value=ev.location, …)` regardless of presence. Key code:

```cpp
bool is_tell(const std::string& p) { return p == "tell" || p == "inform"; }
// cast: physical events only
std::set<std::string> cast;
for (const auto& ev : events) {
    if (is_tell(ev.predicate)) continue;          // tell does not establish physical presence (N1)
    for (const auto& p : participants_of(ev)) cast.insert(p);
}
// in the walk, before the physical branch:
if (is_tell(ev.predicate)) {
    const auto evp = participants_of(ev);  // [teller, recipient...]
    for (size_t i = 1; i < evp.size(); ++i) {     // skip teller at index 0
        if (ev.location.empty()) continue;
        store::PerceptionStateRow row;
        row.tenant_id = std::string(tenant); row.cognizer_id = evp[i];
        row.theme_id = ev.theme; row.state_dim = "location"; row.state_value = ev.location;
        row.observed_at = ev.observed_at; row.position = position; row.source_event_id = ev.stmt_id;
        ps.upsert(row);
    }
    ++position; continue;  // tell is not a presence change and not a physical witnessing
}
```

- [ ] **Step 3: PASS**, full ctest 623, commit.

---

## Phase 3 — Second-order via perception intersection (`observer`)

Goal: `what_does_X_think(Sally, ball, observer=Anne)` = basket (Anne knows Sally left before the move). Derived by intersecting Anne's and Sally's perceived sets — no new storage (fixes N5).

### Task 3.1: `observer` branch in `what_does_X_think`

**Files:** Modify `src/tom/mentalizing_think.cpp`; Test `tests/cpp/test_mentalizing_think.cpp`.

- [ ] **Step 1: Failing test** — seed Sally-Anne (Task 1.2). Assert `what_does_X_think(adapter, frontier, "Sally", "ball", T, AS_OF, "Anne") == basket` (Anne's model of Sally), while first-order `what_does_X_think(…, "Anne", …)` stays box.

- [ ] **Step 2: Impl** — replace the phase-1 `observer` placeholder with an intersection over `perceived_for_theme` (Task 1.1 store method): the candidate set is the events BOTH `observer` and `x` perceived for the theme; take the highest-position member:

```cpp
    if (observer.empty()) {
        row = ps.last_known(tenant, x, theme, dim, as_of);
    } else {
        // observer's model of x: events both perceived (single-scene co-presence).
        auto x_rows  = ps.perceived_for_theme(tenant, x, theme, as_of);
        auto obs_rows = ps.perceived_for_theme(tenant, observer, theme, as_of);
        std::unordered_set<std::string> obs_events;
        for (const auto& r : obs_rows) obs_events.insert(r.source_event_id);
        for (auto it = x_rows.rbegin(); it != x_rows.rend(); ++it) {  // highest position first
            if (it->state_dim == dim && obs_events.count(it->source_event_id)) { row = *it; break; }
        }
    }
```
(Add `#include <unordered_set>`.)

- [ ] **Step 3: PASS**, full ctest 623, commit.

---

## Phase 4 — Unexpected contents (apparent vs actual)

Goal: "Anne sees a closed Smarties tube (really pencils)" → `what_does_X_think(Anne, tube)` = Smarties (`state_dim=content`, `is_stale=true` vs actual pencils). Highest extraction risk — isolated last.

### Task 4.1: action vocab + prompt for `see`/`open` content

**Files:** `predicate_registry.hpp` already has `see`/`look` from Task 2.1 (and `open`/`close` from A). Modify `python/starling/extractor/episodic_prompt.py`.

- [ ] **Step 1:** Add a content convention + WORKED EXAMPLE to the prompt: a `see`/`look` of a closed labelled container emits the **apparent** content; an `open`/`reveal` emits the **actual** content; both carry the content value in `location` (the generic state slot) with the container as `theme`:

```
WORKED EXAMPLE 4 (unexpected contents):
Passage:
  Anne sees a closed Smarties tube. Tom opens it; it actually contains pencils.
JSON array:
[
  {"actor":"Anne","action":"see","theme":"Smarties tube","location":"Smarties","participants":["Anne"],"time":null},
  {"actor":"Tom","action":"open","theme":"Smarties tube","location":"pencils","participants":["Tom"],"time":null}
]
(For a closed labelled container, "see" records the APPARENT content from the label
(location="Smarties"); "open"/"reveal" records the ACTUAL content (location="pencils").)
```

- [ ] **Step 2:** Commit prompt change.

### Task 4.2: reconstructor content rules + `what_does_X_think` dim inference

**Files:** Modify `src/cognizer/perception_reconstructor.cpp`, `src/tom/mentalizing_think.cpp`, `include/starling/store/perception_state_store.hpp`+`.cpp` (add a ground-truth-content helper); Test `tests/cpp/test_perception_reconstructor.cpp` + `tests/cpp/test_mentalizing_think.cpp`.

- [ ] **Step 1: Failing test** — Smarties: `see`@Anne(apparent=Smarties), `open`@Tom(actual=pencils). Assert `what_does_X_think(Anne, "Smarties tube")` → `state_dim="content"`, `state_value="Smarties"`, `is_stale=true`; Tom → pencils, not stale.

- [ ] **Step 2: Reconstructor** — add `is_see(p)` (`see`/`look`) and treat `open`/`reveal`/`close` + `see` as content state-events writing `state_dim="content"`: `see` → present observers learn apparent value (`ev.location`); `open`/`reveal` → present learn actual value. `see`/`open` actors ARE physically present (unlike tell) — they remain in the physical cast (Task 2.1 only excluded `tell`). Distinguish the dim by predicate: presence/physical-move → `location`; see/open/reveal → `content`.

- [ ] **Step 3: Ground-truth content** — `what_does_X_think` needs the actual content for `is_stale` when `dim="content"`. Add `PerceptionStateStore`-independent helper or extend the primitive to read the latest `open`/`reveal` value. Add to `mentalizing_think.cpp`: infer `dim` from the theme's perceived events (query `perception_state` `DISTINCT state_dim` for the theme; prefer `content` if present, else `location`), and for `dim="content"` compute ground truth as the highest-position `content` value among ALL cognizers (the revealed actual). Provide the SQL helper in `PerceptionStateStore`:

```cpp
// latest actual state for a theme+dim across all cognizers (ground truth), "" if none.
std::string PerceptionStateStore::latest_actual(std::string_view tenant,
    std::string_view theme, std::string_view dim);   // SELECT state_value ... ORDER BY position DESC LIMIT 1
```
Use `latest_event_location` for `dim="location"` (unchanged) and `latest_actual(...,"content")` for content. Update `is_stale` accordingly. Implement dim inference (`SELECT DISTINCT state_dim … LIMIT` with content precedence).

- [ ] **Step 4: PASS**, full ctest 623, commit.

---

## Phase 5 — `does_X_know` info-access integration + three-track eval

### Task 5.1: make `does_X_know` event-aware (secondary integration — verify, do not assume free)

**Files:** Modify `src/cognizer/perception_reconstructor.cpp` (also record perceived events into `KnowledgeFrontier`); Test `tests/cpp/test_perception_reconstructor.cpp` or a new `test_does_x_know_events.cpp`.

- [ ] **Step 1: Failing test** — after reconstruction, `does_X_know(adapter, frontier, "Sally", FactKey{...ball/located_at...}, T, as_of)` returns a value reflecting Sally's event-perception (e.g. `NotKnown`/`FullKnowledge` per the frontier path), proving the event engrams reached the frontier.

- [ ] **Step 2: Impl** — in the reconstructor, in addition to `perception_state`, call `frontier.record_presence_from_statement(tenant, {witness}, engram_id, observed_at, conn_)` for each witness so the perceived event's engram becomes visible (this is the `does_X_know` Step-2 plumbing the spec flagged as needing verification). Construct `KnowledgeFrontier frontier(adapter)` — note the reconstructor currently takes only `Connection&`; either pass the engram id through (the OCCURRED statement's `engram_ref`) or grep how `belief_tracker_handlers.cpp` obtains the engram for `record_presence_from_statement` and mirror. Resolve the engram-id source in-task (grep `engram_ref`/`engram_id` on the statements/episodic rows).

- [ ] **Step 3:** If the engram plumbing proves heavier than this task's budget, scope down: keep `what_does_X_think` as the sole supported B query and mark `does_X_know`-over-events as a known follow-up in the eval report (the spec already labels it secondary). Either outcome is acceptable; do NOT block the eval on it. Commit.

### Task 5.2: three-track eval (gated e2e + ToMBench subset)

**Files:** Modify `tests/python/test_perception_e2e.py` (gated real-LLM); Create `scripts/eval_perception_starling.py`.

- [ ] **Step 1: Gated real-LLM e2e** — add a `STARLING_RUN_LLM_E2E`-gated test (mirror A's `tests/python/test_episodic_e2e.py` gate: `_RUN_LLM_E2E = bool(os.environ.get("STARLING_RUN_LLM_E2E")) and _HAS_LLM_KEY`) that runs `remember("Sally puts her ball in the basket and leaves; Anne moves it to the box")` with a real LLM (DeepSeek endpoint per the eval convention: `OPENAI_API_KEY=$DEEPSEEK_API_KEY OPENAI_BASE_URL=https://api.deepseek.com/v1`, `max_tokens=32768`) → asserts `what_does_X_think(Sally,ball)=basket`, `(Anne,ball)=box`. Default `pytest` run skips it.

- [ ] **Step 2: ToMBench subset harness** — `scripts/eval_perception_starling.py`, Starling-in-the-loop, mirroring `scripts/eval_tom2_starling.py` (per-item isolated DB, stub LLM, run C++ machinery, score vs gold). Filter ToMBench items by the `"ability"` field (the exact JSON key `eval_tom_bench.py` uses) — **grep the actual ToMBench corpus for the Knowledge/false-belief ability slug strings** (`scripts/eval_tom_bench.py` uses `record.get("ability","")`; the False-Belief slugs are in `SECOND_ORDER_ABILITIES = {"false-belief","second-order","higher-order"}` — confirm the Knowledge slug, likely `"knowledge"`, by grepping the corpus JSONL). Pipeline per item: extract the narrative (real model) → `remember` → A events → B reconstruct → `what_does_X_think(asked_cognizer, theme)` → compare to `record["options"][int(record["answer"])]`. Report accuracy; mirror P3.a2's three-track report format. Name the exact corpus file/path in the script header.

- [ ] **Step 3:** Run the deterministic tracks (ctest 623 + pytest 619 green); the real-LLM track + ToMBench scoring are run on demand (documented in the script). Commit.

---

## Self-Review

**1. Spec coverage** (spec §1–9 → task):
- §1 four channels → presence (P1), told (P2), unexpected-contents (P4), info-access (P5). ✓
- §3.0 decisions 1–6 → materialise `perception_state` (1.1) / `what_does_X_think` (1.3) / scene-global presence (1.2) / post-pass reconstructor (1.2) / unified state-update + per-kind rules (1.2/2.2/4.2) / three-track eval (5.2). ✓
- §3.1 scene-scoped scan + (observed_at, seq) + co-presence → 1.2 scan SQL + 3.1 intersection. ✓
- §3.3 `StateBelief` + signature + `has_belief` + observer → 1.3 + 3.1. ✓
- §3.4 location/content/told → 1.2 / 4.2 / 2.2. ✓
- §3.5 vocab extension → 2.1 (+ 4.1). ✓
- §3.6 B-owned append-only `perception_state`, A untouched → 1.1. ✓
- §4.1 1st/2nd order → 1.3/3.1. ✓
- §6 error handling (best-effort, no-enter/leave, unknown) → 1.4 try/except + 1.3 `has_belief`. ✓
- §7 phasing → Phases 1–5. ✓ §8 three tracks → 1.x deterministic + 5.2. ✓ §9 constraints → header. ✓

**2. Placeholder scan:** Phase 1 carries full SQL/C++/Python. Phases 2–5 are task-level but every code touch shows the actual snippet; the only deferred-to-task lookups are explicit greps (engram-id source in 5.1, ToMBench ability slug in 5.2, `EpisodicExtractor` bind file in 1.4) — each names what to grep and why, not "figure it out". The Task 1.2/1.3 test seeding says "copy the helper from `tests/cpp/test_episodic_extractor.cpp`" — a concrete existing source, not a placeholder.

**3. Type consistency:** `perception_state` columns (`tenant_id, cognizer_id, theme_id, state_dim, state_value, observed_at, position, source_event_id`) are identical across the migration (1.1), `PerceptionStateRow` (1.1), reconstructor writes (1.2/2.2/4.2), and `last_known`/`perceived_for_theme` reads (1.1/3.1). `StateBelief{has_belief, state_dim, state_value, source_event_id, is_stale}` matches across header (1.3), impl (1.3), binding (1.3). `what_does_X_think(adapter, frontier, x, theme, tenant, as_of, observer="")` is identical in header/impl/binding/wrapper. `PerceptionReconstructor(Connection&).reconstruct(tenant)` matches header/impl/binding/`_memory_core` call. Stores take `Connection&`; mentalizing takes `SqliteAdapter&` + `frontier` (matching `does_X_know`). ✓

**Note carried for the implementer:** confirm `TransactionGuard` commit semantics by reading `episodic_extractor.cpp` (auto-commit on dtor vs explicit `.commit()`) and match it in 1.2; confirm `mem.rt.adapter` / `KnowledgeFrontier` Python accessors in 1.4 against the actual bindings.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-18-perception-knowledge-tracking.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — fresh subagent per task, two-stage review (spec then quality) between tasks, fast iteration.

**2. Inline Execution** — execute tasks in this session via executing-plans, batch execution with checkpoints.

**Which approach?**

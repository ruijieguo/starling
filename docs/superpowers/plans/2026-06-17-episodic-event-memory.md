# Episodic Event Memory (sub-project A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Starling ingest physical-action narratives as first-class **episodic events** (`modality=OCCURRED` statements + an `episodic_events` extension table), extracted via a dedicated narrative pass, so events store/recall through the existing pipeline without disturbing the belief/ToM machinery.

**Architecture:** An episodic event is a `statements` row (`holder=self`, subject=actor, predicate=action, object=theme, `modality=OCCURRED`) plus an `episodic_events` extension row (`seq`, event_time, location, participants_json, action_raw), owned by a single C++ `EpisodicEventStore` (commitments-extension pattern). A new narrative-framed `EpisodicExtractor` runs as a second pass inside `remember()`. OCCURRED rows are excluded from belief_tracker/ToM nesting and conflict arbitration (events are a temporal sequence, not contestable beliefs). Per-cognizer knowledge/perception is sub-project B, not here.

**Tech Stack:** C++20 (`src/`, `include/starling/`, store in `src/store/`), SQLite migration, pybind11, GoogleTest, pytest. Spec: `docs/superpowers/specs/2026-06-17-episodic-event-memory-design.md` (commit c18d1bf).

---

## File Structure

| File | Responsibility | Phase |
|------|----------------|-------|
| `include/starling/schema/statement_enums.hpp` + `src/schema/statement_enums.cpp` | add `OCCURRED` modality + serialization | 1 |
| `bindings/python/bind_*.cpp` (Modality enum, if bound) | expose `OCCURRED` | 1 |
| `migrations/0025_episodic_events.sql` | `episodic_events` extension table | 2 |
| `include/starling/store/episodic_event_store.hpp` + `src/store/episodic_event_store.cpp` | single-owner CRUD + seq order + `latest_event_location` | 2 |
| `include/starling/extractor/predicate_registry.hpp` | curated action predicate class | 3 |
| `src/extractor/statement_validator.cpp` | OCCURRED rows: out-of-set predicate accepted (no downgrade) | 3 |
| `src/tom/second_order.cpp` + `src/tom/belief_tracker_handlers.cpp` | skip `modality=OCCURRED` in ToM nesting | 4 |
| `src/bus/conflict_key.cpp` / `conflict_probe.cpp` | skip `modality=OCCURRED` in conflict-key assignment/arbitration | 4 |
| `python/starling/extractor/episodic_prompt.py` | narrative event-extraction prompt | 5 |
| `src/extractor/episodic_extractor.{hpp,cpp}` + binding | parse events → OCCURRED statements + episodic_events rows | 5 |
| `python/starling/_memory_core.py` + `memory.py` | dual-pass `remember()` wiring | 5 |
| `tests/cpp/test_episodic_event_store.cpp`, `test_episodic_extractor.cpp`, `test_occurred_modality.cpp`; `tests/python/test_episodic_e2e.py` | tests per phase | 1-6 |

**Phase order/deps:** 1 (OCCURRED) is the foundation; 2 (store+migration) and 3 (action vocab) are independent; 4 (guards) needs 1; 5 (extractor+dual-pass) needs 1+2+3; 6 (recall+e2e) needs 1-5. Each phase exits green independently.

**Build/test (repo root `/Users/jaredguo-mini/develop/memory/starling`):** build `PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build`; C++ test `.venv/bin/ctest --test-dir build -R <Name> --output-on-failure`; full `.venv/bin/ctest --test-dir build --output-on-failure` (baseline **610**); rebuild editable before pytest `… --python-editable`; pytest `.venv/bin/python -m pytest <file> -v` (baseline **615**).

**Standing constraints (every task):** core logic C++ (Python = prompt + binding/adapter only); new table via migration (commitments-pattern, single-owner store); subscriber/handler code SAVEPOINT not BEGIN IMMEDIATE; EpisodicEventStore writes best-effort inside the write SAVEPOINT; explicit-path `git add`; no `--no-verify`/`--amend`. Must not break the belief/multi-order-ToM/six-state/conflict pins.

---

## Phase 1 — OCCURRED modality — FULL DETAIL

### Task 1.1: add `OCCURRED` to the Modality enum + serialization

**Files:**
- Modify: `include/starling/schema/statement_enums.hpp` (enum, ~line 21-33)
- Modify: `src/schema/statement_enums.cpp` (`to_string(Modality)` ~18-33, `modality_from_string` ~85-98)
- Test: `tests/cpp/test_occurred_modality.cpp` (Create)

- [ ] **Step 1: failing test** — `tests/cpp/test_occurred_modality.cpp`:
```cpp
#include "starling/schema/statement_enums.hpp"
#include <gtest/gtest.h>
using namespace starling::schema;
TEST(OccurredModality, RoundTrips) {
    EXPECT_EQ(to_string(Modality::OCCURRED), "occurred");
    EXPECT_EQ(modality_from_string("occurred"), Modality::OCCURRED);
}
```
Add it to `tests/cpp/CMakeLists.txt` (mirror an existing `test_*.cpp` entry).

- [ ] **Step 2: build → FAIL** (`Modality::OCCURRED` undeclared).
Run: `PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build`

- [ ] **Step 3: implement** —
  `statement_enums.hpp`: add `OCCURRED,` to the `enum class Modality` (after `RECANTED,` is fine).
  `statement_enums.cpp` `to_string(Modality)`: add `case Modality::OCCURRED: return "occurred";`.
  `statement_enums.cpp` `modality_from_string`: add `if (s == "occurred") return Modality::OCCURRED;`.

- [ ] **Step 4: build + run → PASS**
Run: `… configure_build.py --build --build-dir build && .venv/bin/ctest --test-dir build -R OccurredModality --output-on-failure`

- [ ] **Step 5: full ctest → 610 (+ this test)** `.venv/bin/ctest --test-dir build --output-on-failure`

- [ ] **Step 6: commit**
```bash
git add include/starling/schema/statement_enums.hpp src/schema/statement_enums.cpp tests/cpp/test_occurred_modality.cpp tests/cpp/CMakeLists.txt
git commit -F - <<'EOF'
feat(schema): add OCCURRED modality (episodic events, sub-project A)

EOF
```

### Task 1.2: expose OCCURRED to Python + extractor case-handling

**Files:**
- Modify: the binding that exposes `Modality` (locate: `grep -rn "Modality" bindings/python/`) — add `OCCURRED` if the enum is bound.
- Modify: the extraction JSON parser's modality case-handling (`src/extractor/json_parser.cpp` — confirm it lowercases the modality string before `modality_from_string`, since prompts emit upper-case "BELIEVES"; ensure "OCCURRED"/"occurred" both parse).
- Test: extend `test_occurred_modality.cpp` — parse `{"modality":"OCCURRED"}`-style input → `Modality::OCCURRED`.

- [ ] Steps: TDD as above. If `Modality` is not bound to Python (the extractor uses strings end-to-end), this task is just the parser case-check + a test; note that in the commit. Build, `-R OccurredModality` green, full ctest 610, commit (explicit-path).

---

## Phase 2 — `episodic_events` table + `EpisodicEventStore` — FULL DETAIL

### Task 2.1: migration `0025_episodic_events.sql`

**Files:**
- Create: `migrations/0025_episodic_events.sql`
- Test: `tests/cpp/test_episodic_event_store.cpp` (Create; first test asserts the migration applied — table exists)

- [ ] **Step 1: failing test** — open a fresh adapter, assert `episodic_events` exists (query `sqlite_master`). (Mirror how `tests/cpp/test_*` open `:memory:` + run migrations, e.g. `SqliteAdapter::open(":memory:")`.)

- [ ] **Step 2: run → FAIL** (no such table).

- [ ] **Step 3: implement** — `migrations/0025_episodic_events.sql` (study `migrations/0018_commitments.sql` for the exact header/idempotency style):
```sql
-- 0025: episodic_events — extension table for OCCURRED episodic-event statements (sub-project A).
CREATE TABLE IF NOT EXISTS episodic_events (
    statement_id       TEXT NOT NULL,
    tenant_id          TEXT NOT NULL,
    seq                INTEGER NOT NULL,          -- monotonic event order within an ingestion
    event_time         TEXT,                      -- ISO8601, nullable
    location           TEXT,                      -- theme's resulting location, nullable
    participants_json  TEXT NOT NULL DEFAULT '[]',-- cognizers NAMED in this event
    action_raw         TEXT,                      -- surface verb
    PRIMARY KEY (statement_id, tenant_id),
    FOREIGN KEY (statement_id) REFERENCES statements(id)
);
CREATE INDEX IF NOT EXISTS idx_episodic_events_seq ON episodic_events(tenant_id, seq);
```
Register it in the migration runner the same way 0024 is (confirm whether migrations are auto-discovered or listed — `grep -rn "0024" src/ include/`).

- [ ] **Step 4: run → PASS**; **Step 5: full ctest 610**; **Step 6: commit** (explicit-path: the migration + test + any migration-list file).

### Task 2.2: `EpisodicEventStore` (single-owner CRUD + seq order + latest_event_location)

**Files:**
- Create: `include/starling/store/episodic_event_store.hpp`, `src/store/episodic_event_store.cpp`
- Modify: `src/store/CMakeLists.txt` / the store build list (mirror `sqlite_statement_store.cpp`)
- Test: `tests/cpp/test_episodic_event_store.cpp`

- [ ] **Step 1: failing tests** — `upsert(EpisodicEventRow)` then `get(statement_id)` round-trips all fields; `events_for_theme(tenant, theme_id)` returns rows ordered by `seq`; `latest_event_location(tenant, theme_id)` returns the highest-`seq` event's location. (Seed statements rows + episodic_events via the store; mirror `tests/cpp/test_*store*` setup.)

- [ ] **Step 2: run → FAIL** (store undeclared).

- [ ] **Step 3: implement** — header interface (mirror `include/starling/store/sqlite_statement_store.hpp` ownership style):
```cpp
namespace starling::store {
struct EpisodicEventRow {
    std::string statement_id, tenant_id;
    long long seq = 0;
    std::string event_time;        // "" = NULL
    std::string location;          // "" = NULL
    std::string participants_json = "[]";
    std::string action_raw;
};
class EpisodicEventStore {
public:
    explicit EpisodicEventStore(persistence::Connection& conn);
    void upsert(const EpisodicEventRow&);
    std::optional<EpisodicEventRow> get(std::string_view statement_id, std::string_view tenant);
    // OCCURRED events about a theme (object_value), ordered by seq then event_time.
    std::vector<EpisodicEventRow> events_for_theme(std::string_view tenant, std::string_view theme_id);
    // The highest-seq event's location for a theme (ground-truth current state), or "" if none.
    std::string latest_event_location(std::string_view tenant, std::string_view theme_id);
private:
    persistence::Connection& conn_;
};
}
```
`events_for_theme` JOINs `episodic_events` to `statements` on `statement_id` WHERE `statements.object_value = theme AND modality='occurred' AND tenant` ORDER BY `seq, event_time`. Implement CRUD with prepared statements (mirror `sqlite_statement_store.cpp`).

- [ ] **Step 4: run → PASS**; **Step 5: full ctest 610**; **Step 6: commit** (explicit-path).

---

## Phase 3 — action vocabulary (curated class + OCCURRED free-form)

### Task 3.1: curated action predicate class + modality-aware validator

**Files:**
- Modify: `include/starling/extractor/predicate_registry.hpp` (add an `action` class: put, place, move, take, give, remove, transfer, leave, open, close)
- Modify: `src/extractor/statement_validator.cpp` (for `modality=OCCURRED`, an out-of-registry predicate is ACCEPTED — not downgraded to `review_requested`; non-OCCURRED behaviour unchanged)
- Test: `tests/cpp/test_statement_validator*.cpp` (or new) — OCCURRED + "put" (curated) → approved/canonical; OCCURRED + "yeeted" (out-of-set) → accepted (not review_requested); BELIEVES + "thinks" (out-of-set) → still downgraded.

- [ ] Steps: TDD red→green. Read `predicate_registry.hpp` + `statement_validator.cpp` first; add the action set; thread the row's `modality` into the validator's predicate check so OCCURRED bypasses the downgrade. Build, `-R` the validator test, full ctest 610, commit (explicit-path).

---

## Phase 4 — pipeline guards (events ≠ contestable beliefs)

### Task 4.1: ToM/belief_tracker skips OCCURRED

**Files:**
- Modify: `src/tom/second_order.cpp` (`maybe_persist_second_order` — early-return when source `modality==OCCURRED`)
- Modify: `src/tom/belief_tracker_handlers.cpp` if it inspects modality
- Test: `tests/cpp/test_tom_second_order.cpp` — seeding an other-holder OCCURRED event produces NO meta-belief (reason e.g. `skip_event`).

- [ ] Steps: TDD. Read `second_order.cpp`; add `if (src.modality == "occurred") { out.reason="skip_event"; return out; }` (match how modality is read there). Test red→green; full ctest 610; commit.

### Task 4.2: conflict arbitration skips OCCURRED

**Files:**
- Modify: `src/bus/conflict_key.cpp` and/or `src/bus/conflict_probe.cpp` (skip `canonical_conflict_key` assignment + conflict detection for `modality='occurred'`)
- Test: `tests/cpp/test_conflict*.cpp` — two OCCURRED events on the same theme at different locations (ball→basket seq1, ball→box seq2) produce NO `conflicts_with` edge / NO arbitration.

- [ ] Steps: TDD. Read `conflict_key.cpp`/`conflict_probe.cpp` to find where the conflict key is assigned; gate on modality. Test red→green; full ctest 610 (existing conflict pins must stay green); commit (explicit-path).

---

## Phase 5 — episodic extractor + dual-pass remember

### Task 5.1: narrative episodic-extraction prompt + `EpisodicExtractor`

**Files:**
- Create: `python/starling/extractor/episodic_prompt.py` (narrative-framed; output JSON array `[{actor, action, theme, location, time, participants[], seq}]`; instruct: emit enter/leave as their own events; seq = narrative order; participants = NAMED only)
- Create: `src/extractor/episodic_extractor.{hpp,cpp}` (mirror `src/extractor/extractor.cpp`: injected with the prompt + llm; parses the JSON; for each event writes an OCCURRED statement via `bus::StatementWriter` (subject=actor entity/cognizer, predicate=action, object=theme, modality=occurred, holder=self) + an `episodic_events` row via `EpisodicEventStore`)
- Modify: binding `bindings/python/bind_06_extractor.cpp` (expose `EpisodicExtractor`)
- Test: `tests/cpp/test_episodic_extractor.cpp` (fixture LLM returning a canned events JSON → asserts OCCURRED statements + episodic_events rows with correct seq/participants/location, incl. a leave event).

- [ ] Steps: TDD with a fixture/stub LLM (canned JSON, like `make_stub_llm`) — no network in the unit test. Read `extractor.cpp` for the injection/parse/write pattern. Build, `-R EpisodicExtractor` green, full ctest 610, commit.

### Task 5.2: dual-pass `remember()`

**Files:**
- Modify: `python/starling/_memory_core.py` (`remember` runs the claim extractor AND the episodic extractor) + `python/starling/memory.py` if the facade needs the second extractor wired + `python/starling/dashboard/engine.py` remember
- Test: extend `tests/python/test_episodic_e2e.py` — `remember(narrative, llm=stub_two_pass)` writes both claim statements (if any) and OCCURRED events.

- [ ] Steps: TDD (stub LLM). Rebuild `--python-editable` before pytest. `pytest tests/python/test_episodic_e2e.py -v` green; full pytest 615+; commit (explicit-path; Python + binding).

---

## Phase 6 — recall + end-to-end

### Task 6.1: event recall + `latest_event_location` exposure

**Files:**
- Modify: recall path so `query`/`recall` surface OCCURRED events (+ their episodic_events extension on read) — `src/retrieval/*` / `python/starling/_memory_core.py recall`
- Modify: binding to expose `latest_event_location`
- Test: C++ + a Python recall test.

- [ ] Steps: TDD; build + `--python-editable`; full ctest/pytest green; commit.

### Task 6.2: real-LLM gated e2e

**Files:**
- Modify: `tests/python/test_episodic_e2e.py` — gated (like the eval harnesses): `remember("Sally puts her ball in the basket and leaves the room. Anne moves the ball to the box.")` with a real LLM → assert OCCURRED events for put (location=basket, participants=[Sally]), leave (subject=Sally), move (subject=Anne, location=box) with seq 1<2<3; `latest_event_location(ball)=="box"`; recall returns them.

- [ ] Steps: gated by env (skip when no key, like `eval_tom_bench`). Document the run command. Confirms the A→B handoff data (events + seq + participants + enter/leave) is present for sub-project B.

---

## Self-Review

**Spec coverage:** §3.1 representation → Tasks 1.x+2.x+5.1; §3.2 action vocab → 3.1; §3.3 table+store+seq+latest_event_location → 2.1+2.2; §3.4 OCCURRED → 1.x; §3.5 E1 extractor+dual-pass+enter/leave/seq/named-participants → 5.1+5.2; §3.6 guards (ToM + conflict) → 4.1+4.2; §4 data flow → 5.2+6; §5 A/B boundary (A stops at events+seq+participants+enter/leave) → 6.2 asserts the handoff data; §7 testing → embedded per phase. No gaps.

**Placeholder scan:** Phases 1-2 carry exact code/SQL. Phases 3-6 are task-level with the exact files + the concrete change + a "read X first / grep Y" where the precise insertion line must be located at execution (conflict_key, belief_tracker, predicate_registry, json_parser) — these are location-lookups, not vague requirements.

**Type consistency:** `Modality::OCCURRED`/"occurred" (1.x → 4.x guards → 5.1 writes); `EpisodicEventStore`/`EpisodicEventRow`/`seq`/`latest_event_location`/`events_for_theme` (2.2 → 5.1 → 6.1); `episodic_events` columns (2.1 → 2.2 → 5.1); `EpisodicExtractor` (5.1 → 5.2 binding); dual-pass remember (5.2 → 6.2). Consistent across tasks.

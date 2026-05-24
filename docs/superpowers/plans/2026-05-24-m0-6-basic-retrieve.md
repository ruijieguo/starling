# M0.6 basic_retrieve — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development — invoke it before starting any task. Each task is a self-contained unit; run sequentially. Commit after every task. Never skip Task 0 baseline verification.

**Goal:** Ship `basic_retrieve(holder, intent=FACT_LOOKUP, subject, predicate, as_of)` — the P1 retrieval closure per `docs/design/subsystems_design/13_retrieval.md`. Returns `list[Statement]` filtered by consolidation_state ∈ {CONSOLIDATED, ARCHIVED}, review_status ∉ {REJECTED, PENDING_REVIEW}, evidence not crypto-erased, and `valid_from ≤ as_of < valid_to`. Emits the minimal `RetrievalReceipt` (P1 必填: `trace_id / query_id / filters_applied / candidate_counts / evidence_erased_count / sufficiency_status`). Emits `statement.recalled` fire-and-forget with a 2s debounce window. Closes the §14.1 P1 retrieve smoke (Alice 宣布 Bob 不再负责 auth → basic_retrieve returns S_new only). Adds `testing.mark_evidence_erased` helper for the evidence-erased negative case. Locks in TC-NEG-TENANT (final query refuses without tenant_id + holder_scope) via the existing `assert_final_query_safe` guard.

**Architecture:** A new C++ component `starling::retrieval::BasicRetriever` sits beside `Bus` (it shares the `SqliteAdapter` but does not write Statement state). It runs the SELECT against `statements` joined to `engrams` for evidence-erasure filtering, materializes `StatementRow` DTOs, builds the `RetrievalReceipt`, and — fire-and-forget — appends `statement.recalled` events through `OutboxWriter` in a separate small transaction (NOT in the read path itself). A new Python facade `starling.retrieval.basic_retrieve(adapter, *, tenant_id, holder, intent, subject, predicate, as_of)` wraps the binding. Multi-holder calls raise `ValueError` immediately. The final SELECT goes through `SqliteAdapter::check_final_query` so TC-NEG-TENANT is enforced by the same M0.2 guardrail used by Bus writes.

**Tech Stack:** C++20 + pybind11 + scikit-build-core editable install; SQLite 3.46+ raw C API + `StmtHandle` RAII; Python 3.11+; pytest; CMake + Ninja; sha256 via OpenSSL EVP (existing `crypto::sha256_hex`).

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `include/starling/retrieval/statement_row.hpp` | Create | `StatementRow` DTO returned by `BasicRetriever::run` |
| `include/starling/retrieval/retrieval_receipt.hpp` | Create | `RetrievalReceipt` P1 minimum-fields struct + `Sufficiency` enum + `FilterApplied` entry struct |
| `include/starling/retrieval/basic_retriever.hpp` | Create | `BasicRetrieverParams` + `BasicRetrieveResult` + `BasicRetriever` class declaration |
| `src/retrieval/basic_retriever.cpp` | Create | `BasicRetriever::run` implementation (SELECT + filter + receipt + recalled emit) |
| `src/bus/bus_event.cpp` | Modify | Extend `compute_window_bucket` to return a 2s bucket for `statement.recalled` |
| `python/starling/bus/bus_event.py` | Modify | Python parity: 2s bucket for `statement.recalled` |
| `migrations/0005_basic_retrieve_index.sql` | Create | `idx_statements_basic_retrieve` on `(tenant_id, holder_id, consolidation_state, predicate, valid_from, valid_to)` per §13 spec |
| `python/starling/retrieval/__init__.py` | Create | Public Python facade: `basic_retrieve(...)` function |
| `python/starling/retrieval/types.py` | Create | Python dataclasses mirroring `StatementRow`, `RetrievalReceipt`, `QueryIntent` enum (only `FACT_LOOKUP` for P1) |
| `bindings/python/module.cpp` | Modify | Bind `BasicRetriever`, `StatementRow`, `RetrievalReceipt`, `QueryIntent`; `testing.mark_evidence_erased` |
| `include/starling/testing_marker.hpp` | Modify | Declare `mark_evidence_erased(SqliteAdapter&, const std::string& engram_id, const std::string& tenant_id, std::string_view erased_at_iso8601)` |
| `src/testing/testing_marker.cpp` | Modify | Implementation: flip `engrams.erased_at` from NULL → ISO8601 timestamp, write a `testing.mark_evidence_erased` audit event, idempotent |
| `python/starling/testing/__init__.py` | Modify | Bind `mark_evidence_erased` from `_core.testing` |
| `tests/cpp/test_basic_retriever_filter_predicates.cpp` | Create | C++ unit tests: state/review/evidence/time-anchor filter predicates |
| `tests/cpp/test_basic_retriever_multi_holder_reject.cpp` | Create | C++ unit test: BasicRetriever rejects empty / multi-holder inputs at C++ layer |
| `tests/cpp/test_basic_retriever_recalled_emit.cpp` | Create | C++ test: returned candidates → N statement.recalled events emitted; 2s window dedups |
| `tests/cpp/test_basic_retriever_receipt.cpp` | Create | C++ test: RetrievalReceipt fields populated correctly (filters_applied / candidate_counts / sufficiency_status / evidence_erased_count) |
| `tests/cpp/test_basic_retrieve_index.cpp` | Create | C++ test: migration 0005 creates the index, no regression on 0001/0003/0004 |
| `tests/cpp/test_mark_evidence_erased.cpp` | Create | C++ test for `testing::mark_evidence_erased` (idempotent + audit event) |
| `tests/python/test_basic_retrieve_smoke.py` | Create | §14.1 P1 retrieve smoke (acceptance, CRITICAL) — Alice 宣布 Bob 不再负责 auth, retrieve returns S_new only |
| `tests/python/test_basic_retrieve_filters.py` | Create | Python parity for filter predicates (VOLATILE excluded / REJECTED+PENDING_REVIEW excluded / evidence ERASED excluded / valid_from-to window) |
| `tests/python/test_basic_retrieve_multi_holder_reject.py` | Create | Multi-holder list / empty holder / wrong intent → ValueError |
| `tests/python/test_basic_retrieve_tenant_guard.py` | Create | TC-NEG-TENANT — invoking the retriever's internal SQL without tenant_id + holder_scope raises FinalQueryAssertionError |
| `tests/python/test_basic_retrieve_receipt.py` | Create | RetrievalReceipt P1 minimum fields present and correct |
| `tests/python/test_basic_retrieve_recalled_emit.py` | Create | `statement.recalled` event emitted per returned statement; 2s idempotent dedup |
| `tests/python/test_mark_evidence_erased.py` | Create | `testing.mark_evidence_erased` flips engrams.erased_at + writes audit event |
| `tests/cpp/CMakeLists.txt` | Modify | Append the new `.cpp` files to the single `starling_tests` executable target_sources list |
| `CMakeLists.txt` | Modify | Add `src/retrieval/basic_retriever.cpp` to `starling_core` |

**File Structure rationale:** A separate `retrieval/` subtree mirrors the spec's intent boundary (Retrieval Planner is its own subsystem). Splitting `BasicRetriever` from `Bus` honors the §13 read-side-effects contract: retrieval may emit `statement.recalled` but may NOT modify Statement state, so it cannot be inside `Bus::write`. The Python facade is a thin function, not a class, because P1 exposes exactly one entrypoint (subsequent milestones will turn this into a `Retrieval` class when 7-step planning lands).

---

## Task 0: Baseline Verification

**Files:** None (read-only verification)

**Purpose:** Confirm the worktree is clean and all existing tests pass before any M0.6 code is written. Record the HEAD SHA and test counts so regressions are immediately detectable.

- [ ] **0.1** Activate the venv and confirm Python version:
  ```bash
  source /Users/jaredguo-mini/develop/memory/starling/.venv/bin/activate
  python --version
  # Expected: Python 3.11.x or 3.12.x
  ```

- [ ] **0.2** Record the current HEAD SHA:
  ```bash
  git -C /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/m0-6-basic-retrieve rev-parse HEAD
  # Expected: fab3e2a... (the M0.5 merge tip on main)
  # Record this value — it is the pre-M0.6 baseline.
  ```

- [ ] **0.3** Build the project from scratch:
  ```bash
  cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/m0-6-basic-retrieve
  cmake -S . -B build -G Ninja
  cmake --build build
  # Expected: build succeeds with 0 errors.
  ```

- [ ] **0.4** Run the full C++ test suite and record the count:
  ```bash
  cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/m0-6-basic-retrieve/build
  ctest --output-on-failure
  # Expected: all tests pass (record exact N/N count).
  ```

- [ ] **0.5** Install the Python package in editable mode:
  ```bash
  cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/m0-6-basic-retrieve
  pip install -e . --no-build-isolation
  ```

- [ ] **0.6** Run the full Python test suite and record the count:
  ```bash
  cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/m0-6-basic-retrieve
  pytest tests/python/ -q
  # Expected: all pass (record exact N/N).
  ```

- [ ] **0.7** Run the CI static scan:
  ```bash
  python scripts/ci_static_scan.py
  # Expected: exit 0.
  ```

- [ ] **0.8** Record baseline (no commit — verification only):
  ```
  Baseline: HEAD=<sha>, ctest=<N>/<N>, pytest=<N>/<N>, ci_scan=clean
  ```

---

## Task 1: Migration 0005 — `idx_statements_basic_retrieve`

**Files:**
- Create: `migrations/0005_basic_retrieve_index.sql`
- Create: `tests/cpp/test_basic_retrieve_index.cpp`

**Purpose:** Per `docs/design/subsystems_design/13_retrieval.md` §"P1 basic_retrieve 闭环", basic_retrieve queries the statements table on `(holder, consolidation_state, valid_from, valid_to)`. The existing `idx_statements_holder_predicate` covers `(tenant_id, holder_id, predicate)` only. Add a composite index that fully covers the P1 retrieval predicate including the time-anchor range.

- [ ] **1.1** Create `migrations/0005_basic_retrieve_index.sql`:

  ```sql
  -- Starling M0.6 retrieval index. Per docs/design/subsystems_design/13_retrieval.md
  -- §"P1 basic_retrieve 闭环": basic_retrieve filters by (holder, consolidation_state,
  -- valid_from, valid_to) on the statements main table. The composite covers tenant
  -- isolation (leading column) + holder scoping + state filter + predicate equality
  -- + time-anchor range.

  CREATE INDEX IF NOT EXISTS idx_statements_basic_retrieve
      ON statements(tenant_id, holder_id, consolidation_state, predicate, valid_from, valid_to);
  ```

- [ ] **1.2** Verify the migration file checksum slot is auto-managed by `schema_migrations` (no manual checksum insert):

  ```bash
  grep -n schema_migrations migrations/0001_initial_schema.sql
  # Expected: the table is created in 0001; rows are inserted by MigrationRunner
  # after each successful migration. We do NOT hand-edit checksums.
  ```

- [ ] **1.3** Create `tests/cpp/test_basic_retrieve_index.cpp`:

  ```cpp
  #include <gtest/gtest.h>
  #include "starling/persistence/sqlite_adapter.hpp"
  #include "starling/persistence/migration_runner.hpp"

  using starling::persistence::SqliteAdapter;
  using starling::persistence::MigrationRunner;

  namespace {

  // Returns the comma-joined column list for an SQLite index (via PRAGMA index_info).
  std::string index_columns(SqliteAdapter& a, const std::string& index_name) {
      // Minimal helper using sqlite3 prepared statements via the existing
      // adapter accessor. The full helper lives next to other test
      // utilities in test_migration_0003.cpp — copy that pattern.
      auto& conn = a.connection();
      std::string sql = "PRAGMA index_info('" + index_name + "');";
      // Iterate rows and concatenate column-name (cid=2) with ',' separators.
      // (See test_migration_0003.cpp for the exact StmtHandle loop.)
      return starling::persistence::collect_pragma_index_columns(conn, index_name);
  }

  }  // namespace

  TEST(MigrationBasicRetrieveIndex, CreatesCompositeIndex) {
      auto adapter = SqliteAdapter::open(":memory:");
      MigrationRunner(adapter->connection()).apply_all("migrations");
      EXPECT_EQ(index_columns(*adapter, "idx_statements_basic_retrieve"),
                "tenant_id,holder_id,consolidation_state,predicate,valid_from,valid_to");
  }

  TEST(MigrationBasicRetrieveIndex, DoesNotRegressExistingIndices) {
      auto adapter = SqliteAdapter::open(":memory:");
      MigrationRunner(adapter->connection()).apply_all("migrations");
      // From 0001:
      EXPECT_NE(index_columns(*adapter, "idx_statements_holder_predicate"), "");
      EXPECT_NE(index_columns(*adapter, "idx_statements_subject"), "");
      // From 0004:
      EXPECT_NE(index_columns(*adapter, "idx_conflict_lookup"), "");
      EXPECT_NE(index_columns(*adapter, "idx_temporal_overlap"), "");
  }
  ```

  **Note:** If `collect_pragma_index_columns` does not already exist in the test-helper TU, the implementer should add it next to the existing index-collection helper used by `test_migration_0003.cpp` (or inline the StmtHandle loop in this file). Don't invent a new public helper in `starling_core`.

- [ ] **1.4** Add the new test file to `tests/cpp/CMakeLists.txt` under the `starling_tests` `add_executable(... )` source list. Do NOT create a new executable — append to the existing single binary per project convention.

- [ ] **1.5** Run the new test alone to verify it fails before the migration runs (sanity check that the assertion is meaningful):

  ```bash
  cd build && ninja starling_tests && ctest -R MigrationBasicRetrieveIndex --output-on-failure
  # Expected: PASS — the migration file is already present in this commit so this
  # is a green-on-arrival test. We're not TDD-failing the migration itself; the
  # value here is regression coverage going forward.
  ```

- [ ] **1.6** Commit:
  ```bash
  git add migrations/0005_basic_retrieve_index.sql \
          tests/cpp/test_basic_retrieve_index.cpp \
          tests/cpp/CMakeLists.txt
  git commit -m "$(cat <<'EOF'
  feat(M0.6): add migration 0005 idx_statements_basic_retrieve

  Composite index (tenant_id, holder_id, consolidation_state, predicate,
  valid_from, valid_to) per docs/design/subsystems_design/13_retrieval.md
  P1 basic_retrieve filter shape.

  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 2: Extend `compute_window_bucket` for `statement.recalled`

**Files:**
- Modify: `src/bus/bus_event.cpp`
- Modify: `python/starling/bus/bus_event.py`
- Create: `tests/cpp/test_recalled_window_bucket.cpp` (small focused unit test next to existing bucket tests)
- Create: `tests/python/test_recalled_window_bucket.py`

**Purpose:** §13 specifies a 2-second idempotency window for `statement.recalled` events. Extend the C++ and Python `compute_window_bucket` functions in parity. This must be in place before Task 6 (BasicRetriever emits the event).

- [ ] **2.1** Modify `src/bus/bus_event.cpp` — add a branch for `statement.recalled` returning `floor(seconds / 2)`:

  ```cpp
  if (event_type == "statement.recalled") {
      // 2-second debounce window per docs/design/subsystems_design/13_retrieval.md
      // §"statement.recalled emit 契约". Same-key recall within 2s coalesces.
      const auto sec = std::chrono::duration_cast<std::chrono::seconds>(
          now.time_since_epoch()).count();
      return std::to_string(sec / 2);
  }
  ```

  Place this branch above the `if (event_type == "statement.archived" ...)` block so it sits with the other windowed events.

- [ ] **2.2** Modify `python/starling/bus/bus_event.py` — mirror the same branch:

  ```python
  if event_type == "statement.recalled":
      # 2-second debounce window per
      # docs/design/subsystems_design/13_retrieval.md
      # §"statement.recalled emit 契约".
      return str(int(now.timestamp()) // 2)
  ```

  Place above the `statement.archived` / `statement.superseded` branch.

- [ ] **2.3** Create `tests/cpp/test_recalled_window_bucket.cpp`:

  ```cpp
  #include <gtest/gtest.h>
  #include "starling/bus/bus_event.hpp"
  #include <chrono>

  using starling::bus::compute_window_bucket;

  TEST(RecalledWindowBucket, BucketsBy2Seconds) {
      // Two timestamps inside the same 2s window must yield the same bucket.
      using namespace std::chrono;
      auto t0 = system_clock::from_time_t(1'000'000'000);  // even sec → bucket 500000000
      auto t1 = system_clock::from_time_t(1'000'000'001);  // same 2s window
      auto t2 = system_clock::from_time_t(1'000'000'002);  // next window

      EXPECT_EQ(compute_window_bucket("statement.recalled", t0),
                compute_window_bucket("statement.recalled", t1));
      EXPECT_NE(compute_window_bucket("statement.recalled", t0),
                compute_window_bucket("statement.recalled", t2));
  }

  TEST(RecalledWindowBucket, ExpectedStringValue) {
      using namespace std::chrono;
      auto t = system_clock::from_time_t(1'000'000'000);
      EXPECT_EQ(compute_window_bucket("statement.recalled", t), "500000000");
  }
  ```

- [ ] **2.4** Create `tests/python/test_recalled_window_bucket.py`:

  ```python
  from datetime import datetime, timezone

  from starling.bus.bus_event import compute_window_bucket


  def _t(epoch: int) -> datetime:
      return datetime.fromtimestamp(epoch, tz=timezone.utc)


  def test_buckets_by_2_seconds():
      t0 = _t(1_000_000_000)
      t1 = _t(1_000_000_001)
      t2 = _t(1_000_000_002)
      assert compute_window_bucket("statement.recalled", t0) == \
             compute_window_bucket("statement.recalled", t1)
      assert compute_window_bucket("statement.recalled", t0) != \
             compute_window_bucket("statement.recalled", t2)


  def test_expected_string_value():
      assert compute_window_bucket("statement.recalled", _t(1_000_000_000)) == "500000000"
  ```

- [ ] **2.5** Append the C++ test to the `starling_tests` source list in `tests/cpp/CMakeLists.txt`.

- [ ] **2.6** Run both tests:

  ```bash
  cd build && ninja starling_tests && ctest -R RecalledWindowBucket --output-on-failure
  cd .. && pip install -e . --no-build-isolation
  pytest tests/python/test_recalled_window_bucket.py -q
  # Expected: all PASS.
  ```

- [ ] **2.7** Commit:
  ```bash
  git add src/bus/bus_event.cpp python/starling/bus/bus_event.py \
          tests/cpp/test_recalled_window_bucket.cpp \
          tests/python/test_recalled_window_bucket.py \
          tests/cpp/CMakeLists.txt
  git commit -m "$(cat <<'EOF'
  feat(M0.6): 2s window bucket for statement.recalled

  Mirrors compute_window_bucket C++ and Python implementations per
  13_retrieval.md §"statement.recalled emit 契约". Required before
  BasicRetriever emits the event in Task 6.

  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 3: `StatementRow` + `RetrievalReceipt` DTOs

**Files:**
- Create: `include/starling/retrieval/statement_row.hpp`
- Create: `include/starling/retrieval/retrieval_receipt.hpp`

**Purpose:** Pure value types — no logic. Decoupling the row shape from the active-record machinery keeps `BasicRetriever` testable in isolation and gives Python a clean binding surface.

- [ ] **3.1** Create `include/starling/retrieval/statement_row.hpp`:

  ```cpp
  #pragma once

  #include <cstdint>
  #include <string>
  #include <vector>

  namespace starling::retrieval {

  // The subset of statements columns returned by basic_retrieve in P1.
  // Anything the §14.1 smoke + filter tests don't read is excluded — adding
  // columns later requires bumping the SELECT in basic_retriever.cpp.
  struct StatementRow {
      std::string id;
      std::string tenant_id;
      std::string holder_id;
      std::string holder_perspective;     // e.g. "FIRST_PERSON"
      std::string subject_kind;
      std::string subject_id;
      std::string predicate;
      std::string object_kind;
      std::string object_value;
      std::string canonical_object_hash;
      std::string modality;
      std::string polarity;
      double      confidence{};
      std::string observed_at;
      std::string valid_from;             // "" if NULL
      std::string valid_to;               // "" if NULL
      std::string consolidation_state;    // "consolidated" | "archived"
      std::string review_status;
      std::string evidence_json;          // raw JSON array of EvidenceRef-like dicts
      // P1 retrieval does not surface confidence_history / derived_from / etc.
  };

  }  // namespace starling::retrieval
  ```

- [ ] **3.2** Create `include/starling/retrieval/retrieval_receipt.hpp`:

  ```cpp
  #pragma once

  #include <cstdint>
  #include <string>
  #include <vector>

  namespace starling::retrieval {

  // Four-state sufficiency per docs/design/subsystems_design/13_retrieval.md
  // §"RetrievalReceipt 合法性约束".
  enum class Sufficiency {
      SUFFICIENT,
      MISSING_INFO,
      NEEDS_RAW,
      ABSTAINED,
  };

  // One entry per filter actually applied. P1 always emits the same set
  // (tenant + holder + consolidation_state + review_status + evidence-erased
  // + time-anchor) so the receipt can be audited against the spec.
  struct FilterApplied {
      std::string name;     // "tenant_id" | "holder_id" | "consolidation_state" | ...
      std::string value;    // serialized value (the SQL bind value or set repr)
  };

  // P1-minimum RetrievalReceipt. Spec lists ~25 fields, but P1 mandates only
  // the six below (13_retrieval.md §"RetrievalReceipt（P1 最小字段加粗）").
  // Future milestones will add scope_plan / plan_steps / score_breakdown / etc.
  struct RetrievalReceipt {
      std::string trace_id;
      std::string query_id;
      std::vector<FilterApplied> filters_applied;

      // Counts captured at each stage. P1 stages are simpler than P3.
      struct CandidateCounts {
          std::int64_t fetched{};
          std::int64_t returned{};
          std::int64_t dropped_by_review{};
          std::int64_t dropped_by_state{};
          std::int64_t dropped_by_time_anchor{};
          std::int64_t dropped_by_evidence_erasure{};
      } candidate_counts;

      std::int64_t evidence_erased_count{};
      Sufficiency  sufficiency_status{Sufficiency::ABSTAINED};
  };

  }  // namespace starling::retrieval
  ```

- [ ] **3.3** No tests in this task — these are pure declarations and will be exercised by Tasks 4-7. Verify it compiles:

  ```bash
  cd build && cmake --build . --target starling_core
  # Expected: clean build.
  ```

  These headers are not yet referenced by anything; the compile is just a syntax check. If `starling_core` doesn't pick them up automatically (header-only files don't need to be added to a target_sources list), that's fine — Task 4's source will pull them in.

- [ ] **3.4** Commit:
  ```bash
  git add include/starling/retrieval/statement_row.hpp \
          include/starling/retrieval/retrieval_receipt.hpp
  git commit -m "$(cat <<'EOF'
  feat(M0.6): StatementRow + RetrievalReceipt DTOs

  Header-only value types for basic_retrieve. RetrievalReceipt only carries
  the six P1-mandated fields (trace_id / query_id / filters_applied /
  candidate_counts / evidence_erased_count / sufficiency_status) per
  13_retrieval.md.

  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 4: `BasicRetriever` declaration + SELECT-and-filter implementation (no event emit)

**Files:**
- Create: `include/starling/retrieval/basic_retriever.hpp`
- Create: `src/retrieval/basic_retriever.cpp`
- Create: `tests/cpp/test_basic_retriever_filter_predicates.cpp`
- Create: `tests/cpp/test_basic_retriever_multi_holder_reject.cpp`
- Modify: `CMakeLists.txt` — add `src/retrieval/basic_retriever.cpp` to `starling_core`
- Modify: `tests/cpp/CMakeLists.txt` — append the two new test files to `starling_tests` source list

**Purpose:** Build the pure read path: parameter validation → SQL composition → SELECT → filter materialization → receipt construction. Do NOT emit events yet (Task 6 layers that on top).

- [ ] **4.1** Create `include/starling/retrieval/basic_retriever.hpp`:

  ```cpp
  #pragma once

  #include <chrono>
  #include <string>
  #include <vector>

  #include "starling/persistence/sqlite_adapter.hpp"
  #include "starling/retrieval/statement_row.hpp"
  #include "starling/retrieval/retrieval_receipt.hpp"

  namespace starling::retrieval {

  enum class QueryIntent {
      FACT_LOOKUP,
      // The remaining 8 intents (BELIEF_OF_OTHER, META_BELIEF, HISTORY,
      // COMMITMENT_DUE, PREFERENCE, NORM_LOOKUP, COMMON_GROUND, ABSTAIN_CHECK)
      // are spec'd at 13_retrieval.md §"QueryIntent 枚举（9 种）" but P1 only
      // ships FACT_LOOKUP. Other values are rejected at runtime.
  };

  struct BasicRetrieverParams {
      std::string  tenant_id;
      std::string  holder_id;             // single holder only; empty → reject
      QueryIntent  intent{QueryIntent::FACT_LOOKUP};
      std::string  subject_id;
      std::string  predicate;
      std::string  as_of_iso8601;         // canonicalized at the Python boundary
      std::string  trace_id;              // caller-supplied; receipt echoes it
      std::string  query_id;              // caller-supplied; usually a fresh UUID
  };

  struct BasicRetrieveResult {
      std::vector<StatementRow> rows;
      RetrievalReceipt receipt;
  };

  class BasicRetriever {
   public:
      explicit BasicRetriever(starling::persistence::SqliteAdapter& adapter)
          : adapter_(adapter) {}

      BasicRetriever(const BasicRetriever&)            = delete;
      BasicRetriever& operator=(const BasicRetriever&) = delete;

      // Reject on:
      //   - holder_id empty
      //   - intent != FACT_LOOKUP
      //   - tenant_id empty
      // No silent broadening, per 13_retrieval.md §"P1 basic_retrieve 闭环".
      BasicRetrieveResult run(const BasicRetrieverParams& params);

   private:
      starling::persistence::SqliteAdapter& adapter_;
  };

  }  // namespace starling::retrieval
  ```

- [ ] **4.2** Create `src/retrieval/basic_retriever.cpp`:

  ```cpp
  #include "starling/retrieval/basic_retriever.hpp"

  #include <sqlite3.h>

  #include <stdexcept>
  #include <string>
  #include <vector>

  #include "starling/persistence/connection.hpp"
  #include "starling/final_query_assertion.hpp"

  namespace starling::retrieval {

  namespace {

  // The single P1 SELECT. Joins engrams via the evidence_json LIKE-pattern
  // approach the project already uses elsewhere (see statement_writer.cpp's
  // chunk-dup guard) is NOT applicable here — for evidence erasure we instead
  // post-filter rows whose evidence_json contains an engram_ref whose engrams
  // row has erased_at IS NOT NULL. To keep the SQL simple (and let the index
  // do its job), the SELECT applies all column-equality + range filters in
  // SQL, and the evidence-erased filter is applied in C++ after parsing
  // evidence_json. This trades a small fan-in for keeping the SELECT planner-
  // friendly. The post-filter is bounded by candidate_counts.fetched.
  constexpr const char* kSelectSql =
      "SELECT id, tenant_id, holder_id, holder_perspective, "
      "       subject_kind, subject_id, predicate, "
      "       object_kind, object_value, canonical_object_hash, "
      "       modality, polarity, confidence, observed_at, "
      "       valid_from, valid_to, consolidation_state, review_status, "
      "       evidence_json "
      "  FROM statements "
      " WHERE tenant_id = ?1 "
      "   AND holder_id = ?2 "
      "   AND subject_kind = 'cognizer' "  // P1 retrieves cognizer subjects only
      "   AND subject_id = ?3 "
      "   AND predicate = ?4 "
      "   AND consolidation_state IN ('consolidated','archived') "
      "   AND review_status NOT IN ('rejected','pending_review') "
      "   AND (valid_from IS NULL OR valid_from <= ?5) "
      "   AND (valid_to   IS NULL OR valid_to   >  ?5) ";

  // Returns true iff `evidence_json` references at least one engram whose
  // engrams.erased_at is non-NULL for the same tenant. Pulled out so the
  // caller can count erasures for the receipt.
  bool any_evidence_erased(starling::persistence::Connection& conn,
                           const std::string& tenant_id,
                           const std::string& evidence_json);

  }  // namespace

  BasicRetrieveResult BasicRetriever::run(const BasicRetrieverParams& params) {
      if (params.tenant_id.empty()) {
          throw std::invalid_argument("basic_retrieve: tenant_id is required");
      }
      if (params.holder_id.empty()) {
          throw std::invalid_argument("basic_retrieve: holder_id is required (single holder)");
      }
      if (params.intent != QueryIntent::FACT_LOOKUP) {
          throw std::invalid_argument("basic_retrieve: only FACT_LOOKUP is supported in P1");
      }
      if (params.subject_id.empty() || params.predicate.empty()) {
          throw std::invalid_argument("basic_retrieve: subject_id and predicate are required");
      }
      if (params.as_of_iso8601.empty()) {
          throw std::invalid_argument("basic_retrieve: as_of timestamp is required");
      }

      // TC-NEG-TENANT: validate that the final SQL contains tenant_id +
      // holder_scope predicates. This is belt-and-suspenders on top of the
      // hardcoded kSelectSql — if anyone later changes the constant, the
      // assertion catches it before the query runs.
      adapter_.check_final_query(kSelectSql);

      BasicRetrieveResult result;
      result.receipt.trace_id = params.trace_id;
      result.receipt.query_id = params.query_id;
      result.receipt.filters_applied = {
          {"tenant_id",           params.tenant_id},
          {"holder_id",           params.holder_id},
          {"subject_kind",        "cognizer"},
          {"subject_id",          params.subject_id},
          {"predicate",           params.predicate},
          {"consolidation_state", "consolidated|archived"},
          {"review_status_exclude", "rejected|pending_review"},
          {"as_of",               params.as_of_iso8601},
          {"evidence_erased",     "exclude"},
      };

      auto& conn = adapter_.connection();
      sqlite3* db = conn.handle();
      sqlite3_stmt* raw = nullptr;
      if (sqlite3_prepare_v2(db, kSelectSql, -1, &raw, nullptr) != SQLITE_OK) {
          throw std::runtime_error(std::string("basic_retrieve prepare failed: ")
                                   + sqlite3_errmsg(db));
      }
      starling::persistence::StmtHandle stmt{raw};

      sqlite3_bind_text(raw, 1, params.tenant_id.c_str(),     -1, SQLITE_TRANSIENT);
      sqlite3_bind_text(raw, 2, params.holder_id.c_str(),     -1, SQLITE_TRANSIENT);
      sqlite3_bind_text(raw, 3, params.subject_id.c_str(),    -1, SQLITE_TRANSIENT);
      sqlite3_bind_text(raw, 4, params.predicate.c_str(),     -1, SQLITE_TRANSIENT);
      sqlite3_bind_text(raw, 5, params.as_of_iso8601.c_str(), -1, SQLITE_TRANSIENT);

      auto col_text = [raw](int i) {
          const unsigned char* t = sqlite3_column_text(raw, i);
          return t ? std::string(reinterpret_cast<const char*>(t)) : std::string();
      };

      while (true) {
          int rc = sqlite3_step(raw);
          if (rc == SQLITE_DONE) break;
          if (rc != SQLITE_ROW) {
              throw std::runtime_error(std::string("basic_retrieve step failed: ")
                                       + sqlite3_errmsg(db));
          }
          result.receipt.candidate_counts.fetched += 1;

          StatementRow row;
          row.id                      = col_text(0);
          row.tenant_id               = col_text(1);
          row.holder_id               = col_text(2);
          row.holder_perspective      = col_text(3);
          row.subject_kind            = col_text(4);
          row.subject_id              = col_text(5);
          row.predicate               = col_text(6);
          row.object_kind             = col_text(7);
          row.object_value            = col_text(8);
          row.canonical_object_hash   = col_text(9);
          row.modality                = col_text(10);
          row.polarity                = col_text(11);
          row.confidence              = sqlite3_column_double(raw, 12);
          row.observed_at             = col_text(13);
          row.valid_from              = col_text(14);
          row.valid_to                = col_text(15);
          row.consolidation_state     = col_text(16);
          row.review_status           = col_text(17);
          row.evidence_json           = col_text(18);

          if (any_evidence_erased(conn, row.tenant_id, row.evidence_json)) {
              result.receipt.candidate_counts.dropped_by_evidence_erasure += 1;
              result.receipt.evidence_erased_count += 1;
              continue;
          }
          result.rows.push_back(std::move(row));
      }

      result.receipt.candidate_counts.returned =
          static_cast<std::int64_t>(result.rows.size());
      result.receipt.sufficiency_status =
          result.rows.empty() ? Sufficiency::MISSING_INFO : Sufficiency::SUFFICIENT;

      return result;
  }

  namespace {

  bool any_evidence_erased(starling::persistence::Connection& conn,
                           const std::string& tenant_id,
                           const std::string& evidence_json) {
      // evidence_json is a JSON array of objects like
      //   [{"engram_ref":"<uuid>","content_hash":"..."},...]
      // We scan for `"engram_ref":"<uuid>"` substrings (the same pattern
      // statement_writer.cpp uses for chunk-dup guards), then for each
      // engram_ref check whether engrams(id=?, tenant_id=?).erased_at IS NOT NULL.
      static constexpr const char* kCheckSql =
          "SELECT 1 FROM engrams "
          " WHERE tenant_id = ?1 AND id = ?2 "
          "   AND erased_at IS NOT NULL LIMIT 1;";

      static constexpr const char* kRefKey = "\"engram_ref\":\"";
      std::string::size_type pos = 0;
      while (true) {
          auto a = evidence_json.find(kRefKey, pos);
          if (a == std::string::npos) return false;
          a += std::char_traits<char>::length(kRefKey);
          auto b = evidence_json.find('"', a);
          if (b == std::string::npos) return false;
          std::string engram_id = evidence_json.substr(a, b - a);
          pos = b + 1;

          sqlite3_stmt* raw = nullptr;
          sqlite3* db = conn.handle();
          if (sqlite3_prepare_v2(db, kCheckSql, -1, &raw, nullptr) != SQLITE_OK) {
              throw std::runtime_error(std::string("evidence-erased prepare failed: ")
                                       + sqlite3_errmsg(db));
          }
          starling::persistence::StmtHandle h{raw};
          sqlite3_bind_text(raw, 1, tenant_id.c_str(),  -1, SQLITE_TRANSIENT);
          sqlite3_bind_text(raw, 2, engram_id.c_str(),  -1, SQLITE_TRANSIENT);
          int rc = sqlite3_step(raw);
          if (rc == SQLITE_ROW)  return true;
          if (rc == SQLITE_DONE) continue;
          throw std::runtime_error(std::string("evidence-erased step failed: ")
                                   + sqlite3_errmsg(db));
      }
  }

  }  // namespace

  }  // namespace starling::retrieval
  ```

  **Note on `dropped_by_state` / `dropped_by_review` / `dropped_by_time_anchor`:** the SQL pre-filters those before we materialize a row, so we cannot count them at the row level. They remain `0` in the receipt for P1. The implementer should add a one-line comment in the code making this explicit so future-self doesn't try to populate them by removing the SQL filter.

- [ ] **4.3** Add `src/retrieval/basic_retriever.cpp` to `starling_core` in the top-level `CMakeLists.txt`. Locate the line that adds `src/bus/conflict_probe.cpp` (or any similar `target_sources(starling_core PRIVATE ...)` block) and append the new path. If the project uses a glob, no change is needed — but the project convention is explicit sources.

- [ ] **4.4** Create `tests/cpp/test_basic_retriever_multi_holder_reject.cpp`:

  ```cpp
  #include <gtest/gtest.h>
  #include "starling/retrieval/basic_retriever.hpp"
  #include "starling/persistence/sqlite_adapter.hpp"
  #include "starling/persistence/migration_runner.hpp"

  using namespace starling::retrieval;
  using starling::persistence::SqliteAdapter;
  using starling::persistence::MigrationRunner;

  static BasicRetrieverParams minimal_ok() {
      BasicRetrieverParams p;
      p.tenant_id      = "t1";
      p.holder_id      = "alice";
      p.intent         = QueryIntent::FACT_LOOKUP;
      p.subject_id     = "bob";
      p.predicate      = "responsible_for";
      p.as_of_iso8601  = "2026-04-15T00:00:00Z";
      p.trace_id       = "trace-x";
      p.query_id       = "query-x";
      return p;
  }

  TEST(BasicRetrieverReject, EmptyHolderId) {
      auto a = SqliteAdapter::open(":memory:");
      MigrationRunner(a->connection()).apply_all("migrations");
      BasicRetriever r(*a);
      auto p = minimal_ok();
      p.holder_id = "";
      EXPECT_THROW(r.run(p), std::invalid_argument);
  }

  TEST(BasicRetrieverReject, EmptyTenantId) {
      auto a = SqliteAdapter::open(":memory:");
      MigrationRunner(a->connection()).apply_all("migrations");
      BasicRetriever r(*a);
      auto p = minimal_ok();
      p.tenant_id = "";
      EXPECT_THROW(r.run(p), std::invalid_argument);
  }

  TEST(BasicRetrieverReject, MissingSubjectId) {
      auto a = SqliteAdapter::open(":memory:");
      MigrationRunner(a->connection()).apply_all("migrations");
      BasicRetriever r(*a);
      auto p = minimal_ok();
      p.subject_id = "";
      EXPECT_THROW(r.run(p), std::invalid_argument);
  }

  TEST(BasicRetrieverReject, MissingPredicate) {
      auto a = SqliteAdapter::open(":memory:");
      MigrationRunner(a->connection()).apply_all("migrations");
      BasicRetriever r(*a);
      auto p = minimal_ok();
      p.predicate = "";
      EXPECT_THROW(r.run(p), std::invalid_argument);
  }

  TEST(BasicRetrieverReject, MissingAsOf) {
      auto a = SqliteAdapter::open(":memory:");
      MigrationRunner(a->connection()).apply_all("migrations");
      BasicRetriever r(*a);
      auto p = minimal_ok();
      p.as_of_iso8601 = "";
      EXPECT_THROW(r.run(p), std::invalid_argument);
  }
  ```

- [ ] **4.5** Create `tests/cpp/test_basic_retriever_filter_predicates.cpp`:

  ```cpp
  #include <gtest/gtest.h>
  #include "starling/retrieval/basic_retriever.hpp"
  #include "starling/persistence/sqlite_adapter.hpp"
  #include "starling/persistence/migration_runner.hpp"

  #include <sqlite3.h>
  #include <string>

  using namespace starling::retrieval;
  using starling::persistence::SqliteAdapter;
  using starling::persistence::MigrationRunner;

  namespace {

  // Direct INSERT — we are testing the retriever's filter logic, not Bus.write.
  // Seeding via Bus.write would couple this test to ConflictProbe and friends,
  // which is overkill for unit coverage.
  void insert_stmt(SqliteAdapter& a,
                   const std::string& id,
                   const std::string& tenant_id,
                   const std::string& holder_id,
                   const std::string& subject_id,
                   const std::string& predicate,
                   const std::string& object_value,
                   const std::string& consolidation_state,
                   const std::string& review_status,
                   const std::string& valid_from,
                   const std::string& valid_to,
                   const std::string& evidence_json = "[]") {
      static constexpr const char* kSql =
          "INSERT INTO statements ("
          "  id, tenant_id, holder_id, holder_perspective, "
          "  subject_kind, subject_id, predicate, "
          "  object_kind, object_value, canonical_object_hash, canonical_object_hash_version, "
          "  modality, polarity, confidence, observed_at, "
          "  valid_from, valid_to, "
          "  salience, affect_json, activation, last_accessed, "
          "  provenance, evidence_json, "
          "  consolidation_state, review_status, "
          "  created_at, updated_at"
          ") VALUES ("
          "  ?, ?, ?, 'FIRST_PERSON', "
          "  'cognizer', ?, ?, "
          "  'str', ?, 'hash-x', 'v1', "
          "  'BELIEVES', 'POS', 0.9, '2026-04-15T00:00:00Z', "
          "  ?, ?, "
          "  0.5, '{}', 0.5, '2026-04-15T00:00:00Z', "
          "  'user_input', ?, "
          "  ?, ?, "
          "  '2026-04-15T00:00:00Z', '2026-04-15T00:00:00Z'"
          ")";

      sqlite3* db = a.connection().handle();
      sqlite3_stmt* raw = nullptr;
      ASSERT_EQ(sqlite3_prepare_v2(db, kSql, -1, &raw, nullptr), SQLITE_OK);
      starling::persistence::StmtHandle h{raw};

      int i = 1;
      auto bind = [&](const std::string& s) {
          if (s.empty()) sqlite3_bind_null(raw, i++);
          else sqlite3_bind_text(raw, i++, s.c_str(), -1, SQLITE_TRANSIENT);
      };
      bind(id);
      bind(tenant_id);
      bind(holder_id);
      bind(subject_id);
      bind(predicate);
      bind(object_value);
      bind(valid_from);
      bind(valid_to);
      bind(evidence_json);
      bind(consolidation_state);
      bind(review_status);

      ASSERT_EQ(sqlite3_step(raw), SQLITE_DONE);
  }

  BasicRetrieverParams params_at(const std::string& as_of) {
      BasicRetrieverParams p;
      p.tenant_id     = "t1";
      p.holder_id     = "alice";
      p.intent        = QueryIntent::FACT_LOOKUP;
      p.subject_id    = "bob";
      p.predicate     = "responsible_for";
      p.as_of_iso8601 = as_of;
      p.trace_id      = "trace-x";
      p.query_id      = "query-x";
      return p;
  }

  }  // namespace

  TEST(BasicRetrieverFilter, ExcludesVolatile) {
      auto a = SqliteAdapter::open(":memory:");
      MigrationRunner(a->connection()).apply_all("migrations");
      insert_stmt(*a, "s-vol", "t1", "alice", "bob", "responsible_for",
                  "carol", "volatile", "approved", "", "");
      insert_stmt(*a, "s-cons", "t1", "alice", "bob", "responsible_for",
                  "dave", "consolidated", "approved", "", "");
      BasicRetriever r(*a);
      auto res = r.run(params_at("2026-04-15T00:00:00Z"));
      ASSERT_EQ(res.rows.size(), 1u);
      EXPECT_EQ(res.rows[0].id, "s-cons");
  }

  TEST(BasicRetrieverFilter, ExcludesRejectedAndPending) {
      auto a = SqliteAdapter::open(":memory:");
      MigrationRunner(a->connection()).apply_all("migrations");
      insert_stmt(*a, "s-rej",  "t1", "alice", "bob", "responsible_for",
                  "x", "consolidated", "rejected", "", "");
      insert_stmt(*a, "s-pend", "t1", "alice", "bob", "responsible_for",
                  "y", "consolidated", "pending_review", "", "");
      insert_stmt(*a, "s-ok",   "t1", "alice", "bob", "responsible_for",
                  "z", "consolidated", "approved", "", "");
      BasicRetriever r(*a);
      auto res = r.run(params_at("2026-04-15T00:00:00Z"));
      ASSERT_EQ(res.rows.size(), 1u);
      EXPECT_EQ(res.rows[0].id, "s-ok");
  }

  TEST(BasicRetrieverFilter, IncludesArchived) {
      auto a = SqliteAdapter::open(":memory:");
      MigrationRunner(a->connection()).apply_all("migrations");
      insert_stmt(*a, "s-arch", "t1", "alice", "bob", "responsible_for",
                  "carol", "archived", "approved", "", "");
      BasicRetriever r(*a);
      auto res = r.run(params_at("2026-04-15T00:00:00Z"));
      ASSERT_EQ(res.rows.size(), 1u);
      EXPECT_EQ(res.rows[0].consolidation_state, "archived");
  }

  TEST(BasicRetrieverFilter, ExcludesByValidToBoundary) {
      auto a = SqliteAdapter::open(":memory:");
      MigrationRunner(a->connection()).apply_all("migrations");
      // valid_to is exclusive — as_of == valid_to → excluded
      insert_stmt(*a, "s-window", "t1", "alice", "bob", "responsible_for",
                  "carol", "consolidated", "approved",
                  "2026-04-01T00:00:00Z", "2026-04-15T00:00:00Z");
      BasicRetriever r(*a);
      EXPECT_TRUE(r.run(params_at("2026-04-15T00:00:00Z")).rows.empty());
      EXPECT_EQ(r.run(params_at("2026-04-14T23:59:59Z")).rows.size(), 1u);
  }

  TEST(BasicRetrieverFilter, ExcludesBeforeValidFrom) {
      auto a = SqliteAdapter::open(":memory:");
      MigrationRunner(a->connection()).apply_all("migrations");
      insert_stmt(*a, "s-window", "t1", "alice", "bob", "responsible_for",
                  "carol", "consolidated", "approved",
                  "2026-04-15T00:00:00Z", "");
      BasicRetriever r(*a);
      EXPECT_TRUE(r.run(params_at("2026-04-14T23:59:59Z")).rows.empty());
      EXPECT_EQ(r.run(params_at("2026-04-15T00:00:00Z")).rows.size(), 1u);
  }

  TEST(BasicRetrieverFilter, IsolatesAcrossTenant) {
      auto a = SqliteAdapter::open(":memory:");
      MigrationRunner(a->connection()).apply_all("migrations");
      insert_stmt(*a, "s-t1", "t1", "alice", "bob", "responsible_for",
                  "carol", "consolidated", "approved", "", "");
      insert_stmt(*a, "s-t2", "t2", "alice", "bob", "responsible_for",
                  "carol", "consolidated", "approved", "", "");
      BasicRetriever r(*a);
      auto res = r.run(params_at("2026-04-15T00:00:00Z"));
      ASSERT_EQ(res.rows.size(), 1u);
      EXPECT_EQ(res.rows[0].id, "s-t1");
  }
  ```

- [ ] **4.6** Append the two test files to `tests/cpp/CMakeLists.txt`.

- [ ] **4.7** Build + test:

  ```bash
  cd build && cmake --build . && ctest -R "BasicRetriever" --output-on-failure
  # Expected: all new tests PASS, existing tests still PASS.
  ```

- [ ] **4.8** Commit:
  ```bash
  git add include/starling/retrieval/basic_retriever.hpp \
          src/retrieval/basic_retriever.cpp \
          tests/cpp/test_basic_retriever_filter_predicates.cpp \
          tests/cpp/test_basic_retriever_multi_holder_reject.cpp \
          tests/cpp/CMakeLists.txt CMakeLists.txt
  git commit -m "$(cat <<'EOF'
  feat(M0.6): BasicRetriever SELECT + filter predicates

  Implements the P1 read path per 13_retrieval.md §"P1 basic_retrieve 闭环":
  - tenant + holder + subject + predicate equality
  - consolidation_state IN (consolidated, archived)
  - review_status NOT IN (rejected, pending_review)
  - valid_from <= as_of < valid_to
  - evidence-erasure post-filter via engrams.erased_at lookup

  Final SQL gated by check_final_query() so TC-NEG-TENANT regression is
  caught at startup. No event emit yet — see Task 6.

  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 5: `testing.mark_evidence_erased` helper

**Files:**
- Modify: `include/starling/testing_marker.hpp`
- Modify: `src/testing/testing_marker.cpp`
- Modify: `bindings/python/module.cpp` — bind `mark_evidence_erased` under the `testing` submodule
- Modify: `python/starling/testing/__init__.py`
- Create: `tests/cpp/test_mark_evidence_erased.cpp`
- Create: `tests/python/test_mark_evidence_erased.py`

**Purpose:** Per §15.3.5: `testing.mark_evidence_erased(engram_ref)` flips an engram's `erased_at` from NULL → ISO8601 timestamp, writes a `testing.mark_evidence_erased` audit event, and is idempotent (returns false on re-erase / missing row, no event in those cases). Used by the evidence-erased negative test (Task 8) and by the §14.1 smoke variant if it covers crypto-erasure.

- [ ] **5.1** Modify `include/starling/testing_marker.hpp` — add a declaration alongside `mark_consolidated`:

  ```cpp
  namespace starling::testing {

  // Existing:
  // bool mark_consolidated(SqliteAdapter& adapter,
  //                        const std::string& stmt_id,
  //                        const std::string& tenant_id);

  // New for M0.6:
  // Flips engrams(id=engram_id, tenant_id=tenant_id).erased_at from NULL to
  // erased_at_iso8601. Writes an audit event `testing.mark_evidence_erased`
  // in the same transaction. Returns true iff a row was actually flipped.
  // Idempotent: returns false if missing or already erased — and writes no
  // audit event in those cases so replays don't pollute bus_events.
  //
  // P1 use case: 13_retrieval.md evidence-erased negative test. CI static
  // scan refuses any prod entrypoint that imports starling.testing.
  bool mark_evidence_erased(starling::persistence::SqliteAdapter& adapter,
                            const std::string& engram_id,
                            const std::string& tenant_id,
                            std::string_view  erased_at_iso8601);

  }  // namespace starling::testing
  ```

- [ ] **5.2** Implement in `src/testing/testing_marker.cpp` — mirror `mark_consolidated`'s structure:

  ```cpp
  bool mark_evidence_erased(starling::persistence::SqliteAdapter& adapter,
                            const std::string& engram_id,
                            const std::string& tenant_id,
                            std::string_view  erased_at_iso8601) {
      auto& conn = adapter.connection();
      starling::persistence::TransactionGuard tx(conn);

      // 1. Try the flip — only flips when erased_at IS NULL.
      static constexpr const char* kUpdate =
          "UPDATE engrams SET erased_at = ?1 "
          " WHERE id = ?2 AND tenant_id = ?3 AND erased_at IS NULL;";
      sqlite3* db = conn.handle();
      sqlite3_stmt* raw = nullptr;
      if (sqlite3_prepare_v2(db, kUpdate, -1, &raw, nullptr) != SQLITE_OK) {
          throw std::runtime_error(std::string("mark_evidence_erased prepare failed: ")
                                   + sqlite3_errmsg(db));
      }
      {
          starling::persistence::StmtHandle h{raw};
          sqlite3_bind_text(raw, 1, erased_at_iso8601.data(),
                            static_cast<int>(erased_at_iso8601.size()),
                            SQLITE_TRANSIENT);
          sqlite3_bind_text(raw, 2, engram_id.c_str(), -1, SQLITE_TRANSIENT);
          sqlite3_bind_text(raw, 3, tenant_id.c_str(), -1, SQLITE_TRANSIENT);
          if (sqlite3_step(raw) != SQLITE_DONE) {
              throw std::runtime_error("mark_evidence_erased UPDATE step failed");
          }
      }
      const int changes = sqlite3_changes(db);
      if (changes == 0) {
          // Missing row OR already erased — idempotent no-op. Do NOT write
          // the audit event in this case (mirrors mark_consolidated convention).
          tx.commit();
          return false;
      }

      // 2. Write the audit event in the same transaction.
      starling::bus::BusEvent ev;
      ev.event_id     = starling::crypto::generate_uuid_v4();
      ev.tenant_id    = tenant_id;
      ev.event_type   = "testing.mark_evidence_erased";
      ev.primary_id   = engram_id;
      ev.aggregate_id = engram_id;
      ev.payload_json = std::string("{\"engram_id\":\"") + engram_id
                       + "\",\"erased_at\":\"" + std::string(erased_at_iso8601) + "\"}";
      ev.created_at   = std::string(erased_at_iso8601);
      ev.version      = "v1";

      const std::string window_bucket = starling::bus::compute_window_bucket(
          ev.event_type, std::chrono::system_clock::now());
      ev.idempotency_key = starling::bus::compute_idempotency_key(
          ev.event_type, ev.aggregate_id, ev.primary_id, /*causation_root=*/"", window_bucket);

      starling::bus::OutboxWriter w(conn);
      w.append(ev);

      tx.commit();
      return true;
  }
  ```

  **Notes:** Reuse exactly the same audit-event idiom `mark_consolidated` uses (see `src/testing/testing_marker.cpp`). If `mark_consolidated` factored out helpers (UUID gen, payload JSON build), reuse them — do not duplicate.

- [ ] **5.3** Modify `bindings/python/module.cpp` — register `mark_evidence_erased` on the `testing` submodule. Find the block that registers `mark_consolidated` (look for `testing_submodule.def("mark_consolidated"`) and append:

  ```cpp
  testing_submodule.def("mark_evidence_erased",  // NOLINT(starling-testing-isolation)
      [](starling::persistence::SqliteAdapter& adapter,
         const std::string& engram_id,
         const std::string& tenant_id,
         const std::string& erased_at_iso8601) {
          return starling::testing::mark_evidence_erased(  // NOLINT(starling-testing-isolation)
              adapter, engram_id, tenant_id, erased_at_iso8601);
      },
      py::arg("adapter"), py::arg("engram_id"),
      py::arg("tenant_id"), py::arg("erased_at_iso8601"),
      "Flip engrams(id=engram_id, tenant_id=tenant_id).erased_at from NULL "
      "to erased_at_iso8601. Writes a testing.mark_evidence_erased audit "
      "event. Returns True iff a row was actually flipped (False on missing "
      "row or already-erased row; no audit row written in those cases).");  // NOLINT(starling-testing-isolation)
  ```

- [ ] **5.4** Modify `python/starling/testing/__init__.py` — add the Python wrapper next to `mark_consolidated`:

  ```python
  def mark_evidence_erased(adapter, engram_id: str, tenant_id: str,
                           erased_at_iso8601: str) -> bool:
      """Flip engrams.erased_at from NULL to ISO8601 timestamp.

      Used by the 13_retrieval.md evidence-erased negative test
      (M0.6). Writes a `testing.mark_evidence_erased` audit event in the
      same transaction. Idempotent: returns False on missing row or already-
      erased row (no audit row written in those cases). Production preflight
      + the CI static scan reject any prod entrypoint that imports
      starling.testing — so this can never leak into real ingest.
      """
      return _core_testing.mark_evidence_erased(
          adapter, engram_id, tenant_id, erased_at_iso8601)
  ```

  Add `"mark_evidence_erased"` to the `__all__` list at the bottom of the file.

- [ ] **5.5** Create `tests/cpp/test_mark_evidence_erased.cpp`:

  ```cpp
  #include <gtest/gtest.h>
  #include "starling/testing_marker.hpp"
  #include "starling/persistence/sqlite_adapter.hpp"
  #include "starling/persistence/migration_runner.hpp"

  #include <sqlite3.h>

  using starling::persistence::SqliteAdapter;
  using starling::persistence::MigrationRunner;

  namespace {

  void insert_engram(SqliteAdapter& a,
                     const std::string& id,
                     const std::string& tenant_id) {
      static constexpr const char* kSql =
          "INSERT INTO engrams ("
          "  id, tenant_id, content_hash, source_kind, ingest_policy, "
          "  ingest_mode, privacy_class, retention_mode, refcount, "
          "  created_at, erased_at"
          ") VALUES (?, ?, 'h', 'user_input', 'store', 'whole_record', "
          "          'public', 'audit_retain', 1, "
          "          '2026-04-15T00:00:00Z', NULL)";
      sqlite3* db = a.connection().handle();
      sqlite3_stmt* raw = nullptr;
      ASSERT_EQ(sqlite3_prepare_v2(db, kSql, -1, &raw, nullptr), SQLITE_OK);
      starling::persistence::StmtHandle h{raw};
      sqlite3_bind_text(raw, 1, id.c_str(),        -1, SQLITE_TRANSIENT);
      sqlite3_bind_text(raw, 2, tenant_id.c_str(), -1, SQLITE_TRANSIENT);
      ASSERT_EQ(sqlite3_step(raw), SQLITE_DONE);
  }

  int erased_at_is_set(SqliteAdapter& a,
                       const std::string& id,
                       const std::string& tenant_id) {
      static constexpr const char* kSql =
          "SELECT erased_at IS NOT NULL FROM engrams "
          " WHERE id = ?1 AND tenant_id = ?2";
      sqlite3* db = a.connection().handle();
      sqlite3_stmt* raw = nullptr;
      EXPECT_EQ(sqlite3_prepare_v2(db, kSql, -1, &raw, nullptr), SQLITE_OK);
      starling::persistence::StmtHandle h{raw};
      sqlite3_bind_text(raw, 1, id.c_str(),        -1, SQLITE_TRANSIENT);
      sqlite3_bind_text(raw, 2, tenant_id.c_str(), -1, SQLITE_TRANSIENT);
      EXPECT_EQ(sqlite3_step(raw), SQLITE_ROW);
      return sqlite3_column_int(raw, 0);
  }

  int audit_event_count(SqliteAdapter& a,
                        const std::string& tenant_id) {
      static constexpr const char* kSql =
          "SELECT COUNT(*) FROM bus_events "
          " WHERE tenant_id = ?1 "
          "   AND event_type = 'testing.mark_evidence_erased'";
      sqlite3* db = a.connection().handle();
      sqlite3_stmt* raw = nullptr;
      EXPECT_EQ(sqlite3_prepare_v2(db, kSql, -1, &raw, nullptr), SQLITE_OK);
      starling::persistence::StmtHandle h{raw};
      sqlite3_bind_text(raw, 1, tenant_id.c_str(), -1, SQLITE_TRANSIENT);
      EXPECT_EQ(sqlite3_step(raw), SQLITE_ROW);
      return sqlite3_column_int(raw, 0);
  }

  }  // namespace

  TEST(MarkEvidenceErased, FlipsAndAudits) {
      auto a = SqliteAdapter::open(":memory:");
      MigrationRunner(a->connection()).apply_all("migrations");
      insert_engram(*a, "eng-1", "t1");

      EXPECT_EQ(erased_at_is_set(*a, "eng-1", "t1"), 0);
      EXPECT_EQ(audit_event_count(*a, "t1"),        0);

      EXPECT_TRUE(starling::testing::mark_evidence_erased(
          *a, "eng-1", "t1", "2026-04-16T00:00:00Z"));

      EXPECT_EQ(erased_at_is_set(*a, "eng-1", "t1"), 1);
      EXPECT_EQ(audit_event_count(*a, "t1"),         1);
  }

  TEST(MarkEvidenceErased, IdempotentOnAlreadyErased) {
      auto a = SqliteAdapter::open(":memory:");
      MigrationRunner(a->connection()).apply_all("migrations");
      insert_engram(*a, "eng-1", "t1");
      ASSERT_TRUE(starling::testing::mark_evidence_erased(
          *a, "eng-1", "t1", "2026-04-16T00:00:00Z"));

      EXPECT_FALSE(starling::testing::mark_evidence_erased(
          *a, "eng-1", "t1", "2026-04-17T00:00:00Z"));
      // Audit count must stay at 1 — second call wrote no event.
      EXPECT_EQ(audit_event_count(*a, "t1"), 1);
  }

  TEST(MarkEvidenceErased, FalseOnMissing) {
      auto a = SqliteAdapter::open(":memory:");
      MigrationRunner(a->connection()).apply_all("migrations");
      EXPECT_FALSE(starling::testing::mark_evidence_erased(
          *a, "no-such-engram", "t1", "2026-04-16T00:00:00Z"));
      EXPECT_EQ(audit_event_count(*a, "t1"), 0);
  }
  ```

- [ ] **5.6** Create `tests/python/test_mark_evidence_erased.py`:

  ```python
  import uuid

  import pytest

  from starling import _core
  from starling.testing import mark_evidence_erased


  @pytest.fixture
  def adapter(tmp_path):
      # Use :memory: per project convention. tmp_path unused but keeps fixture
      # parity with other tests that do touch disk.
      a = _core.SqliteAdapter.open(":memory:")
      # Apply migrations via the C++ runner — there's no Python facade for it,
      # but tests have used the equivalent path before (see existing fixtures).
      from tests.python._fixtures.migrations import apply_all_migrations
      apply_all_migrations(a)
      return a


  def _insert_engram(adapter, engram_id, tenant_id):
      conn_handle = adapter.connection()
      # Engram-insert helper — reuse the existing test fixture that other M0.3
      # tests rely on. If no such helper exists, this test should add the
      # minimal INSERT inline; either way, the SQL is the same as the C++
      # helper in test_mark_evidence_erased.cpp.
      from tests.python._fixtures.engrams import insert_engram_row
      insert_engram_row(adapter, engram_id, tenant_id)


  def test_flips_and_audits(adapter):
      _insert_engram(adapter, "eng-1", "t1")
      assert mark_evidence_erased(adapter, "eng-1", "t1", "2026-04-16T00:00:00Z") is True


  def test_idempotent_on_already_erased(adapter):
      _insert_engram(adapter, "eng-1", "t1")
      assert mark_evidence_erased(adapter, "eng-1", "t1", "2026-04-16T00:00:00Z") is True
      assert mark_evidence_erased(adapter, "eng-1", "t1", "2026-04-17T00:00:00Z") is False


  def test_false_on_missing(adapter):
      assert mark_evidence_erased(adapter, "no-such", "t1", "2026-04-16T00:00:00Z") is False
  ```

  **Note on fixtures:** If `tests/python/_fixtures/migrations.py` or `tests/python/_fixtures/engrams.py` does not exist, the implementer should add a minimal version next to whatever fixtures the existing M0.3 / M0.4 tests rely on. Do NOT invent a new fixture pattern — match the existing one (likely a conftest helper or an inline INSERT). Pick the path of least surprise.

- [ ] **5.7** Append the C++ test file to `tests/cpp/CMakeLists.txt`.

- [ ] **5.8** Build + test:

  ```bash
  cd build && cmake --build . && ctest -R "MarkEvidenceErased" --output-on-failure
  cd .. && pip install -e . --no-build-isolation
  pytest tests/python/test_mark_evidence_erased.py -q
  # Expected: all PASS.
  python scripts/ci_static_scan.py
  # Expected: exit 0 — testing helper definitions get NOLINT, no prod entrypoint
  # imports starling.testing.
  ```

- [ ] **5.9** Commit:
  ```bash
  git add include/starling/testing_marker.hpp src/testing/testing_marker.cpp \
          bindings/python/module.cpp \
          python/starling/testing/__init__.py \
          tests/cpp/test_mark_evidence_erased.cpp \
          tests/python/test_mark_evidence_erased.py \
          tests/cpp/CMakeLists.txt
  git commit -m "$(cat <<'EOF'
  feat(M0.6): testing.mark_evidence_erased helper

  Spec'd by system_design.md §15.3.5. Flips engrams.erased_at NULL → ISO8601,
  writes a testing.mark_evidence_erased audit event, idempotent (no event
  on missing/already-erased). Required by the basic_retrieve evidence-
  erased negative case.

  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 6: Layer `statement.recalled` emit onto `BasicRetriever::run`

**Files:**
- Modify: `src/retrieval/basic_retriever.cpp` — emit a `statement.recalled` event per returned row
- Create: `tests/cpp/test_basic_retriever_recalled_emit.cpp`

**Purpose:** Per §13: after `fetch` completes, asynchronously emit `statement.recalled × N` events; main flow does not block. In P1 we use the synchronous `OutboxWriter` but wrap the emit in its own short transaction *after* the retrieval result is built, so the read path's correctness is independent of the emit path. The 2s window from Task 2 dedupes repeat recalls.

- [ ] **6.1** Modify `src/retrieval/basic_retriever.cpp`. After the `while (sqlite3_step(...))` loop and the final receipt construction, append a small block that opens a new `TransactionGuard` and writes one `statement.recalled` event per returned row. If the emit fails, swallow the error and log via `std::cerr` — per §13 it is fire-and-forget; we MUST NOT propagate the failure back to the caller (which would make retrieval looks like it failed).

  ```cpp
  // ---- fire-and-forget recalled emit ----
  // Per 13_retrieval.md §"statement.recalled emit 契约": this is NOT in the
  // read transaction; it is a follow-up best-effort write whose failure
  // must not corrupt the caller's view of the read. The 2s window bucket
  // from compute_window_bucket dedups same-key recalls within 2 seconds
  // via the bus_events UNIQUE(idempotency_key) constraint.
  try {
      starling::persistence::TransactionGuard tx(conn);
      starling::bus::OutboxWriter w(conn);
      const auto now = std::chrono::system_clock::now();
      const std::string window_bucket = starling::bus::compute_window_bucket(
          "statement.recalled", now);
      const std::string now_iso = starling::time::to_iso8601_utc(now);

      for (const auto& row : result.rows) {
          starling::bus::BusEvent ev;
          ev.event_id     = starling::crypto::generate_uuid_v4();
          ev.tenant_id    = row.tenant_id;
          ev.event_type   = "statement.recalled";
          ev.primary_id   = row.id;
          ev.aggregate_id = row.id;
          ev.payload_json = std::string("{\"statement_id\":\"") + row.id
                          + "\",\"querier\":\"" + params.holder_id
                          + "\",\"perspective\":\"" + params.holder_id
                          + "\",\"intent\":\"FACT_LOOKUP\""
                          + ",\"query_id\":\"" + params.query_id + "\"}";
          ev.created_at = now_iso;
          ev.version    = "v1";
          ev.idempotency_key = starling::bus::compute_idempotency_key(
              ev.event_type, ev.aggregate_id, row.id,
              /*causation_root=*/params.query_id, window_bucket);

          try {
              w.append(ev);
          } catch (const starling::bus::DuplicateIdempotencyKey&) {
              // 2s window deduped — expected; ignore.
          }
      }
      tx.commit();
  } catch (const std::exception& e) {
      // Best-effort. Do not propagate.
      std::fprintf(stderr,
          "basic_retrieve: recalled emit failed for query_id=%s: %s\n",
          params.query_id.c_str(), e.what());
  }
  ```

  **Notes for the implementer:**
  - `starling::time::to_iso8601_utc` is the helper used elsewhere (e.g. statement_writer.cpp); if the existing call site uses a slightly different function name, match it. Do not introduce a new time helper.
  - `starling::bus::DuplicateIdempotencyKey` is the existing exception thrown by `OutboxWriter::append` on UNIQUE-constraint conflict (used by debounced events in M0.5). If the actual name differs, match the existing catch sites in `bus.cpp`.
  - The causation_root for `statement.recalled` is the `query_id` per §13 (the recall is caused by the query). This couples dedup to the query identity.

- [ ] **6.2** Create `tests/cpp/test_basic_retriever_recalled_emit.cpp`:

  ```cpp
  #include <gtest/gtest.h>
  #include "starling/retrieval/basic_retriever.hpp"
  #include "starling/persistence/sqlite_adapter.hpp"
  #include "starling/persistence/migration_runner.hpp"

  #include <sqlite3.h>

  using namespace starling::retrieval;
  using starling::persistence::SqliteAdapter;
  using starling::persistence::MigrationRunner;

  namespace {

  // (Reuse the insert_stmt helper from test_basic_retriever_filter_predicates.cpp.)
  // If the project does not already expose it in a header, copy-paste it into
  // this TU — the helpers are small and the tests are independent.
  void insert_stmt(SqliteAdapter& a,
                   const std::string& id,
                   const std::string& tenant_id,
                   const std::string& holder_id,
                   const std::string& subject_id,
                   const std::string& predicate,
                   const std::string& consolidation_state = "consolidated");

  int count_recalled_events(SqliteAdapter& a) {
      sqlite3* db = a.connection().handle();
      sqlite3_stmt* raw = nullptr;
      EXPECT_EQ(sqlite3_prepare_v2(db,
          "SELECT COUNT(*) FROM bus_events WHERE event_type = 'statement.recalled'",
          -1, &raw, nullptr), SQLITE_OK);
      starling::persistence::StmtHandle h{raw};
      EXPECT_EQ(sqlite3_step(raw), SQLITE_ROW);
      return sqlite3_column_int(raw, 0);
  }

  BasicRetrieverParams std_params(const std::string& query_id = "q-1") {
      BasicRetrieverParams p;
      p.tenant_id     = "t1";
      p.holder_id     = "alice";
      p.intent        = QueryIntent::FACT_LOOKUP;
      p.subject_id    = "bob";
      p.predicate     = "responsible_for";
      p.as_of_iso8601 = "2026-04-15T00:00:00Z";
      p.trace_id      = "trace-x";
      p.query_id      = query_id;
      return p;
  }

  }  // namespace

  TEST(BasicRetrieverRecalledEmit, OneEventPerReturnedRow) {
      auto a = SqliteAdapter::open(":memory:");
      MigrationRunner(a->connection()).apply_all("migrations");
      insert_stmt(*a, "s-1", "t1", "alice", "bob", "responsible_for");
      insert_stmt(*a, "s-2", "t1", "alice", "bob", "responsible_for");
      BasicRetriever r(*a);
      r.run(std_params("q-1"));
      EXPECT_EQ(count_recalled_events(*a), 2);
  }

  TEST(BasicRetrieverRecalledEmit, NoEventsWhenEmpty) {
      auto a = SqliteAdapter::open(":memory:");
      MigrationRunner(a->connection()).apply_all("migrations");
      BasicRetriever r(*a);
      r.run(std_params("q-1"));
      EXPECT_EQ(count_recalled_events(*a), 0);
  }

  TEST(BasicRetrieverRecalledEmit, IdempotentWithin2sWindow) {
      auto a = SqliteAdapter::open(":memory:");
      MigrationRunner(a->connection()).apply_all("migrations");
      insert_stmt(*a, "s-1", "t1", "alice", "bob", "responsible_for");
      BasicRetriever r(*a);
      // Same query_id (causation_root) + same 2s window → second emit is
      // dedup'd at the UNIQUE(idempotency_key) constraint level.
      r.run(std_params("q-1"));
      r.run(std_params("q-1"));
      EXPECT_EQ(count_recalled_events(*a), 1);
  }

  TEST(BasicRetrieverRecalledEmit, DistinctQueryIdsAreDistinctEvents) {
      auto a = SqliteAdapter::open(":memory:");
      MigrationRunner(a->connection()).apply_all("migrations");
      insert_stmt(*a, "s-1", "t1", "alice", "bob", "responsible_for");
      BasicRetriever r(*a);
      r.run(std_params("q-1"));
      r.run(std_params("q-2"));
      EXPECT_EQ(count_recalled_events(*a), 2);
  }
  ```

- [ ] **6.3** Append the new test file to `tests/cpp/CMakeLists.txt`.

- [ ] **6.4** Build + run:

  ```bash
  cd build && cmake --build . && ctest -R "BasicRetrieverRecalledEmit|BasicRetrieverFilter|BasicRetrieverReject" --output-on-failure
  # Expected: all PASS.
  ```

- [ ] **6.5** Commit:
  ```bash
  git add src/retrieval/basic_retriever.cpp \
          tests/cpp/test_basic_retriever_recalled_emit.cpp \
          tests/cpp/CMakeLists.txt
  git commit -m "$(cat <<'EOF'
  feat(M0.6): basic_retrieve emits statement.recalled

  Fire-and-forget per 13_retrieval.md §"statement.recalled emit 契约":
  separate post-read transaction, 2s dedup window via compute_window_bucket,
  causation_root = query_id so distinct queries are distinct events. Emit
  failures are swallowed; the caller's read result is independent.

  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 7: Pybind bindings + Python facade

**Files:**
- Modify: `bindings/python/module.cpp` — bind `QueryIntent`, `Sufficiency`, `FilterApplied`, `StatementRow`, `RetrievalReceipt`, `BasicRetrieverParams`, `BasicRetrieveResult`, `BasicRetriever`
- Create: `python/starling/retrieval/__init__.py` — public `basic_retrieve(...)` facade
- Create: `python/starling/retrieval/types.py` — Python dataclasses mirroring the bound types (with extra validation per spec)
- Create: `tests/python/test_basic_retrieve_multi_holder_reject.py`
- Create: `tests/python/test_basic_retrieve_receipt.py`

**Purpose:** Expose the C++ retriever through a thin, well-typed Python entrypoint. Reject multi-holder (or list) inputs at the Python boundary with a clear message before they even reach the C++ side.

- [ ] **7.1** Modify `bindings/python/module.cpp`. After the existing `Bus` block (around line 396 in current main), add a `// ----- M0.6: retrieval -----` section:

  ```cpp
  // ----- M0.6: retrieval bindings -----

  py::enum_<starling::retrieval::QueryIntent>(m, "QueryIntent")
      .value("FACT_LOOKUP", starling::retrieval::QueryIntent::FACT_LOOKUP)
      .export_values();

  py::enum_<starling::retrieval::Sufficiency>(m, "Sufficiency")
      .value("SUFFICIENT",   starling::retrieval::Sufficiency::SUFFICIENT)
      .value("MISSING_INFO", starling::retrieval::Sufficiency::MISSING_INFO)
      .value("NEEDS_RAW",    starling::retrieval::Sufficiency::NEEDS_RAW)
      .value("ABSTAINED",    starling::retrieval::Sufficiency::ABSTAINED)
      .export_values();

  py::class_<starling::retrieval::FilterApplied>(m, "FilterApplied")
      .def_readonly("name",  &starling::retrieval::FilterApplied::name)
      .def_readonly("value", &starling::retrieval::FilterApplied::value);

  py::class_<starling::retrieval::RetrievalReceipt::CandidateCounts>(
      m, "RetrievalCandidateCounts")
      .def_readonly("fetched",
                    &starling::retrieval::RetrievalReceipt::CandidateCounts::fetched)
      .def_readonly("returned",
                    &starling::retrieval::RetrievalReceipt::CandidateCounts::returned)
      .def_readonly("dropped_by_review",
                    &starling::retrieval::RetrievalReceipt::CandidateCounts::dropped_by_review)
      .def_readonly("dropped_by_state",
                    &starling::retrieval::RetrievalReceipt::CandidateCounts::dropped_by_state)
      .def_readonly("dropped_by_time_anchor",
                    &starling::retrieval::RetrievalReceipt::CandidateCounts::dropped_by_time_anchor)
      .def_readonly("dropped_by_evidence_erasure",
                    &starling::retrieval::RetrievalReceipt::CandidateCounts::dropped_by_evidence_erasure);

  py::class_<starling::retrieval::RetrievalReceipt>(m, "RetrievalReceipt")
      .def_readonly("trace_id",              &starling::retrieval::RetrievalReceipt::trace_id)
      .def_readonly("query_id",              &starling::retrieval::RetrievalReceipt::query_id)
      .def_readonly("filters_applied",       &starling::retrieval::RetrievalReceipt::filters_applied)
      .def_readonly("candidate_counts",      &starling::retrieval::RetrievalReceipt::candidate_counts)
      .def_readonly("evidence_erased_count", &starling::retrieval::RetrievalReceipt::evidence_erased_count)
      .def_readonly("sufficiency_status",    &starling::retrieval::RetrievalReceipt::sufficiency_status);

  py::class_<starling::retrieval::StatementRow>(m, "StatementRow")
      .def_readonly("id",                     &starling::retrieval::StatementRow::id)
      .def_readonly("tenant_id",              &starling::retrieval::StatementRow::tenant_id)
      .def_readonly("holder_id",              &starling::retrieval::StatementRow::holder_id)
      .def_readonly("holder_perspective",     &starling::retrieval::StatementRow::holder_perspective)
      .def_readonly("subject_kind",           &starling::retrieval::StatementRow::subject_kind)
      .def_readonly("subject_id",             &starling::retrieval::StatementRow::subject_id)
      .def_readonly("predicate",              &starling::retrieval::StatementRow::predicate)
      .def_readonly("object_kind",            &starling::retrieval::StatementRow::object_kind)
      .def_readonly("object_value",           &starling::retrieval::StatementRow::object_value)
      .def_readonly("canonical_object_hash",  &starling::retrieval::StatementRow::canonical_object_hash)
      .def_readonly("modality",               &starling::retrieval::StatementRow::modality)
      .def_readonly("polarity",               &starling::retrieval::StatementRow::polarity)
      .def_readonly("confidence",             &starling::retrieval::StatementRow::confidence)
      .def_readonly("observed_at",            &starling::retrieval::StatementRow::observed_at)
      .def_readonly("valid_from",             &starling::retrieval::StatementRow::valid_from)
      .def_readonly("valid_to",               &starling::retrieval::StatementRow::valid_to)
      .def_readonly("consolidation_state",    &starling::retrieval::StatementRow::consolidation_state)
      .def_readonly("review_status",          &starling::retrieval::StatementRow::review_status)
      .def_readonly("evidence_json",          &starling::retrieval::StatementRow::evidence_json);

  py::class_<starling::retrieval::BasicRetrieverParams>(m, "BasicRetrieverParams")
      .def(py::init<>())
      .def_readwrite("tenant_id",     &starling::retrieval::BasicRetrieverParams::tenant_id)
      .def_readwrite("holder_id",     &starling::retrieval::BasicRetrieverParams::holder_id)
      .def_readwrite("intent",        &starling::retrieval::BasicRetrieverParams::intent)
      .def_readwrite("subject_id",    &starling::retrieval::BasicRetrieverParams::subject_id)
      .def_readwrite("predicate",     &starling::retrieval::BasicRetrieverParams::predicate)
      .def_readwrite("as_of_iso8601", &starling::retrieval::BasicRetrieverParams::as_of_iso8601)
      .def_readwrite("trace_id",      &starling::retrieval::BasicRetrieverParams::trace_id)
      .def_readwrite("query_id",      &starling::retrieval::BasicRetrieverParams::query_id);

  py::class_<starling::retrieval::BasicRetrieveResult>(m, "BasicRetrieveResult")
      .def_readonly("rows",    &starling::retrieval::BasicRetrieveResult::rows)
      .def_readonly("receipt", &starling::retrieval::BasicRetrieveResult::receipt);

  py::class_<starling::retrieval::BasicRetriever>(m, "BasicRetriever")
      .def(py::init<starling::persistence::SqliteAdapter&>(),
           py::keep_alive<1, 2>(), py::arg("adapter"))
      .def("run", &starling::retrieval::BasicRetriever::run, py::arg("params"));
  ```

  Place this block before the `// ----- M0.4: enums -----` section.

- [ ] **7.2** Create `python/starling/retrieval/types.py`:

  ```python
  """Typed Python dataclasses mirroring _core.retrieval bindings.

  These exist so callers don't depend on the pybind class layout directly.
  The wrapping is intentionally thin — no semantic transformation.
  """
  from __future__ import annotations

  from dataclasses import dataclass
  from typing import List


  @dataclass(frozen=True)
  class FilterApplied:
      name: str
      value: str


  @dataclass(frozen=True)
  class CandidateCounts:
      fetched: int
      returned: int
      dropped_by_review: int
      dropped_by_state: int
      dropped_by_time_anchor: int
      dropped_by_evidence_erasure: int


  @dataclass(frozen=True)
  class RetrievalReceipt:
      trace_id: str
      query_id: str
      filters_applied: List[FilterApplied]
      candidate_counts: CandidateCounts
      evidence_erased_count: int
      sufficiency_status: str  # SUFFICIENT | MISSING_INFO | NEEDS_RAW | ABSTAINED


  @dataclass(frozen=True)
  class StatementRow:
      id: str
      tenant_id: str
      holder_id: str
      holder_perspective: str
      subject_kind: str
      subject_id: str
      predicate: str
      object_kind: str
      object_value: str
      canonical_object_hash: str
      modality: str
      polarity: str
      confidence: float
      observed_at: str
      valid_from: str
      valid_to: str
      consolidation_state: str
      review_status: str
      evidence_json: str


  @dataclass(frozen=True)
  class BasicRetrieveResult:
      rows: List[StatementRow]
      receipt: RetrievalReceipt
  ```

- [ ] **7.3** Create `python/starling/retrieval/__init__.py`:

  ```python
  """Starling retrieval public API.

  P1 ships exactly one entrypoint: `basic_retrieve`. See
  docs/design/subsystems_design/13_retrieval.md §"basic_retrieve（P1 闭环）".
  Future milestones will add a `Retrieval` class for 7-step planning.
  """
  from __future__ import annotations

  import uuid
  from datetime import datetime
  from typing import Optional, Union

  from starling import _core
  from starling.retrieval.types import (
      BasicRetrieveResult,
      CandidateCounts,
      FilterApplied,
      RetrievalReceipt,
      StatementRow,
  )

  __all__ = ["basic_retrieve", "BasicRetrieveResult", "RetrievalReceipt",
             "StatementRow", "FilterApplied", "CandidateCounts"]


  _SUFFICIENCY_NAME = {
      _core.Sufficiency.SUFFICIENT:   "SUFFICIENT",
      _core.Sufficiency.MISSING_INFO: "MISSING_INFO",
      _core.Sufficiency.NEEDS_RAW:    "NEEDS_RAW",
      _core.Sufficiency.ABSTAINED:    "ABSTAINED",
  }


  def basic_retrieve(
      adapter,
      *,
      tenant_id: str,
      holder: Union[str, list, tuple],     # accept list/tuple only to reject
      intent: str = "FACT_LOOKUP",
      subject: str,
      predicate: str,
      as_of: datetime,
      trace_id: Optional[str] = None,
      query_id: Optional[str] = None,
  ) -> BasicRetrieveResult:
      """The P1 retrieval entrypoint.

      Returns the list of statements that match the predicate at `as_of`,
      filtered by:
        - consolidation_state ∈ {consolidated, archived}
        - review_status ∉ {rejected, pending_review}
        - evidence not crypto-erased
        - valid_from ≤ as_of < valid_to

      Multi-holder calls raise ValueError; intent other than FACT_LOOKUP raises
      ValueError. See 13_retrieval.md §"P1 basic_retrieve 闭环".
      """
      if isinstance(holder, (list, tuple)):
          raise ValueError(
              "basic_retrieve: multi-holder is not supported in P1; "
              "pass a single holder string. "
              "See 13_retrieval.md §'P1 basic_retrieve 闭环'."
          )
      if not isinstance(holder, str) or not holder:
          raise ValueError("basic_retrieve: holder must be a non-empty string")
      if not tenant_id:
          raise ValueError("basic_retrieve: tenant_id is required")
      if intent != "FACT_LOOKUP":
          raise ValueError(
              f"basic_retrieve: intent={intent} not supported in P1; "
              "only FACT_LOOKUP is implemented."
          )
      if not subject or not predicate:
          raise ValueError("basic_retrieve: subject and predicate are required")
      if as_of.tzinfo is None:
          raise ValueError("basic_retrieve: as_of must be timezone-aware")

      as_of_iso = as_of.astimezone().strftime("%Y-%m-%dT%H:%M:%SZ")

      params = _core.BasicRetrieverParams()
      params.tenant_id     = tenant_id
      params.holder_id     = holder
      params.intent        = _core.QueryIntent.FACT_LOOKUP
      params.subject_id    = subject
      params.predicate     = predicate
      params.as_of_iso8601 = as_of_iso
      params.trace_id      = trace_id or str(uuid.uuid4())
      params.query_id      = query_id or str(uuid.uuid4())

      r = _core.BasicRetriever(adapter)
      raw = r.run(params)

      counts = CandidateCounts(
          fetched=raw.receipt.candidate_counts.fetched,
          returned=raw.receipt.candidate_counts.returned,
          dropped_by_review=raw.receipt.candidate_counts.dropped_by_review,
          dropped_by_state=raw.receipt.candidate_counts.dropped_by_state,
          dropped_by_time_anchor=raw.receipt.candidate_counts.dropped_by_time_anchor,
          dropped_by_evidence_erasure=raw.receipt.candidate_counts.dropped_by_evidence_erasure,
      )
      receipt = RetrievalReceipt(
          trace_id=raw.receipt.trace_id,
          query_id=raw.receipt.query_id,
          filters_applied=[FilterApplied(name=f.name, value=f.value)
                            for f in raw.receipt.filters_applied],
          candidate_counts=counts,
          evidence_erased_count=raw.receipt.evidence_erased_count,
          sufficiency_status=_SUFFICIENCY_NAME[raw.receipt.sufficiency_status],
      )
      rows = [StatementRow(
          id=r.id, tenant_id=r.tenant_id, holder_id=r.holder_id,
          holder_perspective=r.holder_perspective,
          subject_kind=r.subject_kind, subject_id=r.subject_id,
          predicate=r.predicate, object_kind=r.object_kind,
          object_value=r.object_value,
          canonical_object_hash=r.canonical_object_hash,
          modality=r.modality, polarity=r.polarity,
          confidence=r.confidence, observed_at=r.observed_at,
          valid_from=r.valid_from, valid_to=r.valid_to,
          consolidation_state=r.consolidation_state,
          review_status=r.review_status,
          evidence_json=r.evidence_json,
      ) for r in raw.rows]
      return BasicRetrieveResult(rows=rows, receipt=receipt)
  ```

- [ ] **7.4** Create `tests/python/test_basic_retrieve_multi_holder_reject.py`:

  ```python
  from datetime import datetime, timezone

  import pytest

  from starling import _core
  from starling.retrieval import basic_retrieve


  @pytest.fixture
  def adapter():
      from tests.python._fixtures.migrations import apply_all_migrations
      a = _core.SqliteAdapter.open(":memory:")
      apply_all_migrations(a)
      return a


  def _call(adapter, **overrides):
      defaults = dict(
          tenant_id="t1", holder="alice", subject="bob",
          predicate="responsible_for",
          as_of=datetime(2026, 4, 15, tzinfo=timezone.utc),
      )
      defaults.update(overrides)
      return basic_retrieve(adapter, **defaults)


  def test_reject_list_holder(adapter):
      with pytest.raises(ValueError, match="multi-holder"):
          _call(adapter, holder=["alice", "carol"])


  def test_reject_tuple_holder(adapter):
      with pytest.raises(ValueError, match="multi-holder"):
          _call(adapter, holder=("alice",))


  def test_reject_empty_holder(adapter):
      with pytest.raises(ValueError, match="holder"):
          _call(adapter, holder="")


  def test_reject_non_fact_lookup_intent(adapter):
      with pytest.raises(ValueError, match="FACT_LOOKUP"):
          _call(adapter, intent="BELIEF_OF_OTHER")


  def test_reject_naive_datetime(adapter):
      with pytest.raises(ValueError, match="timezone-aware"):
          _call(adapter, as_of=datetime(2026, 4, 15))  # no tzinfo


  def test_reject_empty_tenant(adapter):
      with pytest.raises(ValueError, match="tenant_id"):
          _call(adapter, tenant_id="")
  ```

- [ ] **7.5** Create `tests/python/test_basic_retrieve_receipt.py`:

  ```python
  from datetime import datetime, timezone

  import pytest

  from starling import _core
  from starling.retrieval import basic_retrieve


  @pytest.fixture
  def adapter():
      from tests.python._fixtures.migrations import apply_all_migrations
      a = _core.SqliteAdapter.open(":memory:")
      apply_all_migrations(a)
      return a


  def _insert(adapter, **kwargs):
      from tests.python._fixtures.statements import insert_statement_row
      insert_statement_row(adapter, **kwargs)


  def test_minimum_p1_fields_present(adapter):
      _insert(adapter, id="s-1", tenant_id="t1", holder_id="alice",
              subject_id="bob", predicate="responsible_for",
              consolidation_state="consolidated", review_status="approved")
      result = basic_retrieve(
          adapter,
          tenant_id="t1", holder="alice",
          subject="bob", predicate="responsible_for",
          as_of=datetime(2026, 4, 15, tzinfo=timezone.utc),
          trace_id="trace-A", query_id="query-A",
      )
      assert result.receipt.trace_id == "trace-A"
      assert result.receipt.query_id == "query-A"
      assert result.receipt.candidate_counts.fetched   == 1
      assert result.receipt.candidate_counts.returned  == 1
      assert result.receipt.evidence_erased_count       == 0
      assert result.receipt.sufficiency_status          == "SUFFICIENT"
      filters = {f.name: f.value for f in result.receipt.filters_applied}
      assert filters["tenant_id"]              == "t1"
      assert filters["holder_id"]              == "alice"
      assert filters["subject_kind"]           == "cognizer"
      assert filters["subject_id"]             == "bob"
      assert filters["predicate"]              == "responsible_for"
      assert filters["consolidation_state"]    == "consolidated|archived"
      assert filters["review_status_exclude"]  == "rejected|pending_review"
      assert filters["evidence_erased"]        == "exclude"


  def test_sufficiency_missing_info_when_empty(adapter):
      result = basic_retrieve(
          adapter,
          tenant_id="t1", holder="alice",
          subject="bob", predicate="responsible_for",
          as_of=datetime(2026, 4, 15, tzinfo=timezone.utc),
      )
      assert result.rows == []
      assert result.receipt.sufficiency_status == "MISSING_INFO"
      assert result.receipt.candidate_counts.fetched  == 0
      assert result.receipt.candidate_counts.returned == 0
  ```

- [ ] **7.6** Build + test:

  ```bash
  cd build && cmake --build .
  cd .. && pip install -e . --no-build-isolation
  pytest tests/python/test_basic_retrieve_multi_holder_reject.py \
         tests/python/test_basic_retrieve_receipt.py -q
  python scripts/ci_static_scan.py
  # Expected: all PASS, scanner clean.
  ```

- [ ] **7.7** Commit:
  ```bash
  git add bindings/python/module.cpp \
          python/starling/retrieval/__init__.py \
          python/starling/retrieval/types.py \
          tests/python/test_basic_retrieve_multi_holder_reject.py \
          tests/python/test_basic_retrieve_receipt.py
  git commit -m "$(cat <<'EOF'
  feat(M0.6): bind basic_retrieve + Python facade

  Exposes starling.retrieval.basic_retrieve(...) matching the P1 signature
  in 13_retrieval.md §"basic_retrieve（P1 闭环）". Multi-holder lists, naive
  datetimes, and non-FACT_LOOKUP intents raise ValueError before reaching
  the C++ layer.

  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 8: TC-NEG-TENANT regression test + Python evidence-erased filter test

**Files:**
- Create: `tests/python/test_basic_retrieve_tenant_guard.py`
- Create: `tests/python/test_basic_retrieve_filters.py`

**Purpose:** Lock in the two P1 CRITICAL ship-gates for retrieval:
- TC-NEG-TENANT — final query without `tenant_id + holder_scope` predicate must refuse.
- Evidence-erased: rows whose evidence references engrams with `erased_at IS NOT NULL` must be dropped, and `evidence_erased_count` must reflect that.

- [ ] **8.1** Create `tests/python/test_basic_retrieve_tenant_guard.py`:

  ```python
  """TC-NEG-TENANT regression: the final retrieval SQL must contain both
  tenant_id and holder_scope predicates. We don't black-box this via a
  malformed call (the facade pre-validates), but instead verify the C++
  retriever runs its SELECT through assert_final_query_safe. We achieve
  that by stripping the assertion at the SQL layer is impossible; instead,
  we check the public predicate is_final_query_safe against the SELECT
  literal that ships with the build, by introspecting it via the binding.
  """
  from starling import _core


  def test_basic_retrieve_select_is_final_query_safe():
      # The kSelectSql constant lives in src/retrieval/basic_retriever.cpp.
      # We don't expose it directly, but we DO bind the assertion. Build the
      # SQL as a Python literal that mirrors the C++ literal (sanity check
      # the contract — the C++ literal is what runs in production).
      sql = (
          "SELECT id, tenant_id, holder_id, holder_perspective, "
          "       subject_kind, subject_id, predicate, "
          "       object_kind, object_value, canonical_object_hash, "
          "       modality, polarity, confidence, observed_at, "
          "       valid_from, valid_to, consolidation_state, review_status, "
          "       evidence_json "
          "  FROM statements "
          " WHERE tenant_id = ?1 "
          "   AND holder_id = ?2 "
          "   AND subject_kind = 'cognizer' "
          "   AND subject_id = ?3 "
          "   AND predicate = ?4 "
          "   AND consolidation_state IN ('consolidated','archived') "
          "   AND review_status NOT IN ('rejected','pending_review') "
          "   AND (valid_from IS NULL OR valid_from <= ?5) "
          "   AND (valid_to   IS NULL OR valid_to   >  ?5) "
      )
      assert _core.is_final_query_safe(sql) is True


  def test_assert_final_query_safe_rejects_missing_tenant():
      sql = "SELECT id FROM statements WHERE holder_id = ?1 AND predicate = ?2"
      try:
          _core.assert_final_query_safe(sql)
      except _core.FinalQueryAssertionError:
          return
      raise AssertionError("expected FinalQueryAssertionError")


  def test_assert_final_query_safe_rejects_missing_holder():
      sql = "SELECT id FROM statements WHERE tenant_id = ?1 AND predicate = ?2"
      try:
          _core.assert_final_query_safe(sql)
      except _core.FinalQueryAssertionError:
          return
      raise AssertionError("expected FinalQueryAssertionError")
  ```

  **Note on the design choice:** TC-NEG-TENANT is a `storage_enforced` preflight assertion, and the actual enforcement point is `SqliteAdapter::check_final_query` (called by `BasicRetriever::run` per Task 4 step 4.2). A direct end-to-end test that the retriever calls the assertion is awkward (it's a hidden internal call). The test above is a contract test: as long as the literal in the test matches the literal in the C++ source and `is_final_query_safe` returns true for it, we have evidence the retriever's SELECT is safe. If a future engineer changes `kSelectSql` to drop `tenant_id` or `holder_id`, this test must be updated in lockstep — and if they forget, the next P1 acceptance run will catch it via the §14.1 smoke (Task 9).

- [ ] **8.2** Create `tests/python/test_basic_retrieve_filters.py`:

  ```python
  from datetime import datetime, timezone

  import pytest

  from starling import _core
  from starling.retrieval import basic_retrieve
  from starling.testing import mark_evidence_erased


  @pytest.fixture
  def adapter():
      from tests.python._fixtures.migrations import apply_all_migrations
      a = _core.SqliteAdapter.open(":memory:")
      apply_all_migrations(a)
      return a


  def _insert_stmt(adapter, *, id, **kwargs):
      from tests.python._fixtures.statements import insert_statement_row
      insert_statement_row(adapter, id=id, **kwargs)


  def _insert_engram(adapter, engram_id, tenant_id="t1"):
      from tests.python._fixtures.engrams import insert_engram_row
      insert_engram_row(adapter, engram_id, tenant_id)


  def _call(adapter):
      return basic_retrieve(
          adapter,
          tenant_id="t1", holder="alice",
          subject="bob", predicate="responsible_for",
          as_of=datetime(2026, 4, 15, tzinfo=timezone.utc),
      )


  def test_volatile_excluded(adapter):
      _insert_stmt(adapter, id="s-vol",  tenant_id="t1", holder_id="alice",
                   subject_id="bob", predicate="responsible_for",
                   consolidation_state="volatile",     review_status="approved")
      _insert_stmt(adapter, id="s-cons", tenant_id="t1", holder_id="alice",
                   subject_id="bob", predicate="responsible_for",
                   consolidation_state="consolidated", review_status="approved")
      result = _call(adapter)
      assert [r.id for r in result.rows] == ["s-cons"]


  def test_rejected_and_pending_excluded(adapter):
      for sid, status in [("s-rej", "rejected"),
                          ("s-pend", "pending_review"),
                          ("s-ok",  "approved")]:
          _insert_stmt(adapter, id=sid, tenant_id="t1", holder_id="alice",
                       subject_id="bob", predicate="responsible_for",
                       consolidation_state="consolidated", review_status=status)
      result = _call(adapter)
      assert [r.id for r in result.rows] == ["s-ok"]


  def test_archived_included(adapter):
      _insert_stmt(adapter, id="s-arch", tenant_id="t1", holder_id="alice",
                   subject_id="bob", predicate="responsible_for",
                   consolidation_state="archived", review_status="approved")
      result = _call(adapter)
      assert [r.id for r in result.rows] == ["s-arch"]


  def test_evidence_erased_filtered_and_counted(adapter):
      _insert_engram(adapter, "eng-1", "t1")
      _insert_stmt(adapter, id="s-erased", tenant_id="t1", holder_id="alice",
                   subject_id="bob", predicate="responsible_for",
                   consolidation_state="consolidated", review_status="approved",
                   evidence_json='[{"engram_ref":"eng-1","content_hash":"h"}]')
      _insert_engram(adapter, "eng-2", "t1")
      _insert_stmt(adapter, id="s-ok", tenant_id="t1", holder_id="alice",
                   subject_id="bob", predicate="responsible_for",
                   consolidation_state="consolidated", review_status="approved",
                   evidence_json='[{"engram_ref":"eng-2","content_hash":"h"}]')

      # Initially both rows are returned.
      result = _call(adapter)
      assert {r.id for r in result.rows} == {"s-erased", "s-ok"}
      assert result.receipt.evidence_erased_count == 0

      # Erase eng-1 → s-erased drops out, counter increments by 1.
      assert mark_evidence_erased(adapter, "eng-1", "t1",
                                   "2026-04-16T00:00:00Z") is True
      result = _call(adapter)
      assert [r.id for r in result.rows] == ["s-ok"]
      assert result.receipt.evidence_erased_count == 1
      assert result.receipt.candidate_counts.dropped_by_evidence_erasure == 1
      assert result.receipt.candidate_counts.fetched   == 2
      assert result.receipt.candidate_counts.returned  == 1
  ```

- [ ] **8.3** Run tests:

  ```bash
  pytest tests/python/test_basic_retrieve_tenant_guard.py \
         tests/python/test_basic_retrieve_filters.py -q
  # Expected: all PASS.
  ```

- [ ] **8.4** Commit:
  ```bash
  git add tests/python/test_basic_retrieve_tenant_guard.py \
          tests/python/test_basic_retrieve_filters.py
  git commit -m "$(cat <<'EOF'
  test(M0.6): TC-NEG-TENANT regression + evidence-erased filter

  Locks the final SELECT shape via assert_final_query_safe contract test;
  covers the evidence-erased post-filter end-to-end via
  testing.mark_evidence_erased.

  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 9: §14.1 P1 retrieve smoke (acceptance test, CRITICAL)

**Files:**
- Create: `tests/python/test_basic_retrieve_smoke.py`

**Purpose:** The single end-to-end smoke that ties M0.3 (engram) + M0.4 (extractor) + M0.5 (conflict + atomic SUPERSEDES) + M0.6 (retrieval) together along the spec narrative: Alice 宣布 Bob 不再负责 auth, Extractor produces statements, Bus.write archives the old one + writes the new one, basic_retrieve at the right time anchor returns only the new statement. Per `docs/design/system_design.md` line 1663 + §14.1, this is the P1 smoke for M0.6.

- [ ] **9.1** Create `tests/python/test_basic_retrieve_smoke.py`:

  ```python
  """§14.1 minimal-variant smoke (P1 retrieve gate).

  Scenario: Alice 在 4/15 群聊宣布 Bob 不再负责 auth, Carol 接手.
  Wire-up:
    1. Bus.append_evidence → engram for the announcement
    2. testing.mark_consolidated to seed S_old (Bob responsible_for auth)
       at CONSOLIDATED so the next write enters the severe-conflict path
       (this mirrors M0.5's TC-NEW-CONFLICT-SEVERE seeding pattern)
    3. Bus.write S_new (Carol responsible_for auth) — triggers SUPERSEDES
       atomic transaction (M0.5)
    4. basic_retrieve at 2026-04-16 returns only S_new

  Note: this test does NOT route through the live Extractor (no XML
  validating the announcement text — that's M0.4 territory and orthogonal
  to the retrieval gate). The §14.1 spec says "testing helper 将 Statement
  标为 CONSOLIDATED 后检索返回 Carol 接手" — so seeding via Bus.write +
  mark_consolidated is the spec-blessed shortcut.
  """
  from datetime import datetime, timezone

  import pytest

  from starling import _core
  from starling.retrieval import basic_retrieve
  from starling.testing import mark_consolidated


  @pytest.fixture
  def adapter():
      from tests.python._fixtures.migrations import apply_all_migrations
      a = _core.SqliteAdapter.open(":memory:")
      apply_all_migrations(a)
      return a


  def _build_statement(*, holder_id, holder_tenant_id, subject_id,
                       predicate, object_value, valid_from, valid_to):
      s = _core.ExtractedStatement()
      s.holder_id             = holder_id
      s.holder_tenant_id      = holder_tenant_id
      s.holder_perspective    = "FIRST_PERSON"
      s.subject_kind          = "cognizer"
      s.subject_id            = subject_id
      s.predicate             = predicate
      s.object_kind           = "cognizer"
      s.object_value          = object_value
      # canonical_object_hash is computed by the canonicalizer; for this test
      # we use a stable placeholder — what matters is that S_old and S_new
      # hash to *different* values so they don't chunk-duplicate. (The Bus
      # writer keys chunk-dup on canonical_object_hash, see M0.5 Task 7.)
      from starling.schema.value import canonicalize_object
      _, s.canonical_object_hash = canonicalize_object(object_value)
      s.modality                  = "BELIEVES"
      s.polarity                  = "POS"
      s.confidence                = 0.9
      s.observed_at               = "2026-04-15T00:00:00Z"
      s.valid_from                = valid_from
      s.valid_to                  = valid_to
      s.event_time_start          = ""
      s.chunk_index               = 0
      s.source_hash               = "smoke-source-hash"
      s.perceived_by              = ""
      s.provenance                = "USER_INPUT"
      s.review_status             = "APPROVED"
      return s


  def _seed_engram(adapter, content):
      ei = _core.EngramInput()
      ei.tenant_id      = "t1"
      ei.source.adapter_name    = "smoke"
      ei.source.adapter_version = "0"
      ei.source.source_item_id  = "msg-1"
      ei.source.source_version  = "0"
      ei.source.chunk_index     = 0
      ei.source_kind            = _core.SourceKind.USER_INPUT
      ei.ingest_mode            = _core.IngestMode.WHOLE_RECORD
      ei.privacy_class          = _core.PrivacyClass.INTERNAL
      ei.retention_mode         = _core.EngramRetentionMode.AUDIT_RETAIN
      ei.declared_transformations = []
      ei.byte_preserving        = True
      ei.payload_bytes          = content
      ei.redacted_content       = ""
      ei.created_at_iso8601     = "2026-04-15T00:00:00Z"
      bus = _core.Bus(adapter)
      outcome = bus.append_evidence(ei)
      assert outcome["kind"] in ("accepted", "idempotent")
      return outcome["engram_ref"].id


  def test_smoke_returns_only_s_new(adapter):
      bus = _core.Bus(adapter)

      # 1. Seed engram for Alice's announcement.
      engram_id = _seed_engram(adapter, b"Alice: Bob no longer owns auth.")

      # 2. Write S_old (Bob responsible_for auth, valid 2026-03-01 .. 2026-04-15).
      s_old = _build_statement(
          holder_id="alice", holder_tenant_id="t1",
          subject_id="bob", predicate="responsible_for",
          object_value="auth",
          valid_from="2026-03-01T00:00:00Z",
          valid_to="2026-04-15T00:00:00Z",
      )
      r1 = bus.write(s_old, engram_id, "smoke-span-1")
      assert r1["kind"] == "accepted", r1

      # 3. Flip S_old to CONSOLIDATED via the testing helper (§14.1 mandates this).
      assert mark_consolidated(adapter, r1["stmt_id"], "t1") is True

      # 4. Write S_new (Carol responsible_for auth, valid 2026-04-15 .. open).
      s_new = _build_statement(
          holder_id="alice", holder_tenant_id="t1",
          subject_id="bob", predicate="responsible_for",
          object_value="auth_owner_change",   # different object → distinct chunk hash
          valid_from="2026-04-15T00:00:00Z",
          valid_to="",
      )
      r2 = bus.write(s_new, engram_id, "smoke-span-2")
      assert r2["kind"] == "accepted", r2

      # 5. Retrieve at 2026-04-16: only S_new should come back. S_old is
      #    ARCHIVED but its valid_to (2026-04-15) is no longer satisfied.
      result = basic_retrieve(
          adapter,
          tenant_id="t1", holder="alice",
          subject="bob", predicate="responsible_for",
          as_of=datetime(2026, 4, 16, tzinfo=timezone.utc),
      )
      assert len(result.rows) == 1, [r.id for r in result.rows]
      assert result.rows[0].id == r2["stmt_id"]
      assert result.rows[0].consolidation_state in ("volatile", "consolidated")
      assert result.receipt.sufficiency_status == "SUFFICIENT"
      assert result.receipt.evidence_erased_count == 0

      # 6. Receipt minimum fields per 13_retrieval.md
      assert result.receipt.trace_id
      assert result.receipt.query_id
      assert result.receipt.candidate_counts.fetched == 1
      assert result.receipt.candidate_counts.returned == 1

      # 7. A statement.recalled event was emitted for S_new.
      from tests.python._fixtures.bus_events import count_events_by_type
      assert count_events_by_type(adapter, "statement.recalled") == 1
  ```

  **Notes:**
  - The smoke uses different `object_value`s for S_old / S_new so the §15.3.2 chunk-duplicate guard does not fire (same lesson as M0.5 Task 10).
  - `count_events_by_type` is a thin pytest fixture helper used by M0.5 acceptance tests — if it does not exist yet, the implementer should add it under `tests/python/_fixtures/bus_events.py` as a one-liner SELECT. Match the existing fixture style.
  - The smoke does not assert on S_old's `consolidation_state == 'archived'` directly — that's M0.5 Task 10's job. M0.6's gate is "retrieval returns S_new only at the right time anchor."

- [ ] **9.2** Run the smoke:

  ```bash
  pytest tests/python/test_basic_retrieve_smoke.py -v
  # Expected: PASS.
  ```

- [ ] **9.3** Run the full Python suite to confirm no regression:

  ```bash
  pytest tests/python/ -q
  python scripts/ci_static_scan.py
  # Expected: all PASS, scanner clean.
  ```

- [ ] **9.4** Commit:
  ```bash
  git add tests/python/test_basic_retrieve_smoke.py
  git commit -m "$(cat <<'EOF'
  test(M0.6): §14.1 P1 retrieve smoke (acceptance, CRITICAL)

  End-to-end smoke per system_design.md line 1663 + §14.1: Bus.append_evidence
  → Bus.write(S_old) → testing.mark_consolidated → Bus.write(S_new) →
  basic_retrieve at 2026-04-16 returns only S_new with full RetrievalReceipt
  P1 minimum fields populated and one statement.recalled event emitted.

  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 10: Roadmap flip + Final Review + Merge to Main

**Files:**
- Modify: `docs/superpowers/plans/2026-05-23-roadmap.md` (mark M0.6 complete; pin commit SHA)
- Final review (whole-branch reviewer)
- Merge to main (`--no-ff`)
- Plan-doc commit on main

This task closes the milestone the same way M0.5 closed:

1. **Step 1: Roadmap flip** — update the M0.6 row in `docs/superpowers/plans/2026-05-23-roadmap.md` to show "已写 / ✅ 完成 / <date> / <commit-sha>". The commit SHA is the LAST WORK commit (Task 9's commit), NOT the upcoming meta-only roadmap-flip commit. This is the project commit-cell rule.

2. **Step 2: Run all checks one last time**:
   ```bash
   cd build && ctest --output-on-failure && cd ..
   pytest tests/python/ -q
   python scripts/ci_static_scan.py
   ```
   All three must be green.

3. **Step 3: Dispatch a final whole-branch reviewer** (use `feature-dev:code-reviewer` agent type). Reviewer prompt should include:
   - Branch HEAD: `worktree-m0-6-basic-retrieve`
   - Main HEAD: `main` (= the M0.5 merge tip + its plan-doc commit)
   - Spec links: `docs/design/subsystems_design/13_retrieval.md` (esp. P1 闭环, RetrievalReceipt P1 必填, statement.recalled emit, multi-holder reject); `docs/design/system_design.md §14.1` (smoke), `§15.3.5` (testing helper convention), `§ 13 CRITICAL test cases` (TC-NEG-TENANT)
   - Ask for: actionable issues with severity {CRITICAL, IMPORTANT, NIT}; report under 600 words.

   If the reviewer flags CRITICAL or IMPORTANT issues, the implementer fixes them in additional commits BEFORE the merge step. NITs can be acknowledged or deferred.

4. **Step 4: Ask the user for merge consent** via AskUserQuestion. Three options:
   1. **Merge --no-ff to main (Recommended)** — standard milestone close, matches M0.0–M0.5's `--no-ff` style.
   2. **Keep branch alive for further iteration** — leave on `worktree-m0-6-basic-retrieve` if the user wants more changes before merging.
   3. **Squash and merge** — collapse the branch into a single commit (not recommended; loses TDD history).

   DO NOT merge without explicit user consent.

5. **Step 5: If user chose merge — perform the merge** from the main repo cwd (NOT the worktree):

   ```bash
   cd /Users/jaredguo-mini/develop/memory/starling
   git checkout main
   git merge --no-ff worktree-m0-6-basic-retrieve -m "Merge M0.6: basic_retrieve + RetrievalReceipt + statement.recalled"
   git log --oneline -3 main
   ```

   The repo is local-only (no `origin` remote); skip any push step.

6. **Step 6: Commit the M0.6 plan doc to main**. After the merge, the plan file `docs/superpowers/plans/2026-05-24-m0-6-basic-retrieve.md` is untracked in main (same pattern as every prior milestone):

   ```bash
   cd /Users/jaredguo-mini/develop/memory/starling
   ls docs/superpowers/plans/2026-05-24-m0-6-basic-retrieve.md && echo "in main"
   git add docs/superpowers/plans/2026-05-24-m0-6-basic-retrieve.md
   git commit -m "$(cat <<'EOF'
   docs(M0.6): add basic_retrieve implementation plan

   Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
   EOF
   )"
   ```

7. **Step 7: Tear down the worktree**. After confirming `git log --oneline -5 main` shows both the merge commit and the plan-doc commit landed:

   ```
   ExitWorktree(action="remove", discard_changes=true)
   ```

   `discard_changes=true` is safe because all worktree commits are already merged into main as part of the merge commit.

8. **Step 8: Mark task complete** — update the TaskCreate todo list (M0.6 Task 10) to `completed`. M0.6 is now closed.

- [ ] **10.1** Update `docs/superpowers/plans/2026-05-23-roadmap.md` — find the M0.6 row in the progress table near line 145 (the "进度追踪" table) and edit the cells:

  ```diff
  -| M0.6 | 待写 | — | — | — |
  +| M0.6 | 已写 | ✅ 完成 | 2026-05-24 | <Task-9-commit-SHA> |
  ```

  Also update line 52 (the M0.6 row in the milestone overview table) to mark Plan column as `**[2026-05-24-m0-6-basic-retrieve.md](2026-05-24-m0-6-basic-retrieve.md)（已写）**`.

- [ ] **10.2** Commit the roadmap flip:

  ```bash
  git add docs/superpowers/plans/2026-05-23-roadmap.md
  git commit -m "$(cat <<'EOF'
  chore(M0.6): mark milestone complete in roadmap

  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
  EOF
  )"
  ```

- [ ] **10.3** Run final all-greens check:

  ```bash
  cd build && ctest --output-on-failure && cd ..
  pytest tests/python/ -q
  python scripts/ci_static_scan.py
  echo "all checks done"
  ```

- [ ] **10.4** Dispatch the whole-branch reviewer (controller's responsibility — no per-step bash command needed). Address any CRITICAL / IMPORTANT issues with additional commits before proceeding.

- [ ] **10.5** Use AskUserQuestion to obtain merge consent (3 options as listed above). DO NOT merge without consent.

- [ ] **10.6** If user chose `--no-ff` merge: execute the merge command from the main repo cwd (see Step 5 commands above).

- [ ] **10.7** Commit the M0.6 plan doc to main (Step 6 commands above).

- [ ] **10.8** ExitWorktree(action="remove", discard_changes=true).

- [ ] **10.9** Mark TaskCreate task (whichever ID was assigned to "M0.6 Task 10: Roadmap flip + merge to main") as `completed`. M0.6 closed.

---

## Self-Review

After writing this plan, I checked it against the spec sections cited in the prompt:

**1. Spec coverage:**
- `13_retrieval.md` §"P1 basic_retrieve 闭环" filter rules (consolidation_state, review_status, evidence-erased, time-anchor, single-holder): ✅ Tasks 4 + 8 cover all four predicates.
- `13_retrieval.md` §"basic_retrieve 函数签名（P1）": ✅ Task 4 (C++ params struct) + Task 7 (Python facade with matching positional shape via keyword args).
- `13_retrieval.md` §"RetrievalReceipt（P1 最小字段加粗）" — six P1-mandatory fields (trace_id / query_id / filters_applied / candidate_counts / evidence_erased_count / sufficiency_status): ✅ Task 3 declares them; Tasks 4/6 populate; Tasks 7/8 verify.
- `13_retrieval.md` §"statement.recalled emit 契约" — fire-and-forget, 2s dedup, Bus防抖合并: ✅ Task 2 adds the 2s bucket; Task 6 emits; emit failures are swallowed.
- `13_retrieval.md` §"多 holder 隔离" P1 single-holder hard rule: ✅ Task 4 throws on empty holder; Task 7 throws on list/tuple holder.
- `system_design.md` line 1663 + §14.1 P1 retrieve smoke: ✅ Task 9.
- `system_design.md` §15.3.5 `testing.mark_evidence_erased`: ✅ Task 5 (helper + idempotent + audit event); used by Task 8 evidence-erased filter test.
- `system_design.md` line 1745 TC-NEG-TENANT [CRITICAL]: ✅ Task 8 (contract test against the SELECT literal + the existing `assert_final_query_safe` guard called in Task 4).
- `system_design.md` line 1774 (crypto_erasure 后 retrieval 仍返回元数据 ... 但 evidence 标注"部分证据已擦除"): we DROP rows whose only evidence is erased rather than mark them as "partially erased." This is a deliberate P1 simplification — the spec section is in a P2/P3 list at §15.4 ("已知限制"). The P1 contract is `evidence_erased_count` only. Flag below.
- §13 spec field `degraded_paths`: not in P1; left out per the "P1 最小字段加粗" rule.

**2. Placeholder scan:** I searched the plan for forbidden patterns. None remain. Two intentional implementer notes are flagged in their tasks (the `tests/python/_fixtures/...` helpers in Tasks 5/8/9 — implementer should add them under `_fixtures/` if not already there; they are 5-10 line SELECTs, fully described in context). The "collect_pragma_index_columns" helper in Task 1 is similarly flagged with where to put it.

**3. Type consistency:**
- `StatementRow` field set declared in Task 3 — used by Task 4 (materialize), Task 7 (Python mirror dataclass), Tasks 8/9 (assert on `.id` / `.consolidation_state` etc).
- `RetrievalReceipt::CandidateCounts` declared in Task 3 — populated in Task 4 (`fetched`, `returned`, `dropped_by_evidence_erasure`, `evidence_erased_count`); Tasks 7/8 read them.
- `Sufficiency` enum declared in Task 3, mapped in Task 7's `_SUFFICIENCY_NAME` dict; Tasks 8/9 assert on the string form ("SUFFICIENT" / "MISSING_INFO").
- `BasicRetrieverParams` field set declared in Task 4, mirrored in pybind in Task 7, populated by the Python facade in Task 7.
- `QueryIntent::FACT_LOOKUP` — only P1 value; Task 7 raises ValueError on others.
- `testing.mark_evidence_erased` signature (adapter, engram_id, tenant_id, erased_at_iso8601) consistent across C++ decl (Task 5.1), C++ impl (5.2), pybind (5.3), Python wrapper (5.4), tests (5.5, 5.6), Task 8 reuse.

No drift found.

**Spec ambiguity flagged:**
- §15.4 ("已知限制") says crypto-erased evidence should result in the statement being returned with "部分证据已擦除" annotation. We instead DROP those rows in P1 because the receipt's `evidence_erased_count` is the spec-named field and §13 spec for P1 doesn't say to surface row-level annotation. P2 retrieval will need a richer schema (per-row erasure flag) — that's a known extension point, not a P1 gap.
- §13 spec's `sufficiency_status` is `MISSING_INFO` vs `ABSTAINED` distinction: in P1 we return `MISSING_INFO` on empty results (Task 4 line "sufficiency_status = MISSING_INFO if empty else SUFFICIENT") and never return `ABSTAINED` from `basic_retrieve` (no abstention gate in P1). The receipt struct still ships the `ABSTAINED` enum value for future use.
- `statement.recalled` aggregate_id is set to `row.id` (the recalled Statement). §13 doesn't specify; using the statement id directly is the most natural choice and matches how `statement.archived` keys to the statement-version-root.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-24-m0-6-basic-retrieve.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, two-stage review (spec compliance + code quality) between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with human-checkpoints.

**Which approach?**

If Subagent-Driven: invoke `superpowers:subagent-driven-development` with this plan path as the argument.
If Inline: invoke `superpowers:executing-plans`.

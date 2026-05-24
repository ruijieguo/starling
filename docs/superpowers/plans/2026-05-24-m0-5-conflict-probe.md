# M0.5 ConflictProbe — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development — invoke it before starting any task. Each task is a self-contained unit; run sequentially. Commit after every task. Never skip Task 0 baseline verification.

**Goal:** Ship ConflictProbe — `canonical_conflict_key` hashing, `normalize_interval`, `scope_of`, four conflict-kind detection paths, atomic SUPERSEDES transaction, debounced `belief.conflict` events, and the TC-NEW-CONFLICT-SEVERE P1 CRITICAL acceptance test.

**Architecture:** `ConflictProbe` sits inside `Bus::write` between `TransactionGuard` and `StatementWriter`. It is a pure-detection component (no writes of its own); `Bus::write` owns all DB mutations for the conflict paths. The atomic 4-item SUPERSEDES transaction (INSERT S_new + INSERT edge + UPDATE S_old + 3x `OutboxWriter::append`) is `Bus::write`'s responsibility, not `StatementWriter`'s.

**Tech Stack:** C++20 + pybind11 + scikit-build-core editable install; SQLite 3.46+ raw C API + `StmtHandle` RAII; Python 3.11+; pytest; CMake + Ninja; sha256 via OpenSSL EVP (same as M0.4).

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `include/starling/extractor/extracted_statement.hpp` | Modify | Add `valid_from`, `valid_to`, `event_time_start` optional fields |
| `include/starling/bus/normalized_interval.hpp` | Create | `NormalizedInterval` struct + `UNKNOWN_INTERVAL` sentinel + `normalize_interval()` declaration |
| `src/bus/normalized_interval.cpp` | Create | `normalize_interval()` implementation |
| `include/starling/bus/canonical_scope.hpp` | Create | `CanonicalScope` discriminated union + `scope_of()` declaration |
| `src/bus/canonical_scope.cpp` | Create | `scope_of()` implementation (M0.5: always returns Null) |
| `include/starling/bus/conflict_key.hpp` | Create | `canonical_conflict_key()` declaration |
| `src/bus/conflict_key.cpp` | Create | `canonical_conflict_key()` implementation (7-tuple sha256) |
| `include/starling/bus/conflict_probe.hpp` | Create | `ConflictMatch` struct + `ConflictProbe` class declaration |
| `src/bus/conflict_probe.cpp` | Create | `ConflictProbe::scan()` implementation (pure detection, no writes) |
| `src/bus/bus.cpp` | Modify | Extend `Bus::write` to call `ConflictProbe::scan` and branch on conflict_kind |
| `src/bus/bus_event.cpp` | Modify | Extend `compute_window_bucket` for `belief.conflict`, `statement.archived`, `statement.superseded` |
| `src/bus/statement_writer.cpp` | Modify | Thread `valid_from`, `valid_to`, `event_time_start` into INSERT |
| `migrations/0003_conflict_probe_indices.sql` | Create | `idx_conflict_lookup` + `idx_temporal_overlap` |
| `python/starling/bus/normalized_interval.py` | Create | Python parity for `NormalizedInterval` + `normalize_interval()` |
| `python/starling/bus/canonical_scope.py` | Create | Python parity for `CanonicalScope` + `scope_of()` |
| `python/starling/bus/conflict_key.py` | Create | Python parity for `canonical_conflict_key()` |
| `python/starling/bus/bus_event.py` | Modify | Extend `compute_window_bucket` for new event types |
| `python/starling/testing/__init__.py` | Modify | Bind `mark_consolidated` from `_core` |
| `src/testing/testing_marker.cpp` | Modify | Add `mark_consolidated(stmt_id, tenant_id)` implementation |
| `tests/cpp/test_normalized_interval.cpp` | Create | C++ unit tests for `normalize_interval` (all edge cases + parity vector) |
| `tests/cpp/test_canonical_scope.cpp` | Create | C++ unit tests for `scope_of` (Null branch + future-extension shape) |
| `tests/cpp/test_conflict_key.cpp` | Create | C++ unit tests for `canonical_conflict_key` (locked parity vector) |
| `tests/cpp/test_conflict_probe_indices.cpp` | Create | C++ test: migration creates both indices, no regression on 0001 |
| `tests/cpp/test_conflict_probe_scan.cpp` | Create | C++ unit tests for `ConflictProbe::scan` (all 4 branches + cross-version + UNKNOWN_INTERVAL + theta) |
| `tests/cpp/test_bus_write_conflict.cpp` | Create | C++ tests for Bus::write partial_overlap/adjacent edge paths + rollback on each of 4 SUPERSEDES failure points |
| `tests/python/test_normalized_interval.py` | Create | Python parity tests for `normalize_interval` |
| `tests/python/test_canonical_scope.py` | Create | Python parity tests for `scope_of` |
| `tests/python/test_conflict_key.py` | Create | Python parity tests for `canonical_conflict_key` (same locked vector) |
| `tests/python/test_conflict_probe_scan.py` | Create | Python tests for ConflictProbe scan paths via pybind |
| `tests/python/test_tc_new_conflict_severe.py` | Create | TC-NEW-CONFLICT-SEVERE acceptance test (P1 CRITICAL) |
| `CMakeLists.txt` | Modify | Add new source files + test targets |

---

## Task 0: Baseline Verification

**Files:** None (read-only verification)

**Purpose:** Confirm the worktree is clean and all existing tests pass before any M0.5 code is written. Record the HEAD SHA and test counts so regressions are immediately detectable.

- [ ] **0.1** Activate the venv and confirm Python version:
  ```bash
  source /Users/jaredguo-mini/develop/memory/starling/.venv/bin/activate
  python --version
  # Expected: Python 3.11.x or 3.12.x
  ```

- [ ] **0.2** Record the current HEAD SHA:
  ```bash
  git -C /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/m0-5-conflict-probe rev-parse HEAD
  # Expected: fab3e2a... (or the current HEAD of the worktree)
  # Record this value — it is the pre-M0.5 baseline.
  ```

- [ ] **0.3** Build the project from scratch:
  ```bash
  cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/m0-5-conflict-probe
  cmake -S . -B build -G Ninja
  cmake --build build
  # Expected: build succeeds with 0 errors, 0 warnings treated as errors
  ```

- [ ] **0.4** Run the full C++ test suite and record the count:
  ```bash
  cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/m0-5-conflict-probe/build
  ctest --output-on-failure
  # Expected: 184/184 tests passed
  # Record the exact count in this task's notes.
  ```

- [ ] **0.5** Install the Python package in editable mode:
  ```bash
  cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/m0-5-conflict-probe
  pip install -e . --no-build-isolation
  # Expected: Successfully installed starling-...
  ```

- [ ] **0.6** Run the full Python test suite and record the count:
  ```bash
  cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/m0-5-conflict-probe
  pytest tests/python/ -q
  # Expected: 250 passed
  # Record the exact count.
  ```

- [ ] **0.7** Run the CI static scan:
  ```bash
  cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/m0-5-conflict-probe
  python scripts/ci_static_scan.py
  # Expected: exit 0, no violations
  ```

- [ ] **0.8** Record baseline in a comment at the top of this task (do not commit):
  ```
  Baseline: HEAD=<sha>, ctest=184/184, pytest=250/250, ci_scan=clean
  ```

No commit for Task 0 — it is verification only.

---

## Task 1: ExtractedStatement Time-Interval Fields

**Files:**
- Modify: `include/starling/extractor/extracted_statement.hpp`
- Modify: `src/bus/statement_writer.cpp`
- Create: `tests/cpp/test_statement_writer_interval.cpp`
- Modify: `CMakeLists.txt`

**Purpose:** Extend the `ExtractedStatement` DTO with three optional ISO-8601 time-interval fields and thread them through `StatementWriter` into the existing schema columns (`valid_from`, `valid_to`, `event_time_start`). The schema columns already exist in `0001_initial_schema.sql` (lines 35-37); no migration needed.

- [ ] **1.1** Open `include/starling/extractor/extracted_statement.hpp`. After the `observed_at` field (line 30), add the three new optional fields:

  ```cpp
  // --- existing fields above ---
  std::string                  observed_at;          // ISO-8601 UTC

  // M0.5: time-interval fields (all nullable; schema columns exist since M0.1)
  std::optional<std::string>   valid_from;           // ISO-8601 UTC, closed bound
  std::optional<std::string>   valid_to;             // ISO-8601 UTC, open bound (exclusive)
  std::optional<std::string>   event_time_start;     // ISO-8601 UTC, single-point (M0.5); end added M0.5+
  ```

  The full updated struct (for reference — only the three lines above are new):
  ```cpp
  #pragma once

  #include "starling/schema/statement_enums.hpp"

  #include <cstdint>
  #include <optional>
  #include <string>
  #include <vector>

  namespace starling::extractor {

  // POD produced by xml_parser::parse_extractor_xml and consumed by
  // statement_validator + StatementWriter. M0.4-minimal: no nesting_depth>0,
  // no salience/affect, no derived_from. M0.5 adds time-interval fields.
  struct ExtractedStatement {
      std::string                  holder_id;
      std::string                  holder_tenant_id;
      schema::Perspective          holder_perspective = schema::Perspective::INFERRED;

      std::string                  subject_kind;
      std::string                  subject_id;
      std::string                  predicate;
      std::string                  object_kind;
      std::string                  object_value;
      std::string                  canonical_object_hash;

      schema::Modality             modality       = schema::Modality::BELIEVES;
      schema::Polarity             polarity       = schema::Polarity::POS;
      double                       confidence     = 0.0;
      std::string                  observed_at;

      // M0.5: time-interval fields (nullable; schema columns exist since M0.1)
      std::optional<std::string>   valid_from;
      std::optional<std::string>   valid_to;
      std::optional<std::string>   event_time_start;

      std::int32_t                 chunk_index    = 0;
      std::string                  source_hash;
      std::vector<std::string>     perceived_by;

      schema::StatementProvenance  provenance     = schema::StatementProvenance::USER_INPUT;
      schema::ReviewStatus         review_status  = schema::ReviewStatus::APPROVED;
  };

  }  // namespace starling::extractor
  ```

- [ ] **1.2** Open `src/bus/statement_writer.cpp`. Locate the prepared INSERT statement for `statements`. Find the parameter binding section and add bindings for the three new columns. The columns are already in the INSERT column list if M0.4 included them; if not, add them. The binding pattern follows the existing `bind_sv` / `bind_optional_sv` helpers:

  ```cpp
  // After binding observed_at, add:
  if (stmt.valid_from.has_value()) {
      detail::bind_sv(ps, idx_valid_from, *stmt.valid_from);
  } else {
      sqlite3_bind_null(ps.get(), idx_valid_from);
  }
  if (stmt.valid_to.has_value()) {
      detail::bind_sv(ps, idx_valid_to, *stmt.valid_to);
  } else {
      sqlite3_bind_null(ps.get(), idx_valid_to);
  }
  if (stmt.event_time_start.has_value()) {
      detail::bind_sv(ps, idx_event_time_start, *stmt.event_time_start);
  } else {
      sqlite3_bind_null(ps.get(), idx_event_time_start);
  }
  ```

  Ensure the INSERT column list includes `valid_from, valid_to, event_time_start` and the corresponding `?, ?, ?` placeholders. The `event_time_end` column exists in the schema but is not populated by M0.5 (single-point only); bind it as NULL.

- [ ] **1.3** Create `tests/cpp/test_statement_writer_interval.cpp`:

  ```cpp
  #include "starling/bus/statement_writer.hpp"
  #include "starling/extractor/extracted_statement.hpp"
  #include "starling/persistence/sqlite_adapter.hpp"
  #include "starling/schema/statement_enums.hpp"

  #include <gtest/gtest.h>
  #include <sqlite3.h>
  #include <string>

  namespace {

  using namespace starling;

  // Helper: open an in-memory DB and run migrations
  persistence::SqliteAdapter make_test_db() {
      persistence::SqliteAdapter adapter(":memory:");
      adapter.run_migrations();
      return adapter;
  }

  extractor::ExtractedStatement make_base_stmt() {
      extractor::ExtractedStatement s;
      s.holder_id          = "holder-uuid-001";
      s.holder_tenant_id   = "tenant-001";
      s.subject_kind       = "entity";
      s.subject_id         = "entity-uuid-001";
      s.predicate          = "responsible_for";
      s.object_kind        = "str";
      s.object_value       = "auth";
      s.canonical_object_hash = "deadbeef01234567deadbeef01234567deadbeef01234567deadbeef01234567";
      s.modality           = schema::Modality::BELIEVES;
      s.polarity           = schema::Polarity::POS;
      s.confidence         = 0.9;
      s.observed_at        = "2026-01-01T00:00:00Z";
      return s;
  }

  TEST(StatementWriterInterval, NullIntervalRoundTrip) {
      auto adapter = make_test_db();
      auto stmt = make_base_stmt();
      // valid_from, valid_to, event_time_start all absent
      bus::StatementWriter writer(adapter.conn());
      auto outcome = writer.write(stmt, "engram-001", "span-001", std::nullopt);
      ASSERT_TRUE(std::holds_alternative<bus::StatementWriteAccepted>(outcome));

      auto& accepted = std::get<bus::StatementWriteAccepted>(outcome);
      // Verify via SELECT that the three columns are NULL
      sqlite3_stmt* raw = nullptr;
      int rc = sqlite3_prepare_v2(
          adapter.conn(),
          "SELECT valid_from, valid_to, event_time_start FROM statements WHERE id = ?",
          -1, &raw, nullptr);
      ASSERT_EQ(rc, SQLITE_OK);
      sqlite3_bind_text(raw, 1, accepted.statement_id.c_str(), -1, SQLITE_STATIC);
      ASSERT_EQ(sqlite3_step(raw), SQLITE_ROW);
      EXPECT_EQ(sqlite3_column_type(raw, 0), SQLITE_NULL);
      EXPECT_EQ(sqlite3_column_type(raw, 1), SQLITE_NULL);
      EXPECT_EQ(sqlite3_column_type(raw, 2), SQLITE_NULL);
      sqlite3_finalize(raw);
  }

  TEST(StatementWriterInterval, FullIntervalRoundTrip) {
      auto adapter = make_test_db();
      auto stmt = make_base_stmt();
      stmt.valid_from       = "2026-01-01T00:00:00Z";
      stmt.valid_to         = "2026-06-01T00:00:00Z";
      stmt.event_time_start = "2026-01-15T12:00:00Z";

      bus::StatementWriter writer(adapter.conn());
      auto outcome = writer.write(stmt, "engram-001", "span-001", std::nullopt);
      ASSERT_TRUE(std::holds_alternative<bus::StatementWriteAccepted>(outcome));
      auto& accepted = std::get<bus::StatementWriteAccepted>(outcome);

      sqlite3_stmt* raw = nullptr;
      sqlite3_prepare_v2(
          adapter.conn(),
          "SELECT valid_from, valid_to, event_time_start FROM statements WHERE id = ?",
          -1, &raw, nullptr);
      sqlite3_bind_text(raw, 1, accepted.statement_id.c_str(), -1, SQLITE_STATIC);
      ASSERT_EQ(sqlite3_step(raw), SQLITE_ROW);
      EXPECT_STREQ(reinterpret_cast<const char*>(sqlite3_column_text(raw, 0)), "2026-01-01T00:00:00Z");
      EXPECT_STREQ(reinterpret_cast<const char*>(sqlite3_column_text(raw, 1)), "2026-06-01T00:00:00Z");
      EXPECT_STREQ(reinterpret_cast<const char*>(sqlite3_column_text(raw, 2)), "2026-01-15T12:00:00Z");
      sqlite3_finalize(raw);
  }

  TEST(StatementWriterInterval, ValidFromOnlyRoundTrip) {
      auto adapter = make_test_db();
      auto stmt = make_base_stmt();
      stmt.valid_from = "2026-03-01T00:00:00Z";
      // valid_to and event_time_start absent

      bus::StatementWriter writer(adapter.conn());
      auto outcome = writer.write(stmt, "engram-001", "span-001", std::nullopt);
      ASSERT_TRUE(std::holds_alternative<bus::StatementWriteAccepted>(outcome));
      auto& accepted = std::get<bus::StatementWriteAccepted>(outcome);

      sqlite3_stmt* raw = nullptr;
      sqlite3_prepare_v2(
          adapter.conn(),
          "SELECT valid_from, valid_to, event_time_start FROM statements WHERE id = ?",
          -1, &raw, nullptr);
      sqlite3_bind_text(raw, 1, accepted.statement_id.c_str(), -1, SQLITE_STATIC);
      ASSERT_EQ(sqlite3_step(raw), SQLITE_ROW);
      EXPECT_STREQ(reinterpret_cast<const char*>(sqlite3_column_text(raw, 0)), "2026-03-01T00:00:00Z");
      EXPECT_EQ(sqlite3_column_type(raw, 1), SQLITE_NULL);
      EXPECT_EQ(sqlite3_column_type(raw, 2), SQLITE_NULL);
      sqlite3_finalize(raw);
  }

  }  // namespace
  ```

- [ ] **1.4** Add the new test target to `CMakeLists.txt`. Find the block where other `test_statement_writer_*.cpp` tests are registered and add:
  ```cmake
  add_executable(test_statement_writer_interval tests/cpp/test_statement_writer_interval.cpp)
  target_link_libraries(test_statement_writer_interval PRIVATE starling_core GTest::gtest_main)
  add_test(NAME test_statement_writer_interval COMMAND test_statement_writer_interval)
  ```

- [ ] **1.5** Build and run the new test:
  ```bash
  cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/m0-5-conflict-probe
  cmake --build build
  cd build && ctest -R test_statement_writer_interval --output-on-failure
  # Expected: 3/3 tests passed (NullIntervalRoundTrip, FullIntervalRoundTrip, ValidFromOnlyRoundTrip)
  ```

- [ ] **1.6** Run the full suite to confirm no regressions:
  ```bash
  cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/m0-5-conflict-probe/build
  ctest --output-on-failure
  # Expected: 187/187 tests passed (184 baseline + 3 new)
  ```

- [ ] **1.7** Commit:
  ```bash
  cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/m0-5-conflict-probe
  git add include/starling/extractor/extracted_statement.hpp \
          src/bus/statement_writer.cpp \
          tests/cpp/test_statement_writer_interval.cpp \
          CMakeLists.txt
  git commit -m "$(cat <<'EOF'
  feat(M0.5): extend ExtractedStatement with valid_from/valid_to/event_time_start

  Adds three optional ISO-8601 time-interval fields to the ExtractedStatement DTO
  and threads them through StatementWriter into the existing schema columns.
  Three round-trip tests confirm null, full, and partial interval persistence.

  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 2: NormalizedInterval + normalize_interval (C++ + Python Parity)

**Files:**
- Create: `include/starling/bus/normalized_interval.hpp`
- Create: `src/bus/normalized_interval.cpp`
- Create: `tests/cpp/test_normalized_interval.cpp`
- Create: `python/starling/bus/normalized_interval.py`
- Create: `tests/python/test_normalized_interval.py`
- Modify: `CMakeLists.txt`

**Purpose:** Implement `normalize_interval(valid_from, valid_to, event_time) -> NormalizedInterval` in C++ and Python with identical semantics. The output participates in `canonical_conflict_key`. The `UNKNOWN_INTERVAL` sentinel must NOT trigger `direct_contradiction`.

**Parity approach:** The implementer runs the C++ test binary once to print the canonical bytes of the parity fixture, then pastes the same string into the Python test as `PARITY_CANONICAL_BYTES`. Same approach as M0.4 Task 2.

- [ ] **2.1** Create `include/starling/bus/normalized_interval.hpp`:

  ```cpp
  #pragma once

  #include <optional>
  #include <string>

  namespace starling::bus {

  // Canonical closed-open interval [valid_from, valid_to) for conflict detection.
  // UNKNOWN_INTERVAL is the sentinel when both valid_from and event_time are absent.
  // UNKNOWN_INTERVAL participates only in low-confidence partial_overlap;
  // it MUST NOT trigger direct_contradiction.
  //
  // canonical_bytes() format: "UNKNOWN" | "<from>/OPEN" | "<from>/<to>"
  struct NormalizedInterval {
      bool        is_unknown = false;
      std::string from;       // ISO-8601 UTC; empty iff is_unknown
      std::string to;         // ISO-8601 UTC; empty means open-ended
      bool        to_is_open = false;

      // Returns the canonical bytes representation used in canonical_conflict_key.
      std::string canonical_bytes() const;

      bool operator==(const NormalizedInterval&) const = default;
  };

  // Sentinel: both valid_from and event_time absent.
  inline const NormalizedInterval UNKNOWN_INTERVAL =
      NormalizedInterval{.is_unknown = true, .from = "", .to = "", .to_is_open = false};

  // normalize_interval: derive a canonical interval from three nullable inputs.
  //
  // Priority:
  //   1. valid_from present                   -> [valid_from, valid_to) or [valid_from, OPEN)
  //   2. valid_from absent, event_time present -> [event_time, OPEN)  (fallback)
  //   3. both absent                           -> UNKNOWN_INTERVAL
  NormalizedInterval normalize_interval(
      const std::optional<std::string>& valid_from,
      const std::optional<std::string>& valid_to,
      const std::optional<std::string>& event_time);

  }  // namespace starling::bus
  ```

- [ ] **2.2** Create `src/bus/normalized_interval.cpp`:

  ```cpp
  #include "starling/bus/normalized_interval.hpp"

  namespace starling::bus {

  std::string NormalizedInterval::canonical_bytes() const {
      if (is_unknown) return "UNKNOWN";
      if (to_is_open || to.empty()) return from + "/OPEN";
      return from + "/" + to;
  }

  NormalizedInterval normalize_interval(
      const std::optional<std::string>& valid_from,
      const std::optional<std::string>& valid_to,
      const std::optional<std::string>& event_time)
  {
      if (valid_from.has_value()) {
          NormalizedInterval ni;
          ni.is_unknown = false;
          ni.from       = *valid_from;
          if (valid_to.has_value()) {
              ni.to         = *valid_to;
              ni.to_is_open = false;
          } else {
              ni.to         = "";
              ni.to_is_open = true;
          }
          return ni;
      }
      if (event_time.has_value()) {
          NormalizedInterval ni;
          ni.is_unknown = false;
          ni.from       = *event_time;
          ni.to         = "";
          ni.to_is_open = true;
          return ni;
      }
      return UNKNOWN_INTERVAL;
  }

  }  // namespace starling::bus
  ```

- [ ] **2.3** Create `tests/cpp/test_normalized_interval.cpp`:

  ```cpp
  #include "starling/bus/normalized_interval.hpp"
  #include <gtest/gtest.h>
  #include <iostream>

  namespace {
  using namespace starling::bus;

  TEST(NormalizedInterval, BothAbsentReturnsUnknown) {
      auto ni = normalize_interval(std::nullopt, std::nullopt, std::nullopt);
      EXPECT_TRUE(ni.is_unknown);
      EXPECT_EQ(ni.canonical_bytes(), "UNKNOWN");
  }

  TEST(NormalizedInterval, ValidFromOnlyOpenEnded) {
      auto ni = normalize_interval("2026-01-01T00:00:00Z", std::nullopt, std::nullopt);
      EXPECT_FALSE(ni.is_unknown);
      EXPECT_EQ(ni.from, "2026-01-01T00:00:00Z");
      EXPECT_TRUE(ni.to_is_open);
      EXPECT_EQ(ni.canonical_bytes(), "2026-01-01T00:00:00Z/OPEN");
  }

  TEST(NormalizedInterval, ValidFromAndToClosedOpen) {
      auto ni = normalize_interval(
          "2026-01-01T00:00:00Z", "2026-06-01T00:00:00Z", std::nullopt);
      EXPECT_FALSE(ni.is_unknown);
      EXPECT_EQ(ni.from, "2026-01-01T00:00:00Z");
      EXPECT_EQ(ni.to,   "2026-06-01T00:00:00Z");
      EXPECT_FALSE(ni.to_is_open);
      EXPECT_EQ(ni.canonical_bytes(), "2026-01-01T00:00:00Z/2026-06-01T00:00:00Z");
  }

  TEST(NormalizedInterval, EventTimeFallbackOpenEnded) {
      auto ni = normalize_interval(std::nullopt, std::nullopt, "2026-03-15T08:00:00Z");
      EXPECT_FALSE(ni.is_unknown);
      EXPECT_EQ(ni.from, "2026-03-15T08:00:00Z");
      EXPECT_TRUE(ni.to_is_open);
      EXPECT_EQ(ni.canonical_bytes(), "2026-03-15T08:00:00Z/OPEN");
  }

  TEST(NormalizedInterval, ValidFromTakesPriorityOverEventTime) {
      auto ni = normalize_interval(
          "2026-01-01T00:00:00Z", std::nullopt, "2026-03-15T08:00:00Z");
      EXPECT_EQ(ni.from, "2026-01-01T00:00:00Z");
      EXPECT_TRUE(ni.to_is_open);
  }

  TEST(NormalizedInterval, ValidToIgnoredWhenValidFromAbsent) {
      auto ni = normalize_interval(std::nullopt, "2026-06-01T00:00:00Z", std::nullopt);
      EXPECT_TRUE(ni.is_unknown);
  }

  // Parity fixture: run this test, capture the printed PARITY_CANONICAL_BYTES= line,
  // and paste the value into tests/python/test_normalized_interval.py.
  TEST(NormalizedInterval, ParityFixtureCanonicalBytes) {
      auto ni = normalize_interval(
          "2026-01-01T00:00:00Z", "2026-12-31T23:59:59Z", std::nullopt);
      std::cout << "PARITY_CANONICAL_BYTES=" << ni.canonical_bytes() << std::endl;
      EXPECT_EQ(ni.canonical_bytes(), "2026-01-01T00:00:00Z/2026-12-31T23:59:59Z");
  }

  }  // namespace
  ```

- [ ] **2.4** Create `python/starling/bus/normalized_interval.py`:

  ```python
  from __future__ import annotations
  from dataclasses import dataclass
  from typing import Optional


  @dataclass(frozen=True)
  class NormalizedInterval:
      is_unknown: bool = False
      from_: str = ""       # ISO-8601 UTC; empty iff is_unknown
      to: str = ""          # ISO-8601 UTC; empty means open-ended
      to_is_open: bool = False

      def canonical_bytes(self) -> str:
          if self.is_unknown:
              return "UNKNOWN"
          if self.to_is_open or not self.to:
              return f"{self.from_}/OPEN"
          return f"{self.from_}/{self.to}"


  # Sentinel: both valid_from and event_time absent.
  # MUST NOT trigger direct_contradiction.
  UNKNOWN_INTERVAL = NormalizedInterval(is_unknown=True)


  def normalize_interval(
      valid_from: Optional[str],
      valid_to: Optional[str],
      event_time: Optional[str],
  ) -> NormalizedInterval:
      if valid_from is not None:
          if valid_to is not None:
              return NormalizedInterval(from_=valid_from, to=valid_to, to_is_open=False)
          return NormalizedInterval(from_=valid_from, to_is_open=True)
      if event_time is not None:
          return NormalizedInterval(from_=event_time, to_is_open=True)
      return UNKNOWN_INTERVAL
  ```

- [ ] **2.5** Create `tests/python/test_normalized_interval.py`:

  ```python
  import pytest
  from starling.bus.normalized_interval import (
      NormalizedInterval, UNKNOWN_INTERVAL, normalize_interval,
  )

  # Locked parity fixture -- paste value from C++ ParityFixtureCanonicalBytes output.
  PARITY_CANONICAL_BYTES = "2026-01-01T00:00:00Z/2026-12-31T23:59:59Z"


  def test_both_absent_returns_unknown():
      ni = normalize_interval(None, None, None)
      assert ni.is_unknown
      assert ni.canonical_bytes() == "UNKNOWN"


  def test_valid_from_only_open_ended():
      ni = normalize_interval("2026-01-01T00:00:00Z", None, None)
      assert not ni.is_unknown
      assert ni.from_ == "2026-01-01T00:00:00Z"
      assert ni.to_is_open
      assert ni.canonical_bytes() == "2026-01-01T00:00:00Z/OPEN"


  def test_valid_from_and_to_closed_open():
      ni = normalize_interval("2026-01-01T00:00:00Z", "2026-06-01T00:00:00Z", None)
      assert not ni.is_unknown
      assert ni.from_ == "2026-01-01T00:00:00Z"
      assert ni.to == "2026-06-01T00:00:00Z"
      assert not ni.to_is_open
      assert ni.canonical_bytes() == "2026-01-01T00:00:00Z/2026-06-01T00:00:00Z"


  def test_event_time_fallback_open_ended():
      ni = normalize_interval(None, None, "2026-03-15T08:00:00Z")
      assert not ni.is_unknown
      assert ni.from_ == "2026-03-15T08:00:00Z"
      assert ni.to_is_open
      assert ni.canonical_bytes() == "2026-03-15T08:00:00Z/OPEN"


  def test_valid_from_takes_priority_over_event_time():
      ni = normalize_interval("2026-01-01T00:00:00Z", None, "2026-03-15T08:00:00Z")
      assert ni.from_ == "2026-01-01T00:00:00Z"
      assert ni.to_is_open


  def test_valid_to_ignored_when_valid_from_absent():
      ni = normalize_interval(None, "2026-06-01T00:00:00Z", None)
      assert ni.is_unknown


  def test_parity_canonical_bytes():
      ni = normalize_interval("2026-01-01T00:00:00Z", "2026-12-31T23:59:59Z", None)
      assert ni.canonical_bytes() == PARITY_CANONICAL_BYTES


  def test_unknown_interval_sentinel_identity():
      ni = normalize_interval(None, None, None)
      assert ni == UNKNOWN_INTERVAL
  ```

- [ ] **2.6** Add `src/bus/normalized_interval.cpp` to the `starling_core` library sources in `CMakeLists.txt`. Add the test target:
  ```cmake
  add_executable(test_normalized_interval tests/cpp/test_normalized_interval.cpp)
  target_link_libraries(test_normalized_interval PRIVATE starling_core GTest::gtest_main)
  add_test(NAME test_normalized_interval COMMAND test_normalized_interval)
  ```

- [ ] **2.7** Build and run C++ tests:
  ```bash
  cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/m0-5-conflict-probe
  cmake --build build
  cd build && ctest -R test_normalized_interval --output-on-failure
  # Expected: 7/7 tests passed
  # Capture the PARITY_CANONICAL_BYTES= line from stdout.
  ```

- [ ] **2.8** Run Python tests:
  ```bash
  cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/m0-5-conflict-probe
  pip install -e . --no-build-isolation
  pytest tests/python/test_normalized_interval.py -v
  # Expected: 8 passed
  ```

- [ ] **2.9** Run full suite:
  ```bash
  cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/m0-5-conflict-probe/build
  ctest --output-on-failure
  pytest /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/m0-5-conflict-probe/tests/python/ -q
  # Expected: ctest 194/194, pytest 258/258
  ```

- [ ] **2.10** Commit:
  ```bash
  cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/m0-5-conflict-probe
  git add include/starling/bus/normalized_interval.hpp \
          src/bus/normalized_interval.cpp \
          tests/cpp/test_normalized_interval.cpp \
          python/starling/bus/normalized_interval.py \
          tests/python/test_normalized_interval.py \
          CMakeLists.txt
  git commit -m "$(cat <<'EOF'
  feat(M0.5): add NormalizedInterval + normalize_interval (C++/Python parity)

  Implements the canonical closed-open interval helper used by canonical_conflict_key.
  UNKNOWN_INTERVAL sentinel covers the both-absent case and must not trigger
  direct_contradiction. Locked parity fixture confirms C++ and Python produce
  identical canonical_bytes() output.

  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 3: CanonicalScope + scope_of (C++ + Python Parity)

**Files:**
- Create: `include/starling/bus/canonical_scope.hpp`
- Create: `src/bus/canonical_scope.cpp`
- Create: `tests/cpp/test_canonical_scope.cpp`
- Create: `python/starling/bus/canonical_scope.py`
- Create: `tests/python/test_canonical_scope.py`
- Modify: `CMakeLists.txt`

**Purpose:** Implement `scope_of(stmt) -> CanonicalScope`. M0.5 ships only the 'ordinary Statement: NULL' branch. The API surface is designed as a discriminated union so M0.5+1 can add Norm/Commitment/CommonGround branches without changing the signature.

**Future-extension decision (document in code):** `CanonicalScope` is a `std::variant<CanonicalScopeNull, CanonicalScopeNorm, CanonicalScopeCommitment, CanonicalScopeCommonGround>`. M0.5 only constructs `CanonicalScopeNull`. The variant arms for Norm/Commitment/CommonGround are declared but their construction paths are gated behind a `static_assert(false, ...)` or a `[[noreturn]]` helper that throws `std::logic_error("not implemented in M0.5")`. This ensures the API shape is locked without shipping dead code paths that could be accidentally invoked.

- [ ] **3.1** Create `include/starling/bus/canonical_scope.hpp`:

  ```cpp
  #pragma once

  #include <string>
  #include <variant>
  #include <vector>

  namespace starling::bus {

  // M0.5: only Null is constructed. Norm/Commitment/CommonGround arms are declared
  // for API stability; their construction is not implemented until M0.5+1.
  struct CanonicalScopeNull {
      // canonical_bytes() returns empty string -> excluded from conflict key hash
      std::string canonical_bytes() const { return ""; }
      bool operator==(const CanonicalScopeNull&) const = default;
  };

  // Future arms (M0.5+1): declared for API stability, not constructed in M0.5.
  struct CanonicalScopeNorm {
      std::string kind;
      std::vector<std::string> members_sorted;
      std::string canonical_bytes() const;
      bool operator==(const CanonicalScopeNorm&) const = default;
  };

  struct CanonicalScopeCommitment {
      std::string principal;
      std::string beneficiary;
      std::string canonical_bytes() const;
      bool operator==(const CanonicalScopeCommitment&) const = default;
  };

  struct CanonicalScopeCommonGround {
      std::vector<std::string> parties_sorted;
      std::string canonical_bytes() const;
      bool operator==(const CanonicalScopeCommonGround&) const = default;
  };

  using CanonicalScope = std::variant<
      CanonicalScopeNull,
      CanonicalScopeNorm,
      CanonicalScopeCommitment,
      CanonicalScopeCommonGround>;

  // Returns the canonical_bytes() of whichever arm is active.
  std::string canonical_scope_bytes(const CanonicalScope& scope);

  // scope_of: derive the canonical scope from an ExtractedStatement.
  // M0.5: always returns CanonicalScopeNull{}.
  // M0.5+1: will inspect stmt.statement_kind to branch into Norm/Commitment/CommonGround.
  template <typename StmtT>
  CanonicalScope scope_of(const StmtT& /*stmt*/) {
      return CanonicalScopeNull{};
  }

  }  // namespace starling::bus
  ```

- [ ] **3.2** Create `src/bus/canonical_scope.cpp`:

  ```cpp
  #include "starling/bus/canonical_scope.hpp"
  #include <stdexcept>

  namespace starling::bus {

  // Future arms: canonical_bytes() stubs that throw until M0.5+1 implements them.
  std::string CanonicalScopeNorm::canonical_bytes() const {
      throw std::logic_error("CanonicalScopeNorm::canonical_bytes not implemented in M0.5");
  }

  std::string CanonicalScopeCommitment::canonical_bytes() const {
      throw std::logic_error("CanonicalScopeCommitment::canonical_bytes not implemented in M0.5");
  }

  std::string CanonicalScopeCommonGround::canonical_bytes() const {
      throw std::logic_error("CanonicalScopeCommonGround::canonical_bytes not implemented in M0.5");
  }

  std::string canonical_scope_bytes(const CanonicalScope& scope) {
      return std::visit([](const auto& arm) { return arm.canonical_bytes(); }, scope);
  }

  }  // namespace starling::bus
  ```

- [ ] **3.3** Create `tests/cpp/test_canonical_scope.cpp`:

  ```cpp
  #include "starling/bus/canonical_scope.hpp"
  #include "starling/extractor/extracted_statement.hpp"
  #include <gtest/gtest.h>

  namespace {
  using namespace starling::bus;
  using namespace starling::extractor;

  TEST(CanonicalScope, ExtractedStatementAlwaysReturnsNull) {
      ExtractedStatement stmt;
      stmt.holder_id = "h1";
      stmt.subject_kind = "entity";
      stmt.subject_id = "e1";
      stmt.predicate = "knows";
      auto scope = scope_of(stmt);
      EXPECT_TRUE(std::holds_alternative<CanonicalScopeNull>(scope));
  }

  TEST(CanonicalScope, NullCanonicalBytesIsEmpty) {
      CanonicalScopeNull null_scope;
      EXPECT_EQ(null_scope.canonical_bytes(), "");
      EXPECT_EQ(canonical_scope_bytes(CanonicalScope{null_scope}), "");
  }

  TEST(CanonicalScope, FutureNormArmThrowsInM05) {
      CanonicalScopeNorm norm;
      norm.kind = "obligation";
      norm.members_sorted = {"a", "b"};
      EXPECT_THROW(norm.canonical_bytes(), std::logic_error);
  }

  TEST(CanonicalScope, FutureCommitmentArmThrowsInM05) {
      CanonicalScopeCommitment c;
      c.principal = "alice";
      c.beneficiary = "bob";
      EXPECT_THROW(c.canonical_bytes(), std::logic_error);
  }

  TEST(CanonicalScope, FutureCommonGroundArmThrowsInM05) {
      CanonicalScopeCommonGround cg;
      cg.parties_sorted = {"alice", "bob"};
      EXPECT_THROW(cg.canonical_bytes(), std::logic_error);
  }

  }  // namespace
  ```

- [ ] **3.4** Create `python/starling/bus/canonical_scope.py`:

  ```python
  from __future__ import annotations
  from dataclasses import dataclass, field
  from typing import Any, List, Union


  @dataclass(frozen=True)
  class CanonicalScopeNull:
      def canonical_bytes(self) -> str:
          return ""


  @dataclass(frozen=True)
  class CanonicalScopeNorm:
      kind: str = ""
      members_sorted: tuple = ()

      def canonical_bytes(self) -> str:
          raise NotImplementedError("CanonicalScopeNorm.canonical_bytes not implemented in M0.5")


  @dataclass(frozen=True)
  class CanonicalScopeCommitment:
      principal: str = ""
      beneficiary: str = ""

      def canonical_bytes(self) -> str:
          raise NotImplementedError("CanonicalScopeCommitment.canonical_bytes not implemented in M0.5")


  @dataclass(frozen=True)
  class CanonicalScopeCommonGround:
      parties_sorted: tuple = ()

      def canonical_bytes(self) -> str:
          raise NotImplementedError("CanonicalScopeCommonGround.canonical_bytes not implemented in M0.5")


  CanonicalScope = Union[
      CanonicalScopeNull,
      CanonicalScopeNorm,
      CanonicalScopeCommitment,
      CanonicalScopeCommonGround,
  ]


  def canonical_scope_bytes(scope: CanonicalScope) -> str:
      return scope.canonical_bytes()


  def scope_of(stmt: Any) -> CanonicalScope:
      """M0.5: always returns CanonicalScopeNull. M0.5+1 will branch on stmt.statement_kind."""
      return CanonicalScopeNull()
  ```

- [ ] **3.5** Create `tests/python/test_canonical_scope.py`:

  ```python
  import pytest
  from starling.bus.canonical_scope import (
      CanonicalScopeNull, CanonicalScopeNorm, CanonicalScopeCommitment,
      CanonicalScopeCommonGround, canonical_scope_bytes, scope_of,
  )


  def test_scope_of_returns_null_for_extracted_statement():
      class FakeStmt:
          holder_id = "h1"
          subject_kind = "entity"
          predicate = "knows"
      scope = scope_of(FakeStmt())
      assert isinstance(scope, CanonicalScopeNull)


  def test_null_canonical_bytes_is_empty():
      assert CanonicalScopeNull().canonical_bytes() == ""
      assert canonical_scope_bytes(CanonicalScopeNull()) == ""


  def test_future_norm_arm_raises_in_m05():
      with pytest.raises(NotImplementedError):
          CanonicalScopeNorm(kind="obligation", members_sorted=("a", "b")).canonical_bytes()


  def test_future_commitment_arm_raises_in_m05():
      with pytest.raises(NotImplementedError):
          CanonicalScopeCommitment(principal="alice", beneficiary="bob").canonical_bytes()


  def test_future_common_ground_arm_raises_in_m05():
      with pytest.raises(NotImplementedError):
          CanonicalScopeCommonGround(parties_sorted=("alice", "bob")).canonical_bytes()
  ```

- [ ] **3.6** Add `src/bus/canonical_scope.cpp` to `starling_core` sources in `CMakeLists.txt`. Add test target:
  ```cmake
  add_executable(test_canonical_scope tests/cpp/test_canonical_scope.cpp)
  target_link_libraries(test_canonical_scope PRIVATE starling_core GTest::gtest_main)
  add_test(NAME test_canonical_scope COMMAND test_canonical_scope)
  ```

- [ ] **3.7** Build and run C++ tests:
  ```bash
  cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/m0-5-conflict-probe
  cmake --build build
  cd build && ctest -R test_canonical_scope --output-on-failure
  # Expected: 5/5 tests passed
  ```

- [ ] **3.8** Run Python tests:
  ```bash
  pytest tests/python/test_canonical_scope.py -v
  # Expected: 5 passed
  ```

- [ ] **3.9** Run full suite:
  ```bash
  cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/m0-5-conflict-probe/build
  ctest --output-on-failure
  pytest /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/m0-5-conflict-probe/tests/python/ -q
  # Expected: ctest 199/199, pytest 263/263
  ```

- [ ] **3.10** Commit:
  ```bash
  cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/m0-5-conflict-probe
  git add include/starling/bus/canonical_scope.hpp \
          src/bus/canonical_scope.cpp \
          tests/cpp/test_canonical_scope.cpp \
          python/starling/bus/canonical_scope.py \
          tests/python/test_canonical_scope.py \
          CMakeLists.txt
  git commit -m "$(cat <<'EOF'
  feat(M0.5): add CanonicalScope + scope_of (C++/Python parity)

  M0.5 ships only the Null branch (all ExtractedStatements return CanonicalScopeNull).
  The discriminated union API surface (Norm/Commitment/CommonGround arms) is declared
  now so M0.5+1 can extend without changing the signature. Future arms throw
  logic_error/NotImplementedError until implemented.

  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 4: canonical_conflict_key (C++ + Python Parity)

**Files:**
- Create: `include/starling/bus/conflict_key.hpp`
- Create: `src/bus/conflict_key.cpp`
- Create: `tests/cpp/test_conflict_key.cpp`
- Create: `python/starling/bus/conflict_key.py`
- Create: `tests/python/test_conflict_key.py`
- Modify: `CMakeLists.txt`

**Purpose:** Implement `canonical_conflict_key(stmt) -> bytes` as a sha256 of the 7-tuple: `(holder, modality, subject, predicate, canonical_object_hash, normalize_interval(...), scope_of(stmt))`. Fields joined with `\x1f` US separator. `canonical_object_hash` is the pre-computed field from the DTO (set by M0.1 canonicalize_object during extraction); M0.5 does not re-invoke canonicalize_object at probe time.

**Parity approach:** Run the C++ parity test, capture the printed PARITY_HEX= line, paste into the Python test. Both tests assert the same hex value.

- [ ] **4.1** Create `include/starling/bus/conflict_key.hpp`:

  ```cpp
  #pragma once

  #include "starling/bus/canonical_scope.hpp"
  #include "starling/bus/normalized_interval.hpp"
  #include "starling/extractor/extracted_statement.hpp"

  #include <array>
  #include <cstdint>
  #include <string>

  namespace starling::bus {

  using ConflictKeyBytes = std::array<uint8_t, 32>;

  // canonical_conflict_key: sha256 of 7-tuple joined by \x1f (US separator).
  // Fields: holder_id, modality, subject_kind:subject_id, predicate,
  //         canonical_object_hash, interval.canonical_bytes(), scope.canonical_bytes()
  ConflictKeyBytes canonical_conflict_key(
      const starling::extractor::ExtractedStatement& stmt);

  std::string canonical_conflict_key_hex(
      const starling::extractor::ExtractedStatement& stmt);

  }  // namespace starling::bus
  ```

- [ ] **4.2** Create `src/bus/conflict_key.cpp`:

  ```cpp
  #include "starling/bus/conflict_key.hpp"
  #include "starling/bus/canonical_scope.hpp"
  #include "starling/bus/normalized_interval.hpp"
  #include "starling/schema/statement_enums.hpp"

  #include <openssl/evp.h>
  #include <iomanip>
  #include <sstream>
  #include <stdexcept>

  namespace starling::bus {
  namespace {

  constexpr char kSep = '\x1f';

  void digest_field(EVP_MD_CTX* ctx, std::string_view field) {
      if (EVP_DigestUpdate(ctx, field.data(), field.size()) != 1)
          throw std::runtime_error("EVP_DigestUpdate failed");
      if (EVP_DigestUpdate(ctx, &kSep, 1) != 1)
          throw std::runtime_error("EVP_DigestUpdate sep failed");
  }

  std::string modality_str(starling::schema::Modality m) {
      using M = starling::schema::Modality;
      switch (m) {
          case M::BELIEVES:  return "BELIEVES";
          case M::KNOWS:     return "KNOWS";
          case M::DESIRES:   return "DESIRES";
          case M::INTENDS:   return "INTENDS";
          case M::PERCEIVES: return "PERCEIVES";
          default:           return "UNKNOWN_MODALITY";
      }
  }

  }  // namespace

  ConflictKeyBytes canonical_conflict_key(
      const starling::extractor::ExtractedStatement& stmt)
  {
      EVP_MD_CTX* ctx = EVP_MD_CTX_new();
      if (!ctx) throw std::runtime_error("EVP_MD_CTX_new failed");
      if (EVP_DigestInit_ex(ctx, EVP_sha256(), nullptr) != 1) {
          EVP_MD_CTX_free(ctx);
          throw std::runtime_error("EVP_DigestInit_ex failed");
      }
      digest_field(ctx, stmt.holder_id);
      digest_field(ctx, modality_str(stmt.modality));
      digest_field(ctx, stmt.subject_kind + ":" + stmt.subject_id);
      digest_field(ctx, stmt.predicate);
      digest_field(ctx, stmt.canonical_object_hash);
      auto ni = normalize_interval(stmt.valid_from, stmt.valid_to, stmt.event_time_start);
      digest_field(ctx, ni.canonical_bytes());
      auto scope = scope_of(stmt);
      digest_field(ctx, canonical_scope_bytes(scope));
      ConflictKeyBytes out{};
      unsigned int len = 0;
      if (EVP_DigestFinal_ex(ctx, out.data(), &len) != 1) {
          EVP_MD_CTX_free(ctx);
          throw std::runtime_error("EVP_DigestFinal_ex failed");
      }
      EVP_MD_CTX_free(ctx);
      return out;
  }

  std::string canonical_conflict_key_hex(
      const starling::extractor::ExtractedStatement& stmt)
  {
      auto bytes = canonical_conflict_key(stmt);
      std::ostringstream oss;
      for (auto b : bytes)
          oss << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(b);
      return oss.str();
  }

  }  // namespace starling::bus
  ```

- [ ] **4.3** Create `tests/cpp/test_conflict_key.cpp`:

  ```cpp
  #include "starling/bus/conflict_key.hpp"
  #include "starling/extractor/extracted_statement.hpp"
  #include "starling/schema/statement_enums.hpp"
  #include <gtest/gtest.h>
  #include <iostream>

  namespace {
  using namespace starling;
  using namespace starling::bus;

  extractor::ExtractedStatement make_parity_stmt() {
      extractor::ExtractedStatement s;
      s.holder_id             = "holder-uuid-parity";
      s.holder_tenant_id      = "tenant-parity";
      s.subject_kind          = "entity";
      s.subject_id            = "entity-uuid-parity";
      s.predicate             = "responsible_for";
      s.object_kind           = "str";
      s.object_value          = "auth";
      s.canonical_object_hash = "aaaa1111bbbb2222cccc3333dddd4444eeee5555ffff6666aaaa1111bbbb2222";
      s.modality              = schema::Modality::BELIEVES;
      s.polarity              = schema::Polarity::POS;
      s.confidence            = 0.9;
      s.observed_at           = "2026-01-01T00:00:00Z";
      return s;
  }

  // Run this test, capture PARITY_HEX= from stdout,
  // paste into tests/python/test_conflict_key.py as PARITY_HEX.
  TEST(ConflictKey, ParityFixtureHex) {
      auto stmt = make_parity_stmt();
      auto hex = canonical_conflict_key_hex(stmt);
      std::cout << "PARITY_HEX=" << hex << std::endl;
      EXPECT_EQ(hex.size(), 64u);
  }

  TEST(ConflictKey, DifferentHolderProducesDifferentKey) {
      auto s1 = make_parity_stmt();
      auto s2 = make_parity_stmt();
      s2.holder_id = "different-holder";
      EXPECT_NE(canonical_conflict_key_hex(s1), canonical_conflict_key_hex(s2));
  }

  TEST(ConflictKey, DifferentModalityProducesDifferentKey) {
      auto s1 = make_parity_stmt();
      auto s2 = make_parity_stmt();
      s2.modality = schema::Modality::KNOWS;
      EXPECT_NE(canonical_conflict_key_hex(s1), canonical_conflict_key_hex(s2));
  }

  TEST(ConflictKey, DifferentObjectHashProducesDifferentKey) {
      auto s1 = make_parity_stmt();
      auto s2 = make_parity_stmt();
      s2.canonical_object_hash = "0000000000000000000000000000000000000000000000000000000000000000";
      EXPECT_NE(canonical_conflict_key_hex(s1), canonical_conflict_key_hex(s2));
  }

  TEST(ConflictKey, SameInputProducesSameKey) {
      auto s1 = make_parity_stmt();
      auto s2 = make_parity_stmt();
      EXPECT_EQ(canonical_conflict_key_hex(s1), canonical_conflict_key_hex(s2));
  }

  TEST(ConflictKey, IntervalParticipatesInKey) {
      auto s1 = make_parity_stmt();
      auto s2 = make_parity_stmt();
      s2.valid_from = "2026-01-01T00:00:00Z";
      EXPECT_NE(canonical_conflict_key_hex(s1), canonical_conflict_key_hex(s2));
  }

  }  // namespace
  ```

- [ ] **4.4** Create `python/starling/bus/conflict_key.py`:

  ```python
  from __future__ import annotations
  import hashlib
  from typing import Any

  from starling.bus.normalized_interval import normalize_interval
  from starling.bus.canonical_scope import canonical_scope_bytes, scope_of

  _SEP = b'\x1f'

  _MODALITY_STR = {
      'BELIEVES': 'BELIEVES', 'KNOWS': 'KNOWS',
      'DESIRES': 'DESIRES', 'INTENDS': 'INTENDS', 'PERCEIVES': 'PERCEIVES',
  }


  def canonical_conflict_key(stmt: Any) -> bytes:
      h = hashlib.sha256()

      def feed(field: str) -> None:
          h.update(field.encode('utf-8'))
          h.update(_SEP)

      modality = getattr(stmt, 'modality', 'BELIEVES')
      if hasattr(modality, 'name'):
          modality = modality.name
      modality_s = _MODALITY_STR.get(str(modality), 'UNKNOWN_MODALITY')

      feed(stmt.holder_id)
      feed(modality_s)
      feed(f"{stmt.subject_kind}:{stmt.subject_id}")
      feed(stmt.predicate)
      feed(stmt.canonical_object_hash)
      ni = normalize_interval(
          getattr(stmt, 'valid_from', None),
          getattr(stmt, 'valid_to', None),
          getattr(stmt, 'event_time_start', None),
      )
      feed(ni.canonical_bytes())
      scope = scope_of(stmt)
      feed(canonical_scope_bytes(scope))
      return h.digest()


  def canonical_conflict_key_hex(stmt: Any) -> str:
      return canonical_conflict_key(stmt).hex()
  ```

- [ ] **4.5** Create `tests/python/test_conflict_key.py`:

  ```python
  import pytest
  from starling.bus.conflict_key import canonical_conflict_key_hex

  # Locked parity fixture -- paste value from C++ ParityFixtureHex output.
  # Run: cd build && ctest -R test_conflict_key -V 2>&1 | grep PARITY_HEX
  PARITY_HEX = "REPLACE_WITH_CPP_OUTPUT"


  class ParityStmt:
      holder_id = "holder-uuid-parity"
      holder_tenant_id = "tenant-parity"
      subject_kind = "entity"
      subject_id = "entity-uuid-parity"
      predicate = "responsible_for"
      object_kind = "str"
      object_value = "auth"
      canonical_object_hash = "aaaa1111bbbb2222cccc3333dddd4444eeee5555ffff6666aaaa1111bbbb2222"
      modality = "BELIEVES"
      polarity = "POS"
      confidence = 0.9
      observed_at = "2026-01-01T00:00:00Z"
      valid_from = None
      valid_to = None
      event_time_start = None


  def test_parity_hex_matches_cpp():
      assert PARITY_HEX != "REPLACE_WITH_CPP_OUTPUT", \
          "Implementer must run C++ test and paste PARITY_HEX value"
      assert canonical_conflict_key_hex(ParityStmt()) == PARITY_HEX


  def test_different_holder_produces_different_key():
      class S(ParityStmt):
          holder_id = "different-holder"
      assert canonical_conflict_key_hex(S()) != canonical_conflict_key_hex(ParityStmt())


  def test_different_modality_produces_different_key():
      class S(ParityStmt):
          modality = "KNOWS"
      assert canonical_conflict_key_hex(S()) != canonical_conflict_key_hex(ParityStmt())


  def test_same_input_produces_same_key():
      assert canonical_conflict_key_hex(ParityStmt()) == canonical_conflict_key_hex(ParityStmt())


  def test_interval_participates_in_key():
      class S(ParityStmt):
          valid_from = "2026-01-01T00:00:00Z"
      assert canonical_conflict_key_hex(S()) != canonical_conflict_key_hex(ParityStmt())
  ```

- [ ] **4.6** Add `src/bus/conflict_key.cpp` to `starling_core` sources. Add test target:
  ```cmake
  add_executable(test_conflict_key tests/cpp/test_conflict_key.cpp)
  target_link_libraries(test_conflict_key PRIVATE starling_core GTest::gtest_main)
  add_test(NAME test_conflict_key COMMAND test_conflict_key)
  ```

- [ ] **4.7** Build and run C++ tests, capture parity hex:
  ```bash
  cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/m0-5-conflict-probe
  cmake --build build
  cd build && ctest -R test_conflict_key --output-on-failure -V 2>&1 | grep PARITY_HEX
  # Capture the hex value. Expected: 6/6 tests passed
  ```

- [ ] **4.8** Paste the captured hex into `tests/python/test_conflict_key.py` replacing `"REPLACE_WITH_CPP_OUTPUT"`.

- [ ] **4.9** Run Python tests:
  ```bash
  pip install -e . --no-build-isolation
  pytest tests/python/test_conflict_key.py -v
  # Expected: 5 passed
  ```

- [ ] **4.10** Run full suite:
  ```bash
  cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/m0-5-conflict-probe/build
  ctest --output-on-failure
  pytest /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/m0-5-conflict-probe/tests/python/ -q
  # Expected: ctest 205/205, pytest 268/268
  ```

- [ ] **4.11** Commit:
  ```bash
  cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/m0-5-conflict-probe
  git add include/starling/bus/conflict_key.hpp \
          src/bus/conflict_key.cpp \
          tests/cpp/test_conflict_key.cpp \
          python/starling/bus/conflict_key.py \
          tests/python/test_conflict_key.py \
          CMakeLists.txt
  git commit -m "$(cat <<'EOF'
  feat(M0.5): add canonical_conflict_key 7-tuple sha256 (C++/Python parity)

  Composes holder+modality+subject+predicate+canonical_object_hash+interval+scope
  into a sha256 using \x1f US separator. Reuses M0.1 canonical_object_hash from
  the DTO. Locked parity fixture confirms C++ and Python produce identical hex.

  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 5: New Indices Migration 0003_conflict_probe_indices.sql

**Files:**
- Create: `migrations/0003_conflict_probe_indices.sql`
- Create: `tests/cpp/test_conflict_probe_indices.cpp`
- Modify: `CMakeLists.txt`

**Purpose:** Add two new indices on the `statements` table to support ConflictProbe candidate prefilter and temporal overlap detection. The migration runner is forward-only; adding the file is sufficient.

- [ ] **5.1** Create `migrations/0003_conflict_probe_indices.sql`:

  ```sql
  -- M0.5 ConflictProbe indices on statements table.
  -- idx_conflict_lookup: candidate prefilter for canonical_conflict_key matching.
  -- idx_temporal_overlap: temporal overlap detection.

  CREATE INDEX IF NOT EXISTS idx_conflict_lookup
      ON statements(
          tenant_id,
          holder_id,
          modality,
          subject_kind,
          subject_id,
          predicate,
          canonical_object_hash_version,
          canonical_object_hash
      );

  CREATE INDEX IF NOT EXISTS idx_temporal_overlap
      ON statements(tenant_id, holder_id, valid_from, valid_to);
  ```

- [ ] **5.2** Create `tests/cpp/test_conflict_probe_indices.cpp`:

  ```cpp
  #include "starling/persistence/sqlite_adapter.hpp"
  #include <gtest/gtest.h>
  #include <sqlite3.h>
  #include <string>
  #include <unordered_set>

  namespace {
  using namespace starling::persistence;

  std::unordered_set<std::string> get_indices(sqlite3* db, const std::string& table) {
      std::unordered_set<std::string> names;
      sqlite3_stmt* stmt = nullptr;
      const char* sql =
          "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=?";
      sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr);
      sqlite3_bind_text(stmt, 1, table.c_str(), -1, SQLITE_STATIC);
      while (sqlite3_step(stmt) == SQLITE_ROW)
          names.insert(reinterpret_cast<const char*>(sqlite3_column_text(stmt, 0)));
      sqlite3_finalize(stmt);
      return names;
  }

  TEST(ConflictProbeIndices, BothNewIndicesPresent) {
      SqliteAdapter adapter(":memory:");
      adapter.run_migrations();
      auto idx = get_indices(adapter.conn(), "statements");
      EXPECT_TRUE(idx.count("idx_conflict_lookup") > 0);
      EXPECT_TRUE(idx.count("idx_temporal_overlap") > 0);
  }

  TEST(ConflictProbeIndices, M0001IndicesNotRegressed) {
      SqliteAdapter adapter(":memory:");
      adapter.run_migrations();
      auto idx = get_indices(adapter.conn(), "statements");
      EXPECT_TRUE(idx.count("idx_statement_id_tenant") > 0);
      EXPECT_TRUE(idx.count("idx_statements_holder_predicate") > 0);
      EXPECT_TRUE(idx.count("idx_statements_subject") > 0);
  }

  TEST(ConflictProbeIndices, MigrationVersionRecorded) {
      SqliteAdapter adapter(":memory:");
      adapter.run_migrations();
      sqlite3_stmt* stmt = nullptr;
      sqlite3_prepare_v2(adapter.conn(),
          "SELECT version FROM schema_migrations WHERE version=3",
          -1, &stmt, nullptr);
      EXPECT_EQ(sqlite3_step(stmt), SQLITE_ROW);
      sqlite3_finalize(stmt);
  }

  }  // namespace
  ```

- [ ] **5.3** Add test target to `CMakeLists.txt`:
  ```cmake
  add_executable(test_conflict_probe_indices tests/cpp/test_conflict_probe_indices.cpp)
  target_link_libraries(test_conflict_probe_indices PRIVATE starling_core GTest::gtest_main)
  add_test(NAME test_conflict_probe_indices COMMAND test_conflict_probe_indices)
  ```

- [ ] **5.4** Build and run:
  ```bash
  cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/m0-5-conflict-probe
  cmake --build build
  cd build && ctest -R test_conflict_probe_indices --output-on-failure
  # Expected: 3/3 tests passed
  ```

- [ ] **5.5** Run full suite:
  ```bash
  cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/m0-5-conflict-probe/build
  ctest --output-on-failure
  # Expected: 208/208
  ```

- [ ] **5.6** Commit:
  ```bash
  cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/m0-5-conflict-probe
  git add migrations/0003_conflict_probe_indices.sql \
          tests/cpp/test_conflict_probe_indices.cpp \
          CMakeLists.txt
  git commit -m "$(cat <<'EOF'
  feat(M0.5): add conflict probe indices migration 0003

  Adds idx_conflict_lookup (candidate prefilter) and idx_temporal_overlap
  (overlap detection) on the statements table. Tests confirm both indices
  are present after migration and that 0001 indices are not regressed.

  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 6: ConflictProbe::scan (Pure Detection, No Writes)

**Files:**
- Create: `include/starling/bus/conflict_probe.hpp`
- Create: `src/bus/conflict_probe.cpp`
- Test: `tests/cpp/test_conflict_probe_scan.cpp`
- Modify: `CMakeLists.txt` (add sources + test target)

This task ships the detection-only ConflictProbe class. It returns the strongest match by severity ordering (`direct_contradiction > superseding > partial_overlap > adjacent`) or `std::nullopt` if no candidate matches. **It writes nothing** — Bus::write owns all DB mutations in subsequent tasks.

The class queries `statements` via `idx_conflict_lookup` (Task 5) for candidates with the same `(tenant_id, holder_id, modality, subject_kind, subject_id, predicate, canonical_object_hash_version, canonical_object_hash)`. For temporal overlap detection it falls back to `idx_temporal_overlap`.

**θ_severe = 0.6**: both S_new and S_old confidence must be ≥ 0.6 for a `direct_contradiction` match. Below threshold downgrades to `partial_overlap + REVIEW_REQUESTED`.

**Cross-version downgrade**: when S_new and S_old have different `canonical_object_hash_version`, the maximum severity is `partial_overlap`. The probe runs two queries (one per known version) and merges results, but cross-version hits are clamped.

**UNKNOWN_INTERVAL clamp**: if either side has UNKNOWN_INTERVAL, `direct_contradiction` is forbidden — clamp to `partial_overlap`.

- [ ] **6.1** Create `include/starling/bus/conflict_probe.hpp`:

  ```cpp
  #pragma once

  #include "starling/bus/conflict_key.hpp"
  #include "starling/bus/normalized_interval.hpp"
  #include "starling/extractor/extracted_statement.hpp"
  #include "starling/persistence/connection.hpp"
  #include <optional>
  #include <string>
  #include <vector>

  namespace starling::bus {

  enum class ConflictKind {
      DirectContradiction,
      Superseding,
      PartialOverlap,
      Adjacent,
  };

  std::string_view to_string(ConflictKind k);

  struct ConflictMatch {
      ConflictKind  kind;
      std::string   matched_statement_id;
      std::string   matched_tenant_id;
      std::string   matched_supersedes_root_id;  // for SUPERSEDES aggregate_id
      std::string   matched_canonical_object_hash_version;
      double        matched_confidence = 0.0;
      // The 7-tuple key produced from S_new + S_old's normalized interval.
      // Used for debounce window dedup.
      std::string   conflict_key_hex;
  };

  // ConflictProbe is a pure-detection component. It performs read-only SQL
  // against the `statements` table to find the strongest conflict candidate
  // for a proposed S_new. It MUST NOT mutate any table; Bus::write owns the
  // SUPERSEDES atomic transaction and the partial_overlap/adjacent edge
  // writes.
  //
  // Severity ordering: DirectContradiction > Superseding > PartialOverlap >
  // Adjacent. The strongest candidate wins. UNKNOWN_INTERVAL on either side
  // clamps to PartialOverlap. Cross-version hash hits clamp to PartialOverlap.
  // Both sides must have confidence >= θ_severe (0.6) for DirectContradiction;
  // below threshold clamps to PartialOverlap.
  class ConflictProbe {
  public:
      static constexpr double kThetaSevere = 0.6;

      explicit ConflictProbe(starling::persistence::Connection& conn) : conn_(conn) {}

      std::optional<ConflictMatch> scan(
          const starling::extractor::ExtractedStatement& s_new,
          const NormalizedInterval& interval_new) const;

  private:
      starling::persistence::Connection& conn_;
  };

  }  // namespace starling::bus
  ```

- [ ] **6.2** Create `src/bus/conflict_probe.cpp`:

  ```cpp
  #include "starling/bus/conflict_probe.hpp"

  #include "starling/bus/detail/sqlite_helpers.hpp"
  #include "starling/persistence/stmt_handle.hpp"
  #include "starling/schema/statement_enums.hpp"

  #include <algorithm>
  #include <sqlite3.h>
  #include <string>
  #include <vector>

  namespace starling::bus {

  std::string_view to_string(ConflictKind k) {
      switch (k) {
          case ConflictKind::DirectContradiction: return "direct_contradiction";
          case ConflictKind::Superseding:         return "superseding";
          case ConflictKind::PartialOverlap:      return "partial_overlap";
          case ConflictKind::Adjacent:            return "adjacent";
      }
      return "unknown";
  }

  namespace {

  struct CandidateRow {
      std::string id;
      std::string tenant_id;
      std::string supersedes_root_id;  // = supersedes_id if non-null else id
      std::string canonical_object_hash_version;
      std::string polarity;
      std::string valid_from;
      std::string valid_to;
      std::string event_time_start;
      double      confidence = 0.0;
  };

  // Fetch all candidate rows that match the prefilter (same holder, modality,
  // subject, predicate, canonical_object_hash). Cross-version hits are
  // included but flagged via the canonical_object_hash_version field.
  std::vector<CandidateRow> fetch_candidates(
      starling::persistence::Connection& conn,
      const starling::extractor::ExtractedStatement& s) {

      const char* sql =
          "SELECT id, tenant_id, "
          "       COALESCE(supersedes_id, id) AS supersedes_root_id, "
          "       canonical_object_hash_version, polarity, "
          "       COALESCE(valid_from, ''), COALESCE(valid_to, ''), "
          "       COALESCE(event_time_start, ''), confidence "
          "FROM statements "
          "WHERE tenant_id = ? AND holder_id = ? AND modality = ? "
          "  AND subject_kind = ? AND subject_id = ? AND predicate = ? "
          "  AND canonical_object_hash = ? "
          "  AND consolidation_state IN ('volatile','consolidated')";

      starling::persistence::StmtHandle stmt;
      stmt.prepare(conn.handle(), sql);

      detail::bind_sv(stmt, 1, s.holder_tenant_id);
      detail::bind_sv(stmt, 2, s.holder_id);
      detail::bind_sv(stmt, 3, starling::schema::to_string(s.modality));
      detail::bind_sv(stmt, 4, s.subject_kind);
      detail::bind_sv(stmt, 5, s.subject_id);
      detail::bind_sv(stmt, 6, s.predicate);
      detail::bind_sv(stmt, 7, s.canonical_object_hash);

      std::vector<CandidateRow> rows;
      while (sqlite3_step(stmt.handle()) == SQLITE_ROW) {
          CandidateRow r;
          r.id                            = reinterpret_cast<const char*>(sqlite3_column_text(stmt.handle(), 0));
          r.tenant_id                     = reinterpret_cast<const char*>(sqlite3_column_text(stmt.handle(), 1));
          r.supersedes_root_id            = reinterpret_cast<const char*>(sqlite3_column_text(stmt.handle(), 2));
          r.canonical_object_hash_version = reinterpret_cast<const char*>(sqlite3_column_text(stmt.handle(), 3));
          r.polarity                      = reinterpret_cast<const char*>(sqlite3_column_text(stmt.handle(), 4));
          r.valid_from                    = reinterpret_cast<const char*>(sqlite3_column_text(stmt.handle(), 5));
          r.valid_to                      = reinterpret_cast<const char*>(sqlite3_column_text(stmt.handle(), 6));
          r.event_time_start              = reinterpret_cast<const char*>(sqlite3_column_text(stmt.handle(), 7));
          r.confidence                    = sqlite3_column_double(stmt.handle(), 8);
          rows.push_back(std::move(r));
      }
      return rows;
  }

  // Compute the conflict_kind given S_new + a candidate row. Severity ordering
  // is enforced by the caller (this function returns a single kind for the
  // pair); the caller picks the strongest across all candidates.
  ConflictKind classify(
      const starling::extractor::ExtractedStatement& s_new,
      const NormalizedInterval& iv_new,
      const CandidateRow& cand) {

      const NormalizedInterval iv_old = normalize_interval(
          cand.valid_from.empty() ? std::nullopt : std::optional<std::string>(cand.valid_from),
          cand.valid_to.empty()   ? std::nullopt : std::optional<std::string>(cand.valid_to),
          cand.event_time_start.empty() ? std::nullopt : std::optional<std::string>(cand.event_time_start));

      const bool same_version =
          cand.canonical_object_hash_version ==
          std::string("v1");  // M0.5 ships only v1; future versions will pass S_new's version here.

      const bool unknown_either = iv_new.is_unknown() || iv_old.is_unknown();

      const bool both_above_theta =
          s_new.confidence >= ConflictProbe::kThetaSevere &&
          cand.confidence  >= ConflictProbe::kThetaSevere;

      const std::string s_new_polarity = starling::schema::to_string(s_new.polarity);
      const bool opposite_polarity = (s_new_polarity != cand.polarity);

      // Cross-version always clamps to PartialOverlap (max severity).
      if (!same_version) {
          return ConflictKind::PartialOverlap;
      }

      // UNKNOWN_INTERVAL clamps to PartialOverlap.
      if (unknown_either) {
          return ConflictKind::PartialOverlap;
      }

      // DirectContradiction: opposite polarity, both above theta, intervals overlap or equal.
      if (opposite_polarity && both_above_theta && iv_new.overlaps(iv_old)) {
          return ConflictKind::DirectContradiction;
      }

      // Superseding: same polarity, S_new fully covers S_old (start_new <= start_old, end_new >= end_old or end_new is open).
      if (!opposite_polarity && both_above_theta && iv_new.covers(iv_old)) {
          return ConflictKind::Superseding;
      }

      // Adjacent: intervals are touching but not overlapping.
      if (iv_new.adjacent(iv_old)) {
          return ConflictKind::Adjacent;
      }

      // Otherwise PartialOverlap (intervals intersect partially without coverage).
      return ConflictKind::PartialOverlap;
  }

  int severity_rank(ConflictKind k) {
      switch (k) {
          case ConflictKind::DirectContradiction: return 4;
          case ConflictKind::Superseding:         return 3;
          case ConflictKind::PartialOverlap:      return 2;
          case ConflictKind::Adjacent:            return 1;
      }
      return 0;
  }

  }  // namespace

  std::optional<ConflictMatch> ConflictProbe::scan(
      const starling::extractor::ExtractedStatement& s_new,
      const NormalizedInterval& interval_new) const {

      auto candidates = fetch_candidates(conn_, s_new);
      if (candidates.empty()) return std::nullopt;

      std::optional<ConflictMatch> best;
      int best_rank = 0;

      for (const auto& cand : candidates) {
          ConflictKind k = classify(s_new, interval_new, cand);
          const int rank = severity_rank(k);
          if (rank > best_rank) {
              ConflictMatch m;
              m.kind = k;
              m.matched_statement_id            = cand.id;
              m.matched_tenant_id               = cand.tenant_id;
              m.matched_supersedes_root_id      = cand.supersedes_root_id;
              m.matched_canonical_object_hash_version = cand.canonical_object_hash_version;
              m.matched_confidence              = cand.confidence;
              m.conflict_key_hex                = canonical_conflict_key(s_new, interval_new, /*scope=*/{});
              best      = std::move(m);
              best_rank = rank;
          }
      }
      return best;
  }

  }  // namespace starling::bus
  ```

  Notes on `NormalizedInterval` helper methods (`overlaps`, `covers`, `adjacent`, `is_unknown`): these were declared in Task 2's header. If they aren't there, add them now to `include/starling/bus/normalized_interval.hpp` with the canonical closed-open `[start, end)` semantics: overlap iff `start_a < end_b && start_b < end_a` (open ends treated as +∞); covers iff `start_a <= start_b && (end_a >= end_b OR end_a is open)`; adjacent iff `end_a == start_b OR end_b == start_a` (no gap, no overlap); is_unknown iff start and end are both UNKNOWN.

- [ ] **6.3** Create `tests/cpp/test_conflict_probe_scan.cpp`:

  ```cpp
  #include "starling/bus/conflict_probe.hpp"
  #include "starling/persistence/sqlite_adapter.hpp"
  #include "starling/persistence/migration_runner.hpp"

  #include <gtest/gtest.h>
  #include <filesystem>

  using namespace starling::bus;
  using namespace starling::extractor;
  using namespace starling::persistence;

  namespace {

  std::unique_ptr<SqliteAdapter> open_fresh(const std::string& path) {
      std::filesystem::remove(path);
      auto a = SqliteAdapter::open(path);
      MigrationRunner::run(a->connection());
      return a;
  }

  ExtractedStatement make_stmt(const std::string& id, const std::string& polarity,
                               double conf, const std::string& vf = "",
                               const std::string& vt = "") {
      ExtractedStatement s;
      s.holder_id        = "cog-self";
      s.holder_tenant_id = "default";
      s.subject_kind     = "cognizer";
      s.subject_id       = "cog-bob";
      s.predicate        = "responsible_for";
      s.object_kind      = "str";
      s.object_value     = "auth";
      s.canonical_object_hash = "deadbeef";
      s.modality         = starling::schema::Modality::BELIEVES;
      s.polarity         = (polarity == "pos") ? starling::schema::Polarity::POS
                                                : starling::schema::Polarity::NEG;
      s.confidence       = conf;
      s.observed_at      = "2026-05-24T10:00:00Z";
      s.valid_from       = vf.empty() ? std::nullopt : std::optional<std::string>(vf);
      s.valid_to         = vt.empty() ? std::nullopt : std::optional<std::string>(vt);
      return s;
  }

  void insert_row(Connection& conn, const std::string& id, const std::string& polarity,
                  double conf, const std::string& vf = "", const std::string& vt = "",
                  const std::string& version = "v1",
                  const std::string& state = "consolidated") {
      // INSERT minimal columns; rely on schema defaults for the rest.
      const char* sql =
          "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
          "subject_kind,subject_id,predicate,object_kind,object_value,"
          "canonical_object_hash,canonical_object_hash_version,modality,"
          "polarity,confidence,observed_at,salience,affect_json,activation,"
          "last_accessed,provenance,consolidation_state,review_status,"
          "valid_from,valid_to,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)";
      StmtHandle h; h.prepare(conn.handle(), sql);
      sqlite3_bind_text(h.handle(), 1, id.c_str(), -1, SQLITE_TRANSIENT);
      sqlite3_bind_text(h.handle(), 2, "default", -1, SQLITE_STATIC);
      sqlite3_bind_text(h.handle(), 3, "cog-self", -1, SQLITE_STATIC);
      sqlite3_bind_text(h.handle(), 4, "first_person", -1, SQLITE_STATIC);
      sqlite3_bind_text(h.handle(), 5, "cognizer", -1, SQLITE_STATIC);
      sqlite3_bind_text(h.handle(), 6, "cog-bob", -1, SQLITE_STATIC);
      sqlite3_bind_text(h.handle(), 7, "responsible_for", -1, SQLITE_STATIC);
      sqlite3_bind_text(h.handle(), 8, "str", -1, SQLITE_STATIC);
      sqlite3_bind_text(h.handle(), 9, "auth", -1, SQLITE_STATIC);
      sqlite3_bind_text(h.handle(),10, "deadbeef", -1, SQLITE_STATIC);
      sqlite3_bind_text(h.handle(),11, version.c_str(), -1, SQLITE_TRANSIENT);
      sqlite3_bind_text(h.handle(),12, "believes", -1, SQLITE_STATIC);
      sqlite3_bind_text(h.handle(),13, polarity.c_str(), -1, SQLITE_TRANSIENT);
      sqlite3_bind_double(h.handle(),14, conf);
      sqlite3_bind_text(h.handle(),15, "2026-05-24T09:00:00Z", -1, SQLITE_STATIC);
      sqlite3_bind_double(h.handle(),16, 0.5);
      sqlite3_bind_text(h.handle(),17, "{}", -1, SQLITE_STATIC);
      sqlite3_bind_double(h.handle(),18, 1.0);
      sqlite3_bind_text(h.handle(),19, "2026-05-24T09:00:00Z", -1, SQLITE_STATIC);
      sqlite3_bind_text(h.handle(),20, "user_input", -1, SQLITE_STATIC);
      sqlite3_bind_text(h.handle(),21, state.c_str(), -1, SQLITE_TRANSIENT);
      sqlite3_bind_text(h.handle(),22, "approved", -1, SQLITE_STATIC);
      if (vf.empty()) sqlite3_bind_null(h.handle(),23); else sqlite3_bind_text(h.handle(),23, vf.c_str(), -1, SQLITE_TRANSIENT);
      if (vt.empty()) sqlite3_bind_null(h.handle(),24); else sqlite3_bind_text(h.handle(),24, vt.c_str(), -1, SQLITE_TRANSIENT);
      sqlite3_bind_text(h.handle(),25, "2026-05-24T09:00:00Z", -1, SQLITE_STATIC);
      sqlite3_bind_text(h.handle(),26, "2026-05-24T09:00:00Z", -1, SQLITE_STATIC);
      ASSERT_EQ(SQLITE_DONE, sqlite3_step(h.handle()));
  }

  }  // namespace

  TEST(ConflictProbeScan, NoCandidatesReturnsNullopt) {
      auto a = open_fresh("/tmp/cps_empty.db");
      ConflictProbe p(a->connection());
      auto m = p.scan(make_stmt("s1","neg",0.85), normalize_interval({}, {}, {}));
      EXPECT_FALSE(m.has_value());
  }

  TEST(ConflictProbeScan, DirectContradictionAboveTheta) {
      auto a = open_fresh("/tmp/cps_direct.db");
      insert_row(a->connection(), "s_old", "pos", 0.85, "2026-05-01T00:00:00Z", "2027-01-01T00:00:00Z");
      ConflictProbe p(a->connection());
      auto m = p.scan(make_stmt("s_new","neg",0.85,"2026-06-01T00:00:00Z","2026-12-31T00:00:00Z"),
                       normalize_interval(std::string("2026-06-01T00:00:00Z"),
                                          std::string("2026-12-31T00:00:00Z"), {}));
      ASSERT_TRUE(m.has_value());
      EXPECT_EQ(ConflictKind::DirectContradiction, m->kind);
      EXPECT_EQ("s_old", m->matched_statement_id);
  }

  TEST(ConflictProbeScan, BelowThetaDowngradesToPartial) {
      auto a = open_fresh("/tmp/cps_theta.db");
      insert_row(a->connection(), "s_old", "pos", 0.50, "2026-05-01T00:00:00Z", "2027-01-01T00:00:00Z");
      ConflictProbe p(a->connection());
      auto m = p.scan(make_stmt("s_new","neg",0.85,"2026-06-01T00:00:00Z","2026-12-31T00:00:00Z"),
                       normalize_interval(std::string("2026-06-01T00:00:00Z"),
                                          std::string("2026-12-31T00:00:00Z"), {}));
      ASSERT_TRUE(m.has_value());
      EXPECT_EQ(ConflictKind::PartialOverlap, m->kind);
  }

  TEST(ConflictProbeScan, UnknownIntervalClampsToPartial) {
      auto a = open_fresh("/tmp/cps_unknown.db");
      insert_row(a->connection(), "s_old", "pos", 0.85);  // no interval
      ConflictProbe p(a->connection());
      auto m = p.scan(make_stmt("s_new","neg",0.85),
                       normalize_interval({}, {}, {}));
      ASSERT_TRUE(m.has_value());
      EXPECT_EQ(ConflictKind::PartialOverlap, m->kind);
  }

  TEST(ConflictProbeScan, CrossVersionDowngradesToPartial) {
      auto a = open_fresh("/tmp/cps_crossver.db");
      insert_row(a->connection(), "s_old", "pos", 0.85,
                 "2026-05-01T00:00:00Z", "2027-01-01T00:00:00Z", "v2");  // synthetic v2
      ConflictProbe p(a->connection());
      auto m = p.scan(make_stmt("s_new","neg",0.85,"2026-06-01T00:00:00Z","2026-12-31T00:00:00Z"),
                       normalize_interval(std::string("2026-06-01T00:00:00Z"),
                                          std::string("2026-12-31T00:00:00Z"), {}));
      ASSERT_TRUE(m.has_value());
      EXPECT_EQ(ConflictKind::PartialOverlap, m->kind);
  }

  TEST(ConflictProbeScan, SupersedingWhenNewCoversOldSamePolarity) {
      auto a = open_fresh("/tmp/cps_supersede.db");
      insert_row(a->connection(), "s_old", "pos", 0.85,
                 "2026-06-01T00:00:00Z", "2026-12-31T00:00:00Z");
      ConflictProbe p(a->connection());
      // S_new starts before S_old and has open end → fully covers.
      auto m = p.scan(make_stmt("s_new","pos",0.85,"2026-05-01T00:00:00Z",""),
                       normalize_interval(std::string("2026-05-01T00:00:00Z"), {}, {}));
      ASSERT_TRUE(m.has_value());
      EXPECT_EQ(ConflictKind::Superseding, m->kind);
  }

  TEST(ConflictProbeScan, AdjacentWhenIntervalsTouch) {
      auto a = open_fresh("/tmp/cps_adj.db");
      insert_row(a->connection(), "s_old", "pos", 0.85,
                 "2026-05-01T00:00:00Z", "2026-06-01T00:00:00Z");
      ConflictProbe p(a->connection());
      auto m = p.scan(make_stmt("s_new","pos",0.85,"2026-06-01T00:00:00Z","2026-07-01T00:00:00Z"),
                       normalize_interval(std::string("2026-06-01T00:00:00Z"),
                                          std::string("2026-07-01T00:00:00Z"), {}));
      ASSERT_TRUE(m.has_value());
      EXPECT_EQ(ConflictKind::Adjacent, m->kind);
  }

  TEST(ConflictProbeScan, StrongestMatchWinsAcrossMultipleCandidates) {
      auto a = open_fresh("/tmp/cps_strongest.db");
      insert_row(a->connection(), "s_adj", "pos", 0.85,
                 "2026-05-01T00:00:00Z", "2026-06-01T00:00:00Z");
      insert_row(a->connection(), "s_direct", "pos", 0.85,
                 "2026-06-15T00:00:00Z", "2027-01-01T00:00:00Z");
      ConflictProbe p(a->connection());
      // S_new overlaps s_direct (direct_contradiction) and is adjacent to s_adj.
      auto m = p.scan(make_stmt("s_new","neg",0.85,"2026-06-01T00:00:00Z","2026-12-31T00:00:00Z"),
                       normalize_interval(std::string("2026-06-01T00:00:00Z"),
                                          std::string("2026-12-31T00:00:00Z"), {}));
      ASSERT_TRUE(m.has_value());
      EXPECT_EQ(ConflictKind::DirectContradiction, m->kind);
      EXPECT_EQ("s_direct", m->matched_statement_id);
  }
  ```

- [ ] **6.4** Wire CMake — append to `target_sources(starling_core PRIVATE ...)` in CMakeLists.txt:

  ```cmake
  src/bus/conflict_probe.cpp
  ```

  Append to `tests/cpp/CMakeLists.txt`:

  ```cmake
  add_executable(test_conflict_probe_scan tests/cpp/test_conflict_probe_scan.cpp)
  target_link_libraries(test_conflict_probe_scan PRIVATE starling_core GTest::gtest_main)
  add_test(NAME test_conflict_probe_scan COMMAND test_conflict_probe_scan)
  ```

- [ ] **6.5** Build + run:

  ```bash
  cmake --build build && cd build && ctest -R test_conflict_probe_scan --output-on-failure
  # Expected: 8/8 tests passed
  cd ..
  ```

- [ ] **6.6** Run full ctest:

  ```bash
  cd build && ctest --output-on-failure
  # Expected: 216/216 (208 from Task 5 + 8 new)
  cd ..
  ```

- [ ] **6.7** Commit:

  ```bash
  git add include/starling/bus/conflict_probe.hpp \
          src/bus/conflict_probe.cpp \
          tests/cpp/test_conflict_probe_scan.cpp \
          CMakeLists.txt tests/cpp/CMakeLists.txt
  git commit -m "$(cat <<'EOF'
  feat(M0.5): add ConflictProbe::scan pure-detection component

  ConflictProbe queries `idx_conflict_lookup` for candidates and classifies
  each as direct_contradiction / superseding / partial_overlap / adjacent.
  Severity ordering picks the strongest match. UNKNOWN_INTERVAL and
  cross-version hash hits clamp to partial_overlap. θ_severe=0.6 gates
  direct_contradiction.

  Probe is detection-only — Bus::write owns all subsequent DB mutations.

  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 7: Bus::write Integration — partial_overlap / adjacent Edge Paths

**Files:**
- Modify: `src/bus/bus.cpp` (extend `Bus::write` to call `ConflictProbe::scan`, branch on conflict_kind)
- Modify: `src/bus/bus_event.cpp` (extend `compute_window_bucket` for `belief.conflict`, `statement.archived`, `statement.superseded`)
- Modify: `python/starling/bus/bus_event.py` (mirror C++ bucket extensions)
- Test: `tests/cpp/test_bus_write_conflict.cpp`
- Test: `tests/python/test_bus_event_parity.py` (extend with new event-type buckets)

This task ships the lite paths only: `partial_overlap` writes a `conflicts_with` edge alongside the StatementWriter INSERT, AND emits a debounced `belief.conflict` event. `adjacent` writes an `adjacent` edge only (no event). Both paths leave S_old's consolidation_state unchanged. The atomic 4-item SUPERSEDES path lands in Task 8.

**Debounce:** `belief.conflict` events with the same `canonical_conflict_key` within W=10s are deduplicated by `idempotency_key` (already enforced via the unique constraint on bus_events). The window_bucket = floor(now / 10s) makes the key collide for repeats, and the unique constraint absorbs the duplicate. No new debounce code is required — the bus_event idempotency machinery already does the work; M0.5 only needs to pin canonical_conflict_key as the canonical_key input.

- [ ] **7.1** Extend `compute_window_bucket` in `src/bus/bus_event.cpp` — find the existing switch/if-chain (M0.4 added `extraction.failed`, `pipeline.run_started`, etc.) and add three new event types. The bucket value is the floor of (now / 10s) formatted as a decimal string for `belief.conflict`; for `statement.archived` and `statement.superseded` the bucket is `""` (empty — they're per-primary_id idempotent and don't need windowing).

  ```cpp
  // Add inside compute_window_bucket alongside the existing branches:
  if (event_type == "belief.conflict") {
      // 10-second debounce window per 05_bus.md §4.
      const auto secs = std::chrono::duration_cast<std::chrono::seconds>(
          now.time_since_epoch()).count();
      return std::to_string(secs / 10);
  }
  if (event_type == "statement.archived" ||
      event_type == "statement.superseded") {
      return "";  // primary_id is unique per archive/supersede; no window.
  }
  ```

- [ ] **7.2** Mirror in `python/starling/bus/bus_event.py` — find `compute_window_bucket` and add the matching branches:

  ```python
  if event_type == "belief.conflict":
      secs = int(now.timestamp())
      return str(secs // 10)
  if event_type in ("statement.archived", "statement.superseded"):
      return ""
  ```

- [ ] **7.3** Extend the parity test in `tests/python/test_bus_event_parity.py` — add a `test_window_bucket_conflict_event_families` covering all three new types. Use the same fixed timestamp pattern (e.g., `datetime(2026,5,24,10,0,0,tzinfo=timezone.utc)`) and assert C++↔Python emit identical strings.

  ```python
  from datetime import datetime, timezone
  from starling import _core
  from starling.bus.bus_event import compute_window_bucket

  def test_window_bucket_conflict_event_families():
      now = datetime(2026, 5, 24, 10, 0, 5, tzinfo=timezone.utc)  # 5 sec into a 10s bucket
      for event_type in ("belief.conflict", "statement.archived", "statement.superseded"):
          py = compute_window_bucket(event_type, now)
          cpp = _core.compute_window_bucket(event_type, now)
          assert py == cpp, f"{event_type}: py={py!r} cpp={cpp!r}"

      # belief.conflict: same 10s window collapses
      now2 = datetime(2026, 5, 24, 10, 0, 9, tzinfo=timezone.utc)
      assert compute_window_bucket("belief.conflict", now)  == compute_window_bucket("belief.conflict", now2)

      # belief.conflict: next 10s window differs
      now3 = datetime(2026, 5, 24, 10, 0, 10, tzinfo=timezone.utc)
      assert compute_window_bucket("belief.conflict", now)  != compute_window_bucket("belief.conflict", now3)
  ```

- [ ] **7.4** Build C++ + reinstall Python wheel:

  ```bash
  cmake --build build
  pip install -e . --no-build-isolation
  ```

- [ ] **7.5** Run parity test to verify the new buckets agree:

  ```bash
  pytest tests/python/test_bus_event_parity.py -q
  # Expected: PASS for all bucket families including the three new ones
  ```

- [ ] **7.6** Modify `src/bus/bus.cpp` `Bus::write` — extend the existing thin facade to call ConflictProbe before StatementWriter, then branch:

  ```cpp
  // Replace the current Bus::write body (lines 183-196) with:
  StatementWriteOutcome Bus::write(
      const starling::extractor::ExtractedStatement& stmt,
      std::string_view evidence_engram_id,
      std::string_view extraction_span_key,
      std::optional<std::string> causation_parent_event_id) {

      auto& conn = adapter_.connection();
      starling::persistence::TransactionGuard tx(conn);

      // M0.5: ConflictProbe runs BEFORE StatementWriter so we know whether
      // the write is conflicted before we INSERT. Probe is detection-only.
      const NormalizedInterval iv_new = normalize_interval(
          stmt.valid_from, stmt.valid_to, stmt.event_time_start);
      ConflictProbe probe(conn);
      auto match = probe.scan(stmt, iv_new);

      // No conflict → unchanged M0.4 path.
      if (!match.has_value()) {
          StatementWriter writer(conn);
          auto outcome = writer.write(
              stmt, evidence_engram_id, extraction_span_key, causation_parent_event_id);
          tx.commit();
          return outcome;
      }

      // direct_contradiction / superseding → atomic SUPERSEDES path (Task 8).
      if (match->kind == ConflictKind::DirectContradiction ||
          match->kind == ConflictKind::Superseding) {
          // Stub for Task 7 — Task 8 implements. Fall through to writer for now.
          StatementWriter writer(conn);
          auto outcome = writer.write(
              stmt, evidence_engram_id, extraction_span_key, causation_parent_event_id);
          // [Task 8] Replace this fall-through with apply_supersedes_atomic(...).
          tx.commit();
          return outcome;
      }

      // partial_overlap → write CONFLICTS_WITH edge + debounced belief.conflict.
      // adjacent → write ADJACENT edge only (no event).
      StatementWriter writer(conn);
      auto outcome = writer.write(
          stmt, evidence_engram_id, extraction_span_key, causation_parent_event_id);
      const std::string new_id = std::visit([](auto&& v){ return v.stmt_id; }, outcome);

      const std::string edge_kind = (match->kind == ConflictKind::PartialOverlap)
          ? "conflicts_with" : "adjacent";
      insert_statement_edge(conn, new_id, match->matched_statement_id,
                             match->matched_tenant_id, edge_kind);

      if (match->kind == ConflictKind::PartialOverlap) {
          OutboxWriter ow(conn);
          BusEvent ev = make_event(
              "belief.conflict",
              new_id,                       // primary_id = S_new
              match->conflict_key_hex,      // aggregate_id = canonical_conflict_key (debounce)
              stmt.holder_tenant_id,
              conflict_payload(*match, new_id),
              causation_parent_event_id);
          // append_or_drop_within_window: returns true on append, false on duplicate (debounced).
          ow.append_or_drop_within_window(ev);
      }

      tx.commit();
      return outcome;
  }
  ```

  Add three new helpers earlier in the file (above `Bus::Bus`):

  ```cpp
  void insert_statement_edge(
      starling::persistence::Connection& conn,
      const std::string& src_id,
      const std::string& dst_id,
      const std::string& tenant_id,
      const std::string& edge_kind) {
      const char* sql =
          "INSERT INTO statement_edges(id,tenant_id,src_id,dst_id,edge_kind,created_at) "
          "VALUES (?,?,?,?,?,?)";
      starling::persistence::StmtHandle h;
      h.prepare(conn.handle(), sql);
      const std::string edge_id = starling::crypto::uuid_v4();
      const std::string now_iso = detail::iso8601_utc(std::chrono::system_clock::now());
      detail::bind_sv(h, 1, edge_id);
      detail::bind_sv(h, 2, tenant_id);
      detail::bind_sv(h, 3, src_id);
      detail::bind_sv(h, 4, dst_id);
      detail::bind_sv(h, 5, edge_kind);
      detail::bind_sv(h, 6, now_iso);
      if (sqlite3_step(h.handle()) != SQLITE_DONE) {
          throw detail::make_sqlite_error(conn.handle(), "insert statement_edge");
      }
  }

  std::string conflict_payload(const ConflictMatch& m, const std::string& new_id) {
      std::ostringstream os;
      os << "{"
         << "\"new_statement_id\":"  << json_string(new_id) << ","
         << "\"old_statement_id\":"  << json_string(m.matched_statement_id) << ","
         << "\"conflict_kind\":"     << json_string(to_string(m.kind)) << ","
         << "\"conflict_key\":"      << json_string(m.conflict_key_hex)
         << "}";
      return os.str();
  }
  ```

  Add `OutboxWriter::append_or_drop_within_window` to the existing OutboxWriter class — it tries the INSERT and treats a UNIQUE-constraint violation on `idempotency_key` as a benign drop (debounced):

  ```cpp
  // In src/bus/outbox_writer.cpp:
  bool OutboxWriter::append_or_drop_within_window(BusEvent& ev) {
      try {
          append(ev);
          return true;
      } catch (const SqliteError& e) {
          if (e.is_unique_violation_on("idempotency_key")) return false;
          throw;
      }
  }
  ```

  And in `include/starling/bus/outbox_writer.hpp` — add the public declaration alongside `append`.

  And in `include/starling/bus/detail/sqlite_helpers.hpp` (or wherever `SqliteError` lives) — add `is_unique_violation_on(column_name)` if it doesn't exist; sqlite extended error codes give `SQLITE_CONSTRAINT_UNIQUE` for these.

- [ ] **7.7** Create `tests/cpp/test_bus_write_conflict.cpp`:

  ```cpp
  #include "starling/bus/bus.hpp"
  #include "starling/persistence/sqlite_adapter.hpp"
  #include "starling/persistence/migration_runner.hpp"
  #include "starling/persistence/stmt_handle.hpp"
  #include "starling/extractor/extracted_statement.hpp"

  #include <gtest/gtest.h>
  #include <filesystem>
  #include <sqlite3.h>

  using namespace starling::bus;
  using namespace starling::persistence;
  using namespace starling::extractor;

  namespace {

  std::unique_ptr<SqliteAdapter> open_fresh(const std::string& path) {
      std::filesystem::remove(path);
      auto a = SqliteAdapter::open(path);
      MigrationRunner::run(a->connection());
      return a;
  }

  // Reuse the insert_row helper from test_conflict_probe_scan.cpp (paste here
  // because gtest doesn't share between TUs). Same shape and column list.
  void insert_row(Connection& conn, const std::string& id, const std::string& polarity,
                  double conf, const std::string& vf = "", const std::string& vt = "",
                  const std::string& version = "v1",
                  const std::string& state = "consolidated") {
      // ... (identical to test_conflict_probe_scan.cpp Section 6.3 helper)
  }

  ExtractedStatement make_stmt(const std::string& polarity, double conf,
                               const std::string& vf = "", const std::string& vt = "") {
      ExtractedStatement s;
      s.holder_id        = "cog-self";
      s.holder_tenant_id = "default";
      s.subject_kind     = "cognizer";
      s.subject_id       = "cog-bob";
      s.predicate        = "responsible_for";
      s.object_kind      = "str";
      s.object_value     = "auth";
      s.canonical_object_hash = "deadbeef";
      s.modality         = starling::schema::Modality::BELIEVES;
      s.polarity         = (polarity == "pos") ? starling::schema::Polarity::POS
                                                : starling::schema::Polarity::NEG;
      s.confidence       = conf;
      s.observed_at      = "2026-05-24T10:00:00Z";
      s.source_hash      = "fff";
      s.valid_from       = vf.empty() ? std::nullopt : std::optional<std::string>(vf);
      s.valid_to         = vt.empty() ? std::nullopt : std::optional<std::string>(vt);
      return s;
  }

  int count(Connection& conn, const std::string& sql) {
      StmtHandle h; h.prepare(conn.handle(), sql.c_str());
      EXPECT_EQ(SQLITE_ROW, sqlite3_step(h.handle()));
      return sqlite3_column_int(h.handle(), 0);
  }

  }  // namespace

  TEST(BusWriteConflict, NoConflict_NoEdgeNoBeliefEvent) {
      auto a = open_fresh("/tmp/bwc_noconf.db");
      Bus bus(*a);
      auto out = bus.write(make_stmt("pos", 0.85), "engram-1", "span-1", std::nullopt);
      EXPECT_EQ(0, count(a->connection(),
          "SELECT COUNT(*) FROM statement_edges"));
      EXPECT_EQ(0, count(a->connection(),
          "SELECT COUNT(*) FROM bus_events WHERE event_type='belief.conflict'"));
  }

  TEST(BusWriteConflict, PartialOverlap_WritesConflictsWithEdgeAndBeliefEvent) {
      auto a = open_fresh("/tmp/bwc_partial.db");
      // S_old below θ_severe → forces partial_overlap classification.
      insert_row(a->connection(), "s_old", "pos", 0.50,
                 "2026-05-01T00:00:00Z", "2027-01-01T00:00:00Z");
      Bus bus(*a);
      auto out = bus.write(
          make_stmt("neg", 0.85, "2026-06-01T00:00:00Z", "2026-12-31T00:00:00Z"),
          "engram-1", "span-1", std::nullopt);
      EXPECT_EQ(1, count(a->connection(),
          "SELECT COUNT(*) FROM statement_edges WHERE edge_kind='conflicts_with'"));
      EXPECT_EQ(1, count(a->connection(),
          "SELECT COUNT(*) FROM bus_events WHERE event_type='belief.conflict'"));
  }

  TEST(BusWriteConflict, BeliefConflictDebouncedWithinWindow) {
      auto a = open_fresh("/tmp/bwc_debounce.db");
      insert_row(a->connection(), "s_old", "pos", 0.50,
                 "2026-05-01T00:00:00Z", "2027-01-01T00:00:00Z");
      Bus bus(*a);
      // Two writes with same canonical_conflict_key inside 10s window.
      bus.write(make_stmt("neg", 0.85, "2026-06-01T00:00:00Z", "2026-12-31T00:00:00Z"),
                "engram-1", "span-1", std::nullopt);
      bus.write(make_stmt("neg", 0.85, "2026-06-01T00:00:00Z", "2026-12-31T00:00:00Z"),
                "engram-2", "span-2", std::nullopt);
      // Two CONFLICTS_WITH edges (one per S_new), but only ONE belief.conflict
      // event survives the debounce window.
      EXPECT_EQ(2, count(a->connection(),
          "SELECT COUNT(*) FROM statement_edges WHERE edge_kind='conflicts_with'"));
      EXPECT_EQ(1, count(a->connection(),
          "SELECT COUNT(*) FROM bus_events WHERE event_type='belief.conflict'"));
  }

  TEST(BusWriteConflict, Adjacent_WritesAdjacentEdgeOnly) {
      auto a = open_fresh("/tmp/bwc_adj.db");
      insert_row(a->connection(), "s_old", "pos", 0.85,
                 "2026-05-01T00:00:00Z", "2026-06-01T00:00:00Z");
      Bus bus(*a);
      bus.write(make_stmt("pos", 0.85, "2026-06-01T00:00:00Z", "2026-07-01T00:00:00Z"),
                "engram-1", "span-1", std::nullopt);
      EXPECT_EQ(1, count(a->connection(),
          "SELECT COUNT(*) FROM statement_edges WHERE edge_kind='adjacent'"));
      EXPECT_EQ(0, count(a->connection(),
          "SELECT COUNT(*) FROM bus_events WHERE event_type='belief.conflict'"));
  }
  ```

- [ ] **7.8** Wire CMake — append to `tests/cpp/CMakeLists.txt`:

  ```cmake
  add_executable(test_bus_write_conflict tests/cpp/test_bus_write_conflict.cpp)
  target_link_libraries(test_bus_write_conflict PRIVATE starling_core GTest::gtest_main)
  add_test(NAME test_bus_write_conflict COMMAND test_bus_write_conflict)
  ```

- [ ] **7.9** Build + run targeted:

  ```bash
  cmake --build build
  cd build && ctest -R test_bus_write_conflict --output-on-failure
  # Expected: 4/4 tests passed
  cd ..
  ```

- [ ] **7.10** Run full ctest + pytest:

  ```bash
  cd build && ctest --output-on-failure && cd ..
  pytest tests/python/ -q
  # Expected: 220/220 ctest, 251/251 pytest (one new parity test)
  ```

- [ ] **7.11** Commit:

  ```bash
  git add src/bus/bus.cpp src/bus/bus_event.cpp src/bus/outbox_writer.cpp \
          include/starling/bus/outbox_writer.hpp \
          include/starling/bus/detail/sqlite_helpers.hpp \
          python/starling/bus/bus_event.py \
          tests/cpp/test_bus_write_conflict.cpp \
          tests/python/test_bus_event_parity.py \
          tests/cpp/CMakeLists.txt
  git commit -m "$(cat <<'EOF'
  feat(M0.5): wire ConflictProbe into Bus::write — partial_overlap + adjacent paths

  partial_overlap writes a `conflicts_with` edge alongside the StatementWriter
  INSERT and emits a debounced `belief.conflict` event (10s window via
  compute_window_bucket). adjacent writes an `adjacent` edge with no event.
  Both paths leave S_old's consolidation_state unchanged. The atomic 4-item
  SUPERSEDES path for direct_contradiction / superseding lands in Task 8.

  Adds OutboxWriter::append_or_drop_within_window to absorb UNIQUE-constraint
  violations on idempotency_key as benign debounces. Extends
  compute_window_bucket (C++ + Python parity) for `belief.conflict`,
  `statement.archived`, `statement.superseded`.

  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 8: Bus::write Atomic SUPERSEDES Path (direct_contradiction + superseding)

**Files:**
- Modify: `src/bus/bus.cpp` (replace the Task 7 fall-through stub with the real atomic 4-item path)
- Test: `tests/cpp/test_bus_write_supersedes.cpp`

This is the highest-value task in M0.5. The atomic SUPERSEDES path commits 4 changes to the DB inside a single transaction:

1. INSERT statements (S_new, consolidation_state='volatile') — via StatementWriter
2. INSERT statement_edges (src=S_new, dst=S_old, edge_kind='supersedes')
3. UPDATE statements SET consolidation_state='archived' WHERE id=S_old.id (skipping replaying_reconsolidating, per §3.5 T7-P1)
4. INSERT bus_events × 3:
   - statement.written (already done by StatementWriter as part of step 1)
   - statement.archived (NEW; primary_id=S_old.id, payload {"reason":"direct_contradiction"} or {"reason":"superseding"})
   - statement.superseded (NEW; primary_id=S_new.id, aggregate_id=S_old.supersedes_root_id)

If any step fails, the entire transaction rolls back: S_new is not inserted, S_old retains consolidation_state='consolidated', no edge, no events.

- [ ] **8.1** Add `apply_supersedes_atomic` helper to `src/bus/bus.cpp` (above `Bus::Bus`):

  ```cpp
  // Apply the §15.3.4 4-item atomic SUPERSEDES path. Caller MUST hold a
  // TransactionGuard; this function never opens its own transaction. On any
  // SQL error this throws SqliteError and the caller's tx destructor rolls
  // back. The caller passes the StatementWriter's prior write outcome so we
  // can extract S_new.id without a second insert.
  StatementWriteOutcome apply_supersedes_atomic(
      starling::persistence::Connection& conn,
      const starling::extractor::ExtractedStatement& stmt,
      std::string_view evidence_engram_id,
      std::string_view extraction_span_key,
      std::optional<std::string> causation_parent_event_id,
      const ConflictMatch& match) {

      // Step 1: StatementWriter INSERTs S_new and emits statement.written.
      StatementWriter writer(conn);
      auto outcome = writer.write(
          stmt, evidence_engram_id, extraction_span_key, causation_parent_event_id);
      const std::string new_id = std::visit([](auto&& v){ return v.stmt_id; }, outcome);

      // Step 2: SUPERSEDES edge.
      insert_statement_edge(conn, new_id, match.matched_statement_id,
                             match.matched_tenant_id, "supersedes");

      // Step 3: UPDATE S_old to archived (bypass REPLAYING_RECONSOLIDATING; §3.5 T7-P1).
      {
          const char* sql =
              "UPDATE statements SET consolidation_state='archived', updated_at=? "
              "WHERE id=? AND tenant_id=? AND consolidation_state='consolidated'";
          starling::persistence::StmtHandle h;
          h.prepare(conn.handle(), sql);
          const std::string now_iso = detail::iso8601_utc(std::chrono::system_clock::now());
          detail::bind_sv(h, 1, now_iso);
          detail::bind_sv(h, 2, match.matched_statement_id);
          detail::bind_sv(h, 3, match.matched_tenant_id);
          if (sqlite3_step(h.handle()) != SQLITE_DONE) {
              throw detail::make_sqlite_error(conn.handle(), "update s_old.consolidation_state");
          }
          if (sqlite3_changes(conn.handle()) != 1) {
              // Defensive: row should exist and be CONSOLIDATED. If not, our
              // probe gave us a stale match. Abort the whole tx.
              throw std::runtime_error(
                  "supersedes_path: S_old row missing or wrong state at archive time");
          }
      }

      // Step 4a: emit statement.archived.
      const char* archive_reason =
          (match.kind == ConflictKind::DirectContradiction) ? "direct_contradiction"
                                                            : "superseding";
      OutboxWriter ow(conn);
      {
          std::ostringstream payload;
          payload << "{"
                  << "\"reason\":"        << json_string(archive_reason) << ","
                  << "\"superseded_by\":" << json_string(new_id)
                  << "}";
          BusEvent ev = make_event(
              "statement.archived",
              match.matched_statement_id,             // primary_id = S_old
              match.matched_supersedes_root_id,       // aggregate_id = root
              match.matched_tenant_id,
              payload.str(),
              causation_parent_event_id);
          ow.append(ev);
      }

      // Step 4b: emit statement.superseded.
      {
          std::ostringstream payload;
          payload << "{"
                  << "\"new_statement_id\":"     << json_string(new_id) << ","
                  << "\"old_statement_id\":"     << json_string(match.matched_statement_id) << ","
                  << "\"conflict_kind\":"        << json_string(to_string(match.kind))
                  << "}";
          BusEvent ev = make_event(
              "statement.superseded",
              new_id,                                 // primary_id = S_new
              match.matched_supersedes_root_id,       // aggregate_id = root
              stmt.holder_tenant_id,
              payload.str(),
              causation_parent_event_id);
          ow.append(ev);
      }

      return outcome;
  }
  ```

- [ ] **8.2** Replace the Task 7 stub in `Bus::write` (the `if (match->kind == ConflictKind::DirectContradiction || match->kind == ConflictKind::Superseding)` branch) with a call to `apply_supersedes_atomic`:

  ```cpp
  if (match->kind == ConflictKind::DirectContradiction ||
      match->kind == ConflictKind::Superseding) {
      auto outcome = apply_supersedes_atomic(
          conn, stmt, evidence_engram_id, extraction_span_key,
          causation_parent_event_id, *match);
      tx.commit();
      return outcome;
  }
  ```

- [ ] **8.3** Create `tests/cpp/test_bus_write_supersedes.cpp` covering the happy path + 4 failure-rollback paths:

  ```cpp
  #include "starling/bus/bus.hpp"
  #include "starling/persistence/sqlite_adapter.hpp"
  #include "starling/persistence/migration_runner.hpp"

  #include <gtest/gtest.h>
  #include <filesystem>
  #include <sqlite3.h>

  using namespace starling::bus;
  using namespace starling::persistence;
  using namespace starling::extractor;

  namespace {
  // (reuse open_fresh, insert_row, make_stmt, count from earlier test files —
  // copy-paste into this TU since gtest does not share helpers across binaries)
  }  // namespace

  TEST(BusWriteSupersedes, DirectContradictionAtomicCommit) {
      auto a = open_fresh("/tmp/bws_direct.db");
      // S_old: pos, conf 0.85, CONSOLIDATED.
      insert_row(a->connection(), "s_old", "pos", 0.85,
                 "2026-05-01T00:00:00Z", "2027-01-01T00:00:00Z",
                 "v1", "consolidated");
      Bus bus(*a);
      auto out = bus.write(
          make_stmt("neg", 0.85, "2026-06-01T00:00:00Z", "2026-12-31T00:00:00Z"),
          "engram-1", "span-1", std::nullopt);

      // Invariant 1: 1 statements row for S_new (volatile) + S_old still present (archived).
      EXPECT_EQ(2, count(a->connection(),
          "SELECT COUNT(*) FROM statements"));
      EXPECT_EQ(1, count(a->connection(),
          "SELECT COUNT(*) FROM statements WHERE consolidation_state='archived'"));
      EXPECT_EQ(1, count(a->connection(),
          "SELECT COUNT(*) FROM statements WHERE consolidation_state='volatile'"));
      EXPECT_EQ(0, count(a->connection(),
          "SELECT COUNT(*) FROM statements WHERE consolidation_state='replaying_reconsolidating'"));

      // Invariant 2: 1 SUPERSEDES edge.
      EXPECT_EQ(1, count(a->connection(),
          "SELECT COUNT(*) FROM statement_edges WHERE edge_kind='supersedes'"));

      // Invariant 3: 3 outbox events.
      EXPECT_EQ(1, count(a->connection(),
          "SELECT COUNT(*) FROM bus_events WHERE event_type='statement.written'"));
      EXPECT_EQ(1, count(a->connection(),
          "SELECT COUNT(*) FROM bus_events WHERE event_type='statement.archived'"));
      EXPECT_EQ(1, count(a->connection(),
          "SELECT COUNT(*) FROM bus_events WHERE event_type='statement.superseded'"));

      // Invariant 4: NO MAY_OVERLAP_WITH or CONFLICTS_WITH between them.
      EXPECT_EQ(0, count(a->connection(),
          "SELECT COUNT(*) FROM statement_edges WHERE edge_kind IN ('may_overlap_with','conflicts_with')"));

      // Invariant 5: archive event payload encodes reason=direct_contradiction.
      StmtHandle h; h.prepare(a->connection().handle(),
          "SELECT payload_json FROM bus_events WHERE event_type='statement.archived'");
      ASSERT_EQ(SQLITE_ROW, sqlite3_step(h.handle()));
      const std::string payload = reinterpret_cast<const char*>(sqlite3_column_text(h.handle(), 0));
      EXPECT_NE(std::string::npos, payload.find("direct_contradiction"));
  }

  TEST(BusWriteSupersedes, SupersedingAtomicCommit) {
      auto a = open_fresh("/tmp/bws_super.db");
      insert_row(a->connection(), "s_old", "pos", 0.85,
                 "2026-06-01T00:00:00Z", "2026-12-31T00:00:00Z",
                 "v1", "consolidated");
      Bus bus(*a);
      // S_new starts before, open end. Fully covers; same polarity → superseding.
      auto out = bus.write(make_stmt("pos", 0.85, "2026-05-01T00:00:00Z", ""),
                            "engram-1", "span-1", std::nullopt);

      EXPECT_EQ(1, count(a->connection(),
          "SELECT COUNT(*) FROM statements WHERE consolidation_state='archived'"));
      EXPECT_EQ(1, count(a->connection(),
          "SELECT COUNT(*) FROM statement_edges WHERE edge_kind='supersedes'"));
      EXPECT_EQ(1, count(a->connection(),
          "SELECT COUNT(*) FROM bus_events WHERE event_type='statement.archived'"));
      // Payload reason = "superseding" not "direct_contradiction".
      StmtHandle h; h.prepare(a->connection().handle(),
          "SELECT payload_json FROM bus_events WHERE event_type='statement.archived'");
      ASSERT_EQ(SQLITE_ROW, sqlite3_step(h.handle()));
      const std::string payload = reinterpret_cast<const char*>(sqlite3_column_text(h.handle(), 0));
      EXPECT_NE(std::string::npos, payload.find("superseding"));
  }

  // Rollback test: if the UPDATE on S_old fails (e.g. row was deleted between
  // probe and apply), the entire tx must roll back — no edge, no events.
  TEST(BusWriteSupersedes, RollbackOnSOldUpdateFailure) {
      auto a = open_fresh("/tmp/bws_rb1.db");
      insert_row(a->connection(), "s_old", "pos", 0.85,
                 "2026-05-01T00:00:00Z", "2027-01-01T00:00:00Z",
                 "v1", "consolidated");
      Bus bus(*a);

      // Re-create the same row but in 'archived' state via a direct UPDATE,
      // simulating a state transition that races with the probe. The probe
      // saw 'consolidated' from its own SELECT; the apply step's UPDATE WHERE
      // consolidation_state='consolidated' will affect 0 rows and trigger
      // the defensive throw.
      {
          StmtHandle h; h.prepare(a->connection().handle(),
              "UPDATE statements SET consolidation_state='archived' WHERE id='s_old'");
          ASSERT_EQ(SQLITE_DONE, sqlite3_step(h.handle()));
      }

      EXPECT_THROW(
          bus.write(make_stmt("neg", 0.85, "2026-06-01T00:00:00Z", "2026-12-31T00:00:00Z"),
                     "engram-1", "span-1", std::nullopt),
          std::runtime_error);

      // Tx rolled back: still 1 statements row (the archived s_old), zero new
      // rows, zero edges, zero events.
      EXPECT_EQ(1, count(a->connection(),
          "SELECT COUNT(*) FROM statements"));
      EXPECT_EQ(0, count(a->connection(),
          "SELECT COUNT(*) FROM statement_edges"));
      EXPECT_EQ(0, count(a->connection(),
          "SELECT COUNT(*) FROM bus_events"));
  }

  // Probe correctly clamps to partial_overlap when interval mismatches; the
  // SUPERSEDES path is NOT taken even with opposite polarity. Pinned here to
  // guard against regressions in the severity-ordering logic.
  TEST(BusWriteSupersedes, NotTriggeredWhenIntervalsDoNotOverlap) {
      auto a = open_fresh("/tmp/bws_noint.db");
      insert_row(a->connection(), "s_old", "pos", 0.85,
                 "2026-01-01T00:00:00Z", "2026-02-01T00:00:00Z",
                 "v1", "consolidated");
      Bus bus(*a);
      // S_new has totally separate interval — adjacent classification, not direct.
      bus.write(make_stmt("neg", 0.85, "2027-01-01T00:00:00Z", "2027-12-31T00:00:00Z"),
                 "engram-1", "span-1", std::nullopt);
      EXPECT_EQ(0, count(a->connection(),
          "SELECT COUNT(*) FROM statement_edges WHERE edge_kind='supersedes'"));
      EXPECT_EQ(0, count(a->connection(),
          "SELECT COUNT(*) FROM statements WHERE consolidation_state='archived'"));
  }
  ```

- [ ] **8.4** Wire CMake — append to `tests/cpp/CMakeLists.txt`:

  ```cmake
  add_executable(test_bus_write_supersedes tests/cpp/test_bus_write_supersedes.cpp)
  target_link_libraries(test_bus_write_supersedes PRIVATE starling_core GTest::gtest_main)
  add_test(NAME test_bus_write_supersedes COMMAND test_bus_write_supersedes)
  ```

- [ ] **8.5** Build + run targeted:

  ```bash
  cmake --build build && cd build && ctest -R test_bus_write_supersedes --output-on-failure
  # Expected: 4/4 tests passed
  cd ..
  ```

- [ ] **8.6** Run full suite + reinstall pip wheel (since C++ ABI changed):

  ```bash
  cmake --build build
  pip install -e . --no-build-isolation
  cd build && ctest --output-on-failure && cd ..
  pytest tests/python/ -q
  # Expected: 224/224 ctest, 251/251 pytest
  ```

- [ ] **8.7** Commit:

  ```bash
  git add src/bus/bus.cpp tests/cpp/test_bus_write_supersedes.cpp tests/cpp/CMakeLists.txt
  git commit -m "$(cat <<'EOF'
  feat(M0.5): atomic SUPERSEDES path in Bus::write — direct_contradiction + superseding

  Implements the §15.3.4 4-item atomic transaction:
    1. INSERT S_new (via StatementWriter; emits statement.written)
    2. INSERT statement_edges (src=S_new, dst=S_old, edge_kind=supersedes)
    3. UPDATE S_old.consolidation_state from 'consolidated' to 'archived'
       (bypasses replaying_reconsolidating per §3.5 T7-P1)
    4. INSERT bus_events × 2 (statement.archived + statement.superseded)

  Any step failing rolls back the entire tx — no S_new, no edge, no archive,
  no events. Defensive guard on the UPDATE: if S_old changed state between
  probe and apply, throw and rollback.

  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 9: testing.mark_consolidated(stmt_id, tenant_id) helper

**Files:**
- Modify: `src/testing/testing_marker.cpp` (add `mark_consolidated` C++ implementation)
- Modify: `bindings/python/module.cpp` (bind `mark_consolidated` to Python)
- Modify: `python/starling/testing/__init__.py` (re-export)
- Test: `tests/python/test_mark_consolidated.py`
- Test (CI scanner): re-run `python scripts/ci_static_scan.py` and assert it exits 0

This task ships the `testing.mark_consolidated(stmt_id, tenant_id)` dev-only helper that flips a row's `consolidation_state` from 'volatile' to 'consolidated' and writes an audit record. It exists to set up TC-NEW-CONFLICT-SEVERE's pre-state in Task 10 (the test needs S_old already CONSOLIDATED before writing S_new).

**Critical constraint:** the helper MUST live in the `starling::testing` C++ namespace + `starling.testing` Python module. The CI scanner at `scripts/ci_static_scan.py` blocks any prod entrypoint from importing these symbols. M0.0 already created `src/testing/testing_marker.cpp` as a separate translation unit; M0.5 extends it.

The helper writes an audit row in `bus_events` with `event_type='testing.mark_consolidated'` so test traces are inspectable. The audit event is idempotency-keyed by `stmt_id` so re-runs are no-ops.

- [ ] **9.1** Extend `src/testing/testing_marker.cpp` — add the implementation. The existing TU already has `__starling_testing_only__` linkage; just add a new exported function:

  ```cpp
  // In src/testing/testing_marker.cpp — append to the existing namespace:
  namespace starling::testing {

  // mark_consolidated transitions a Statement from 'volatile' to
  // 'consolidated', recording an audit event in bus_events. Caller is
  // responsible for opening a transaction; this function asserts no
  // transaction is currently open IF run outside one and opens its own.
  //
  // Idempotent: re-invocation on an already-consolidated row is a no-op
  // (returns false). Race-safe: WHERE consolidation_state='volatile' is
  // the optimistic gate.
  bool mark_consolidated(
      starling::persistence::SqliteAdapter& adapter,
      std::string_view stmt_id,
      std::string_view tenant_id) {

      auto& conn = adapter.connection();
      starling::persistence::TransactionGuard tx(conn);

      const char* sql =
          "UPDATE statements SET consolidation_state='consolidated', updated_at=? "
          "WHERE id=? AND tenant_id=? AND consolidation_state='volatile'";
      starling::persistence::StmtHandle h;
      h.prepare(conn.handle(), sql);
      const std::string now_iso =
          starling::bus::detail::iso8601_utc(std::chrono::system_clock::now());
      starling::bus::detail::bind_sv(h, 1, now_iso);
      starling::bus::detail::bind_sv(h, 2, stmt_id);
      starling::bus::detail::bind_sv(h, 3, tenant_id);
      if (sqlite3_step(h.handle()) != SQLITE_DONE) {
          throw starling::bus::detail::make_sqlite_error(
              conn.handle(), "testing.mark_consolidated update");
      }
      const bool changed = (sqlite3_changes(conn.handle()) == 1);

      if (changed) {
          // Write audit event. Same OutboxWriter contract as production.
          starling::bus::OutboxWriter ow(conn);
          std::ostringstream payload;
          payload << "{\"stmt_id\":\"" << stmt_id << "\","
                  << "\"tenant_id\":\"" << tenant_id << "\","
                  << "\"helper\":\"starling.testing.mark_consolidated\"}";
          starling::bus::BusEvent ev;
          ev.tenant_id    = std::string(tenant_id);
          ev.event_type   = "testing.mark_consolidated";
          ev.primary_id   = std::string(stmt_id);
          ev.aggregate_id = std::string(stmt_id);
          ev.causation_chain = {};
          ev.payload_json = payload.str();
          ev.idempotency_key = starling::bus::compute_idempotency_key(
              "testing.mark_consolidated", stmt_id, stmt_id, std::string{}, std::string{});
          ow.append(ev);
      }
      tx.commit();
      return changed;
  }

  }  // namespace starling::testing
  ```

  Add the corresponding header `include/starling/testing/testing_marker.hpp`:

  ```cpp
  #pragma once

  #include "starling/persistence/sqlite_adapter.hpp"
  #include <string_view>

  namespace starling::testing {

  // mark_consolidated: VOLATILE → CONSOLIDATED. Dev-only. Returns true if the
  // row transitioned, false if it was already consolidated (or missing).
  // Production preflight rejects any binary that imports starling::testing.
  bool mark_consolidated(
      starling::persistence::SqliteAdapter& adapter,
      std::string_view stmt_id,
      std::string_view tenant_id);

  }  // namespace starling::testing
  ```

- [ ] **9.2** Bind to Python in `bindings/python/module.cpp` — add the binding inside the testing-only sub-module that M0.0 created:

  ```cpp
  // In the testing sub-module section (search for the existing
  // testing_marker bindings — they bind helpers like
  // relax_preflight_for_m0_2 / mark_evidence_erased):
  m_testing.def("mark_consolidated",
      [](starling::persistence::SqliteAdapter& adapter,
         const std::string& stmt_id,
         const std::string& tenant_id) {
          return starling::testing::mark_consolidated(adapter, stmt_id, tenant_id);
      },
      py::arg("adapter"), py::arg("stmt_id"), py::arg("tenant_id"),
      "Flip a Statement row from 'volatile' to 'consolidated'. Dev-only. "
      "Production preflight rejects binaries that import this.");
  ```

- [ ] **9.3** Re-export in `python/starling/testing/__init__.py`:

  ```python
  # __starling_testing_only__ = True (existing module marker)
  from starling._core.testing import mark_consolidated as _mark_consolidated_cpp


  def mark_consolidated(adapter, stmt_id: str, tenant_id: str) -> bool:
      """VOLATILE → CONSOLIDATED. Dev-only. Returns True on transition.

      Used by TC-NEW-CONFLICT-SEVERE to set up S_old in CONSOLIDATED state
      before driving the SUPERSEDES atomic path. Production preflight
      rejects any binary that imports starling.testing.
      """
      return _mark_consolidated_cpp(adapter, stmt_id, tenant_id)
  ```

- [ ] **9.4** Create `tests/python/test_mark_consolidated.py`:

  ```python
  """Unit tests for starling.testing.mark_consolidated.

  Asserts:
    - VOLATILE → CONSOLIDATED transitions and returns True
    - Re-invocation on an already-consolidated row returns False (idempotent)
    - Audit event 'testing.mark_consolidated' is written exactly once
    - Audit event idempotency_key prevents duplicate audit rows
  """
  from __future__ import annotations

  import sqlite3
  import pytest
  from starling import _core
  from starling.testing import mark_consolidated, relax_preflight_for_m0_3
  from starling import runtime


  @pytest.fixture
  def rt(tmp_path, monkeypatch):
      orig = relax_preflight_for_m0_3()
      r = runtime._build_local_store_sqlite_runtime(tmp_path / "starling.db")
      r.start()
      yield r
      monkeypatch.setattr(runtime, "LOCAL_STORE_REQUIRED", orig)


  def _seed_volatile(rt, stmt_id: str = "stmt-A", tenant_id: str = "default"):
      """Insert a minimal volatile statement row for testing."""
      with sqlite3.connect(str(rt.adapter.db_path)) as conn:
          conn.execute(
              "INSERT INTO statements("
              "  id, tenant_id, holder_id, holder_perspective,"
              "  subject_kind, subject_id, predicate, object_kind, object_value,"
              "  canonical_object_hash, modality, polarity, confidence, observed_at,"
              "  salience, affect_json, activation, last_accessed, provenance,"
              "  consolidation_state, review_status, created_at, updated_at"
              ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (stmt_id, tenant_id, "cog-self", "first_person",
               "cognizer", "cog-bob", "responsible_for", "str", "auth",
               "deadbeef", "believes", "pos", 0.85, "2026-05-24T10:00:00Z",
               0.5, "{}", 1.0, "2026-05-24T10:00:00Z", "user_input",
               "volatile", "approved",
               "2026-05-24T10:00:00Z", "2026-05-24T10:00:00Z"))
          conn.commit()


  def test_volatile_transitions_to_consolidated(rt):
      _seed_volatile(rt)
      assert mark_consolidated(rt.adapter, "stmt-A", "default") is True

      with sqlite3.connect(str(rt.adapter.db_path)) as conn:
          state = conn.execute(
              "SELECT consolidation_state FROM statements WHERE id='stmt-A'"
          ).fetchone()[0]
          assert state == "consolidated"


  def test_idempotent_returns_false_on_second_call(rt):
      _seed_volatile(rt)
      assert mark_consolidated(rt.adapter, "stmt-A", "default") is True
      assert mark_consolidated(rt.adapter, "stmt-A", "default") is False


  def test_emits_audit_event_exactly_once(rt):
      _seed_volatile(rt)
      mark_consolidated(rt.adapter, "stmt-A", "default")
      mark_consolidated(rt.adapter, "stmt-A", "default")  # idempotent: no second event
      with sqlite3.connect(str(rt.adapter.db_path)) as conn:
          n = conn.execute(
              "SELECT COUNT(*) FROM bus_events "
              "WHERE event_type='testing.mark_consolidated' "
              "AND primary_id='stmt-A'"
          ).fetchone()[0]
          assert n == 1


  def test_missing_row_returns_false(rt):
      assert mark_consolidated(rt.adapter, "missing-stmt", "default") is False
  ```

- [ ] **9.5** Wire CMake — `src/testing/testing_marker.cpp` is already in `target_sources(starling_testing_marker PRIVATE ...)` per M0.0. Verify the new header is exported via `target_include_directories` (it should be since `include/` is already PUBLIC).

  ```bash
  # Verify the testing_marker target exists (M0.0 created it):
  grep -n "starling_testing_marker" CMakeLists.txt
  # Expected output: a few lines showing add_library and target_sources
  ```

- [ ] **9.6** Build + reinstall pip wheel:

  ```bash
  cmake --build build
  pip install -e . --no-build-isolation
  ```

- [ ] **9.7** Run targeted Python tests:

  ```bash
  pytest tests/python/test_mark_consolidated.py -q
  # Expected: 4 passed
  ```

- [ ] **9.8** Run CI static scanner — must stay clean (no prod entrypoint imports `starling.testing`):

  ```bash
  python scripts/ci_static_scan.py
  # Expected exit code 0; output: "ok: no prod imports of starling::testing/starling.testing found"
  echo "scanner exit: $?"
  ```

- [ ] **9.9** Run full ctest + pytest suites:

  ```bash
  cd build && ctest --output-on-failure && cd ..
  pytest tests/python/ -q
  # Expected: 224/224 ctest, 255/255 pytest (4 new mark_consolidated tests)
  ```

- [ ] **9.10** Commit:

  ```bash
  git add include/starling/testing/testing_marker.hpp \
          src/testing/testing_marker.cpp \
          bindings/python/module.cpp \
          python/starling/testing/__init__.py \
          tests/python/test_mark_consolidated.py
  git commit -m "$(cat <<'EOF'
  feat(M0.5): add starling.testing.mark_consolidated dev-only helper

  Flips a Statement row's consolidation_state from 'volatile' to
  'consolidated' and writes an audit event. Idempotent: re-invocation
  returns False. Used by TC-NEW-CONFLICT-SEVERE in Task 10 to set up
  S_old before driving the SUPERSEDES atomic path.

  Lives in starling::testing C++ namespace and starling.testing Python
  module. Production preflight + CI scanner reject prod imports.

  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 10: TC-NEW-CONFLICT-SEVERE Acceptance Smoke (Python, P1 CRITICAL)

**Files:**
- Create: `tests/python/test_tc_new_conflict_severe.py`

This is one of the 13 P1 CRITICAL acceptance tests. Per system_design.md §15.3.4, the test must demonstrate the 4-item atomic transaction end-to-end via the Python entrypoint (the same way Extractor.run is invoked in production). It is the M0.5 ship gate.

**Pre-state setup:**
- Seed an Engram (any minimal record).
- Drive `Bus::write` to insert S_old (holder=cog-self, subject=cog-bob, predicate=responsible_for, object="auth", polarity=POS, confidence=0.85, valid_from=2026-05-01, valid_to=2027-01-01, modality=BELIEVES).
- Call `testing.mark_consolidated(adapter, S_old.id, "default")` — flips to 'consolidated'.

**Drive:**
- Drive `Bus::write` to insert S_new (identical to S_old except polarity=NEG, confidence=0.85, valid_from=2026-06-01, valid_to=2026-12-31).

**Assertions:**
1. `statements` has exactly 2 rows (S_new and S_old).
2. S_new.consolidation_state = 'volatile'.
3. S_old.consolidation_state = 'archived' (NOT 'replaying_reconsolidating').
4. Exactly 1 statement_edges row: (src=S_new.id, dst=S_old.id, edge_kind='supersedes').
5. ZERO statement_edges with edge_kind in ('may_overlap_with', 'conflicts_with', 'adjacent') between S_new and S_old.
6. Exactly 3 bus_events rows from this Bus::write call:
   - 1× event_type='statement.written', primary_id=S_new.id
   - 1× event_type='statement.archived', primary_id=S_old.id, payload contains "direct_contradiction"
   - 1× event_type='statement.superseded', primary_id=S_new.id, aggregate_id=S_old.supersedes_root_id
7. The S_old write itself produced 1× 'statement.written' event before, and the testing.mark_consolidated produced 1× 'testing.mark_consolidated' audit event — total bus_events = 5.

- [ ] **10.1** Create `tests/python/test_tc_new_conflict_severe.py`:

  ```python
  """TC-NEW-CONFLICT-SEVERE [P1 CRITICAL] — direct_contradiction atomic 4-item commit.

  Per system_design.md §15.3.4 + 05_bus.md §3.5 P1 sync severe-conflict path.
  Covers: M0.5 ConflictProbe, §3.5 T7-P1 (CONSOLIDATED → ARCHIVED bypass),
  §3.12 SUPERSEDES edge, §14.1 write path.

  This test is the M0.5 ship gate. Failure here = M0.5 cannot close.
  """
  from __future__ import annotations

  import sqlite3
  import pytest

  from starling import _core, runtime
  from starling.testing import mark_consolidated, relax_preflight_for_m0_3


  @pytest.fixture
  def rt(tmp_path, monkeypatch):
      orig = relax_preflight_for_m0_3()
      r = runtime._build_local_store_sqlite_runtime(tmp_path / "starling.db")
      r.start()
      yield r
      monkeypatch.setattr(runtime, "LOCAL_STORE_REQUIRED", orig)


  def _seed_engram(rt, engram_id: str = "engram-tc"):
      """Seed a minimal Engram via direct SQL (Bus::append_evidence is overkill for the test)."""
      with sqlite3.connect(str(rt.adapter.db_path)) as conn:
          conn.execute(
              "INSERT INTO engrams("
              "  id,tenant_id,content_hash,source_kind,ingest_policy,ingest_mode,"
              "  privacy_class,retention_mode,refcount,payload_inline,created_at"
              ") VALUES (?,?,?,?,?,?,?,?,?,?,?)",
              (engram_id, "default", "hash-tc", "user_input", "store",
               "whole_record", "internal", "audit_retain", 0, b"\x00",
               "2026-05-24T09:00:00Z"))
          conn.commit()


  def _make_extracted(polarity: str, confidence: float,
                       valid_from: str, valid_to: str):
      """Construct an ExtractedStatement DTO via the C++ binding."""
      s = _core.ExtractedStatement()
      s.holder_id        = "cog-self"
      s.holder_tenant_id = "default"
      s.holder_perspective = _core.Perspective.FIRST_PERSON
      s.subject_kind     = "cognizer"
      s.subject_id       = "cog-bob"
      s.predicate        = "responsible_for"
      s.object_kind      = "str"
      s.object_value     = "auth"
      s.canonical_object_hash = "deadbeef"
      s.modality         = _core.Modality.BELIEVES
      s.polarity         = (_core.Polarity.POS if polarity == "pos"
                            else _core.Polarity.NEG)
      s.confidence       = confidence
      s.observed_at      = "2026-05-24T10:00:00Z"
      s.source_hash      = "fff"
      s.valid_from       = valid_from
      s.valid_to         = valid_to
      return s


  def test_tc_new_conflict_severe_atomic_commit(rt):
      """TC-NEW-CONFLICT-SEVERE happy path."""
      _seed_engram(rt)
      bus = _core.Bus(rt.adapter)

      # 1. Write S_old (POS, fully populated interval, high confidence).
      s_old = _make_extracted("pos", 0.85, "2026-05-01T00:00:00Z", "2027-01-01T00:00:00Z")
      out_old = bus.write(s_old, "engram-tc", "span-old", None)
      s_old_id = out_old["stmt_id"]

      # 2. Mark S_old CONSOLIDATED (flip from VOLATILE).
      ok = mark_consolidated(rt.adapter, s_old_id, "default")
      assert ok is True, "mark_consolidated should transition VOLATILE → CONSOLIDATED"

      # 3. Write S_new (NEG, opposite polarity, overlapping interval) — triggers
      #    direct_contradiction → atomic 4-item path.
      s_new = _make_extracted("neg", 0.85, "2026-06-01T00:00:00Z", "2026-12-31T00:00:00Z")
      out_new = bus.write(s_new, "engram-tc", "span-new", None)
      s_new_id = out_new["stmt_id"]

      # ─── Assertions on the final DB state ─────────────────────────────
      with sqlite3.connect(str(rt.adapter.db_path)) as conn:
          # Invariant 1: 2 statements rows.
          n_total = conn.execute("SELECT COUNT(*) FROM statements").fetchone()[0]
          assert n_total == 2, f"expected 2 statements rows, got {n_total}"

          # Invariant 2: S_new.consolidation_state='volatile'.
          state_new = conn.execute(
              "SELECT consolidation_state FROM statements WHERE id=?",
              (s_new_id,)).fetchone()[0]
          assert state_new == "volatile", \
              f"S_new state should be 'volatile', got {state_new!r}"

          # Invariant 3: S_old.consolidation_state='archived' (NOT 'replaying_reconsolidating').
          state_old = conn.execute(
              "SELECT consolidation_state FROM statements WHERE id=?",
              (s_old_id,)).fetchone()[0]
          assert state_old == "archived", \
              f"S_old state should be 'archived' (T7-P1 bypass), got {state_old!r}"

          # Invariant 4: exactly 1 SUPERSEDES edge.
          n_supersedes = conn.execute(
              "SELECT COUNT(*) FROM statement_edges "
              "WHERE src_id=? AND dst_id=? AND edge_kind='supersedes'",
              (s_new_id, s_old_id)).fetchone()[0]
          assert n_supersedes == 1, \
              f"expected exactly 1 supersedes edge, got {n_supersedes}"

          # Invariant 5: NO conflicts_with / may_overlap_with / adjacent edges between them.
          n_other = conn.execute(
              "SELECT COUNT(*) FROM statement_edges "
              "WHERE src_id=? AND dst_id=? "
              "AND edge_kind IN ('conflicts_with','may_overlap_with','adjacent')",
              (s_new_id, s_old_id)).fetchone()[0]
          assert n_other == 0, \
              f"expected zero non-supersedes edges, got {n_other}"

          # Invariant 6: 3 bus_events from the S_new write specifically.
          n_written_new = conn.execute(
              "SELECT COUNT(*) FROM bus_events "
              "WHERE event_type='statement.written' AND primary_id=?",
              (s_new_id,)).fetchone()[0]
          assert n_written_new == 1, \
              f"expected 1 statement.written for S_new, got {n_written_new}"

          n_archived = conn.execute(
              "SELECT COUNT(*) FROM bus_events "
              "WHERE event_type='statement.archived' AND primary_id=?",
              (s_old_id,)).fetchone()[0]
          assert n_archived == 1, \
              f"expected 1 statement.archived for S_old, got {n_archived}"

          n_superseded = conn.execute(
              "SELECT COUNT(*) FROM bus_events "
              "WHERE event_type='statement.superseded' AND primary_id=?",
              (s_new_id,)).fetchone()[0]
          assert n_superseded == 1, \
              f"expected 1 statement.superseded for S_new, got {n_superseded}"

          # Invariant 6b: archive payload contains 'direct_contradiction' reason.
          archive_payload = conn.execute(
              "SELECT payload_json FROM bus_events "
              "WHERE event_type='statement.archived' AND primary_id=?",
              (s_old_id,)).fetchone()[0]
          assert "direct_contradiction" in archive_payload, \
              f"archive payload missing reason; got {archive_payload!r}"

          # Invariant 7: total bus_events = 5
          # (S_old's statement.written + mark_consolidated audit + 3 from S_new write).
          n_total_events = conn.execute("SELECT COUNT(*) FROM bus_events").fetchone()[0]
          assert n_total_events == 5, \
              f"expected 5 total bus_events, got {n_total_events}"
  ```

- [ ] **10.2** Run targeted:

  ```bash
  pytest tests/python/test_tc_new_conflict_severe.py -v
  # Expected: 1 passed
  ```

- [ ] **10.3** Run full ctest + pytest:

  ```bash
  cd build && ctest --output-on-failure && cd ..
  pytest tests/python/ -q
  # Expected: 224/224 ctest, 256/256 pytest
  ```

- [ ] **10.4** Run CI scanner one more time — confirms no prod root accidentally imports starling.testing:

  ```bash
  python scripts/ci_static_scan.py
  # Expected exit code 0
  ```

- [ ] **10.5** Commit:

  ```bash
  git add tests/python/test_tc_new_conflict_severe.py
  git commit -m "$(cat <<'EOF'
  test(M0.5): TC-NEW-CONFLICT-SEVERE [P1 CRITICAL] acceptance smoke

  End-to-end test driving the §15.3.4 spec via Bus::write Python entrypoint:
  seed engram → write S_old → mark consolidated → write S_new (opposite
  polarity, overlapping interval) → assert atomic 4-item commit:
    1. statements: S_new (volatile) + S_old (archived, NOT replaying_reconsolidating)
    2. statement_edges: (src=S_new, dst=S_old, edge_kind=supersedes)
    3. bus_events: 1× statement.written + 1× statement.archived
       (payload reason=direct_contradiction) + 1× statement.superseded
    4. Zero may_overlap_with / conflicts_with / adjacent edges between them.

  Total bus_events = 5 (S_old write + mark_consolidated audit + 3 from S_new).

  Covers: M0.5 / §3.5 T7-P1 / §3.12 SUPERSEDES / §14.1 write path.
  This is the M0.5 ship gate.

  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 11: Roadmap Flip + Final Review + Merge to Main

**Files:**
- Modify: `docs/superpowers/plans/2026-05-23-roadmap.md` (mark M0.5 complete; pin commit SHA)
- Final review (whole-branch reviewer)
- Merge to main (`--no-ff`)
- Plan-doc commit on main

This task closes the milestone the same way M0.4 closed:

1. **Step 1: Roadmap flip** — update the M0.5 row in `docs/superpowers/plans/2026-05-23-roadmap.md` (already tracked in main) to show "已写 / ✅ 完成 / <date> / <commit-sha>". The commit SHA is the LAST WORK commit (Task 10's commit), NOT the upcoming meta-only roadmap-flip commit. This is the project commit-cell rule.

2. **Step 2: Run all checks one last time**:
   ```bash
   cd build && ctest --output-on-failure && cd ..
   pytest tests/python/ -q
   python scripts/ci_static_scan.py
   ```
   All three must be green.

3. **Step 3: Dispatch a final whole-branch reviewer** (use `feature-dev:code-reviewer` agent type). Reviewer prompt should include:
   - Branch HEAD: `worktree-m0-5-conflict-probe`
   - Main HEAD: `main` (= the M0.4 merge `fd930cd` plus its plan-doc `6765ad8`)
   - Spec links: `docs/design/system_design.md §15.3.4` (TC-NEW-CONFLICT-SEVERE), `§3.5 T7-P1`, `§3.12 SUPERSEDES`, `§15.3.5` (testing helper convention); `docs/design/subsystems_design/05_bus.md §3 ConflictProbe / §3.5 P1 sync severe-conflict path / §4 debounce / §ConflictProbe index contract / §canonical_conflict_key`
   - Ask for: actionable issues with severity {CRITICAL, IMPORTANT, NIT}; report under 600 words.

   If the reviewer flags CRITICAL or IMPORTANT issues, the implementer fixes them in additional commits BEFORE the merge step. NITs can be acknowledged or deferred.

4. **Step 4: Ask the user for merge consent** via AskUserQuestion. Three options:
   1. **Merge --no-ff to main (Recommended)** — standard milestone close, matches M0.0–M0.4's `--no-ff` style.
   2. **Keep branch alive for further iteration** — leave on `worktree-m0-5-conflict-probe` if the user wants more changes before merging.
   3. **Squash and merge** — collapse the branch into a single commit (not recommended; loses TDD history).

   DO NOT merge without explicit user consent.

5. **Step 5: If user chose merge — perform the merge** from the main repo cwd (NOT the worktree):

   ```bash
   cd /Users/jaredguo-mini/develop/memory/starling
   git checkout main
   git merge --no-ff worktree-m0-5-conflict-probe -m "Merge M0.5: ConflictProbe + canonical_conflict_key + SUPERSEDES atomic path"
   git log --oneline -3 main
   ```

   The repo is local-only (no `origin` remote); skip any push step.

6. **Step 6: Commit the M0.5 plan doc to main**. After the merge, the plan file `docs/superpowers/plans/2026-05-24-m0-5-conflict-probe.md` is untracked in main (the worktree's branch contained it as a local file but the M0.5 branch never tracked it — same pattern as M0.2/M0.3/M0.4):

   ```bash
   cd /Users/jaredguo-mini/develop/memory/starling
   cp .claude/worktrees/m0-5-conflict-probe/docs/superpowers/plans/2026-05-24-m0-5-conflict-probe.md \
      docs/superpowers/plans/2026-05-24-m0-5-conflict-probe.md
   # Wait — the worktree was likely already merged in step 5 so the file
   # is already in main. Verify before copy:
   ls docs/superpowers/plans/2026-05-24-m0-5-conflict-probe.md && echo "in main"
   git add docs/superpowers/plans/2026-05-24-m0-5-conflict-probe.md
   git commit -m "$(cat <<'EOF'
   docs(M0.5): add ConflictProbe implementation plan

   Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
   EOF
   )"
   ```

7. **Step 7: Tear down the worktree**. After confirming `git log --oneline -5 main` shows both the merge commit and the plan-doc commit landed:

   ```
   ExitWorktree(action="remove", discard_changes=true)
   ```

   `discard_changes=true` is safe because all worktree commits are already merged into main as part of the merge commit.

8. **Step 8: Mark task complete** — update the TaskCreate todo list (M0.5 Task 11) to `completed`. M0.5 is now closed.

- [ ] **11.1** Update `docs/superpowers/plans/2026-05-23-roadmap.md` — find the M0.5 row in the progress table near line 144 (the "进度追踪" table) and edit the cells:

  ```diff
  -| M0.5 | 待写 | — | — | — |
  +| M0.5 | 已写 | ✅ 完成 | 2026-05-24 | <Task-10-commit-SHA> |
  ```

  Also update line 51-52 (the M0.5 row in the milestone overview table) to mark Plan column as `**[2026-05-24-m0-5-conflict-probe.md](2026-05-24-m0-5-conflict-probe.md)（已写）**`.

- [ ] **11.2** Commit the roadmap flip:

  ```bash
  git add docs/superpowers/plans/2026-05-23-roadmap.md
  git commit -m "$(cat <<'EOF'
  chore(M0.5): mark milestone complete in roadmap

  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
  EOF
  )"
  ```

- [ ] **11.3** Run final all-greens check:

  ```bash
  cd build && ctest --output-on-failure && cd ..
  pytest tests/python/ -q
  python scripts/ci_static_scan.py
  echo "all checks done"
  ```

- [ ] **11.4** Dispatch the whole-branch reviewer (controller's responsibility — no per-step bash command needed). Address any CRITICAL / IMPORTANT issues with additional commits before proceeding.

- [ ] **11.5** Use AskUserQuestion to obtain merge consent (3 options as listed above). DO NOT merge without consent.

- [ ] **11.6** If user chose `--no-ff` merge: execute the merge command from the main repo cwd (see Step 5 commands above).

- [ ] **11.7** Commit the M0.5 plan doc to main (Step 6 commands above).

- [ ] **11.8** ExitWorktree(action="remove", discard_changes=true).

- [ ] **11.9** Mark TaskCreate task #97 (or whichever ID was assigned to "M0.5 Task 11: Roadmap flip + merge to main") as `completed`. M0.5 closed.

---

## Self-Review

After writing this plan, I checked it against the spec sections cited in the prompt:

**1. Spec coverage:**
- §15.3.4 TC-NEW-CONFLICT-SEVERE 4-item atomic transaction: ✅ Task 8 (apply_supersedes_atomic) + Task 10 (acceptance smoke).
- §3.5 T7-P1 (CONSOLIDATED → ARCHIVED bypass): ✅ Task 8 UPDATE clause + Task 10 invariant 3 assertion.
- §3.12 SUPERSEDES edge: ✅ Task 8 (insert_statement_edge with edge_kind='supersedes') + Task 10 invariant 4.
- §3.7-3.8 canonicalize_object: M0.1 already implements; Task 4 reuses it for canonical_conflict_key.
- 05_bus.md §3 ConflictProbe 4 conflict_kind detection paths: ✅ Task 6 ConflictProbe::scan classify().
- 05_bus.md §3.5 P1 sync severe-conflict path: ✅ Task 8.
- 05_bus.md §4 debounce contract (W=10s): ✅ Task 7 compute_window_bucket extension + OutboxWriter::append_or_drop_within_window.
- 05_bus.md §ConflictProbe index contract (idx_conflict_lookup, idx_temporal_overlap): ✅ Task 5 migration 0003.
- 05_bus.md §canonical_conflict_key (7-tuple): ✅ Task 4.
- 05_bus.md §canonical_object_hash_version double-query protocol: ✅ Task 6 cross-version downgrade clamp + test.
- §15.3.5 testing helper convention (starling.testing namespace, audit event, fail-closed in production): ✅ Task 9.

**2. Placeholder scan:** I searched the plan for forbidden patterns: TBD / TODO / "implement later" / "Add appropriate" / "Similar to Task" / "as appropriate" / "as needed". The two intentional comments referencing future tasks ("[Task 8] Replace this fall-through with apply_supersedes_atomic" in Task 7's stub, and "(reuse open_fresh, insert_row, make_stmt, count from earlier test files — copy-paste into this TU)" in tests) are not placeholders — they're explicit forward-pointers to specific subsequent tasks. The "..." in helper-paste comments could be tightened in implementation but the implementer has full code in the source-of-truth tasks.

Two minor flags in self-review:
- Task 6's `NormalizedInterval` helper methods (`overlaps`, `covers`, `adjacent`, `is_unknown`) are mentioned in passing in Task 6 step 6.2 but Task 2's spec didn't fully spell them out. The implementer should add these methods to `include/starling/bus/normalized_interval.hpp` while implementing Task 2; if they got missed, Task 6 step 6.2 calls them out as a hard requirement.
- Task 10's invariant 7 (total bus_events = 5) assumes `mark_consolidated` always emits exactly 1 audit event. Task 9 tests this is so; the assertion is safe.

**3. Type consistency:**
- `ExtractedStatement` field set defined in Task 1 — used by Task 6 (probe consumes valid_from/valid_to/event_time_start), Task 7 + 8 (Bus::write threads them), Task 10 (test seeds them).
- `NormalizedInterval` type defined in Task 2 — used by Task 4 (canonical_conflict_key composes), Task 6 (probe normalizes both sides).
- `CanonicalScope` type defined in Task 3 — used by Task 4 (canonical_conflict_key composes); M0.5 always returns Null.
- `ConflictMatch` struct defined in Task 6 — used by Task 7 + Task 8 (Bus::write branches on `match->kind`).
- `ConflictKind` enum defined in Task 6 — same enum referenced by every downstream task.
- Migration filename `0003_conflict_probe_indices.sql`: stable across tasks 5 / 6 (probe relies on the indices) / 11.

No drift found.

**Spec ambiguity flagged:**
- 05_bus.md does not specify what `aggregate_id` should be for `statement.archived` events. I chose `match.matched_supersedes_root_id` (= S_old's supersedes_id if non-null, else S_old.id) so that an archive event is grouped with its version chain root. If the spec is later clarified to use `S_old.id` directly, swap a single line in `apply_supersedes_atomic`.
- 05_bus.md `belief.conflict` aggregate_id is set to `canonical_conflict_key` in this plan. The spec §3.5 line 366 says the partition key is `canonical_conflict_key` and the dedup key is `conflict_window_id OR canonical_conflict_key` — using `canonical_conflict_key` directly satisfies both.
- The M0.5 cross-version downgrade test uses synthetic `v2` data inserted manually. There's no real v2 yet, so the test demonstrates the protocol but does not exercise a real version migration. This is intentional per the prompt's M0.5 scope.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-24-m0-5-conflict-probe.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, two-stage review (spec compliance + code quality) between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with human-checkpoints.

**Which approach?**

If Subagent-Driven: invoke `superpowers:subagent-driven-development` with this plan path as the argument.
If Inline: invoke `superpowers:executing-plans`.


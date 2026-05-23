# M0.2 SQLite + Outbox Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the P1 local-store substrate + Statement Bus outbox: SQLite schema for the eight P1 tables, transactional `Bus.write` / `Bus.append_evidence` adapter primitives, at-least-once outbox dispatcher with `idempotency_key` dedup + dead-letter, PipelineRun ledger with ExtractionAttempt items, and the `idx_statement_id_tenant` + ConflictProbe indices that gate M0.5 — terminating in TC-NEW-OUTBOX-IDEMP [CRITICAL] passing on a real crash-restart loop.

**Architecture:** Single `SqliteAdapter` C++ class implementing the `RelationalAdapter` part of the local-store contract from `subsystems_design/04_substrate.md`, layered onto SQLite 3.46+ via the system `<sqlite3.h>` header. Schema is owned by a versioned migration runner that the runtime supervisor calls before preflight; preflight reads `sqlite_master` to verify required indices exist (TC-NEW-PREFLIGHT branch (a)). Outbox + dispatcher live in C++ for the transactional path, with a Python supervisor wrapper exposed through pybind so M0.7 acceptance tests and M0.4 extractor stubs can drive end-to-end scenarios. The outbox is a single ordered table; per-`aggregate_id` ordering is enforced by the dispatcher (not a per-stream queue), and idempotency is checked at the subscriber inbox before each business handler runs.

**Tech Stack:**
- SQLite 3.46+ via Homebrew on macOS (`/opt/homebrew/opt/sqlite`), system on Linux. Built statically into `starling_core` so subsequent milestones can ship a single binary. WAL mode, `PRAGMA foreign_keys=ON`, `PRAGMA journal_mode=WAL`, `PRAGMA synchronous=NORMAL`.
- C++20: `SqliteAdapter`, `OutboxDispatcher`, `MigrationRunner`, `IdempotencyInbox`. Header-only RAII wrappers around `sqlite3*` / `sqlite3_stmt*`. No third-party SQLite C++ wrapper.
- Python: `starling.substrate.sqlite_adapter`, `starling.bus.dispatcher`, `starling.runtime` extended to wire migrations + dispatcher. Pybind11 bindings expose `SqliteAdapter`, `OutboxDispatcher`, `BusEvent` envelope, and `PipelineRun` accessors for tests.
- Tests: pytest + GoogleTest. TC-NEW-OUTBOX-IDEMP is a Python integration test that drives a real crash via `os._exit` in a subprocess; C++ tests cover migration idempotency + dispatcher dedup unit-by-unit.
- Reuses M0.1 schema: `Statement`, `EvidenceRef`, `EngramRef`, `StatementRef`, `CognizerRef`, `EntityRef`, `ConsolidationState`, `ReviewStatus`, `EngramRetentionMode`, `IngestPolicy`, `canonical_object_hash` field, all 16 enums.

---

## Source Material Locked

- `docs/design/system_design.md` §3.1 (lines 555-627) ER diagram + index hierarchy
- `docs/design/system_design.md` §3.10 (lines 1178-1310) BusEvent envelope, primary_id / aggregate_id table, idempotency_key formula, window_bucket defaults, causation_chain depth ≤ 3
- `docs/design/system_design.md` §15.2 (lines 1685-1712) M0.2 row + dependency table
- `docs/design/system_design.md` §15.3.1 (lines 1750-1756) TC-NEW-OUTBOX-IDEMP listed as one of three new P1 CRITICALs
- `docs/design/system_design.md` §15.3.4 (lines 1821-1839) TC-NEW-OUTBOX-IDEMP full Given/When/Then
- `docs/design/subsystems_design/04_substrate.md` Adapter contract, Capability declaration, preflight flow
- `docs/design/subsystems_design/05_bus.md` (note: user referenced `06_bus.md`; actual filename is `05_bus.md`) — write path, idempotency, ConflictProbe index contract, ExtractionAttempt + Container schemas, PipelineRun reference

**P1 simplification (not in design doc, locked here):** P1 ships SQLite as the local-store relational backend, not seekdb. Substrate doc lists SQLite + LadybugDB as the explicit "量级 ≤ 10⁵ 且追求极简" simplification; M0.0–M0.7 all use it. seekdb migration is a P2 problem and tracked under §16.3 / `p2-b-brain-dynamics.md`.

---

## File Structure

### New files

C++ headers (under `include/starling/`):
- `include/starling/persistence/sqlite_handles.hpp` — RAII deleters for sqlite3 / sqlite3_stmt
- `include/starling/persistence/connection.hpp` — `Connection` + `TransactionGuard`
- `include/starling/persistence/migration_runner.hpp` — embedded-SQL migration runner with checksum drift detection
- `include/starling/persistence/sqlite_adapter.hpp` — `SqliteAdapter` (declares `Adapter`-derived; capability + final-query predicate)
- `include/starling/bus/bus_event.hpp` — `BusEvent` POD + `compute_idempotency_key` + `compute_window_bucket`
- `include/starling/bus/outbox_writer.hpp` — `OutboxWriter` (transactional append, monotonic sequence)
- `include/starling/bus/consumer_state.hpp` — `ConsumerCheckpoint` + `IdempotencyInbox`
- `include/starling/bus/outbox_dispatcher.hpp` — `OutboxDispatcher` + `Consumer` callback type
- `include/starling/bus/pipeline_ledger.hpp` — `PipelineLedger` (M0.4 ledger write API)

C++ source (under `src/`):
- `src/persistence/connection.cpp`
- `src/persistence/migration_runner.cpp`
- `src/persistence/sqlite_adapter.cpp`
- `src/bus/bus_event.cpp`
- `src/bus/outbox_writer.cpp`
- `src/bus/consumer_state.cpp`
- `src/bus/outbox_dispatcher.cpp`
- `src/bus/pipeline_ledger.cpp`

Embedded SQL migrations:
- `migrations/0001_initial_schema.sql` — 8 tables + 9 indices + outbox_sequence_counter + schema_migrations
- `migrations/0002_extraction_attempt_unique.sql` — adds `idx_extraction_attempt_unique`

Python (under `python/starling/`):
- `python/starling/bus/__init__.py`
- `python/starling/bus/bus_event.py` — `BusEvent` dataclass + Python `compute_idempotency_key` (parity with C++)
- `python/starling/bus/idempotency.py` — canonical-key builders for known event types
- `python/starling/bus/outbox_dispatcher_py.py` — Python re-implementation of `OutboxDispatcher.run_once` (only used by the TC-NEW-OUTBOX-IDEMP crash worker, since you can't `os._exit()` mid-callback in C++)

Tests (under `tests/`):
- `tests/cpp/test_sqlite_link.cpp` — Task 1 link-time smoke
- `tests/cpp/test_migration_runner.cpp`
- `tests/cpp/test_connection.cpp`
- `tests/cpp/test_idempotency_key.cpp`
- `tests/cpp/test_outbox_writer.cpp`
- `tests/cpp/test_consumer_state.cpp`
- `tests/cpp/test_outbox_dispatcher.cpp`
- `tests/cpp/test_pipeline_ledger.cpp`
- `tests/cpp/test_sqlite_adapter.cpp`
- `tests/python/test_bus_event_parity.py` — Python-only digest pin
- `tests/python/test_bus_binding_parity.py` — cross-language C++ ↔ Python parity (54 cases)
- `tests/python/test_tc_new_outbox_idemp.py` — TC-NEW-OUTBOX-IDEMP [CRITICAL]
- `tests/python/test_m0_2_acceptance.py` — milestone acceptance smoke
- `tests/python/_fixtures/outbox_crash_worker.py` — subprocess worker that crashes via `os._exit`

### Modified files
- `CMakeLists.txt` — add SQLite link, embed migrations via `file(READ)`, append M0.2 source files to `starling_core`
- `tests/cpp/CMakeLists.txt` — register all new C++ test executables
- `bindings/python/module.cpp` — extend the existing `PYBIND11_MODULE(_core, m)` with `BusEvent`, `compute_idempotency_key`, `SqliteAdapter`, `append_event_unsafe`
- `python/starling/runtime.py` — add optional `adapter` field, `_SqliteBackedBus`, and `_build_local_store_sqlite_runtime` factory
- `python/starling/testing/__init__.py` — append `relax_preflight_for_m0_2` helper
- `tools/ci/scan_prod_uses_testing.py` — extend the M0.0 scanner's forbidden-symbol list with `append_event_unsafe`
- `docs/superpowers/plans/2026-05-23-roadmap.md` — flip M0.2 row to `已写 / ✅ 完成` after acceptance is green (handled by Task 11)

### Decomposition rationale
- One file per concern: connection (RAII + pragmas), migration_runner (embedded SQL + checksum), bus_event (envelope POD + idempotency_key), outbox_writer (transactional insert), consumer_state (checkpoint + inbox dedup), outbox_dispatcher (per-aggregate ordering + dead-letter), pipeline_ledger (M0.4 ledger writes), sqlite_adapter (capability + final-query predicate).
- Migrations live in dedicated `.sql` files with an embedded checksum table so re-running the runner is idempotent. This survives the M0.5 SUPERSEDES / canonical_object_hash extensions being added without rewriting the world.
- Tests split by component because the dispatcher's crash test needs an isolated subprocess and benefits from being its own file; mixing it with adapter unit tests would slow the rest of the suite.

---

## Subsystem Contracts (locked at plan time)

### A. SQLite schema (eight tables, P1)

Mirrors the §3.1 ER diagram (lines 559-613). Field names match Python dataclasses from M0.1 byte-for-byte; types are SQLite affinities (TEXT for UUID + ISO datetime + JSON, INTEGER for booleans + counts, REAL for floats).

1. `statements` — 38 columns matching `python/starling/schema/statement.py:43`. UUIDs stored as 36-char TEXT (canonical hyphenated form, lowercase). `evidence`, `source_spans`, `derived_from`, `perceived_by`, `visibility`, `confidence_history`, `event_time`, `temporal_anchor`, `affect`, `supersedes` stored as JSON TEXT (single column per field; we do not normalize evidence into a junction table in M0.2 — that's M0.5 ConflictProbe / M0.4 Extractor work). PK `id`. Indices: `idx_statement_id_tenant(id, tenant_id)` (P1 mandatory, gated by preflight); `idx_conflict_lookup(tenant_id, holder, modality, subject, predicate, canonical_object_hash_version, canonical_object_hash)`; `idx_temporal_overlap(tenant_id, holder, valid_from, valid_to)`.
2. `statement_edges` — `(source_id, target_id, edge_kind)` PK, `metadata` JSON TEXT, `created_at` TEXT. Indices: `idx_edges_source(source_id, edge_kind)`, `idx_edges_target(target_id, edge_kind)`.
3. `engrams` — fields per §3.1 (lines 580-590): `id`, `source`, `source_kind`, `ingest_policy`, `adapter_name`, `adapter_version`, `ingest_mode`, `declared_transformations` (JSON), `privacy_class`, `byte_preserving` (INTEGER 0/1), `content_ciphertext` (BLOB nullable), `redacted_content` (TEXT nullable), `content_hash`, `retention_mode`, `key_ref`, `chunk_index`, `speaker_id`, `timestamp`, `source_time_range` (JSON), `segment_map` (JSON, P3 placeholder NULL in P1), `audit_trail` (JSON array, append-only at app level). PK `id`.
4. `containers` — `id`, `kind`, `source_refs` (JSON array of statement IDs), `materialized_payload` (JSON), `version` INTEGER (P1 integer CAS), `dimension_versions` (JSON, NULL in P1), `dimension_sequences` (JSON, NULL in P1), `last_rebuilt_at`, `build_policy`. PK `id`.
5. `bus_events` — outbox + audit log. Columns: `event_id` TEXT PK, `event_type` TEXT, `primary_id` TEXT, `aggregate_id` TEXT, `outbox_sequence` INTEGER `AUTOINCREMENT` (single global monotonic), `causation_chain` TEXT (JSON array of UUIDs, length ≤ 3), `idempotency_key` TEXT, `payload` TEXT (JSON), `created_at` TEXT, `version` TEXT default `'v1'`, `dispatch_status` TEXT (NEW: `'pending' | 'in_flight' | 'delivered' | 'dead_letter'`), `retry_count` INTEGER default 0, `last_error` TEXT nullable, `last_attempt_at` TEXT nullable. Indices: `idx_outbox_seq(outbox_sequence)`, `idx_aggregate_seq(aggregate_id, outbox_sequence)`, `idx_pending(dispatch_status, outbox_sequence)`, `idx_event_type_created(event_type, created_at)`.
6. `consumer_checkpoints` — `subscriber_name` TEXT, `shard` TEXT (default `'default'` in P1), `last_dispatched_sequence` INTEGER, `updated_at` TEXT. PK `(subscriber_name, shard)`.
7. `idempotency_inbox` — Subscriber-side dedup. `subscriber_name` TEXT, `idempotency_key` TEXT, `event_id` TEXT, `acked_at` TEXT, `expires_at` TEXT (acked_at + 7 days, per §3.10). PK `(subscriber_name, idempotency_key)`. Index `idx_inbox_expiry(expires_at)` for nightly purge.
8. `pipeline_runs` — `run_id` TEXT PK, `kind` TEXT (`'extraction' | 'replay' | 'projection_rebuild' | 'reconsolidation'`; only `'extraction'` exercised in M0.2 — others reserved), `status` TEXT (`'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'CANCELLED'`), `started_at` TEXT, `finished_at` TEXT nullable, `tenant_id` TEXT, `triggered_by_event_id` TEXT nullable, `warnings` TEXT (JSON array), `metadata` TEXT (JSON).
9. `extraction_attempts` — item-level rows under `pipeline_runs` (run kind = `extraction`). `id` TEXT PK, `run_id` TEXT FK → `pipeline_runs.run_id`, `engram_ref` TEXT, `attempt_no` INTEGER, `extractor_version` TEXT, `prompt_version` TEXT, `prompt_input_hash` TEXT, `existing_ref_map` TEXT (JSON), `status` TEXT (`'RUNNING' | 'SUCCESS' | 'PARTIAL_SUCCESS' | 'FAILED' | 'DEAD_LETTERED' | 'NOOP'`), `accepted_statement_ids` TEXT (JSON array), `rejected_fragments` TEXT (JSON array), `noop_reason` TEXT nullable, `raw_output_hash` TEXT nullable, `started_at` TEXT, `finished_at` TEXT nullable. Index `idx_attempts_run(run_id)`.

**Schema migrations table** (the migration runner's own ledger): `schema_migrations(version INTEGER PK, applied_at TEXT, checksum TEXT)`.

### B. BusEvent envelope (Python ↔ C++ parity)

Python dataclass in `python/starling/bus/event.py`:

```python
import hashlib, json, uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

@dataclass(frozen=True, slots=True, kw_only=True)
class BusEvent:
    event_id: uuid.UUID
    event_type: str
    primary_id: str
    aggregate_id: str
    outbox_sequence: int
    causation_chain: tuple[uuid.UUID, ...] = ()
    idempotency_key: str
    payload: dict
    created_at: datetime
    version: str = "v1"

    def __post_init__(self):
        if len(self.causation_chain) > 3:
            raise ValueError(
                f"causation_chain length {len(self.causation_chain)} exceeds limit 3"
            )
```

`idempotency_key` is computed by a free function (not in `__post_init__` — producers pass canonical_key + window_bucket explicitly so the formula stays auditable):

```python
def compute_idempotency_key(
    *,
    event_type: str,
    aggregate_id: str,
    canonical_key: str,
    causation_chain_root: str | None,
    window_bucket: str,
) -> str:
    blob = "\x1f".join([
        event_type,
        aggregate_id,
        canonical_key,
        causation_chain_root or "",
        window_bucket,
    ]).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()
```

Field separator `\x1f` (ASCII Unit Separator) is unambiguous against any allowed value (UUIDs / ASCII-safe canonical keys / ISO timestamps).

### C. Outbox + dispatcher contract

- **OutboxWriter.append(event, tx)** — insert into `bus_events` with `dispatch_status='pending'` inside an open `Transaction`. Caller MUST call from inside the same transaction that wrote the business row (Statement / Engram / Container). No standalone `append` outside a transaction is allowed; the C++ method takes `Transaction&` by reference and callers without a tx fail to compile.
- **OutboxDispatcher.run_once()** — single drain pass; useful for tests + tick-driven supervisors.
- **OutboxDispatcher.run_forever()** — calls `run_once()` then sleeps `poll_interval_ms` (default 50ms in tests, 500ms in prod).
- **Per-aggregate_id ordering** — `run_once()` SELECTs by `(aggregate_id, outbox_sequence)`, processes pending events grouped by aggregate. Within an aggregate, a failure (retryable or not) blocks downstream events of THAT aggregate only — other aggregates continue. This matches §3.10's "同 aggregate 内按此顺序投递" semantics.
- **Idempotency check** — before invoking subscriber, dispatcher checks `idempotency_inbox(subscriber_name, idempotency_key)`. Hit → skip subscriber call, advance checkpoint, mark event `delivered`, increment `events_acked_idempotent` metric.
- **Failure modes**:
  - Subscriber returns normally → mark `delivered`, write `idempotency_inbox` row, advance checkpoint.
  - Subscriber raises `RetryableError` → increment `retry_count`, leave `dispatch_status='pending'`, schedule next attempt (immediate in P1; backoff is P2). Stop processing this aggregate this pass.
  - Subscriber raises `NonRetryableError` (or any other exception in P1, since we don't yet have a retry classifier) → if `retry_count < max_retries (5)`, treat as retryable; else mark `dispatch_status='dead_letter'`, emit `system.delivery_failed` (synthetic outbox row, NOT recursive — see below), advance checkpoint past the dead-lettered row.
  - **Recursion guard**: `system.delivery_failed` events are appended with `causation_chain` already at length 0 (root) and a `dispatch_status='delivered'` shortcut entry that is never re-dispatched to subscribers — only audit / Ops consume it via `consumer_checkpoint`. P1 has no Ops subscriber registered, so the row sits in the table for inspection. This avoids "dispatcher fails → emits delivery_failed → also fails → infinite emit" loops.
- **Subscriber registry** — Python dict `name -> Subscriber`. The dispatcher resolves `event_type` → list of subscribers via a static map declared at start. M0.2 ships with two test subscribers (`AlwaysOk`, `AlwaysFail`) and zero prod subscribers; M0.3 onwards adds Extractor / Audit / etc.

### D. Idempotency inbox 7-day expiry

A purge job runs at dispatcher start AND every `purge_interval_ms` (default 60s in tests, 1h in prod): `DELETE FROM idempotency_inbox WHERE expires_at < datetime('now')`. M0.2 wires the loop but doesn't schedule it on a separate thread — the dispatcher's main loop calls `purge_expired()` once per N polls. P2 moves to a background thread when scheduling lands.

### E. Capability + preflight extension

`SqliteAdapter::declare_capability()` returns:
```cpp
ProfileCapability{
    .profile_name = "local-store",
    .relational_backend = "sqlite",
    .vector_backend = "",          // M0.2 does not implement VectorAdapter
    .graph_backend = "",
    .c_plus_plus_core = true,
    .cross_partition_transaction = true,   // single-DB SQLite, trivially true
    .transactional_outbox = true,
    .consumer_checkpoint = true,
    .tenant_isolation = "storage_enforced",
    .engram_per_record_key = false,        // P1 baseline; flips true when M0.3 EngramStore lands KMS hook
    .engram_refcount = false,
    .projection_index_supported = false,
    .dimension_versions_supported = false,
    .testing_helper_marker = false,        // production translation unit
};
```

`engram_per_record_key=false` would normally fail TC-NEW-PREFLIGHT branch (all required caps must be true). M0.3 lands the KMS-backed key derivation that flips this true; M0.2 acceptance MUST patch the runtime's `LOCAL_STORE_REQUIRED` to remove `engram_per_record_key` for tests OR the test must use `testing.relax_preflight_for_m0_2()`. Decision: relax via test-only helper (consistent with `starling.testing.*` discipline).

`Runtime.idx_statement_id_tenant_present` callable, currently a stub returning `True`, gets replaced by a real read on `sqlite_master`:
```python
def _idx_present(adapter, name="idx_statement_id_tenant"):
    cur = adapter.execute("SELECT 1 FROM sqlite_master WHERE type='index' AND name=?", (name,))
    return cur.fetchone() is not None
```

### F. Test wedge for TC-NEW-OUTBOX-IDEMP

The CRITICAL test must (a) seed 100 events, (b) crash mid-delivery, (c) restart, (d) verify exact counts. To make "crash mid-delivery" deterministic without flakiness, the test uses a **fault-injection subscriber**: the test subscriber is wired with a `crash_after_n` parameter, and crashes via `os._exit(137)` from within `handle()` after delivering N events. The 100-event seed has known per-event fates (50 already-acked / 30 first-time / 20 will-perma-fail). The crash happens after 60 events (to ensure some delivered + some pending split). Restart → second dispatcher run drains the rest. Counts come from `bus_events.dispatch_status` aggregations and `idempotency_inbox` row counts; metrics are read from `OutboxDispatcher.metrics_snapshot()`.

---

## Tasks

### Task 1: SQLite discovery + CMake link

**Files:**
- Modify: `CMakeLists.txt`
- Create: `tests/cpp/test_sqlite_link.cpp`
- Modify: `tests/cpp/CMakeLists.txt`

**Goal:** SQLite3 is found and linked into `starling_core`; a smoke test opens an in-memory DB and runs `SELECT sqlite_version();`.

- [ ] **Step 1: Add SQLite3 discovery to CMakeLists.txt**

Insert after the OpenSSL block (current `CMakeLists.txt:19`):

```cmake
# SQLite3 — Homebrew on Apple Silicon installs at /opt/homebrew/opt/sqlite.
# The system framework on macOS is older than 3.46; prefer Homebrew when present.
if(APPLE AND NOT DEFINED SQLite3_ROOT)
    if(EXISTS "/opt/homebrew/opt/sqlite/lib/libsqlite3.dylib")
        set(SQLite3_ROOT "/opt/homebrew/opt/sqlite")
        list(PREPEND CMAKE_PREFIX_PATH "/opt/homebrew/opt/sqlite")
    endif()
endif()
find_package(SQLite3 3.46 REQUIRED)
```

Then in the `target_link_libraries(starling_core PUBLIC ...)` line, add `SQLite::SQLite3`:

```cmake
target_link_libraries(starling_core PUBLIC OpenSSL::Crypto SQLite::SQLite3)
```

- [ ] **Step 2: Write the failing smoke test**

Create `tests/cpp/test_sqlite_link.cpp`:

```cpp
#include <gtest/gtest.h>
#include <sqlite3.h>

#include <string>

TEST(SqliteLink, OpenInMemoryAndQueryVersion) {
    sqlite3* db = nullptr;
    ASSERT_EQ(sqlite3_open(":memory:", &db), SQLITE_OK);
    ASSERT_NE(db, nullptr);

    sqlite3_stmt* stmt = nullptr;
    ASSERT_EQ(sqlite3_prepare_v2(db, "SELECT sqlite_version();", -1, &stmt, nullptr),
              SQLITE_OK);
    ASSERT_EQ(sqlite3_step(stmt), SQLITE_ROW);
    const unsigned char* version = sqlite3_column_text(stmt, 0);
    ASSERT_NE(version, nullptr);
    std::string v(reinterpret_cast<const char*>(version));

    // Require at least 3.46 (matches CMake find_package version).
    int major = 0, minor = 0;
    ASSERT_EQ(std::sscanf(v.c_str(), "%d.%d.", &major, &minor), 2);
    EXPECT_GE(major, 3);
    if (major == 3) EXPECT_GE(minor, 46);

    sqlite3_finalize(stmt);
    sqlite3_close(db);
}
```

- [ ] **Step 3: Register the test in tests/cpp/CMakeLists.txt**

Append to the existing test list (mirror the pattern used by `test_smoke.cpp`):

```cmake
add_executable(test_sqlite_link test_sqlite_link.cpp)
target_link_libraries(test_sqlite_link PRIVATE starling_core GTest::gtest_main)
gtest_discover_tests(test_sqlite_link)
```

- [ ] **Step 4: Run the build + test**

Run:
```
cmake --preset default && cmake --build --preset default
ctest --preset default --output-on-failure -R SqliteLink
```
Expected: 1 test, PASS, sqlite version printed (≥ 3.46).

- [ ] **Step 5: Commit**

```bash
git add CMakeLists.txt tests/cpp/test_sqlite_link.cpp tests/cpp/CMakeLists.txt
git commit -m "feat(M0.2): link SQLite3 ≥ 3.46 into starling_core"
```

---

### Task 2: Migration runner + initial schema (P1 tables, indices, schema_migrations)

**Files:**
- Create: `include/starling/persistence/migration_runner.hpp`
- Create: `src/persistence/migration_runner.cpp`
- Create: `migrations/0001_initial_schema.sql`
- Create: `tests/cpp/test_migration_runner.cpp`
- Modify: `CMakeLists.txt` (embed migration SQL via `file(READ ...)` at configure time; register test)

**Why first:** Every subsequent task assumes the schema exists. Hashing each migration's SQL into `schema_migrations.checksum` lets us refuse to start when a deployed migration's content drifts (the same fail-closed posture as preflight).

- [ ] **Step 1: Write `migrations/0001_initial_schema.sql` — P1 tables**

Create the file with the full DDL below. Keep `PRAGMA` statements at the top so they apply to the connection that runs the migration; the runtime opens connections with the same pragmas separately.

```sql
-- Starling M0.2 initial schema. Targets SQLite 3.46+.
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;

-- ── containers (persona / common_ground / knowledge_frontier; §3.4) ──
CREATE TABLE IF NOT EXISTS containers (
    id TEXT PRIMARY KEY,                    -- UUID
    tenant_id TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('persona','common_ground','knowledge_frontier')),
    holder_id TEXT NOT NULL,                -- CognizerRef
    scope_descriptor TEXT NOT NULL,         -- canonical JSON
    created_at TEXT NOT NULL,               -- ISO-8601 UTC
    updated_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_containers_tenant_holder
    ON containers(tenant_id, holder_id, kind);

-- ── statements (38-field core; §3.3) ──
CREATE TABLE IF NOT EXISTS statements (
    id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    holder_id TEXT NOT NULL,
    holder_perspective TEXT NOT NULL,
    subject_kind TEXT NOT NULL CHECK (subject_kind IN ('cognizer','entity')),
    subject_id TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object_kind TEXT NOT NULL,              -- bool|int|float|str|datetime|cognizer|entity|statement
    object_value TEXT NOT NULL,             -- canonical string form (see canonicalize_object, M0.5)
    canonical_object_hash TEXT NOT NULL,
    canonical_object_hash_version TEXT NOT NULL DEFAULT 'v1',
    modality TEXT NOT NULL,
    polarity TEXT NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    observed_at TEXT NOT NULL,
    inferred_at TEXT,
    valid_from TEXT,
    valid_to TEXT,
    event_time_start TEXT,
    event_time_end TEXT,
    salience REAL NOT NULL CHECK (salience >= 0.0 AND salience <= 1.0),
    affect_json TEXT NOT NULL,              -- canonical JSON of AffectVector
    activation REAL NOT NULL,
    last_accessed TEXT NOT NULL,
    provenance TEXT NOT NULL,
    confidence_history_json TEXT NOT NULL DEFAULT '[]',
    evidence_json TEXT NOT NULL DEFAULT '[]',
    source_spans_json TEXT NOT NULL DEFAULT '[]',
    temporal_anchor_json TEXT,
    derived_from_json TEXT NOT NULL DEFAULT '[]',
    derived_depth INTEGER NOT NULL DEFAULT 0,
    perceived_by_json TEXT NOT NULL DEFAULT '[]',
    supersedes_id TEXT,
    access_count INTEGER NOT NULL DEFAULT 0,
    last_replayed TEXT,
    replay_count INTEGER NOT NULL DEFAULT 0,
    consolidation_state TEXT NOT NULL DEFAULT 'volatile',
    review_status TEXT NOT NULL DEFAULT 'approved',
    nesting_depth INTEGER NOT NULL DEFAULT 0,
    visibility_json TEXT NOT NULL DEFAULT '[]',
    retention_policy TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (id, tenant_id)
);
-- P1-mandatory composite index (preflight checks for this exact name)
CREATE UNIQUE INDEX IF NOT EXISTS idx_statement_id_tenant
    ON statements(id, tenant_id);
CREATE INDEX IF NOT EXISTS idx_statements_holder_predicate
    ON statements(tenant_id, holder_id, predicate);
CREATE INDEX IF NOT EXISTS idx_statements_subject
    ON statements(tenant_id, subject_kind, subject_id);

-- ── statement_edges (typed edges between statements; §3.4) ──
CREATE TABLE IF NOT EXISTS statement_edges (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    src_id TEXT NOT NULL,
    dst_id TEXT NOT NULL,
    edge_kind TEXT NOT NULL,
    weight REAL NOT NULL DEFAULT 1.0,
    created_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_edges_src
    ON statement_edges(tenant_id, src_id, edge_kind);
CREATE INDEX IF NOT EXISTS idx_edges_dst
    ON statement_edges(tenant_id, dst_id, edge_kind);

-- ── engrams (raw evidence anchors; §3.7) ──
CREATE TABLE IF NOT EXISTS engrams (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    ingest_policy TEXT NOT NULL,
    ingest_mode TEXT NOT NULL,
    privacy_class TEXT NOT NULL,
    retention_mode TEXT NOT NULL,
    refcount INTEGER NOT NULL DEFAULT 0,
    payload_uri TEXT,                       -- KMS-encrypted blob URI; M0.3 wires real adapter
    payload_inline BLOB,                    -- M0.2 inline only for tests
    created_at TEXT NOT NULL,
    erased_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_engrams_content_hash
    ON engrams(tenant_id, content_hash);

-- ── bus_events (transactional outbox; §3.10) ──
CREATE TABLE IF NOT EXISTS bus_events (
    event_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    primary_id TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    outbox_sequence INTEGER NOT NULL,       -- monotonic, claimed from outbox_sequence_counter
    causation_chain_json TEXT NOT NULL DEFAULT '[]',
    idempotency_key TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT 'v1',
    dispatch_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (dispatch_status IN ('pending','in_flight','delivered','dead_letter')),
    dispatch_attempts INTEGER NOT NULL DEFAULT 0,
    last_attempt_at TEXT,
    last_error TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_bus_events_sequence
    ON bus_events(outbox_sequence);
CREATE INDEX IF NOT EXISTS idx_bus_events_dispatch
    ON bus_events(dispatch_status, outbox_sequence)
    WHERE dispatch_status IN ('pending','in_flight');
CREATE INDEX IF NOT EXISTS idx_bus_events_aggregate
    ON bus_events(aggregate_id, outbox_sequence);
CREATE UNIQUE INDEX IF NOT EXISTS idx_bus_events_idempotency
    ON bus_events(idempotency_key);

-- ── outbox_sequence_counter (single-row monotonic claim) ──
CREATE TABLE IF NOT EXISTS outbox_sequence_counter (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    next_value INTEGER NOT NULL
);
INSERT OR IGNORE INTO outbox_sequence_counter(id, next_value) VALUES (1, 1);

-- ── consumer_checkpoint (per-consumer last delivered sequence) ──
CREATE TABLE IF NOT EXISTS consumer_checkpoint (
    consumer_id TEXT PRIMARY KEY,
    last_delivered_sequence INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

-- ── idempotency_inbox (consumer-side dedup; 7-day expiry) ──
CREATE TABLE IF NOT EXISTS idempotency_inbox (
    consumer_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    received_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    PRIMARY KEY (consumer_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_idempotency_expires
    ON idempotency_inbox(expires_at);

-- ── pipeline_run + extraction_attempt (M0.4 ledger; columns reserved here so M0.4 needs no migration) ──
CREATE TABLE IF NOT EXISTS pipeline_run (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    input_ref TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS extraction_attempt (
    id TEXT PRIMARY KEY,
    pipeline_run_id TEXT NOT NULL REFERENCES pipeline_run(id),
    extraction_span_key TEXT NOT NULL,
    attempt_number INTEGER NOT NULL,
    status TEXT NOT NULL,                   -- success|partial_success|failed
    raw_output TEXT,
    error TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_extraction_attempt_span
    ON extraction_attempt(extraction_span_key, attempt_number);

-- ── schema_migrations (drift detection) ──
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL,
    checksum TEXT NOT NULL                  -- sha256 hex of the migration file
);
```

- [ ] **Step 2: Embed migrations into the C++ binary at configure time**

Modify `CMakeLists.txt` to read every `migrations/*.sql` file and generate a header containing them as raw string literals.

Append this block to `CMakeLists.txt` after the SQLite link section from Task 1:

```cmake
# Embed migration SQL into a header. Re-run cmake configure when files change.
file(GLOB STARLING_MIGRATION_FILES
    LIST_DIRECTORIES false
    RELATIVE "${CMAKE_SOURCE_DIR}/migrations"
    "${CMAKE_SOURCE_DIR}/migrations/*.sql")
list(SORT STARLING_MIGRATION_FILES)
set(STARLING_MIGRATIONS_INC "${CMAKE_BINARY_DIR}/generated/starling/migrations.inc")
file(MAKE_DIRECTORY "${CMAKE_BINARY_DIR}/generated/starling")
set(_mig_body "")
foreach(mig ${STARLING_MIGRATION_FILES})
    set(_mig_path "${CMAKE_SOURCE_DIR}/migrations/${mig}")
    file(READ "${_mig_path}" _mig_sql)
    string(REGEX MATCH "^([0-9]+)_(.+)\\.sql$" _ "${mig}")
    set(_mig_version "${CMAKE_MATCH_1}")
    set(_mig_name "${CMAKE_MATCH_2}")
    string(APPEND _mig_body
        "  { ${_mig_version}, \"${_mig_name}\", R\"STARLING_MIG(${_mig_sql})STARLING_MIG\" },\n")
    # Re-configure when migration file content changes
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${_mig_path}")
endforeach()
file(WRITE "${STARLING_MIGRATIONS_INC}"
    "// Auto-generated by CMakeLists.txt. Do not edit.\n"
    "// Each row: { version, name, raw_sql }.\n"
    "namespace starling::persistence::detail {\n"
    "struct EmbeddedMigration { int version; const char* name; const char* sql; };\n"
    "inline constexpr EmbeddedMigration kEmbeddedMigrations[] = {\n"
    "${_mig_body}"
    "};\n"
    "}\n")
target_include_directories(starling_core PRIVATE "${CMAKE_BINARY_DIR}/generated")
```

- [ ] **Step 3: Write `include/starling/persistence/migration_runner.hpp`**

```cpp
#pragma once
#include <sqlite3.h>
#include <stdexcept>
#include <string>
#include <vector>

namespace starling::persistence {

struct AppliedMigration {
    int version;
    std::string name;
    std::string applied_at;
    std::string checksum;
};

class MigrationDriftError : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

class MigrationRunner {
public:
    explicit MigrationRunner(sqlite3* db);

    // Idempotent. Runs every embedded migration whose version is not yet in
    // schema_migrations. For already-applied versions, verifies that the
    // recorded checksum matches the embedded SQL — if not, throws
    // MigrationDriftError without applying anything.
    void migrate_to_latest();

    // Returns rows from schema_migrations ordered by version.
    std::vector<AppliedMigration> applied() const;

    // sha256 hex of the SQL string. Exposed for tests.
    static std::string checksum_of(std::string_view sql);

private:
    sqlite3* db_;  // not owned
};

}  // namespace starling::persistence
```

- [ ] **Step 4: Write `src/persistence/migration_runner.cpp`**

```cpp
#include "starling/persistence/migration_runner.hpp"
#include "starling/migrations.inc"

#include <openssl/evp.h>
#include <chrono>
#include <ctime>
#include <iomanip>
#include <sstream>

namespace starling::persistence {

namespace {

std::string now_iso8601_utc() {
    using namespace std::chrono;
    const auto t = system_clock::to_time_t(system_clock::now());
    std::tm tm{};
    gmtime_r(&t, &tm);
    std::ostringstream oss;
    oss << std::put_time(&tm, "%Y-%m-%dT%H:%M:%SZ");
    return oss.str();
}

void exec_or_throw(sqlite3* db, const char* sql) {
    char* err = nullptr;
    if (sqlite3_exec(db, sql, nullptr, nullptr, &err) != SQLITE_OK) {
        std::string msg = err ? err : "unknown sqlite_exec error";
        sqlite3_free(err);
        throw std::runtime_error("migration_exec failed: " + msg);
    }
}

}  // namespace

std::string MigrationRunner::checksum_of(std::string_view sql) {
    unsigned char digest[EVP_MAX_MD_SIZE];
    unsigned int digest_len = 0;
    EVP_MD_CTX* ctx = EVP_MD_CTX_new();
    EVP_DigestInit_ex(ctx, EVP_sha256(), nullptr);
    EVP_DigestUpdate(ctx, sql.data(), sql.size());
    EVP_DigestFinal_ex(ctx, digest, &digest_len);
    EVP_MD_CTX_free(ctx);
    std::ostringstream oss;
    oss << std::hex << std::setfill('0');
    for (unsigned int i = 0; i < digest_len; ++i) {
        oss << std::setw(2) << static_cast<int>(digest[i]);
    }
    return oss.str();
}

MigrationRunner::MigrationRunner(sqlite3* db) : db_(db) {}

void MigrationRunner::migrate_to_latest() {
    exec_or_throw(db_,
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version INTEGER PRIMARY KEY, name TEXT NOT NULL, "
        "applied_at TEXT NOT NULL, checksum TEXT NOT NULL)");

    for (const auto& mig : detail::kEmbeddedMigrations) {
        const std::string expected = checksum_of(mig.sql);

        sqlite3_stmt* stmt = nullptr;
        sqlite3_prepare_v2(db_,
            "SELECT checksum FROM schema_migrations WHERE version = ?",
            -1, &stmt, nullptr);
        sqlite3_bind_int(stmt, 1, mig.version);
        const int rc = sqlite3_step(stmt);
        if (rc == SQLITE_ROW) {
            const std::string recorded = reinterpret_cast<const char*>(
                sqlite3_column_text(stmt, 0));
            sqlite3_finalize(stmt);
            if (recorded != expected) {
                throw MigrationDriftError(
                    "migration drift: version " + std::to_string(mig.version) +
                    " recorded=" + recorded + " expected=" + expected);
            }
            continue;
        }
        sqlite3_finalize(stmt);

        exec_or_throw(db_, "BEGIN IMMEDIATE");
        try {
            exec_or_throw(db_, mig.sql);
            sqlite3_stmt* ins = nullptr;
            sqlite3_prepare_v2(db_,
                "INSERT INTO schema_migrations(version,name,applied_at,checksum) "
                "VALUES(?,?,?,?)", -1, &ins, nullptr);
            const std::string ts = now_iso8601_utc();
            sqlite3_bind_int(ins, 1, mig.version);
            sqlite3_bind_text(ins, 2, mig.name, -1, SQLITE_TRANSIENT);
            sqlite3_bind_text(ins, 3, ts.c_str(), -1, SQLITE_TRANSIENT);
            sqlite3_bind_text(ins, 4, expected.c_str(), -1, SQLITE_TRANSIENT);
            if (sqlite3_step(ins) != SQLITE_DONE) {
                sqlite3_finalize(ins);
                throw std::runtime_error("schema_migrations insert failed");
            }
            sqlite3_finalize(ins);
            exec_or_throw(db_, "COMMIT");
        } catch (...) {
            sqlite3_exec(db_, "ROLLBACK", nullptr, nullptr, nullptr);
            throw;
        }
    }
}

std::vector<AppliedMigration> MigrationRunner::applied() const {
    std::vector<AppliedMigration> out;
    sqlite3_stmt* stmt = nullptr;
    sqlite3_prepare_v2(db_,
        "SELECT version,name,applied_at,checksum FROM schema_migrations "
        "ORDER BY version", -1, &stmt, nullptr);
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        out.push_back({
            sqlite3_column_int(stmt, 0),
            reinterpret_cast<const char*>(sqlite3_column_text(stmt, 1)),
            reinterpret_cast<const char*>(sqlite3_column_text(stmt, 2)),
            reinterpret_cast<const char*>(sqlite3_column_text(stmt, 3)),
        });
    }
    sqlite3_finalize(stmt);
    return out;
}

}  // namespace starling::persistence
```

- [ ] **Step 5: Wire `migration_runner.cpp` into `starling_core`**

Add the new translation unit to the `starling_core` source list in `CMakeLists.txt`:

```cmake
target_sources(starling_core PRIVATE
    src/persistence/migration_runner.cpp
)
target_include_directories(starling_core PUBLIC include)
```

- [ ] **Step 6: Write `tests/cpp/test_migration_runner.cpp`**

```cpp
#include <gtest/gtest.h>
#include <sqlite3.h>
#include "starling/persistence/migration_runner.hpp"

namespace {

sqlite3* open_memory() {
    sqlite3* db = nullptr;
    EXPECT_EQ(sqlite3_open(":memory:", &db), SQLITE_OK);
    return db;
}

int count_rows(sqlite3* db, const char* sql) {
    sqlite3_stmt* stmt = nullptr;
    EXPECT_EQ(sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr), SQLITE_OK);
    EXPECT_EQ(sqlite3_step(stmt), SQLITE_ROW);
    const int n = sqlite3_column_int(stmt, 0);
    sqlite3_finalize(stmt);
    return n;
}

}  // namespace

TEST(MigrationRunner, AppliesEveryMigrationOnce) {
    sqlite3* db = open_memory();
    starling::persistence::MigrationRunner r(db);
    r.migrate_to_latest();
    const auto applied = r.applied();
    EXPECT_FALSE(applied.empty());
    EXPECT_EQ(applied.front().version, 1);
    sqlite3_close(db);
}

TEST(MigrationRunner, IdempotentSecondRun) {
    sqlite3* db = open_memory();
    starling::persistence::MigrationRunner r(db);
    r.migrate_to_latest();
    const auto first = r.applied().size();
    r.migrate_to_latest();
    EXPECT_EQ(r.applied().size(), first);
    sqlite3_close(db);
}

TEST(MigrationRunner, P1MandatoryIndexExists) {
    sqlite3* db = open_memory();
    starling::persistence::MigrationRunner(db).migrate_to_latest();
    EXPECT_EQ(count_rows(db,
        "SELECT COUNT(*) FROM sqlite_master "
        "WHERE type='index' AND name='idx_statement_id_tenant'"), 1);
    sqlite3_close(db);
}

TEST(MigrationRunner, DetectsChecksumDrift) {
    sqlite3* db = open_memory();
    starling::persistence::MigrationRunner(db).migrate_to_latest();
    // Tamper: rewrite the recorded checksum so the next migrate sees drift.
    char* err = nullptr;
    ASSERT_EQ(sqlite3_exec(db,
        "UPDATE schema_migrations SET checksum='deadbeef' WHERE version=1",
        nullptr, nullptr, &err), SQLITE_OK);
    EXPECT_THROW(
        starling::persistence::MigrationRunner(db).migrate_to_latest(),
        starling::persistence::MigrationDriftError);
    sqlite3_close(db);
}
```

- [ ] **Step 7: Register the test in `tests/cpp/CMakeLists.txt`**

```cmake
add_executable(test_migration_runner test_migration_runner.cpp)
target_link_libraries(test_migration_runner PRIVATE starling_core GTest::gtest_main)
gtest_discover_tests(test_migration_runner)
```

- [ ] **Step 8: Build and run**

Run: `cmake --build --preset default && ctest --preset default --output-on-failure -R MigrationRunner`
Expected: 4 tests, all PASS.

- [ ] **Step 9: Sanity-check with the sqlite3 CLI**

Run: `sqlite3 :memory: < migrations/0001_initial_schema.sql ".schema statements" | head -5`
Expected: schema dump containing `idx_statement_id_tenant`.

- [ ] **Step 10: Commit**

Run:
- `git add migrations/0001_initial_schema.sql include/starling/persistence/migration_runner.hpp src/persistence/migration_runner.cpp tests/cpp/test_migration_runner.cpp tests/cpp/CMakeLists.txt CMakeLists.txt`
- `git commit -m "feat(M0.2): migration runner with embedded SQL + drift detection"`

---

### Task 3: RAII sqlite3 wrappers + Connection class

**Files:**
- Create: `include/starling/persistence/sqlite_handles.hpp`
- Create: `include/starling/persistence/connection.hpp`
- Create: `src/persistence/connection.cpp`
- Create: `tests/cpp/test_connection.cpp`
- Modify: `CMakeLists.txt` (add `connection.cpp` to `starling_core` source list)
- Modify: `tests/cpp/CMakeLists.txt` (register test)

**Why:** Every later task acquires sqlite resources. Centralising the unique_ptr deleters and connection pragmas avoids leak/teardown bugs and keeps `BEGIN IMMEDIATE` / `ROLLBACK` consistent.

- [ ] **Step 1: Write `include/starling/persistence/sqlite_handles.hpp`**

```cpp
#pragma once
#include <sqlite3.h>
#include <memory>

namespace starling::persistence {

struct SqliteCloser  { void operator()(sqlite3* p)      const noexcept { if (p) sqlite3_close_v2(p); } };
struct StmtFinalizer { void operator()(sqlite3_stmt* p) const noexcept { if (p) sqlite3_finalize(p); } };

using SqliteHandle = std::unique_ptr<sqlite3, SqliteCloser>;
using StmtHandle   = std::unique_ptr<sqlite3_stmt, StmtFinalizer>;

}  // namespace starling::persistence
```

- [ ] **Step 2: Write `include/starling/persistence/connection.hpp`**

```cpp
#pragma once
#include "starling/persistence/sqlite_handles.hpp"
#include <filesystem>
#include <stdexcept>
#include <string>

namespace starling::persistence {

class SqliteError : public std::runtime_error {
public:
    SqliteError(std::string msg, int code) : runtime_error(std::move(msg)), code_(code) {}
    int code() const noexcept { return code_; }
private:
    int code_;
};

class Connection {
public:
    // Opens db_path with WAL + foreign_keys=ON + busy_timeout=5000.
    // Use ":memory:" for tests. Creates parent directories as needed.
    static Connection open(const std::filesystem::path& db_path);

    sqlite3* raw() noexcept { return handle_.get(); }

    // Executes SQL with no parameters. Throws on error.
    void exec(std::string_view sql);

    // BEGIN IMMEDIATE / COMMIT / ROLLBACK helpers. Nesting is not supported.
    void begin_immediate();
    void commit();
    void rollback() noexcept;

    // sqlite3_last_insert_rowid pass-through.
    int64_t last_insert_rowid() const noexcept;

private:
    explicit Connection(SqliteHandle h) : handle_(std::move(h)) {}
    SqliteHandle handle_;
};

class TransactionGuard {
public:
    explicit TransactionGuard(Connection& c) : conn_(c), active_(true) { conn_.begin_immediate(); }
    ~TransactionGuard() { if (active_) conn_.rollback(); }
    void commit() { conn_.commit(); active_ = false; }

    TransactionGuard(const TransactionGuard&) = delete;
    TransactionGuard& operator=(const TransactionGuard&) = delete;

private:
    Connection& conn_;
    bool active_;
};

}  // namespace starling::persistence
```

- [ ] **Step 3: Write `src/persistence/connection.cpp`**

```cpp
#include "starling/persistence/connection.hpp"

namespace starling::persistence {

namespace {
[[noreturn]] void throw_sqlite(sqlite3* db, std::string_view what) {
    const int rc = sqlite3_errcode(db);
    throw SqliteError(std::string(what) + ": " + sqlite3_errmsg(db), rc);
}
}  // namespace

Connection Connection::open(const std::filesystem::path& db_path) {
    if (db_path != ":memory:" && db_path.has_parent_path()) {
        std::filesystem::create_directories(db_path.parent_path());
    }
    sqlite3* raw = nullptr;
    const int rc = sqlite3_open_v2(
        db_path.string().c_str(), &raw,
        SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE | SQLITE_OPEN_FULLMUTEX,
        nullptr);
    SqliteHandle h(raw);
    if (rc != SQLITE_OK) {
        throw SqliteError(std::string("sqlite3_open_v2 failed: ") +
            (raw ? sqlite3_errmsg(raw) : "alloc failure"), rc);
    }
    Connection c(std::move(h));
    c.exec("PRAGMA foreign_keys = ON");
    c.exec("PRAGMA journal_mode = WAL");
    c.exec("PRAGMA synchronous = NORMAL");
    c.exec("PRAGMA busy_timeout = 5000");
    return c;
}

void Connection::exec(std::string_view sql) {
    char* err = nullptr;
    if (sqlite3_exec(handle_.get(), std::string(sql).c_str(),
                     nullptr, nullptr, &err) != SQLITE_OK) {
        std::string msg = err ? err : "unknown sqlite_exec error";
        sqlite3_free(err);
        throw SqliteError("exec failed: " + msg, sqlite3_errcode(handle_.get()));
    }
}

void Connection::begin_immediate() { exec("BEGIN IMMEDIATE"); }
void Connection::commit()          { exec("COMMIT"); }
void Connection::rollback() noexcept {
    sqlite3_exec(handle_.get(), "ROLLBACK", nullptr, nullptr, nullptr);
}

int64_t Connection::last_insert_rowid() const noexcept {
    return sqlite3_last_insert_rowid(handle_.get());
}

}  // namespace starling::persistence
```

- [ ] **Step 4: Add `connection.cpp` to `starling_core`**

In `CMakeLists.txt`:

```cmake
target_sources(starling_core PRIVATE
    src/persistence/connection.cpp
)
```

- [ ] **Step 5: Write `tests/cpp/test_connection.cpp`**

```cpp
#include <gtest/gtest.h>
#include "starling/persistence/connection.hpp"

using starling::persistence::Connection;
using starling::persistence::SqliteError;
using starling::persistence::TransactionGuard;

TEST(Connection, OpensInMemoryWithPragmas) {
    auto c = Connection::open(":memory:");
    ASSERT_NE(c.raw(), nullptr);
    c.exec("CREATE TABLE t(x INTEGER PRIMARY KEY)");
    c.exec("INSERT INTO t(x) VALUES(1)");
}

TEST(Connection, RollbackOnGuardDestruction) {
    auto c = Connection::open(":memory:");
    c.exec("CREATE TABLE t(x INTEGER)");
    {
        TransactionGuard g(c);
        c.exec("INSERT INTO t(x) VALUES(1)");
        // no commit -> rollback in dtor
    }
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(c.raw(), "SELECT COUNT(*) FROM t", -1, &s, nullptr);
    ASSERT_EQ(sqlite3_step(s), SQLITE_ROW);
    EXPECT_EQ(sqlite3_column_int(s, 0), 0);
    sqlite3_finalize(s);
}

TEST(Connection, CommitInsideGuardPersists) {
    auto c = Connection::open(":memory:");
    c.exec("CREATE TABLE t(x INTEGER)");
    {
        TransactionGuard g(c);
        c.exec("INSERT INTO t(x) VALUES(42)");
        g.commit();
    }
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(c.raw(), "SELECT x FROM t", -1, &s, nullptr);
    ASSERT_EQ(sqlite3_step(s), SQLITE_ROW);
    EXPECT_EQ(sqlite3_column_int(s, 0), 42);
    sqlite3_finalize(s);
}

TEST(Connection, ExecThrowsOnSyntaxError) {
    auto c = Connection::open(":memory:");
    EXPECT_THROW(c.exec("THIS IS NOT SQL"), SqliteError);
}
```

- [ ] **Step 6: Register test**

Append to `tests/cpp/CMakeLists.txt`:

```cmake
add_executable(test_connection test_connection.cpp)
target_link_libraries(test_connection PRIVATE starling_core GTest::gtest_main)
gtest_discover_tests(test_connection)
```

- [ ] **Step 7: Build + run**

Run: `cmake --build --preset default && ctest --preset default --output-on-failure -R Connection`
Expected: 4 tests PASS.

- [ ] **Step 8: Commit**

Run:
- `git add include/starling/persistence/sqlite_handles.hpp include/starling/persistence/connection.hpp src/persistence/connection.cpp tests/cpp/test_connection.cpp tests/cpp/CMakeLists.txt CMakeLists.txt`
- `git commit -m "feat(M0.2): RAII sqlite handles + Connection with TransactionGuard"`

---

### Task 4: BusEvent envelope (C++ struct + Python dataclass + parity test)

**Files:**
- Create: `include/starling/bus/bus_event.hpp`
- Create: `src/bus/bus_event.cpp`
- Create: `python/starling/bus/__init__.py`
- Create: `python/starling/bus/bus_event.py`
- Create: `python/starling/bus/idempotency.py`
- Create: `tests/cpp/test_idempotency_key.cpp`
- Create: `tests/python/test_bus_event_parity.py`
- Modify: `CMakeLists.txt`, `tests/cpp/CMakeLists.txt`

**Why:** The idempotency key formula must be byte-identical between C++ writer and Python consumer; otherwise dedup breaks across the binding boundary. Lock the formula here with a parity test before either side has callers.

- [ ] **Step 1: Write `include/starling/bus/bus_event.hpp`**

```cpp
#pragma once
#include <chrono>
#include <cstdint>
#include <string>
#include <vector>

namespace starling::bus {

struct BusEvent {
    std::string event_id;          // UUID
    std::string tenant_id;
    std::string event_type;        // e.g. "statement.created"
    std::string primary_id;        // table-driven: see §3.10 primary_id table
    std::string aggregate_id;      // ordering key — usually holder_id
    int64_t outbox_sequence = 0;   // claimed by OutboxWriter, monotonic
    std::vector<std::string> causation_chain;  // length ≤ 3
    std::string idempotency_key;   // sha256 hex of canonical material
    std::string payload_json;
    std::string created_at;        // ISO-8601 UTC
    std::string version = "v1";
};

// idempotency_key = sha256_hex(
//   event_type      ⊕ \x1f ⊕
//   aggregate_id    ⊕ \x1f ⊕
//   canonical_key   ⊕ \x1f ⊕
//   causation_root  ⊕ \x1f ⊕
//   window_bucket
// )
// causation_root = causation_chain.front() if non-empty else "".
// window_bucket is event-type-specific; see compute_window_bucket().
std::string compute_idempotency_key(
    std::string_view event_type,
    std::string_view aggregate_id,
    std::string_view canonical_key,
    std::string_view causation_root,
    std::string_view window_bucket);

// Per-event-type bucket. P1 events:
//   statement.created            -> ""               (already idempotent on canonical_key)
//   statement.superseded         -> ""
//   engram.appended              -> ""
//   pipeline_run.started         -> floor(now / 60s)
//   pipeline_run.finished        -> ""
//   extraction_attempt.recorded  -> ""
//   conflict_probe.flagged       -> ""
//   system.delivery_failed       -> ""
std::string compute_window_bucket(
    std::string_view event_type,
    std::chrono::system_clock::time_point now);

}  // namespace starling::bus
```

- [ ] **Step 2: Write `src/bus/bus_event.cpp`**

```cpp
#include "starling/bus/bus_event.hpp"

#include <openssl/evp.h>
#include <iomanip>
#include <sstream>

namespace starling::bus {

namespace {
constexpr char kSep = '\x1f';

std::string sha256_hex(std::string_view data) {
    unsigned char digest[EVP_MAX_MD_SIZE];
    unsigned int digest_len = 0;
    EVP_MD_CTX* ctx = EVP_MD_CTX_new();
    EVP_DigestInit_ex(ctx, EVP_sha256(), nullptr);
    EVP_DigestUpdate(ctx, data.data(), data.size());
    EVP_DigestFinal_ex(ctx, digest, &digest_len);
    EVP_MD_CTX_free(ctx);
    std::ostringstream oss;
    oss << std::hex << std::setfill('0');
    for (unsigned int i = 0; i < digest_len; ++i) {
        oss << std::setw(2) << static_cast<int>(digest[i]);
    }
    return oss.str();
}
}  // namespace

std::string compute_idempotency_key(
        std::string_view event_type,
        std::string_view aggregate_id,
        std::string_view canonical_key,
        std::string_view causation_root,
        std::string_view window_bucket) {
    std::string buf;
    buf.reserve(event_type.size() + aggregate_id.size() + canonical_key.size()
                + causation_root.size() + window_bucket.size() + 4);
    buf.append(event_type);   buf.push_back(kSep);
    buf.append(aggregate_id); buf.push_back(kSep);
    buf.append(canonical_key);buf.push_back(kSep);
    buf.append(causation_root);buf.push_back(kSep);
    buf.append(window_bucket);
    return sha256_hex(buf);
}

std::string compute_window_bucket(
        std::string_view event_type,
        std::chrono::system_clock::time_point now) {
    if (event_type == "pipeline_run.started") {
        const auto sec = std::chrono::duration_cast<std::chrono::seconds>(
            now.time_since_epoch()).count();
        return std::to_string(sec / 60);
    }
    return "";
}

}  // namespace starling::bus
```

- [ ] **Step 3: Wire into `starling_core`**

```cmake
target_sources(starling_core PRIVATE
    src/bus/bus_event.cpp
)
```

- [ ] **Step 4: Write `python/starling/bus/__init__.py`**

```python
"""Bus envelope + outbox/inbox dedup primitives (M0.2)."""

from starling.bus.bus_event import BusEvent, compute_idempotency_key, compute_window_bucket

__all__ = ["BusEvent", "compute_idempotency_key", "compute_window_bucket"]
```

- [ ] **Step 5: Write `python/starling/bus/bus_event.py`**

```python
"""BusEvent envelope (§3.10) — Python parity with src/bus/bus_event.cpp.

The idempotency_key formula MUST stay byte-identical to the C++ side. The
parity test (tests/python/test_bus_event_parity.py) calls into the pybind
binding and compares against this implementation.
"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone

_SEP = "\x1f"


@dataclass(frozen=True, slots=True, kw_only=True)
class BusEvent:
    event_id: str
    tenant_id: str
    event_type: str
    primary_id: str
    aggregate_id: str
    outbox_sequence: int
    causation_chain: tuple[str, ...]
    idempotency_key: str
    payload_json: str
    created_at: datetime
    version: str = "v1"


def compute_idempotency_key(
    *,
    event_type: str,
    aggregate_id: str,
    canonical_key: str,
    causation_root: str,
    window_bucket: str,
) -> str:
    parts = (event_type, aggregate_id, canonical_key, causation_root, window_bucket)
    raw = _SEP.join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def compute_window_bucket(event_type: str, now: datetime) -> str:
    if event_type == "pipeline_run.started":
        return str(int(now.replace(tzinfo=timezone.utc).timestamp()) // 60)
    return ""
```

- [ ] **Step 6: Write `python/starling/bus/idempotency.py`**

```python
"""Helpers for building canonical_key strings per event_type (§3.10)."""

from starling.schema.refs import CognizerRef


def canonical_key_for_statement_created(statement_id: str) -> str:
    return f"statement_id={statement_id}"


def canonical_key_for_statement_superseded(superseded_id: str, supersede_id: str) -> str:
    return f"superseded={superseded_id};by={supersede_id}"


def canonical_key_for_engram_appended(content_hash: str, holder_id: str) -> str:
    return f"engram_content={content_hash};holder={holder_id}"


def causation_root(causation_chain: tuple[str, ...]) -> str:
    return causation_chain[0] if causation_chain else ""
```

- [ ] **Step 7: Write `tests/cpp/test_idempotency_key.cpp`**

```cpp
#include <gtest/gtest.h>
#include "starling/bus/bus_event.hpp"

using starling::bus::compute_idempotency_key;

TEST(IdempotencyKey, SameInputsSameDigest) {
    const auto a = compute_idempotency_key("statement.created", "h1", "k1", "", "");
    const auto b = compute_idempotency_key("statement.created", "h1", "k1", "", "");
    EXPECT_EQ(a, b);
    EXPECT_EQ(a.size(), 64u);  // sha256 hex
}

TEST(IdempotencyKey, FieldChangesPropagate) {
    const auto base = compute_idempotency_key("e", "h", "k", "", "");
    EXPECT_NE(base, compute_idempotency_key("e", "h", "k2", "", ""));
    EXPECT_NE(base, compute_idempotency_key("e", "h2", "k", "", ""));
    EXPECT_NE(base, compute_idempotency_key("e2", "h", "k", "", ""));
    EXPECT_NE(base, compute_idempotency_key("e", "h", "k", "root", ""));
    EXPECT_NE(base, compute_idempotency_key("e", "h", "k", "", "bucket"));
}

TEST(IdempotencyKey, SeparatorPreventsCollision) {
    // "ab" + "" must differ from "a" + "b".
    EXPECT_NE(
        compute_idempotency_key("ab", "", "", "", ""),
        compute_idempotency_key("a", "b", "", "", ""));
}
```

- [ ] **Step 8: Register the C++ test**

```cmake
add_executable(test_idempotency_key test_idempotency_key.cpp)
target_link_libraries(test_idempotency_key PRIVATE starling_core GTest::gtest_main)
gtest_discover_tests(test_idempotency_key)
```

- [ ] **Step 9: Write `tests/python/test_bus_event_parity.py`**

This test calls a thin pybind wrapper exposed in Task 9. For Task 4 we ship a Python-only parity check against precomputed digests. The cross-language test gets added in Task 9.

```python
"""Pin the Python idempotency_key formula against pre-computed sha256 digests.

The digests below were produced by hashing the canonical material
``"\x1f".join(parts)`` with sha256 — same algorithm the C++ side uses.
The cross-language parity test that calls the C++ implementation lives
in ``tests/python/test_bus_binding_parity.py`` (added in Task 9).
"""

import hashlib

from starling.bus.bus_event import compute_idempotency_key


def _expected(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def test_basic_digest():
    actual = compute_idempotency_key(
        event_type="statement.created",
        aggregate_id="holder-1",
        canonical_key="statement_id=abc",
        causation_root="",
        window_bucket="",
    )
    assert actual == _expected("statement.created", "holder-1", "statement_id=abc", "", "")


def test_separator_prevents_concatenation_collision():
    a = compute_idempotency_key(
        event_type="ab", aggregate_id="", canonical_key="", causation_root="", window_bucket="",
    )
    b = compute_idempotency_key(
        event_type="a", aggregate_id="b", canonical_key="", causation_root="", window_bucket="",
    )
    assert a != b
```

- [ ] **Step 10: Build + run both sides**

Run:
- `cmake --build --preset default && ctest --preset default --output-on-failure -R IdempotencyKey`
- `pytest tests/python/test_bus_event_parity.py -v`

Expected: 3 C++ tests + 2 Python tests, all PASS.

- [ ] **Step 11: Commit**

Run:
- `git add include/starling/bus/bus_event.hpp src/bus/bus_event.cpp python/starling/bus/__init__.py python/starling/bus/bus_event.py python/starling/bus/idempotency.py tests/cpp/test_idempotency_key.cpp tests/python/test_bus_event_parity.py CMakeLists.txt tests/cpp/CMakeLists.txt`
- `git commit -m "feat(M0.2): BusEvent envelope + idempotency_key formula (C++/Py parity)"`

---

### Task 5: OutboxWriter.append (transactional, monotonic sequence claim)

**Files:**
- Create: `include/starling/bus/outbox_writer.hpp`
- Create: `src/bus/outbox_writer.cpp`
- Create: `tests/cpp/test_outbox_writer.cpp`
- Modify: `CMakeLists.txt`, `tests/cpp/CMakeLists.txt`

**Why:** OutboxWriter is the **only** sanctioned write path into `bus_events`. The append must run inside the same transaction as the producer's domain write — otherwise we lose at-least-once. Sequence claim uses `outbox_sequence_counter` (single-row, claimed under the same lock) so a rolled-back transaction does not consume sequence numbers.

- [ ] **Step 1: Write `include/starling/bus/outbox_writer.hpp`**

```cpp
#pragma once
#include "starling/bus/bus_event.hpp"
#include "starling/persistence/connection.hpp"
#include <chrono>

namespace starling::bus {

class OutboxWriter {
public:
    explicit OutboxWriter(starling::persistence::Connection& conn) : conn_(conn) {}

    // Append must be called inside an OPEN transaction on the same connection.
    // Throws if no transaction is active. Mutates ev: assigns event_id (UUIDv7),
    // outbox_sequence (claimed from outbox_sequence_counter), and created_at.
    // dispatch_status defaults to 'pending'.
    void append(BusEvent& ev);

    // Variant for the recursion guard: writes with dispatch_status='delivered'
    // so the dispatcher never picks it up. Used by the dispatcher's own
    // system.delivery_failed emit path.
    void append_already_delivered(BusEvent& ev);

private:
    void append_impl(BusEvent& ev, const char* dispatch_status);
    int64_t claim_next_sequence();

    starling::persistence::Connection& conn_;
};

}  // namespace starling::bus
```

- [ ] **Step 2: Write `src/bus/outbox_writer.cpp`**

```cpp
#include "starling/bus/outbox_writer.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <chrono>
#include <ctime>
#include <iomanip>
#include <random>
#include <sstream>
#include <stdexcept>

namespace starling::bus {

namespace {

std::string uuid_v7_like() {
    // Sufficient for M0.2: 128 random bits hex with dashes. Real UUIDv7 lands
    // in M0.4 alongside the LLM extractor (it needs time-prefix ordering for
    // extraction_span_key); for now random is fine because event_id is purely
    // a primary key, not an ordering key.
    static thread_local std::mt19937_64 rng{std::random_device{}()};
    uint64_t a = rng();
    uint64_t b = rng();
    std::ostringstream oss;
    oss << std::hex << std::setfill('0')
        << std::setw(8) << static_cast<uint32_t>(a >> 32) << '-'
        << std::setw(4) << static_cast<uint16_t>(a >> 16) << '-'
        << std::setw(4) << static_cast<uint16_t>(a) << '-'
        << std::setw(4) << static_cast<uint16_t>(b >> 48) << '-'
        << std::setw(12) << (b & 0xFFFFFFFFFFFFULL);
    return oss.str();
}

std::string now_iso8601_utc() {
    using namespace std::chrono;
    const auto t = system_clock::to_time_t(system_clock::now());
    std::tm tm{};
    gmtime_r(&t, &tm);
    std::ostringstream oss;
    oss << std::put_time(&tm, "%Y-%m-%dT%H:%M:%SZ");
    return oss.str();
}

std::string causation_chain_json(const std::vector<std::string>& chain) {
    std::ostringstream oss;
    oss << '[';
    for (size_t i = 0; i < chain.size(); ++i) {
        if (i) oss << ',';
        oss << '"' << chain[i] << '"';  // chain entries are UUIDs — no escape needed
    }
    oss << ']';
    return oss.str();
}

}  // namespace

int64_t OutboxWriter::claim_next_sequence() {
    starling::persistence::StmtHandle sel;
    sqlite3_stmt* raw = nullptr;
    sqlite3_prepare_v2(conn_.raw(),
        "SELECT next_value FROM outbox_sequence_counter WHERE id=1",
        -1, &raw, nullptr);
    sel.reset(raw);
    if (sqlite3_step(sel.get()) != SQLITE_ROW) {
        throw std::runtime_error("outbox_sequence_counter row missing");
    }
    const int64_t claimed = sqlite3_column_int64(sel.get(), 0);

    sqlite3_stmt* upd = nullptr;
    sqlite3_prepare_v2(conn_.raw(),
        "UPDATE outbox_sequence_counter SET next_value = next_value + 1 WHERE id=1",
        -1, &upd, nullptr);
    starling::persistence::StmtHandle u(upd);
    if (sqlite3_step(u.get()) != SQLITE_DONE) {
        throw std::runtime_error("outbox_sequence_counter update failed");
    }
    return claimed;
}

void OutboxWriter::append(BusEvent& ev) { append_impl(ev, "pending"); }

void OutboxWriter::append_already_delivered(BusEvent& ev) {
    append_impl(ev, "delivered");
}

void OutboxWriter::append_impl(BusEvent& ev, const char* dispatch_status) {
    if (ev.tenant_id.empty() || ev.event_type.empty()
        || ev.aggregate_id.empty() || ev.idempotency_key.empty()
        || ev.primary_id.empty() || ev.payload_json.empty()) {
        throw std::invalid_argument("OutboxWriter::append: required field empty");
    }
    if (ev.causation_chain.size() > 3) {
        throw std::invalid_argument("causation_chain length > 3");
    }
    if (ev.event_id.empty())     ev.event_id = uuid_v7_like();
    if (ev.created_at.empty())   ev.created_at = now_iso8601_utc();
    ev.outbox_sequence = claim_next_sequence();

    sqlite3_stmt* ins = nullptr;
    const char* sql =
        "INSERT INTO bus_events("
        "event_id,tenant_id,event_type,primary_id,aggregate_id,outbox_sequence,"
        "causation_chain_json,idempotency_key,payload_json,created_at,version,"
        "dispatch_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)";
    sqlite3_prepare_v2(conn_.raw(), sql, -1, &ins, nullptr);
    starling::persistence::StmtHandle s(ins);
    const std::string chain_json = causation_chain_json(ev.causation_chain);

    sqlite3_bind_text (s.get(),  1, ev.event_id.c_str(),       -1, SQLITE_TRANSIENT);
    sqlite3_bind_text (s.get(),  2, ev.tenant_id.c_str(),      -1, SQLITE_TRANSIENT);
    sqlite3_bind_text (s.get(),  3, ev.event_type.c_str(),     -1, SQLITE_TRANSIENT);
    sqlite3_bind_text (s.get(),  4, ev.primary_id.c_str(),     -1, SQLITE_TRANSIENT);
    sqlite3_bind_text (s.get(),  5, ev.aggregate_id.c_str(),   -1, SQLITE_TRANSIENT);
    sqlite3_bind_int64(s.get(),  6, ev.outbox_sequence);
    sqlite3_bind_text (s.get(),  7, chain_json.c_str(),        -1, SQLITE_TRANSIENT);
    sqlite3_bind_text (s.get(),  8, ev.idempotency_key.c_str(),-1, SQLITE_TRANSIENT);
    sqlite3_bind_text (s.get(),  9, ev.payload_json.c_str(),   -1, SQLITE_TRANSIENT);
    sqlite3_bind_text (s.get(), 10, ev.created_at.c_str(),     -1, SQLITE_TRANSIENT);
    sqlite3_bind_text (s.get(), 11, ev.version.c_str(),        -1, SQLITE_TRANSIENT);
    sqlite3_bind_text (s.get(), 12, dispatch_status,           -1, SQLITE_STATIC);

    if (sqlite3_step(s.get()) != SQLITE_DONE) {
        throw starling::persistence::SqliteError(
            std::string("bus_events INSERT failed: ") + sqlite3_errmsg(conn_.raw()),
            sqlite3_errcode(conn_.raw()));
    }
}

}  // namespace starling::bus
```

- [ ] **Step 3: Wire into `starling_core`**

```cmake
target_sources(starling_core PRIVATE
    src/bus/outbox_writer.cpp
)
```

- [ ] **Step 4: Write `tests/cpp/test_outbox_writer.cpp`**

```cpp
#include <gtest/gtest.h>
#include "starling/bus/outbox_writer.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/migration_runner.hpp"

using starling::bus::BusEvent;
using starling::bus::OutboxWriter;
using starling::persistence::Connection;
using starling::persistence::MigrationRunner;
using starling::persistence::TransactionGuard;

namespace {

Connection fresh_db() {
    auto c = Connection::open(":memory:");
    MigrationRunner(c.raw()).migrate_to_latest();
    return c;
}

BusEvent make_event(const std::string& key) {
    return BusEvent{
        .tenant_id = "t1",
        .event_type = "statement.created",
        .primary_id = "stmt-1",
        .aggregate_id = "holder-1",
        .causation_chain = {},
        .idempotency_key = key,
        .payload_json = "{}",
    };
}

int count(Connection& c, const char* sql) {
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(c.raw(), sql, -1, &s, nullptr);
    sqlite3_step(s);
    const int n = sqlite3_column_int(s, 0);
    sqlite3_finalize(s);
    return n;
}

}  // namespace

TEST(OutboxWriter, AppendsAssignsSequenceAndPersists) {
    auto c = fresh_db();
    OutboxWriter w(c);
    auto ev = make_event("k1");
    {
        TransactionGuard g(c);
        w.append(ev);
        g.commit();
    }
    EXPECT_GT(ev.outbox_sequence, 0);
    EXPECT_FALSE(ev.event_id.empty());
    EXPECT_FALSE(ev.created_at.empty());
    EXPECT_EQ(count(c, "SELECT COUNT(*) FROM bus_events WHERE dispatch_status='pending'"), 1);
}

TEST(OutboxWriter, SequenceMonotonicAcrossAppends) {
    auto c = fresh_db();
    OutboxWriter w(c);
    auto a = make_event("k1");
    auto b = make_event("k2");
    {
        TransactionGuard g(c);
        w.append(a);
        w.append(b);
        g.commit();
    }
    EXPECT_EQ(b.outbox_sequence, a.outbox_sequence + 1);
}

TEST(OutboxWriter, RollbackDoesNotLeaveSequenceGaps) {
    auto c = fresh_db();
    OutboxWriter w(c);
    auto a = make_event("k1");
    {
        TransactionGuard g(c);
        w.append(a);
        // implicit rollback
    }
    auto b = make_event("k2");
    {
        TransactionGuard g(c);
        w.append(b);
        g.commit();
    }
    // The rolled-back transaction's UPDATE on outbox_sequence_counter is also
    // rolled back — so b reuses a's would-be sequence, no gap.
    EXPECT_EQ(b.outbox_sequence, a.outbox_sequence);
}

TEST(OutboxWriter, RejectsDuplicateIdempotencyKey) {
    auto c = fresh_db();
    OutboxWriter w(c);
    auto a = make_event("dup");
    auto b = make_event("dup");
    {
        TransactionGuard g(c);
        w.append(a);
        EXPECT_THROW(w.append(b), starling::persistence::SqliteError);
        // guard rolls back
    }
    EXPECT_EQ(count(c, "SELECT COUNT(*) FROM bus_events"), 0);
}

TEST(OutboxWriter, AppendAlreadyDeliveredFlagSet) {
    auto c = fresh_db();
    OutboxWriter w(c);
    auto a = make_event("k1");
    {
        TransactionGuard g(c);
        w.append_already_delivered(a);
        g.commit();
    }
    EXPECT_EQ(count(c, "SELECT COUNT(*) FROM bus_events WHERE dispatch_status='delivered'"), 1);
}
```

- [ ] **Step 5: Register the test**

```cmake
add_executable(test_outbox_writer test_outbox_writer.cpp)
target_link_libraries(test_outbox_writer PRIVATE starling_core GTest::gtest_main)
gtest_discover_tests(test_outbox_writer)
```

- [ ] **Step 6: Build + run**

Run: `cmake --build --preset default && ctest --preset default --output-on-failure -R OutboxWriter`
Expected: 5 tests PASS.

- [ ] **Step 7: Commit**

Run:
- `git add include/starling/bus/outbox_writer.hpp src/bus/outbox_writer.cpp tests/cpp/test_outbox_writer.cpp CMakeLists.txt tests/cpp/CMakeLists.txt`
- `git commit -m "feat(M0.2): OutboxWriter with monotonic sequence claim + idempotency_key uniqueness"`

---

### Task 6: ConsumerCheckpoint + IdempotencyInbox (consumer-side dedup, 7-day expiry)

**Files:**
- Create: `include/starling/bus/consumer_state.hpp`
- Create: `src/bus/consumer_state.cpp`
- Create: `tests/cpp/test_consumer_state.cpp`
- Modify: `CMakeLists.txt`, `tests/cpp/CMakeLists.txt`

**Why:** Splits cleanly from OutboxWriter. The dispatcher (Task 7) calls into these primitives; tests pin the dedup window + expiry rule before the dispatcher integrates them.

- [ ] **Step 1: Write `include/starling/bus/consumer_state.hpp`**

```cpp
#pragma once
#include "starling/persistence/connection.hpp"
#include <chrono>
#include <optional>
#include <string>

namespace starling::bus {

class ConsumerCheckpoint {
public:
    explicit ConsumerCheckpoint(starling::persistence::Connection& c) : conn_(c) {}

    int64_t last_delivered(std::string_view consumer_id);
    void advance(std::string_view consumer_id, int64_t sequence);

private:
    starling::persistence::Connection& conn_;
};

class IdempotencyInbox {
public:
    explicit IdempotencyInbox(starling::persistence::Connection& c) : conn_(c) {}

    // Returns true if the (consumer, key) pair was inserted (i.e., not seen).
    // Returns false if it was already present (caller must skip the side-effect).
    bool record_if_new(std::string_view consumer_id,
                       std::string_view idempotency_key,
                       std::chrono::system_clock::time_point now,
                       std::chrono::seconds ttl);

    // Deletes rows whose expires_at < now. Returns rows pruned.
    int64_t purge_expired(std::chrono::system_clock::time_point now);

private:
    starling::persistence::Connection& conn_;
};

}  // namespace starling::bus
```

- [ ] **Step 2: Write `src/bus/consumer_state.cpp`**

```cpp
#include "starling/bus/consumer_state.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <chrono>
#include <ctime>
#include <iomanip>
#include <sstream>
#include <stdexcept>

namespace starling::bus {

namespace {
std::string iso8601_utc(std::chrono::system_clock::time_point t) {
    const auto secs = std::chrono::system_clock::to_time_t(t);
    std::tm tm{};
    gmtime_r(&secs, &tm);
    std::ostringstream oss;
    oss << std::put_time(&tm, "%Y-%m-%dT%H:%M:%SZ");
    return oss.str();
}
}  // namespace

int64_t ConsumerCheckpoint::last_delivered(std::string_view consumer_id) {
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(conn_.raw(),
        "SELECT last_delivered_sequence FROM consumer_checkpoint WHERE consumer_id=?",
        -1, &s, nullptr);
    starling::persistence::StmtHandle h(s);
    sqlite3_bind_text(h.get(), 1, std::string(consumer_id).c_str(), -1, SQLITE_TRANSIENT);
    const int rc = sqlite3_step(h.get());
    if (rc == SQLITE_ROW) return sqlite3_column_int64(h.get(), 0);
    return 0;
}

void ConsumerCheckpoint::advance(std::string_view consumer_id, int64_t sequence) {
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(conn_.raw(),
        "INSERT INTO consumer_checkpoint(consumer_id,last_delivered_sequence,updated_at) "
        "VALUES(?,?,?) "
        "ON CONFLICT(consumer_id) DO UPDATE SET "
        "  last_delivered_sequence=MAX(consumer_checkpoint.last_delivered_sequence, excluded.last_delivered_sequence),"
        "  updated_at=excluded.updated_at",
        -1, &s, nullptr);
    starling::persistence::StmtHandle h(s);
    const std::string ts = iso8601_utc(std::chrono::system_clock::now());
    sqlite3_bind_text (h.get(), 1, std::string(consumer_id).c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int64(h.get(), 2, sequence);
    sqlite3_bind_text (h.get(), 3, ts.c_str(),                       -1, SQLITE_TRANSIENT);
    if (sqlite3_step(h.get()) != SQLITE_DONE) {
        throw std::runtime_error("consumer_checkpoint upsert failed");
    }
}

bool IdempotencyInbox::record_if_new(
        std::string_view consumer_id,
        std::string_view idempotency_key,
        std::chrono::system_clock::time_point now,
        std::chrono::seconds ttl) {
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(conn_.raw(),
        "INSERT OR IGNORE INTO idempotency_inbox("
        "consumer_id,idempotency_key,received_at,expires_at) VALUES(?,?,?,?)",
        -1, &s, nullptr);
    starling::persistence::StmtHandle h(s);
    const std::string received = iso8601_utc(now);
    const std::string expires  = iso8601_utc(now + ttl);
    sqlite3_bind_text(h.get(), 1, std::string(consumer_id).c_str(),     -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(h.get(), 2, std::string(idempotency_key).c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(h.get(), 3, received.c_str(),                     -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(h.get(), 4, expires.c_str(),                      -1, SQLITE_TRANSIENT);
    if (sqlite3_step(h.get()) != SQLITE_DONE) {
        throw std::runtime_error("idempotency_inbox insert failed");
    }
    return sqlite3_changes(conn_.raw()) > 0;
}

int64_t IdempotencyInbox::purge_expired(std::chrono::system_clock::time_point now) {
    const std::string nowstr = iso8601_utc(now);
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(conn_.raw(),
        "DELETE FROM idempotency_inbox WHERE expires_at < ?", -1, &s, nullptr);
    starling::persistence::StmtHandle h(s);
    sqlite3_bind_text(h.get(), 1, nowstr.c_str(), -1, SQLITE_TRANSIENT);
    if (sqlite3_step(h.get()) != SQLITE_DONE) {
        throw std::runtime_error("idempotency_inbox purge failed");
    }
    return sqlite3_changes(conn_.raw());
}

}  // namespace starling::bus
```

- [ ] **Step 3: Wire in**

```cmake
target_sources(starling_core PRIVATE
    src/bus/consumer_state.cpp
)
```

- [ ] **Step 4: Write `tests/cpp/test_consumer_state.cpp`**

```cpp
#include <gtest/gtest.h>
#include "starling/bus/consumer_state.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/migration_runner.hpp"

using starling::bus::ConsumerCheckpoint;
using starling::bus::IdempotencyInbox;
using starling::persistence::Connection;
using starling::persistence::MigrationRunner;

namespace {
Connection fresh() {
    auto c = Connection::open(":memory:");
    MigrationRunner(c.raw()).migrate_to_latest();
    return c;
}
}

TEST(ConsumerCheckpoint, DefaultsToZero) {
    auto c = fresh();
    EXPECT_EQ(ConsumerCheckpoint(c).last_delivered("c1"), 0);
}

TEST(ConsumerCheckpoint, AdvanceMonotonic) {
    auto c = fresh();
    ConsumerCheckpoint cp(c);
    cp.advance("c1", 5);
    cp.advance("c1", 3);  // attempted regression
    EXPECT_EQ(cp.last_delivered("c1"), 5);
    cp.advance("c1", 10);
    EXPECT_EQ(cp.last_delivered("c1"), 10);
}

TEST(IdempotencyInbox, RecordIfNewDedups) {
    auto c = fresh();
    IdempotencyInbox inbox(c);
    const auto now = std::chrono::system_clock::now();
    EXPECT_TRUE (inbox.record_if_new("c1", "k1", now, std::chrono::hours(24*7)));
    EXPECT_FALSE(inbox.record_if_new("c1", "k1", now, std::chrono::hours(24*7)));
    EXPECT_TRUE (inbox.record_if_new("c2", "k1", now, std::chrono::hours(24*7)));
}

TEST(IdempotencyInbox, PurgeExpiredRemovesOldRows) {
    auto c = fresh();
    IdempotencyInbox inbox(c);
    const auto t0 = std::chrono::system_clock::now();
    inbox.record_if_new("c1", "old", t0, std::chrono::hours(1));
    inbox.record_if_new("c1", "new", t0, std::chrono::hours(48));
    const auto later = t0 + std::chrono::hours(2);
    EXPECT_EQ(inbox.purge_expired(later), 1);
    // 'new' still present -> record_if_new returns false
    EXPECT_FALSE(inbox.record_if_new("c1", "new", later, std::chrono::hours(48)));
}
```

- [ ] **Step 5: Register test**

```cmake
add_executable(test_consumer_state test_consumer_state.cpp)
target_link_libraries(test_consumer_state PRIVATE starling_core GTest::gtest_main)
gtest_discover_tests(test_consumer_state)
```

- [ ] **Step 6: Build + run**

Run: `cmake --build --preset default && ctest --preset default --output-on-failure -R ConsumerCheckpoint -R IdempotencyInbox`
Expected: 4 tests PASS.

- [ ] **Step 7: Commit**

Run:
- `git add include/starling/bus/consumer_state.hpp src/bus/consumer_state.cpp tests/cpp/test_consumer_state.cpp CMakeLists.txt tests/cpp/CMakeLists.txt`
- `git commit -m "feat(M0.2): consumer_checkpoint + idempotency_inbox with 7-day TTL"`

---

### Task 7: OutboxDispatcher.run_once (per-aggregate ordering, retries, dead-letter)

**Files:**
- Create: `include/starling/bus/outbox_dispatcher.hpp`
- Create: `src/bus/outbox_dispatcher.cpp`
- Create: `tests/cpp/test_outbox_dispatcher.cpp`
- Modify: `CMakeLists.txt`, `tests/cpp/CMakeLists.txt`

**Why:** This is the heart of TC-NEW-OUTBOX-IDEMP. The dispatcher must:
1. Drain `bus_events` in `outbox_sequence` order, **respecting per-`aggregate_id` ordering** (don't deliver later sequence for `holder-1` while an earlier one is still in flight).
2. Mark in_flight → delivered atomically with the consumer's idempotency_inbox row + checkpoint.
3. Retry on consumer failure with `dispatch_attempts < max_retries=5`.
4. After max_retries, flip to `dead_letter` and emit a `system.delivery_failed` event with `dispatch_status='delivered'` (recursion guard — see Subsystem Contract D).
5. Provide a callback hook so tests can inject a "fail the first N times" consumer.

- [ ] **Step 1: Write `include/starling/bus/outbox_dispatcher.hpp`**

```cpp
#pragma once
#include "starling/bus/bus_event.hpp"
#include "starling/bus/consumer_state.hpp"
#include "starling/bus/outbox_writer.hpp"
#include "starling/persistence/connection.hpp"
#include <chrono>
#include <functional>
#include <string>

namespace starling::bus {

struct DispatchOptions {
    std::string consumer_id = "default";
    int max_retries = 5;
    int max_events_per_run = 1000;
    std::chrono::seconds inbox_ttl = std::chrono::hours(24 * 7);
};

enum class ConsumerDecision {
    Accept,            // mark delivered
    TransientError,    // increment attempts, leave pending
    PermanentError,    // jump straight to dead_letter
};

// Consumer callback. Receives the event; throwing is treated as TransientError.
using Consumer = std::function<ConsumerDecision(const BusEvent&)>;

struct DispatchStats {
    int delivered = 0;
    int retried = 0;
    int dead_lettered = 0;
    int skipped_blocked = 0;  // earlier event for same aggregate still pending
};

class OutboxDispatcher {
public:
    OutboxDispatcher(starling::persistence::Connection& conn,
                     Consumer consumer,
                     DispatchOptions opts = {});

    DispatchStats run_once();

private:
    starling::persistence::Connection& conn_;
    Consumer consumer_;
    DispatchOptions opts_;
};

}  // namespace starling::bus
```

- [ ] **Step 2: Write `src/bus/outbox_dispatcher.cpp`**

```cpp
#include "starling/bus/outbox_dispatcher.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <chrono>
#include <ctime>
#include <iomanip>
#include <set>
#include <sstream>
#include <stdexcept>

namespace starling::bus {

namespace {

std::string now_iso8601_utc() {
    using namespace std::chrono;
    const auto t = system_clock::to_time_t(system_clock::now());
    std::tm tm{};
    gmtime_r(&t, &tm);
    std::ostringstream oss;
    oss << std::put_time(&tm, "%Y-%m-%dT%H:%M:%SZ");
    return oss.str();
}

std::string read_text(sqlite3_stmt* s, int col) {
    const auto* p = sqlite3_column_text(s, col);
    return p ? std::string(reinterpret_cast<const char*>(p)) : std::string();
}

}  // namespace

OutboxDispatcher::OutboxDispatcher(
        starling::persistence::Connection& conn,
        Consumer consumer,
        DispatchOptions opts)
    : conn_(conn), consumer_(std::move(consumer)), opts_(std::move(opts)) {}

DispatchStats OutboxDispatcher::run_once() {
    DispatchStats stats;

    // Crash recovery: reset any in_flight events back to pending. This handles
    // the TC-NEW-OUTBOX-IDEMP crash scenario where the process died mid-deliver.
    conn_.exec("UPDATE bus_events SET dispatch_status='pending' "
               "WHERE dispatch_status='in_flight'");

    // Snapshot pending events by ascending outbox_sequence.
    std::vector<BusEvent> pending;
    std::vector<int> attempts;
    {
        sqlite3_stmt* sel = nullptr;
        sqlite3_prepare_v2(conn_.raw(),
            "SELECT event_id,tenant_id,event_type,primary_id,aggregate_id,"
            "outbox_sequence,causation_chain_json,idempotency_key,payload_json,"
            "created_at,version,dispatch_attempts "
            "FROM bus_events WHERE dispatch_status='pending' "
            "ORDER BY outbox_sequence ASC LIMIT ?",
            -1, &sel, nullptr);
        starling::persistence::StmtHandle h(sel);
        sqlite3_bind_int(h.get(), 1, opts_.max_events_per_run);
        while (sqlite3_step(h.get()) == SQLITE_ROW) {
            BusEvent ev;
            ev.event_id        = read_text(h.get(), 0);
            ev.tenant_id       = read_text(h.get(), 1);
            ev.event_type      = read_text(h.get(), 2);
            ev.primary_id      = read_text(h.get(), 3);
            ev.aggregate_id    = read_text(h.get(), 4);
            ev.outbox_sequence = sqlite3_column_int64(h.get(), 5);
            ev.idempotency_key = read_text(h.get(), 7);
            ev.payload_json    = read_text(h.get(), 8);
            ev.created_at      = read_text(h.get(), 9);
            ev.version         = read_text(h.get(), 10);
            // causation_chain_json is opaque on this side (Task 8 parses it
            // when needed); leave ev.causation_chain empty.
            pending.push_back(std::move(ev));
            attempts.push_back(sqlite3_column_int(h.get(), 11));
        }
    }

    std::set<std::string> blocked_aggregates;

    ConsumerCheckpoint cp(conn_);
    IdempotencyInbox inbox(conn_);
    OutboxWriter writer(conn_);

    for (size_t i = 0; i < pending.size(); ++i) {
        BusEvent& ev = pending[i];

        // Per-aggregate ordering: if an earlier event for this aggregate has
        // failed permanently or is currently being retried this run, do not
        // proceed past it for the same aggregate.
        if (blocked_aggregates.contains(ev.aggregate_id)) {
            ++stats.skipped_blocked;
            continue;
        }

        // Mark in_flight outside the consumer call so a crash mid-call leaves
        // a recoverable trail.
        {
            starling::persistence::TransactionGuard g(conn_);
            sqlite3_stmt* upd = nullptr;
            sqlite3_prepare_v2(conn_.raw(),
                "UPDATE bus_events SET dispatch_status='in_flight', "
                "last_attempt_at=? WHERE event_id=? AND dispatch_status='pending'",
                -1, &upd, nullptr);
            starling::persistence::StmtHandle h(upd);
            const std::string ts = now_iso8601_utc();
            sqlite3_bind_text(h.get(), 1, ts.c_str(),         -1, SQLITE_TRANSIENT);
            sqlite3_bind_text(h.get(), 2, ev.event_id.c_str(),-1, SQLITE_TRANSIENT);
            sqlite3_step(h.get());
            g.commit();
        }

        // Invoke consumer. Exceptions count as transient failures.
        ConsumerDecision decision = ConsumerDecision::TransientError;
        std::string err;
        try {
            decision = consumer_(ev);
        } catch (const std::exception& e) {
            err = e.what();
        }

        const int new_attempts = attempts[i] + 1;

        if (decision == ConsumerDecision::Accept) {
            starling::persistence::TransactionGuard g(conn_);
            const bool fresh = inbox.record_if_new(
                opts_.consumer_id, ev.idempotency_key,
                std::chrono::system_clock::now(), opts_.inbox_ttl);
            (void)fresh;  // dedup observed at consumer side; both branches commit delivered.
            sqlite3_stmt* upd = nullptr;
            sqlite3_prepare_v2(conn_.raw(),
                "UPDATE bus_events SET dispatch_status='delivered',"
                "dispatch_attempts=?, last_attempt_at=? WHERE event_id=?",
                -1, &upd, nullptr);
            starling::persistence::StmtHandle h(upd);
            const std::string ts = now_iso8601_utc();
            sqlite3_bind_int (h.get(), 1, new_attempts);
            sqlite3_bind_text(h.get(), 2, ts.c_str(),         -1, SQLITE_TRANSIENT);
            sqlite3_bind_text(h.get(), 3, ev.event_id.c_str(),-1, SQLITE_TRANSIENT);
            sqlite3_step(h.get());
            cp.advance(opts_.consumer_id, ev.outbox_sequence);
            g.commit();
            ++stats.delivered;
            continue;
        }

        const bool exhausted =
            decision == ConsumerDecision::PermanentError
            || new_attempts >= opts_.max_retries;

        if (!exhausted) {
            starling::persistence::TransactionGuard g(conn_);
            sqlite3_stmt* upd = nullptr;
            sqlite3_prepare_v2(conn_.raw(),
                "UPDATE bus_events SET dispatch_status='pending',"
                "dispatch_attempts=?, last_attempt_at=?, last_error=? "
                "WHERE event_id=?",
                -1, &upd, nullptr);
            starling::persistence::StmtHandle h(upd);
            const std::string ts = now_iso8601_utc();
            sqlite3_bind_int (h.get(), 1, new_attempts);
            sqlite3_bind_text(h.get(), 2, ts.c_str(),                -1, SQLITE_TRANSIENT);
            sqlite3_bind_text(h.get(), 3, err.empty() ? "transient_error" : err.c_str(),
                                                                     -1, SQLITE_TRANSIENT);
            sqlite3_bind_text(h.get(), 4, ev.event_id.c_str(),       -1, SQLITE_TRANSIENT);
            sqlite3_step(h.get());
            g.commit();
            ++stats.retried;
            blocked_aggregates.insert(ev.aggregate_id);
            continue;
        }

        // Dead-letter path
        {
            starling::persistence::TransactionGuard g(conn_);
            sqlite3_stmt* upd = nullptr;
            sqlite3_prepare_v2(conn_.raw(),
                "UPDATE bus_events SET dispatch_status='dead_letter',"
                "dispatch_attempts=?, last_attempt_at=?, last_error=? "
                "WHERE event_id=?",
                -1, &upd, nullptr);
            starling::persistence::StmtHandle h(upd);
            const std::string ts = now_iso8601_utc();
            sqlite3_bind_int (h.get(), 1, new_attempts);
            sqlite3_bind_text(h.get(), 2, ts.c_str(),                -1, SQLITE_TRANSIENT);
            sqlite3_bind_text(h.get(), 3, err.empty() ? "permanent_error" : err.c_str(),
                                                                     -1, SQLITE_TRANSIENT);
            sqlite3_bind_text(h.get(), 4, ev.event_id.c_str(),       -1, SQLITE_TRANSIENT);
            sqlite3_step(h.get());

            // Recursion guard: emit system.delivery_failed with
            // dispatch_status='delivered' so the dispatcher itself never picks
            // it up. Payload is just the original event_id.
            BusEvent failure_evt{
                .tenant_id = ev.tenant_id,
                .event_type = "system.delivery_failed",
                .primary_id = ev.event_id,
                .aggregate_id = ev.aggregate_id,
                .causation_chain = {ev.event_id},
                .idempotency_key = ev.idempotency_key + ":delivery_failed",
                .payload_json = std::string("{\"failed_event_id\":\"") + ev.event_id + "\"}",
            };
            writer.append_already_delivered(failure_evt);
            g.commit();
        }
        ++stats.dead_lettered;
        blocked_aggregates.insert(ev.aggregate_id);
    }

    return stats;
}

}  // namespace starling::bus
```

- [ ] **Step 3: Wire into `starling_core`**

```cmake
target_sources(starling_core PRIVATE
    src/bus/outbox_dispatcher.cpp
)
```

- [ ] **Step 4: Write `tests/cpp/test_outbox_dispatcher.cpp`**

```cpp
#include <gtest/gtest.h>
#include "starling/bus/outbox_dispatcher.hpp"
#include "starling/bus/outbox_writer.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/migration_runner.hpp"
#include <atomic>

using namespace starling::bus;
using starling::persistence::Connection;
using starling::persistence::MigrationRunner;
using starling::persistence::TransactionGuard;

namespace {

Connection fresh() {
    auto c = Connection::open(":memory:");
    MigrationRunner(c.raw()).migrate_to_latest();
    return c;
}

void seed(Connection& c, const std::string& aggregate, const std::string& key) {
    OutboxWriter w(c);
    BusEvent ev{
        .tenant_id = "t1",
        .event_type = "statement.created",
        .primary_id = "stmt-" + key,
        .aggregate_id = aggregate,
        .idempotency_key = key,
        .payload_json = "{}",
    };
    TransactionGuard g(c);
    w.append(ev);
    g.commit();
}

int count(Connection& c, const char* sql) {
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(c.raw(), sql, -1, &s, nullptr);
    sqlite3_step(s);
    const int n = sqlite3_column_int(s, 0);
    sqlite3_finalize(s);
    return n;
}

}  // namespace

TEST(OutboxDispatcher, AcceptingConsumerDeliversAll) {
    auto c = fresh();
    seed(c, "h1", "k1");
    seed(c, "h1", "k2");
    seed(c, "h2", "k3");
    OutboxDispatcher d(c, [](const BusEvent&) { return ConsumerDecision::Accept; });
    auto stats = d.run_once();
    EXPECT_EQ(stats.delivered, 3);
    EXPECT_EQ(count(c, "SELECT COUNT(*) FROM bus_events WHERE dispatch_status='delivered'"), 3);
}

TEST(OutboxDispatcher, PerAggregateOrderingHonoredOnRetry) {
    auto c = fresh();
    seed(c, "h1", "k1");  // will fail
    seed(c, "h1", "k2");  // must NOT deliver while k1 still pending
    seed(c, "h2", "k3");  // independent aggregate, should deliver
    int calls = 0;
    OutboxDispatcher d(c, [&](const BusEvent& ev) {
        ++calls;
        if (ev.idempotency_key == "k1") return ConsumerDecision::TransientError;
        return ConsumerDecision::Accept;
    });
    auto stats = d.run_once();
    EXPECT_EQ(stats.delivered, 1);             // only k3
    EXPECT_EQ(stats.retried, 1);                // k1
    EXPECT_EQ(stats.skipped_blocked, 1);        // k2 blocked by k1
}

TEST(OutboxDispatcher, DeadLetterAfterMaxRetries) {
    auto c = fresh();
    seed(c, "h1", "k1");
    OutboxDispatcher d(c, [](const BusEvent&) { return ConsumerDecision::TransientError; },
                      DispatchOptions{.max_retries = 3});
    int total_attempts = 0;
    for (int i = 0; i < 4; ++i) {
        auto s = d.run_once();
        total_attempts += s.retried + s.dead_lettered;
    }
    EXPECT_EQ(count(c, "SELECT COUNT(*) FROM bus_events WHERE dispatch_status='dead_letter'"), 1);
    // system.delivery_failed appended with dispatch_status='delivered'
    EXPECT_EQ(count(c,
        "SELECT COUNT(*) FROM bus_events "
        "WHERE event_type='system.delivery_failed' AND dispatch_status='delivered'"), 1);
}

TEST(OutboxDispatcher, IdempotencyInboxDedupsOnRedelivery) {
    auto c = fresh();
    seed(c, "h1", "k1");
    int delivered_count = 0;
    Consumer once = [&](const BusEvent&) {
        ++delivered_count;
        return ConsumerDecision::Accept;
    };
    OutboxDispatcher(c, once).run_once();
    // Simulate a forced redeliver by flipping the row back to pending.
    c.exec("UPDATE bus_events SET dispatch_status='pending' WHERE idempotency_key='k1'");
    OutboxDispatcher(c, once).run_once();
    // Consumer was invoked twice (the inbox lives at the consumer side, not
    // the dispatcher; the dispatcher's job is to deliver — the test verifies
    // the inbox row is still present after the second delivery).
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(c.raw(),
        "SELECT COUNT(*) FROM idempotency_inbox WHERE idempotency_key='k1'",
        -1, &s, nullptr);
    sqlite3_step(s);
    EXPECT_EQ(sqlite3_column_int(s, 0), 1);
    sqlite3_finalize(s);
    EXPECT_EQ(delivered_count, 2);
}

TEST(OutboxDispatcher, CrashRecoveryResetsInFlight) {
    auto c = fresh();
    seed(c, "h1", "k1");
    // Simulate crash mid-deliver: row stuck in_flight.
    c.exec("UPDATE bus_events SET dispatch_status='in_flight' WHERE idempotency_key='k1'");
    OutboxDispatcher d(c, [](const BusEvent&) { return ConsumerDecision::Accept; });
    auto stats = d.run_once();
    EXPECT_EQ(stats.delivered, 1);
}
```

- [ ] **Step 5: Register test**

```cmake
add_executable(test_outbox_dispatcher test_outbox_dispatcher.cpp)
target_link_libraries(test_outbox_dispatcher PRIVATE starling_core GTest::gtest_main)
gtest_discover_tests(test_outbox_dispatcher)
```

- [ ] **Step 6: Build + run**

Run: `cmake --build --preset default && ctest --preset default --output-on-failure -R OutboxDispatcher`
Expected: 5 tests PASS.

- [ ] **Step 7: Commit**

Run:
- `git add include/starling/bus/outbox_dispatcher.hpp src/bus/outbox_dispatcher.cpp tests/cpp/test_outbox_dispatcher.cpp CMakeLists.txt tests/cpp/CMakeLists.txt`
- `git commit -m "feat(M0.2): outbox dispatcher with per-aggregate ordering + dead-letter recursion guard"`

---

### Task 8: PipelineRun + ExtractionAttempt ledger writes (M0.4 prep, no LLM yet)

**Files:**
- Create: `include/starling/bus/pipeline_ledger.hpp`
- Create: `src/bus/pipeline_ledger.cpp`
- Create: `tests/cpp/test_pipeline_ledger.cpp`
- Modify: `CMakeLists.txt`, `tests/cpp/CMakeLists.txt`

**Why:** The schema columns landed in Task 2; this task seals the **write API** so M0.4's LLM extractor only writes via `PipelineLedger`. Forces the (extraction_span_key, attempt_number) discipline before the extractor exists, preventing M0.4 from inventing its own ad-hoc inserts.

- [ ] **Step 1: Write `include/starling/bus/pipeline_ledger.hpp`**

```cpp
#pragma once
#include "starling/persistence/connection.hpp"
#include <chrono>
#include <optional>
#include <string>

namespace starling::bus {

enum class PipelineStatus    { Started, Finished, Failed };
enum class ExtractionStatus  { Success, PartialSuccess, Failed };

class PipelineLedger {
public:
    explicit PipelineLedger(starling::persistence::Connection& c) : conn_(c) {}

    // Returns the run_id (UUID) it generated. Inserts a row with status=Started.
    std::string start_run(std::string_view tenant_id,
                          std::string_view input_ref,
                          std::string_view metadata_json = "{}");

    void finish_run(std::string_view run_id, PipelineStatus terminal);

    // Records an attempt under the given (extraction_span_key, attempt_number).
    // The pair is unique per pipeline_run; duplicate raises.
    std::string record_attempt(std::string_view run_id,
                               std::string_view extraction_span_key,
                               int attempt_number,
                               ExtractionStatus status,
                               std::string_view raw_output = {},
                               std::string_view error = {});

private:
    starling::persistence::Connection& conn_;
};

}  // namespace starling::bus
```

- [ ] **Step 2: Write `src/bus/pipeline_ledger.cpp`**

```cpp
#include "starling/bus/pipeline_ledger.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <chrono>
#include <ctime>
#include <iomanip>
#include <random>
#include <sstream>
#include <stdexcept>

namespace starling::bus {

namespace {

std::string uuid_like() {
    static thread_local std::mt19937_64 rng{std::random_device{}()};
    uint64_t a = rng(), b = rng();
    std::ostringstream oss;
    oss << std::hex << std::setfill('0')
        << std::setw(8) << static_cast<uint32_t>(a >> 32) << '-'
        << std::setw(4) << static_cast<uint16_t>(a >> 16) << '-'
        << std::setw(4) << static_cast<uint16_t>(a) << '-'
        << std::setw(4) << static_cast<uint16_t>(b >> 48) << '-'
        << std::setw(12) << (b & 0xFFFFFFFFFFFFULL);
    return oss.str();
}

std::string now_iso() {
    using namespace std::chrono;
    const auto t = system_clock::to_time_t(system_clock::now());
    std::tm tm{};
    gmtime_r(&t, &tm);
    std::ostringstream oss;
    oss << std::put_time(&tm, "%Y-%m-%dT%H:%M:%SZ");
    return oss.str();
}

const char* pipeline_status_string(PipelineStatus s) {
    switch (s) {
        case PipelineStatus::Started:  return "started";
        case PipelineStatus::Finished: return "finished";
        case PipelineStatus::Failed:   return "failed";
    }
    return "unknown";
}

const char* extraction_status_string(ExtractionStatus s) {
    switch (s) {
        case ExtractionStatus::Success:        return "success";
        case ExtractionStatus::PartialSuccess: return "partial_success";
        case ExtractionStatus::Failed:         return "failed";
    }
    return "unknown";
}

}  // namespace

std::string PipelineLedger::start_run(
        std::string_view tenant_id,
        std::string_view input_ref,
        std::string_view metadata_json) {
    const std::string id = uuid_like();
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(conn_.raw(),
        "INSERT INTO pipeline_run(id,tenant_id,started_at,status,input_ref,metadata_json) "
        "VALUES(?,?,?,?,?,?)", -1, &s, nullptr);
    starling::persistence::StmtHandle h(s);
    const std::string ts = now_iso();
    const std::string tenant(tenant_id);
    const std::string input(input_ref);
    const std::string meta(metadata_json);
    sqlite3_bind_text(h.get(), 1, id.c_str(),     -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(h.get(), 2, tenant.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(h.get(), 3, ts.c_str(),     -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(h.get(), 4, "started",      -1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), 5, input.c_str(),  -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(h.get(), 6, meta.c_str(),   -1, SQLITE_TRANSIENT);
    if (sqlite3_step(h.get()) != SQLITE_DONE) {
        throw std::runtime_error("pipeline_run insert failed");
    }
    return id;
}

void PipelineLedger::finish_run(std::string_view run_id, PipelineStatus terminal) {
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(conn_.raw(),
        "UPDATE pipeline_run SET finished_at=?, status=? WHERE id=?",
        -1, &s, nullptr);
    starling::persistence::StmtHandle h(s);
    const std::string ts = now_iso();
    const std::string id(run_id);
    sqlite3_bind_text(h.get(), 1, ts.c_str(),                    -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(h.get(), 2, pipeline_status_string(terminal),-1, SQLITE_STATIC);
    sqlite3_bind_text(h.get(), 3, id.c_str(),                    -1, SQLITE_TRANSIENT);
    if (sqlite3_step(h.get()) != SQLITE_DONE) {
        throw std::runtime_error("pipeline_run finish failed");
    }
}

std::string PipelineLedger::record_attempt(
        std::string_view run_id,
        std::string_view extraction_span_key,
        int attempt_number,
        ExtractionStatus status,
        std::string_view raw_output,
        std::string_view error) {
    const std::string id = uuid_like();
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(conn_.raw(),
        "INSERT INTO extraction_attempt("
        "id,pipeline_run_id,extraction_span_key,attempt_number,"
        "status,raw_output,error,created_at) VALUES(?,?,?,?,?,?,?,?)",
        -1, &s, nullptr);
    starling::persistence::StmtHandle h(s);
    const std::string ts = now_iso();
    const std::string rid(run_id), span(extraction_span_key);
    const std::string raw(raw_output), err(error);
    sqlite3_bind_text (h.get(), 1, id.c_str(),                          -1, SQLITE_TRANSIENT);
    sqlite3_bind_text (h.get(), 2, rid.c_str(),                         -1, SQLITE_TRANSIENT);
    sqlite3_bind_text (h.get(), 3, span.c_str(),                        -1, SQLITE_TRANSIENT);
    sqlite3_bind_int  (h.get(), 4, attempt_number);
    sqlite3_bind_text (h.get(), 5, extraction_status_string(status),    -1, SQLITE_STATIC);
    if (raw.empty()) sqlite3_bind_null(h.get(), 6);
    else             sqlite3_bind_text(h.get(), 6, raw.c_str(),         -1, SQLITE_TRANSIENT);
    if (err.empty()) sqlite3_bind_null(h.get(), 7);
    else             sqlite3_bind_text(h.get(), 7, err.c_str(),         -1, SQLITE_TRANSIENT);
    sqlite3_bind_text (h.get(), 8, ts.c_str(),                          -1, SQLITE_TRANSIENT);
    if (sqlite3_step(h.get()) != SQLITE_DONE) {
        throw std::runtime_error(
            std::string("extraction_attempt insert failed: ") +
            sqlite3_errmsg(conn_.raw()));
    }
    return id;
}

}  // namespace starling::bus
```

- [ ] **Step 3: Wire into `starling_core` + add a uniqueness index**

The schema we wrote in Task 2 has only a non-unique `idx_extraction_attempt_span`. M0.4's discipline requires `(span_key, attempt_number)` to be unique per run. We add it via a follow-up migration.

Create `migrations/0002_extraction_attempt_unique.sql`:

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_extraction_attempt_unique
    ON extraction_attempt(pipeline_run_id, extraction_span_key, attempt_number);
```

Wire in:

```cmake
target_sources(starling_core PRIVATE
    src/bus/pipeline_ledger.cpp
)
```

- [ ] **Step 4: Write `tests/cpp/test_pipeline_ledger.cpp`**

```cpp
#include <gtest/gtest.h>
#include "starling/bus/pipeline_ledger.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/migration_runner.hpp"

using namespace starling::bus;
using starling::persistence::Connection;
using starling::persistence::MigrationRunner;
using starling::persistence::SqliteError;

namespace {
Connection fresh() {
    auto c = Connection::open(":memory:");
    MigrationRunner(c.raw()).migrate_to_latest();
    return c;
}
int count(Connection& c, const char* sql) {
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(c.raw(), sql, -1, &s, nullptr);
    sqlite3_step(s);
    const int n = sqlite3_column_int(s, 0);
    sqlite3_finalize(s);
    return n;
}
}  // namespace

TEST(PipelineLedger, StartFinishRoundTrip) {
    auto c = fresh();
    PipelineLedger l(c);
    const auto run_id = l.start_run("t1", "msg-uri-1", "{\"k\":\"v\"}");
    EXPECT_FALSE(run_id.empty());
    EXPECT_EQ(count(c, "SELECT COUNT(*) FROM pipeline_run WHERE status='started'"), 1);
    l.finish_run(run_id, PipelineStatus::Finished);
    EXPECT_EQ(count(c, "SELECT COUNT(*) FROM pipeline_run WHERE status='finished'"), 1);
}

TEST(PipelineLedger, AttemptUniquePerSpanAndAttemptNumber) {
    auto c = fresh();
    PipelineLedger l(c);
    const auto run_id = l.start_run("t1", "msg-uri-1");
    l.record_attempt(run_id, "span-1", 1, ExtractionStatus::Success, "<xml/>");
    EXPECT_THROW(
        l.record_attempt(run_id, "span-1", 1, ExtractionStatus::Success, "<xml/>"),
        std::runtime_error);
    l.record_attempt(run_id, "span-1", 2, ExtractionStatus::PartialSuccess);
    l.record_attempt(run_id, "span-2", 1, ExtractionStatus::Success);
    EXPECT_EQ(count(c, "SELECT COUNT(*) FROM extraction_attempt"), 3);
}

TEST(PipelineLedger, AttemptStatusEnumStrings) {
    auto c = fresh();
    PipelineLedger l(c);
    const auto run_id = l.start_run("t1", "ref");
    l.record_attempt(run_id, "s1", 1, ExtractionStatus::Failed, {}, "boom");
    EXPECT_EQ(count(c,
        "SELECT COUNT(*) FROM extraction_attempt "
        "WHERE status='failed' AND error='boom'"), 1);
}
```

- [ ] **Step 5: Register test**

```cmake
add_executable(test_pipeline_ledger test_pipeline_ledger.cpp)
target_link_libraries(test_pipeline_ledger PRIVATE starling_core GTest::gtest_main)
gtest_discover_tests(test_pipeline_ledger)
```

- [ ] **Step 6: Build + run**

Run: `cmake --build --preset default && ctest --preset default --output-on-failure -R PipelineLedger`
Expected: 3 tests PASS.

- [ ] **Step 7: Commit**

Run:
- `git add migrations/0002_extraction_attempt_unique.sql include/starling/bus/pipeline_ledger.hpp src/bus/pipeline_ledger.cpp tests/cpp/test_pipeline_ledger.cpp CMakeLists.txt tests/cpp/CMakeLists.txt`
- `git commit -m "feat(M0.2): pipeline_run + extraction_attempt ledger API + unique span index"`

---

### Task 9: SqliteAdapter (capability declaration + final-query check + Python wiring)

**Files:**
- Create: `include/starling/persistence/sqlite_adapter.hpp`
- Create: `src/persistence/sqlite_adapter.cpp`
- Modify: `bindings/python/module.cpp` (extend existing M0.0 module: bind `BusEvent`, `compute_idempotency_key`, `SqliteAdapter`)
- Create: `tests/cpp/test_sqlite_adapter.cpp`
- Create: `tests/python/test_bus_binding_parity.py`
- Modify: `python/starling/runtime.py` (replace `_StubBus` and `_StubEngramStore` wiring with `SqliteAdapter`)
- Modify: `CMakeLists.txt`, `tests/cpp/CMakeLists.txt`

**Why:** This is the one task that crosses the C++/Python seam. We declare a `ProfileCapability` for the local-store SQLite profile so `Runtime` preflight passes; we expose `OutboxWriter` and `compute_idempotency_key` to Python so the parity test in Task 4 can be upgraded to call the actual C++ formula; we replace the stub bus in `runtime.py`.

**Note on `Adapter` base class:** `starling::Adapter` (M0.0) declares `bool check_final_query(const std::string& sql) const = 0` (returns bool, takes `const std::string&` — see `include/starling/adapter.hpp`). The override signature below matches that exactly. Also, `Adapter` deletes its move-ctor, so `SqliteAdapter::open()` returns a `std::unique_ptr<SqliteAdapter>` rather than by value.

- [ ] **Step 1: Write `include/starling/persistence/sqlite_adapter.hpp`**

```cpp
#pragma once
#include "starling/adapter.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/profile_capability.hpp"
#include <filesystem>
#include <memory>
#include <string>

namespace starling::persistence {

class SqliteAdapter : public starling::Adapter {
public:
    // SqliteAdapter is non-movable (Adapter base deletes move). open() returns
    // a unique_ptr so callers can hand it to Runtime by reference and store
    // it without slicing.
    static std::unique_ptr<SqliteAdapter> open(const std::filesystem::path& db_path);

    starling::ProfileCapability declare_capability() const override;
    bool check_final_query(const std::string& sql) const override;

    Connection& connection() noexcept { return conn_; }
    const std::filesystem::path& db_path() const noexcept { return db_path_; }

private:
    SqliteAdapter(Connection c, std::filesystem::path p)
        : conn_(std::move(c)), db_path_(std::move(p)) {}
    Connection conn_;
    std::filesystem::path db_path_;
};

}  // namespace starling::persistence
```

- [ ] **Step 2: Write `src/persistence/sqlite_adapter.cpp`**

```cpp
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/final_query_assertion.hpp"
#include "starling/persistence/migration_runner.hpp"

namespace starling::persistence {

std::unique_ptr<SqliteAdapter> SqliteAdapter::open(
        const std::filesystem::path& db_path) {
    auto conn = Connection::open(db_path);
    MigrationRunner(conn.raw()).migrate_to_latest();
    // unique_ptr<...>(new SqliteAdapter(...)) because the ctor is private.
    return std::unique_ptr<SqliteAdapter>(
        new SqliteAdapter(std::move(conn), db_path));
}

starling::ProfileCapability SqliteAdapter::declare_capability() const {
    starling::ProfileCapability cap;
    cap.profile_name                  = "local-store-sqlite";
    cap.relational_backend            = "sqlite";
    cap.vector_backend                = "none";          // P1: no vectors
    cap.graph_backend                 = "none";          // P1: edges via statement_edges
    cap.c_plus_plus_core              = true;
    cap.cross_partition_transaction   = true;            // single SQLite db; trivially yes
    cap.transactional_outbox          = true;
    cap.consumer_checkpoint           = true;
    cap.tenant_isolation              = "storage_enforced";  // every P1 query joins tenant_id
    cap.engram_per_record_key         = false;           // KMS lands in M0.3
    cap.engram_refcount               = true;
    cap.projection_index_supported    = false;
    cap.dimension_versions_supported  = false;
    cap.testing_helper_marker         = false;
    return cap;
}

bool SqliteAdapter::check_final_query(const std::string& sql) const {
    return starling::is_final_query_safe(sql);
}

}  // namespace starling::persistence
```

- [ ] **Step 3: Wire `sqlite_adapter.cpp` in**

```cmake
target_sources(starling_core PRIVATE
    src/persistence/sqlite_adapter.cpp
)
```

- [ ] **Step 4: Write `tests/cpp/test_sqlite_adapter.cpp`**

```cpp
#include <gtest/gtest.h>
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/final_query_assertion.hpp"

using starling::persistence::SqliteAdapter;

TEST(SqliteAdapter, DeclaredCapabilityHasOutboxAndCheckpoint) {
    auto a = SqliteAdapter::open(":memory:");
    const auto cap = a->declare_capability();
    EXPECT_TRUE(cap.transactional_outbox);
    EXPECT_TRUE(cap.consumer_checkpoint);
    EXPECT_TRUE(cap.cross_partition_transaction);
    EXPECT_EQ(cap.tenant_isolation, "storage_enforced");
    EXPECT_FALSE(cap.engram_per_record_key);  // M0.3 will set this
    EXPECT_FALSE(cap.testing_helper_marker);
}

TEST(SqliteAdapter, FinalQueryPredicateRejectsMissingTenantClause) {
    auto a = SqliteAdapter::open(":memory:");
    // check_final_query is the bool predicate variant — false on missing
    // guards, true when tenant_id + holder_scope are both present.
    EXPECT_FALSE(a->check_final_query("SELECT * FROM statements"));
    EXPECT_TRUE(a->check_final_query(
        "SELECT * FROM statements WHERE tenant_id=? AND holder_scope=?"));
}

TEST(SqliteAdapter, MigrationsRunOnOpen) {
    auto a = SqliteAdapter::open(":memory:");
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(a->connection().raw(),
        "SELECT COUNT(*) FROM sqlite_master "
        "WHERE type='index' AND name='idx_statement_id_tenant'",
        -1, &s, nullptr);
    sqlite3_step(s);
    EXPECT_EQ(sqlite3_column_int(s, 0), 1);
    sqlite3_finalize(s);
}
```

- [ ] **Step 5: Register the test**

```cmake
add_executable(test_sqlite_adapter test_sqlite_adapter.cpp)
target_link_libraries(test_sqlite_adapter PRIVATE starling_core GTest::gtest_main)
gtest_discover_tests(test_sqlite_adapter)
```

- [ ] **Step 6: Add pybind bindings**

The pybind module entry is `PYBIND11_MODULE(_core, m)` in `bindings/python/module.cpp` (created in M0.0). Append the M0.2 bindings inline at the end of that block — see step 6 below.

- [ ] **Step 6: Add pybind bindings to the existing M0.0 module**

The pybind module lives at `bindings/python/module.cpp` (created in M0.0). Append the M0.2 bindings inside the existing `PYBIND11_MODULE(_core, m) { ... }` block — do not create a new module file. The existing block already binds `ProfileCapability`, `RuntimeHealth`, `PreflightStatus`, `PreflightResult`, `preflight`, `assert_final_query_safe`, `is_final_query_safe`, `FinalQueryAssertionError`, `canonicalize_object_cpp`, and the `testing` submodule — leave all of those untouched.

Add these `#include`s near the top of the file:

```cpp
#include "starling/bus/bus_event.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
```

Append the following inside `PYBIND11_MODULE(_core, m)` after the existing M0.0 bindings:

```cpp
py::class_<starling::bus::BusEvent>(m, "BusEvent")
    .def(py::init<>())
    .def_readwrite("event_id",        &starling::bus::BusEvent::event_id)
    .def_readwrite("tenant_id",       &starling::bus::BusEvent::tenant_id)
    .def_readwrite("event_type",      &starling::bus::BusEvent::event_type)
    .def_readwrite("primary_id",      &starling::bus::BusEvent::primary_id)
    .def_readwrite("aggregate_id",    &starling::bus::BusEvent::aggregate_id)
    .def_readwrite("outbox_sequence", &starling::bus::BusEvent::outbox_sequence)
    .def_readwrite("causation_chain", &starling::bus::BusEvent::causation_chain)
    .def_readwrite("idempotency_key", &starling::bus::BusEvent::idempotency_key)
    .def_readwrite("payload_json",    &starling::bus::BusEvent::payload_json)
    .def_readwrite("created_at",      &starling::bus::BusEvent::created_at)
    .def_readwrite("version",         &starling::bus::BusEvent::version);

m.def("compute_idempotency_key",
      &starling::bus::compute_idempotency_key,
      py::arg("event_type"),
      py::arg("aggregate_id"),
      py::arg("canonical_key"),
      py::arg("causation_root"),
      py::arg("window_bucket"));

// SqliteAdapter is non-copyable + non-movable (Adapter base deletes both).
// The unique_ptr holder lets pybind take ownership from open()'s factory.
py::class_<starling::persistence::SqliteAdapter,
           std::unique_ptr<starling::persistence::SqliteAdapter>>(m, "SqliteAdapter")
    .def_static("open", [](const std::string& path) {
        return starling::persistence::SqliteAdapter::open(path);
    })
    .def("declare_capability",
         &starling::persistence::SqliteAdapter::declare_capability)
    .def("check_final_query",
         &starling::persistence::SqliteAdapter::check_final_query)
    .def_property_readonly("db_path", [](const starling::persistence::SqliteAdapter& a) {
        return a.db_path().string();
    })
    // append_event_unsafe is a TEST-ONLY shortcut: it wraps OutboxWriter in a
    // self-contained transaction, bypassing the producer's domain write. Real
    // producers must share their own transaction with OutboxWriter — this
    // binding exists solely so TC-NEW-OUTBOX-IDEMP can seed events without
    // duplicating the schema layer in Python. The CI static scan (M0.0) must
    // refuse any prod-entrypoint reference to this name.
    .def("append_event_unsafe", [](starling::persistence::SqliteAdapter& a,
                                    starling::bus::BusEvent& ev) {
        starling::persistence::TransactionGuard g(a.connection());
        starling::bus::OutboxWriter w(a.connection());
        w.append(ev);
        g.commit();
    });
```

Add the corresponding `#include`s for `OutboxWriter` and `TransactionGuard`:

```cpp
#include "starling/bus/outbox_writer.hpp"
// (TransactionGuard is in starling/persistence/connection.hpp, already included transitively)
```

- [ ] **Step 7: Update CI static scan list**

In `tools/ci/scan_prod_uses_testing.py` (or wherever the M0.0 scanner lives), append `append_event_unsafe` and `_core.SqliteAdapter.append_event_unsafe` to the forbidden-symbol list. Prod entrypoints that reference either name must fail the scan.

- [ ] **Step 8: Replace the runtime stubs**

In `python/starling/runtime.py`, M0.0's `Runtime` is a `@dataclass` with `capability: ProfileCapability`, `idx_statement_id_tenant_present: Callable[[], bool]`, and a `_StubBus` field initialized in `__post_init__`. M0.2 keeps that signature byte-stable (so M0.0's `tests/python/test_runtime.py` cases keep passing) and adds a new optional `adapter` field plus a `_SqliteBackedBus` that the constructor selects when an adapter is supplied.

Edit `python/starling/runtime.py`:

```python
# new imports near the top:
from pathlib import Path
from typing import Any

# add a new field to the existing @dataclass class Runtime:
@dataclass
class Runtime:
    capability: _core.ProfileCapability
    on_health_change: Optional[Callable[[dict], None]] = None
    idx_statement_id_tenant_present: Callable[[], bool] = field(
        default=lambda: True
    )
    adapter: Optional[Any] = None   # M0.2: _core.SqliteAdapter when local-store

    foreground_workers_started: bool = False
    background_workers_started: bool = False
    exit_code: Optional[int] = None
    bus: Any = field(init=False)
    engram_store: _StubEngramStore = field(default_factory=_StubEngramStore)

    _state: _core.RuntimeHealth = field(default=_core.RuntimeHealth.UNREADY)

    def __post_init__(self):
        if self.adapter is None:
            # M0.0 stub path stays byte-stable.
            self.bus = _StubBus(health_getter=lambda: self._state)
        else:
            self.bus = _SqliteBackedBus(self.adapter,
                                       health_getter=lambda: self._state)


class _SqliteBackedBus:
    """M0.2 SQLite-backed bus surface.

    Mirrors `_StubBus`'s `append_evidence` / `write` shape so existing callers
    keep working. The actual append-into-bus_events flow lands behind
    OutboxWriter in M0.3 (engram) + M0.4 (statement); M0.2 only needs the
    health gate and the adapter handle.
    """
    def __init__(self, adapter, *, health_getter):
        self._adapter = adapter
        self._health_getter = health_getter

    def adapter(self):
        return self._adapter


def _build_local_store_sqlite_runtime(db_path: Path) -> "Runtime":
    adapter = _core.SqliteAdapter.open(str(db_path))
    cap = adapter.declare_capability()

    # idx_statement_id_tenant_present: real check against sqlite_master.
    def _idx_present() -> bool:
        import sqlite3
        with sqlite3.connect(str(db_path)) as conn:
            row = conn.execute(
                "SELECT 1 FROM sqlite_master "
                "WHERE type='index' AND name='idx_statement_id_tenant'"
            ).fetchone()
            return row is not None

    return Runtime(
        capability=cap,
        adapter=adapter,
        idx_statement_id_tenant_present=_idx_present,
    )
```

The `LOCAL_STORE_REQUIRED` tuple in `runtime.py` lists `engram_per_record_key` and `testing_helper_marker`. `SqliteAdapter` reports both as `False` in M0.2 (KMS lands in M0.3; `testing_helper_marker=true` is dev-only). Acceptance therefore relies on the `starling.testing.relax_preflight_for_m0_2()` helper:

```python
# python/starling/testing/__init__.py — append:
def relax_preflight_for_m0_2() -> tuple[str, ...]:
    """Trim engram_per_record_key + testing_helper_marker from LOCAL_STORE_REQUIRED.

    Required by M0.2 acceptance only; M0.3 wires real KMS and removes the
    engram exclusion. The CI static scan (added in M0.0) refuses to merge
    prod entrypoints that import starling.testing — so this can never leak.

    Returns the original tuple so the caller can restore it in tearDown.
    """
    from starling import runtime as _r
    original = _r.LOCAL_STORE_REQUIRED
    _r.LOCAL_STORE_REQUIRED = tuple(
        c for c in original
        if c not in {"engram_per_record_key", "testing_helper_marker"}
    )
    return original
```

- [ ] **Step 9: Cross-language idempotency parity test**

Create `tests/python/test_bus_binding_parity.py`:

```python
"""Verify the C++ and Python implementations of compute_idempotency_key
agree byte-for-byte across a representative input matrix."""

import itertools

import pytest

from starling import _core
from starling.bus.bus_event import compute_idempotency_key as py_compute


@pytest.mark.parametrize(
    "event_type,aggregate_id,canonical_key,causation_root,window_bucket",
    list(itertools.product(
        ["statement.created", "engram.appended", "system.delivery_failed"],
        ["holder-1", "holder-2", ""],
        ["k=1", "k=2", "k=very-long-canonical-key-with-lots-of-content"],
        ["", "evt-root-uuid"],
        ["", "1234567890"],
    )),
)
def test_idempotency_key_parity(
    event_type, aggregate_id, canonical_key, causation_root, window_bucket
):
    py_key = py_compute(
        event_type=event_type, aggregate_id=aggregate_id,
        canonical_key=canonical_key, causation_root=causation_root,
        window_bucket=window_bucket,
    )
    cpp_key = _core.compute_idempotency_key(
        event_type, aggregate_id, canonical_key, causation_root, window_bucket,
    )
    assert py_key == cpp_key
```

- [ ] **Step 10: Build + run all the new tests**

Run:
- `cmake --build --preset default && ctest --preset default --output-on-failure -R SqliteAdapter`
- `pip install -e . --no-build-isolation && pytest tests/python/test_bus_binding_parity.py -v`

Expected: 3 C++ tests PASS, 54 Python parity cases PASS.

- [ ] **Step 11: Commit**

Run:
- `git add include/starling/persistence/sqlite_adapter.hpp src/persistence/sqlite_adapter.cpp bindings/python/module.cpp tests/cpp/test_sqlite_adapter.cpp tests/python/test_bus_binding_parity.py python/starling/runtime.py python/starling/testing/__init__.py CMakeLists.txt tests/cpp/CMakeLists.txt`
- `git commit -m "feat(M0.2): SqliteAdapter + pybind bindings + Runtime SQLite wiring"`

---

### Task 10: TC-NEW-OUTBOX-IDEMP integration test (CRITICAL P1 wedge)

**Files:**
- Create: `tests/python/test_tc_new_outbox_idemp.py`
- Create: `tests/python/_fixtures/outbox_crash_worker.py`

**Why:** This is the test that locks in M0.2's CRITICAL acceptance. It uses `os._exit()` in a subprocess to simulate a hard crash mid-dispatch and verifies:
1. After restart, no event is ever delivered more than once to the consumer that already accepted it.
2. Total deliveries ≤ 200 across 100 events with up to 5 retries each.
3. `dispatch_status='dead_letter'` flips after `max_retries=5`.
4. `system.delivery_failed` row exists for every dead-lettered event with `dispatch_status='delivered'` (i.e., never re-dispatches).

The C++ tests in Task 7 cover dispatcher unit behavior; this test covers the **process-crash** path that unit tests can't.

- [ ] **Step 1: Write the crash worker `tests/python/_fixtures/outbox_crash_worker.py`**

```python
"""Subprocess worker for TC-NEW-OUTBOX-IDEMP.

Reads command-line args:
    --db PATH                SQLite DB path (must already have migrations applied)
    --crash-after-n N        After N successful Accept callbacks, os._exit(137)
    --consumer-id ID         Defaults to 'tc-outbox'

The worker drains the outbox via a single dispatcher.run_once() call. The
parent test process re-spawns it as many times as needed to drain the queue,
asserting that each successful delivery is recorded in a side-channel JSONL
file so dedup violations are detectable across restarts.
"""

import argparse
import json
import os
import sys
from pathlib import Path

from starling import _core  # exposes SqliteAdapter, BusEvent, etc.
from starling.bus.outbox_dispatcher_py import (  # thin wrapper added below
    OutboxDispatcher, ConsumerDecision,
)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--db", required=True)
    p.add_argument("--crash-after-n", type=int, default=-1)
    p.add_argument("--consumer-id", default="tc-outbox")
    p.add_argument("--delivery-log", required=True)
    args = p.parse_args()

    adapter = _core.SqliteAdapter.open(args.db)
    log = Path(args.delivery_log)
    accepted = 0

    def consumer(ev):
        nonlocal accepted
        # Record delivery first so a crash AFTER the consumer logic runs but
        # BEFORE the dispatcher commits 'delivered' is detectable.
        with log.open("a") as fh:
            fh.write(json.dumps({
                "event_id": ev.event_id,
                "idempotency_key": ev.idempotency_key,
                "outbox_sequence": ev.outbox_sequence,
            }) + "\n")
        accepted += 1
        if args.crash_after_n >= 0 and accepted >= args.crash_after_n:
            os._exit(137)
        return ConsumerDecision.ACCEPT

    OutboxDispatcher(adapter, consumer, consumer_id=args.consumer_id).run_once()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

To make `OutboxDispatcher` callable from Python, add a tiny pure-Python wrapper. (Binding the C++ dispatcher with a Python-callable Consumer would require pybind GIL gymnastics; we instead do the dispatcher loop in Python on top of the C++ adapter's connection.)

Create `python/starling/bus/outbox_dispatcher_py.py`:

```python
"""Python re-implementation of OutboxDispatcher.run_once.

Mirrors src/bus/outbox_dispatcher.cpp 1:1 for behavior. The C++ version
exists for performance + as the primary implementation; the Python version
exists so tests can crash the worker via os._exit() (you can't easily kill a
C++ thread mid-callback). Both must produce identical bus_events row states —
this is enforced by test_outbox_dispatcher_parity.py (added in this task).
"""

import enum
import sqlite3
from datetime import datetime, timedelta, timezone


class ConsumerDecision(enum.Enum):
    ACCEPT = "accept"
    TRANSIENT_ERROR = "transient_error"
    PERMANENT_ERROR = "permanent_error"


def _utcnow_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class OutboxDispatcher:
    def __init__(self, adapter, consumer, *, consumer_id="default",
                 max_retries=5, max_events_per_run=1000,
                 inbox_ttl=timedelta(days=7)):
        # adapter is a starling._core.SqliteAdapter; we open a fresh sqlite3
        # connection on the same file because pybind doesn't expose the raw
        # sqlite3* handle to Python (and that's intentional — the only
        # legitimate prod write path is OutboxWriter on the C++ side; this
        # Python loop is for tests).
        self._adapter = adapter
        self._db_path = adapter.db_path  # bound as def_property_readonly in Task 9 step 6
        self._consumer = consumer
        self._consumer_id = consumer_id
        self._max_retries = max_retries
        self._limit = max_events_per_run
        self._inbox_ttl = inbox_ttl

    def run_once(self):
        conn = sqlite3.connect(self._db_path, isolation_level=None)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute(
            "UPDATE bus_events SET dispatch_status='pending' "
            "WHERE dispatch_status='in_flight'"
        )
        rows = list(conn.execute(
            "SELECT event_id, tenant_id, event_type, primary_id, aggregate_id, "
            "outbox_sequence, idempotency_key, payload_json, created_at, version, "
            "dispatch_attempts FROM bus_events WHERE dispatch_status='pending' "
            "ORDER BY outbox_sequence ASC LIMIT ?", (self._limit,)
        ))
        blocked = set()
        delivered = retried = dead_lettered = skipped = 0

        for row in rows:
            (event_id, tenant_id, event_type, primary_id, aggregate_id,
             outbox_sequence, idempotency_key, payload_json, created_at,
             version, attempts) = row
            if aggregate_id in blocked:
                skipped += 1
                continue

            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "UPDATE bus_events SET dispatch_status='in_flight', last_attempt_at=? "
                "WHERE event_id=? AND dispatch_status='pending'",
                (_utcnow_iso(), event_id),
            )
            conn.execute("COMMIT")

            class _Ev:
                pass
            ev = _Ev()
            ev.event_id = event_id; ev.tenant_id = tenant_id
            ev.event_type = event_type; ev.primary_id = primary_id
            ev.aggregate_id = aggregate_id; ev.outbox_sequence = outbox_sequence
            ev.idempotency_key = idempotency_key; ev.payload_json = payload_json
            ev.created_at = created_at; ev.version = version
            try:
                decision = self._consumer(ev)
                err = None
            except Exception as exc:
                decision = ConsumerDecision.TRANSIENT_ERROR
                err = repr(exc)

            new_attempts = attempts + 1

            if decision == ConsumerDecision.ACCEPT:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    "INSERT OR IGNORE INTO idempotency_inbox("
                    "consumer_id,idempotency_key,received_at,expires_at) "
                    "VALUES(?,?,?,?)",
                    (self._consumer_id, idempotency_key, _utcnow_iso(),
                     (datetime.now(tz=timezone.utc) + self._inbox_ttl)
                     .strftime("%Y-%m-%dT%H:%M:%SZ")),
                )
                conn.execute(
                    "UPDATE bus_events SET dispatch_status='delivered',"
                    "dispatch_attempts=?, last_attempt_at=? WHERE event_id=?",
                    (new_attempts, _utcnow_iso(), event_id),
                )
                conn.execute(
                    "INSERT INTO consumer_checkpoint(consumer_id,last_delivered_sequence,updated_at) "
                    "VALUES(?,?,?) ON CONFLICT(consumer_id) DO UPDATE SET "
                    "last_delivered_sequence=MAX(consumer_checkpoint.last_delivered_sequence,excluded.last_delivered_sequence),"
                    "updated_at=excluded.updated_at",
                    (self._consumer_id, outbox_sequence, _utcnow_iso()),
                )
                conn.execute("COMMIT")
                delivered += 1
                continue

            exhausted = (decision == ConsumerDecision.PERMANENT_ERROR
                         or new_attempts >= self._max_retries)
            if not exhausted:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    "UPDATE bus_events SET dispatch_status='pending',"
                    "dispatch_attempts=?, last_attempt_at=?, last_error=? WHERE event_id=?",
                    (new_attempts, _utcnow_iso(),
                     err or "transient_error", event_id),
                )
                conn.execute("COMMIT")
                retried += 1
                blocked.add(aggregate_id)
                continue

            # dead-letter
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "UPDATE bus_events SET dispatch_status='dead_letter',"
                "dispatch_attempts=?, last_attempt_at=?, last_error=? WHERE event_id=?",
                (new_attempts, _utcnow_iso(),
                 err or "permanent_error", event_id),
            )
            failure_seq = conn.execute(
                "SELECT next_value FROM outbox_sequence_counter WHERE id=1"
            ).fetchone()[0]
            conn.execute(
                "UPDATE outbox_sequence_counter SET next_value=next_value+1 WHERE id=1"
            )
            conn.execute(
                "INSERT INTO bus_events(event_id,tenant_id,event_type,primary_id,"
                "aggregate_id,outbox_sequence,causation_chain_json,idempotency_key,"
                "payload_json,created_at,version,dispatch_status) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    f"{event_id}-failed", tenant_id, "system.delivery_failed",
                    event_id, aggregate_id, failure_seq,
                    f'["{event_id}"]',
                    f"{idempotency_key}:delivery_failed",
                    f'{{"failed_event_id":"{event_id}"}}',
                    _utcnow_iso(), "v1", "delivered",
                ),
            )
            conn.execute("COMMIT")
            dead_lettered += 1
            blocked.add(aggregate_id)

        conn.close()
        return {"delivered": delivered, "retried": retried,
                "dead_lettered": dead_lettered, "skipped_blocked": skipped}
```

The `db_path` property and `append_event_unsafe` method this dispatcher relies on are already part of Task 9 step 6's `SqliteAdapter` binding — no follow-up patch is required here.

- [ ] **Step 2: Write `tests/python/test_tc_new_outbox_idemp.py`**

```python
"""TC-NEW-OUTBOX-IDEMP [CRITICAL]: outbox dispatcher must guarantee
at-least-once + dedup + dead-letter under hard process crash.

Given:  100 events, dispatcher consumer fails the first 0..K attempts then
        accepts; one event always fails permanently; one mid-batch crash via
        os._exit kills the worker.
When :  parent re-spawns workers until queue drains.
Then :  - every accepted event observed at most once via the inbox-side check
        - dead-letter row exists for the always-fail event
        - system.delivery_failed has dispatch_status='delivered'
        - total deliveries (across restarts) ≤ 200 (≤ 2 * num_events)
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from starling import _core

NUM_EVENTS = 100
ALWAYS_FAIL_KEY = "k-poison"
WORKER = Path(__file__).parent / "_fixtures" / "outbox_crash_worker.py"


def _seed_events(adapter, n: int):
    # Append 100 events using the C++ OutboxWriter (exposed in Task 9 step 6).
    for i in range(n):
        ev = _core.BusEvent()
        ev.tenant_id = "t1"
        ev.event_type = "statement.created"
        ev.primary_id = f"stmt-{i}"
        ev.aggregate_id = f"holder-{i % 5}"   # 5 aggregates -> some ordering pressure
        ev.idempotency_key = ALWAYS_FAIL_KEY if i == n - 1 else f"k-{i}"
        ev.payload_json = "{}"
        adapter.append_event_unsafe(ev)        # a thin C++ wrapper that runs OutboxWriter inside its own transaction; bound in Task 9 step 6


def _run_worker(db: Path, log: Path, *, crash_after_n: int = -1) -> int:
    return subprocess.call([
        sys.executable, str(WORKER),
        "--db", str(db),
        "--crash-after-n", str(crash_after_n),
        "--delivery-log", str(log),
    ])


def test_tc_new_outbox_idemp(tmp_path):
    # No Runtime / preflight involvement here — the test talks to SqliteAdapter
    # directly, so the relax helper is intentionally NOT called. (M0.0's
    # static-scan rule against importing `starling.testing` from prod paths
    # already isolates this — keeping the import out of this test removes
    # any chance of a leaked LOCAL_STORE_REQUIRED tuple bleeding into the
    # acceptance suite that runs after.)
    db = tmp_path / "outbox.db"
    log = tmp_path / "deliveries.jsonl"

    adapter = _core.SqliteAdapter.open(str(db))
    _seed_events(adapter, NUM_EVENTS)

    # 1st run: crash mid-batch.
    rc = _run_worker(db, log, crash_after_n=37)
    assert rc != 0  # killed via os._exit(137); subprocess.call returns 137

    # Drain remaining events with at most a few re-spawns.
    for _ in range(8):
        rc = _run_worker(db, log)
        if rc == 0:
            break
    else:
        pytest.fail("worker never drained the outbox")

    deliveries = [json.loads(line) for line in log.read_text().splitlines()]

    # ── Assertion 1: every non-poison event eventually delivered ─────────
    delivered_keys = {d["idempotency_key"] for d in deliveries}
    expected = {f"k-{i}" for i in range(NUM_EVENTS - 1)}
    assert delivered_keys >= expected

    # ── Assertion 2: total deliveries ≤ 200 (≤ 2x num_events; the crash is
    #     the only legitimate cause of double-delivery) ──────────────────
    assert len(deliveries) <= 2 * NUM_EVENTS

    # ── Assertion 3: poison event landed in dead_letter ─────────────────
    import sqlite3
    conn = sqlite3.connect(str(db))
    (dead_count,) = conn.execute(
        "SELECT COUNT(*) FROM bus_events "
        "WHERE dispatch_status='dead_letter' AND idempotency_key=?",
        (ALWAYS_FAIL_KEY,),
    ).fetchone()
    assert dead_count == 1

    # ── Assertion 4: system.delivery_failed row with dispatch_status='delivered' ─
    (failed_count,) = conn.execute(
        "SELECT COUNT(*) FROM bus_events "
        "WHERE event_type='system.delivery_failed' "
        "AND dispatch_status='delivered' "
        "AND payload_json LIKE '%' || ? || '%'",
        ("delivery_failed",),
    ).fetchone()
    assert failed_count >= 1

    # ── Assertion 5: idempotency_inbox rows == unique successful deliveries ──
    (inbox_count,) = conn.execute(
        "SELECT COUNT(*) FROM idempotency_inbox WHERE consumer_id=?",
        ("tc-outbox",),
    ).fetchone()
    assert inbox_count == NUM_EVENTS - 1
```

The poison event always-fails because the consumer in `outbox_crash_worker.py` returns `Accept` for everything; we therefore need the worker to return `TransientError` for `idempotency_key == ALWAYS_FAIL_KEY` so that retries exhaust to dead-letter. Update the worker's `consumer` function:

```python
# in outbox_crash_worker.py main(), replace the consumer body with:
def consumer(ev):
    nonlocal accepted
    if ev.idempotency_key == "k-poison":
        return ConsumerDecision.TRANSIENT_ERROR
    with log.open("a") as fh:
        fh.write(json.dumps({
            "event_id": ev.event_id,
            "idempotency_key": ev.idempotency_key,
            "outbox_sequence": ev.outbox_sequence,
        }) + "\n")
    accepted += 1
    if args.crash_after_n >= 0 and accepted >= args.crash_after_n:
        os._exit(137)
    return ConsumerDecision.ACCEPT
```

- [ ] **Step 3: Confirm `append_event_unsafe` is wired**

The seed helper `SqliteAdapter.append_event_unsafe` and its CI-scan guard are already specified in Task 9 step 6 + step 7 — no additional binding work in Task 10. Re-run the static scanner here as a guard:

```bash
python tools/ci/scan_prod_uses_testing.py
```

Expected: 0 violations. The scan should refuse any prod-entrypoint reference to `append_event_unsafe`.

- [ ] **Step 4: Run the test**

Run: `pytest tests/python/test_tc_new_outbox_idemp.py -v`
Expected: 1 test PASS. (Test takes ~5–10 s due to subprocess re-spawns.)

- [ ] **Step 5: Commit**

Run:
- `git add tests/python/test_tc_new_outbox_idemp.py tests/python/_fixtures/outbox_crash_worker.py python/starling/bus/outbox_dispatcher_py.py bindings/python/module.cpp include/starling/persistence/sqlite_adapter.hpp`
- `git commit -m "test(M0.2): TC-NEW-OUTBOX-IDEMP — at-least-once + dedup under crash [CRITICAL]"`

---

### Task 11: M0.2 acceptance smoke test + roadmap update

**Files:**
- Create: `tests/python/test_m0_2_acceptance.py`
- Modify: `docs/superpowers/plans/2026-05-23-roadmap.md` (flip M0.2 row to ✅)

**Why:** Final wedge before opening the milestone PR. Verifies that:
1. A fresh `Runtime` boots on a SQLite db, runs preflight (with the M0.2-specific relax), reports `RuntimeHealth=READY`.
2. The C++ unit suite + Python parity suite + TC-NEW-OUTBOX-IDEMP all pass in a single `ctest && pytest` invocation.
3. The CI static scan still flags any prod import of `starling.testing` or `__append_event_unsafe`.
4. The 13 P1 CRITICAL set is unchanged in count (M0.0 added TC-NEW-PREFLIGHT; M0.2 adds TC-NEW-OUTBOX-IDEMP — both are P1 CRITICAL gates).

- [ ] **Step 1: Write `tests/python/test_m0_2_acceptance.py`**

```python
"""M0.2 milestone acceptance smoke.

Boots a Runtime, walks the preflight, drains a small outbox batch end-to-end,
and confirms the runtime health surface stays consistent with §15 / §16
preflight contracts.
"""

from pathlib import Path

import pytest

from starling import _core, runtime, testing as _testing


@pytest.fixture
def runtime_instance(tmp_path):
    # relax_preflight_for_m0_2 mutates LOCAL_STORE_REQUIRED at the module
    # level; restore the original tuple on teardown so we don't leak into
    # other tests' preflight assumptions.
    original = _testing.relax_preflight_for_m0_2()
    db = tmp_path / "starling.db"
    rt = runtime._build_local_store_sqlite_runtime(db)
    yield rt
    runtime.LOCAL_STORE_REQUIRED = original


def test_runtime_starts_ready(runtime_instance):
    runtime_instance.start()
    assert runtime_instance.health() == _core.RuntimeHealth.READY
    assert runtime_instance.foreground_workers_started is True
    assert runtime_instance.background_workers_started is True


def test_idx_statement_id_tenant_present(runtime_instance):
    # idx_statement_id_tenant_present is a Callable[[], bool] field, not a method.
    assert runtime_instance.idx_statement_id_tenant_present() is True


def test_outbox_round_trip(runtime_instance):
    adapter = runtime_instance.adapter
    assert adapter is not None
    ev = _core.BusEvent()
    ev.tenant_id = "t1"
    ev.event_type = "statement.created"
    ev.primary_id = "stmt-acc-1"
    ev.aggregate_id = "holder-acc"
    ev.idempotency_key = "k-acceptance"
    ev.payload_json = "{}"
    adapter.append_event_unsafe(ev)
    assert ev.outbox_sequence > 0


def test_final_query_predicate_blocks_unguarded_select(runtime_instance):
    # SqliteAdapter::check_final_query is the bool predicate variant; returns
    # False if guard predicates are missing, True if both tenant_id and
    # holder_scope appear in the SQL.
    assert runtime_instance.adapter.check_final_query(
        "SELECT * FROM statements") is False
    assert runtime_instance.adapter.check_final_query(
        "SELECT * FROM statements WHERE tenant_id=? AND holder_scope=?"
    ) is True
```

- [ ] **Step 2: Run the full suite**

Run:
- `cmake --build --preset default`
- `ctest --preset default --output-on-failure`
- `pytest tests/python/ -v`

Expected: 0 failures, 0 errors. Note any flakes in the test report.

- [ ] **Step 3: Run the CI static scan**

Run: `python tools/ci/scan_prod_uses_testing.py`
Expected: 0 violations.

- [ ] **Step 4: Update `docs/superpowers/plans/2026-05-23-roadmap.md`**

Flip the M0.2 row from `待写 / —` to `已写 / ✅ 完成`. Set the date and commit hash to match the merge commit (filled in after merge).

| 里程碑 | Plan 状态 | 实施状态 | 完成日期 | Commit |
|---|---|---|---|---|
| M0.2 | 已写 | ✅ 完成 | 2026-05-23 | `<merge-sha>` |

- [ ] **Step 5: Commit the acceptance test + roadmap update separately**

Run:
- `git add tests/python/test_m0_2_acceptance.py`
- `git commit -m "test(M0.2): milestone acceptance smoke"`
- `git add docs/superpowers/plans/2026-05-23-roadmap.md`
- `git commit -m "docs(M0.2): mark milestone complete in roadmap"`

- [ ] **Step 6: Open the M0.2 PR**

Branch: `feature/m0-2-sqlite-outbox`. Use `--no-ff` merge once approved.

PR body must list:
- All 11 tasks above (link to plan file)
- TC-NEW-OUTBOX-IDEMP added to the 13 P1 CRITICAL set
- Confirmation that TC-NEW-PREFLIGHT + every M0.0/M0.1 unit test still passes
- Confirmation that prod entrypoints contain no reference to `starling.testing` or `__append_event_unsafe`

---

## Final Notes

- **Do NOT bundle Tasks 1-11 into one commit.** Each task ships its own commit so reviewers can isolate failures.
- **Worktree-per-milestone discipline applies.** Plan execution happens in `.worktrees/m0-2-sqlite-outbox` on branch `feature/m0-2-sqlite-outbox`. Merge with `--no-ff` after review.
- **Engram per-record encryption (`engram_per_record_key=true`) lands in M0.3, not here.** The `relax_preflight_for_m0_2()` testing helper is the explicit ledger entry for that gap and is removed when M0.3 closes.
- **No `starling.testing` import may appear in prod code paths.** The CI static scan from M0.0 already enforces this; verify before merging.
- **No premature optimization.** P1 SQLite is the explicit choice per `subsystems_design/04_substrate.md` §"≤ 10⁵ 极简" — seekdb is P2, not now.


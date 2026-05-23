# M0.3 Bus.append_evidence + EngramStore Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the P1 evidence write path: `Bus.append_evidence` as the only ingress for raw payloads, `EngramStore` that persists Engrams atomically with the matching `evidence.appended` outbox event, the `IngestPolicyResolver` that defaults `system_internal / observer_agent / replay_output` to `NO_STORE` (self-pollution guard), source-level idempotency on `(adapter_name, source_item_id, source_version, chunk_index)`, content_hash determinism over `declared_transformations`, and a `relax_preflight_for_m0_3()` helper that keeps the M0.3 acceptance smoke green while M0.4 still owes the per-record AES key + `engram_per_record_key` capability flip.

**Architecture:** EngramStore is a thin C++ class layered on the existing `SqliteAdapter` (M0.2). Its `put` and `get` run inside a `TransactionGuard` opened by `Bus::append_evidence`, which is itself a new method on a new `Bus` C++ class that owns the OutboxWriter (M0.2) and the EvidenceValidator (M0.3). EvidenceValidator is the only place where `IngestPolicyResolver`, source idempotency lookup, and `declared_transformations` checks live; the validator decides BEFORE EngramStore.put whether to short-circuit to `NO_STORE` (audit-only outbox row, no `engrams` row, no `evidence.appended` business event), to return an existing `EngramRef` (idempotent re-ingest), or to proceed. The transaction always commits exactly one outbox row (either `evidence.appended` or `evidence.no_store_audit`), keeping the at-least-once dispatcher contract intact. Per-record encryption (AES-256-GCM + KMS) is **out of scope for M0.3** — `key_ref` is `NULL` and `content_ciphertext` stores the raw payload bytes (the column is BLOB-typed; M0.3 ships an "inline plaintext" KMS adapter named `null_kms` so M0.4 can swap in a real KMS without rewriting the call site). Crypto-erasure, redacted-retain replacement, and the `evidence.erased` reverse-propagation cascade are likewise deferred — M0.3 only writes `retention_mode` as the producer declared it and surfaces it on `EngramRef`. The §3.1 acceptance branch we deliver is "self-pollution guard rejects RetrievalReceipt-style replay input," which is one of the §15.3.2 P1 non-CRITICAL retentions.

**Tech Stack:**
- C++20: `Bus`, `EngramStore`, `EvidenceValidator`, `IngestPolicyResolver`, `null_kms` adapter (header-only), `Engram` POD struct mirroring `python/starling/schema/engram.py`. RAII via existing `TransactionGuard` from `include/starling/persistence/connection.hpp`.
- SQLite 3.46+ via existing `SqliteAdapter` — M0.3 adds migration `0003_engram_store_columns.sql` that extends the M0.2 `engrams` table with `adapter_name`, `adapter_version`, `source_item_id`, `source_version`, `declared_transformations_json`, `byte_preserving`, `redacted_content`, `key_ref`, `audit_trail_json`, `chunk_index`, plus a UNIQUE index on `(tenant_id, adapter_name, source_item_id, source_version, chunk_index)` for source idempotency. M0.2 already provisioned `id`, `tenant_id`, `content_hash`, `source_kind`, `ingest_policy`, `ingest_mode`, `privacy_class`, `retention_mode`, `refcount`, `payload_uri`, `payload_inline`, `created_at`, `erased_at` — those rows are reused.
- pybind11 bindings: extend the existing `_core` module with `EngramInput`, `EngramRef`, `IngestPolicyResolver`, `EvidenceValidator`, `EngramStore`, `Bus.append_evidence`. The Python wrapper class `starling.bus.Bus` (new, not the M0.2 dispatcher) wraps the binding and is what tests + M0.4 extractor call.
- Python: `starling.evidence` package with `EngramInput` dataclass + builder helpers (`for_user_input`, `for_external_doc`, `for_system_internal`, etc.), and a parity test for the C++ resolver.
- Crypto: continue using the consolidated `starling::crypto::sha256_hex` (M0.1). content_hash is `sha256_hex(canonicalize_engram_payload(...))` where the canonical form includes payload bytes + `declared_transformations` (sorted, deduped, joined with `\x1f`) — this is the §3.7 invariant "different normalization pipelines on identical bytes produce different hashes."
- Tests: GoogleTest for C++ unit tests (resolver, validator, EngramStore put/get, Bus transaction atomicity), pytest for Python parity + acceptance smoke + the §15.3.2 self-pollution non-CRITICAL retention test.

---

## Source Material Locked

- `docs/design/system_design.md` §3.7 (lines 1075-1184) Engram schema, SourceKind, IngestPolicy, retention_mode lifecycle, content_hash formula, declared_transformations rule
- `docs/design/system_design.md` §15.2 (lines 1685-1712) M0.3 row + dependency table — `EngramStore + retention_mode + ingest_policy + 自污染防护`
- `docs/design/system_design.md` §15.3.1 (lines 1730-1756) — confirms M0.3 has NO new CRITICAL test of its own; M0.3 is foundation for §15.3.2 retentions
- `docs/design/system_design.md` §15.3.2 (line 1778) — P1 non-CRITICAL: `自污染防护：source_kind=system_internal 默认 NO_STORE，不得产生用户画像 Statement`. M0.3 owns the **resolver + audit-event half**; M0.4 / M0.6 own the "no Statement materializes" half.
- `docs/design/subsystems_design/06_engramstore.md` (full file) — `append_evidence` flow (lines 26-52), retention_mode state machine (lines 70-99), Engram dataclass (lines 168-210), EngramRetentionMode / SourceKind / IngestPolicy enums (lines 169-187)
- `docs/design/subsystems_design/05_bus.md` lines 4-71 (Bus responsibilities + the self-pollution guard rule on line 65), lines 340-400 (BusEvent envelope + `evidence.appended` event), lines 270-275 (causation_parent rule)
- M0.2 wired surface (preserved as-is): `OutboxWriter::append`, `BusEvent`, `compute_idempotency_key`, `compute_window_bucket`, `SqliteAdapter`, `TransactionGuard`, `MigrationRunner`

**P1 simplifications (locked here, not in design doc):**
1. **No KMS / per-record key**. `key_ref` is `NULL`. `content_ciphertext` column stores raw payload bytes; the column type is BLOB so a future migration to real ciphertext doesn't change shape. The `null_kms` adapter is a single-file header (`include/starling/crypto/null_kms.hpp`) that just returns the input unchanged. M0.4 OR a later M0.x can swap in real AES-256-GCM by replacing the KMS adapter — the call site in EngramStore stays the same. **`engram_per_record_key` ProfileCapability stays `false`; `relax_preflight_for_m0_3()` continues to strip it from `LOCAL_STORE_REQUIRED`** (same as M0.2).
2. **No crypto-erasure cascade**. M0.3 writes `retention_mode` as declared (any of the four enum values) and stores it on `EngramRef`. `legal_hold / audit_retain / redacted_retain / crypto_erasure` are all just persisted strings — no state transitions, no `evidence.erased` event, no Statement-side propagation. That's M0.x post-M0.7.
3. **No `segment_map`**. P1 is chunk-level only; `segment_map` column is not added to the schema (the design doc explicitly marks it P3). `chunk_index` is a column.
4. **`byte_preserving` is producer-declared, not conformance-tested**. P1 trusts the adapter's claim; the §3.7 "byte_preserving requires conformance test" rule is enforced at adapter-conformance time, not inside EvidenceValidator.
5. **`refcount` stays at the M0.2 default of 0 and is not touched by M0.3**. The `evidence_refcount` ProfileCapability stays `false`. Refcount maintenance lands when `Statement.evidence` first writes lookups in M0.5.
6. **Source idempotency is enforced via SQL `UNIQUE` index**, not application-level dedup. The validator's "已存在 → 返回已有 EngramRef" path is implemented as a pre-INSERT `SELECT` on the unique tuple — `INSERT OR IGNORE` would silently overwrite the `id` UUID even when the row exists, and we want the existing `EngramRef`.
7. **No `evidence.no_store_audit` event in §3.10's published table**. We invent it as an audit-only event with `dispatch_status='delivered'` already set (same pattern as M0.2's `system.delivery_failed` recursion guard) — sits in the table for inspection by Ops, never re-dispatched to subscribers. Naming this `evidence.no_store_audit` rather than overloading `evidence.appended` keeps M0.4's `evidence.appended` consumer (Extractor) free of `NO_STORE` corner cases.

---

## File Structure

### New files

C++ headers (under `include/starling/`):
- `include/starling/schema/enums.hpp` — C++ mirrors of `SourceKind`, `IngestPolicy`, `IngestMode`, `PrivacyClass`, `EngramRetentionMode` (string-enum parity with `python/starling/schema/enums.py`). M0.1 left this for whoever first needed it; M0.3 is that consumer.
- `include/starling/evidence/engram.hpp` — `Engram` POD struct + `EngramRef` + `EngramInput` + canonical-payload hashing helper.
- `include/starling/evidence/ingest_policy_resolver.hpp` — `IngestPolicyResolver::resolve(source_kind, privacy_class, declared)` returning `IngestPolicy`. Pure function; no state.
- `include/starling/evidence/evidence_validator.hpp` — `EvidenceValidator::validate(input, conn) -> ValidationOutcome`. Owns idempotency lookup + transformations check + policy resolution.
- `include/starling/evidence/engram_store.hpp` — `EngramStore::put(input, content_hash, conn) -> Engram` and `EngramStore::get(id, tenant_id, conn) -> std::optional<Engram>`.
- `include/starling/bus/bus.hpp` — `Bus` C++ class. Owns `OutboxWriter`, `EngramStore`, `EvidenceValidator`. Single public API in M0.3: `append_evidence(EngramInput, causation_parent) -> AppendEvidenceOutcome`.
- `include/starling/crypto/null_kms.hpp` — header-only `NullKms` (encrypt = identity, decrypt = identity, generate_key_ref returns `std::nullopt`).

C++ source (under `src/`):
- `src/schema/enums.cpp` — `to_string` / `from_string` for the five M0.3 enums.
- `src/evidence/engram.cpp` — `canonicalize_engram_payload` + `compute_engram_content_hash`.
- `src/evidence/ingest_policy_resolver.cpp`
- `src/evidence/evidence_validator.cpp`
- `src/evidence/engram_store.cpp`
- `src/bus/bus.cpp`

Embedded SQL migration:
- `migrations/0003_engram_store_columns.sql` — adds the M0.3 columns + UNIQUE index on `(tenant_id, adapter_name, source_item_id, source_version, chunk_index)`.

Python (under `python/starling/`):
- `python/starling/evidence/__init__.py` — public surface: `EngramInput`, `EngramRef`, `IngestPolicy`, `SourceKind`, `EngramRetentionMode`, `for_user_input`, `for_external_doc`, `for_tool_observation`, `for_system_internal`, `for_observer_agent`, `for_replay_output`.
- `python/starling/evidence/inputs.py` — `EngramInput` dataclass + the six builder helpers.
- `python/starling/bus/append_evidence.py` — high-level Python `Bus.append_evidence` wrapper that opens an SqliteAdapter txn and calls the binding.

Tests (under `tests/`):
- `tests/cpp/test_ingest_policy_resolver.cpp`
- `tests/cpp/test_evidence_validator.cpp`
- `tests/cpp/test_engram_store.cpp`
- `tests/cpp/test_bus_append_evidence.cpp` — atomicity + outbox event shape
- `tests/cpp/test_engram_content_hash.cpp` — `declared_transformations` affects hash
- `tests/python/test_evidence_inputs.py` — builder defaults match resolver expectations
- `tests/python/test_bus_append_evidence_parity.py` — Python ↔ C++ parity for `IngestPolicy` resolution
- `tests/python/test_self_pollution_guard.py` — §15.3.2 `自污染防护` regression: `system_internal` payload → `NO_STORE`, no `engrams` row, audit row only
- `tests/python/test_m0_3_acceptance.py` — milestone acceptance smoke

### Modified files
- `CMakeLists.txt` — append M0.3 source files to `starling_core`; embed `0003_engram_store_columns.sql` via the existing `migrations.inc` glob mechanism (no CMake change actually required if the glob already covers `migrations/*.sql` — verify in Task 0).
- `tests/cpp/CMakeLists.txt` — register the five new C++ test executables (or append to the aggregated `starling_tests` target — verify the M0.2 convention in Task 0).
- `bindings/python/module.cpp` — extend `PYBIND11_MODULE(_core, m)` with `EngramInput`, `EngramRef`, `IngestPolicyResolver`, `EvidenceValidator`, `EngramStore`, `Bus`, plus the five M0.3 enum classes (or alias them to the Python-side `StrEnum` via `py::enum_<>`).
- `python/starling/runtime.py` — extend `_build_local_store_sqlite_runtime` to construct + return the new C++ `Bus`. Add a thin `_BusFacade` that the runtime exposes as `runtime.bus`. Keep the existing M0.2 `_SqliteBackedBus` (statement-write side) as `runtime._statement_bus` until M0.5 unifies them.
- `python/starling/testing/__init__.py` — add `relax_preflight_for_m0_3()` (alias of `relax_preflight_for_m0_2()` since M0.3 doesn't flip any new capabilities, but giving it a separate name lets the M0.3 acceptance test be self-documenting).
- `tools/ci/scan_prod_uses_testing.py` — extend the M0.2 forbidden-symbol scanner with `relax_preflight_for_m0_3` (so prod code can't accidentally pull it in).
- `docs/superpowers/plans/2026-05-23-roadmap.md` — flip M0.3 row to `已写 / ✅ 完成` after acceptance is green (handled by Task 11).

### Decomposition rationale
- One file per concern: `engram.hpp` owns the data shape, `ingest_policy_resolver` owns the rule, `evidence_validator` owns the orchestration (resolver + idempotency lookup + transformations check), `engram_store` owns persistence, `bus.hpp` owns the transactional envelope. This mirrors the §1 sentence in `06_engramstore.md`: "EngramStore 不做：派生抽取、检索排序、业务逻辑路由."
- Migration `0003` rather than amending `0001`: the M0.2 schema is already on main and has had a migration run against it. Editing `0001` would change its checksum and trigger drift detection. New columns + new index live in `0003`.
- Python evidence package separated from `starling.bus`: the `bus` package is M0.2's dispatcher + envelope. M0.3 adds *what* gets sent through it, which conceptually belongs in `starling.evidence`. The `Bus.append_evidence` wrapper lives in `starling.bus.append_evidence` as glue.
- `null_kms` rather than `#ifdef KMS`: keeping the call site stable from day one means M0.4's KMS swap-in is a one-file change. We pay one header file's cost now to avoid a refactor later.
- The §15.3.2 self-pollution test is its own file (`test_self_pollution_guard.py`) so the milestone acceptance test (`test_m0_3_acceptance.py`) stays narrow on "M0.3 surface works end-to-end." The retention test traces back to a §15.3 line item by name and is the one we point at when M0.7 acceptance reviews this milestone.

---

## Subsystem Contracts (locked at plan time)

### A. C++ enum mirrors

`include/starling/schema/enums.hpp`:

```cpp
#pragma once

#include <stdexcept>
#include <string>
#include <string_view>

namespace starling::schema {

enum class SourceKind {
    USER_INPUT,
    EXTERNAL_DOC,
    TOOL_OBSERVATION,
    SYSTEM_INTERNAL,
    OBSERVER_AGENT,
    REPLAY_OUTPUT,
};

enum class IngestPolicy {
    STORE,
    NO_STORE,
    STORE_METADATA_ONLY,
    REQUIRE_REVIEW,
};

enum class IngestMode {
    CHUNKED_CONTENT,
    WHOLE_RECORD,
    METADATA_ONLY,
};

enum class PrivacyClass {
    PUBLIC,
    INTERNAL,
    PERSONAL,
    SENSITIVE,
    REGULATED,
};

enum class EngramRetentionMode {
    LEGAL_HOLD,
    AUDIT_RETAIN,
    REDACTED_RETAIN,
    CRYPTO_ERASURE,
};

std::string_view to_string(SourceKind);
std::string_view to_string(IngestPolicy);
std::string_view to_string(IngestMode);
std::string_view to_string(PrivacyClass);
std::string_view to_string(EngramRetentionMode);

SourceKind          source_kind_from_string(std::string_view);
IngestPolicy        ingest_policy_from_string(std::string_view);
IngestMode          ingest_mode_from_string(std::string_view);
PrivacyClass        privacy_class_from_string(std::string_view);
EngramRetentionMode engram_retention_mode_from_string(std::string_view);

}  // namespace starling::schema
```

The string values MUST be byte-identical to the Python `StrEnum` values in `python/starling/schema/enums.py:48-72`: `"user_input"`, `"external_doc"`, `"tool_observation"`, `"system_internal"`, `"observer_agent"`, `"replay_output"`, `"store"`, `"no_store"`, `"store_metadata_only"`, `"require_review"`, `"chunked_content"`, `"whole_record"`, `"metadata_only"`, `"public"`, `"internal"`, `"personal"`, `"sensitive"`, `"regulated"`, `"legal_hold"`, `"audit_retain"`, `"redacted_retain"`, `"crypto_erasure"`. The M0.1 parity test `tests/cpp/test_canonicalize.cpp` already locks this contract for the enums it covers; we extend it.

`from_string` throws `std::invalid_argument` on unknown values. (Fail-closed: a typo in a migration shouldn't silently become STORE.)

### B. Engram POD + EngramInput + EngramRef

`include/starling/evidence/engram.hpp`:

```cpp
#pragma once

#include "starling/schema/enums.hpp"

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace starling::evidence {

// Adapter / source identification. P1 has no segment_map, so chunk_index is the
// finest grain. P3 will add (segment_id, span_start, span_end).
struct SourceIdentity {
    std::string adapter_name;     // "direct_api" if produced by a direct caller
    std::string adapter_version;  // semver or commit hash
    std::string source_item_id;   // adapter-stable id of the source record
    std::string source_version;   // adapter-stable version of that record
    int32_t     chunk_index = 0;  // 0 if the whole record is one chunk
};

// Producer-supplied input. Bus.append_evidence is the only consumer.
struct EngramInput {
    std::string                tenant_id;
    SourceIdentity             source;
    schema::SourceKind         source_kind;
    schema::IngestMode         ingest_mode;
    schema::PrivacyClass       privacy_class;
    schema::EngramRetentionMode retention_mode;
    std::vector<std::string>   declared_transformations;  // empty == byte_preserving claim
    bool                       byte_preserving;           // producer claim; trusted in P1
    std::vector<uint8_t>       payload_bytes;             // verbatim payload (or metadata blob)
    std::optional<std::string> redacted_content;          // for redacted_retain only
    std::string                created_at_iso8601;        // caller-supplied; UTC ISO-8601
};

// Persistence-side row.
struct Engram {
    std::string                id;                 // UUID
    std::string                tenant_id;
    SourceIdentity             source;
    schema::SourceKind         source_kind;
    schema::IngestPolicy       ingest_policy;
    schema::IngestMode         ingest_mode;
    schema::PrivacyClass       privacy_class;
    schema::EngramRetentionMode retention_mode;
    std::vector<std::string>   declared_transformations;
    bool                       byte_preserving = false;
    std::string                content_hash;       // sha256 hex
    std::optional<std::string> key_ref;            // null in P1
    std::vector<uint8_t>       content_ciphertext; // raw bytes in P1 (null_kms)
    std::optional<std::string> redacted_content;
    int64_t                    refcount = 0;       // not touched in M0.3
    std::string                created_at_iso8601;
    std::optional<std::string> erased_at_iso8601;  // always null in M0.3
};

// Returned by Bus.append_evidence to producers. Statement.evidence will use
// this shape (M0.5).
struct EngramRef {
    std::string                id;
    std::string                content_hash;
    schema::EngramRetentionMode retention_mode;
};

// Canonical bytes for content_hash. The §3.7 invariant is that
// declared_transformations is part of the hash domain so that two pipelines
// that produced "same bytes" via different normalizations get different hashes.
//
// Format:
//   "v1\x1f" + payload_bytes + "\x1f" + sorted_unique(transformations).join("\x1f")
//
// Sorted+unique because transformations is a *set* semantically; sorting makes
// the producer's tuple order irrelevant. v1 prefix lets us version the
// canonical form later without colliding with M0.3 hashes.
std::string canonicalize_engram_payload(
    const std::vector<uint8_t>& payload_bytes,
    const std::vector<std::string>& declared_transformations);

std::string compute_engram_content_hash(
    const std::vector<uint8_t>& payload_bytes,
    const std::vector<std::string>& declared_transformations);

}  // namespace starling::evidence
```

### C. IngestPolicyResolver — the self-pollution guard

`include/starling/evidence/ingest_policy_resolver.hpp`:

```cpp
#pragma once

#include "starling/schema/enums.hpp"

namespace starling::evidence {

// Pure function; no state. Mirrors §3.7 lines 1085-1094:
//
//   user_input                   → STORE
//   external_doc                 → STORE
//   tool_observation             → STORE_METADATA_ONLY
//   system_internal              → NO_STORE   ← self-pollution guard
//   observer_agent               → NO_STORE   ← self-pollution guard
//   replay_output                → NO_STORE   ← self-pollution guard
//
// privacy_class can DOWNGRADE the result (REGULATED on user_input → REQUIRE_REVIEW)
// but CANNOT upgrade NO_STORE to STORE. Self-pollution beats privacy.
//
// `producer_declared` is what the producer asked for. P1 honors STORE_METADATA_ONLY
// and REQUIRE_REVIEW as downgrades when source_kind would otherwise allow STORE,
// but ignores any producer attempt to override NO_STORE.
class IngestPolicyResolver {
public:
    static schema::IngestPolicy resolve(
        schema::SourceKind source_kind,
        schema::PrivacyClass privacy_class,
        schema::IngestPolicy producer_declared);
};

}  // namespace starling::evidence
```

Resolution table (derived from §3.7 + §05_bus line 65):

| source_kind | privacy_class | producer_declared | result |
|---|---|---|---|
| user_input | public/internal/personal | STORE | STORE |
| user_input | sensitive | STORE | STORE |
| user_input | regulated | STORE | REQUIRE_REVIEW |
| user_input | * | STORE_METADATA_ONLY | STORE_METADATA_ONLY |
| user_input | * | REQUIRE_REVIEW | REQUIRE_REVIEW |
| external_doc | public/internal/personal | STORE | STORE |
| external_doc | sensitive/regulated | STORE | REQUIRE_REVIEW |
| external_doc | * | STORE_METADATA_ONLY | STORE_METADATA_ONLY |
| tool_observation | * | STORE | STORE_METADATA_ONLY |
| tool_observation | * | STORE_METADATA_ONLY | STORE_METADATA_ONLY |
| tool_observation | * | REQUIRE_REVIEW | REQUIRE_REVIEW |
| system_internal | * | * | NO_STORE |
| observer_agent | * | * | NO_STORE |
| replay_output | * | * | NO_STORE |

The "tool_observation × STORE → STORE_METADATA_ONLY" downgrade is the §3.7 line "tool_observation 默认 STORE_METADATA_ONLY，仅当工具输出是用户可见事实或外部世界观测时升级为 STORE". P1 keeps the downgrade rule simple (always downgrade in the resolver) and leaves the "user-visible fact escape hatch" as M0.x post-P1 — the producer can't override it via `producer_declared` alone, but a future `tool_observation_promoted: bool` field on `EngramInput` can. That field is **not** added in M0.3 (YAGNI; the §15.3.2 retention only tests `system_internal`).

### D. EvidenceValidator — orchestration

`include/starling/evidence/evidence_validator.hpp`:

```cpp
#pragma once

#include "starling/evidence/engram.hpp"
#include "starling/persistence/connection.hpp"

#include <optional>
#include <string>
#include <variant>

namespace starling::evidence {

// Outcome of validation; Bus uses this to decide what to do next.
struct ValidationProceed {
    schema::IngestPolicy resolved_policy;  // STORE / STORE_METADATA_ONLY / REQUIRE_REVIEW
};
struct ValidationIdempotentHit {
    Engram existing;  // already-stored Engram for the same source-identity tuple
};
struct ValidationNoStore {
    schema::IngestPolicy resolved_policy = schema::IngestPolicy::NO_STORE;
};
struct ValidationReject {
    std::string reason;  // "transformations_must_be_unique", "byte_preserving_requires_empty_transformations", ...
};

using ValidationOutcome = std::variant<
    ValidationProceed,
    ValidationIdempotentHit,
    ValidationNoStore,
    ValidationReject>;

class EvidenceValidator {
public:
    // Idempotency lookup runs against the open transaction, NOT a fresh
    // connection — this matters because the caller (Bus) holds a write txn,
    // and a separate-connection read could miss a concurrent insert from
    // another producer in the same wall-clock instant. SQLite WAL gives us
    // repeatable-read within a single transaction.
    static ValidationOutcome validate(
        const EngramInput& input,
        starling::persistence::Connection& conn);
};

}  // namespace starling::evidence
```

Validation steps, in order (locked):
1. **Schema-shape checks** (cheap, no DB):
   - `byte_preserving == true` ⇒ `declared_transformations` MUST be empty. Otherwise → `ValidationReject{"byte_preserving_requires_empty_transformations"}`.
   - `declared_transformations` MUST be unique (no duplicate strings). Otherwise → `ValidationReject{"transformations_must_be_unique"}`. (Determinism of content_hash depends on this.)
   - `tenant_id`, `source.adapter_name`, `source.source_item_id`, `source.source_version` MUST be non-empty. Otherwise → `ValidationReject{"required_field_missing:<name>"}`.
   - `created_at_iso8601` MUST parse as UTC ISO-8601 (re-use the M0.1 helper if present, otherwise a small `chrono::parse` call). Otherwise → `ValidationReject{"created_at_not_iso8601"}`.
2. **Resolve IngestPolicy** via `IngestPolicyResolver::resolve(source_kind, privacy_class, declared=STORE)` — P1 takes the producer's `EngramInput` as implicitly declaring STORE; the resolver applies the self-pollution guard.
3. **If resolved == NO_STORE**: short-circuit return `ValidationNoStore`. No idempotency lookup (NO_STORE never writes a row, so there's nothing to dedup against).
4. **Source idempotency lookup**: `SELECT * FROM engrams WHERE tenant_id = ? AND adapter_name = ? AND source_item_id = ? AND source_version = ? AND chunk_index = ?`. If a row exists → return `ValidationIdempotentHit{existing}`.
5. Else → return `ValidationProceed{resolved_policy}`.

(REQUIRE_REVIEW is NOT a reject in M0.3 — it's stored on the row so a future review queue can pick it up. The `review_status` column on `engrams` is reserved by the schema but not part of M0.3's API surface.)

### E. EngramStore — persistence

`include/starling/evidence/engram_store.hpp`:

```cpp
#pragma once

#include "starling/evidence/engram.hpp"
#include "starling/persistence/connection.hpp"

#include <optional>
#include <string>
#include <string_view>

namespace starling::evidence {

class EngramStore {
public:
    // Inserts a new Engram row inside the caller's transaction. The id field
    // is set by put() (UUIDv4 via std::random_device); content_hash is
    // computed; refcount=0; erased_at=null. Returns the persisted Engram so
    // the caller can build an EngramRef.
    //
    // Pre-conditions enforced by EvidenceValidator (caller is Bus; Bus calls
    // validator first, then put — put doesn't re-check):
    //  - resolved_policy != NO_STORE
    //  - source-identity tuple is unique
    //  - declared_transformations is unique
    //  - byte_preserving consistent with declared_transformations
    static Engram put(
        const EngramInput& input,
        schema::IngestPolicy resolved_policy,
        starling::persistence::Connection& conn);

    static std::optional<Engram> get(
        std::string_view id,
        std::string_view tenant_id,
        starling::persistence::Connection& conn);
};

}  // namespace starling::evidence
```

INSERT shape (matching the migration in Task 2):

```sql
INSERT INTO engrams(
    id, tenant_id, content_hash, source_kind, ingest_policy, ingest_mode,
    privacy_class, retention_mode, refcount, payload_uri, payload_inline,
    created_at, erased_at,
    adapter_name, adapter_version, source_item_id, source_version, chunk_index,
    declared_transformations_json, byte_preserving, redacted_content,
    key_ref, audit_trail_json
) VALUES (
    :id, :tenant_id, :content_hash, :source_kind, :ingest_policy, :ingest_mode,
    :privacy_class, :retention_mode, 0, NULL, :payload_inline,
    :created_at, NULL,
    :adapter_name, :adapter_version, :source_item_id, :source_version, :chunk_index,
    :declared_transformations_json, :byte_preserving, :redacted_content,
    NULL, '[]'
);
```

`payload_inline` carries the raw bytes (M0.2 left it as `BLOB` for tests; M0.3 uses it as the production location until KMS lands). `payload_uri` stays NULL; `key_ref` stays NULL; `audit_trail_json` is the empty array literal.

### F. Bus.append_evidence — transactional envelope

`include/starling/bus/bus.hpp`:

```cpp
#pragma once

#include "starling/bus/bus_event.hpp"
#include "starling/bus/outbox_writer.hpp"
#include "starling/evidence/engram.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <optional>
#include <string>
#include <variant>

namespace starling::bus {

struct AppendEvidenceAccepted {
    starling::evidence::EngramRef ref;
    std::string event_id;             // event_id of the evidence.appended row
    int64_t outbox_sequence;          // sequence claimed for that row
};
struct AppendEvidenceIdempotent {
    starling::evidence::EngramRef ref;  // existing engram
    std::string audit_event_id;         // evidence.idempotent_hit (audit-only)
};
struct AppendEvidenceNoStore {
    std::string audit_event_id;         // evidence.no_store_audit (audit-only)
};
struct AppendEvidenceRejected {
    std::string reason;
};

using AppendEvidenceOutcome = std::variant<
    AppendEvidenceAccepted,
    AppendEvidenceIdempotent,
    AppendEvidenceNoStore,
    AppendEvidenceRejected>;

class Bus {
public:
    // Holds a non-owning reference to an SqliteAdapter. The adapter's lifetime
    // must outlive the Bus; the runtime supervisor enforces this (Bus is owned
    // by the runtime and torn down before the adapter).
    explicit Bus(starling::persistence::SqliteAdapter& adapter);

    // The §1 invariant: Bus is the only writer to engrams + bus_events. There
    // is no public EngramStore::put on the runtime surface.
    AppendEvidenceOutcome append_evidence(
        const starling::evidence::EngramInput& input,
        std::optional<std::string> causation_parent_event_id);

private:
    starling::persistence::SqliteAdapter& adapter_;
};

}  // namespace starling::bus
```

Transaction flow inside `append_evidence`:

```
BEGIN IMMEDIATE
  outcome = EvidenceValidator::validate(input, conn)
  match outcome:
    ValidationReject(r)         → ROLLBACK; return AppendEvidenceRejected{r}
    ValidationNoStore           →
        event = make_audit_event("evidence.no_store_audit", input, causation_parent)
        OutboxWriter::append_already_delivered(event, conn)   // dispatch_status='delivered'
        COMMIT
        return AppendEvidenceNoStore{event.event_id}
    ValidationIdempotentHit(e)  →
        event = make_audit_event("evidence.idempotent_hit", input, causation_parent,
                                 existing_engram_id=e.id)
        OutboxWriter::append_already_delivered(event, conn)   // dispatch_status='delivered'
        COMMIT
        return AppendEvidenceIdempotent{ref_from(e), event.event_id}
    ValidationProceed(policy)   →
        engram = EngramStore::put(input, policy, conn)
        event = make_business_event("evidence.appended", engram, causation_parent)
        OutboxWriter::append(event, conn)                     // dispatch_status='pending'
        COMMIT
        return AppendEvidenceAccepted{ref_from(engram), event.event_id, event.outbox_sequence}
COMMIT or ROLLBACK
```

`make_business_event` shape:
- `event_type = "evidence.appended"`
- `primary_id = engram.id`
- `aggregate_id = engram.id`  (§3.10 table: `evidence.* → primary_id=engram_ref, aggregate_id=engram_ref`)
- `payload_json = canonical JSON of {engram_id, content_hash, retention_mode, source_kind, tenant_id}`
- `idempotency_key = compute_idempotency_key(event_type, aggregate_id, canonical_key=engram.id, causation_root, window_bucket="")`
- `causation_chain = (causation_parent_event_id ? [causation_parent] : [])`

`make_audit_event` for `evidence.no_store_audit`:
- `event_type = "evidence.no_store_audit"`
- `primary_id = compute_audit_primary_id(input)` — the source-identity tuple hashed (sha256 of `adapter_name\x1fsource_item_id\x1fsource_version\x1fchunk_index`). Audit events have no Engram, so `engram_id` doesn't exist; we still need a stable primary_id for outbox table integrity.
- `aggregate_id = primary_id`
- `payload_json = canonical JSON of {tenant_id, source_kind, privacy_class, source_identity, reason: "self_pollution_guard_or_producer_declared_no_store"}`
- `idempotency_key = compute_idempotency_key(...)` with `canonical_key=primary_id`

`OutboxWriter::append_already_delivered` — NEW method paralleling M0.2's `append_already_delivered` for `system.delivery_failed`. It exists for exactly the same reason: this row is audit-only, never re-dispatched to subscribers, so we mark it `delivered` at insertion time. Verify in Task 0 that `OutboxWriter::append_already_delivered` is already defined by M0.2 (the M0.2 plan references it for the dispatcher recursion guard); if the method only existed in the dispatcher's call path, M0.3 lifts it onto the writer's public API.

### G. Self-pollution guard test (§15.3.2)

The §15.3.2 retention test in `tests/python/test_self_pollution_guard.py`:

```python
def test_system_internal_payload_does_not_create_engram(starling_runtime):
    # Producer attempts to ingest a RetrievalReceipt-style trace as evidence.
    inp = for_system_internal(
        tenant_id="t1",
        adapter_name="retrieval_planner",
        adapter_version="0.1.0",
        source_item_id="receipt-abc",
        source_version="1",
        privacy_class=PrivacyClass.INTERNAL,
        retention_mode=EngramRetentionMode.AUDIT_RETAIN,
        payload_bytes=b"sufficiency_status=SUFFICIENT|...",
        created_at=datetime.now(timezone.utc),
    )
    outcome = starling_runtime.bus.append_evidence(inp)

    # NO Engram row was created.
    rows = starling_runtime.adapter.execute("SELECT count(*) FROM engrams").fetchone()
    assert rows[0] == 0

    # ONE audit row exists with event_type = evidence.no_store_audit.
    audit = starling_runtime.adapter.execute(
        "SELECT event_type, dispatch_status FROM bus_events"
    ).fetchall()
    assert audit == [("evidence.no_store_audit", "delivered")]

    # The outcome surfaces NO_STORE to the producer.
    assert outcome.kind == "no_store"
    assert outcome.audit_event_id  # non-empty UUID
```

This is **the** §15.3.2 retention M0.3 owns. The complementary "no Statement materializes" half is M0.4's responsibility (the Extractor doesn't subscribe to `evidence.no_store_audit`).

### H. relax_preflight_for_m0_3

```python
# python/starling/testing/__init__.py (extension)

def relax_preflight_for_m0_3() -> None:
    """M0.3 still defers per-record AES key + KMS to M0.4+. The required-set
    surgery is identical to relax_preflight_for_m0_2 — kept as a separate
    function so the M0.3 acceptance test can name what it's relaxing."""
    relax_preflight_for_m0_2()
```

Consequence: the M0.3 acceptance test calls `relax_preflight_for_m0_3()` once at module import. The CI scanner (Task 9) blocks any prod-side import. M0.4 is expected to **delete** both helpers when it lands the real `engram_per_record_key` capability.

---

## Tasks

### Task 0: Worktree + baseline + M0.2 surface verification

**Files:**
- No file changes; verification only.

**Goal:** Confirm we are on a clean tree, M0.2 baseline is green, and the M0.2 facts this plan depends on (migration glob, `OutboxWriter::append_already_delivered`, aggregated `starling_tests` target) are actually true so later tasks can rely on them.

- [ ] **Step 1: Verify HEAD and clean tree**

Run:
```bash
git rev-parse HEAD
git status --porcelain
```
Expected: HEAD prints `ab5f2c4` (the M0.2 merge commit). `git status --porcelain` prints nothing.

If HEAD differs (e.g., a doc-only commit landed since): note the actual SHA, confirm with the user that the M0.2 surface is unchanged, and proceed.

- [ ] **Step 2: Enter a fresh worktree for M0.3**

Use the native `EnterWorktree` tool (the platform provides it; do NOT fall back to `git worktree add`). Suggested name: `m0-3-engram-store`. After entering the worktree, run:
```bash
git rev-parse HEAD
git branch --show-current
```
Expected: same SHA as main, branch is the worktree-private branch the tool created.

- [ ] **Step 3: Verify build + test baseline**

Run:
```bash
cmake --preset default && cmake --build --preset default
ctest --preset default --output-on-failure
.venv/bin/pytest -q
```
Expected: `ctest` reports 62/62 pass. `pytest` reports 212/212 pass (M0.2 baseline). If either is red, STOP and report — do NOT start M0.3 on a broken baseline.

- [ ] **Step 4: Verify the M0.2 facts this plan assumes**

Run these checks (each independently — if any fails, fix the plan, not the assumption):

```bash
# 1. Migrations glob: does CMake auto-discover *.sql in migrations/?
grep -n "migrations" CMakeLists.txt | head -20
ls migrations/

# 2. OutboxWriter::append_already_delivered — does the method exist on the writer?
grep -n "append_already_delivered" include/starling/bus/outbox_writer.hpp src/bus/outbox_writer.cpp

# 3. Aggregated test target — single starling_tests exe or per-file exes?
grep -n "add_executable\|gtest_discover_tests\|starling_tests" tests/cpp/CMakeLists.txt

# 4. engrams table — confirm M0.2 columns we're going to extend
grep -A 20 "CREATE TABLE IF NOT EXISTS engrams" migrations/0001_initial_schema.sql

# 5. SqliteAdapter — does it expose Connection& or do we need a getter?
grep -n "connection\|conn_\|conn()" include/starling/persistence/sqlite_adapter.hpp
```

Record findings (this is reference material for later tasks):
- If migrations glob is present (`file(GLOB ... migrations/*.sql)`), Task 2 is just "drop a file." If not, Task 2 also adds the glob.
- If `append_already_delivered` is NOT on `OutboxWriter`, Task 8 adds it (lifted from `OutboxDispatcher`).
- If tests use an aggregated `starling_tests` target, all Task `tests/cpp/...` files become source additions to that target, not new executables.
- If `SqliteAdapter` does NOT expose `Connection&`, Task 8 adds a const-getter.

- [ ] **Step 5: Commit the worktree-private starting point (no files changed, just a marker)**

Do NOT make a commit yet. The first M0.3 commit lands in Task 1.

---

### Task 1: C++ enum mirror header + parity test

**Files:**
- Create: `include/starling/schema/enums.hpp`
- Create: `src/schema/enums.cpp`
- Create: `tests/cpp/test_schema_enums.cpp`
- Modify: `CMakeLists.txt` (add `src/schema/enums.cpp` to `starling_core`)
- Modify: `tests/cpp/CMakeLists.txt` (register the new test — or append a source line if aggregated target)

**Goal:** C++ has compile-time-checked enums for the five M0.3 enum classes with `to_string` / `from_string` parity to `python/starling/schema/enums.py`. Foundation for everything else.

- [ ] **Step 1: Write the failing parity test**

Create `tests/cpp/test_schema_enums.cpp`:

```cpp
#include <gtest/gtest.h>

#include "starling/schema/enums.hpp"

#include <stdexcept>
#include <string>

using starling::schema::SourceKind;
using starling::schema::IngestPolicy;
using starling::schema::IngestMode;
using starling::schema::PrivacyClass;
using starling::schema::EngramRetentionMode;

TEST(SchemaEnums, SourceKindRoundTrip) {
    EXPECT_EQ(to_string(SourceKind::USER_INPUT), "user_input");
    EXPECT_EQ(to_string(SourceKind::EXTERNAL_DOC), "external_doc");
    EXPECT_EQ(to_string(SourceKind::TOOL_OBSERVATION), "tool_observation");
    EXPECT_EQ(to_string(SourceKind::SYSTEM_INTERNAL), "system_internal");
    EXPECT_EQ(to_string(SourceKind::OBSERVER_AGENT), "observer_agent");
    EXPECT_EQ(to_string(SourceKind::REPLAY_OUTPUT), "replay_output");

    EXPECT_EQ(source_kind_from_string("user_input"), SourceKind::USER_INPUT);
    EXPECT_EQ(source_kind_from_string("replay_output"), SourceKind::REPLAY_OUTPUT);
    EXPECT_THROW(source_kind_from_string("unknown"), std::invalid_argument);
    EXPECT_THROW(source_kind_from_string(""), std::invalid_argument);
}

TEST(SchemaEnums, IngestPolicyRoundTrip) {
    EXPECT_EQ(to_string(IngestPolicy::STORE), "store");
    EXPECT_EQ(to_string(IngestPolicy::NO_STORE), "no_store");
    EXPECT_EQ(to_string(IngestPolicy::STORE_METADATA_ONLY), "store_metadata_only");
    EXPECT_EQ(to_string(IngestPolicy::REQUIRE_REVIEW), "require_review");

    EXPECT_EQ(ingest_policy_from_string("no_store"), IngestPolicy::NO_STORE);
    EXPECT_THROW(ingest_policy_from_string("STORE"), std::invalid_argument);  // case-sensitive
}

TEST(SchemaEnums, IngestModeRoundTrip) {
    EXPECT_EQ(to_string(IngestMode::CHUNKED_CONTENT), "chunked_content");
    EXPECT_EQ(to_string(IngestMode::WHOLE_RECORD), "whole_record");
    EXPECT_EQ(to_string(IngestMode::METADATA_ONLY), "metadata_only");
    EXPECT_EQ(ingest_mode_from_string("whole_record"), IngestMode::WHOLE_RECORD);
}

TEST(SchemaEnums, PrivacyClassRoundTrip) {
    EXPECT_EQ(to_string(PrivacyClass::PUBLIC), "public");
    EXPECT_EQ(to_string(PrivacyClass::REGULATED), "regulated");
    EXPECT_EQ(privacy_class_from_string("sensitive"), PrivacyClass::SENSITIVE);
}

TEST(SchemaEnums, EngramRetentionModeRoundTrip) {
    EXPECT_EQ(to_string(EngramRetentionMode::LEGAL_HOLD), "legal_hold");
    EXPECT_EQ(to_string(EngramRetentionMode::AUDIT_RETAIN), "audit_retain");
    EXPECT_EQ(to_string(EngramRetentionMode::REDACTED_RETAIN), "redacted_retain");
    EXPECT_EQ(to_string(EngramRetentionMode::CRYPTO_ERASURE), "crypto_erasure");

    EXPECT_EQ(engram_retention_mode_from_string("crypto_erasure"),
              EngramRetentionMode::CRYPTO_ERASURE);
    EXPECT_THROW(engram_retention_mode_from_string("erased"), std::invalid_argument);
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `ctest --preset default --output-on-failure -R SchemaEnums`
Expected: FAIL with linker error (no `enums.hpp`).

- [ ] **Step 3: Write the header**

Create `include/starling/schema/enums.hpp` with the full content from Subsystem Contract A above (copied verbatim — repeated here so the engineer doesn't have to scroll back):

```cpp
#pragma once

#include <stdexcept>
#include <string>
#include <string_view>

namespace starling::schema {

enum class SourceKind {
    USER_INPUT,
    EXTERNAL_DOC,
    TOOL_OBSERVATION,
    SYSTEM_INTERNAL,
    OBSERVER_AGENT,
    REPLAY_OUTPUT,
};

enum class IngestPolicy {
    STORE,
    NO_STORE,
    STORE_METADATA_ONLY,
    REQUIRE_REVIEW,
};

enum class IngestMode {
    CHUNKED_CONTENT,
    WHOLE_RECORD,
    METADATA_ONLY,
};

enum class PrivacyClass {
    PUBLIC,
    INTERNAL,
    PERSONAL,
    SENSITIVE,
    REGULATED,
};

enum class EngramRetentionMode {
    LEGAL_HOLD,
    AUDIT_RETAIN,
    REDACTED_RETAIN,
    CRYPTO_ERASURE,
};

std::string_view to_string(SourceKind);
std::string_view to_string(IngestPolicy);
std::string_view to_string(IngestMode);
std::string_view to_string(PrivacyClass);
std::string_view to_string(EngramRetentionMode);

SourceKind          source_kind_from_string(std::string_view);
IngestPolicy        ingest_policy_from_string(std::string_view);
IngestMode          ingest_mode_from_string(std::string_view);
PrivacyClass        privacy_class_from_string(std::string_view);
EngramRetentionMode engram_retention_mode_from_string(std::string_view);

}  // namespace starling::schema
```

- [ ] **Step 4: Write the implementation**

Create `src/schema/enums.cpp`:

```cpp
#include "starling/schema/enums.hpp"

#include <stdexcept>
#include <string>

namespace starling::schema {

std::string_view to_string(SourceKind v) {
    switch (v) {
        case SourceKind::USER_INPUT:       return "user_input";
        case SourceKind::EXTERNAL_DOC:     return "external_doc";
        case SourceKind::TOOL_OBSERVATION: return "tool_observation";
        case SourceKind::SYSTEM_INTERNAL:  return "system_internal";
        case SourceKind::OBSERVER_AGENT:   return "observer_agent";
        case SourceKind::REPLAY_OUTPUT:    return "replay_output";
    }
    throw std::invalid_argument("unknown SourceKind value");
}

std::string_view to_string(IngestPolicy v) {
    switch (v) {
        case IngestPolicy::STORE:               return "store";
        case IngestPolicy::NO_STORE:            return "no_store";
        case IngestPolicy::STORE_METADATA_ONLY: return "store_metadata_only";
        case IngestPolicy::REQUIRE_REVIEW:      return "require_review";
    }
    throw std::invalid_argument("unknown IngestPolicy value");
}

std::string_view to_string(IngestMode v) {
    switch (v) {
        case IngestMode::CHUNKED_CONTENT: return "chunked_content";
        case IngestMode::WHOLE_RECORD:    return "whole_record";
        case IngestMode::METADATA_ONLY:   return "metadata_only";
    }
    throw std::invalid_argument("unknown IngestMode value");
}

std::string_view to_string(PrivacyClass v) {
    switch (v) {
        case PrivacyClass::PUBLIC:    return "public";
        case PrivacyClass::INTERNAL:  return "internal";
        case PrivacyClass::PERSONAL:  return "personal";
        case PrivacyClass::SENSITIVE: return "sensitive";
        case PrivacyClass::REGULATED: return "regulated";
    }
    throw std::invalid_argument("unknown PrivacyClass value");
}

std::string_view to_string(EngramRetentionMode v) {
    switch (v) {
        case EngramRetentionMode::LEGAL_HOLD:      return "legal_hold";
        case EngramRetentionMode::AUDIT_RETAIN:    return "audit_retain";
        case EngramRetentionMode::REDACTED_RETAIN: return "redacted_retain";
        case EngramRetentionMode::CRYPTO_ERASURE:  return "crypto_erasure";
    }
    throw std::invalid_argument("unknown EngramRetentionMode value");
}

SourceKind source_kind_from_string(std::string_view s) {
    if (s == "user_input")       return SourceKind::USER_INPUT;
    if (s == "external_doc")     return SourceKind::EXTERNAL_DOC;
    if (s == "tool_observation") return SourceKind::TOOL_OBSERVATION;
    if (s == "system_internal")  return SourceKind::SYSTEM_INTERNAL;
    if (s == "observer_agent")   return SourceKind::OBSERVER_AGENT;
    if (s == "replay_output")    return SourceKind::REPLAY_OUTPUT;
    throw std::invalid_argument(std::string("unknown SourceKind: ") + std::string(s));
}

IngestPolicy ingest_policy_from_string(std::string_view s) {
    if (s == "store")               return IngestPolicy::STORE;
    if (s == "no_store")            return IngestPolicy::NO_STORE;
    if (s == "store_metadata_only") return IngestPolicy::STORE_METADATA_ONLY;
    if (s == "require_review")      return IngestPolicy::REQUIRE_REVIEW;
    throw std::invalid_argument(std::string("unknown IngestPolicy: ") + std::string(s));
}

IngestMode ingest_mode_from_string(std::string_view s) {
    if (s == "chunked_content") return IngestMode::CHUNKED_CONTENT;
    if (s == "whole_record")    return IngestMode::WHOLE_RECORD;
    if (s == "metadata_only")   return IngestMode::METADATA_ONLY;
    throw std::invalid_argument(std::string("unknown IngestMode: ") + std::string(s));
}

PrivacyClass privacy_class_from_string(std::string_view s) {
    if (s == "public")    return PrivacyClass::PUBLIC;
    if (s == "internal")  return PrivacyClass::INTERNAL;
    if (s == "personal")  return PrivacyClass::PERSONAL;
    if (s == "sensitive") return PrivacyClass::SENSITIVE;
    if (s == "regulated") return PrivacyClass::REGULATED;
    throw std::invalid_argument(std::string("unknown PrivacyClass: ") + std::string(s));
}

EngramRetentionMode engram_retention_mode_from_string(std::string_view s) {
    if (s == "legal_hold")      return EngramRetentionMode::LEGAL_HOLD;
    if (s == "audit_retain")    return EngramRetentionMode::AUDIT_RETAIN;
    if (s == "redacted_retain") return EngramRetentionMode::REDACTED_RETAIN;
    if (s == "crypto_erasure")  return EngramRetentionMode::CRYPTO_ERASURE;
    throw std::invalid_argument(std::string("unknown EngramRetentionMode: ") + std::string(s));
}

}  // namespace starling::schema
```

- [ ] **Step 5: Register the source file in CMake**

Append `src/schema/enums.cpp` to the `starling_core` source list. The exact mechanism depends on what Task 0 Step 4 found:
- If the source list uses `file(GLOB ... src/*.cpp src/*/*.cpp)`, no edit is needed.
- If sources are listed explicitly, add `src/schema/enums.cpp` to the list.

- [ ] **Step 6: Register the test**

Depending on Task 0 Step 4 finding:
- If aggregated `starling_tests` target: append `test_schema_enums.cpp` to its source list.
- If per-file executables: add the same `add_executable + target_link_libraries + gtest_discover_tests` block as `test_smoke.cpp`.

- [ ] **Step 7: Run the test to verify it passes**

```bash
cmake --build --preset default
ctest --preset default --output-on-failure -R SchemaEnums
```
Expected: 5 tests in the suite, all PASS.

- [ ] **Step 8: Commit**

```bash
git add include/starling/schema/enums.hpp src/schema/enums.cpp \
        tests/cpp/test_schema_enums.cpp CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -m "feat(M0.3): add C++ enum mirrors for SourceKind/IngestPolicy/IngestMode/PrivacyClass/EngramRetentionMode"
```

---

### Task 2: Schema migration 0003 — extend engrams table

**Files:**
- Create: `migrations/0003_engram_store_columns.sql`
- Create: `tests/cpp/test_migration_0003.cpp`

**Goal:** Add the M0.3 columns + unique index. Idempotent re-application leaves the table unchanged (SQLite's `ALTER TABLE ADD COLUMN` is idempotent only if absent; we use `IF NOT EXISTS` where SQLite supports it and fall back to a "column exists?" check otherwise).

- [ ] **Step 1: Write the failing migration test**

Create `tests/cpp/test_migration_0003.cpp`:

```cpp
#include <gtest/gtest.h>

#include "starling/persistence/connection.hpp"
#include "starling/persistence/migration_runner.hpp"

#include <set>
#include <string>

using starling::persistence::Connection;
using starling::persistence::MigrationRunner;

namespace {

std::set<std::string> column_names(Connection& conn, const std::string& table) {
    std::set<std::string> out;
    auto stmt = conn.prepare("PRAGMA table_info(" + table + ");");
    while (stmt.step() == SQLITE_ROW) {
        out.insert(stmt.column_text(1));  // column 1 is "name"
    }
    return out;
}

bool has_index(Connection& conn, const std::string& name) {
    auto stmt = conn.prepare(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?;");
    stmt.bind_text(1, name);
    return stmt.step() == SQLITE_ROW;
}

}  // namespace

TEST(Migration0003, AddsM03ColumnsAndUniqueIndex) {
    Connection conn = Connection::open_in_memory();
    MigrationRunner runner(conn);
    runner.run_all();

    auto cols = column_names(conn, "engrams");
    EXPECT_TRUE(cols.count("adapter_name"));
    EXPECT_TRUE(cols.count("adapter_version"));
    EXPECT_TRUE(cols.count("source_item_id"));
    EXPECT_TRUE(cols.count("source_version"));
    EXPECT_TRUE(cols.count("chunk_index"));
    EXPECT_TRUE(cols.count("declared_transformations_json"));
    EXPECT_TRUE(cols.count("byte_preserving"));
    EXPECT_TRUE(cols.count("redacted_content"));
    EXPECT_TRUE(cols.count("key_ref"));
    EXPECT_TRUE(cols.count("audit_trail_json"));

    EXPECT_TRUE(has_index(conn, "idx_engrams_source_identity"));
}

TEST(Migration0003, ReRunningMigrationsIsIdempotent) {
    Connection conn = Connection::open_in_memory();
    MigrationRunner runner(conn);
    runner.run_all();
    runner.run_all();  // must not throw, must not duplicate columns
    auto cols = column_names(conn, "engrams");
    // Spot check: still exactly one of each new column
    EXPECT_EQ(cols.count("adapter_name"), 1);
}
```

(If `Connection::open_in_memory` / `prepare` / `column_text` / `bind_text` have slightly different M0.2 names, Task 0 Step 4 surfaced them — adjust the call sites to match. The test SHAPE stays the same.)

- [ ] **Step 2: Run the test to verify it fails**

```bash
cmake --build --preset default
ctest --preset default --output-on-failure -R Migration0003
```
Expected: FAIL — columns not present.

- [ ] **Step 3: Write the migration SQL**

Create `migrations/0003_engram_store_columns.sql`:

```sql
-- M0.3 EngramStore column extensions and source-identity uniqueness.
-- Idempotent: each ALTER guards against re-running by inspecting sqlite_master
-- via a SELECT in the MigrationRunner-managed checksum table.

ALTER TABLE engrams ADD COLUMN adapter_name TEXT NOT NULL DEFAULT '';
ALTER TABLE engrams ADD COLUMN adapter_version TEXT NOT NULL DEFAULT '';
ALTER TABLE engrams ADD COLUMN source_item_id TEXT NOT NULL DEFAULT '';
ALTER TABLE engrams ADD COLUMN source_version TEXT NOT NULL DEFAULT '';
ALTER TABLE engrams ADD COLUMN chunk_index INTEGER NOT NULL DEFAULT 0;
ALTER TABLE engrams ADD COLUMN declared_transformations_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE engrams ADD COLUMN byte_preserving INTEGER NOT NULL DEFAULT 0;
ALTER TABLE engrams ADD COLUMN redacted_content TEXT;
ALTER TABLE engrams ADD COLUMN key_ref TEXT;
ALTER TABLE engrams ADD COLUMN audit_trail_json TEXT NOT NULL DEFAULT '[]';

-- Source idempotency: a producer that re-ingests the same (adapter, item, version, chunk)
-- gets the existing EngramRef back from the validator. SQLite UNIQUE on a multi-column
-- tuple does the dedup at the storage layer if the validator's pre-INSERT SELECT races.
CREATE UNIQUE INDEX IF NOT EXISTS idx_engrams_source_identity
    ON engrams(tenant_id, adapter_name, source_item_id, source_version, chunk_index);
```

**Idempotency note**: SQLite's `ALTER TABLE ADD COLUMN` does NOT have `IF NOT EXISTS`. The `MigrationRunner` (M0.2) already guards re-running by skipping already-applied migrations via the `schema_migrations` checksum table, so the raw `ALTER` is safe as long as the runner respects its own ledger. Task 0 Step 4 confirmed the runner's idempotency contract; trust it.

- [ ] **Step 4: Run the test to verify it passes**

```bash
cmake --build --preset default
ctest --preset default --output-on-failure -R Migration0003
```
Expected: both tests PASS.

- [ ] **Step 5: Verify the full migration suite still passes**

```bash
ctest --preset default --output-on-failure -R Migration
```
Expected: all migration tests PASS (M0.2 migration tests + the two new ones).

- [ ] **Step 6: Commit**

```bash
git add migrations/0003_engram_store_columns.sql tests/cpp/test_migration_0003.cpp \
        tests/cpp/CMakeLists.txt
git commit -m "feat(M0.3): migration 0003 extends engrams with adapter/source identity + UNIQUE index"
```

---

### Task 3: Engram POD + canonical hash

**Files:**
- Create: `include/starling/evidence/engram.hpp`
- Create: `src/evidence/engram.cpp`
- Create: `tests/cpp/test_engram_content_hash.cpp`
- Modify: `CMakeLists.txt` / `tests/cpp/CMakeLists.txt`

**Goal:** `compute_engram_content_hash` is deterministic, includes `declared_transformations` in the hash domain, treats `declared_transformations` as a set (order-independent), and survives a regression test that pins three known input → hash pairs.

- [ ] **Step 1: Write the failing hash test**

Create `tests/cpp/test_engram_content_hash.cpp`:

```cpp
#include <gtest/gtest.h>

#include "starling/evidence/engram.hpp"

#include <string>
#include <vector>

using starling::evidence::compute_engram_content_hash;
using starling::evidence::canonicalize_engram_payload;

namespace {
std::vector<uint8_t> bytes(const std::string& s) {
    return {s.begin(), s.end()};
}
}  // namespace

TEST(EngramContentHash, DifferentPayloadsProduceDifferentHashes) {
    auto a = compute_engram_content_hash(bytes("hello"), {});
    auto b = compute_engram_content_hash(bytes("hellp"), {});
    EXPECT_NE(a, b);
    EXPECT_EQ(a.size(), 64u);  // sha256 hex
}

TEST(EngramContentHash, DeclaredTransformationsAffectHash) {
    auto raw = compute_engram_content_hash(bytes("hello"), {});
    auto normalized = compute_engram_content_hash(bytes("hello"), {"nfc"});
    EXPECT_NE(raw, normalized);
}

TEST(EngramContentHash, TransformationsAreOrderIndependent) {
    auto ab = compute_engram_content_hash(bytes("hello"), {"nfc", "trim"});
    auto ba = compute_engram_content_hash(bytes("hello"), {"trim", "nfc"});
    EXPECT_EQ(ab, ba);
}

TEST(EngramContentHash, PinnedDigests) {
    // Pin three digests so future refactors of canonicalize_engram_payload
    // can't silently change the hash domain.
    EXPECT_EQ(
        compute_engram_content_hash(bytes("hello"), {}),
        // sha256_hex of "v1\x1fhello\x1f"
        // (no transformations → trailing separator with empty suffix)
        // Compute this value once locally and paste here.
        "PLACEHOLDER_PIN_1");
    EXPECT_EQ(
        compute_engram_content_hash(bytes("hello"), {"nfc"}),
        "PLACEHOLDER_PIN_2");
    EXPECT_EQ(
        compute_engram_content_hash(bytes(""), {}),
        "PLACEHOLDER_PIN_3");
}
```

**Pin generation**: the three `PLACEHOLDER_PIN_N` values are computed by running a one-shot Python script after Step 3 implements the canonicalizer:
```python
import hashlib
def h(payload: bytes, transforms: list[str]) -> str:
    body = b"v1\x1f" + payload + b"\x1f" + "\x1f".join(sorted(set(transforms))).encode()
    return hashlib.sha256(body).hexdigest()
print(h(b"hello", []))
print(h(b"hello", ["nfc"]))
print(h(b"", []))
```
Paste the three resulting hex strings into the test file. Re-running Step 1 with the placeholders replaced is part of Step 3's "make-the-test-pass" loop.

- [ ] **Step 2: Run the test to verify it fails**

```bash
ctest --preset default --output-on-failure -R EngramContentHash
```
Expected: link error (`compute_engram_content_hash` not defined).

- [ ] **Step 3: Write the header**

Create `include/starling/evidence/engram.hpp` with the full content from Subsystem Contract B above. Verbatim re-paste:

```cpp
#pragma once

#include "starling/schema/enums.hpp"

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace starling::evidence {

struct SourceIdentity {
    std::string adapter_name;
    std::string adapter_version;
    std::string source_item_id;
    std::string source_version;
    int32_t     chunk_index = 0;
};

struct EngramInput {
    std::string                 tenant_id;
    SourceIdentity              source;
    schema::SourceKind          source_kind;
    schema::IngestMode          ingest_mode;
    schema::PrivacyClass        privacy_class;
    schema::EngramRetentionMode retention_mode;
    std::vector<std::string>    declared_transformations;
    bool                        byte_preserving = false;
    std::vector<uint8_t>        payload_bytes;
    std::optional<std::string>  redacted_content;
    std::string                 created_at_iso8601;
};

struct Engram {
    std::string                 id;
    std::string                 tenant_id;
    SourceIdentity              source;
    schema::SourceKind          source_kind;
    schema::IngestPolicy        ingest_policy;
    schema::IngestMode          ingest_mode;
    schema::PrivacyClass        privacy_class;
    schema::EngramRetentionMode retention_mode;
    std::vector<std::string>    declared_transformations;
    bool                        byte_preserving = false;
    std::string                 content_hash;
    std::optional<std::string>  key_ref;
    std::vector<uint8_t>        content_ciphertext;
    std::optional<std::string>  redacted_content;
    int64_t                     refcount = 0;
    std::string                 created_at_iso8601;
    std::optional<std::string>  erased_at_iso8601;
};

struct EngramRef {
    std::string                 id;
    std::string                 content_hash;
    schema::EngramRetentionMode retention_mode;
};

std::string canonicalize_engram_payload(
    const std::vector<uint8_t>& payload_bytes,
    const std::vector<std::string>& declared_transformations);

std::string compute_engram_content_hash(
    const std::vector<uint8_t>& payload_bytes,
    const std::vector<std::string>& declared_transformations);

}  // namespace starling::evidence
```

- [ ] **Step 4: Write the implementation**

Create `src/evidence/engram.cpp`:

```cpp
#include "starling/evidence/engram.hpp"
#include "starling/crypto/sha256.hpp"

#include <algorithm>
#include <set>
#include <string>
#include <vector>

namespace starling::evidence {

std::string canonicalize_engram_payload(
    const std::vector<uint8_t>& payload_bytes,
    const std::vector<std::string>& declared_transformations) {

    // Deduplicate + sort transformations so producer tuple order doesn't change
    // the hash. A set is the right shape semantically.
    std::set<std::string> sorted_unique(
        declared_transformations.begin(), declared_transformations.end());

    std::string out;
    out.reserve(3 + payload_bytes.size() + 64);  // "v1\x1f" + payload + sep + ~transforms
    out.append("v1\x1f");
    out.append(reinterpret_cast<const char*>(payload_bytes.data()),
               payload_bytes.size());
    out.push_back('\x1f');

    bool first = true;
    for (const auto& t : sorted_unique) {
        if (!first) out.push_back('\x1f');
        out.append(t);
        first = false;
    }
    return out;
}

std::string compute_engram_content_hash(
    const std::vector<uint8_t>& payload_bytes,
    const std::vector<std::string>& declared_transformations) {
    auto canonical = canonicalize_engram_payload(payload_bytes, declared_transformations);
    return starling::crypto::sha256_hex(canonical);
}

}  // namespace starling::evidence
```

- [ ] **Step 5: Generate the pinned digests and update the test**

Run the Python one-liner from Step 1's "Pin generation" note. Paste the three hex strings into `tests/cpp/test_engram_content_hash.cpp` replacing `PLACEHOLDER_PIN_1/2/3`.

- [ ] **Step 6: Run the test to verify it passes**

```bash
cmake --build --preset default
ctest --preset default --output-on-failure -R EngramContentHash
```
Expected: 4 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add include/starling/evidence/engram.hpp src/evidence/engram.cpp \
        tests/cpp/test_engram_content_hash.cpp CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -m "feat(M0.3): Engram POD + content_hash canonicalizer (v1; includes declared_transformations)"
```

---

### Task 4: IngestPolicyResolver

**Files:**
- Create: `include/starling/evidence/ingest_policy_resolver.hpp`
- Create: `src/evidence/ingest_policy_resolver.cpp`
- Create: `tests/cpp/test_ingest_policy_resolver.cpp`

**Goal:** The resolver matches the §3.7 table from Subsystem Contract C, with self-pollution always winning over producer intent.

- [ ] **Step 1: Write the failing test**

Create `tests/cpp/test_ingest_policy_resolver.cpp`:

```cpp
#include <gtest/gtest.h>

#include "starling/evidence/ingest_policy_resolver.hpp"

using starling::evidence::IngestPolicyResolver;
using starling::schema::IngestPolicy;
using starling::schema::PrivacyClass;
using starling::schema::SourceKind;

TEST(IngestPolicyResolver, UserInputPublicStoreStaysStore) {
    EXPECT_EQ(
        IngestPolicyResolver::resolve(
            SourceKind::USER_INPUT, PrivacyClass::PUBLIC, IngestPolicy::STORE),
        IngestPolicy::STORE);
}

TEST(IngestPolicyResolver, UserInputRegulatedDowngradesToRequireReview) {
    EXPECT_EQ(
        IngestPolicyResolver::resolve(
            SourceKind::USER_INPUT, PrivacyClass::REGULATED, IngestPolicy::STORE),
        IngestPolicy::REQUIRE_REVIEW);
}

TEST(IngestPolicyResolver, ExternalDocSensitiveDowngradesToRequireReview) {
    EXPECT_EQ(
        IngestPolicyResolver::resolve(
            SourceKind::EXTERNAL_DOC, PrivacyClass::SENSITIVE, IngestPolicy::STORE),
        IngestPolicy::REQUIRE_REVIEW);
}

TEST(IngestPolicyResolver, ToolObservationDowngradesStoreToMetadataOnly) {
    EXPECT_EQ(
        IngestPolicyResolver::resolve(
            SourceKind::TOOL_OBSERVATION, PrivacyClass::INTERNAL, IngestPolicy::STORE),
        IngestPolicy::STORE_METADATA_ONLY);
}

TEST(IngestPolicyResolver, SystemInternalAlwaysNoStore) {
    for (auto privacy : {PrivacyClass::PUBLIC, PrivacyClass::INTERNAL,
                         PrivacyClass::PERSONAL, PrivacyClass::SENSITIVE,
                         PrivacyClass::REGULATED}) {
        for (auto declared : {IngestPolicy::STORE,
                              IngestPolicy::STORE_METADATA_ONLY,
                              IngestPolicy::REQUIRE_REVIEW,
                              IngestPolicy::NO_STORE}) {
            EXPECT_EQ(
                IngestPolicyResolver::resolve(
                    SourceKind::SYSTEM_INTERNAL, privacy, declared),
                IngestPolicy::NO_STORE)
                << "privacy=" << static_cast<int>(privacy)
                << " declared=" << static_cast<int>(declared);
        }
    }
}

TEST(IngestPolicyResolver, ObserverAgentAlwaysNoStore) {
    EXPECT_EQ(
        IngestPolicyResolver::resolve(
            SourceKind::OBSERVER_AGENT, PrivacyClass::PUBLIC, IngestPolicy::STORE),
        IngestPolicy::NO_STORE);
}

TEST(IngestPolicyResolver, ReplayOutputAlwaysNoStore) {
    EXPECT_EQ(
        IngestPolicyResolver::resolve(
            SourceKind::REPLAY_OUTPUT, PrivacyClass::INTERNAL, IngestPolicy::STORE),
        IngestPolicy::NO_STORE);
}

TEST(IngestPolicyResolver, ProducerDeclaredNoStoreIsHonored) {
    // user_input + producer explicitly says NO_STORE → NO_STORE.
    // The resolver doesn't promote NO_STORE to STORE; producer-declared
    // NO_STORE is final for non-storeworthy source_kinds too.
    EXPECT_EQ(
        IngestPolicyResolver::resolve(
            SourceKind::USER_INPUT, PrivacyClass::PUBLIC, IngestPolicy::NO_STORE),
        IngestPolicy::NO_STORE);
}
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
ctest --preset default --output-on-failure -R IngestPolicyResolver
```
Expected: link error.

- [ ] **Step 3: Write the resolver**

Create `include/starling/evidence/ingest_policy_resolver.hpp` (verbatim from Subsystem Contract C above).

Create `src/evidence/ingest_policy_resolver.cpp`:

```cpp
#include "starling/evidence/ingest_policy_resolver.hpp"

namespace starling::evidence {

schema::IngestPolicy IngestPolicyResolver::resolve(
    schema::SourceKind source_kind,
    schema::PrivacyClass privacy_class,
    schema::IngestPolicy producer_declared) {
    using SK = schema::SourceKind;
    using PC = schema::PrivacyClass;
    using IP = schema::IngestPolicy;

    // Producer-declared NO_STORE is always honored.
    if (producer_declared == IP::NO_STORE) return IP::NO_STORE;

    // Self-pollution guard: these source kinds are always NO_STORE regardless
    // of producer intent or privacy_class. §3.7 line 1094.
    if (source_kind == SK::SYSTEM_INTERNAL  ||
        source_kind == SK::OBSERVER_AGENT  ||
        source_kind == SK::REPLAY_OUTPUT) {
        return IP::NO_STORE;
    }

    // Producer-declared REQUIRE_REVIEW or STORE_METADATA_ONLY are honored as
    // explicit downgrades (producer knows something the table doesn't).
    if (producer_declared == IP::REQUIRE_REVIEW ||
        producer_declared == IP::STORE_METADATA_ONLY) {
        // tool_observation can downgrade STORE_METADATA_ONLY to itself (no-op);
        // there's no "downgrade further" for REQUIRE_REVIEW.
        if (source_kind == SK::TOOL_OBSERVATION &&
            producer_declared == IP::STORE_METADATA_ONLY) {
            return IP::STORE_METADATA_ONLY;
        }
        return producer_declared;
    }

    // From here, producer_declared == STORE.
    // tool_observation always downgrades STORE to STORE_METADATA_ONLY (§3.7).
    if (source_kind == SK::TOOL_OBSERVATION) {
        return IP::STORE_METADATA_ONLY;
    }

    // Privacy-driven downgrades for user_input / external_doc.
    if (privacy_class == PC::REGULATED) {
        // Regulated always needs human review before being treated as STORE.
        return IP::REQUIRE_REVIEW;
    }
    if (source_kind == SK::EXTERNAL_DOC && privacy_class == PC::SENSITIVE) {
        return IP::REQUIRE_REVIEW;
    }

    return IP::STORE;
}

}  // namespace starling::evidence
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cmake --build --preset default
ctest --preset default --output-on-failure -R IngestPolicyResolver
```
Expected: 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add include/starling/evidence/ingest_policy_resolver.hpp \
        src/evidence/ingest_policy_resolver.cpp \
        tests/cpp/test_ingest_policy_resolver.cpp \
        CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -m "feat(M0.3): IngestPolicyResolver with self-pollution guard"
```

---

### Task 5: EvidenceValidator

**Files:**
- Create: `include/starling/evidence/evidence_validator.hpp`
- Create: `src/evidence/evidence_validator.cpp`
- Create: `tests/cpp/test_evidence_validator.cpp`

**Goal:** EvidenceValidator orchestrates schema-shape checks → policy resolution → idempotency lookup → outcome variant. Idempotency lookup runs inside the caller's open transaction.

- [ ] **Step 1: Write the failing test**

Create `tests/cpp/test_evidence_validator.cpp`:

```cpp
#include <gtest/gtest.h>

#include "starling/evidence/evidence_validator.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/migration_runner.hpp"

#include <variant>

using starling::evidence::EngramInput;
using starling::evidence::EvidenceValidator;
using starling::evidence::SourceIdentity;
using starling::evidence::ValidationIdempotentHit;
using starling::evidence::ValidationNoStore;
using starling::evidence::ValidationProceed;
using starling::evidence::ValidationReject;
using starling::persistence::Connection;
using starling::persistence::MigrationRunner;
using starling::schema::EngramRetentionMode;
using starling::schema::IngestMode;
using starling::schema::IngestPolicy;
using starling::schema::PrivacyClass;
using starling::schema::SourceKind;

namespace {

EngramInput valid_user_input() {
    return EngramInput{
        .tenant_id = "t1",
        .source = SourceIdentity{
            .adapter_name = "direct_api",
            .adapter_version = "1.0.0",
            .source_item_id = "msg-1",
            .source_version = "1",
            .chunk_index = 0,
        },
        .source_kind = SourceKind::USER_INPUT,
        .ingest_mode = IngestMode::WHOLE_RECORD,
        .privacy_class = PrivacyClass::INTERNAL,
        .retention_mode = EngramRetentionMode::AUDIT_RETAIN,
        .declared_transformations = {},
        .byte_preserving = true,
        .payload_bytes = {'h','i'},
        .redacted_content = std::nullopt,
        .created_at_iso8601 = "2026-05-23T10:00:00Z",
    };
}

Connection migrated_db() {
    Connection conn = Connection::open_in_memory();
    MigrationRunner(conn).run_all();
    return conn;
}

}  // namespace

TEST(EvidenceValidator, ValidUserInputProceedsAsStore) {
    auto conn = migrated_db();
    auto out = EvidenceValidator::validate(valid_user_input(), conn);
    auto* proceed = std::get_if<ValidationProceed>(&out);
    ASSERT_NE(proceed, nullptr);
    EXPECT_EQ(proceed->resolved_policy, IngestPolicy::STORE);
}

TEST(EvidenceValidator, SystemInternalShortCircuitsToNoStore) {
    auto conn = migrated_db();
    auto inp = valid_user_input();
    inp.source_kind = SourceKind::SYSTEM_INTERNAL;
    auto out = EvidenceValidator::validate(inp, conn);
    EXPECT_NE(std::get_if<ValidationNoStore>(&out), nullptr);
}

TEST(EvidenceValidator, BytePreservingWithTransformationsRejects) {
    auto conn = migrated_db();
    auto inp = valid_user_input();
    inp.byte_preserving = true;
    inp.declared_transformations = {"nfc"};
    auto out = EvidenceValidator::validate(inp, conn);
    auto* rej = std::get_if<ValidationReject>(&out);
    ASSERT_NE(rej, nullptr);
    EXPECT_EQ(rej->reason, "byte_preserving_requires_empty_transformations");
}

TEST(EvidenceValidator, DuplicateTransformationsReject) {
    auto conn = migrated_db();
    auto inp = valid_user_input();
    inp.byte_preserving = false;
    inp.declared_transformations = {"nfc", "trim", "nfc"};
    auto out = EvidenceValidator::validate(inp, conn);
    auto* rej = std::get_if<ValidationReject>(&out);
    ASSERT_NE(rej, nullptr);
    EXPECT_EQ(rej->reason, "transformations_must_be_unique");
}

TEST(EvidenceValidator, RequiredFieldMissingRejects) {
    auto conn = migrated_db();
    auto inp = valid_user_input();
    inp.tenant_id = "";
    auto out = EvidenceValidator::validate(inp, conn);
    auto* rej = std::get_if<ValidationReject>(&out);
    ASSERT_NE(rej, nullptr);
    EXPECT_EQ(rej->reason, "required_field_missing:tenant_id");
}

TEST(EvidenceValidator, RegulatedUserInputDowngradesToRequireReview) {
    auto conn = migrated_db();
    auto inp = valid_user_input();
    inp.privacy_class = PrivacyClass::REGULATED;
    auto out = EvidenceValidator::validate(inp, conn);
    auto* proceed = std::get_if<ValidationProceed>(&out);
    ASSERT_NE(proceed, nullptr);
    EXPECT_EQ(proceed->resolved_policy, IngestPolicy::REQUIRE_REVIEW);
}

TEST(EvidenceValidator, IdempotentHitReturnsExistingRow) {
    auto conn = migrated_db();
    // Insert a row manually that matches valid_user_input's identity tuple.
    auto stmt = conn.prepare(
        "INSERT INTO engrams("
        "  id, tenant_id, content_hash, source_kind, ingest_policy, ingest_mode,"
        "  privacy_class, retention_mode, created_at,"
        "  adapter_name, adapter_version, source_item_id, source_version, chunk_index,"
        "  declared_transformations_json, byte_preserving"
        ") VALUES ("
        "  'pre-existing-id', 't1', 'deadbeef', 'user_input', 'store', 'whole_record',"
        "  'internal', 'audit_retain', '2026-05-23T09:00:00Z',"
        "  'direct_api', '1.0.0', 'msg-1', '1', 0,"
        "  '[]', 1"
        ");");
    stmt.step_done();

    auto out = EvidenceValidator::validate(valid_user_input(), conn);
    auto* hit = std::get_if<ValidationIdempotentHit>(&out);
    ASSERT_NE(hit, nullptr);
    EXPECT_EQ(hit->existing.id, "pre-existing-id");
    EXPECT_EQ(hit->existing.content_hash, "deadbeef");
}
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
ctest --preset default --output-on-failure -R EvidenceValidator
```
Expected: link error.

- [ ] **Step 3: Write the validator**

Create `include/starling/evidence/evidence_validator.hpp` (verbatim from Subsystem Contract D).

Create `src/evidence/evidence_validator.cpp`:

```cpp
#include "starling/evidence/evidence_validator.hpp"
#include "starling/evidence/ingest_policy_resolver.hpp"

#include <chrono>
#include <set>
#include <sstream>
#include <string>

namespace starling::evidence {

namespace {

bool is_iso8601_utc(const std::string& s) {
    // P1 minimal: require trailing 'Z' and a 'T' separator. A full RFC3339
    // parser belongs in M0.x; the M0.1 helper (if present) can replace this.
    return s.size() >= 20 && s.find('T') != std::string::npos && s.back() == 'Z';
}

ValidationOutcome make_reject(std::string reason) {
    return ValidationReject{std::move(reason)};
}

}  // namespace

ValidationOutcome EvidenceValidator::validate(
    const EngramInput& input,
    starling::persistence::Connection& conn) {

    // 1. Schema-shape checks (cheap, no DB).
    if (input.byte_preserving && !input.declared_transformations.empty()) {
        return make_reject("byte_preserving_requires_empty_transformations");
    }
    {
        std::set<std::string> seen;
        for (const auto& t : input.declared_transformations) {
            if (!seen.insert(t).second) {
                return make_reject("transformations_must_be_unique");
            }
        }
    }
    if (input.tenant_id.empty())
        return make_reject("required_field_missing:tenant_id");
    if (input.source.adapter_name.empty())
        return make_reject("required_field_missing:adapter_name");
    if (input.source.source_item_id.empty())
        return make_reject("required_field_missing:source_item_id");
    if (input.source.source_version.empty())
        return make_reject("required_field_missing:source_version");
    if (!is_iso8601_utc(input.created_at_iso8601))
        return make_reject("created_at_not_iso8601");

    // 2. Resolve IngestPolicy.
    auto resolved = IngestPolicyResolver::resolve(
        input.source_kind, input.privacy_class, schema::IngestPolicy::STORE);

    // 3. NO_STORE short-circuits before the idempotency lookup.
    if (resolved == schema::IngestPolicy::NO_STORE) {
        return ValidationNoStore{};
    }

    // 4. Source idempotency lookup within the caller's transaction.
    auto stmt = conn.prepare(
        "SELECT id, content_hash, source_kind, ingest_policy, ingest_mode,"
        "       privacy_class, retention_mode, adapter_version,"
        "       declared_transformations_json, byte_preserving,"
        "       redacted_content, created_at"
        "  FROM engrams"
        " WHERE tenant_id = ? AND adapter_name = ? AND source_item_id = ?"
        "   AND source_version = ? AND chunk_index = ?");
    stmt.bind_text(1, input.tenant_id);
    stmt.bind_text(2, input.source.adapter_name);
    stmt.bind_text(3, input.source.source_item_id);
    stmt.bind_text(4, input.source.source_version);
    stmt.bind_int(5, input.source.chunk_index);

    if (stmt.step() == SQLITE_ROW) {
        Engram existing;
        existing.id            = stmt.column_text(0);
        existing.content_hash  = stmt.column_text(1);
        existing.tenant_id     = input.tenant_id;
        existing.source        = input.source;
        existing.source_kind   = schema::source_kind_from_string(stmt.column_text(2));
        existing.ingest_policy = schema::ingest_policy_from_string(stmt.column_text(3));
        existing.ingest_mode   = schema::ingest_mode_from_string(stmt.column_text(4));
        existing.privacy_class = schema::privacy_class_from_string(stmt.column_text(5));
        existing.retention_mode= schema::engram_retention_mode_from_string(stmt.column_text(6));
        existing.source.adapter_version = stmt.column_text(7);
        // declared_transformations_json / byte_preserving / redacted_content / created_at
        // populated for completeness; callers usually only need id + content_hash + retention_mode.
        existing.byte_preserving        = stmt.column_int(9) != 0;
        if (!stmt.column_is_null(10))
            existing.redacted_content = stmt.column_text(10);
        existing.created_at_iso8601     = stmt.column_text(11);
        return ValidationIdempotentHit{std::move(existing)};
    }

    // 5. Proceed.
    return ValidationProceed{resolved};
}

}  // namespace starling::evidence
```

(If the M0.2 `Connection`/`Statement` wrapper exposes different method names — `column_text` vs `column_string`, `column_is_null` vs `is_null` — adjust to match what Task 0 Step 4 surfaced.)

- [ ] **Step 4: Run the test to verify it passes**

```bash
cmake --build --preset default
ctest --preset default --output-on-failure -R EvidenceValidator
```
Expected: 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add include/starling/evidence/evidence_validator.hpp \
        src/evidence/evidence_validator.cpp \
        tests/cpp/test_evidence_validator.cpp \
        CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -m "feat(M0.3): EvidenceValidator (schema checks + policy + idempotency lookup)"
```

---

### Task 6: null_kms placeholder + EngramStore.put/get

**Files:**
- Create: `include/starling/crypto/null_kms.hpp`
- Create: `include/starling/evidence/engram_store.hpp`
- Create: `src/evidence/engram_store.cpp`
- Create: `tests/cpp/test_engram_store.cpp`

**Goal:** `EngramStore::put` persists a row inside a caller-supplied transaction, computes UUIDv4 id, sets content_hash via the canonicalizer, writes raw payload bytes to `payload_inline`. `EngramStore::get(id, tenant_id)` round-trips the row.

- [ ] **Step 1: Write the failing test**

Create `tests/cpp/test_engram_store.cpp`:

```cpp
#include <gtest/gtest.h>

#include "starling/evidence/engram_store.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/migration_runner.hpp"

using starling::evidence::Engram;
using starling::evidence::EngramInput;
using starling::evidence::EngramStore;
using starling::evidence::SourceIdentity;
using starling::persistence::Connection;
using starling::persistence::MigrationRunner;
using starling::schema::EngramRetentionMode;
using starling::schema::IngestMode;
using starling::schema::IngestPolicy;
using starling::schema::PrivacyClass;
using starling::schema::SourceKind;

namespace {

Connection migrated_db() {
    Connection conn = Connection::open_in_memory();
    MigrationRunner(conn).run_all();
    return conn;
}

EngramInput sample_input() {
    return EngramInput{
        .tenant_id = "t1",
        .source = SourceIdentity{
            .adapter_name = "direct_api",
            .adapter_version = "1.0.0",
            .source_item_id = "msg-1",
            .source_version = "1",
            .chunk_index = 0,
        },
        .source_kind = SourceKind::USER_INPUT,
        .ingest_mode = IngestMode::WHOLE_RECORD,
        .privacy_class = PrivacyClass::INTERNAL,
        .retention_mode = EngramRetentionMode::AUDIT_RETAIN,
        .declared_transformations = {},
        .byte_preserving = true,
        .payload_bytes = {'h','e','l','l','o'},
        .redacted_content = std::nullopt,
        .created_at_iso8601 = "2026-05-23T10:00:00Z",
    };
}

}  // namespace

TEST(EngramStore, PutAssignsUuidAndContentHash) {
    auto conn = migrated_db();
    auto e = EngramStore::put(sample_input(), IngestPolicy::STORE, conn);
    EXPECT_FALSE(e.id.empty());
    EXPECT_EQ(e.id.size(), 36u);  // UUID 8-4-4-4-12 hex chars
    EXPECT_EQ(e.content_hash.size(), 64u);  // sha256 hex
    EXPECT_EQ(e.ingest_policy, IngestPolicy::STORE);
}

TEST(EngramStore, GetRoundTrips) {
    auto conn = migrated_db();
    auto written = EngramStore::put(sample_input(), IngestPolicy::STORE, conn);
    auto fetched = EngramStore::get(written.id, "t1", conn);
    ASSERT_TRUE(fetched.has_value());
    EXPECT_EQ(fetched->id, written.id);
    EXPECT_EQ(fetched->content_hash, written.content_hash);
    EXPECT_EQ(fetched->source.adapter_name, "direct_api");
    EXPECT_EQ(fetched->source.chunk_index, 0);
    EXPECT_EQ(fetched->ingest_policy, IngestPolicy::STORE);
    EXPECT_EQ(fetched->retention_mode, EngramRetentionMode::AUDIT_RETAIN);
    // payload_inline round-trips
    EXPECT_EQ(fetched->content_ciphertext,
              (std::vector<uint8_t>{'h','e','l','l','o'}));
}

TEST(EngramStore, GetReturnsNulloptForWrongTenant) {
    auto conn = migrated_db();
    auto written = EngramStore::put(sample_input(), IngestPolicy::STORE, conn);
    auto fetched = EngramStore::get(written.id, "t2", conn);
    EXPECT_FALSE(fetched.has_value());
}

TEST(EngramStore, PutRejectsDuplicateSourceIdentity) {
    auto conn = migrated_db();
    EngramStore::put(sample_input(), IngestPolicy::STORE, conn);
    // Second put with identical source identity should hit the UNIQUE index.
    // EngramStore::put does NOT pre-check (that's EvidenceValidator's job),
    // so a direct second call should throw.
    EXPECT_THROW(
        EngramStore::put(sample_input(), IngestPolicy::STORE, conn),
        std::exception);
}
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
ctest --preset default --output-on-failure -R EngramStore
```
Expected: link error.

- [ ] **Step 3: Write the null_kms placeholder**

Create `include/starling/crypto/null_kms.hpp`:

```cpp
#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace starling::crypto {

// P1 placeholder. M0.4+ replaces with a real AES-256-GCM + KMS adapter.
// The call site in EngramStore stays the same when the swap happens.
class NullKms {
public:
    // Returns payload unchanged. "Encryption" in P1 is identity.
    static std::vector<uint8_t> encrypt(const std::vector<uint8_t>& payload,
                                        const std::string& /*key_ref*/) {
        return payload;
    }

    // Always returns std::nullopt — no key is generated, key_ref column stays NULL.
    static std::optional<std::string> generate_key_ref() {
        return std::nullopt;
    }
};

}  // namespace starling::crypto
```

- [ ] **Step 4: Write the EngramStore header + implementation**

Create `include/starling/evidence/engram_store.hpp` (verbatim from Subsystem Contract E).

Create `src/evidence/engram_store.cpp`:

```cpp
#include "starling/evidence/engram_store.hpp"
#include "starling/crypto/null_kms.hpp"
#include "starling/evidence/engram.hpp"

#include <random>
#include <sstream>
#include <iomanip>
#include <stdexcept>
#include <string>

namespace starling::evidence {

namespace {

std::string generate_uuid_v4() {
    // P1 uses std::random_device + RFC4122 variant bits. M0.4 may switch to
    // UUIDv7 for time-ordered ids if Bus.write performance requires it.
    static thread_local std::mt19937_64 rng{std::random_device{}()};
    auto a = rng();
    auto b = rng();
    // Set RFC4122 version 4 (random) and variant 10xx.
    uint8_t bytes[16];
    for (int i = 0; i < 8; ++i) bytes[i]     = (a >> (i * 8)) & 0xff;
    for (int i = 0; i < 8; ++i) bytes[i + 8] = (b >> (i * 8)) & 0xff;
    bytes[6] = (bytes[6] & 0x0f) | 0x40;  // version 4
    bytes[8] = (bytes[8] & 0x3f) | 0x80;  // variant 10xx

    std::ostringstream out;
    out << std::hex << std::setfill('0');
    for (int i = 0; i < 16; ++i) {
        out << std::setw(2) << static_cast<int>(bytes[i]);
        if (i == 3 || i == 5 || i == 7 || i == 9) out << '-';
    }
    return out.str();
}

std::string transformations_json(const std::vector<std::string>& t) {
    std::string out = "[";
    bool first = true;
    for (const auto& s : t) {
        if (!first) out.push_back(',');
        out.push_back('"');
        // P1: transformation strings are ASCII identifiers (validator
        // enforces non-duplicate, and adapter-conformance defines the set).
        // No JSON escaping needed for the P1 vocabulary.
        out.append(s);
        out.push_back('"');
        first = false;
    }
    out.push_back(']');
    return out;
}

}  // namespace

Engram EngramStore::put(
    const EngramInput& input,
    schema::IngestPolicy resolved_policy,
    starling::persistence::Connection& conn) {

    if (resolved_policy == schema::IngestPolicy::NO_STORE) {
        throw std::invalid_argument(
            "EngramStore::put called with NO_STORE; caller must short-circuit");
    }

    Engram e;
    e.id                       = generate_uuid_v4();
    e.tenant_id                = input.tenant_id;
    e.source                   = input.source;
    e.source_kind              = input.source_kind;
    e.ingest_policy            = resolved_policy;
    e.ingest_mode              = input.ingest_mode;
    e.privacy_class            = input.privacy_class;
    e.retention_mode           = input.retention_mode;
    e.declared_transformations = input.declared_transformations;
    e.byte_preserving          = input.byte_preserving;
    e.content_hash             = compute_engram_content_hash(
                                     input.payload_bytes,
                                     input.declared_transformations);
    e.key_ref                  = starling::crypto::NullKms::generate_key_ref();
    e.content_ciphertext       = starling::crypto::NullKms::encrypt(
                                     input.payload_bytes, /*key_ref=*/"");
    e.redacted_content         = input.redacted_content;
    e.refcount                 = 0;
    e.created_at_iso8601       = input.created_at_iso8601;
    e.erased_at_iso8601        = std::nullopt;

    auto stmt = conn.prepare(
        "INSERT INTO engrams("
        "  id, tenant_id, content_hash, source_kind, ingest_policy, ingest_mode,"
        "  privacy_class, retention_mode, refcount, payload_uri, payload_inline,"
        "  created_at, erased_at,"
        "  adapter_name, adapter_version, source_item_id, source_version, chunk_index,"
        "  declared_transformations_json, byte_preserving, redacted_content,"
        "  key_ref, audit_trail_json"
        ") VALUES ("
        "  ?, ?, ?, ?, ?, ?,"
        "  ?, ?, 0, NULL, ?,"
        "  ?, NULL,"
        "  ?, ?, ?, ?, ?,"
        "  ?, ?, ?,"
        "  NULL, '[]'"
        ");");

    int i = 1;
    stmt.bind_text(i++, e.id);
    stmt.bind_text(i++, e.tenant_id);
    stmt.bind_text(i++, e.content_hash);
    stmt.bind_text(i++, std::string(schema::to_string(e.source_kind)));
    stmt.bind_text(i++, std::string(schema::to_string(e.ingest_policy)));
    stmt.bind_text(i++, std::string(schema::to_string(e.ingest_mode)));
    stmt.bind_text(i++, std::string(schema::to_string(e.privacy_class)));
    stmt.bind_text(i++, std::string(schema::to_string(e.retention_mode)));
    stmt.bind_blob(i++, e.content_ciphertext);  // payload_inline
    stmt.bind_text(i++, e.created_at_iso8601);
    stmt.bind_text(i++, e.source.adapter_name);
    stmt.bind_text(i++, e.source.adapter_version);
    stmt.bind_text(i++, e.source.source_item_id);
    stmt.bind_text(i++, e.source.source_version);
    stmt.bind_int (i++, e.source.chunk_index);
    stmt.bind_text(i++, transformations_json(e.declared_transformations));
    stmt.bind_int (i++, e.byte_preserving ? 1 : 0);
    if (e.redacted_content) stmt.bind_text(i++, *e.redacted_content);
    else                    stmt.bind_null(i++);

    stmt.step_done();
    return e;
}

std::optional<Engram> EngramStore::get(
    std::string_view id,
    std::string_view tenant_id,
    starling::persistence::Connection& conn) {

    auto stmt = conn.prepare(
        "SELECT id, tenant_id, content_hash, source_kind, ingest_policy, ingest_mode,"
        "       privacy_class, retention_mode, refcount, payload_inline,"
        "       created_at, erased_at,"
        "       adapter_name, adapter_version, source_item_id, source_version, chunk_index,"
        "       declared_transformations_json, byte_preserving, redacted_content, key_ref"
        "  FROM engrams"
        " WHERE id = ? AND tenant_id = ?;");
    stmt.bind_text(1, std::string(id));
    stmt.bind_text(2, std::string(tenant_id));

    if (stmt.step() != SQLITE_ROW) return std::nullopt;

    Engram e;
    int c = 0;
    e.id              = stmt.column_text(c++);
    e.tenant_id       = stmt.column_text(c++);
    e.content_hash    = stmt.column_text(c++);
    e.source_kind     = schema::source_kind_from_string(stmt.column_text(c++));
    e.ingest_policy   = schema::ingest_policy_from_string(stmt.column_text(c++));
    e.ingest_mode     = schema::ingest_mode_from_string(stmt.column_text(c++));
    e.privacy_class   = schema::privacy_class_from_string(stmt.column_text(c++));
    e.retention_mode  = schema::engram_retention_mode_from_string(stmt.column_text(c++));
    e.refcount        = stmt.column_int64(c++);
    e.content_ciphertext = stmt.column_blob(c++);
    e.created_at_iso8601 = stmt.column_text(c++);
    if (!stmt.column_is_null(c)) e.erased_at_iso8601 = stmt.column_text(c);
    c++;
    e.source.adapter_name    = stmt.column_text(c++);
    e.source.adapter_version = stmt.column_text(c++);
    e.source.source_item_id  = stmt.column_text(c++);
    e.source.source_version  = stmt.column_text(c++);
    e.source.chunk_index     = stmt.column_int(c++);
    // declared_transformations_json: P1 leaves the field unparsed on the Engram
    // POD (the JSON string round-trips elsewhere); we drop it here for brevity.
    c++;  // skip declared_transformations_json
    e.byte_preserving = stmt.column_int(c++) != 0;
    if (!stmt.column_is_null(c)) e.redacted_content = stmt.column_text(c);
    c++;
    if (!stmt.column_is_null(c)) e.key_ref = stmt.column_text(c);
    c++;

    return e;
}

}  // namespace starling::evidence
```

- [ ] **Step 5: Run the test to verify it passes**

```bash
cmake --build --preset default
ctest --preset default --output-on-failure -R EngramStore
```
Expected: 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add include/starling/crypto/null_kms.hpp \
        include/starling/evidence/engram_store.hpp \
        src/evidence/engram_store.cpp \
        tests/cpp/test_engram_store.cpp \
        CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -m "feat(M0.3): EngramStore put/get with null_kms placeholder; payload stored in payload_inline"
```

---

### Task 7: OutboxWriter.append_already_delivered + audit event helpers

**Files:**
- Modify: `include/starling/bus/outbox_writer.hpp` (if Task 0 found the method only on the dispatcher)
- Modify: `src/bus/outbox_writer.cpp`
- Modify: `tests/cpp/test_outbox_writer.cpp` (add coverage for the new method if not present)

**Goal:** `OutboxWriter` has a public `append_already_delivered(event, conn)` that inserts a row with `dispatch_status='delivered'`. Bus.append_evidence uses this for the audit-only `evidence.no_store_audit` and `evidence.idempotent_hit` rows.

**If Task 0 Step 4 confirmed `OutboxWriter::append_already_delivered` already exists on the writer's public API (M0.2 plan Subsystem Contract C explicitly references it for `system.delivery_failed`)**, skip to Step 4 — only add tests if coverage is missing.

- [ ] **Step 1: Write a test confirming the method's existence + behavior**

Edit `tests/cpp/test_outbox_writer.cpp` and append:

```cpp
TEST(OutboxWriter, AppendAlreadyDeliveredMarksRowDeliveredAndClaimsSequence) {
    auto conn = migrated_db();  // helper from the existing file
    starling::bus::BusEvent e;
    e.event_id        = "evt-1";
    e.tenant_id       = "t1";
    e.event_type      = "evidence.no_store_audit";
    e.primary_id      = "src-abc";
    e.aggregate_id    = "src-abc";
    e.causation_chain = {};
    e.idempotency_key = "deadbeef";
    e.payload_json    = "{}";
    e.created_at      = "2026-05-23T10:00:00Z";
    e.version         = "v1";

    starling::bus::OutboxWriter::append_already_delivered(e, conn);

    auto stmt = conn.prepare(
        "SELECT dispatch_status, outbox_sequence FROM bus_events WHERE event_id = ?;");
    stmt.bind_text(1, "evt-1");
    ASSERT_EQ(stmt.step(), SQLITE_ROW);
    EXPECT_EQ(stmt.column_text(0), "delivered");
    EXPECT_GE(stmt.column_int64(1), 1);
}
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
ctest --preset default --output-on-failure -R OutboxWriter.AppendAlready
```
Expected: link error if the method doesn't exist; row check fails if it exists but doesn't set `delivered`.

- [ ] **Step 3: Add `append_already_delivered` to the writer**

If absent from `include/starling/bus/outbox_writer.hpp`, add:

```cpp
static void append_already_delivered(
    const BusEvent& event,
    starling::persistence::Connection& conn);
```

In `src/bus/outbox_writer.cpp`, implement by reusing the existing `append` SQL path but with `dispatch_status='delivered'`. Concretely, factor a private helper `insert_event(event, status, conn)` that the existing `append` and the new `append_already_delivered` both call:

```cpp
namespace {
void insert_event(const BusEvent& event,
                  const char* dispatch_status,
                  starling::persistence::Connection& conn) {
    // Claim sequence
    auto upd = conn.prepare(
        "UPDATE outbox_sequence_counter SET next_value = next_value + 1 WHERE id = 1"
        " RETURNING next_value - 1;");
    if (upd.step() != SQLITE_ROW) {
        throw std::runtime_error("outbox_sequence_counter row missing");
    }
    int64_t seq = upd.column_int64(0);

    auto ins = conn.prepare(
        "INSERT INTO bus_events("
        "  event_id, tenant_id, event_type, primary_id, aggregate_id,"
        "  outbox_sequence, causation_chain_json, idempotency_key,"
        "  payload_json, created_at, version, dispatch_status"
        ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?);");
    int i = 1;
    ins.bind_text(i++, event.event_id);
    ins.bind_text(i++, event.tenant_id);
    ins.bind_text(i++, event.event_type);
    ins.bind_text(i++, event.primary_id);
    ins.bind_text(i++, event.aggregate_id);
    ins.bind_int64(i++, seq);
    ins.bind_text(i++, /* JSON-serialize event.causation_chain */ "[]");
    ins.bind_text(i++, event.idempotency_key);
    ins.bind_text(i++, event.payload_json);
    ins.bind_text(i++, event.created_at);
    ins.bind_text(i++, event.version);
    ins.bind_text(i++, dispatch_status);
    ins.step_done();
}
}  // namespace

void OutboxWriter::append(const BusEvent& event, persistence::Connection& conn) {
    insert_event(event, "pending", conn);
}

void OutboxWriter::append_already_delivered(const BusEvent& event,
                                            persistence::Connection& conn) {
    insert_event(event, "delivered", conn);
}
```

Causation_chain JSON serialization should reuse whatever the existing `append` uses; if the M0.2 code path used a `BusEvent::serialize_causation_chain()` helper, factor that into a header so the new method shares it.

- [ ] **Step 4: Run the test to verify it passes**

```bash
cmake --build --preset default
ctest --preset default --output-on-failure -R OutboxWriter
```
Expected: all OutboxWriter tests PASS (M0.2 set + the new one).

- [ ] **Step 5: Commit**

```bash
git add include/starling/bus/outbox_writer.hpp src/bus/outbox_writer.cpp \
        tests/cpp/test_outbox_writer.cpp
git commit -m "feat(M0.3): OutboxWriter.append_already_delivered for audit-only rows"
```

(If the method already existed and only the test was missing, the commit message is `test(M0.3): coverage for OutboxWriter.append_already_delivered`.)

---

### Task 8: Bus.append_evidence — transactional envelope

**Files:**
- Create: `include/starling/bus/bus.hpp`
- Create: `src/bus/bus.cpp`
- Create: `tests/cpp/test_bus_append_evidence.cpp`

**Goal:** `Bus::append_evidence` runs the validator → engram store → outbox path atomically. On `ValidationProceed`, exactly one `evidence.appended` row with `dispatch_status='pending'` exists in `bus_events`. On `ValidationNoStore`, exactly one `evidence.no_store_audit` row with `dispatch_status='delivered'` exists. On `ValidationIdempotentHit`, exactly one `evidence.idempotent_hit` row with `dispatch_status='delivered'` exists AND no new `engrams` row is created. On `ValidationReject`, neither table is touched.

- [ ] **Step 1: Write the failing test**

Create `tests/cpp/test_bus_append_evidence.cpp`:

```cpp
#include <gtest/gtest.h>

#include "starling/bus/bus.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/migration_runner.hpp"

#include <variant>

using starling::bus::AppendEvidenceAccepted;
using starling::bus::AppendEvidenceIdempotent;
using starling::bus::AppendEvidenceNoStore;
using starling::bus::AppendEvidenceRejected;
using starling::bus::Bus;
using starling::evidence::EngramInput;
using starling::evidence::SourceIdentity;
using starling::persistence::SqliteAdapter;
using starling::persistence::MigrationRunner;
using starling::schema::EngramRetentionMode;
using starling::schema::IngestMode;
using starling::schema::PrivacyClass;
using starling::schema::SourceKind;

namespace {

SqliteAdapter make_adapter() {
    SqliteAdapter a = SqliteAdapter::open_in_memory();
    MigrationRunner(a.connection()).run_all();
    return a;
}

EngramInput user_input() {
    return EngramInput{
        .tenant_id = "t1",
        .source = SourceIdentity{
            .adapter_name = "direct_api",
            .adapter_version = "1.0.0",
            .source_item_id = "msg-1",
            .source_version = "1",
            .chunk_index = 0,
        },
        .source_kind = SourceKind::USER_INPUT,
        .ingest_mode = IngestMode::WHOLE_RECORD,
        .privacy_class = PrivacyClass::INTERNAL,
        .retention_mode = EngramRetentionMode::AUDIT_RETAIN,
        .declared_transformations = {},
        .byte_preserving = true,
        .payload_bytes = {'h','e','l','l','o'},
        .redacted_content = std::nullopt,
        .created_at_iso8601 = "2026-05-23T10:00:00Z",
    };
}

int row_count(SqliteAdapter& a, const std::string& table) {
    auto s = a.connection().prepare("SELECT count(*) FROM " + table + ";");
    s.step();
    return s.column_int(0);
}

}  // namespace

TEST(BusAppendEvidence, AcceptedPathWritesOneEngramAndOnePendingEvent) {
    auto a = make_adapter();
    Bus bus(a);
    auto outcome = bus.append_evidence(user_input(), std::nullopt);

    auto* acc = std::get_if<AppendEvidenceAccepted>(&outcome);
    ASSERT_NE(acc, nullptr);
    EXPECT_EQ(row_count(a, "engrams"), 1);

    auto s = a.connection().prepare(
        "SELECT event_type, dispatch_status FROM bus_events;");
    ASSERT_EQ(s.step(), SQLITE_ROW);
    EXPECT_EQ(s.column_text(0), "evidence.appended");
    EXPECT_EQ(s.column_text(1), "pending");
}

TEST(BusAppendEvidence, NoStorePathWritesZeroEngramAndOneDeliveredAuditEvent) {
    auto a = make_adapter();
    auto inp = user_input();
    inp.source_kind = SourceKind::SYSTEM_INTERNAL;

    Bus bus(a);
    auto outcome = bus.append_evidence(inp, std::nullopt);

    EXPECT_NE(std::get_if<AppendEvidenceNoStore>(&outcome), nullptr);
    EXPECT_EQ(row_count(a, "engrams"), 0);

    auto s = a.connection().prepare(
        "SELECT event_type, dispatch_status FROM bus_events;");
    ASSERT_EQ(s.step(), SQLITE_ROW);
    EXPECT_EQ(s.column_text(0), "evidence.no_store_audit");
    EXPECT_EQ(s.column_text(1), "delivered");
}

TEST(BusAppendEvidence, IdempotentHitWritesZeroNewEngramAndOneDeliveredAuditEvent) {
    auto a = make_adapter();
    Bus bus(a);

    // First write succeeds.
    auto out1 = bus.append_evidence(user_input(), std::nullopt);
    ASSERT_NE(std::get_if<AppendEvidenceAccepted>(&out1), nullptr);

    // Second write with identical source identity.
    auto out2 = bus.append_evidence(user_input(), std::nullopt);
    auto* hit = std::get_if<AppendEvidenceIdempotent>(&out2);
    ASSERT_NE(hit, nullptr);

    EXPECT_EQ(row_count(a, "engrams"), 1);  // no new engram

    auto s = a.connection().prepare(
        "SELECT event_type, dispatch_status FROM bus_events ORDER BY outbox_sequence;");
    ASSERT_EQ(s.step(), SQLITE_ROW);
    EXPECT_EQ(s.column_text(0), "evidence.appended");
    EXPECT_EQ(s.column_text(1), "pending");
    ASSERT_EQ(s.step(), SQLITE_ROW);
    EXPECT_EQ(s.column_text(0), "evidence.idempotent_hit");
    EXPECT_EQ(s.column_text(1), "delivered");
}

TEST(BusAppendEvidence, RejectedPathLeavesBothTablesEmpty) {
    auto a = make_adapter();
    auto inp = user_input();
    inp.tenant_id = "";  // forces ValidationReject

    Bus bus(a);
    auto outcome = bus.append_evidence(inp, std::nullopt);

    auto* rej = std::get_if<AppendEvidenceRejected>(&outcome);
    ASSERT_NE(rej, nullptr);
    EXPECT_EQ(rej->reason, "required_field_missing:tenant_id");
    EXPECT_EQ(row_count(a, "engrams"), 0);
    EXPECT_EQ(row_count(a, "bus_events"), 0);
}

TEST(BusAppendEvidence, CausationParentBecomesFirstChainElement) {
    auto a = make_adapter();
    Bus bus(a);
    auto outcome = bus.append_evidence(user_input(), std::string("parent-evt-abc"));

    auto* acc = std::get_if<AppendEvidenceAccepted>(&outcome);
    ASSERT_NE(acc, nullptr);

    auto s = a.connection().prepare(
        "SELECT causation_chain_json FROM bus_events WHERE event_type='evidence.appended';");
    ASSERT_EQ(s.step(), SQLITE_ROW);
    EXPECT_EQ(s.column_text(0), "[\"parent-evt-abc\"]");
}
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
ctest --preset default --output-on-failure -R BusAppendEvidence
```
Expected: link error.

- [ ] **Step 3: Write the Bus header**

Create `include/starling/bus/bus.hpp` (verbatim from Subsystem Contract F).

- [ ] **Step 4: Write the Bus implementation**

Create `src/bus/bus.cpp`:

```cpp
#include "starling/bus/bus.hpp"
#include "starling/bus/bus_event.hpp"
#include "starling/bus/outbox_writer.hpp"
#include "starling/crypto/sha256.hpp"
#include "starling/evidence/engram_store.hpp"
#include "starling/evidence/evidence_validator.hpp"
#include "starling/persistence/connection.hpp"

#include <random>
#include <sstream>
#include <iomanip>
#include <string>

namespace starling::bus {

namespace {

std::string generate_uuid_v4() {
    // Duplicated from engram_store.cpp; M0.4 will consolidate into a shared util.
    static thread_local std::mt19937_64 rng{std::random_device{}()};
    auto a = rng(), b = rng();
    uint8_t bytes[16];
    for (int i = 0; i < 8; ++i) bytes[i]     = (a >> (i * 8)) & 0xff;
    for (int i = 0; i < 8; ++i) bytes[i + 8] = (b >> (i * 8)) & 0xff;
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    std::ostringstream out;
    out << std::hex << std::setfill('0');
    for (int i = 0; i < 16; ++i) {
        out << std::setw(2) << static_cast<int>(bytes[i]);
        if (i == 3 || i == 5 || i == 7 || i == 9) out << '-';
    }
    return out.str();
}

std::string source_identity_hash(const starling::evidence::SourceIdentity& s) {
    std::string blob = s.adapter_name + "\x1f" + s.source_item_id + "\x1f" +
                       s.source_version + "\x1f" + std::to_string(s.chunk_index);
    return starling::crypto::sha256_hex(blob);
}

// Minimal JSON object serialization for the few payload shapes we emit. P1
// avoids pulling a JSON library; the shapes here are closed and known.
std::string json_string(const std::string& s) {
    std::string out;
    out.push_back('"');
    for (char c : s) {
        switch (c) {
            case '"':  out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n"; break;
            default:   out.push_back(c);
        }
    }
    out.push_back('"');
    return out;
}

std::string accepted_payload(const starling::evidence::Engram& e) {
    std::ostringstream os;
    os << "{"
       << "\"engram_id\":"     << json_string(e.id) << ","
       << "\"content_hash\":"  << json_string(e.content_hash) << ","
       << "\"retention_mode\":" << json_string(std::string(schema::to_string(e.retention_mode))) << ","
       << "\"source_kind\":"    << json_string(std::string(schema::to_string(e.source_kind))) << ","
       << "\"tenant_id\":"      << json_string(e.tenant_id)
       << "}";
    return os.str();
}

std::string no_store_payload(const starling::evidence::EngramInput& i) {
    std::ostringstream os;
    os << "{"
       << "\"tenant_id\":"      << json_string(i.tenant_id) << ","
       << "\"source_kind\":"    << json_string(std::string(schema::to_string(i.source_kind))) << ","
       << "\"privacy_class\":"  << json_string(std::string(schema::to_string(i.privacy_class))) << ","
       << "\"adapter_name\":"   << json_string(i.source.adapter_name) << ","
       << "\"source_item_id\":" << json_string(i.source.source_item_id) << ","
       << "\"source_version\":" << json_string(i.source.source_version) << ","
       << "\"chunk_index\":"    << i.source.chunk_index << ","
       << "\"reason\":\"self_pollution_guard_or_producer_declared_no_store\""
       << "}";
    return os.str();
}

std::string idempotent_payload(const starling::evidence::Engram& existing) {
    std::ostringstream os;
    os << "{"
       << "\"existing_engram_id\":" << json_string(existing.id) << ","
       << "\"content_hash\":"       << json_string(existing.content_hash) << ","
       << "\"tenant_id\":"          << json_string(existing.tenant_id)
       << "}";
    return os.str();
}

BusEvent make_event(
    const std::string& event_type,
    const std::string& primary_id,
    const std::string& aggregate_id,
    const std::string& tenant_id,
    const std::string& payload_json,
    const std::optional<std::string>& causation_parent,
    const std::string& canonical_key) {

    BusEvent e;
    e.event_id      = generate_uuid_v4();
    e.tenant_id     = tenant_id;
    e.event_type    = event_type;
    e.primary_id    = primary_id;
    e.aggregate_id  = aggregate_id;
    if (causation_parent) e.causation_chain = { *causation_parent };
    e.idempotency_key = compute_idempotency_key(
        event_type,
        aggregate_id,
        canonical_key,
        e.causation_chain.empty() ? "" : e.causation_chain.front(),
        compute_window_bucket(event_type, /*now=*/std::chrono::system_clock::now()));
    e.payload_json = payload_json;
    e.created_at   = format_iso8601_utc_now();  // existing M0.2 helper
    e.version      = "v1";
    e.outbox_sequence = 0;  // claimed by writer
    return e;
}

}  // namespace

Bus::Bus(starling::persistence::SqliteAdapter& adapter) : adapter_(adapter) {}

AppendEvidenceOutcome Bus::append_evidence(
    const starling::evidence::EngramInput& input,
    std::optional<std::string> causation_parent_event_id) {

    auto& conn = adapter_.connection();
    persistence::TransactionGuard tx(conn);  // BEGIN IMMEDIATE in ctor

    auto outcome = starling::evidence::EvidenceValidator::validate(input, conn);

    if (auto* rej = std::get_if<starling::evidence::ValidationReject>(&outcome)) {
        // ROLLBACK happens in TransactionGuard dtor when commit() is not called.
        return AppendEvidenceRejected{rej->reason};
    }

    if (std::holds_alternative<starling::evidence::ValidationNoStore>(outcome)) {
        auto event = make_event(
            "evidence.no_store_audit",
            source_identity_hash(input.source),
            source_identity_hash(input.source),
            input.tenant_id,
            no_store_payload(input),
            causation_parent_event_id,
            source_identity_hash(input.source));
        OutboxWriter::append_already_delivered(event, conn);
        tx.commit();
        return AppendEvidenceNoStore{event.event_id};
    }

    if (auto* hit = std::get_if<starling::evidence::ValidationIdempotentHit>(&outcome)) {
        auto event = make_event(
            "evidence.idempotent_hit",
            hit->existing.id,
            hit->existing.id,
            input.tenant_id,
            idempotent_payload(hit->existing),
            causation_parent_event_id,
            hit->existing.id);
        OutboxWriter::append_already_delivered(event, conn);
        tx.commit();
        return AppendEvidenceIdempotent{
            starling::evidence::EngramRef{hit->existing.id,
                                          hit->existing.content_hash,
                                          hit->existing.retention_mode},
            event.event_id};
    }

    auto& proceed = std::get<starling::evidence::ValidationProceed>(outcome);
    auto engram = starling::evidence::EngramStore::put(input, proceed.resolved_policy, conn);
    auto event = make_event(
        "evidence.appended",
        engram.id,
        engram.id,
        input.tenant_id,
        accepted_payload(engram),
        causation_parent_event_id,
        engram.id);
    OutboxWriter::append(event, conn);
    tx.commit();
    return AppendEvidenceAccepted{
        starling::evidence::EngramRef{engram.id, engram.content_hash, engram.retention_mode},
        event.event_id,
        event.outbox_sequence};
}

}  // namespace starling::bus
```

(If `SqliteAdapter::open_in_memory()` / `connection()` / `TransactionGuard::commit()` / `format_iso8601_utc_now` have different M0.2 spellings, adjust to match what Task 0 Step 4 found. The control flow stays the same.)

- [ ] **Step 5: Run the test to verify it passes**

```bash
cmake --build --preset default
ctest --preset default --output-on-failure -R BusAppendEvidence
```
Expected: 5 tests PASS.

- [ ] **Step 6: Run the full ctest suite as a regression gate**

```bash
ctest --preset default --output-on-failure
```
Expected: all M0.2 tests + new M0.3 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add include/starling/bus/bus.hpp src/bus/bus.cpp \
        tests/cpp/test_bus_append_evidence.cpp \
        CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -m "feat(M0.3): Bus.append_evidence transactional envelope with self-pollution + idempotent + reject paths"
```

---

### Task 9: Pybind bindings + Python evidence package

**Files:**
- Modify: `bindings/python/module.cpp`
- Create: `python/starling/evidence/__init__.py`
- Create: `python/starling/evidence/inputs.py`
- Create: `python/starling/bus/append_evidence.py`
- Create: `tests/python/test_evidence_inputs.py`
- Create: `tests/python/test_bus_append_evidence_parity.py`

**Goal:** Python tests can call `runtime.bus.append_evidence(engram_input)` and get a Python-side `AppendEvidenceOutcome` back. Builder helpers (`for_user_input`, `for_system_internal`, etc.) construct `EngramInput` with the right `source_kind` + reasonable defaults.

- [ ] **Step 1: Extend `bindings/python/module.cpp` with M0.3 types**

Locate the `PYBIND11_MODULE(_core, m)` block and append (the existing module pattern from M0.2's BusEvent binding is the template):

```cpp
// --- M0.3 enums (mirror starling::schema::*) ---
py::enum_<starling::schema::SourceKind>(m, "SourceKind")
    .value("USER_INPUT",       starling::schema::SourceKind::USER_INPUT)
    .value("EXTERNAL_DOC",     starling::schema::SourceKind::EXTERNAL_DOC)
    .value("TOOL_OBSERVATION", starling::schema::SourceKind::TOOL_OBSERVATION)
    .value("SYSTEM_INTERNAL",  starling::schema::SourceKind::SYSTEM_INTERNAL)
    .value("OBSERVER_AGENT",   starling::schema::SourceKind::OBSERVER_AGENT)
    .value("REPLAY_OUTPUT",    starling::schema::SourceKind::REPLAY_OUTPUT);

py::enum_<starling::schema::IngestPolicy>(m, "IngestPolicy")
    .value("STORE",               starling::schema::IngestPolicy::STORE)
    .value("NO_STORE",            starling::schema::IngestPolicy::NO_STORE)
    .value("STORE_METADATA_ONLY", starling::schema::IngestPolicy::STORE_METADATA_ONLY)
    .value("REQUIRE_REVIEW",      starling::schema::IngestPolicy::REQUIRE_REVIEW);

py::enum_<starling::schema::IngestMode>(m, "IngestMode")
    .value("CHUNKED_CONTENT", starling::schema::IngestMode::CHUNKED_CONTENT)
    .value("WHOLE_RECORD",    starling::schema::IngestMode::WHOLE_RECORD)
    .value("METADATA_ONLY",   starling::schema::IngestMode::METADATA_ONLY);

py::enum_<starling::schema::PrivacyClass>(m, "PrivacyClass")
    .value("PUBLIC",    starling::schema::PrivacyClass::PUBLIC)
    .value("INTERNAL",  starling::schema::PrivacyClass::INTERNAL)
    .value("PERSONAL",  starling::schema::PrivacyClass::PERSONAL)
    .value("SENSITIVE", starling::schema::PrivacyClass::SENSITIVE)
    .value("REGULATED", starling::schema::PrivacyClass::REGULATED);

py::enum_<starling::schema::EngramRetentionMode>(m, "EngramRetentionMode")
    .value("LEGAL_HOLD",      starling::schema::EngramRetentionMode::LEGAL_HOLD)
    .value("AUDIT_RETAIN",    starling::schema::EngramRetentionMode::AUDIT_RETAIN)
    .value("REDACTED_RETAIN", starling::schema::EngramRetentionMode::REDACTED_RETAIN)
    .value("CRYPTO_ERASURE",  starling::schema::EngramRetentionMode::CRYPTO_ERASURE);

// --- M0.3 IngestPolicyResolver ---
py::class_<starling::evidence::IngestPolicyResolver>(m, "IngestPolicyResolver")
    .def_static("resolve", &starling::evidence::IngestPolicyResolver::resolve,
                py::arg("source_kind"), py::arg("privacy_class"),
                py::arg("producer_declared"));

// --- M0.3 EngramInput / SourceIdentity / EngramRef ---
py::class_<starling::evidence::SourceIdentity>(m, "SourceIdentity")
    .def(py::init<>())
    .def_readwrite("adapter_name",    &starling::evidence::SourceIdentity::adapter_name)
    .def_readwrite("adapter_version", &starling::evidence::SourceIdentity::adapter_version)
    .def_readwrite("source_item_id",  &starling::evidence::SourceIdentity::source_item_id)
    .def_readwrite("source_version",  &starling::evidence::SourceIdentity::source_version)
    .def_readwrite("chunk_index",     &starling::evidence::SourceIdentity::chunk_index);

py::class_<starling::evidence::EngramInput>(m, "EngramInput")
    .def(py::init<>())
    .def_readwrite("tenant_id",      &starling::evidence::EngramInput::tenant_id)
    .def_readwrite("source",         &starling::evidence::EngramInput::source)
    .def_readwrite("source_kind",    &starling::evidence::EngramInput::source_kind)
    .def_readwrite("ingest_mode",    &starling::evidence::EngramInput::ingest_mode)
    .def_readwrite("privacy_class",  &starling::evidence::EngramInput::privacy_class)
    .def_readwrite("retention_mode", &starling::evidence::EngramInput::retention_mode)
    .def_readwrite("declared_transformations",
                   &starling::evidence::EngramInput::declared_transformations)
    .def_readwrite("byte_preserving",   &starling::evidence::EngramInput::byte_preserving)
    .def_readwrite("payload_bytes",     &starling::evidence::EngramInput::payload_bytes)
    .def_readwrite("redacted_content",  &starling::evidence::EngramInput::redacted_content)
    .def_readwrite("created_at_iso8601",
                   &starling::evidence::EngramInput::created_at_iso8601);

py::class_<starling::evidence::EngramRef>(m, "EngramRef")
    .def_readonly("id",             &starling::evidence::EngramRef::id)
    .def_readonly("content_hash",   &starling::evidence::EngramRef::content_hash)
    .def_readonly("retention_mode", &starling::evidence::EngramRef::retention_mode);

// --- M0.3 Bus ---
py::class_<starling::bus::Bus>(m, "Bus")
    .def(py::init<starling::persistence::SqliteAdapter&>(),
         py::keep_alive<1, 2>())
    .def("append_evidence",
         [](starling::bus::Bus& self,
            const starling::evidence::EngramInput& input,
            std::optional<std::string> causation_parent) -> py::object {
             auto outcome = self.append_evidence(input, causation_parent);
             // Convert variant → tagged dict for Python ergonomics.
             return std::visit([](auto&& v) -> py::object {
                 using T = std::decay_t<decltype(v)>;
                 if constexpr (std::is_same_v<T, starling::bus::AppendEvidenceAccepted>) {
                     return py::dict("kind"_a="accepted",
                                     "engram_ref"_a=v.ref,
                                     "event_id"_a=v.event_id,
                                     "outbox_sequence"_a=v.outbox_sequence);
                 } else if constexpr (std::is_same_v<T, starling::bus::AppendEvidenceIdempotent>) {
                     return py::dict("kind"_a="idempotent",
                                     "engram_ref"_a=v.ref,
                                     "audit_event_id"_a=v.audit_event_id);
                 } else if constexpr (std::is_same_v<T, starling::bus::AppendEvidenceNoStore>) {
                     return py::dict("kind"_a="no_store",
                                     "audit_event_id"_a=v.audit_event_id);
                 } else {
                     return py::dict("kind"_a="rejected", "reason"_a=v.reason);
                 }
             }, outcome);
         },
         py::arg("input"), py::arg("causation_parent") = std::nullopt);
```

- [ ] **Step 2: Create `python/starling/evidence/inputs.py`**

```python
"""EngramInput builder helpers (M0.3).

Construct EngramInput instances with the right source_kind preset. Callers
pass the adapter identity tuple + payload + retention; the helpers fill in
the rest with safe defaults.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from starling import _core


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _build(
    *,
    tenant_id: str,
    adapter_name: str,
    adapter_version: str,
    source_item_id: str,
    source_version: str,
    chunk_index: int,
    source_kind,
    ingest_mode,
    privacy_class,
    retention_mode,
    payload_bytes: bytes,
    declared_transformations: tuple[str, ...],
    byte_preserving: bool,
    redacted_content: Optional[str],
    created_at: datetime,
) -> "_core.EngramInput":
    inp = _core.EngramInput()
    inp.tenant_id = tenant_id
    src = _core.SourceIdentity()
    src.adapter_name = adapter_name
    src.adapter_version = adapter_version
    src.source_item_id = source_item_id
    src.source_version = source_version
    src.chunk_index = chunk_index
    inp.source = src
    inp.source_kind = source_kind
    inp.ingest_mode = ingest_mode
    inp.privacy_class = privacy_class
    inp.retention_mode = retention_mode
    inp.declared_transformations = list(declared_transformations)
    inp.byte_preserving = byte_preserving
    inp.payload_bytes = list(payload_bytes)
    inp.redacted_content = redacted_content
    inp.created_at_iso8601 = _iso(created_at)
    return inp


def for_user_input(*, tenant_id, adapter_name, adapter_version, source_item_id,
                   source_version, payload_bytes, privacy_class, retention_mode,
                   created_at, chunk_index=0, declared_transformations=(),
                   byte_preserving=True, redacted_content=None):
    return _build(
        tenant_id=tenant_id, adapter_name=adapter_name, adapter_version=adapter_version,
        source_item_id=source_item_id, source_version=source_version,
        chunk_index=chunk_index, source_kind=_core.SourceKind.USER_INPUT,
        ingest_mode=_core.IngestMode.WHOLE_RECORD, privacy_class=privacy_class,
        retention_mode=retention_mode, payload_bytes=payload_bytes,
        declared_transformations=declared_transformations,
        byte_preserving=byte_preserving, redacted_content=redacted_content,
        created_at=created_at,
    )


def for_external_doc(*, tenant_id, adapter_name, adapter_version, source_item_id,
                     source_version, payload_bytes, privacy_class, retention_mode,
                     created_at, chunk_index=0, declared_transformations=(),
                     byte_preserving=True, redacted_content=None):
    return _build(
        tenant_id=tenant_id, adapter_name=adapter_name, adapter_version=adapter_version,
        source_item_id=source_item_id, source_version=source_version,
        chunk_index=chunk_index, source_kind=_core.SourceKind.EXTERNAL_DOC,
        ingest_mode=_core.IngestMode.WHOLE_RECORD, privacy_class=privacy_class,
        retention_mode=retention_mode, payload_bytes=payload_bytes,
        declared_transformations=declared_transformations,
        byte_preserving=byte_preserving, redacted_content=redacted_content,
        created_at=created_at,
    )


def for_tool_observation(*, tenant_id, adapter_name, adapter_version, source_item_id,
                         source_version, payload_bytes, privacy_class, retention_mode,
                         created_at, chunk_index=0, declared_transformations=(),
                         byte_preserving=False, redacted_content=None):
    return _build(
        tenant_id=tenant_id, adapter_name=adapter_name, adapter_version=adapter_version,
        source_item_id=source_item_id, source_version=source_version,
        chunk_index=chunk_index, source_kind=_core.SourceKind.TOOL_OBSERVATION,
        ingest_mode=_core.IngestMode.METADATA_ONLY, privacy_class=privacy_class,
        retention_mode=retention_mode, payload_bytes=payload_bytes,
        declared_transformations=declared_transformations,
        byte_preserving=byte_preserving, redacted_content=redacted_content,
        created_at=created_at,
    )


def for_system_internal(*, tenant_id, adapter_name, adapter_version, source_item_id,
                        source_version, payload_bytes, privacy_class, retention_mode,
                        created_at, chunk_index=0, declared_transformations=(),
                        byte_preserving=False, redacted_content=None):
    return _build(
        tenant_id=tenant_id, adapter_name=adapter_name, adapter_version=adapter_version,
        source_item_id=source_item_id, source_version=source_version,
        chunk_index=chunk_index, source_kind=_core.SourceKind.SYSTEM_INTERNAL,
        ingest_mode=_core.IngestMode.METADATA_ONLY, privacy_class=privacy_class,
        retention_mode=retention_mode, payload_bytes=payload_bytes,
        declared_transformations=declared_transformations,
        byte_preserving=byte_preserving, redacted_content=redacted_content,
        created_at=created_at,
    )


def for_observer_agent(*, tenant_id, adapter_name, adapter_version, source_item_id,
                       source_version, payload_bytes, privacy_class, retention_mode,
                       created_at, chunk_index=0, declared_transformations=(),
                       byte_preserving=False, redacted_content=None):
    return _build(
        tenant_id=tenant_id, adapter_name=adapter_name, adapter_version=adapter_version,
        source_item_id=source_item_id, source_version=source_version,
        chunk_index=chunk_index, source_kind=_core.SourceKind.OBSERVER_AGENT,
        ingest_mode=_core.IngestMode.METADATA_ONLY, privacy_class=privacy_class,
        retention_mode=retention_mode, payload_bytes=payload_bytes,
        declared_transformations=declared_transformations,
        byte_preserving=byte_preserving, redacted_content=redacted_content,
        created_at=created_at,
    )


def for_replay_output(*, tenant_id, adapter_name, adapter_version, source_item_id,
                      source_version, payload_bytes, privacy_class, retention_mode,
                      created_at, chunk_index=0, declared_transformations=(),
                      byte_preserving=False, redacted_content=None):
    return _build(
        tenant_id=tenant_id, adapter_name=adapter_name, adapter_version=adapter_version,
        source_item_id=source_item_id, source_version=source_version,
        chunk_index=chunk_index, source_kind=_core.SourceKind.REPLAY_OUTPUT,
        ingest_mode=_core.IngestMode.METADATA_ONLY, privacy_class=privacy_class,
        retention_mode=retention_mode, payload_bytes=payload_bytes,
        declared_transformations=declared_transformations,
        byte_preserving=byte_preserving, redacted_content=redacted_content,
        created_at=created_at,
    )
```

- [ ] **Step 3: Create `python/starling/evidence/__init__.py`**

```python
"""Public surface for the M0.3 EngramStore write path."""

from starling._core import (
    SourceKind,
    IngestPolicy,
    IngestMode,
    PrivacyClass,
    EngramRetentionMode,
    SourceIdentity,
    EngramInput,
    EngramRef,
    IngestPolicyResolver,
)
from starling.evidence.inputs import (
    for_user_input,
    for_external_doc,
    for_tool_observation,
    for_system_internal,
    for_observer_agent,
    for_replay_output,
)

__all__ = [
    "SourceKind", "IngestPolicy", "IngestMode", "PrivacyClass", "EngramRetentionMode",
    "SourceIdentity", "EngramInput", "EngramRef", "IngestPolicyResolver",
    "for_user_input", "for_external_doc", "for_tool_observation",
    "for_system_internal", "for_observer_agent", "for_replay_output",
]
```

- [ ] **Step 4: Create `python/starling/bus/append_evidence.py`**

```python
"""High-level Python wrapper around _core.Bus.append_evidence."""

from typing import Optional

from starling import _core


class BusFacade:
    """Thin wrapper held by runtime; M0.3 only exposes append_evidence."""

    def __init__(self, adapter: "_core.SqliteAdapter") -> None:
        self._adapter = adapter
        self._bus = _core.Bus(adapter)

    def append_evidence(
        self,
        engram_input: "_core.EngramInput",
        causation_parent: Optional[str] = None,
    ) -> dict:
        return self._bus.append_evidence(engram_input, causation_parent)
```

- [ ] **Step 5: Wire `BusFacade` into `runtime._build_local_store_sqlite_runtime`**

Edit `python/starling/runtime.py` near the existing `_build_local_store_sqlite_runtime`:

```python
# In the runtime construction path (find the existing factory and append):
from starling.bus.append_evidence import BusFacade  # at top of file

# ... inside _build_local_store_sqlite_runtime (or _LocalStoreSqliteRuntime ctor):
self.bus = BusFacade(self.adapter)
```

The exact integration point depends on the M0.2 factory shape — Task 0 Step 4 surfaced whether `_LocalStoreSqliteRuntime` is a dataclass, NamedTuple, or plain class. Place `self.bus = ...` after `self.adapter = ...` and after migrations have run.

- [ ] **Step 6: Write the builder test**

Create `tests/python/test_evidence_inputs.py`:

```python
from datetime import datetime, timezone

from starling._core import (
    SourceKind, IngestMode, PrivacyClass, EngramRetentionMode,
)
from starling.evidence import (
    for_user_input, for_system_internal, for_tool_observation,
)


def test_for_user_input_defaults():
    inp = for_user_input(
        tenant_id="t1", adapter_name="direct_api", adapter_version="1.0.0",
        source_item_id="msg-1", source_version="1",
        payload_bytes=b"hello",
        privacy_class=PrivacyClass.INTERNAL,
        retention_mode=EngramRetentionMode.AUDIT_RETAIN,
        created_at=datetime(2026, 5, 23, 10, 0, tzinfo=timezone.utc),
    )
    assert inp.source_kind == SourceKind.USER_INPUT
    assert inp.ingest_mode == IngestMode.WHOLE_RECORD
    assert inp.byte_preserving is True
    assert inp.source.chunk_index == 0
    assert inp.created_at_iso8601 == "2026-05-23T10:00:00Z"


def test_for_system_internal_uses_metadata_only_default():
    inp = for_system_internal(
        tenant_id="t1", adapter_name="retrieval_planner", adapter_version="0.1.0",
        source_item_id="receipt-1", source_version="1",
        payload_bytes=b"trace",
        privacy_class=PrivacyClass.INTERNAL,
        retention_mode=EngramRetentionMode.AUDIT_RETAIN,
        created_at=datetime(2026, 5, 23, 10, 0, tzinfo=timezone.utc),
    )
    assert inp.source_kind == SourceKind.SYSTEM_INTERNAL
    assert inp.ingest_mode == IngestMode.METADATA_ONLY
    assert inp.byte_preserving is False


def test_for_tool_observation_defaults():
    inp = for_tool_observation(
        tenant_id="t1", adapter_name="weather_api", adapter_version="2",
        source_item_id="q-1", source_version="1",
        payload_bytes=b'{"temp":72}',
        privacy_class=PrivacyClass.PUBLIC,
        retention_mode=EngramRetentionMode.AUDIT_RETAIN,
        created_at=datetime(2026, 5, 23, 10, 0, tzinfo=timezone.utc),
    )
    assert inp.source_kind == SourceKind.TOOL_OBSERVATION
    assert inp.ingest_mode == IngestMode.METADATA_ONLY
```

- [ ] **Step 7: Write the C++/Python parity test**

Create `tests/python/test_bus_append_evidence_parity.py`:

```python
"""Confirm IngestPolicyResolver behavior is identical from Python and C++."""

from starling._core import (
    IngestPolicy, IngestPolicyResolver, PrivacyClass, SourceKind,
)


def test_system_internal_always_no_store_from_python():
    for privacy in PrivacyClass.__members__.values():
        for declared in IngestPolicy.__members__.values():
            assert IngestPolicyResolver.resolve(
                SourceKind.SYSTEM_INTERNAL, privacy, declared
            ) == IngestPolicy.NO_STORE


def test_user_input_regulated_downgrades():
    assert IngestPolicyResolver.resolve(
        SourceKind.USER_INPUT, PrivacyClass.REGULATED, IngestPolicy.STORE
    ) == IngestPolicy.REQUIRE_REVIEW


def test_tool_observation_always_metadata_only_on_store():
    assert IngestPolicyResolver.resolve(
        SourceKind.TOOL_OBSERVATION, PrivacyClass.PUBLIC, IngestPolicy.STORE
    ) == IngestPolicy.STORE_METADATA_ONLY
```

- [ ] **Step 8: Rebuild + run all tests**

```bash
cmake --build --preset default
.venv/bin/pytest -q tests/python/test_evidence_inputs.py tests/python/test_bus_append_evidence_parity.py
```
Expected: all tests PASS.

- [ ] **Step 9: Commit**

```bash
git add bindings/python/module.cpp \
        python/starling/evidence/__init__.py python/starling/evidence/inputs.py \
        python/starling/bus/append_evidence.py python/starling/runtime.py \
        tests/python/test_evidence_inputs.py tests/python/test_bus_append_evidence_parity.py
git commit -m "feat(M0.3): pybind Bus.append_evidence + Python evidence package"
```

---

### Task 10: Self-pollution guard test + relax_preflight_for_m0_3 + acceptance smoke

**Files:**
- Modify: `python/starling/testing/__init__.py` (add `relax_preflight_for_m0_3`)
- Modify: `tools/ci/scan_prod_uses_testing.py` (extend forbidden list)
- Create: `tests/python/test_self_pollution_guard.py`
- Create: `tests/python/test_m0_3_acceptance.py`

**Goal:** The §15.3.2 self-pollution non-CRITICAL retention is green. The milestone acceptance smoke confirms the M0.3 surface works end-to-end (build the runtime, call append_evidence for the four major paths: STORE → engrams row + pending event, NO_STORE → no engrams row + delivered audit event, IDEMPOTENT → no new row + delivered audit event, REJECT → both tables unchanged).

- [ ] **Step 1: Extend `python/starling/testing/__init__.py`**

Append:

```python
def relax_preflight_for_m0_3() -> None:
    """M0.3 acceptance helper. Same surgery as relax_preflight_for_m0_2 (the
    `engram_per_record_key` capability is still deferred to M0.4 + KMS). Kept
    as a separate function so the M0.3 acceptance test names what it's
    relaxing. Delete both helpers when M0.4 lands the real capability."""
    relax_preflight_for_m0_2()
```

- [ ] **Step 2: Extend the CI scanner**

Edit `tools/ci/scan_prod_uses_testing.py` and add `"relax_preflight_for_m0_3"` to the forbidden-symbol list. If the M0.2 plan's Task 9 left a tuple like `FORBIDDEN_SYMBOLS = ("relax_preflight_for_m0_2", "testing_helper_marker", ...)`, append the new name there.

Add an inline pytest case to whatever scanner-test file already exists (`tests/python/test_ci_static_scan.py` per Task 0 Step 4 listing):

```python
def test_scanner_blocks_relax_preflight_for_m0_3_in_prod():
    # Lift the test pattern from test_scanner_blocks_relax_preflight_for_m0_2.
    # Same assertion, new symbol.
    ...
```

(Copy the existing m0_2 test verbatim, replace the symbol name. Don't write "similar to" — write the actual test code.)

- [ ] **Step 3: Write the self-pollution guard test**

Create `tests/python/test_self_pollution_guard.py`:

```python
"""§15.3.2 retention: source_kind=system_internal → NO_STORE.

RetrievalReceipt and PipelineRun traces are commonly re-fed into the system
during debugging or playback. The self-pollution guard ensures they cannot
silently become user-profile evidence. M0.3 owns the storage-layer half:
no engrams row, audit row only. M0.4/M0.6 own the inference-layer half:
no Statement materializes (no Extractor consumer on evidence.no_store_audit).
"""

from datetime import datetime, timezone

import pytest

from starling import testing as starling_testing
from starling._core import PrivacyClass, EngramRetentionMode
from starling.evidence import for_system_internal


@pytest.fixture
def runtime(tmp_path):
    starling_testing.relax_preflight_for_m0_3()
    from starling.runtime import build_local_store_sqlite_runtime  # M0.2 factory
    return build_local_store_sqlite_runtime(tmp_path / "starling.db")


def _count(runtime, table):
    cur = runtime.adapter.execute(f"SELECT count(*) FROM {table}")
    return cur.fetchone()[0]


def test_system_internal_payload_does_not_create_engram(runtime):
    inp = for_system_internal(
        tenant_id="t1",
        adapter_name="retrieval_planner",
        adapter_version="0.1.0",
        source_item_id="receipt-abc",
        source_version="1",
        privacy_class=PrivacyClass.INTERNAL,
        retention_mode=EngramRetentionMode.AUDIT_RETAIN,
        payload_bytes=b"sufficiency_status=SUFFICIENT|trace=...",
        created_at=datetime(2026, 5, 23, 10, 0, tzinfo=timezone.utc),
    )
    outcome = runtime.bus.append_evidence(inp)

    assert outcome["kind"] == "no_store"
    assert outcome["audit_event_id"]  # non-empty
    assert _count(runtime, "engrams") == 0

    audit_rows = runtime.adapter.execute(
        "SELECT event_type, dispatch_status FROM bus_events ORDER BY outbox_sequence"
    ).fetchall()
    assert audit_rows == [("evidence.no_store_audit", "delivered")]


def test_observer_agent_payload_is_also_no_store(runtime):
    from starling.evidence import for_observer_agent
    inp = for_observer_agent(
        tenant_id="t1",
        adapter_name="tom_observer",
        adapter_version="0.1.0",
        source_item_id="obs-1",
        source_version="1",
        privacy_class=PrivacyClass.INTERNAL,
        retention_mode=EngramRetentionMode.AUDIT_RETAIN,
        payload_bytes=b"observed_event=...",
        created_at=datetime(2026, 5, 23, 10, 0, tzinfo=timezone.utc),
    )
    outcome = runtime.bus.append_evidence(inp)
    assert outcome["kind"] == "no_store"
    assert _count(runtime, "engrams") == 0


def test_replay_output_payload_is_also_no_store(runtime):
    from starling.evidence import for_replay_output
    inp = for_replay_output(
        tenant_id="t1",
        adapter_name="replay_scheduler",
        adapter_version="0.1.0",
        source_item_id="replay-1",
        source_version="1",
        privacy_class=PrivacyClass.INTERNAL,
        retention_mode=EngramRetentionMode.AUDIT_RETAIN,
        payload_bytes=b"derived=...",
        created_at=datetime(2026, 5, 23, 10, 0, tzinfo=timezone.utc),
    )
    outcome = runtime.bus.append_evidence(inp)
    assert outcome["kind"] == "no_store"
    assert _count(runtime, "engrams") == 0
```

- [ ] **Step 4: Write the acceptance smoke**

Create `tests/python/test_m0_3_acceptance.py`:

```python
"""M0.3 milestone acceptance smoke. Confirms the four outcomes of
Bus.append_evidence work end-to-end against a real on-disk SQLite DB."""

from datetime import datetime, timezone

import pytest

from starling import testing as starling_testing
from starling._core import PrivacyClass, EngramRetentionMode
from starling.evidence import for_user_input, for_system_internal


@pytest.fixture
def runtime(tmp_path):
    starling_testing.relax_preflight_for_m0_3()
    from starling.runtime import build_local_store_sqlite_runtime
    return build_local_store_sqlite_runtime(tmp_path / "starling.db")


def _user_input(idx: int):
    return for_user_input(
        tenant_id="t1", adapter_name="direct_api", adapter_version="1.0.0",
        source_item_id=f"msg-{idx}", source_version="1",
        payload_bytes=f"hello-{idx}".encode(),
        privacy_class=PrivacyClass.INTERNAL,
        retention_mode=EngramRetentionMode.AUDIT_RETAIN,
        created_at=datetime(2026, 5, 23, 10, 0, tzinfo=timezone.utc),
    )


def test_store_path_writes_engram_and_pending_event(runtime):
    outcome = runtime.bus.append_evidence(_user_input(1))
    assert outcome["kind"] == "accepted"
    assert outcome["engram_ref"].id
    assert outcome["event_id"]
    assert outcome["outbox_sequence"] >= 1

    n_engrams = runtime.adapter.execute("SELECT count(*) FROM engrams").fetchone()[0]
    assert n_engrams == 1
    row = runtime.adapter.execute(
        "SELECT event_type, dispatch_status FROM bus_events"
    ).fetchone()
    assert row == ("evidence.appended", "pending")


def test_no_store_path_writes_audit_only(runtime):
    inp = for_system_internal(
        tenant_id="t1", adapter_name="x", adapter_version="1",
        source_item_id="s-1", source_version="1",
        payload_bytes=b"trace",
        privacy_class=PrivacyClass.INTERNAL,
        retention_mode=EngramRetentionMode.AUDIT_RETAIN,
        created_at=datetime(2026, 5, 23, 10, 0, tzinfo=timezone.utc),
    )
    outcome = runtime.bus.append_evidence(inp)
    assert outcome["kind"] == "no_store"
    assert runtime.adapter.execute("SELECT count(*) FROM engrams").fetchone()[0] == 0


def test_idempotent_repeat_returns_existing_ref(runtime):
    o1 = runtime.bus.append_evidence(_user_input(1))
    o2 = runtime.bus.append_evidence(_user_input(1))
    assert o1["kind"] == "accepted"
    assert o2["kind"] == "idempotent"
    assert o2["engram_ref"].id == o1["engram_ref"].id

    assert runtime.adapter.execute("SELECT count(*) FROM engrams").fetchone()[0] == 1
    types = [r[0] for r in runtime.adapter.execute(
        "SELECT event_type FROM bus_events ORDER BY outbox_sequence").fetchall()]
    assert types == ["evidence.appended", "evidence.idempotent_hit"]


def test_rejected_path_leaves_both_tables_empty(runtime):
    bad = _user_input(1)
    bad.tenant_id = ""
    outcome = runtime.bus.append_evidence(bad)
    assert outcome["kind"] == "rejected"
    assert outcome["reason"] == "required_field_missing:tenant_id"
    assert runtime.adapter.execute("SELECT count(*) FROM engrams").fetchone()[0] == 0
    assert runtime.adapter.execute("SELECT count(*) FROM bus_events").fetchone()[0] == 0


def test_pending_evidence_event_payload_carries_engram_id(runtime):
    outcome = runtime.bus.append_evidence(_user_input(1))
    payload = runtime.adapter.execute(
        "SELECT payload_json FROM bus_events WHERE event_type='evidence.appended'"
    ).fetchone()[0]
    assert outcome["engram_ref"].id in payload
    assert outcome["engram_ref"].content_hash in payload
```

- [ ] **Step 5: Rebuild + run all M0.3 tests**

```bash
cmake --build --preset default
.venv/bin/pytest -q tests/python/test_self_pollution_guard.py \
                    tests/python/test_m0_3_acceptance.py \
                    tests/python/test_evidence_inputs.py \
                    tests/python/test_bus_append_evidence_parity.py \
                    tests/python/test_ci_static_scan.py
```
Expected: all tests PASS.

- [ ] **Step 6: Run the full regression suite**

```bash
ctest --preset default --output-on-failure
.venv/bin/pytest -q
```
Expected: all C++ tests + all Python tests PASS (no M0.0 / M0.1 / M0.2 regressions).

- [ ] **Step 7: Commit**

```bash
git add python/starling/testing/__init__.py \
        tools/ci/scan_prod_uses_testing.py \
        tests/python/test_self_pollution_guard.py \
        tests/python/test_m0_3_acceptance.py \
        tests/python/test_ci_static_scan.py
git commit -m "feat(M0.3): self-pollution guard test + relax_preflight_for_m0_3 + acceptance smoke"
```

---

### Task 11: Roadmap flip + final whole-branch review + merge consent

**Files:**
- Modify: `docs/superpowers/plans/2026-05-23-roadmap.md`

**Goal:** Roadmap shows M0.3 as ✅ 完成 and points at the last work commit (NOT this roadmap-flip commit). Then the whole branch is reviewed and merge consent is requested.

- [ ] **Step 1: Identify the M0.3 last-work commit**

```bash
git log --oneline | head -20
```
The "last work commit" is whatever Task 10 Step 7 produced. Note its SHA.

- [ ] **Step 2: Edit the roadmap row**

Open `docs/superpowers/plans/2026-05-23-roadmap.md`. Find the M0.3 row. Update:
- Status column → `✅ 完成`
- Commit column → the SHA from Step 1
- Date column → today's date

If the roadmap also has a "merged-to-main commit" column, leave it blank until the merge actually happens (Task 11 Step 6 fills it post-merge).

- [ ] **Step 3: Commit the roadmap flip**

```bash
git add docs/superpowers/plans/2026-05-23-roadmap.md
git commit -m "chore(M0.3): mark milestone complete in roadmap"
```

- [ ] **Step 4: Run final regression**

```bash
cmake --build --preset default
ctest --preset default --output-on-failure
.venv/bin/pytest -q
```
Expected: all green.

- [ ] **Step 5: Dispatch the final whole-branch reviewer**

Per `superpowers:subagent-driven-development`, after all tasks complete, dispatch a final code-reviewer subagent that reviews the **entire M0.3 branch** (not just the last task). The review covers:
- Schema migration 0003 correctness + idempotency
- IngestPolicyResolver matches §3.7 table
- EvidenceValidator covers all four outcome variants
- EngramStore.put / get round-trip
- Bus.append_evidence atomicity across all four paths
- Pybind bindings + Python evidence package
- Self-pollution guard test traces back to §15.3.2
- relax_preflight_for_m0_3 helper is properly fenced by the CI scanner
- No deferred-but-undocumented work (KMS, crypto-erasure, refcount must be called out as M0.4+ scope in commit messages or code comments)

Address any "Important" or "Critical" findings in fix commits before merge. Repeat the reviewer dispatch until approved.

- [ ] **Step 6: Request merge consent + merge**

Ask the user via `AskUserQuestion`:
- "Merge --no-ff to main (Recommended)"
- "Keep the branch open for more work"
- "Discard the branch"

If approved for merge:
```bash
git checkout main
git pull --ff-only origin main
git merge --no-ff <m0-3-branch-name> -m "Merge M0.3: EngramStore + Bus.append_evidence + self-pollution guard"
```

After merging, repoint the roadmap cell to the actual merge commit (or the worktree's last-work commit, per the project's commit-cell rule):
```bash
# If the rule is "cell points at last work commit, NOT the merge commit":
# the cell already points at Step 1's SHA; do nothing.
# If the rule is "cell points at the merge commit": edit the cell and commit
# `chore(M0.3): repoint roadmap cell at the actual milestone-close commit`.
```

Push only with explicit user consent:
```bash
# DO NOT push without asking the user first.
git push origin main
```

- [ ] **Step 7: Worktree teardown**

After merge is on main, exit the worktree:
```
ExitWorktree(action="remove")
```
(The worktree branch is unreachable once merged; removing is clean.)

---

## Self-Review

After writing this plan, I re-read the spec — Subsystem doc §06_engramstore.md, §05_bus.md, §15.2 M0.3 row, §15.3.2 self-pollution retention, §3.7 SourceKind/IngestPolicy table — and the §15.3.1 13-CRITICAL list to confirm M0.3 owns no CRITICAL test of its own.

**1. Spec coverage:**
- §15.2 M0.3 row: `EngramStore + retention_mode + ingest_policy + 自污染防护` → Task 2 (schema columns including retention_mode + ingest_policy) + Task 4 (IngestPolicyResolver) + Task 5 (EvidenceValidator) + Task 6 (EngramStore) + Task 8 (Bus.append_evidence) + Task 10 (self-pollution guard test). ✅
- §3.7 IngestPolicy table → Task 4's test table is the table verbatim. ✅
- §06_engramstore.md "append_evidence" flow (lines 26-52) → Task 8's flowchart in Subsystem Contract F mirrors it (validator → engram store → outbox.append, with NO_STORE short-circuit). ✅
- §06_engramstore.md "幂等检查：(adapter_name, source_item_id, version, chunk_index)" → Task 2's UNIQUE index + Task 5's validator lookup. ✅
- §06_engramstore.md "content_hash; 含 declared_transformations 域" → Task 3's `canonicalize_engram_payload` includes transformations. ✅
- §05_bus.md line 65 self-pollution rule → Task 4's resolver implements it; Task 10's test asserts it. ✅
- §15.3.2 self-pollution retention → Task 10 owns the storage half explicitly; M0.4/M0.6 hand-off noted in the test docstring. ✅
- M0.4 dependency (§15.2 row: "Extractor + Validator + extraction_span_key") → the `evidence.appended` event shape (Task 8) carries `engram_id` + `content_hash` + `tenant_id`, which is what an Extractor subscriber needs. ✅

**2. Placeholder scan:**
- No "TBD" / "fill in" / "similar to Task N" / "implement later" survived the draft.
- The `PLACEHOLDER_PIN_N` strings in Task 3 are explicitly named placeholders with a one-liner Python script to compute the replacements; this is intentional and the step is gated on running the script and replacing the placeholders before re-running the test.
- All steps that touch code include the actual code block (no "add error handling here" hand-waves).

**3. Type consistency:**
- `EngramInput`, `EngramRef`, `SourceIdentity`, `Engram`, `IngestPolicyResolver`, `EvidenceValidator`, `EngramStore`, `Bus` — same names used in headers (Task 1/3/4/5/6/8), Python bindings (Task 9), and tests throughout.
- `IngestPolicy::NO_STORE` (C++) ↔ `IngestPolicy.NO_STORE` (Python) — string value `"no_store"` is asserted in Task 1's parity test.
- `compute_engram_content_hash(payload, transformations)` — same signature in Task 3 header, Task 3 implementation, Task 3 test, and Task 6 (EngramStore.put calls it).
- `AppendEvidenceOutcome` variant tags: `"accepted" / "idempotent" / "no_store" / "rejected"` — same in Task 8 (pybind dict tags) and Tasks 9/10 (Python tests that read `outcome["kind"]`).
- `OutboxWriter::append_already_delivered` — assumed to exist per Task 0 Step 4 verification; if absent, Task 7 adds it (M0.2 plan's Subsystem Contract C said it does, but the implementation may have been in the dispatcher).

**4. Out-of-scope items called out explicitly:**
- Per-record AES key + KMS → P1 simplification 1, Task 6 null_kms placeholder
- Crypto-erasure cascade → P1 simplification 2
- segment_map → P1 simplification 3
- byte_preserving conformance test → P1 simplification 4
- Refcount maintenance → P1 simplification 5
- `tool_observation` promotion-to-STORE escape hatch → Subsystem Contract C closing paragraph

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-23-m0-3-engram-store.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, two-stage review between tasks (spec compliance, then code quality), continuous progress without checking in between tasks.

**2. Inline Execution** — Execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints for review.

Which approach?

#pragma once

#include "starling/persistence/sqlite_adapter.hpp"
#include <string_view>

namespace starling::testing {

// True iff the testing-only translation unit is linked into the current binary.
// Defined in a separate target (starling_testing_marker) that prod profiles MUST NOT
// link. preflight reads this at startup and refuses to enter READY when:
//   - profile == "prod" AND testing_marker_loaded() == true
//
// CI grep (defense-in-depth #1) further bans `starling::testing` references in prod
// entrypoints — see scripts/ci_static_scan.py.
bool testing_marker_loaded() noexcept;

// VOLATILE -> CONSOLIDATED transition for test setup. Writes an audit event
// 'testing.mark_consolidated' (atomic with the UPDATE under a single
// TransactionGuard). Idempotent: returns false if the row was already
// consolidated, missing, or in any non-volatile state.
//
// Used by TC-NEW-CONFLICT-SEVERE (M0.5 Task 10) to seed S_old in the
// CONSOLIDATED state before driving Bus::write through the §15.3.4 atomic
// SUPERSEDES path. Production preflight + the CI static scan reject any prod
// entrypoint that imports starling::testing — so this can never leak into
// real ingest.
bool mark_consolidated(
    starling::persistence::SqliteAdapter& adapter,
    std::string_view stmt_id,
    std::string_view tenant_id);

// Flip engrams(id=engram_id, tenant_id=tenant_id).erased_at from NULL to
// erased_at_iso8601. Writes an audit event 'testing.mark_evidence_erased'
// in the same transaction (atomic with the UPDATE under a single
// TransactionGuard). Returns true iff a row was actually flipped.
// Idempotent: returns false if missing or already erased — and writes no
// audit event in those cases so replays don't pollute bus_events.
//
// Used by the M0.6 13_retrieval.md evidence-erased negative test
// (the BasicRetriever filter must drop engrams with non-NULL erased_at).
// The CI static scan rejects any prod entrypoint that imports
// starling::testing — so this can never leak into real ingest.
bool mark_evidence_erased(
    starling::persistence::SqliteAdapter& adapter,
    std::string_view engram_id,
    std::string_view tenant_id,
    std::string_view erased_at_iso8601);

}  // namespace starling::testing

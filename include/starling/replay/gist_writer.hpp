#pragma once
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/replay/gist_clustering.hpp"
#include <string_view>
#include <vector>

namespace starling::replay {

// Outcome of an offline gist-write batch. `failed` is surfaced (not silently
// swallowed) so a caller/test can assert it is zero in the happy path; a
// non-zero `failed` means some proposal was rejected by validation/conflict/
// arbitration and will be retried next consolidation cycle (Phase-1 idempotency
// only suppresses keys that actually produced a gist).
struct GistWriteOutcome {
    int written = 0;
    int failed = 0;
};

// #38-C Phase 2: write each detected NORM-gist cluster as a derived Statement
// through the EXISTING Bus::write pipeline (validation -> conflict-probe ->
// arbitration). A gist is a generalized belief held by a reserved common-ground
// holder about a generic "people" subject:
//     (common_ground) believes (people, <predicate>, <object>)
// stamped provenance=consolidation_abstract, derived_from = the cluster member
// ids, derived_depth = max(member depth)+1 (computed by the writer). It lands
// consolidation_state=volatile + review_status not-approved (pending_review,
// or review_requested / inferred_unreviewed depending on predicate/perspective).
// It is INERT: the consolidated-knowledge retrieval/ToM queries require
// consolidated/archived, so a volatile gist is never surfaced. It is also a
// STABLE proposal — the oscillation guard and the volatile TTL sweep are fenced
// against provenance='consolidation_abstract', so a gist is neither
// force-consolidated nor TTL-archived; it persists untouched until Phase-4
// gating consolidates+approves it (or forget/reject removes it).
//
// MUST be called only from an OFFLINE replay path (run_idle / run_sleep, which
// run in autocommit). Bus::write opens a BEGIN; calling it from inside the
// post-write subscriber path (where a transaction is already open) would nest
// BEGIN and abort. Returns the count of gists written + failed.
GistWriteOutcome write_gist_proposals(persistence::SqliteAdapter& adapter,
                                      const std::vector<GistProposal>& proposals,
                                      std::string_view now_iso);

}  // namespace starling::replay

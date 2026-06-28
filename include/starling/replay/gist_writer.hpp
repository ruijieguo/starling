#pragma once
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/replay/gist_clustering.hpp"
#include <string_view>
#include <vector>

namespace starling::extractor { class LLMAdapter; }  // the injected LLM I/O seam

namespace starling::replay {

// Outcome of an offline gist-write batch. `failed` is surfaced (not silently
// swallowed) so a caller/test can assert it is zero in the happy path; a
// non-zero `failed` means some proposal was rejected by validation/conflict/
// arbitration and will be retried next consolidation cycle (Phase-1 idempotency
// only suppresses keys that actually produced a gist).
struct GistWriteOutcome {
    int written = 0;   // gists written (LLM path: verified + promoted to consolidated)
    int failed = 0;    // LLM / write / promote errors (couldn't complete)
    int gated = 0;     // #38-C P4: rejected by gating — below confidence floor,
                       // not entailed, or conflict-archived by pipeline arbitration
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
//
// #38-C Phase 3+4: when `gist_llm` is non-null, each candidate is JUDGED then
// GATED before any write — (P3) build_norm_gist_prompt → confidence + summary;
// (P4) confidence floor + an INDEPENDENT entailment-verification LLM pass. Only a
// candidate that clears both gates is written (via Bus::write — validation /
// conflict-probe / arbitration) and then PROMOTED volatile→consolidated+approved
// (state-guarded: a conflict-archived gist is not promoted). A rejected candidate
// leaves NO row, so it is re-detectable next cycle (no confabulation rows, no
// permanent suppression). consolidation_summary holds the LLM's rendering.
// Outcome: written = verified+promoted; gated = floor/entailment/conflict reject;
// failed = LLM/write/promote error. When `gist_llm` is null (the C++ embedded
// tick, or no consolidation role configured), the deterministic path writes an
// INERT gist (volatile + not-approved, never promoted) and never gates.
// `confidence_floor` is the Phase-4 gate floor (a judged gist below it is gated,
// not written); defaults to the canonical GistThresholds value, overridable from
// the dashboard "consolidation" config (threshold config surface, v2).
GistWriteOutcome write_gist_proposals(persistence::SqliteAdapter& adapter,
                                      const std::vector<GistProposal>& proposals,
                                      std::string_view now_iso,
                                      extractor::LLMAdapter* gist_llm = nullptr,
                                      double confidence_floor = GistThresholds{}.min_confidence);

}  // namespace starling::replay

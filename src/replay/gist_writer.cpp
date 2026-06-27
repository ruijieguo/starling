#include "starling/replay/gist_writer.hpp"

#include "starling/bus/bus.hpp"
#include "starling/extractor/extracted_statement.hpp"
#include "starling/schema/statement_enums.hpp"

#include <sqlite3.h>
#include <exception>
#include <optional>
#include <stdexcept>
#include <string>
#include <string_view>

namespace starling::replay {
namespace {

// Reserved synthetic identities for NORM gists. Deliberately NOT real
// Cognizer/Entity rows in v1 (the writer does no FK check, and a gist stays
// pending_review/inert until Phase 4 gates it). A norm reads
// "(common ground) people generally <predicate> <object>".
constexpr std::string_view kNormHolderId    = "__common_ground__";
constexpr std::string_view kNormSubjectKind = "entity";
constexpr std::string_view kNormSubjectId   = "__people__";

// Provisional confidence for an ungated gist: above the validator's
// confidence_drop_floor (0.30) so the write is accepted, but the gist is
// pending_review so it is not retrievable. Phase 4 computes the real value.
constexpr double kProvisionalConfidence = 0.5;

extractor::ExtractedStatement build_gist_statement(
    std::string_view tenant_id,
    const GistCluster& cluster,
    std::string_view now_iso)
{
    extractor::ExtractedStatement stmt;
    stmt.holder_id             = std::string(kNormHolderId);
    stmt.holder_tenant_id      = std::string(tenant_id);
    stmt.holder_perspective    = schema::Perspective::INFERRED;
    stmt.subject_kind          = std::string(kNormSubjectKind);
    stmt.subject_id            = std::string(kNormSubjectId);
    stmt.predicate             = cluster.predicate;
    stmt.object_kind           = cluster.object_kind;
    stmt.object_value          = cluster.object_value;
    stmt.canonical_object_hash = cluster.canonical_object_hash;
    stmt.modality              = schema::Modality::BELIEVES;
    stmt.polarity              = schema::Polarity::POS;
    stmt.confidence            = kProvisionalConfidence;
    stmt.observed_at           = std::string(now_iso);
    // A norm is timeless in v1: no valid_from / valid_to / event_time_start.
    // source_hash is a required validator field; make it deterministic per key.
    stmt.source_hash           = "consolidation:" + cluster.predicate + ":" +
                                 cluster.canonical_object_hash;
    stmt.provenance            = schema::StatementProvenance::CONSOLIDATION_ABSTRACT;
    // Request review — never auto-approved. (validate_for_write may further
    // upgrade this to REVIEW_REQUESTED for a non-core predicate; both are
    // "not approved".) The gist's real inertness, though, comes from the
    // writer hardcoding consolidation_state='volatile': the consolidated-
    // knowledge retrieval/ToM queries require consolidated/archived, so a
    // volatile gist is not surfaced. Phase 4 gating flips it to consolidated
    // + approved only after the verification pass.
    stmt.review_status         = schema::ReviewStatus::PENDING_REVIEW;
    stmt.derived_from          = cluster.member_ids;
    return stmt;
}

}  // namespace

GistWriteOutcome write_gist_proposals(persistence::SqliteAdapter& adapter,
                                      const std::vector<GistProposal>& proposals,
                                      std::string_view now_iso)
{
    GistWriteOutcome outcome;
    // Precondition (fail LOUD): must run in autocommit. Bus::write opens a
    // BEGIN; if a transaction were already open — e.g. this were ever misused
    // from the post-write subscriber path — the nested BEGIN would abort every
    // write and the per-proposal catch below would silently swallow it. A
    // logic_error here turns that misuse into an immediate, visible failure.
    if (sqlite3_get_autocommit(adapter.connection().raw()) == 0) {
        throw std::logic_error(
            "write_gist_proposals must run in autocommit (offline replay only); "
            "an open transaction means it was called from a write/subscriber path");
    }
    bus::Bus gist_bus(adapter);
    for (const auto& proposal : proposals) {
        const auto stmt =
            build_gist_statement(proposal.tenant_id, proposal.cluster, now_iso);
        // Deterministic span key per cluster so a re-emitted statement.written
        // event dedups on its idempotency_key.
        const std::string span_key =
            "consolidation:" + proposal.tenant_id + ":" +
            proposal.cluster.predicate + ":" + proposal.cluster.canonical_object_hash;
        try {
            // A gist has NO source engram — its lineage is derived_from (the
            // cluster members), stamped by the writer. The empty evidence_engram_id
            // is honest: the chunk-duplicate probe is an exact (holder, predicate,
            // hash, approved) match and gists are never approved pre-gating, so it
            // is a benign no-op; gist dedup is the Phase-1 idempotency guard.
            gist_bus.write(stmt, /*evidence_engram_id=*/"", span_key, std::nullopt);
            ++outcome.written;
        } catch (const std::exception&) {
            // A single gist failing (validation / conflict / arbitration) must not
            // abort the offline batch — count it (surfaced to the caller, not
            // silently swallowed) and move on. Phase-1 idempotency only suppresses
            // keys that actually produced a gist, so an un-written key is retried
            // next consolidation cycle.
            ++outcome.failed;
        }
    }
    return outcome;
}

}  // namespace starling::replay

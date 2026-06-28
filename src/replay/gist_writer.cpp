#include "starling/replay/gist_writer.hpp"

#include "starling/bus/bus.hpp"
#include "starling/extractor/extracted_statement.hpp"
#include "starling/extractor/llm_adapter.hpp"
#include "starling/replay/gist_prompt.hpp"
#include "starling/schema/statement_enums.hpp"
#include "starling/store/sqlite_statement_store.hpp"

#include <sqlite3.h>
#include <cstdint>
#include <exception>
#include <optional>
#include <stdexcept>
#include <string>
#include <string_view>
#include <variant>

namespace starling::replay {
namespace {

// Reserved synthetic identities for NORM gists. Deliberately NOT real
// Cognizer/Entity rows in v1 (the writer does no FK check, and a gist stays
// pending_review/inert until Phase 4 gates it). A norm reads
// "(common ground) people generally <predicate> <object>".
constexpr std::string_view kNormHolderId    = "__common_ground__";
constexpr std::string_view kNormSubjectKind = "entity";
constexpr std::string_view kNormSubjectId   = "__people__";

// Provisional confidence for the no-LLM (deterministic) path: above the
// validator's confidence_drop_floor (0.30) so the write is accepted; the gist
// stays inert (volatile + not-approved), never promoted.
constexpr double kProvisionalConfidence = 0.5;

// #38-C Phase 4 gating: a gist needs at least the confidence floor (LLM-judged) to
// be consolidated; below it → gated. The floor is now a parameter
// (write_gist_proposals' confidence_floor, default GistThresholds::min_confidence =
// 0.6), overridable from the dashboard "consolidation" config (v2 threshold tuning).
// It is deliberately above the validator's 0.30 write-floor — consolidation is a
// stronger bar than write.

// Deterministic span/idempotency key for a gist's statement.written event. entity-gist
// includes the SUBJECT (two entities sharing predicate+object don't collide); people-norm
// omits it (byte-identical to the pre-entity key).
std::string gist_span_key(std::string_view tenant_id, const GistCluster& cluster) {
    std::string key = "consolidation:" + std::string(tenant_id) + ":";
    if (!cluster.subject_id.empty()) {
        key += cluster.subject_id + ":";
    }
    return key + cluster.predicate + ":" + cluster.canonical_object_hash;
}

extractor::ExtractedStatement build_gist_statement(
    std::string_view tenant_id,
    const GistCluster& cluster,
    std::string_view now_iso,
    double confidence)
{
    extractor::ExtractedStatement stmt;
    stmt.holder_id             = std::string(kNormHolderId);
    stmt.holder_tenant_id      = std::string(tenant_id);
    stmt.holder_perspective    = schema::Perspective::INFERRED;
    // #38-C v2 entity-gist: a cluster carrying a subject is a consensus ABOUT that
    // specific entity → keep it; else the generic people-norm subject (__people__).
    const bool is_entity = !cluster.subject_id.empty();
    stmt.subject_kind          = is_entity ? cluster.subject_kind : std::string(kNormSubjectKind);
    stmt.subject_id            = is_entity ? cluster.subject_id : std::string(kNormSubjectId);
    stmt.predicate             = cluster.predicate;
    stmt.object_kind           = cluster.object_kind;
    stmt.object_value          = cluster.object_value;
    stmt.canonical_object_hash = cluster.canonical_object_hash;
    stmt.modality              = schema::Modality::BELIEVES;
    stmt.polarity              = schema::Polarity::POS;
    stmt.confidence            = confidence;  // LLM-judged (Phase 3) or provisional (no adapter)
    stmt.observed_at           = std::string(now_iso);
    // A norm is timeless in v1: no valid_from / valid_to / event_time_start.
    // source_hash is a required validator field; make it deterministic per key.
    // entity-gist includes the SUBJECT so a consensus about Bob ≠ one about Alice;
    // people-norm keeps the original subject-less key (byte-identical, no churn).
    stmt.source_hash           = is_entity
                                     ? "consolidation:" + stmt.subject_id + ":" +
                                           cluster.predicate + ":" + cluster.canonical_object_hash
                                     : "consolidation:" + cluster.predicate + ":" +
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

enum class GateDecision : std::uint8_t { Pass, Failed, Gated };

// Phase-3 judge + Phase-4 pre-write gates (confidence floor + independent
// entailment verification). Two LLM calls on the consolidation adapter. On Pass,
// `judgment` is filled (confidence + summary) for the write/promote. Failed = LLM
// error / unparseable; Gated = below floor or not entailed (a deliberate reject).
GateDecision gate_candidate(extractor::LLMAdapter& gist_llm, const GistCluster& cluster,
                            GistJudgment& judgment, double confidence_floor) {
    const extractor::LLMResponse judge_resp = gist_llm.generate(build_norm_gist_prompt(cluster));
    if (!judge_resp.ok) { return GateDecision::Failed; }
    judgment = parse_gist_judgment(judge_resp.raw_xml);
    if (!judgment.ok) { return GateDecision::Failed; }
    if (judgment.confidence < confidence_floor) { return GateDecision::Gated; }
    // Per-member entailment (#38-C v2 false-merge safety): verify the summary against
    // EACH member phrasing independently. A semantic cluster lists its VARIED objects,
    // so a false-merged outlier the summary does not entail gates the whole candidate;
    // an exact cluster (member_objects empty) checks its one shared object, as before.
    const std::vector<std::string> objects =
        cluster.member_objects.empty() ? std::vector<std::string>{cluster.object_value}
                                       : cluster.member_objects;
    for (const auto& object : objects) {
        const extractor::LLMResponse verify_resp =
            gist_llm.generate(build_entailment_prompt(cluster, object, judgment.summary));
        if (!verify_resp.ok) { return GateDecision::Failed; }
        const EntailmentVerdict verdict = parse_entailment_verdict(verify_resp.raw_xml);
        if (!verdict.ok) { return GateDecision::Failed; }
        if (!verdict.entailed) { return GateDecision::Gated; }
    }
    return GateDecision::Pass;
}

}  // namespace

GistWriteOutcome write_gist_proposals(persistence::SqliteAdapter& adapter,
                                      const std::vector<GistProposal>& proposals,
                                      std::string_view now_iso,
                                      extractor::LLMAdapter* gist_llm,
                                      double confidence_floor)
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
        // #38-C: with a consolidation LLM, JUDGE then GATE before any write, so a
        // candidate rejected by the PRE-WRITE gates (confidence floor / entailment)
        // leaves NO row — re-detectable next cycle, no confabulation rows. (The
        // separate conflict-archive path below DOES leave a suppressed row; that
        // is deliberate — a norm that conflicts with existing knowledge is not
        // retried.) No adapter ⇒ deterministic inert gist (Phase-2/3), never gated
        // or promoted.
        GistJudgment judgment;
        if (gist_llm != nullptr) {
            // Judge + gate (confidence floor + independent entailment verify) —
            // all BEFORE any write, so a rejected candidate leaves no row.
            const GateDecision decision =
                gate_candidate(*gist_llm, proposal.cluster, judgment, confidence_floor);
            if (decision == GateDecision::Failed) { ++outcome.failed; continue; }
            if (decision == GateDecision::Gated)  { ++outcome.gated;  continue; }
        }
        const double confidence =
            (gist_llm != nullptr) ? judgment.confidence : kProvisionalConfidence;
        const auto stmt =
            build_gist_statement(proposal.tenant_id, proposal.cluster, now_iso, confidence);
        // Deterministic span key per cluster so a re-emitted statement.written event
        // dedups on its idempotency_key (entity-gist adds the subject — see helper).
        const std::string span_key = gist_span_key(proposal.tenant_id, proposal.cluster);
        // Write through the pipeline (validation + conflict-probe + arbitration).
        // A gist has NO source engram — lineage is derived_from (stamped by the
        // writer); empty evidence_engram_id is honest (chunk-dup is a benign
        // no-op pre-gating). The writer forces consolidation_state='volatile';
        // the gist becomes live only via the explicit promote below.
        std::string stmt_id;
        try {
            const auto write_outcome =
                gist_bus.write(stmt, /*evidence_engram_id=*/"", span_key, std::nullopt);
            stmt_id = std::visit([](const auto& res) { return res.stmt_id; }, write_outcome);
        } catch (const std::exception&) {
            ++outcome.failed;  // validation / write error — un-written key retried next cycle
            continue;
        }
        if (gist_llm == nullptr) {
            ++outcome.written;  // no-LLM: inert gist (volatile + not-approved), never promoted
            continue;
        }
        // Gate (d) + promote: flip volatile+pending → consolidated+approved, but
        // ONLY if still volatile — if pipeline arbitration archived the gist on a
        // conflict, promote is a no-op (conflict ⇒ no auto-consolidate).
        try {
            store::SqliteStatementStore store(adapter.connection());
            if (store.promote_gist_to_consolidated(stmt_id, proposal.tenant_id, now_iso) > 0) {
                ++outcome.written;
                if (!judgment.summary.empty()) {
                    store.set_consolidation_summary(stmt_id, proposal.tenant_id, judgment.summary);
                }
            } else {
                // promote no-op ⇒ pipeline arbitration archived the gist on a
                // conflict. The archived consolidation_abstract row remains and
                // suppresses re-detection — a norm that conflicts with existing
                // knowledge is deliberately NOT retried (eng-review gate (d)).
                ++outcome.gated;
            }
        } catch (const std::exception&) {
            ++outcome.failed;  // promote SQL error (rare); gist left inert
        }
    }
    return outcome;
}

}  // namespace starling::replay

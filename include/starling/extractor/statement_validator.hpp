#pragma once

#include "starling/extractor/extracted_statement.hpp"
#include "starling/extractor/structured_output.hpp"
#include "starling/schema/statement_enums.hpp"

#include <functional>
#include <optional>
#include <string>
#include <vector>

namespace starling::extractor {

struct ValidationOutcome {
    bool                                accepted = false;
    std::string                         error_kind;     // empty when accepted
    std::string                         detail;         // human-readable
    std::optional<schema::ReviewStatus> review_status_override;  // set when accepted but downgraded

    bool ok() const { return accepted; }
};

// Deployment-tunable validator policy. A default-constructed ValidationPolicy
// reproduces the built-in behaviour byte-for-byte: extra_core_predicates is
// additive to the compile-time core set in predicate_registry.hpp (so it only
// suppresses the REVIEW_REQUESTED downgrade for the named non-OCCURRED
// predicates), and the two floors equal the historical 0.30 / 0.50 literals.
struct ValidationPolicy {
    std::vector<std::string> extra_core_predicates;   // ADDITIVE to the constexpr core set
    double confidence_drop_floor = 0.30;
    double weak_inference_floor  = 0.50;

    // OPT-IN (default OFF → fully additive): when ON, a FIRST-ORDER mental-state
    // statement (llm_nesting_depth==0, mental modality/predicate) is attributed
    // to its LLM-named bearer (cognizer-resolved) instead of the agent, so a
    // narrated 3rd-person attitude ("Xiao Ming wants a computer") lands under
    // holder_id=Xiao Ming and mental_state_of(character) finds it. Consumed only
    // by Extractor::run; the validator itself ignores this field.
    bool attribute_first_order_mental_to_holder = false;

    // Opt-in for clause-valued belief/general-fact objects. Preserve their
    // surface and hash it directly; noun-theme grounding remains the default.
    // Episodic entity themes are unaffected. Enable consistently per corpus;
    // switching does not migrate previously normalized objects or hashes.
    bool preserve_text_objects = false;

    // Experimental supplemental v2 path; never enables itself for base facts.
    bool semantic_claim_contract = false;
    bool claim_allow_code_fence = false;
    OutputMode claim_output_mode = OutputMode::Legacy;
    // Structured claim protocol correction attempts.  The native extractor
    // is the only owner of retry semantics; Python may only select 0 or 1.
    int claim_protocol_retry_budget = 0;
    // Opt-in native source-unit batches; zero retains the legacy single call.
    int claim_batch_size = 0;
    // Opt-in target-only evidence index; the complete payload remains context.
    bool claim_batch_target_units = false;

    // Single native policy authority, also exposed through Python bindings.
    void validate() const;
};

// M0.4 minimal validator. Enforces the §15.3.1 EXTRACTOR contracts
// (TC-Q2-001..004) and the §15.3.2 confidence / review_status defaults.
// Does NOT enforce cross-tenant explicit-protocol path (§3.11 — M0.5+)
// and does NOT run ConflictProbe (M0.5). Pure function: no DB, no I/O.
ValidationOutcome validate_extracted_statement(const ExtractedStatement& s,
                                               const ValidationPolicy& policy = {});

// M0.7: cross-tenant derived_from gate (§15.3.1 TC-NEG-CROSSTENANT).
// Runs the base validator first; on success, checks each parent id via
// resolve_parent_tenant. If a parent lives in a different tenant and
// provenance_protocol_id is empty, returns a rejection with
// error_kind="cross_tenant_derivation_forbidden". If protocol_id is set,
// returns accepted with review_status_override=REVIEW_REQUESTED.
// resolve_parent_tenant must return:
//   - the parent tenant when exactly one parent row is found,
//   - "" when the parent row is not found,
//   - an error sentinel (for example "ambiguous:<id>") when the bare
//     StatementRef is not enough to resolve a unique (id, tenant_id) row.
ValidationOutcome validate_for_write(
    const ExtractedStatement& s,
    const std::function<std::string(const std::string&)>& resolve_parent_tenant,
    const ValidationPolicy& policy = {});

}  // namespace starling::extractor

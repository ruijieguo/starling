#include "starling/extractor/statement_validator.hpp"

#include <functional>
#include <set>
#include <string>
#include <vector>

#include "starling/extractor/predicate_registry.hpp"

namespace starling::extractor {

namespace {

const std::set<std::string> kKnownObjectKinds = {
    "bool", "int", "float", "str", "datetime", "cognizer", "entity", "statement",
};

bool is_weak_inference(const ExtractedStatement& s, double weak_floor) {
    return s.holder_perspective == schema::Perspective::HEARSAY
        || s.holder_perspective == schema::Perspective::INFERRED
        || s.provenance == schema::StatementProvenance::TOM_INFERRED
        || s.confidence < weak_floor;
}

bool in_extra_set(const std::vector<std::string>& extra, const std::string& pred) {
    for (const auto& p : extra) { if (p == pred) return true; }
    return false;
}

}  // namespace

ValidationOutcome validate_extracted_statement(const ExtractedStatement& s,
                                               const ValidationPolicy& policy) {
    ValidationOutcome out;

    auto missing = [&](const char* field) {
        out.accepted = false;
        out.error_kind = "missing_required_field";
        out.detail = std::string("missing or empty: ") + field;
    };
    if (s.holder_id.empty())             { missing("holder_id");             return out; }
    if (s.holder_tenant_id.empty())      { missing("holder_tenant_id");      return out; }
    if (s.subject_kind.empty())          { missing("subject_kind");          return out; }
    if (s.subject_id.empty())            { missing("subject_id");            return out; }
    if (s.predicate.empty())             { missing("predicate");             return out; }
    if (s.object_kind.empty())           { missing("object_kind");           return out; }
    if (s.object_value.empty())          { missing("object_value");          return out; }
    if (s.canonical_object_hash.empty()) { missing("canonical_object_hash"); return out; }
    if (s.observed_at.empty())           { missing("observed_at");           return out; }
    if (s.source_hash.empty())           { missing("source_hash");           return out; }

    if (kKnownObjectKinds.find(s.object_kind) == kKnownObjectKinds.end()) {
        out.accepted = false;
        out.error_kind = "value_type_unsupported";
        out.detail = "object_kind not in {bool,int,float,str,datetime,cognizer,entity,statement}: " + s.object_kind;
        return out;
    }

    if (s.confidence < 0.0 || s.confidence > 1.0) {
        out.accepted = false;
        out.error_kind = "confidence_out_of_range";
        out.detail = "confidence must be in [0.0, 1.0]";
        return out;
    }
    if (s.confidence < policy.confidence_drop_floor) {
        out.accepted = false;
        out.error_kind = "below_minimum_confidence";
        out.detail = "confidence < 0.3 — extractor drops per §15.3.2";
        return out;
    }

    out.accepted = true;
    if (is_weak_inference(s, policy.weak_inference_floor)) {
        out.review_status_override = schema::ReviewStatus::INFERRED_UNREVIEWED;
    }
    // Controlled predicate set (system_design §3.3, P2 lightweight tier): an
    // unregistered (LLM-invented) predicate is accepted but downgraded to
    // REVIEW_REQUESTED — it outranks INFERRED_UNREVIEWED (human-action signal,
    // same precedence rule as validate_for_write's cross-tenant gate). The core
    // set mirrors the EXTRACTION_PROMPT vocabulary; raw-SQL/engine seeds bypass
    // this validator, so only the extraction path is gated.
    //
    // Sub-project A phase 3: episodic events (modality=OCCURRED) use open-domain
    // action verbs as their predicate ("Sally put ball in basket" → predicate=put).
    // For OCCURRED rows an out-of-set predicate is kept verbatim (NOT downgraded);
    // the curated action class (put/place/move/...) covers the common cases for
    // all modalities. Non-OCCURRED predicate validation is unchanged.
    if (!is_core_predicate(s.predicate)
        && !in_extra_set(policy.extra_core_predicates, s.predicate)
        && s.modality != schema::Modality::OCCURRED) {
        out.review_status_override = schema::ReviewStatus::REVIEW_REQUESTED;
    }
    return out;
}

// M0.7: cross-tenant derivation gate (§15.3.1 TC-NEG-CROSSTENANT).
ValidationOutcome validate_for_write(
    const ExtractedStatement& s,
    const std::function<std::string(const std::string&)>& resolve_parent_tenant,
    const ValidationPolicy& policy)
{
    // Run base field + confidence rules first.
    auto base = validate_extracted_statement(s, policy);
    if (!base.ok()) return base;

    bool any_cross_tenant_with_protocol = false;
    for (const auto& parent_id : s.derived_from) {
        const std::string parent_tenant = resolve_parent_tenant(parent_id);
        if (parent_tenant.empty()) {
            return {false, "derived_parent_not_found", parent_id, std::nullopt};
        }
        if (parent_tenant.rfind("ambiguous:", 0) == 0) {
            return {false, "derived_parent_ambiguous", parent_id, std::nullopt};
        }
        if (parent_tenant != s.holder_tenant_id) {
            if (s.provenance_protocol_id.empty()) {
                return {false, "cross_tenant_derivation_forbidden",
                        "parent_tenant=" + parent_tenant + " new_tenant=" + s.holder_tenant_id,
                        std::nullopt};
            }
            any_cross_tenant_with_protocol = true;
        }
    }
    if (any_cross_tenant_with_protocol) {
        // REVIEW_REQUESTED takes precedence over any base override (e.g. INFERRED_UNREVIEWED):
        // a human-action signal outranks an inference flag.
        base.review_status_override = schema::ReviewStatus::REVIEW_REQUESTED;
    }
    return base;
}

}  // namespace starling::extractor

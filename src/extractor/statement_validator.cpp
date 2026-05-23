#include "starling/extractor/statement_validator.hpp"

#include <set>
#include <string>

namespace starling::extractor {

namespace {

const std::set<std::string> kAllowedObjectKinds = {
    "bool", "int", "float", "str", "datetime", "cognizer", "entity", "statement",
};

bool is_weak_inference(const ExtractedStatement& s) {
    return s.holder_perspective == schema::Perspective::HEARSAY
        || s.holder_perspective == schema::Perspective::INFERRED
        || s.provenance == schema::StatementProvenance::TOM_INFERRED
        || s.confidence < 0.5;
}

}  // namespace

ValidationOutcome validate_extracted_statement(const ExtractedStatement& s) {
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

    if (kAllowedObjectKinds.find(s.object_kind) == kAllowedObjectKinds.end()) {
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
    if (s.confidence < 0.3) {
        out.accepted = false;
        out.error_kind = "below_minimum_confidence";
        out.detail = "confidence < 0.3 — extractor drops per §15.3.2";
        return out;
    }

    out.accepted = true;
    if (is_weak_inference(s)) {
        out.review_status_override = schema::ReviewStatus::INFERRED_UNREVIEWED;
    }
    return out;
}

}  // namespace starling::extractor

#pragma once

#include "starling/schema/statement_enums.hpp"

#include <cstdint>
#include <string>
#include <vector>

namespace starling::extractor {

// POD produced by xml_parser::parse_extractor_xml and consumed by
// statement_validator + StatementWriter. M0.4-minimal: no nesting_depth>0,
// no salience/affect, no derived_from. M0.5 will extend (or supersede) this
// when ConflictProbe + reconsolidation arrive.
struct ExtractedStatement {
    std::string                  holder_id;            // CognizerRef.id (UUID)
    std::string                  holder_tenant_id;     // for Statement.tenant_id derivation
    schema::Perspective          holder_perspective = schema::Perspective::INFERRED;

    std::string                  subject_kind;         // "cognizer" | "entity"
    std::string                  subject_id;           // resolved id (Cognizer or Entity)
    std::string                  predicate;            // controlled URI
    std::string                  object_kind;          // bool|int|float|str|datetime|cognizer|entity|statement
    std::string                  object_value;         // M0.1 canonicalize_object output
    std::string                  canonical_object_hash;// sha256 hex from canonicalize_object

    schema::Modality             modality       = schema::Modality::BELIEVES;
    schema::Polarity             polarity       = schema::Polarity::POS;
    double                       confidence     = 0.0;
    std::string                  observed_at;          // ISO-8601 UTC

    std::int32_t                 chunk_index    = 0;
    std::string                  source_hash;          // chunk content hash; persisted to source_spans_json
    std::vector<std::string>     perceived_by;         // CognizerRef.id list

    schema::StatementProvenance  provenance     = schema::StatementProvenance::USER_INPUT;
    schema::ReviewStatus         review_status  = schema::ReviewStatus::APPROVED;
};

}  // namespace starling::extractor

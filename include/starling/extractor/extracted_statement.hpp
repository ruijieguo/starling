#pragma once

#include "starling/schema/statement_enums.hpp"

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace starling::extractor {

// POD produced by json_parser::parse_extractor_json and consumed by
// statement_validator + StatementWriter. M0.4-minimal: no nesting_depth>0,
// no salience/affect. M0.7 adds derived_from (parent Statement.id list).
// M0.5 will extend (or supersede) this when ConflictProbe + reconsolidation arrive.
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

    // M0.5: time-interval fields (nullable; schema columns exist since M0.1)
    std::optional<std::string>   valid_from;           // ISO-8601 UTC, closed bound
    std::optional<std::string>   valid_to;             // ISO-8601 UTC, open bound (exclusive)
    std::optional<std::string>   event_time_start;     // ISO-8601 UTC, single-point (M0.5); end added M0.5+

    std::int32_t                 chunk_index    = 0;
    std::string                  source_hash;          // chunk content hash; persisted to source_spans_json
    std::vector<std::string>     perceived_by;         // CognizerRef.id list
    std::vector<std::string>     scope_parties;        // grounding 参与方（sorted{self,interlocutor}）；空=私有。独立于 perceived_by。

    schema::StatementProvenance  provenance     = schema::StatementProvenance::USER_INPUT;
    schema::ReviewStatus         review_status  = schema::ReviewStatus::APPROVED;

    std::vector<std::string>     derived_from;         // parent Statement.id list; empty for ingestion-root
    std::string                  provenance_protocol_id; // cross-tenant protocol key; empty = absent (§15.3.1)
};

}  // namespace starling::extractor

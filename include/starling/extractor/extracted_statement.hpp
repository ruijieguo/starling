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

    // ---- LLM-advisory fields (read from the extractor JSON, NOT trusted by the
    // writer; carried so the orchestrator can make attribution decisions) ----
    // The LLM's named attitude bearer ("holder" in the JSON). The default write
    // path IGNORES this (holder_id is the agent); it is consulted only when the
    // opt-in ValidationPolicy.attribute_first_order_mental_to_holder flag is ON,
    // to re-attribute first-order mental states to the narrated character. Empty
    // when the model omitted it.
    std::string                  llm_holder;
    // The LLM's emitted nesting_depth ("A believes B believes Z" => 2). The DB
    // nesting_depth is computed from object_kind (always 0 for str-objects), so
    // this advisory copy is the only signal of the model's first/second-order
    // intent. Default 0 (flat / first-order).
    std::int32_t                 llm_nesting_depth = 0;
};

}  // namespace starling::extractor

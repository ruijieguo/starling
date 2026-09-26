#pragma once

#include <cstddef>
#include <optional>
#include <string>
#include <vector>

#include "starling/persistence/connection.hpp"
#include "starling/retrieval/statement_row.hpp"
#include "starling/retrieval/temporal_evidence.hpp"

namespace starling::retrieval {

struct StructuredClaimRequest {
    std::string tenant_id;
    std::string holder_id;
    std::string subject_id;
    std::string predicate;
    std::string topic;
    std::string as_of_iso8601;
    int limit = 10;
    std::optional<TemporalEvidenceRequest> temporal;
};

struct StructuredClaimView {
    std::vector<StatementRow> selected;
    std::string receipt_json;
    bool sufficient = false;
    std::string insufficiency_reason;
    std::optional<TemporalEvidenceRef> early;
    std::optional<TemporalEvidenceRef> late;
    std::size_t input_candidates = 0;
    std::size_t excluded_scope = 0;
    std::size_t excluded_invalid_evidence = 0;
    std::size_t excluded_unknown_predicate = 0;
    std::size_t excluded_missing_order = 0;
};

StructuredClaimView select_structured_claims(
    persistence::Connection& conn,
    const std::vector<StatementRow>& candidates,
    const StructuredClaimRequest& request);

std::string structured_claim_view_json(const StructuredClaimView& view);

}  // namespace starling::retrieval

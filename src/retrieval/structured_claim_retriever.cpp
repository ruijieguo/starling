#include "starling/retrieval/structured_claim_retriever.hpp"

#include "starling/extractor/claim_contract.hpp"
#include "starling/retrieval/claim_evidence.hpp"

#include <algorithm>
#include <cctype>
#include <map>
#include <nlohmann/json.hpp>
#include <stdexcept>
#include <tuple>

namespace starling::retrieval {
namespace {
using Json = nlohmann::json;

bool blank(const std::string& value) {
    return value.empty() || std::all_of(value.begin(), value.end(), [](unsigned char c) {
        return std::isspace(c) != 0;
    });
}

Json ref_json(const TemporalEvidenceRef& ref) {
    return Json{{"tenant_id", ref.tenant_id}, {"statement_id", ref.statement_id},
                {"session_id", ref.session_id}, {"turn_index", ref.turn_index}};
}

bool row_matches_topic(const StatementRow& row, const std::string& topic) {
    if (topic.empty()) { return true;
}
    try {
        const auto claim = extractor::claim_strict_json(row.semantic_claim_json);
        return claim.contains("topic") && claim["topic"].is_string() &&
               claim["topic"].get<std::string>() == topic;
    } catch (const std::exception&) {
        return false;
    }
}
}

StructuredClaimView select_structured_claims(
    persistence::Connection& conn,
    const std::vector<StatementRow>& candidates,
    const StructuredClaimRequest& request) {
    StructuredClaimView view;
    view.input_candidates = candidates.size();

    if (blank(request.tenant_id) ||
        (blank(request.holder_id) && blank(request.subject_id))) {
        view.insufficiency_reason = "missing_scope";
        return view;
    }
    if (request.limit < 1) {
        view.insufficiency_reason = "invalid_limit";
        return view;
    }
    if (!request.as_of_iso8601.empty() &&
        !extractor::claim_is_explicit_utc_time(request.as_of_iso8601)) {
        view.insufficiency_reason = "invalid_as_of";
        return view;
    }
    if (!request.predicate.empty() &&
        extractor::canonical_claim_predicate(request.predicate).empty()) {
        ++view.excluded_unknown_predicate;
        view.insufficiency_reason = "unknown_predicate";
        return view;
    }
    const auto requested_predicate = extractor::canonical_claim_predicate(request.predicate);

    std::vector<StatementRow> eligible;
    std::vector<TemporalEvidenceCandidate> temporal_candidates;
    eligible.reserve(candidates.size());
    temporal_candidates.reserve(candidates.size());
    for (const auto& row : candidates) {
        if (row.tenant_id != request.tenant_id ||
            (!blank(request.holder_id) && row.holder_id != request.holder_id) ||
            (!blank(request.subject_id) && row.subject_id != request.subject_id)) {
            ++view.excluded_scope;
            continue;
        }
        if (!requested_predicate.empty() &&
            extractor::canonical_claim_predicate(row.predicate) != requested_predicate) {
            ++view.excluded_unknown_predicate;
            continue;
        }
        if (row.semantic_claim_json.empty() ||
            !claim_evidence_error(conn, row).empty()) {
            ++view.excluded_invalid_evidence;
            continue;
        }
        if (!row_matches_topic(row, request.topic)) {
            ++view.excluded_invalid_evidence;
            continue;
        }
        if (!request.as_of_iso8601.empty() && !row.observed_at.empty() &&
            row.observed_at > request.as_of_iso8601) {
            ++view.excluded_missing_order;
            continue;
        }
        eligible.push_back(row);
        temporal_candidates.push_back(TemporalEvidenceCandidate{row, row.confidence});
    }

    if (eligible.empty()) {
        view.insufficiency_reason = "no_candidates";
        view.receipt_json = structured_claim_view_json(view);
        return view;
    }

    if (request.temporal) {
        auto temporal_request = *request.temporal;
        if (temporal_request.tenant_id.empty()) { temporal_request.tenant_id = request.tenant_id;
}
        if (temporal_request.actor_id.empty()) { temporal_request.actor_id = request.subject_id;
}
        const auto temporal = select_temporal_evidence(temporal_candidates, temporal_request);
        view.early = temporal.early;
        view.late = temporal.late;
        view.insufficiency_reason = temporal.insufficiency_reason;
        if (temporal.early && temporal.late && temporal.sufficient) { view.sufficient = true;
}
        view.excluded_missing_order += temporal.excluded_missing_order;
        std::map<std::string, StatementRow> by_id;
        for (const auto& row : eligible) by_id.emplace(row.id, row);
        for (const auto& ref : temporal.selected) {
            const auto it = by_id.find(ref.statement_id);
            if (it != by_id.end() && view.selected.size() < static_cast<std::size_t>(request.limit))
                view.selected.push_back(it->second);
        }
    } else {
        std::sort(eligible.begin(), eligible.end(), [](const auto& left, const auto& right) {
            return std::tie(left.confidence, left.observed_at, left.id) >
                   std::tie(right.confidence, right.observed_at, right.id);
        });
        if (eligible.size() > static_cast<std::size_t>(request.limit)) {
            eligible.resize(static_cast<std::size_t>(request.limit));
}
        view.selected = std::move(eligible);
        view.sufficient = !view.selected.empty();
        if (!view.sufficient) { view.insufficiency_reason = "no_candidates";
}
    }
    view.receipt_json = structured_claim_view_json(view);
    return view;
}

std::string structured_claim_view_json(const StructuredClaimView& view) {
    Json selected = Json::array();
    for (const auto& row : view.selected) selected.push_back(row.id);
    return Json{{"schema_version", 1},
                {"sufficient", view.sufficient},
                {"insufficiency_reason", view.insufficiency_reason},
                {"selected", selected},
                {"early", view.early ? ref_json(*view.early) : Json(nullptr)},
                {"late", view.late ? ref_json(*view.late) : Json(nullptr)},
                {"input_candidates", view.input_candidates},
                {"excluded_scope", view.excluded_scope},
                {"excluded_invalid_evidence", view.excluded_invalid_evidence},
                {"excluded_unknown_predicate", view.excluded_unknown_predicate},
                {"excluded_missing_order", view.excluded_missing_order}}.dump();
}

}  // namespace starling::retrieval

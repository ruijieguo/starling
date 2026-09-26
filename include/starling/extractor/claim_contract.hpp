#pragma once
#include "starling/extractor/json_parser.hpp"
#include <string>
#include <string_view>
#include <vector>
#include <optional>
#include <map>
#include <nlohmann/json_fwd.hpp>

namespace starling::extractor {
struct ExtractionLlmResult;
struct ValidationPolicy;

std::string claim_extraction_batch_plan(std::string_view payload, const ValidationPolicy& policy);
// Shared by extraction and persistence replay. Global source IDs never change.
std::string claim_extraction_batch_prompt(std::string_view payload, std::string_view holder,
    int batch_index, const std::vector<std::string>& target_clause_ids, const ValidationPolicy& policy,
    const std::vector<ParseError>* previous_errors = nullptr);
struct ClaimBatchIntegrity {
    bool complete = false;
    std::string detail;
    bool extraction_failed = false; // valid attempt prefix ended in an original technical failure
};
// One native completion authority for reporting and the persistence boundary.
ClaimBatchIntegrity claim_batch_integrity(const ExtractionLlmResult& result,
                                         const ValidationPolicy* policy = nullptr);

// C++ 是结构化声明语义的唯一事实来源。绑定层只读映射这些字段，不能维护
// 第二份谓词、别名或模态规则。
struct PredicateSpec {
    std::string name;
    std::vector<std::string> aliases;
    std::string semantic_family;
    std::vector<std::string> allowed_modalities;
    std::vector<std::string> allowed_polarities;
    std::vector<std::string> subject_kinds;
    std::vector<std::string> object_kinds;
    bool supports_event_time = false;
    bool supports_topic = true;
};

struct PredicateCatalog {
    std::string version;
    std::vector<PredicateSpec> predicates;
};

// Whole nonempty lines, with source-owned UTF-8 byte positions. This is an
// evidence inventory, not a linguistic clause parser.
std::string claim_source_units(std::string_view payload);
// Render validated source-owned metadata; bindings pass JSON without reimplementing it.
std::string claim_source_turn_payload(std::string_view turns_json, bool preserve_invalid_time = false);
// Shared calendar validation for explicit native query/registration timestamps.
bool claim_is_explicit_utc_time(const std::string& value);
// Shared strict parser for model envelopes and native stored evidence.
nlohmann::json claim_strict_json(std::string_view raw);
std::string claim_extraction_prompt(std::string_view payload, std::string_view holder);
// Rebuilds the complete source-grounded contract prompt with a native
// protocol correction reminder.  It intentionally does not include the
// previous model response, so malformed JSON is never copied or repaired.
std::string claim_extraction_retry_prompt(std::string_view payload, std::string_view holder);
std::string claim_extraction_retry_prompt(std::string_view payload, std::string_view holder,
                                          const std::vector<ParseError>& errors);
std::string claim_admission_prompt(std::string_view payload, std::string_view candidates_json);
struct ClaimSemanticRejection {
    std::size_t index = 0;
    std::string kind;
    std::string detail;
    std::string predicate = {}; // 原生目录规范名；无法识别时显式标记未知
};
struct ClaimScopeResolution {
    std::string mode = "whole_unit";
    std::string reason;
    std::string coordinate_space;
    std::string clause_id;
    std::optional<std::size_t> begin;
    std::optional<std::size_t> end;
};
struct ClaimRowDiagnostic {
    std::size_t index = 0;
    std::optional<std::size_t> candidate_index;
    std::string outcome;
    std::optional<ClaimScopeResolution> scope_resolution;
};
struct ClaimParseResult : ParseResult {
    std::vector<ClaimSemanticRejection> semantic_rejections;
    std::vector<ClaimRowDiagnostic> row_diagnostics;
};
ClaimParseResult parse_claim_response(std::string_view raw, std::string_view payload,
                                 std::string_view holder, bool allow_code_fence = false,
                                 const std::vector<std::string>* target_clause_ids = nullptr);
std::string claim_parse_response_json(std::string_view raw, std::string_view payload,
                                      std::string_view holder, bool allow_code_fence = false);
std::string claim_candidates_json(const ParseResult& parsed);
struct ClaimAdmissionResult {
    std::vector<ParseError> errors;
    int semantic_rejected = 0;
    std::map<std::string, std::size_t> rejected_by_predicate;
};
ClaimAdmissionResult apply_claim_admission(std::string_view raw, ParseResult& parsed,
                                          bool allow_code_fence = false);
std::string claim_extraction_receipt(const ExtractionLlmResult& result);
nlohmann::json claim_predicate_catalog_json();
PredicateCatalog claim_predicate_catalog();
const PredicateSpec* find_claim_predicate(std::string_view name);
std::string canonical_claim_predicate(std::string_view name);
nlohmann::json claim_contract_catalog();
bool is_claim_predicate(std::string_view predicate);
} // namespace starling::extractor

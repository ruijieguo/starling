#pragma once
#include "starling/extractor/claim_contract.hpp"

namespace starling::extractor {
// 已完成 wire/主体校验的候选；只决定 QUESTIONED 守卫的输入范围。
ClaimScopeResolution resolve_claim_question_scope(
    std::string_view source, std::string_view coordinate_space,
    const nlohmann::json& row, const nlohmann::json& evidence,
    bool source_self_report);
}

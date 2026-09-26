#pragma once
#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <vector>
#include "starling/retrieval/statement_row.hpp"

namespace starling::retrieval {
struct TemporalEvidenceRequest {
    std::string tenant_id, actor_id, topic;
    std::vector<std::string> ordered_session_ids;
    std::string through_session_id;
    int limit = 10;
};
struct TemporalEvidenceCandidate { StatementRow row; double score = 0; };
struct TemporalEvidenceRef {
    std::string tenant_id, statement_id, session_id;
    std::int64_t turn_index = 0;
};
struct TemporalEvidenceView {
    bool sufficient = false;
    bool ambiguous = false;
    std::string insufficiency_reason;
    std::string topic;
    std::optional<TemporalEvidenceRef> early, late;
    std::vector<TemporalEvidenceRef> selected;
    std::size_t input_candidates = 0, eligible_candidates = 0;
    std::size_t excluded_after_cutoff = 0, excluded_scope = 0, excluded_topic = 0;
    std::size_t excluded_missing_order = 0, excluded_invalid_evidence = 0, duplicates = 0;
};
// 候选必须先通过调用方的权限、来源认证和相关性过滤。纯函数不读取数据库或生成事实。
TemporalEvidenceView select_temporal_evidence(const std::vector<TemporalEvidenceCandidate>& candidates,
                                              const TemporalEvidenceRequest& request);
std::string temporal_evidence_json(const TemporalEvidenceView& view);
} // namespace starling::retrieval

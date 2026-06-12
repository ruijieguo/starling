#include "starling/retrieval/context_pack.hpp"

#include <sstream>

namespace starling::retrieval {

namespace {
// evidence_json 是 EvidenceRef 数组;数 "engram_id" 出现次数即证据条数。
int evidence_count(std::string_view evidence_json) {
    int n = 0;
    std::string::size_type pos = 0;
    const std::string s(evidence_json);
    while ((pos = s.find("engram_id", pos)) != std::string::npos) { ++n; pos += 9; }
    return n;
}
}  // namespace

ContextPackLabel classify_with_provenance(const StatementRow& row,
                                          const PackContext& ctx,
                                          std::string_view provenance) {
    if (ctx.todo_ids.count(row.id))     return ContextPackLabel::TODO;
    if (ctx.conflict_ids.count(row.id)) return ContextPackLabel::CONFLICT;
    if (ctx.common_ids.count(row.id))   return ContextPackLabel::COMMON;
    if (!provenance.empty() && provenance != "user_input")
        return ContextPackLabel::INFERRED;
    const bool other_holder = !ctx.querier.empty() && row.holder_id != ctx.querier;
    if (other_holder && evidence_count(row.evidence_json) <= 1)
        return ContextPackLabel::HEARSAY;
    if (other_holder) return ContextPackLabel::BELIEF;
    if ((row.modality == "BELIEVES" || row.modality == "ASSUMES" ||
         row.modality == "DOUBTS") && row.confidence < 0.8)
        return ContextPackLabel::BELIEF;
    return ContextPackLabel::FACT;
}

ContextPackLabel classify(const StatementRow& row, const PackContext& ctx) {
    return classify_with_provenance(row, ctx, "user_input");
}

std::string render_line(const StatementRow& row, ContextPackLabel label) {
    std::ostringstream os;
    os << "[" << to_string(label) << "] "
       << row.subject_id << " " << row.predicate << " " << row.object_value;
    os.setf(std::ios::fixed); os.precision(2);
    os << " (conf " << row.confidence;
    if (!row.holder_id.empty()) os << ", holder " << row.holder_id;
    os << ")";
    return os.str();
}

std::string render_pack(const std::vector<PackEntry>& entries,
                        std::string_view abstention_reason) {
    if (!abstention_reason.empty()) {
        std::string s = "[ABSTAIN] 无可靠记忆,主动拒答(";
        s += abstention_reason; s += ")";
        return s;
    }
    std::ostringstream os;
    for (std::size_t i = 0; i < entries.size(); ++i) {
        if (i) os << "\n";
        os << entries[i].line;
    }
    return os.str();
}

}  // namespace starling::retrieval

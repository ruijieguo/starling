#pragma once

#include "starling/cognizer/knowledge_frontier.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/retrieval/statement_row.hpp"

#include <string>
#include <string_view>
#include <vector>

namespace starling::tom::mentalizing {

// ─── PODs ────────────────────────────────────────────────────────────────────

// Identifies a specific fact without knowing who holds it.
struct FactKey {
    std::string subject_kind;
    std::string subject_id;
    std::string predicate;
    std::string canonical_object_hash;
};

// Result of does_X_know.
enum class KnowsResult {
    FullKnowledge,  // X has asserted the fact with polarity=pos
    NotKnown,       // X hasn't asserted it, but visible evidence suggests they could
    Unknowable,     // No visible evidence path to the fact
};

// Result of find_misalignment.
struct Misalignment {
    std::vector<retrieval::StatementRow> only_x_believes;
    std::vector<retrieval::StatementRow> only_y_believes;
    // Pairs where same (predicate, canonical_object_hash) but |conf_x - conf_y| > 0.3
    std::vector<std::pair<retrieval::StatementRow, retrieval::StatementRow>> confidence_diverges;
};

// One fact believed by all queried members.
struct SharedFact {
    std::string subject_kind;
    std::string subject_id;
    std::string predicate;
    std::string canonical_object_hash;
    std::string polarity;
    std::vector<std::string> source_statement_ids;
};

// ─── Free functions ───────────────────────────────────────────────────────────

// 1. Returns all statements held by cognizer X about subject Y (subject_kind='cognizer').
// Optional modality_filter: if non-empty, adds AND modality = modality_filter.
std::vector<retrieval::StatementRow> what_does_X_believe(
    persistence::SqliteAdapter& adapter,
    std::string_view x,
    std::string_view about_y,
    std::string_view tenant,
    std::string_view as_of,
    std::string_view modality_filter = "");

// 2. Tri-valued know query: FullKnowledge / NotKnown / Unknowable.
KnowsResult does_X_know(
    persistence::SqliteAdapter& adapter,
    cognizer::KnowledgeFrontier& frontier,
    std::string_view x,
    const FactKey& fact_key,
    std::string_view tenant,
    std::string_view as_of);

// 3. Finds belief misalignments between X and Y about (subject_kind, subject_id).
Misalignment find_misalignment(
    persistence::SqliteAdapter& adapter,
    std::string_view x,
    std::string_view y,
    std::string_view subject_kind,
    std::string_view subject_id,
    std::string_view tenant,
    std::string_view as_of);

// 4. Returns facts believed by ALL members in member_cognizer_ids.
std::vector<SharedFact> shared_with(
    persistence::SqliteAdapter& adapter,
    const std::vector<std::string>& member_cognizer_ids,
    std::string_view tenant,
    std::string_view as_of);

// ─── P3.a2: 补全 7 API 的后三个 ───────────────────────────────────────────────

// 二阶查询结果:外层(X believes ref)+ 内层(被引用的原语句)。
struct NestedBelief {
    retrieval::StatementRow outer;
    retrieval::StatementRow inner;
};

// 5. 二阶 ToM:X 认为 Y 相信什么。展开 holder=X、subject=Y、
//    object_kind='statement' 的嵌套行,JOIN 内层语句。
std::vector<NestedBelief> what_does_X_think_Y_believes(
    persistence::SqliteAdapter& adapter,
    std::string_view x,
    std::string_view y,
    std::string_view tenant,
    std::string_view as_of);

// 预测依据(v1 诚实契约:返回可审计的 basis——X 的相关信念/偏好/承诺,
// 不编造预测文本;LLM 模拟归 P3+)。
struct PredictionBasis {
    std::vector<retrieval::StatementRow> beliefs;       // situation 相关信念
    std::vector<retrieval::StatementRow> preferences;   // predicate='prefers'
    std::vector<retrieval::StatementRow> commitments;   // 活跃承诺语句
};

// 6. predict_X_would:按 situation 关键词(LIKE 匹配 object_value/subject)
//    汇集 X 的行为依据。
PredictionBasis predict_X_would(
    persistence::SqliteAdapter& adapter,
    std::string_view x,
    std::string_view situation_keyword,
    std::string_view tenant,
    std::string_view as_of);

// 关于某事的未决承诺。
struct CommitmentFact {
    retrieval::StatementRow stmt;   // 承诺语句(holder=承诺人)
    std::string state;              // ACTIVE / created
    std::string deadline;           // "" if NULL
};

// 7. who_committed:object_value LIKE %about% 的活跃承诺(commitments JOIN)。
std::vector<CommitmentFact> who_committed(
    persistence::SqliteAdapter& adapter,
    std::string_view about,
    std::string_view tenant,
    std::string_view as_of);

}  // namespace starling::tom::mentalizing

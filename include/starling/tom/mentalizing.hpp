#pragma once

#include "starling/cognizer/knowledge_frontier.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/retrieval/statement_row.hpp"
#include "starling/tom/nesting_depth_writer.hpp"

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

// X's full mental state, grouped by propositional attitude. An out-of-the-box
// "what's in X's mind" aggregate over X's held statements (holder_id=x, as of as_of via
// valid_from/valid_to — NULL validity always visible; same time semantics as what_does_X_believe).
struct MentalState {
    std::vector<retrieval::StatementRow> beliefs;       // modality 'believes'
    std::vector<retrieval::StatementRow> knowledge;     // predicate 'knows'
    std::vector<retrieval::StatementRow> desires;       // modality 'desires'
    std::vector<retrieval::StatementRow> intentions;    // modality 'intends'
    std::vector<retrieval::StatementRow> commitments;   // modality 'commits'
    std::vector<retrieval::StatementRow> preferences;   // predicate 'prefers'
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

// 任意多阶 ToM:嵌套链上的一层(level 1 = 紧邻内层,递增到 depth-0 叶)。
// 字段是审计所需最小集(不复用 StatementRow 全列——链可深,只取定位列)。
struct ChainLevel {
    int level = 0;             // 1 = immediate inner; +1 per unwrap toward leaf
    std::string holder_id;
    std::string subject_id;
    std::string predicate;
    std::string object_kind;
    std::string object_value;
    std::string id;
};

// 二阶查询结果:外层(X believes ref)+ 内层(被引用的原语句)。
// .inner 保留 level-1 紧邻内层(向后兼容);.chain 是从 level-1 递归展开到
// depth-0 叶的有序全链(任意多阶 ToM)。
struct NestedBelief {
    retrieval::StatementRow outer;
    retrieval::StatementRow inner;
    std::vector<ChainLevel> chain;
};

// 5. 二阶 ToM:X 认为 Y 相信什么。展开 holder=X、subject=Y、
//    object_kind='statement' 的嵌套行,WITH RECURSIVE 递归展开整条嵌套链
//    (到 depth-0 叶或 level>=max_unwrap 止;靠 level 界做环安全)。
std::vector<NestedBelief> what_does_X_think_Y_believes(
    persistence::SqliteAdapter& adapter,
    std::string_view x,
    std::string_view y,
    std::string_view tenant,
    std::string_view as_of,
    int max_unwrap = nesting_depth_writer::kDefaultMaxNestingDepth);

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

// ─── per-family social-cognition operators ────────────────────────────────────

// A faux-pas precondition: `ignorant` doesn't know `unknown_fact`, which co-present
// `who_knows` cognizers DO know. The structural setup of a faux pas (the speaker may
// then say something inappropriate). Semantic sensitivity is NOT judged here.
struct FauxPasCandidate {
    std::string ignorant;
    retrieval::StatementRow unknown_fact;
    std::vector<std::string> who_knows;
};

// Scan cast × established facts: for each fact F, classify each cast cognizer via
// does_X_know (Unknowable -> ignorant; NotKnown/FullKnowledge -> knower). Emit a
// candidate per ignorant cognizer when at least one cast cognizer knows F. Cast =
// distinct cognizers in perception_state; facts = distinct (subject_kind,subject_id,
// predicate,canonical_object_hash) over consolidated statements.
std::vector<FauxPasCandidate> detect_faux_pas(
    persistence::SqliteAdapter& adapter,
    cognizer::KnowledgeFrontier& frontier,
    std::string_view tenant,
    std::string_view as_of);

// ─── sub-project B: perception → belief ──────────────────────────────────────

// X's last-perceived state of a theme (sub-project B). has_belief=false → X never
// perceived any state-event for the theme.
struct StateBelief {
    bool has_belief = false;
    std::string state_dim;       // "location" | "content"
    std::string state_value;
    std::string source_event_id;
    bool is_stale = false;       // state_value != global latest actual state
};

// 8. First/second-order: X's last-perceived state of `theme`. observer="" → first
//    order; observer set → restrict to events both observer and x perceived.
StateBelief what_does_X_think(
    persistence::SqliteAdapter& adapter,
    cognizer::KnowledgeFrontier& frontier,
    std::string_view x,
    std::string_view theme,
    std::string_view tenant,
    std::string_view as_of,
    std::string_view observer = "");

// 9. 任意多阶感知 ToM:chain=[c1..cN],"c1 think c2 think … cN think theme is where"。
//    holder=cN,observers=c1..c_{N-1}。返回 holder 在「所有链成员都感知过的事件」中
//    position 最高的状态。N=1 等价一阶;N=2 等价 what_does_X_think 的 observer 分支。
//    空链 / dim 不可定 / 无交集行 → has_belief=false。
StateBelief what_does_X_think_chain(
    persistence::SqliteAdapter& adapter,
    cognizer::KnowledgeFrontier& frontier,
    const std::vector<std::string>& chain,
    std::string_view theme,
    std::string_view tenant,
    std::string_view as_of);

// 10. X's full mental state, bucketed by attitude. Predicate-first ('prefers'->preferences,
//     'knows'->knowledge), else by modality. occurred/norm_*/enforces/observes dropped
//     (not propositional attitudes). Unknown X -> all empty.
MentalState mental_state_of(
    persistence::SqliteAdapter& adapter,
    std::string_view x,
    std::string_view tenant,
    std::string_view as_of);

}  // namespace starling::tom::mentalizing

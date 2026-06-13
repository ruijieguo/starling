#include "starling/retrieval/pattern_completor.hpp"

#include <sqlite3.h>
#include <algorithm>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

#include "starling/persistence/sqlite_helpers.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/store/sqlite_meta_store.hpp"

namespace starling::retrieval {

namespace {
using starling::persistence::detail::make_sqlite_error;
using starling::persistence::StmtHandle;

// per-kind 乘子;P2.d 全部传播边默认 1.0(MAY_OVERLAP_WITH 用存储余弦权)。
double kind_multiplier(const std::string& /*kind*/) { return 1.0; }

// edge_weight = kind_multiplier × clamp(stored_weight, 0, 1)。
double edge_weight(const std::string& kind, double stored_weight) {
    double w = stored_weight;
    if (w < 0.0) w = 0.0;
    if (w > 1.0) w = 1.0;
    return kind_multiplier(kind) * w;
}

// frontier id 集合 → JSON 数组字面量。statement id 为 UUID(无引号/反斜杠),手工拼安全。
std::string build_frontier_json(const std::unordered_map<std::string, double>& activation) {
    std::string s = "[";
    bool first = true;
    for (const auto& kv : activation) {
        if (!first) s += ",";
        s += "\"" + kv.first + "\"";
        first = false;
    }
    s += "]";
    return s;
}

struct EdgeHit { std::string src_id, target_id, edge_kind; double weight; };

// 每跳边扩展:前向(前沿作 src,target=dst,所有传播边) + 对称反向(前沿作 dst,
// target=src,仅 MAY_OVERLAP_WITH)。scope 谓词逐字对齐 search_topk,隐私永不放宽。
std::vector<EdgeHit> expand(persistence::Connection& conn,
                            const std::string& frontier_json,
                            const PatternCompletionParams& p) {
    const char* sql =
        "SELECT f.value AS src_id, e.dst_id AS target_id, e.edge_kind, e.weight"
        "  FROM json_each(?1) f"
        "  JOIN statement_edges e ON e.tenant_id = ?2 AND e.src_id = f.value"
        "  JOIN statements s ON s.id = e.dst_id AND s.tenant_id = e.tenant_id"
        " WHERE e.edge_kind IN ('MAY_OVERLAP_WITH','derived_from','evidence',"
        "                       'OBSERVED_BY','SHARED_GROUND')"
        "   AND (?3 = '' OR s.holder_id = ?3)"
        "   AND (?4 = '' OR s.holder_perspective = ?4)"
        "   AND s.consolidation_state IN ('consolidated','archived')"
        "   AND s.review_status NOT IN ('rejected','pending_review')"
        " UNION ALL "
        "SELECT f.value AS src_id, e.src_id AS target_id, e.edge_kind, e.weight"
        "  FROM json_each(?1) f"
        "  JOIN statement_edges e ON e.tenant_id = ?2 AND e.dst_id = f.value"
        "  JOIN statements s ON s.id = e.src_id AND s.tenant_id = e.tenant_id"
        " WHERE e.edge_kind IN ('MAY_OVERLAP_WITH')"
        "   AND (?3 = '' OR s.holder_id = ?3)"
        "   AND (?4 = '' OR s.holder_perspective = ?4)"
        "   AND s.consolidation_state IN ('consolidated','archived')"
        "   AND s.review_status NOT IN ('rejected','pending_review')";
    sqlite3* db = conn.raw();
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "PatternCompletor::expand prepare");
    StmtHandle h{raw};
    auto bind_txt = [raw](int i, const std::string& v) {
        sqlite3_bind_text(raw, i, v.c_str(), -1, SQLITE_TRANSIENT);
    };
    bind_txt(1, frontier_json);
    bind_txt(2, p.tenant_id);
    bind_txt(3, p.holder_id);
    bind_txt(4, p.holder_perspective);

    auto col = [raw](int i) {
        const unsigned char* t = sqlite3_column_text(raw, i);
        return t ? std::string(reinterpret_cast<const char*>(t)) : std::string();
    };
    std::vector<EdgeHit> hits;
    while (sqlite3_step(raw) == SQLITE_ROW) {
        hits.push_back(EdgeHit{col(0), col(1), col(2), sqlite3_column_double(raw, 3)});
    }
    return hits;
}

// Fetch a full StatementRow by (id, tenant) re-checking visibility.
// P3.b1 phase 3:读收编进 MetaStore;query_statements 默认守卫(state IN
// (consolidated,archived) + review NOT IN(rejected,pending_review))= 原
// kSelectByIdSql 的 visibility 二次校验(走每跳 scope 之上的 defense-in-depth)。
// 空结果 → 空 row(空 id 表示 vanished / not visible,与原行为一致)。
StatementRow fetch_row(persistence::Connection& conn, const std::string& id,
                       const std::string& tenant) {
    store::SqliteMetaStore meta(conn);
    store::StatementFilter f;
    f.tenant_id = tenant;
    f.id_in = {id};
    const auto rows = meta.query_statements(f);
    return rows.empty() ? StatementRow{} : rows.front();
}

}  // namespace

CompletionResult PatternCompletor::complete(persistence::Connection& conn,
                                            const PatternCompletionParams& params) {
    CompletionResult out;

    // Step 1: seeds via vector_recall (privacy-first; reused verbatim).
    SemanticRetrieverParams sp;
    sp.tenant_id = params.tenant_id;
    sp.holder_id = params.holder_id;
    sp.holder_perspective = params.holder_perspective;
    sp.query_text = params.cue_text;
    sp.k = params.seed_k;
    sp.trace_id = params.trace_id;
    sp.query_id = params.query_id;
    auto seeds = seeds_.vector_recall(conn, sp);
    out.degraded = seeds.degraded;
    if (seeds.rows.empty()) return out;  // no seeds → no walk

    // Step 2: activation init (seeds at 1.0).
    std::unordered_map<std::string, double> activation;
    std::unordered_set<std::string> visited;
    for (const auto& s : seeds.rows) {
        activation[s.row.id] = 1.0;
        visited.insert(s.row.id);
    }

    // Step 3: spreading-activation walk（06_hippocampus.md §3）。
    int node_count = static_cast<int>(visited.size());
    bool truncated = false;
    for (int step = 0; step < params.budget; ++step) {
        const std::string frontier_json = build_frontier_json(activation);
        auto hits = expand(conn, frontier_json, params);

        std::unordered_map<std::string, double> next;
        for (const auto& e : hits) {
            const double contrib =
                activation[e.src_id] * edge_weight(e.edge_kind, e.weight) * params.decay;
            if (contrib < params.theta_propagate) continue;
            auto it = next.find(e.target_id);
            if (it == next.end() || contrib > it->second) next[e.target_id] = contrib;
        }

        bool changed = false;
        for (const auto& kv : next) {
            if (visited.insert(kv.first).second) ++node_count;
            auto it = activation.find(kv.first);
            if (it == activation.end()) {
                activation[kv.first] = kv.second;
                changed = true;
            } else if (kv.second > it->second) {
                it->second = kv.second;
                changed = true;
            }
        }

        if (node_count >= params.node_cap) { truncated = true; break; }
        // 收敛:本步既无新节点也无激活抬升 → 达不动点即停。(设计的 max(activation)<θ
        //  被种子 1.0 支配永不触发;"无新节点且无抬升"才是 value-exact 收敛判据。激活
        //  单调递增且有上界 → 必收敛;budget 为兜底上限。)
        if (!changed) break;
    }
    out.completion_truncated = truncated;

    // Step 4: top result_k by activation desc.
    std::vector<std::pair<std::string, double>> ranked(activation.begin(), activation.end());
    std::sort(ranked.begin(), ranked.end(),
              [](const auto& a, const auto& b) { return a.second > b.second; });
    if (static_cast<int>(ranked.size()) > params.result_k)
        ranked.resize(static_cast<size_t>(params.result_k));

    for (const auto& [id, act] : ranked) {
        StatementRow row = fetch_row(conn, id, params.tenant_id);
        if (row.id.empty()) continue;  // vanished between walk and fetch
        out.rows.push_back(CompletionScored{std::move(row), act});
    }
    return out;
}

}  // namespace starling::retrieval

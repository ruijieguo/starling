#include "starling/hippocampus/affect_buffer.hpp"

#include "starling/store/sqlite_meta_store.hpp"

namespace starling::hippocampus::affect_buffer {

std::vector<std::string> member_ids(persistence::Connection& conn,
                                    std::string_view tenant_id,
                                    const Config& cfg) {
    // P3.b1 phase 3:读收编进 MetaStore.query_statements。salience_ge=θ_buffer、
    // 无 review 守卫(原行为)、双键 salience DESC/created_at ASC、limit=capacity。
    store::SqliteMetaStore meta(conn);
    store::StatementFilter f;
    f.tenant_id            = std::string(tenant_id);
    f.consolidation_states = {"volatile"};
    f.salience_ge          = cfg.theta_buffer;
    f.default_review_guard = false;
    f.order_by             = "salience DESC, created_at ASC";
    f.limit                = cfg.capacity;
    std::vector<std::string> out;
    for (const auto& r : meta.query_statements(f)) out.push_back(r.id);
    return out;
}

std::unordered_set<std::string> member_set(persistence::Connection& conn,
                                           std::string_view tenant_id,
                                           const Config& cfg) {
    const auto ids = member_ids(conn, tenant_id, cfg);
    return {ids.begin(), ids.end()};
}

}  // namespace starling::hippocampus::affect_buffer

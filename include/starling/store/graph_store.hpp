#pragma once
// GraphStore — 关系/图类存储接口(P3.b1)。引擎无关:SQLite backend(phase 1)
// 与 LadybugDB backend(phase 6 后置)都实现它。
//
// 当前覆盖 statement_edges(CONFLICTS_WITH / MAY_OVERLAP_WITH / supersedes);
// cognizer_relations(社会图)在 phase 4 路由 cognizer_hub 时并入。
//
// 接口签名不带引擎特定句柄(无 SQLite Connection&)——SQLite backend 经其持有
// 的单写者 adapter 连接读写(与现有 bus 事务同连接,phase 4 路由后行为不变);
// LadybugDB backend 持有自己的 DB 句柄。
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace starling::store {

struct EdgeRecord {
    std::string tenant_id;
    std::string src_id;
    std::string dst_id;
    std::string edge_kind;
    double weight = 1.0;
    std::optional<std::string> canonical_conflict_key;
    std::string metadata_json = "{}";
    std::string created_at;   // 空 → backend 盖当前时间
};

struct EdgeOut {
    std::string id;
    std::string src_id;
    std::string dst_id;
    std::string edge_kind;
    double weight = 1.0;
    std::optional<std::string> canonical_conflict_key;
};

class GraphStore {
public:
    virtual ~GraphStore() = default;

    // 插入一条边(当前语义=plain insert,与 bus::insert_statement_edge 一致;
    // 去重不变式由调用方/UNIQUE 约束持有,不在此隐式 dedup)。返回 edge id。
    virtual std::string insert_edge(const EdgeRecord&) = 0;

    // 取 src 在给定 edge_kind 集合下的直接邻居(weight 一并返回)。
    // kinds 为空 = 不限 kind。
    virtual std::vector<EdgeOut> neighbors(std::string_view tenant_id,
                                           std::string_view src_id,
                                           const std::vector<std::string>& kinds) = 0;

    // 按 canonical_conflict_key 查边(冲突去重查询)。
    virtual std::vector<EdgeOut> edges_by_conflict_key(std::string_view tenant_id,
                                                       std::string_view key) = 0;
};

}  // namespace starling::store

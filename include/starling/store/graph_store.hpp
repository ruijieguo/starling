#pragma once
// GraphStore — 关系/图类存储接口(P3.b1)。引擎无关:SQLite backend(phase 1)
// 与 LadybugDB backend(phase 6 后置)都实现它。
//
// 当前覆盖 statement_edges(conflicts_with / MAY_OVERLAP_WITH / supersedes 等);
// cognizer_relations(社会图)并入 defer 至 phase 6(LadybugDB go 后随社会图换装,
// 见 plan Task 4.3)——异构图 schema 不提前塞进 statement-edge 接口。
//
// 接口方法签名不带引擎特定句柄——SQLite backend 构造时注入单写者 Connection&
// 读写(各 edge 写者用各自事务的 conn,与现有 bus 事务同连接、原子性不变);
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

// insert_edge 结果:正常插入返回新边 id;conflicts_with 的 canonical_conflict_key
// UNIQUE 命中时 deduped=true、id 空(已存在边保留,未插入)。
struct EdgeInsert {
    std::string id;
    bool deduped = false;
};

class GraphStore {
public:
    virtual ~GraphStore() = default;

    // 插入一条边。conflicts_with 边的 canonical_conflict_key UNIQUE(0009 partial
    // index)命中时静默 dedup(deduped=true,不插入),封装 spec §8.4 冲突去重;其余
    // 边 plain insert。dedup 命中的 WARN 日志由调用方据 deduped 决定(业务日志不入 store)。
    virtual EdgeInsert insert_edge(const EdgeRecord&) = 0;

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

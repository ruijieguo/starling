#pragma once
// SqliteGraphStore — GraphStore 的 local-store(SQLite)backend(P3.b1 phase 1)。
// 持有单写者 Connection 读写 statement_edges。phase 4 路由后各 edge 写者用各自
// 事务的 conn 构造(与 SqliteStatementStore 对称),故与现有 bus/arbitration/
// embedding/commitment 事务同连接、原子性与行为不变。
#include "starling/persistence/connection.hpp"
#include "starling/store/graph_store.hpp"

namespace starling::store {

class SqliteGraphStore : public GraphStore {
public:
    explicit SqliteGraphStore(persistence::Connection& conn) : conn_(conn) {}

    EdgeInsert insert_edge(const EdgeRecord&) override;
    std::vector<EdgeOut> neighbors(std::string_view tenant_id,
                                   std::string_view src_id,
                                   const std::vector<std::string>& kinds) override;
    std::vector<EdgeOut> edges_by_conflict_key(std::string_view tenant_id,
                                               std::string_view key) override;

private:
    persistence::Connection& conn_;
};

}  // namespace starling::store

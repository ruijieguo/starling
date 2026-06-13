#pragma once
// SqliteGraphStore — GraphStore 的 local-store(SQLite)backend(P3.b1 phase 1)。
// 经持有的单写者 adapter 连接读写 statement_edges,故 phase 4 路由后与现有
// bus 事务同连接、行为不变。
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/store/graph_store.hpp"

namespace starling::store {

class SqliteGraphStore : public GraphStore {
public:
    explicit SqliteGraphStore(persistence::SqliteAdapter& adapter)
        : adapter_(adapter) {}

    std::string insert_edge(const EdgeRecord&) override;
    std::vector<EdgeOut> neighbors(std::string_view tenant_id,
                                   std::string_view src_id,
                                   const std::vector<std::string>& kinds) override;
    std::vector<EdgeOut> edges_by_conflict_key(std::string_view tenant_id,
                                               std::string_view key) override;

private:
    persistence::SqliteAdapter& adapter_;
};

}  // namespace starling::store

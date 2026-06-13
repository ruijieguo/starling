#pragma once
// SqliteMetaStore —— MetaStore 的 local-store(SQLite)backend(P3.b1 phase 3)。
// 经持有 Connection& 读 statements(与写者同连接、同事务可见性)。
#include "starling/persistence/connection.hpp"
#include "starling/store/meta_store.hpp"

namespace starling::store {

class SqliteMetaStore : public MetaStore {
public:
    explicit SqliteMetaStore(persistence::Connection& conn) : conn_(conn) {}

    std::optional<retrieval::StatementRow> get_statement(
        std::string_view id, std::string_view tenant) override;
    std::vector<retrieval::StatementRow> query_statements(
        const StatementFilter&) override;

private:
    persistence::Connection& conn_;
};

}  // namespace starling::store

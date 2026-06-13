#pragma once
// SqliteStatementStore —— StatementStore 的 local-store(SQLite)backend
// (P3.b1 phase 2)。绑定 Connection&(写的实际单位):replay/recon/bus 的写者
// 都持有 Connection&(常在已开事务中),故路由后与原事务同连接、行为不变。
#include "starling/persistence/connection.hpp"
#include "starling/store/statement_store.hpp"

namespace starling::store {

class SqliteStatementStore : public StatementStore {
public:
    explicit SqliteStatementStore(persistence::Connection& conn) : conn_(conn) {}

    int mark_consolidated(const std::vector<std::string>&, std::string_view,
                          std::string_view) override;
    int reinforce(const std::vector<std::string>&, std::string_view,
                  std::string_view) override;
    int bump_replay_count(const std::vector<std::string>&, std::string_view,
                          std::string_view) override;
    int enter_reconsolidating(std::string_view, std::string_view) override;
    int restore_consolidated(std::string_view, std::string_view) override;
    int force_consolidate_pending_review() override;
    int archive(const std::vector<std::string>&, std::string_view,
                std::string_view, std::optional<std::string>) override;
    void apply_mild_correction(std::string_view, std::string_view, double,
                               std::string_view, std::string_view) override;
    void set_confidence_consolidated(std::string_view, std::string_view,
                                     double) override;
    void inherit_salience(std::string_view, std::string_view, double,
                          std::string_view) override;

private:
    persistence::Connection& conn_;
};

}  // namespace starling::store

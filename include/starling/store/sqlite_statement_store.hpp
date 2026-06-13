#pragma once
// SqliteStatementStore —— StatementStore 的 local-store(SQLite)backend
// (P3.b1 phase 2)。经持有的单写者 adapter 连接读写,故 phase 2 路由后与现有
// bus/replay/recon 事务同连接、行为不变。
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/store/statement_store.hpp"

namespace starling::store {

class SqliteStatementStore : public StatementStore {
public:
    explicit SqliteStatementStore(persistence::SqliteAdapter& adapter)
        : adapter_(adapter) {}

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
    persistence::SqliteAdapter& adapter_;
};

}  // namespace starling::store

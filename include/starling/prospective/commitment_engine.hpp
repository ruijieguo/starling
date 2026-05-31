#pragma once
#include <string>
#include <string_view>
#include "starling/persistence/sqlite_adapter.hpp"

namespace starling::prospective {

inline constexpr int kMaxBrokenCount = 3;
inline constexpr int kMaxRenegotiationChain = 3;

class CommitmentEngine {
public:
    explicit CommitmentEngine(persistence::SqliteAdapter& a) : adapter_(a) {}
    void create_from_statement(persistence::Connection&, std::string_view stmt_id,
                               std::string_view tenant_id, std::string_view deadline,
                               std::string_view now_iso);
    void fulfill(persistence::Connection&, std::string_view stmt_id,
                 std::string_view tenant_id, std::string_view now_iso);
    void withdraw(persistence::Connection&, std::string_view stmt_id,
                  std::string_view tenant_id, std::string_view now_iso);
    void on_deadline_expired(persistence::Connection&, std::string_view stmt_id,
                             std::string_view tenant_id, std::string_view now_iso);
    bool renegotiate(persistence::Connection&, std::string_view old_stmt_id,
                     std::string_view new_stmt_id, std::string_view tenant_id,
                     std::string_view now_iso);
    persistence::Connection& connection() { return adapter_.connection(); }
private:
    persistence::SqliteAdapter& adapter_;
};

}  // namespace starling::prospective

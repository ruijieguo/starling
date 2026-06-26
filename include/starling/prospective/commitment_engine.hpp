#pragma once
#include <string>
#include <string_view>
#include <vector>
#include "starling/persistence/sqlite_adapter.hpp"

namespace starling::prospective {

inline constexpr int kMaxBrokenCount = 3;
inline constexpr int kMaxRenegotiationChain = 3;

struct CommitmentView {
    std::string stmt_id, state, deadline;
    std::string subject_id, predicate, object_value;
    bool fired = false;
};

class CommitmentEngine {
public:
    explicit CommitmentEngine(persistence::SqliteAdapter& a) : adapter_(a) {}
    void create_from_statement(persistence::Connection&, std::string_view stmt_id,
                               std::string_view tenant_id, std::string_view deadline,
                               std::string_view now_iso);
    // Manual transitions: ACTIVE-only (atomically guarded). Return true iff the
    // commitment was ACTIVE and transitioned; false (no-op, no event emitted) for a
    // settled (FULFILLED/WITHDRAWN/FIRED/BROKEN/RENEGOTIATED) or missing commitment.
    bool fulfill(persistence::Connection&, std::string_view stmt_id,
                 std::string_view tenant_id, std::string_view now_iso);
    bool withdraw(persistence::Connection&, std::string_view stmt_id,
                  std::string_view tenant_id, std::string_view now_iso);
    void on_deadline_expired(persistence::Connection&, std::string_view stmt_id,
                             std::string_view tenant_id, std::string_view now_iso);
    bool renegotiate(persistence::Connection&, std::string_view old_stmt_id,
                     std::string_view new_stmt_id, std::string_view tenant_id,
                     std::string_view now_iso);
    std::vector<CommitmentView> pending(persistence::Connection& conn,
            std::string_view tenant_id, std::string_view holder_id,
            std::string_view interlocutor_id);
    persistence::Connection& connection() { return adapter_.connection(); }
private:
    persistence::SqliteAdapter& adapter_;
};

}  // namespace starling::prospective

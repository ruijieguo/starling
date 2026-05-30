#pragma once
#include "starling/persistence/sqlite_adapter.hpp"
#include <string>
#include <string_view>
#include <vector>

namespace starling::tom {

class CommonGroundWriter {
public:
    explicit CommonGroundWriter(persistence::SqliteAdapter& adapter);
    // assert: 新 CommonGround 条目 → asserted_unack. 返回 cg_id.
    std::string assert_(persistence::Connection& conn, std::string_view tenant_id,
                        std::string_view stmt_id, const std::vector<std::string>& parties,
                        std::string_view now_iso);
    // acknowledge: 显式确认 → grounded (grounded_at=now).
    void acknowledge(persistence::Connection& conn, std::string_view cg_id,
                     std::string_view actor, std::string_view now_iso);
    // repair: 质疑 → suspected_diverge.
    void repair(persistence::Connection& conn, std::string_view cg_id,
                std::string_view actor, std::string_view now_iso);
    // withdraw: 撤回 → recanted.
    void withdraw(persistence::Connection& conn, std::string_view cg_id,
                  std::string_view actor, std::string_view now_iso);
    // supersede_ground: 旧条目 superseded_by=new_stmt_id; (旧标记被取代).
    void supersede_ground(persistence::Connection& conn, std::string_view old_cg_id,
                          std::string_view new_stmt_id, std::string_view now_iso);
    // 24h 超时降级: asserted_unack > 24h 无 Ack/Repair → suspected_diverge. 返回降级数.
    int sweep_timeout_downgrade(persistence::Connection& conn, std::string_view now_iso);

    // Python binding helper.
    persistence::Connection& connection() { return adapter_.connection(); }

private:
    persistence::SqliteAdapter& adapter_;
};

}  // namespace starling::tom

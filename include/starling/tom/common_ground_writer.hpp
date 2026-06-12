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

    // ── P3.a2 补全(spec 09_tom Grounding Acts 七幕) ──
    // expire_ground: 共识过时/项目结束/retention 到期 → grounded → expired
    // (expired_at=now,不再享受 is_grounded 衰减保护)。
    void expire_ground(persistence::Connection& conn, std::string_view cg_id,
                       std::string_view actor, std::string_view now_iso);
    // unground: 共同知识被显式否认或 evidence 擦除 → grounded → suspected_diverge。
    void unground(persistence::Connection& conn, std::string_view cg_id,
                  std::string_view actor, std::string_view now_iso);
    // 人工确认(grounded 判定规则 #4):acknowledge + 落 audit_actor 列
    // (spec:人工确认必须保留审计 actor)。
    void acknowledge_manual(persistence::Connection& conn, std::string_view cg_id,
                            std::string_view audit_actor, std::string_view now_iso);

    // Python binding helper.
    persistence::Connection& connection() { return adapter_.connection(); }

private:
    persistence::SqliteAdapter& adapter_;
};

}  // namespace starling::tom

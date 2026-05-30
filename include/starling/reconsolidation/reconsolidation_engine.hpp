#pragma once
#include "starling/persistence/sqlite_adapter.hpp"
#include <string>
#include <string_view>

namespace starling::reconsolidation {

struct EngineStats { int events_processed=0; int windows_opened=0; int windows_closed=0; };

class ReconsolidationEngine {  // Outbox subscriber, tick-driven
public:
    explicit ReconsolidationEngine(persistence::SqliteAdapter& adapter);
    // 消费 last_checkpoint+1.. outbox 事件 → open_or_append 窗口.
    // 5 触发: statement.recalled / statement.references_existing / belief.conflict /
    //         (显式 reconsolidate) / commitment.fulfilled|broken (P2.c stub, 不开窗).
    EngineStats tick_one_batch(persistence::Connection& conn, std::string_view now_iso);
    // 仲裁所有 close_deadline<=now 的 open 窗口. TC-A5-002 双层兜底:
    //   仲裁抛异常 → 窗口仍标 closed + stmt 回 CONSOLIDATED (不卡死). 返回 closed 数.
    int close_due_windows(persistence::Connection& conn, std::string_view now_iso);
    // 显式 API (触发路径之一).
    void reconsolidate(persistence::Connection& conn, std::string_view stmt_id,
                       std::string_view event_type, std::string_view payload_hash,
                       double weight, std::string_view now_iso);
private:
    persistence::SqliteAdapter& adapter_;
};

}  // namespace starling::reconsolidation

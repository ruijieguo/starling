#pragma once
// Memory events — 按调用方给的稳定 key 记一次写入的收据(迁移 0038 的 events 表)。
//
// rise 的记忆写入要幂等:同一个 key 重放不会再抽取一次。收据行记下 key、原文、
// 说话对象、序号和状态(pending / committed / abandoned)。本头文件现在只放读侧:
// 序号时钟 next_seq 与待处理清单 pending_events。写侧(remember_event、
// abandon_event)随后续任务加进同一对文件。
//
// 状态机与查询放在 C++(Starling CLAUDE.md 的边界);Python 绑定只转发,门面只把
// 行包成 PendingEvent。
#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

#include "starling/persistence/connection.hpp"

namespace starling::memoryops {

// events 表里一条 state='pending' 的行,只带调用方恢复所需的字段。
struct PendingEventRow {
    std::string key;
    std::string text;
    std::string interlocutor;
    std::int64_t seq = 0;
    std::string failure_category;
};

// 本租户下一个可用序号:COALESCE(MAX(seq) + 1, 0)。含 abandoned 行,所以序号只增
// 不复用;空库为 0,第一条事件的 seq 就是 0。
[[nodiscard]] std::int64_t next_seq(persistence::Connection& conn, std::string_view tenant);

// 本租户 state='pending' 的行,按 seq 升序。committed 与 abandoned 不返回。
[[nodiscard]] std::vector<PendingEventRow> pending_events(persistence::Connection& conn,
                                                          std::string_view tenant);

}  // namespace starling::memoryops

#pragma once

// cleanup.hpp — 可回收世界与回滚归档的自动清理（spec §9，第 6 期）。
//
// 规则全在 C++：选出该删的世界（plan_cleanup），在注册表锁内重新核对后删除（execute_cleanup）。Python 只按
// 间隔调用、传入当前时刻与开着的世界，并在世界锁下确认引擎已关（Task 6.2）。C++ 不读墙钟：now_iso 由调用方给。
// 拿不准时一律少删（裁定 R56）。

#include "starling/governance/world_store.hpp"

#include <cstdint>
#include <set>
#include <string>
#include <string_view>
#include <vector>

namespace starling::governance {

class RegistryDb;

// 服务配置里可调（spec §9、§18）。三项都必须 >= 1，否则 invalid_settings。
struct CleanupConfig {
    std::int64_t keep_per_group = 200;       // 每个分组只保留最新的这么多个世界
    std::int64_t max_age_days = 14;          // 可回收世界只保留这么多天
    std::int64_t archive_max_age_days = 14;  // 不可回收世界的回滚归档只保留这么多天
};

// 一个要删的世界。reason："over_count" | "over_age"（两条都满足时记 over_age）。
// dir_id 是 plan 时注册表里的世界目录名：execute 时不同（世界被删了又以同名重建）就不删（裁定 R56 Q5）。
struct CleanupCandidate {
    std::string world, group, reason;
    std::string dir_id;
};

// 一个本该删、却跳过的世界。reason：plan 给 "held_snapshot"（有调用方持有的快照，spec §9）| "open"（调用方
// 说它开着）；execute 重新核对时还会给 "not_reclaimable" | "world_changed" | "failed"（detail 写原因）。
struct CleanupSkip {
    std::string world, reason;
    std::string group, detail;
};

// 一份到期的回滚归档（不可回收世界的 pre-rollback 旧库，按名字里的时刻算天数）。
struct CleanupArchive {
    std::string world, dir_id, name;
};

struct CleanupPlan {
    std::vector<CleanupCandidate> remove;
    std::vector<CleanupSkip> skip;
    std::vector<CleanupArchive> archives;
};

// 注册表里的一个世界，带着清理要看的两项（RegistryDb::cleanup_census，一次持锁读出）。record 不带标签。
struct CleanupCensusRow {
    WorldRecord record;
    bool has_held = false;     // 有 kind="held" 的快照
    bool is_default = false;   // 是默认世界
};

// 自动清理只碰的世界：reclaimable=1、不是种子、不是默认世界。种子即使标了 reclaimable 也不碰（spec §6.2）。
[[nodiscard]] bool cleanup_eligible(const WorldRecord& rec, bool is_default);

// 选出该删的世界与到期的归档，只读（不写注册表、不删文件）。cfg 不合法或 now_iso 不是 YYYY-MM-DDTHH:MM:SSZ
// 抛 invalid_settings。规则（spec §9，裁定 R56）：
//   - 只看 cleanup_eligible 的世界。
//   - 天数：now - created_at 严格大于 max_age_days 天 → over_age。
//   - 份数：retention_group 非空的世界按分组排，最新在前（created_at 降序；相同时后登记的在前）。排在
//     keep_per_group 之后的 → over_count（已是 over_age 的仍记 over_age）。retention_group 为空的世界不套份数
//     规则。被保护的世界（下面的 held、open）照样占名额。
//   - created_at 解析不了的世界两条规则都不选；在分组里按最新排，占一个名额。
//   - 选中的世界有 held 快照 → skip "held_snapshot"；否则在 open_worlds 里 → skip "open"；否则进 remove。
//     没选中的世界不出现在 skip 里。
//   - 归档：每个 reclaimable=0 的世界（含默认世界与种子）的 list_rollback_archives，名字里的时刻距 now 严格
//     大于 archive_max_age_days 天的进 archives。某个世界列不出来（布局校验不过等）只记 stderr，不影响别的世界。
//     可回收世界的归档不在这里：随世界一起删。
// remove 与 skip 按登记顺序排。
[[nodiscard]] CleanupPlan plan_cleanup(const RegistryDb& reg, const CleanupConfig& cfg,
                                       std::string_view now_iso,
                                       const std::set<std::string>& open_worlds);

}  // namespace starling::governance

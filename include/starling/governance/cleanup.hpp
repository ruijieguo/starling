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

// 一条清理记录（registry.db 的 cleanup_log 表，注册表 schema 2）。
//   action："removed"（删了一个世界）| "skipped"（跳过，reason 同 CleanupSkip）| "archive_removed"（删了一份
//   回滚归档，detail 是归档名）。reason：removed 是 over_count / over_age；archive_removed 是 over_age。
//   at 是 execute_cleanup 的 now_iso；group 是世界的 retention_group（可空）。
struct CleanupLogEntry {
    std::int64_t id = 0;   // 递增，越大越新
    std::string at, world, group, action, reason, detail;
};

// 最近的清理记录，最新在前，至多 limit 条。limit 不在 1–500 抛 invalid_world_query（与 RegistryDb::list 同一个码）。
[[nodiscard]] std::vector<CleanupLogEntry> cleanup_log(const RegistryDb& reg, std::int64_t limit);

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

// 删除 plan 里的世界与归档，写 cleanup_log，返回真正删掉（摘掉注册项）的世界。now_iso 同 plan_cleanup（解析不了抛
// invalid_settings，什么都不动）；记录的 at 就是它。
//
// 0. 先补删上一轮留下的待删目录（见下面的删除顺序）：只删 worlds/<dir_id>，而且这个 dir_id 必须在 cleanup_log 里
//    标成待删、在 worlds 表里已经没有（裁定 R56 补充 1）。dir_id 形状不对（空、"."、".."、含 '/' 或 '\\'）、
//    解析后不是 worlds/<dir_id> 本身（符号链接外链）的记录不删，只记 stderr。删完（或目录本来就不在）清掉标记；
//    删不掉的留着标记，下一轮再试。worlds/ 下别的东西一概不碰。
// 1. 对 plan.remove 的每个世界，在注册表锁内重新读它的记录与快照列表再判定（Review Focus 第 5 条）：
//      世界已不在 → 什么都不记；dir_id 与 plan 时不同 → skip world_changed；不再满足 cleanup_eligible
//      → skip not_reclaimable；有 held 快照 → skip held_snapshot；布局校验不过（dir_id 形状、worlds/ 外链、
//      世界目录解析后不是 worlds/<dir_id>）→ skip failed（detail 写原因）。
//    「此刻开着」的判定由调用方负责：Task 6.2 在世界锁下确认引擎已关、再把这个世界放进 plan 调用（open_worlds 在
//    plan_cleanup 时传入）；6.1 只保证上面这些在注册表锁内重新读取。
//    通过时的删除顺序（崩溃时只可能留下「注册项已摘、目录还在、有记录」，下一轮第 0 步补删）：
//      a. 注册表锁内、一个事务：写 removed 记录（dir_id、pending_dir=1），摘掉 worlds 行、标签、快照条目；
//      b. 锁外：remove_within(worlds/, worlds/<dir_id>) 删掉整个世界目录（库、快照、归档一起）；
//      c. 删完清掉这条记录的待删标记。b 失败（权限等）只记 stderr，标记留着，世界仍算删掉（注册项已摘）。
// 2. plan.skip 的每一项照写 skipped 记录。
// 3. 对 plan.archives 的每一份：世界还在、dir_id 相同、仍不 cleanup_eligible、这份归档仍出现在
//    list_rollback_archives 里，才经 remove_within(archive/, …) 删掉并写 archive_removed 记录（detail 是归档名）。
//    不满足或删不掉的跳过（不记）。调用方在该世界的世界锁下调用（与看板清理归档同一把锁）。
// skipped 记录去重：这个世界最新一条记录的 (action, reason) 与这次相同时不再写，所以每 10 分钟一轮不会刷屏。
// 一个世界失败不影响别的世界。
std::vector<CleanupCandidate> execute_cleanup(RegistryDb& reg, const CleanupPlan& plan,
                                              std::string_view now_iso);

}  // namespace starling::governance

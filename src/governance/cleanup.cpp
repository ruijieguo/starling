// cleanup.cpp — 见 include/starling/governance/cleanup.hpp。

#include "starling/governance/cleanup.hpp"

#include "world_store_internal.hpp"

#include "starling/governance/registry_db.hpp"

#include <algorithm>
#include <array>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <exception>
#include <filesystem>
#include <iostream>
#include <map>
#include <optional>
#include <string>
#include <utility>
#include <vector>

namespace starling::governance {

namespace {

using Seconds = std::chrono::sys_seconds;

constexpr std::int64_t kSecondsPerDay = 86'400;
constexpr std::string_view kPreRollback = ".pre-rollback-";
constexpr std::size_t kCompactStampLength = 16;   // 20261101T000000Z
constexpr std::int64_t kMaxLogLimit = 500;

[[noreturn]] void invalid(const std::string& detail) {
    throw WorldStoreError("invalid_settings", detail);
}

Seconds require_now(std::string_view now_iso) {
    const auto now = internal::parse_utc_seconds(now_iso);
    if (!now) { invalid("now is not YYYY-MM-DDTHH:MM:SSZ: '" + std::string(now_iso) + "'"); }
    return *now;
}

void require_config(const CleanupConfig& cfg) {
    const std::array<std::pair<const char*, std::int64_t>, 3> fields{{
        {"keep_per_group", cfg.keep_per_group},
        {"max_age_days", cfg.max_age_days},
        {"archive_max_age_days", cfg.archive_max_age_days},
    },};
    for (const auto& [field, value] : fields) {
        if (value < 1) { invalid(std::string("cleanup ") + field + " must be >= 1"); }
    }
}

// now - stamp 严格大于 days 天。stamp 晚于 now（时钟回拨）不算。不溢出：只做除法。
bool older_than(Seconds stamp, Seconds now, std::int64_t days) {
    const std::int64_t age = (now - stamp).count();
    return age > 0 && (age - 1) / kSecondsPerDay >= days;
}

// "<库文件名>.pre-rollback-20261101T000000Z-abcd" 里的时刻。形状或日期不对（20261399T…）返回 nullopt。
std::optional<Seconds> archive_stamp(std::string_view name) {
    const auto pos = name.rfind(kPreRollback);
    if (pos == std::string_view::npos) { return std::nullopt; }
    const std::string_view compact = name.substr(pos + kPreRollback.size(), kCompactStampLength);
    if (compact.size() != kCompactStampLength) { return std::nullopt; }
    // 20261101T000000Z → 2026-11-01T00:00:00Z，交给同一个严格解析函数（日期必须真实存在）。
    std::string iso;
    iso.append(compact.substr(0, 4)).append("-").append(compact.substr(4, 2)).append("-");
    iso.append(compact.substr(6, 2)).append("T").append(compact.substr(9, 2)).append(":");
    iso.append(compact.substr(11, 2)).append(":").append(compact.substr(13, 2)).append("Z");
    if (compact.at(8) != 'T' || compact.at(15) != 'Z') { return std::nullopt; }
    return internal::parse_utc_seconds(iso);
}

// 分组里排名用：最新在前。created_at 解析不了的排最前（按最新算、占名额、从不选中）；相同时刻后登记的在前。
struct Ranked {
    std::size_t pos = 0;                // 在 census 里的位置（登记顺序）
    std::optional<Seconds> created;
};

bool newer_first(const Ranked& lhs, const Ranked& rhs) {
    if (lhs.created.has_value() != rhs.created.has_value()) { return !lhs.created.has_value(); }
    if (lhs.created && *lhs.created != *rhs.created) { return *lhs.created > *rhs.created; }
    return lhs.pos > rhs.pos;
}

}  // namespace

std::vector<CleanupLogEntry> cleanup_log(const RegistryDb& reg, std::int64_t limit) {
    if (limit < 1 || limit > kMaxLogLimit) {
        throw WorldStoreError("invalid_world_query",
                              "cleanup_log limit must be 1-500 (got " + std::to_string(limit) + ")");
    }
    return reg.read_cleanup_log(limit);
}

bool cleanup_eligible(const WorldRecord& rec, bool is_default) {
    return rec.reclaimable && !rec.seed && !is_default;
}

CleanupPlan plan_cleanup(const RegistryDb& reg, const CleanupConfig& cfg, std::string_view now_iso,
                         const std::set<std::string>& open_worlds) {
    require_config(cfg);
    const Seconds now = require_now(now_iso);
    const std::vector<CleanupCensusRow> census = reg.cleanup_census();

    // 每个世界选中的原因（空 = 不选）。
    std::vector<std::string> reason(census.size());
    std::map<std::string, std::vector<Ranked>> groups;
    for (std::size_t pos = 0; pos < census.size(); ++pos) {
        const CleanupCensusRow& row = census.at(pos);
        if (!cleanup_eligible(row.record, row.is_default)) { continue; }
        const auto created = internal::parse_utc_seconds(row.record.created_at);
        if (created && older_than(*created, now, cfg.max_age_days)) { reason.at(pos) = "over_age"; }
        if (!row.record.retention_group.empty()) {
            groups[row.record.retention_group].push_back(Ranked{.pos = pos, .created = created});
        }
    }
    const auto keep = static_cast<std::uint64_t>(cfg.keep_per_group);
    for (auto& [group, members] : groups) {
        std::ranges::sort(members, newer_first);
        for (std::size_t rank = keep; rank < members.size(); ++rank) {
            const Ranked& member = members.at(rank);
            if (!member.created) { continue; }   // 解析不了：占名额，不选
            std::string& why = reason.at(member.pos);
            if (why.empty()) { why = "over_count"; }
        }
    }

    CleanupPlan plan;
    for (std::size_t pos = 0; pos < census.size(); ++pos) {
        const std::string& why = reason.at(pos);
        if (why.empty()) { continue; }
        const WorldRecord& rec = census.at(pos).record;
        if (census.at(pos).has_held) {
            plan.skip.push_back(CleanupSkip{.world = rec.name, .reason = "held_snapshot",
                                            .group = rec.retention_group, .detail = {},});
        } else if (open_worlds.contains(rec.name)) {
            plan.skip.push_back(CleanupSkip{.world = rec.name, .reason = "open",
                                            .group = rec.retention_group, .detail = {},});
        } else {
            plan.remove.push_back(CleanupCandidate{.world = rec.name, .group = rec.retention_group,
                                                   .reason = why, .dir_id = rec.dir_id,});
        }
    }

    // 归档：清理不会删的世界（不可回收、种子、默认世界），名字里的时刻超过 archive_max_age_days 天。
    for (const CleanupCensusRow& row : census) {
        if (cleanup_eligible(row.record, row.is_default)) { continue; }   // 随世界一起删
        std::vector<ArchiveEntry> listed;
        try {
            listed = list_rollback_archives(reg, row.record.name);
        } catch (const std::exception& err) {
            std::cerr << "[cleanup] cannot list archives of '" << row.record.name
                      << "': " << err.what() << "\n";
            continue;
        }
        for (const ArchiveEntry& item : listed) {
            const auto stamp = archive_stamp(item.name);
            if (!stamp || !older_than(*stamp, now, cfg.archive_max_age_days)) { continue; }
            plan.archives.push_back(CleanupArchive{.world = row.record.name,
                                                   .dir_id = row.record.dir_id,
                                                   .name = item.name,});
        }
    }
    return plan;
}

namespace {

namespace fs = std::filesystem;

// 删掉 worlds/<dir_id>（经 remove_within，不出 worlds/）。目录本来就不在算删完。返回删完没有；失败只记 stderr。
// 删除目标由 dir_id 推出，dir_id 必须是单独一级路径，且 worlds/<dir_id> 解析后恰好是它自己（不是外链）。
bool remove_world_home(const fs::path& data_dir, const std::string& dir_id, const std::string& label) {
    try {
        internal::require_plain_dir_id(dir_id, label, "snapshot_failed");
        const fs::path worlds_root = data_dir / "worlds";
        internal::require_worlds_root_inside(data_dir, worlds_root);
        const fs::path home = worlds_root / dir_id;
        std::error_code err;
        if (!fs::exists(fs::symlink_status(home, err))) { return true; }
        internal::require_resolved_home(worlds_root, dir_id, "snapshot_failed", label);
        if (!internal::remove_within(worlds_root, home)) {
            std::cerr << "[cleanup] " << home.string() << " resolves outside " << worlds_root.string()
                      << "; not removed\n";
            return false;
        }
        return true;
    } catch (const std::exception& err) {
        std::cerr << "[cleanup] cannot remove world directory of '" << label << "': " << err.what() << "\n";
        return false;
    }
}

// 第 0 步：补删上一轮留下的待删目录（裁定 R56 补充 1）。只删 cleanup_log 标成待删、worlds 表里已经没有的 dir_id。
void finish_pending_dirs(RegistryDb& reg) {
    for (const std::string& dir_id : reg.pending_cleanup_dirs()) {
        if (remove_world_home(reg.data_dir(), dir_id, dir_id)) { reg.clear_cleanup_pending(dir_id); }
    }
}

// 第 3 步的重新核对：世界还在、dir_id 相同、仍不归清理管、这份归档仍被 list_rollback_archives 列出。
bool archive_still_due(const RegistryDb& reg, const CleanupArchive& item, WorldRecord& rec) {
    try {
        rec = reg.get(item.world);
    } catch (const WorldStoreError&) {
        return false;
    }
    if (rec.dir_id != item.dir_id) { return false; }
    if (cleanup_eligible(rec, rec.name == reg.default_world())) { return false; }
    const auto listed = list_rollback_archives(reg, item.world);
    return std::ranges::any_of(listed, [&item](const ArchiveEntry& entry) { return entry.name == item.name; });
}

void remove_archive(RegistryDb& reg, const CleanupArchive& item, std::string_view now_iso) {
    try {
        WorldRecord rec;
        if (!archive_still_due(reg, item, rec)) { return; }
        const fs::path dir = reg.data_dir() / "worlds" / rec.dir_id / "archive";
        if (!internal::remove_within(dir, dir / item.name)) {
            std::cerr << "[cleanup] archive " << item.name << " of '" << item.world
                      << "' resolves outside its archive directory; not removed\n";
            return;
        }
        reg.append_archive_removed(item.world, rec.retention_group, item.name, now_iso);
    } catch (const std::exception& err) {
        std::cerr << "[cleanup] cannot remove archive " << item.name << " of '" << item.world
                  << "': " << err.what() << "\n";
    }
}

}  // namespace

std::vector<CleanupCandidate> execute_cleanup(RegistryDb& reg, const CleanupPlan& plan,
                                              std::string_view now_iso) {
    (void)require_now(now_iso);   // 任何改动之前
    finish_pending_dirs(reg);

    std::vector<CleanupCandidate> removed;
    for (const CleanupCandidate& candidate : plan.remove) {
        RegistryDb::UnregisterOutcome outcome;
        try {
            outcome = reg.unregister_for_cleanup(candidate, now_iso);
        } catch (const std::exception& err) {
            std::cerr << "[cleanup] cannot unregister '" << candidate.world << "': " << err.what() << "\n";
            continue;
        }
        if (!outcome.skipped.empty()) { continue; }
        removed.push_back(candidate);
        // 注册项已摘、记录已带待删标记：目录删不掉时留着标记，下一轮第 0 步再删。
        if (remove_world_home(reg.data_dir(), candidate.dir_id, candidate.world)) {
            reg.clear_cleanup_pending(candidate.dir_id);
        }
    }
    for (const CleanupSkip& skip : plan.skip) {
        try {
            (void)reg.append_cleanup_skip(skip, now_iso);
        } catch (const std::exception& err) {
            std::cerr << "[cleanup] cannot record skip of '" << skip.world << "': " << err.what() << "\n";
        }
    }
    for (const CleanupArchive& item : plan.archives) { remove_archive(reg, item, now_iso); }
    return removed;
}

}  // namespace starling::governance

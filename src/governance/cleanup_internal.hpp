#pragma once

// cleanup_internal.hpp — cleanup.cpp 与 registry_db.cpp 共用的清理规则。plan_cleanup 选世界，与 execute_cleanup 在注册表锁内
// 重算「是否仍到期」，用的是同一份代码（裁定 R70）。不属于公开 API，只供 src/governance 内部包含。

#include "starling/governance/cleanup.hpp"

#include <chrono>
#include <filesystem>
#include <string>
#include <string_view>
#include <vector>

namespace starling::governance::internal {

// 三项都 >= 1，否则 invalid_settings。
void require_cleanup_config(const CleanupConfig& cfg);
// YYYY-MM-DDTHH:MM:SSZ，否则 invalid_settings。
[[nodiscard]] std::chrono::sys_seconds require_cleanup_now(std::string_view now_iso);

// 每一行此刻按规则的到期原因："" | "over_age" | "over_count"（规则见 cleanup.hpp plan_cleanup）。rows 必须按登记顺序
// （worlds 的 rowid）排：份数规则相同时刻时后登记的算更新。只看 cleanup_eligible 的行，不看 held 与 open。要算份数，
// rows 必须含该分组的全部世界（plan 传整个注册表，重新核对传该分组的全部世界）。
[[nodiscard]] std::vector<std::string> cleanup_due_reasons(const std::vector<CleanupCensusRow>& rows,
                                                           const CleanupConfig& cfg,
                                                           std::chrono::sys_seconds now);
[[nodiscard]] inline bool is_cleanup_due(std::string_view reason) {
    return reason == "over_age" || reason == "over_count";
}

// 清理删世界目录之前的布局检查（裁定 R72 M8：注册表锁内的核对与锁外的删除共用这一份）：dir_id 是单独一级路径、
// <data_dir>/worlds 解析后仍在数据目录之下、worlds/<dir_id> 解析后恰好是它自己（不是指到别处的符号链接；还不存在时
// 照常通过）。规则与 RegistryDb::remove 相同。不通过（含解析出错，例如 EACCES）抛 snapshot_failed，消息点名 label。
// 返回 worlds/<dir_id>（未解析符号链接）。
[[nodiscard]] std::filesystem::path checked_cleanup_home(const std::filesystem::path& data_dir,
                                                         const std::string& dir_id, const std::string& label);

// reserve_home 生成的 dir_id 形状：16 位小写十六进制（裁定 R72 M2，补删只认这种）。
[[nodiscard]] bool is_generated_dir_id(std::string_view dir_id);

// 一份回滚归档按名字里的时刻（"<库文件名>.pre-rollback-<YYYYMMDDTHHMMSSZ>-<4 hex>"）距 now 严格大于
// archive_max_age_days 天。名字的形状或日期不对返回 false。
[[nodiscard]] bool cleanup_archive_due(std::string_view name, const CleanupConfig& cfg,
                                       std::chrono::sys_seconds now);

}  // namespace starling::governance::internal

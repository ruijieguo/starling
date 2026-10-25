#pragma once

// world_store.hpp — 世界注册表（W1）与快照（W2）的唯一权威实现。
//
// 设计稿：docs/superpowers/specs/2026-10-25-world-scene-management-design.md
//   §3 世界注册表、§4 快照。
//
// 一个世界 = 一个 SQLite 文件 + 一个租户 id。注册表 worlds.json 是世界路径的
// 唯一来源：任何 API 都不接受客户端传入文件路径。绑定层（Python / HTTP）只做
// 转发；注册、校验、保留策略与快照语义全部在这里。

#include <cstdint>
#include <filesystem>
#include <map>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace starling::governance {

class WorldStoreError : public std::runtime_error {
public:
    WorldStoreError(std::string code, const std::string& detail);
    [[nodiscard]] const std::string& code() const noexcept;
private:
    std::string code_;
};
// code 取值：invalid_world_name | world_exists | world_not_found | world_protected
//           | registry_corrupt | invalid_retention | snapshot_not_found
//           | insufficient_disk | snapshot_failed | world_tenant_mismatch

struct SnapshotEntry {
    std::string id;           // 20261025T011200Z-a1b2
    std::string path;         // 绝对路径
    std::string kind;         // "auto" | "manual"
    std::string reason;       // manual 时 "manual"
    std::string note;
    std::string created_at;   // ISO-8601 UTC 秒精度
    std::string world_time;   // 快照覆盖到的世界时刻水位，可为空
    std::int64_t size_bytes = 0;
};

struct WorldEntry {
    std::string name;
    std::string tenant;
    std::string db_path;      // 绝对路径
    std::string snapshot_dir; // 绝对路径
    std::string label;
    std::string created_at;
};

struct Registry {
    int version = 1;
    std::string default_world = "default";
    std::string active = "default";
    int snapshot_retention = 5;
    std::map<std::string, WorldEntry> worlds;                       // 按 name 排序
    std::map<std::string, std::vector<SnapshotEntry>> snapshots;    // world name → 列表
};

[[nodiscard]] bool is_valid_world_name(std::string_view name);
[[nodiscard]] Registry load_registry(const std::filesystem::path& registry_path);
void save_registry(const std::filesystem::path& registry_path, const Registry& reg);
// 注册表文件不存在时，创建只含 default 世界的注册表并保存。
// 注册表已存在时，原样返回，不修改 default 的路径。
[[nodiscard]] Registry ensure_registry(const std::filesystem::path& registry_path,
                                       const std::filesystem::path& default_db_path,
                                       const std::string& default_tenant);
// 新世界目录为 <registry_dir>/worlds/<name>/，库文件为 world.db，快照目录为 snapshots/。
// 只创建目录和注册项，不创建库文件，库文件留到首次激活时由 SqliteAdapter 建。
// tenant 固定为 name（新建世界不是分叉，没有来源租户）。
WorldEntry create_world(Registry& reg, const std::filesystem::path& registry_dir,
                        const std::string& name, const std::string& label,
                        std::string_view now_iso);
// 拒绝删除 default 和当前活动世界，抛 world_protected。
// 删除注册项、对应的快照列表，并删除 <registry_dir>/worlds/<name>/ 整个目录。
// 只删 registry_dir 之下的路径（防止注册表被篡改后删到外部目录）。
void delete_world(Registry& reg, const std::filesystem::path& registry_dir,
                  const std::string& name);
void set_active(Registry& reg, const std::string& name);

}  // namespace starling::governance

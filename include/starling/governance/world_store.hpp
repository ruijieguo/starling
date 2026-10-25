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
#include <functional>
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

// ---- 世界统计与快照（W2） --------------------------------------------------

struct WorldStats {
    std::int64_t db_bytes = 0;        // 主文件 + -wal 的字节数；文件不存在时为 0
    std::int64_t live_bytes = 0;      // (page_count - freelist_count) * page_size
    std::int64_t statements = 0;      // WHERE tenant_id = tenant
    std::int64_t engrams = 0;         // WHERE tenant_id = tenant
    std::string world_time;           // 见 snapshot_world_time
};
// 只读打开 db_path（mode=ro）。库文件不存在时返回全 0 的统计，不抛异常。
// 表不存在时（库是空的、未迁移），对应计数为 0。
[[nodiscard]] WorldStats world_stats(const std::string& db_path, const std::string& tenant);

// 世界时刻水位：source_unit_meta 存在且有非空 observed_at 时取 MAX(observed_at)，
// 否则取 engrams 的 MAX(created_at)，都没有则为空字符串。只读，按 tenant 过滤。
[[nodiscard]] std::string snapshot_world_time(const std::string& db_path,
                                              const std::string& tenant);

struct SnapshotOptions {
    std::string kind = "manual";      // "manual" | "auto"
    std::string reason = "manual";
    std::string note;
    // 测试注入用：返回可用字节数。为空时用 std::filesystem::space(dir).available。
    std::function<std::int64_t(const std::filesystem::path&)> free_space;
};

// 1. 取世界；不存在抛 world_not_found。
// 2. 只读打开 db_path，计算 live_bytes；free_space(snapshot_dir) < 3 * live_bytes 时
//    抛 insufficient_disk（不写任何文件）。
// 3. id = compact_now() + "-" + 4 位随机十六进制；与该世界已有的 id 重复时重新生成。
// 4. 删掉残留的 <id>.db.partial，再用只读连接执行 VACUUM INTO ?（绑定参数）写到 partial。
// 5. 关闭连接，再用只读连接打开 partial，PRAGMA integrity_check 必须为 "ok"，
//    否则删掉 partial 并抛 snapshot_failed。
// 6. fs::rename(partial, <id>.db)，填 size_bytes、world_time、created_at。
// 7. 插到 reg.snapshots[world] 的开头（最新在前），然后调用 apply_retention。
// 8. 不负责 save_registry，由调用方保存。
// 任何 SQLite 错误都转成 snapshot_failed，并保证不留下 partial 文件。
SnapshotEntry take_snapshot(Registry& reg, const std::string& world,
                            const SnapshotOptions& opts);

// 按保留份数 N 修剪 reg.snapshots[world]，并删除对应的文件，返回被删除的 id 列表。
// 规则（spec §4.4）：
//   - 总数 <= N：不删。
//   - 超出部分从最旧的开始删，优先删 auto；auto 删完还超出时才删 manual，从最旧的开始。
//   - 但列表里有 auto 时，至少保留最新的 1 份 auto（回滚锚点）。
std::vector<std::string> apply_retention(Registry& reg, const std::string& world);

// 删除一份快照（注册项 + 文件）。不存在时抛 snapshot_not_found。
// 只删 snapshot_dir 之下的文件（防篡改，规则同 delete_world）。
void delete_snapshot(Registry& reg, const std::string& world, const std::string& snapshot_id);

}  // namespace starling::governance

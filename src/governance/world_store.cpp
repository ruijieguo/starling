#include "starling/governance/world_store.hpp"

#include <nlohmann/json.hpp>

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <ctime>
#include <fstream>
#include <iomanip>
#include <iterator>
#include <random>
#include <sstream>
#include <system_error>
#include <utility>

namespace starling::governance {

namespace fs = std::filesystem;
using Json = nlohmann::json;

WorldStoreError::WorldStoreError(std::string code, const std::string& detail)
    : std::runtime_error(code + ": " + detail), code_(std::move(code)) {}
const std::string& WorldStoreError::code() const noexcept { return code_; }

bool is_valid_world_name(std::string_view name) {
    if (name.empty() || name.size() > 32) { return false; }
    const auto alnum = [](char chr) {
        return (chr >= 'a' && chr <= 'z') || (chr >= '0' && chr <= '9');
    };
    if (!alnum(name.front())) { return false; }
    return std::ranges::all_of(
        name, [&alnum](char chr) { return alnum(chr) || chr == '_' || chr == '-'; });
}

namespace {

// ---- 时间 ----------------------------------------------------------------

std::string format_utc_now(const char* pattern) {
    const std::time_t now = std::time(nullptr);
    std::tm parts{};
    if (gmtime_r(&now, &parts) == nullptr) {
        throw std::runtime_error("gmtime_r failed");
    }
    std::array<char, 32> buf{};
    const std::size_t len = std::strftime(buf.data(), buf.size(), pattern, &parts);
    if (len == 0) { throw std::runtime_error("strftime failed"); }
    return {buf.data(), len};
}

// 2026-10-25T01:12:00Z
std::string iso_now() { return format_utc_now("%Y-%m-%dT%H:%M:%SZ"); }
// 20261025T011200Z（快照 id 前缀；快照代码复用）
[[maybe_unused]] std::string compact_now() { return format_utc_now("%Y%m%dT%H%M%SZ"); }

// ---- 路径 ----------------------------------------------------------------

// 仅当 target 严格位于 base 之下（解析符号链接与 ".." 之后）才递归删除。
// 返回 true 表示已执行删除；确认 target 越界（被篡改的注册表、指向外部的
// 符号链接）时返回 false，什么都不碰。路径解析本身出错（EACCES、ELOOP 等）时
// 无法判断是否越界，抛 snapshot_failed，由调用方保留注册项，数据不会被悄悄
// 遗弃在磁盘上。
// NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
bool remove_within(const fs::path& base, const fs::path& target) {
    std::error_code err;
    const fs::path real_base = fs::weakly_canonical(base, err);
    if (err) {
        throw WorldStoreError("snapshot_failed",
                              "cannot resolve " + base.string() + ": " + err.message());
    }
    const fs::path real_target = fs::weakly_canonical(target, err);
    if (err) {
        throw WorldStoreError("snapshot_failed",
                              "cannot resolve " + target.string() + ": " + err.message());
    }
    const fs::path rel = real_target.lexically_relative(real_base);
    if (rel.empty() || rel == "." || *rel.begin() == "..") { return false; }
    fs::remove_all(real_target);
    return true;
}

// ---- JSON 映射 -----------------------------------------------------------
// 缺字段用默认值；类型不符由 nlohmann 抛 Json::exception，
// load_registry 统一转 registry_corrupt。

[[noreturn]] void corrupt(const std::string& detail) {
    throw WorldStoreError("registry_corrupt", detail);
}

Json snapshot_to_json(const SnapshotEntry& snap) {
    return Json{{"id", snap.id},
                {"path", snap.path},
                {"kind", snap.kind},
                {"reason", snap.reason},
                {"note", snap.note},
                {"created_at", snap.created_at},
                {"world_time", snap.world_time},
                {"size_bytes", snap.size_bytes},};
}

SnapshotEntry snapshot_from_json(const Json& node) {
    if (!node.is_object()) { corrupt("snapshot entry is not an object"); }
    SnapshotEntry snap;
    snap.id = node.at("id").get<std::string>();
    snap.path = node.at("path").get<std::string>();
    snap.kind = node.at("kind").get<std::string>();
    snap.reason = node.value("reason", std::string{});
    snap.note = node.value("note", std::string{});
    snap.created_at = node.value("created_at", std::string{});
    snap.world_time = node.value("world_time", std::string{});
    snap.size_bytes = node.value("size_bytes", std::int64_t{0});
    return snap;
}

Json world_to_json(const WorldEntry& world) {
    return Json{{"tenant", world.tenant},
                {"db_path", world.db_path},
                {"snapshot_dir", world.snapshot_dir},
                {"label", world.label},
                {"created_at", world.created_at},};
}

WorldEntry world_from_json(const std::string& name, const Json& node) {
    if (!node.is_object()) { corrupt("world '" + name + "' is not an object"); }
    WorldEntry world;
    world.name = name;
    world.tenant = node.at("tenant").get<std::string>();
    world.db_path = node.at("db_path").get<std::string>();
    world.snapshot_dir = node.at("snapshot_dir").get<std::string>();
    world.label = node.value("label", std::string{});
    world.created_at = node.value("created_at", std::string{});
    return world;
}

Json registry_to_json(const Registry& reg) {
    Json worlds = Json::object();
    for (const auto& [name, world] : reg.worlds) { worlds.emplace(name, world_to_json(world)); }
    Json snapshots = Json::object();
    for (const auto& [name, list] : reg.snapshots) {
        Json arr = Json::array();
        for (const auto& snap : list) { arr.push_back(snapshot_to_json(snap)); }
        snapshots.emplace(name, std::move(arr));
    }
    return Json{{"version", reg.version},
                {"default", reg.default_world},
                {"active", reg.active},
                {"snapshot_retention", reg.snapshot_retention},
                {"worlds", std::move(worlds)},
                {"snapshots", std::move(snapshots)},};
}

Registry registry_from_json(const Json& root) {
    if (!root.is_object()) { corrupt("top-level value is not an object"); }
    Registry reg;
    reg.version = root.value("version", 1);
    reg.default_world = root.value("default", std::string{"default"});
    reg.active = root.value("active", std::string{"default"});
    reg.snapshot_retention = root.value("snapshot_retention", 5);

    const auto worlds = root.find("worlds");
    if (worlds == root.end() || !worlds->is_object()) {
        corrupt("'worlds' is missing or not an object");
    }
    for (const auto& [name, node] : worlds->items()) {
        reg.worlds.emplace(name, world_from_json(name, node));
    }

    const auto snapshots = root.find("snapshots");
    if (snapshots != root.end()) {
        if (!snapshots->is_object()) { corrupt("'snapshots' is not an object"); }
        for (const auto& [name, list] : snapshots->items()) {
            if (!list.is_array()) { corrupt("snapshots of '" + name + "' is not an array"); }
            auto& dest = reg.snapshots[name];
            for (const auto& node : list) { dest.push_back(snapshot_from_json(node)); }
        }
    }
    return reg;
}

// load 与 save 共用的不变式：load 拒绝的注册表，save 也不能写出去覆盖
// 好文件。
void validate(const Registry& reg) {
    if (!reg.worlds.contains(reg.default_world)) {
        corrupt("default world '" + reg.default_world + "' is not registered");
    }
    if (!reg.worlds.contains(reg.active)) {
        corrupt("active world '" + reg.active + "' is not registered");
    }
    if (reg.snapshot_retention < 2) {
        throw WorldStoreError("invalid_retention",
                              "snapshot_retention must be >= 2, got " +
                                  std::to_string(reg.snapshot_retention));
    }
}

std::string random_hex() {
    std::mt19937_64 gen{std::random_device{}()};
    std::ostringstream out;
    out << std::hex << std::setw(16) << std::setfill('0') << gen();
    return out.str();
}

WorldEntry make_entry(const fs::path& registry_dir, const std::string& name) {
    const fs::path dir = registry_dir / "worlds" / name;
    WorldEntry world;
    world.name = name;
    world.tenant = name;
    world.db_path = (dir / "world.db").string();
    world.snapshot_dir = (dir / "snapshots").string();
    return world;
}

}  // namespace

Registry load_registry(const fs::path& registry_path) {
    std::ifstream file(registry_path);
    if (!file) { corrupt("cannot open " + registry_path.string()); }
    const std::string text{std::istreambuf_iterator<char>(file), std::istreambuf_iterator<char>()};
    Registry reg;
    try {
        reg = registry_from_json(Json::parse(text));
    } catch (const Json::exception& err) {
        corrupt(err.what());
    }
    validate(reg);
    return reg;
}

void save_registry(const fs::path& registry_path, const Registry& reg) {
    validate(reg);
    const fs::path dir = registry_path.parent_path();
    if (!dir.empty()) { fs::create_directories(dir); }
    const fs::path tmp = dir / (".worlds-" + random_hex() + ".tmp");
    try {
        {
            std::ofstream out(tmp, std::ios::binary | std::ios::trunc);
            if (!out) { throw std::runtime_error("cannot create " + tmp.string()); }
            // 文件一创建就收紧权限，内容写入前不留宽权限窗口。
            fs::permissions(tmp, fs::perms::owner_read | fs::perms::owner_write,
                            fs::perm_options::replace);
            out << registry_to_json(reg).dump(2);
            out.flush();
            if (!out) { throw std::runtime_error("cannot write " + tmp.string()); }
        }
        fs::rename(tmp, registry_path);
    } catch (...) {
        std::error_code ignore;
        fs::remove(tmp, ignore);
        throw;
    }
}

// NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
Registry ensure_registry(const fs::path& registry_path,
                         const fs::path& default_db_path,
                         const std::string& default_tenant) {
    // 已存在就原样返回；损坏时异常继续抛，不重建（重建会丢掉其他世界的登记）。
    if (fs::exists(registry_path)) { return load_registry(registry_path); }

    const fs::path registry_dir = fs::absolute(registry_path).parent_path();
    Registry reg;
    WorldEntry world;
    world.name = reg.default_world;
    world.tenant = default_tenant;
    world.db_path = fs::absolute(default_db_path).string();
    world.snapshot_dir = (registry_dir / "worlds" / reg.default_world / "snapshots").string();
    world.label = "主世界";
    world.created_at = iso_now();
    reg.worlds.emplace(world.name, world);
    save_registry(registry_path, reg);
    return reg;
}

// NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
WorldEntry create_world(Registry& reg, const fs::path& registry_dir, const std::string& name,
                        const std::string& label, std::string_view now_iso) {
    if (!is_valid_world_name(name)) {
        throw WorldStoreError("invalid_world_name",
                              "'" + name + "' does not match [a-z0-9][a-z0-9_-]{0,31}");
    }
    if (reg.worlds.contains(name)) {
        throw WorldStoreError("world_exists", "world '" + name + "' already exists");
    }
    WorldEntry world = make_entry(fs::absolute(registry_dir), name);
    world.label = label;
    world.created_at = std::string(now_iso);
    fs::create_directories(world.snapshot_dir);
    reg.worlds.emplace(name, world);
    return world;
}

void delete_world(Registry& reg, const fs::path& registry_dir, const std::string& name) {
    if (!reg.worlds.contains(name)) {
        throw WorldStoreError("world_not_found", "world '" + name + "' is not registered");
    }
    if (name == reg.default_world) {
        throw WorldStoreError("world_protected", "the default world cannot be deleted");
    }
    if (name == reg.active) {
        throw WorldStoreError("world_protected", "the active world cannot be deleted");
    }
    // 先删目录再摘注册项：目录删到一半失败时注册表仍是完整的，可重试。
    // 删除目标固定为 <registry_dir>/worlds/<name>，不读注册项里的路径，
    // 所以被篡改的 db_path / snapshot_dir 碰不到外部目录。
    const fs::path base = fs::absolute(registry_dir) / "worlds";
    (void)remove_within(base, base / name);
    reg.worlds.erase(name);
    reg.snapshots.erase(name);
}

void set_active(Registry& reg, const std::string& name) {
    if (!reg.worlds.contains(name)) {
        throw WorldStoreError("world_not_found", "world '" + name + "' is not registered");
    }
    reg.active = name;
}

}  // namespace starling::governance

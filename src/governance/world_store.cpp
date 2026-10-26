#include "starling/governance/world_store.hpp"

#include "starling/persistence/sqlite_handles.hpp"
#include "starling/persistence/stmt.hpp"

#include <nlohmann/json.hpp>
#include <sqlite3.h>

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <ctime>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <limits>
#include <random>
#include <set>
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
// 20261025T011200Z（快照 id 前缀）
std::string compact_now() { return format_utc_now("%Y%m%dT%H%M%SZ"); }

// ---- 路径 ----------------------------------------------------------------

// lexically_normal 之后去掉末尾的分隔符（"/a/b/" → "/a/b"），否则 lexically_relative 会把
// 末尾的空文件名当成一级目录。根目录保持原样。
fs::path normalized(const fs::path& path) {
    fs::path out = path.lexically_normal();
    if (!out.has_filename() && out.has_parent_path() && out != out.root_path()) {
        out = out.parent_path();
    }
    return out;
}

// target 严格位于 base 之下（两者都已规范化；相等不算）。
bool strictly_under(const fs::path& base, const fs::path& target) {
    const fs::path rel = target.lexically_relative(base);
    return !rel.empty() && rel != "." && *rel.begin() != "..";
}

// 字面判断，不解析符号链接：注册表校验只看写在 worlds.json 里的路径本身。
bool lexically_within(const fs::path& base, const fs::path& target) {
    return strictly_under(normalized(base), normalized(target));
}

// 布局校验用：字面在 base 之下，或两侧解析符号链接之后在 base 之下，都算。
// 同一份注册表换一种路径写法打开（/tmp 与 /private/tmp、软链回来的 ~/.starling、换了拼法的
// STARLING_DASH_DB）时，字面比较会把合法布局判成越界，启动直接 registry_corrupt。解析失败就只
// 认字面结果。".." 越界两种判法都拒；删除时的真正边界仍由 remove_within / require_inside_registry
// 在解析符号链接之后把守。
// NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
bool within_layout(const fs::path& base, const fs::path& target) {
    if (lexically_within(base, target)) { return true; }
    std::error_code err;
    const fs::path real_base = fs::weakly_canonical(base, err);
    if (err) { return false; }
    const fs::path real_target = fs::weakly_canonical(target, err);
    if (err) { return false; }
    return strictly_under(normalized(real_base), normalized(real_target));
}

// 仅当 target 严格位于 base 之下（解析符号链接与 ".." 之后）才递归删除。
// 返回 true 表示已执行删除；确认 target 越界（被篡改的注册表、指向外部的
// 符号链接）时返回 false，什么都不碰。路径解析出错（EACCES、ELOOP 等）时无法
// 判断是否越界，删除本身失败（EACCES、EBUSY 等）时文件仍在盘上，两种情况都抛
// snapshot_failed（不抛裸 filesystem_error，上层按 code 映射），由调用方保留
// 注册项，数据不会被悄悄遗弃在磁盘上。
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
    if (!strictly_under(real_base, real_target)) { return false; }
    (void)fs::remove_all(real_target, err);
    if (err) {
        throw WorldStoreError("snapshot_failed",
                              "cannot remove " + real_target.string() + ": " + err.message());
    }
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

Json registry_to_node(const Registry& reg) {
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

Registry registry_from_node(const Json& root) {
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

// 保留份数 < 2 会让修剪删掉唯一的回滚点。注册表校验与快照代码共用。
void require_valid_retention(int retention) {
    if (retention < 2) {
        throw WorldStoreError("invalid_retention",
                              "snapshot_retention must be >= 2, got " +
                                  std::to_string(retention));
    }
}

// 与注册表所在目录无关的不变式。registry_from_json（绑定层的 dict 入口）只能做这一层；
// load / save 另加 validate_layout。load 拒绝的注册表，save 也不能写出去覆盖好文件。
// retention 放在路径检查之前：retention 非法的注册表报 invalid_retention，不被路径问题
// 盖成 registry_corrupt。
void validate_shape(const Registry& reg) {
    if (!reg.worlds.contains(reg.default_world)) {
        corrupt("default world '" + reg.default_world + "' is not registered");
    }
    if (!reg.worlds.contains(reg.active)) {
        corrupt("active world '" + reg.active + "' is not registered");
    }
    require_valid_retention(reg.snapshot_retention);
    for (const auto& [name, world] : reg.worlds) {
        // default 的键是固定的（"default"），不是用户起的名字。
        if (name != reg.default_world && !is_valid_world_name(name)) {
            corrupt("world name '" + name + "' does not match [a-z0-9][a-z0-9_-]{0,31}");
        }
        if (!fs::path(world.db_path).is_absolute()) {
            corrupt("db_path of '" + name + "' is not absolute: " + world.db_path);
        }
        if (!fs::path(world.snapshot_dir).is_absolute()) {
            corrupt("snapshot_dir of '" + name + "' is not absolute: " + world.snapshot_dir);
        }
    }
    for (const auto& [owner, list] : reg.snapshots) {
        const auto found = reg.worlds.find(owner);
        if (found == reg.worlds.end()) {
            corrupt("snapshots listed for unregistered world '" + owner + "'");
        }
        for (const auto& snap : list) {
            if (snap.kind != "manual" && snap.kind != "auto") {
                corrupt("snapshot '" + snap.id + "' of '" + owner + "' has kind '" + snap.kind +
                        "'");
            }
            if (!lexically_within(found->second.snapshot_dir, snap.path)) {
                corrupt("snapshot '" + snap.id + "' of '" + owner + "' lies outside " +
                        found->second.snapshot_dir + ": " + snap.path);
            }
        }
    }
}

// 世界目录布局：每个世界的 snapshot_dir、以及非 default 世界的 db_path，在字面上都位于
// <registry_dir>/worlds/<name>/ 之下。default 的库保持原地（spec §0.1），不受此限；但它的
// 快照目录同样固定在 worlds/<default>/ 下——否则把它改成 "/"，删除快照、保留策略和残留
// 清扫就能删到任意位置。
// worlds/ 解析符号链接之后必须仍在注册表目录之下。within_layout 两侧都解析符号链接，
// 若 worlds/ 本身指向外部，「目标在 home 之下」会在外部成立，快照清扫、保留策略、删快照
// 便以外部目录为根。所以在逐项比较之前先把根钉死：worlds/ 还不存在（全新注册表）时放行。
void require_worlds_root_inside(const fs::path& registry_dir, const fs::path& worlds_root) {
    std::error_code err;
    if (!fs::exists(fs::symlink_status(worlds_root, err))) { return; }
    const fs::path real_dir = fs::weakly_canonical(registry_dir, err);
    if (err) { corrupt("cannot resolve " + registry_dir.string() + ": " + err.message()); }
    const fs::path real_root = fs::weakly_canonical(worlds_root, err);
    if (err) { corrupt("cannot resolve " + worlds_root.string() + ": " + err.message()); }
    if (!strictly_under(normalized(real_dir), normalized(real_root))) {
        corrupt(worlds_root.string() + " resolves to " + real_root.string() + ", outside " +
                real_dir.string());
    }
}

void validate_layout(const Registry& reg, const fs::path& registry_dir) {
    const fs::path worlds_root = fs::absolute(registry_dir) / "worlds";
    require_worlds_root_inside(fs::absolute(registry_dir), worlds_root);
    for (const auto& [name, world] : reg.worlds) {
        const fs::path home = worlds_root / name;
        if (!lexically_within(worlds_root, home)) {
            corrupt("world '" + name + "' has no home under " + worlds_root.string());
        }
        if (name != reg.default_world && !within_layout(home, world.db_path)) {
            corrupt("db_path of '" + name + "' lies outside " + home.string() + ": " +
                    world.db_path);
        }
        if (!within_layout(home, world.snapshot_dir)) {
            corrupt("snapshot_dir of '" + name + "' lies outside " + home.string() + ": " +
                    world.snapshot_dir);
        }
    }
}

// 注册表文件所在目录（与 ensure_registry / create_world 推导世界目录的方式一致）。
fs::path registry_dir_of(const fs::path& registry_path) {
    return fs::absolute(registry_path).parent_path();
}

// delete_world 递归删除的根 <registry_dir>/worlds 解析符号链接之后必须仍在注册表目录
// 之下：worlds/ 本身若是指向外部的符号链接，remove_within 两侧都解析到外部，会把外部的
// <name> 目录当成合法子目录删掉。
void require_inside_registry(const fs::path& root, const fs::path& base) {
    std::error_code err;
    const fs::path real_root = fs::weakly_canonical(root, err);
    if (err) {
        throw WorldStoreError("snapshot_failed",
                              "cannot resolve " + root.string() + ": " + err.message());
    }
    const fs::path real_worlds = fs::weakly_canonical(base, err);
    if (err) {
        throw WorldStoreError("snapshot_failed",
                              "cannot resolve " + base.string() + ": " + err.message());
    }
    if (!strictly_under(real_root, real_worlds)) {
        throw WorldStoreError("snapshot_failed", base.string() + " resolves to " +
                                                     real_worlds.string() + ", outside " +
                                                     real_root.string());
    }
}

// 快照 id 的形状：20261025T011200Z-a1b2（compact_now + "-" + 4 位小写十六进制）。
bool looks_like_snapshot_id(std::string_view stem) {
    constexpr std::size_t kIdLength = 21;
    if (stem.size() != kIdLength) { return false; }
    const auto digit = [](char chr) { return chr >= '0' && chr <= '9'; };
    const auto hex = [&digit](char chr) { return digit(chr) || (chr >= 'a' && chr <= 'f'); };
    for (std::size_t pos = 0; pos < kIdLength; ++pos) {
        const char chr = stem.at(pos);
        bool good = false;
        if (pos == 8) { good = chr == 'T'; }
        else if (pos == 15) { good = chr == 'Z'; }
        else if (pos == 16) { good = chr == '-'; }
        else if (pos > 16) { good = hex(chr); }
        else { good = digit(chr); }
        if (!good) { return false; }
    }
    return true;
}

bool ends_with(std::string_view text, std::string_view suffix) {
    return text.size() >= suffix.size() &&
           text.substr(text.size() - suffix.size()) == suffix;
}

// take_snapshot 前清扫上次崩溃的残留（见 world_store.hpp take_snapshot 第 1b 步）。
// 返回删掉的文件数；任何错误只记日志，不外抛。
std::size_t sweep_leftovers(const Registry& reg, const std::string& world, const fs::path& dir) {
    // 按路径和 id 两种方式认「已登记」：任一命中都不删，宁可漏扫也不误删登记过的快照。
    std::set<std::string> referenced;
    std::set<std::string> referenced_ids;
    if (const auto listed = reg.snapshots.find(world); listed != reg.snapshots.end()) {
        for (const auto& snap : listed->second) {
            referenced.insert(normalized(snap.path).string());
            referenced_ids.insert(snap.id);
        }
    }
    std::vector<fs::path> victims;
    std::error_code err;
    fs::directory_iterator iter(dir, err);
    const fs::directory_iterator done;
    for (; !err && iter != done; iter.increment(err)) {
        const fs::directory_entry& item = *iter;
        std::error_code status_err;
        // 只碰普通文件：符号链接（我们从不创建）一概跳过，免得经它删到登记过的快照。
        if (item.is_symlink(status_err) || !item.is_regular_file(status_err)) { continue; }
        const std::string name = item.path().filename().string();
        constexpr std::string_view kPartial = ".db.partial";
        constexpr std::string_view kFinal = ".db";
        if (ends_with(name, kPartial)) {
            if (looks_like_snapshot_id(std::string_view(name).substr(0, name.size() - kPartial.size()))) {
                victims.push_back(item.path());
            }
        } else if (ends_with(name, kFinal)) {
            const std::string stem = name.substr(0, name.size() - kFinal.size());
            if (looks_like_snapshot_id(stem) && !referenced_ids.contains(stem) &&
                !referenced.contains(normalized(item.path()).string())) {
                victims.push_back(item.path());
            }
        }
    }
    std::size_t swept = 0;
    for (const auto& victim : victims) {
        try {
            if (remove_within(dir, victim)) { ++swept; }
        } catch (const WorldStoreError& sweep_err) {
            std::cerr << "[world_store] cannot sweep " << victim.string() << ": "
                      << sweep_err.what() << "\n";
        }
    }
    if (swept > 0) {
        std::cerr << "[world_store] swept " << swept << " leftover snapshot file(s) in "
                  << dir.string() << "\n";
    }
    return swept;
}

// SQL 标识符加双引号（内部的双引号写两遍）。表名来自库文件自己的 sqlite_master。
std::string quote_identifier(const std::string& name) {
    std::string out = "\"";
    for (const char chr : name) {
        out += chr;
        if (chr == '"') { out += '"'; }
    }
    out += '"';
    return out;
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

// ---- SQLite 只读访问 -------------------------------------------------------

// URI 里 %、?、# 有特殊含义，路径来自注册表（可能被手改），必须百分号编码。
std::string uri_escape_path(const std::string& path) {
    std::string out;
    out.reserve(path.size());
    for (const char chr : path) {
        switch (chr) {
            case '%': out += "%25"; break;
            case '?': out += "%3f"; break;
            case '#': out += "%23"; break;
            default: out += chr; break;
        }
    }
    return out;
}

persistence::SqliteHandle open_read_only(const std::string& path) {
    sqlite3* raw = nullptr;
    const std::string uri = "file:" + uri_escape_path(path) + "?mode=ro";
    const int code = sqlite3_open_v2(uri.c_str(), &raw, SQLITE_OPEN_READONLY | SQLITE_OPEN_URI,
                                     nullptr);
    persistence::SqliteHandle handle(raw);
    if (code != SQLITE_OK) {
        throw WorldStoreError("snapshot_failed",
                              std::string("open ") + path + ": " +
                                  (raw != nullptr ? sqlite3_errmsg(raw) : "alloc"));
    }
    sqlite3_busy_timeout(raw, 5000);
    return handle;
}

std::string column_text(sqlite3_stmt* stmt, int idx) {
    // NOLINTNEXTLINE(cppcoreguidelines-pro-type-reinterpret-cast)
    const auto* txt = reinterpret_cast<const char*>(sqlite3_column_text(stmt, idx));
    return txt != nullptr ? std::string(txt) : std::string{};
}

std::int64_t single_int(sqlite3* dbh, const char* sql) {
    persistence::Stmt query(dbh, sql);
    if (!query.step_row()) { return 0; }
    return sqlite3_column_int64(query.raw(), 0);
}

bool table_exists(sqlite3* dbh, const std::string& name) {
    persistence::Stmt query(dbh, "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?1");
    query.bind(name);
    return query.step_row();
}

// 活数据量：不含 freelist。生产库 2.4GB 里 97.7% 是 freelist，磁盘守卫看文件
// 大小会误拒。
std::int64_t live_bytes_of(sqlite3* dbh) {
    const std::int64_t pages = single_int(dbh, "PRAGMA page_count");
    const std::int64_t free_pages = single_int(dbh, "PRAGMA freelist_count");
    const std::int64_t page_size = single_int(dbh, "PRAGMA page_size");
    return (pages - free_pages) * page_size;
}

std::int64_t count_tenant_rows(sqlite3* dbh, const char* table, const std::string& tenant) {
    if (!table_exists(dbh, table)) { return 0; }
    persistence::Stmt query(dbh, (std::string("SELECT COUNT(*) FROM ") + table +
                                 " WHERE tenant_id=?1").c_str());
    query.bind(tenant);
    return query.step_row() ? sqlite3_column_int64(query.raw(), 0) : 0;
}

// source_unit_meta 在生产库里不存在（迁移停在 36），先查 sqlite_master，不靠 SQL 报错。
std::string world_time_on(sqlite3* dbh, const std::string& tenant) {
    if (table_exists(dbh, "source_unit_meta")) {
        persistence::Stmt query(dbh,
            "SELECT MAX(observed_at) FROM source_unit_meta "
            "WHERE tenant_id=?1 AND observed_at IS NOT NULL AND observed_at <> ''");
        query.bind(tenant);
        if (query.step_row()) {
            std::string stamp = column_text(query.raw(), 0);
            if (!stamp.empty()) { return stamp; }
        }
    }
    if (table_exists(dbh, "engrams")) {
        persistence::Stmt query(dbh, "SELECT MAX(created_at) FROM engrams WHERE tenant_id=?1");
        query.bind(tenant);
        if (query.step_row()) { return column_text(query.raw(), 0); }
    }
    return {};
}

// 可用字节数。标准允许 fs::space 在 FUSE / 网络文件系统上返回 uintmax_t(-1)
// 表示「未知」，直接转成 int64 会得到 -1，让每次快照都被误拒为 insufficient_disk。
// 未知或超出 int64 的值一律按「足够」处理，等于跳过守卫。
std::int64_t available_bytes(const fs::path& dir) {
    const std::uintmax_t avail = fs::space(dir).available;
    constexpr auto kCeiling = static_cast<std::uintmax_t>(std::numeric_limits<std::int64_t>::max());
    return avail > kCeiling ? std::numeric_limits<std::int64_t>::max()
                            : static_cast<std::int64_t>(avail);
}

// 与该世界已有快照（注册项或磁盘文件）不重名的 id。
std::string fresh_snapshot_id(const Registry& reg, const std::string& world,
                              const fs::path& dir) {
    const auto listed = reg.snapshots.find(world);
    const auto taken = [&](const std::string& cand) {
        std::error_code err;
        if (fs::exists(dir / (cand + ".db"), err)) { return true; }
        return listed != reg.snapshots.end() &&
               std::ranges::any_of(listed->second,
                                   [&cand](const SnapshotEntry& snap) { return snap.id == cand; });
    };
    std::string cand = compact_now() + "-" + random_hex().substr(0, 4);
    while (taken(cand)) { cand = compact_now() + "-" + random_hex().substr(0, 4); }
    return cand;
}

}  // namespace

Registry load_registry(const fs::path& registry_path) {
    std::ifstream file(registry_path);
    if (!file) { corrupt("cannot open " + registry_path.string()); }
    const std::string text{std::istreambuf_iterator<char>(file), std::istreambuf_iterator<char>()};
    Registry reg = registry_from_json(text);
    validate_layout(reg, registry_dir_of(registry_path));
    return reg;
}

// ---- JSON 文本接口（绑定层用） ---------------------------------------------

std::string registry_to_json(const Registry& reg) { return registry_to_node(reg).dump(); }

Registry registry_from_json(const std::string& text) {
    Registry reg;
    try {
        reg = registry_from_node(Json::parse(text));
    } catch (const Json::exception& err) {
        corrupt(err.what());
    }
    validate_shape(reg);
    return reg;
}

std::string world_entry_to_json(const WorldEntry& entry) {
    return world_to_json(entry).dump();
}

std::string snapshot_entry_to_json(const SnapshotEntry& entry) {
    return snapshot_to_json(entry).dump();
}

void save_registry(const fs::path& registry_path, const Registry& reg) {
    validate_shape(reg);
    validate_layout(reg, registry_dir_of(registry_path));
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
            out << registry_to_node(reg).dump(2);
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
    // 所以被篡改的 db_path / snapshot_dir 碰不到外部目录。worlds/ 本身被换成指向外部的
    // 符号链接时，先在这里拒绝（抛 snapshot_failed，注册项保留）。
    const fs::path root = fs::absolute(registry_dir);
    const fs::path base = root / "worlds";
    require_inside_registry(root, base);
    // worlds/<name> 本身是指向外部的符号链接时 remove_within 不删（返回 false）。与快照的
    // 越界处理一致 fail closed：抛 snapshot_failed、注册项保留，不让外部数据变成无主孤儿。
    if (!remove_within(base, base / name)) {
        throw WorldStoreError("snapshot_failed",
                              "world directory of '" + name + "' resolves outside " +
                                  base.string() + "; refusing to delete");
    }
    reg.worlds.erase(name);
    reg.snapshots.erase(name);
}

void set_active(Registry& reg, const std::string& name) {
    if (!reg.worlds.contains(name)) {
        throw WorldStoreError("world_not_found", "world '" + name + "' is not registered");
    }
    reg.active = name;
}

// ---- 世界统计与快照（W2） --------------------------------------------------

std::string snapshot_world_time(const std::string& db_path, const std::string& tenant) {
    std::error_code err;
    if (!fs::exists(db_path, err)) { return {}; }
    try {
        const auto handle = open_read_only(db_path);
        return world_time_on(handle.get(), tenant);
    } catch (const WorldStoreError&) {
        throw;
    } catch (const std::exception& ex) {
        throw WorldStoreError("snapshot_failed", db_path + ": " + ex.what());
    }
}

WorldStats world_stats(const std::string& db_path, const std::string& tenant) {
    WorldStats stats;
    std::error_code err;
    if (!fs::exists(db_path, err)) { return stats; }
    const auto main_size = fs::file_size(db_path, err);
    if (!err) { stats.db_bytes += static_cast<std::int64_t>(main_size); }
    const auto wal_size = fs::file_size(db_path + "-wal", err);   // 不存在时按 0 计
    if (!err) { stats.db_bytes += static_cast<std::int64_t>(wal_size); }
    try {
        const auto handle = open_read_only(db_path);
        stats.live_bytes = live_bytes_of(handle.get());
        stats.statements = count_tenant_rows(handle.get(), "statements", tenant);
        stats.engrams = count_tenant_rows(handle.get(), "engrams", tenant);
        stats.world_time = world_time_on(handle.get(), tenant);
    } catch (const WorldStoreError&) {
        throw;
    } catch (const std::exception& ex) {
        throw WorldStoreError("snapshot_failed", db_path + ": " + ex.what());
    }
    return stats;
}

// NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
void verify_world_tenant(const std::string& db_path, const std::string& tenant) {
    std::error_code err;
    if (!fs::exists(db_path, err)) { return; }   // 新世界：库留到首次激活才建
    try {
        const auto handle = open_read_only(db_path);
        std::vector<std::string> tables;
        {
            persistence::Stmt list(handle.get(),
                "SELECT tbl.name FROM sqlite_master AS tbl WHERE tbl.type = 'table' "
                "AND EXISTS (SELECT 1 FROM pragma_table_info(tbl.name) AS col "
                "WHERE col.name = 'tenant_id') ORDER BY tbl.name");
            while (list.step_row()) { tables.push_back(column_text(list.raw(), 0)); }
        }
        for (const auto& table : tables) {
            persistence::Stmt probe(handle.get(),
                ("SELECT 1 FROM " + quote_identifier(table) +
                 " WHERE tenant_id IS NOT NULL AND tenant_id <> ?1 LIMIT 1").c_str());
            probe.bind(tenant);
            if (probe.step_row()) {
                std::string detail = "table '";
                detail += table;
                detail += "' in ";
                detail += db_path;
                detail += " holds rows of a tenant other than '";
                detail += tenant;
                detail += '\'';
                throw WorldStoreError("world_tenant_mismatch", detail);
            }
        }
    } catch (const WorldStoreError&) {
        throw;
    } catch (const std::exception& ex) {
        throw WorldStoreError("snapshot_failed", db_path + ": " + ex.what());
    }
}

SnapshotEntry take_snapshot(Registry& reg, const std::string& world,
                            const SnapshotOptions& opts) {
    const auto found = reg.worlds.find(world);
    if (found == reg.worlds.end()) {
        throw WorldStoreError("world_not_found", "world '" + world + "' is not registered");
    }
    // 先校验入参与保留份数：否则快照写完才发现配置非法，留下无人登记的文件。
    // kind 拼错（"Auto"）不能静默当成 manual：保留策略只认 "auto"，会丢掉回滚锚点保护。
    if (opts.kind != "manual" && opts.kind != "auto") {
        throw WorldStoreError("invalid_snapshot_kind",
                              "kind must be 'manual' or 'auto', got '" + opts.kind + "'");
    }
    // 向量在库文件之外的后端（zvec）拍出来的快照缺向量，不是完整的世界（spec §12）。
    if (opts.vector_backend != "sqlite") {
        throw WorldStoreError("snapshot_unsupported_backend",
                              "vector_backend '" + opts.vector_backend + "' keeps vectors "
                              "outside the database file");
    }
    require_valid_retention(reg.snapshot_retention);
    const WorldEntry& entry = found->second;
    const fs::path dir = entry.snapshot_dir;

    // 库文件不存在（世界从未激活）：在打开连接前拒绝，否则 mode=ro 只会报含糊的
    // "unable to open database file"。
    std::error_code exists_err;
    if (!fs::exists(entry.db_path, exists_err)) {
        throw WorldStoreError("snapshot_failed",
                              "database file " + entry.db_path + " does not exist");
    }

    SnapshotEntry snap;
    snap.kind = opts.kind;
    snap.reason = opts.reason;
    snap.note = opts.note;
    fs::path partial;
    try {
        // default 世界的快照目录由 ensure_registry 登记但不创建，首次快照时补建。
        fs::create_directories(dir);
        (void)sweep_leftovers(reg, world, dir);

        auto source = open_read_only(entry.db_path);
        const std::int64_t live = live_bytes_of(source.get());
        const std::int64_t avail = opts.free_space ? opts.free_space(dir) : available_bytes(dir);
        if (avail < 3 * live) {
            throw WorldStoreError("insufficient_disk",
                                  "need " + std::to_string(3 * live) + " bytes free in " +
                                      dir.string() + ", have " + std::to_string(avail));
        }

        snap.id = fresh_snapshot_id(reg, world, dir);
        partial = dir / (snap.id + ".db.partial");
        const fs::path final_path = dir / (snap.id + ".db");
        {
            std::error_code ignore;
            fs::remove(partial, ignore);
        }
        {
            persistence::Stmt vacuum(source.get(), "VACUUM INTO ?1");
            vacuum.bind(partial.string());
            vacuum.step_done();
        }
        source.reset();

        {
            const auto copy = open_read_only(partial.string());
            bool intact = false;
            {
                persistence::Stmt check(copy.get(), "PRAGMA integrity_check");
                intact = check.step_row() && column_text(check.raw(), 0) == "ok";
            }
            if (!intact) {
                throw WorldStoreError("snapshot_failed",
                                      "integrity_check failed for " + partial.string());
            }
            snap.world_time = world_time_on(copy.get(), entry.tenant);
        }
        snap.size_bytes = static_cast<std::int64_t>(fs::file_size(partial));
        snap.path = final_path.string();
        snap.created_at = iso_now();
        fs::rename(partial, final_path);
    } catch (const WorldStoreError&) {
        std::error_code ignore;
        if (!partial.empty()) { fs::remove(partial, ignore); }
        throw;
    } catch (const std::exception& ex) {
        std::error_code ignore;
        if (!partial.empty()) { fs::remove(partial, ignore); }
        throw WorldStoreError("snapshot_failed", ex.what());
    }

    auto& list = reg.snapshots[world];
    list.insert(list.begin(), snap);
    // 快照已落盘并登记，成功的快照必须把条目返回给调用方。修剪失败（旧快照路径
    // 无法解析或无法删除，WorldStoreError snapshot_failed）不外抛：apply_retention
    // 逐个「先删文件、再摘注册项」，失败时列表与磁盘仍一致，只是暂时多出几份，
    // 下一次 take_snapshot 或显式 apply_retention 会重试。
    try {
        (void)apply_retention(reg, world);
    } catch (const WorldStoreError& retention_err) {
        // 见上：留待下次修剪重试。越界的注册项会一直卡住修剪，记下来才看得见。
        std::cerr << "[world_store] retention for '" << world
                  << "' deferred: " << retention_err.what() << "\n";
    }
    return snap;
}

std::vector<std::string> apply_retention(Registry& reg, const std::string& world) {
    const auto found = reg.worlds.find(world);
    if (found == reg.worlds.end()) {
        throw WorldStoreError("world_not_found", "world '" + world + "' is not registered");
    }
    require_valid_retention(reg.snapshot_retention);
    std::vector<std::string> removed;
    const auto listed = reg.snapshots.find(world);
    if (listed == reg.snapshots.end()) { return removed; }
    auto& list = listed->second;   // 最新在前
    const auto limit = static_cast<std::size_t>(reg.snapshot_retention);
    if (list.size() <= limit) { return removed; }

    // 先定好要删谁：第一轮从最旧的 auto 起（最新的那份 auto 是回滚锚点，跳过），
    // 仍超出时第二轮从最旧的 manual 起。
    const auto newest_auto = std::ranges::find_if(
        list, [](const SnapshotEntry& snap) { return snap.kind == "auto"; });
    const SnapshotEntry* anchor = newest_auto == list.end() ? nullptr : &*newest_auto;
    const std::size_t excess = list.size() - limit;
    std::vector<std::string> victims;
    for (auto iter = list.rbegin(); iter != list.rend() && victims.size() < excess; ++iter) {
        if (iter->kind == "auto" && &*iter != anchor) { victims.push_back(iter->id); }
    }
    for (auto iter = list.rbegin(); iter != list.rend() && victims.size() < excess; ++iter) {
        if (iter->kind != "auto") { victims.push_back(iter->id); }
    }

    // 逐个「先删文件、再摘注册项」：中途失败时内存里的列表仍与磁盘一致。路径越界时
    // fail closed：文件没删，摘掉注册项就再也无法经注册表清理它。
    const fs::path dir = found->second.snapshot_dir;
    for (const auto& victim : victims) {
        const auto pos = std::ranges::find_if(
            list, [&victim](const SnapshotEntry& snap) { return snap.id == victim; });
        if (!remove_within(dir, pos->path)) {
            throw WorldStoreError("snapshot_failed", "snapshot '" + victim + "' path " +
                                                         pos->path + " is outside " + dir.string());
        }
        list.erase(pos);
        removed.push_back(victim);
    }
    return removed;
}

void delete_snapshot(Registry& reg, const std::string& world, const std::string& snapshot_id) {
    const auto found = reg.worlds.find(world);
    if (found == reg.worlds.end()) {
        throw WorldStoreError("world_not_found", "world '" + world + "' is not registered");
    }
    const auto listed = reg.snapshots.find(world);
    if (listed == reg.snapshots.end()) {
        throw WorldStoreError("snapshot_not_found", "snapshot '" + snapshot_id + "' not found");
    }
    auto& list = listed->second;
    const auto pos = std::ranges::find_if(
        list, [&snapshot_id](const SnapshotEntry& snap) { return snap.id == snapshot_id; });
    if (pos == list.end()) {
        throw WorldStoreError("snapshot_not_found", "snapshot '" + snapshot_id + "' not found");
    }
    // 先删文件再摘注册项。文件已经不在了（保存失败后的补偿、手工删除）照摘；路径越界
    // （被篡改的注册表）时 fail closed：文件不动，注册项保留。
    if (!remove_within(found->second.snapshot_dir, pos->path)) {
        throw WorldStoreError("snapshot_failed", "snapshot '" + snapshot_id + "' path " +
                                                     pos->path + " is outside " +
                                                     found->second.snapshot_dir);
    }
    list.erase(pos);
}

// NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
void discard_snapshot_file(const Registry& reg, const std::string& world,
                           const std::string& snapshot_id) {
    const auto found = reg.worlds.find(world);
    if (found == reg.worlds.end()) {
        throw WorldStoreError("world_not_found", "world '" + world + "' is not registered");
    }
    const auto listed = reg.snapshots.find(world);
    if (listed == reg.snapshots.end()) {
        throw WorldStoreError("snapshot_not_found", "snapshot '" + snapshot_id + "' not found");
    }
    const auto pos = std::ranges::find_if(
        listed->second, [&snapshot_id](const SnapshotEntry& snap) { return snap.id == snapshot_id; });
    if (pos == listed->second.end()) {
        throw WorldStoreError("snapshot_not_found", "snapshot '" + snapshot_id + "' not found");
    }
    if (!remove_within(found->second.snapshot_dir, pos->path)) {
        throw WorldStoreError("snapshot_failed", "snapshot '" + snapshot_id + "' path " +
                                                     pos->path + " is outside " +
                                                     found->second.snapshot_dir);
    }
}

// ---- 回滚与归档（W3） ------------------------------------------------------

namespace {

const WorldEntry& registered_world(const Registry& reg, const std::string& world) {
    const auto found = reg.worlds.find(world);
    if (found == reg.worlds.end()) {
        throw WorldStoreError("world_not_found", "world '" + world + "' is not registered");
    }
    return found->second;
}

// NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
const SnapshotEntry& registered_snapshot(const Registry& reg, const std::string& world,
                                         const std::string& snapshot_id) {
    if (const auto listed = reg.snapshots.find(world); listed != reg.snapshots.end()) {
        const auto& list = listed->second;
        const auto pos = std::ranges::find_if(
            list, [&snapshot_id](const SnapshotEntry& snap) { return snap.id == snapshot_id; });
        if (pos != list.end()) { return *pos; }
    }
    throw WorldStoreError("snapshot_not_found", "snapshot '" + snapshot_id + "' not found");
}

// 世界 home = snapshot_dir 的父目录（字面，与注册表布局 <registry_dir>/worlds/<name>/ 一致）。
fs::path world_home(const WorldEntry& entry) {
    return normalized(entry.snapshot_dir).parent_path();
}

fs::path archive_dir_of(const WorldEntry& entry) { return world_home(entry) / "archive"; }

// 不跟随符号链接的 stat。文件不存在返回 not_found（libc++ 此时也会把 err 设成 ENOENT，
// 不能据此当成错误）；其余错误（EACCES、ELOOP 等）抛 snapshot_failed。
fs::file_status lstat_or_throw(const fs::path& path) {
    std::error_code err;
    const fs::file_status status = fs::symlink_status(path, err);
    if (err && status.type() != fs::file_type::not_found) {
        throw WorldStoreError("snapshot_failed",
                              "cannot stat " + path.string() + ": " + err.message());
    }
    return status;
}

constexpr std::string_view kPreRollback = ".pre-rollback-";

// "<库文件名>.pre-rollback-<YYYYMMDDTHHMMSSZ>-<4 hex>"：后缀与快照 id 同形。
bool looks_like_archive_name(std::string_view name) {
    const auto pos = name.rfind(kPreRollback);
    return pos != std::string_view::npos && pos > 0 &&
           looks_like_snapshot_id(name.substr(pos + kPreRollback.size()));
}

// 归档目录里还没被占用的名字：同一秒内两次回滚靠随机后缀区分，撞名就重抽（rename 会覆盖已有归档）。
// NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
fs::path fresh_archive_path(const fs::path& dir, const std::string& db_name) {
    const auto candidate = [&dir, &db_name] {
        return dir / (db_name + std::string(kPreRollback) + compact_now() + "-" +
                      random_hex().substr(0, 4));
    };
    fs::path out = candidate();
    while (fs::exists(lstat_or_throw(out))) { out = candidate(); }
    return out;
}

// 只读打开 path，执行 pragma（integrity_check / quick_check），第一行为 "ok" 时返回 true。
// 打不开或不是 SQLite 文件时抛异常（open_read_only 的 snapshot_failed，或 SqliteError）。
bool passes_check(const std::string& path, const char* pragma) {
    const auto handle = open_read_only(path);
    persistence::Stmt check(handle.get(), pragma);
    return check.step_row() && column_text(check.raw(), 0) == "ok";
}

// 第 3 步：快照文件缺失、打不开、不是 SQLite 或 integrity_check 不过，一律 snapshot_corrupt。
void require_intact_snapshot(const std::string& path) {
    std::error_code err;
    if (!fs::is_regular_file(path, err)) {
        throw WorldStoreError("snapshot_corrupt", "snapshot file " + path + " is missing");
    }
    bool intact = false;
    try {
        intact = passes_check(path, "PRAGMA integrity_check");
    } catch (const std::exception& ex) {
        throw WorldStoreError("snapshot_corrupt",
                              "cannot read snapshot " + path + ": " + ex.what());
    }
    if (!intact) {
        throw WorldStoreError("snapshot_corrupt", "integrity_check failed for " + path);
    }
}

// 库旁边的 -wal 非空（或不是普通文件）：还有未合并进主文件的写入，或者写连接还开着。
// 此时主文件不是完整的库，改名归档会丢数据；残留的 WAL 还会被 SQLite 重放到恢复出来的库上。
void require_no_pending_wal(const fs::path& wal) {
    const auto status = lstat_or_throw(wal);
    if (!fs::exists(status)) { return; }
    std::error_code err;
    if (!fs::is_regular_file(status) || fs::file_size(wal, err) != 0 || err) {
        throw WorldStoreError("snapshot_failed",
                              wal.string() + " is not empty: the database still has unmerged "
                              "writes or an open writer");
    }
}

// 第 7 步之后失败：把归档改名回库路径。返回追加到错误信息里的说明。
// NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
std::string restore_archived(const fs::path& archived, const fs::path& db_file) {
    if (archived.empty()) { return {}; }   // 回滚前库不存在：没有可复原的东西
    std::error_code err;
    fs::rename(archived, db_file, err);
    if (!err) { return "; restored " + db_file.string(); }
    std::cerr << "[world_store] rollback could not restore " << db_file.string() << " from "
              << archived.string() << ": " << err.message() << "\n";
    return "; could not restore " + db_file.string() + ", the previous database is at " +
           archived.string() + ": " + err.message();
}

}  // namespace

// NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
RollbackResult rollback_world(const Registry& reg, const std::string& world,
                              const std::string& snapshot_id, const RollbackOptions& opts) {
    fs::path partial;    // 第 6 步起非空：任何失败都删掉它
    RollbackResult result;
    try {
        // 1–2. 路径只从注册表取；快照文件解析符号链接后必须仍在该世界的 snapshot_dir 之下。
        const WorldEntry& entry = registered_world(reg, world);
        const SnapshotEntry& snap = registered_snapshot(reg, world, snapshot_id);
        require_inside_registry(entry.snapshot_dir, snap.path);
        const fs::path db_file = entry.db_path;
        const fs::path db_dir = db_file.parent_path();
        const fs::path wal = db_file.string() + "-wal";
        const fs::path shm = db_file.string() + "-shm";

        // 3–4. 先验快照本身，任何文件都还没写。
        require_intact_snapshot(snap.path);
        verify_world_tenant(snap.path, entry.tenant);

        // 5. 复制品与（极端情况下复原时的）余量：2 × 快照大小。
        const auto snap_bytes = static_cast<std::int64_t>(fs::file_size(snap.path));
        const std::int64_t avail =
            opts.free_space ? opts.free_space(db_dir) : available_bytes(db_dir);
        if (avail < 2 * snap_bytes) {
            throw WorldStoreError("insufficient_disk",
                                  "need " + std::to_string(2 * snap_bytes) + " bytes free in " +
                                      db_dir.string() + ", have " + std::to_string(avail));
        }

        // 6. 复制到库所在目录的隐藏 partial（同目录，第 8 步的改名才是原子的）。库目录只读时
        //    在这里失败，目标库一个字节都没动：绝不直接往库路径上复制。
        partial = db_dir / ("." + db_file.filename().string() + ".rollback-" + random_hex() +
                            ".partial");
        fs::copy_file(snap.path, partial, fs::copy_options::overwrite_existing);
        const auto db_status = lstat_or_throw(db_file);
        const bool db_exists = fs::exists(db_status);
        if (db_exists && !fs::is_regular_file(db_status)) {
            // 符号链接被改名进 archive 后，list / purge 都不认它（跳过符号链接），归档就丢了。
            throw WorldStoreError("snapshot_failed",
                                  db_file.string() + " is not a regular file; refusing to replace");
        }
        if (db_exists) {
            // 恢复出来的库沿用现役库的权限位（例如收紧过的 0600），不随快照文件放宽。
            fs::permissions(partial, fs::status(db_file).permissions(), fs::perm_options::replace);
        }
        const auto staged_bytes = static_cast<std::int64_t>(fs::file_size(partial));
        if (!passes_check(partial.string(), "PRAGMA quick_check")) {
            throw WorldStoreError("snapshot_failed", "quick_check failed for " + partial.string());
        }

        // 7. -wal 非空就拒绝；否则把现役库改名进 <世界 home>/archive。改名跨文件系统失败
        //    （EXDEV）时 rename 什么都没做，由下面的 catch 转成 snapshot_failed。
        require_no_pending_wal(wal);
        fs::path archived;   // 非空 = 现役库已挪进 archive，之后的失败要把它改名回来
        if (db_exists) {
            const fs::path archive = archive_dir_of(entry);
            fs::create_directories(archive);
            // archive/ 被换成指向外部的符号链接时拒绝：不把现役库挪出世界目录。
            require_inside_registry(world_home(entry), archive);
            const fs::path target = fresh_archive_path(archive, db_file.filename().string());
            fs::rename(db_file, target);
            archived = target;
        }

        // 第 7 步之后的任何失败：归档改名回库路径，partial 由外层 catch 删掉。
        try {
            // 只读读者留下的空 -wal（已确认为空）与 -shm 属于旧库，不能挂在新库旁边。
            fs::remove(wal);
            fs::remove(shm);
            if (opts.before_replace) { opts.before_replace(partial); }
            // 8.
            fs::rename(partial, db_file);
        } catch (const std::exception& ex) {
            const std::string restored = restore_archived(archived, db_file);
            throw WorldStoreError("snapshot_failed", "cannot replace " + db_file.string() + ": " +
                                                         ex.what() + restored);
        } catch (...) {
            const std::string restored = restore_archived(archived, db_file);
            throw WorldStoreError("snapshot_failed",
                                  "cannot replace " + db_file.string() + restored);
        }
        result.archive_path = archived.string();
        result.restored_bytes = staged_bytes;
    } catch (const WorldStoreError&) {
        std::error_code ignore;
        if (!partial.empty()) { fs::remove(partial, ignore); }
        throw;
    } catch (const std::exception& ex) {
        std::error_code ignore;
        if (!partial.empty()) { fs::remove(partial, ignore); }
        throw WorldStoreError("snapshot_failed", ex.what());
    } catch (...) {
        std::error_code ignore;
        if (!partial.empty()) { fs::remove(partial, ignore); }
        throw WorldStoreError("snapshot_failed", "rollback of '" + world + "' failed");
    }
    return result;
}

std::vector<ArchiveEntry> list_rollback_archives(const Registry& reg, const std::string& world) {
    const WorldEntry& entry = registered_world(reg, world);
    const fs::path dir = archive_dir_of(entry);
    if (!fs::exists(lstat_or_throw(dir))) { return {}; }
    // archive/ 本身指向外部时，逐个列出与 remove_within(archive, …) 都会以外部目录为根。
    require_inside_registry(world_home(entry), dir);

    std::vector<ArchiveEntry> out;
    std::error_code err;
    fs::directory_iterator iter(dir, err);
    const fs::directory_iterator done;
    for (; !err && iter != done; iter.increment(err)) {
        const fs::directory_entry& item = *iter;
        std::error_code item_err;
        // 只认普通文件：符号链接（回滚从不创建）一概跳过，免得经它删到别处。
        if (item.is_symlink(item_err) || !item.is_regular_file(item_err)) { continue; }
        std::string name = item.path().filename().string();
        if (!looks_like_archive_name(name)) { continue; }
        const auto size = item.file_size(item_err);
        if (item_err) { continue; }   // 列的同时被删了
        ArchiveEntry archive;
        archive.name = std::move(name);
        archive.size_bytes = static_cast<std::int64_t>(size);
        out.push_back(std::move(archive));
    }
    if (err) {
        throw WorldStoreError("snapshot_failed",
                              "cannot list " + dir.string() + ": " + err.message());
    }
    std::ranges::sort(out, std::ranges::greater{}, &ArchiveEntry::name);
    return out;
}

std::size_t purge_rollback_archives(const Registry& reg, const std::string& world) {
    const auto listed = list_rollback_archives(reg, world);
    const fs::path dir = archive_dir_of(registered_world(reg, world));
    std::size_t removed = 0;
    for (const auto& item : listed) {
        if (!remove_within(dir, dir / item.name)) {
            throw WorldStoreError("snapshot_failed", "archive " + item.name + " resolves outside " +
                                                         dir.string() + "; refusing to delete");
        }
        ++removed;
    }
    return removed;
}

}  // namespace starling::governance

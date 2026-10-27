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

// 字面判断，不解析符号链接。这是字面预检：形状校验（快照路径在 snapshot_dir 之下）与世界名推出的
// home 的字面检查用它；布局校验另外解析符号链接之后再判断（见 require_resolved_within）。
bool lexically_within(const fs::path& base, const fs::path& target) {
    return strictly_under(normalized(base), normalized(target));
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

// 布局校验用的解析：跟随符号链接之后的绝对位置（已规范化）。末端是悬空的符号链接时也跟到底：
// fs::weakly_canonical 把它当成一个不存在的普通名字原样留下，而 SQLite 以 O_CREAT 打开它会在
// 链接目标处建库（实测），世界库就建到了世界目录之外。中间某一级悬空时，在它下面什么都建不
// 出来（mkdir 报 EEXIST、open 报 ENOENT），weakly_canonical 的字面结果够用。
// 也就是说，中间某一级是悬空链接时只解析末尾，其余部分按字面算。这可能多拒绝一些布局（例如
// worlds/sim-1 悬空地指向 worlds/sim-1-real），但不会让路径越界放行，即 fail closed。
// 解析出错（EACCES、ELOOP 等）时证明不了路径在哪里，按越界处理：registry_corrupt，带上原因。
[[noreturn]] void unresolvable(const fs::path& path, const std::error_code& err) {
    corrupt("cannot resolve " + path.string() + ": " + err.message());
}

// 去掉末尾的 "/" 与 "."（"a/b/"、"a/b/." → "a/b"）。主要理由：lstat("链接/") 会跟随链接，把末端
// 的链接本身藏起来（悬空时就成了「不存在」），字面结果于是放行；去掉末尾的分隔符，规则才能一致地
// 执行，不取决于注册表里的写法。另外 mkdir("链接/") 在 macOS 上会在链接目标处建目录（实测），但
// take_snapshot 的 create_directories 走不走得到这一步取决于实现（libc++ 可能先在父路径那一级报
// EEXIST），不作为依据。
fs::path without_trailing_dot_or_slash(fs::path path) {
    while (path.has_relative_path() && (path.filename().empty() || path.filename() == ".")) {
        path = path.parent_path();
    }
    return path;
}

fs::path resolve_for_layout(const fs::path& path) {
    constexpr int kMaxLinkHops = 40;
    fs::path current = path;
    for (int hop = 0; hop < kMaxLinkHops; ++hop) {
        // 每一跳都去：链接内容本身也可以以 "/" 结尾。
        current = without_trailing_dot_or_slash(current);
        std::error_code err;
        const fs::file_status status = fs::symlink_status(current, err);
        // 不存在时 libc++ 也会把 err 设成 ENOENT，不算错误（同 lstat_or_throw）。
        if (err && status.type() != fs::file_type::not_found) { unresolvable(path, err); }
        if (status.type() != fs::file_type::symlink) {
            err.clear();
            const fs::path real = fs::weakly_canonical(current, err);
            if (err) { unresolvable(path, err); }
            return normalized(real);
        }
        const fs::path link = fs::read_symlink(current, err);
        if (err) { unresolvable(path, err); }
        // 相对的链接内容相对于链接所在的目录，与内核解析同义；".." 留给 weakly_canonical 处理。
        current = link.is_absolute() ? link : current.parent_path() / link;
    }
    unresolvable(path, std::make_error_code(std::errc::too_many_symbolic_link_levels));
}

// 布局校验：target 解析符号链接之后严格位于 base 解析之后的位置之下，否则 registry_corrupt。
// 两侧都解析，所以同一处换一种写法（/tmp 与 /private/tmp、经符号链接打开的注册表目录）仍然放行。
// 不保留「字面在 base 之下就放行」的捷径：字面上在世界目录里、磁盘上却是指向外部的符号链接时，
// W2 的快照写入、残留清扫、保留策略、删快照以 snapshot_dir 为根，引擎在 db_path 建库，全都会落到
// 世界目录之外（用户裁定 2026-10-27：这种布局不再支持）。".." 越界照样拒绝。
// NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
void require_resolved_within(const fs::path& base, const fs::path& target,
                             const std::string& what) {
    const fs::path real_base = resolve_for_layout(base);
    const fs::path real_target = resolve_for_layout(target);
    if (!strictly_under(real_base, real_target)) {
        corrupt(what + " " + target.string() + " resolves to " + real_target.string() +
                ", outside " + real_base.string());
    }
}

// 世界目录本身：解析符号链接之后必须恰好是「解析后的 worlds/」/<name>，只在 worlds/ 之下不够。
// 否则 worlds/sim-1 -> worlds/sim-2（或 worlds/sim-2/sub）能通过，delete_world("sim-1") 经
// remove_within 解析到 sim-2，删掉兄弟世界的整个目录和库（用户裁定 2026-10-27：每个世界目录解析后
// 都是 worlds/<它自己的名字>）。世界目录还不存在时 weakly_canonical 把缺的末尾原样接上，照常通过；
// worlds/ 整体外链到注册表目录内、注册表目录本身是符号链接，两侧同样解析，仍然放行。
void require_resolved_home(const fs::path& worlds_root, const std::string& name) {
    const fs::path home = worlds_root / name;
    const fs::path expected = resolve_for_layout(worlds_root) / name;
    const fs::path real_home = resolve_for_layout(home);
    if (real_home != expected) {
        corrupt("home of '" + name + "' " + home.string() + " resolves to " +
                real_home.string() + ", not " + expected.string());
    }
}

// 世界目录布局（解析符号链接之后判断，见 require_resolved_within）：
//   - 世界目录 <registry_dir>/worlds/<name> 解析后恰好是解析后的 worlds/ 下的 <name>
//     （require_resolved_home），不能是别的世界的目录或它的子目录；
//   - 非 default 世界的 db_path、所有世界的 snapshot_dir 严格位于各自的世界目录之下。
// default 的库保持原地（spec §0.1），不受此限；但它的快照目录同样固定在 worlds/<default>/ 下
// ——否则把它改成 "/"，删除快照、保留策略和残留清扫就能删到任意位置。
// 注册表目录本身可以是符号链接：两侧都解析，比的是同一处。
// worlds/ 解析符号链接之后必须仍在注册表目录之下。逐项比较两侧都解析符号链接，
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
        require_resolved_home(worlds_root, name);
        if (name != reg.default_world) {
            require_resolved_within(home, world.db_path, "db_path of '" + name + "'");
        }
        require_resolved_within(home, world.snapshot_dir, "snapshot_dir of '" + name + "'");
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

// 世界 home = <registry_dir>/worlds/<name>，与 create_world / delete_world 同一推导，只由服务端的
// 目录布局决定。snapshot_dir 不参与：load_registry 已拒绝解析后越出世界目录的 snapshot_dir
// （validate_layout），但 rollback_world 也可以不经 load 直接调用，归档位置不能依赖它。
// 归档目录为 <世界 home>/archive。
// 归档操作（回滚建硬链接、列出、清理）之前先 fail closed，此时还什么都没建：
//   1. worlds/ 解析符号链接后仍在注册表目录之下（require_worlds_root_inside，registry_corrupt）；
//   2. 世界 home 解析符号链接后严格在 worlds/ 之下，否则 snapshot_failed。与 delete_world 拒删
//      指向外部的世界目录是同一个边界。
// 返回世界 home（未解析符号链接的路径）。
fs::path checked_world_home(const fs::path& registry_dir, const std::string& world) {
    const fs::path root = normalized(fs::absolute(registry_dir));
    const fs::path worlds_root = root / "worlds";
    require_worlds_root_inside(root, worlds_root);
    const fs::path home = worlds_root / world;
    require_inside_registry(worlds_root, home);
    return home;
}

// candidate 与 db_file 是不是同一个文件（同一 inode）。任一方不存在或 stat 失败都算「不是」。
bool is_live_alias(const fs::path& candidate, const fs::path& db_file) {
    std::error_code err;
    const bool same = fs::equivalent(candidate, db_file, err);
    return !err && same;
}

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
constexpr std::string_view kRollbackTag = ".rollback-";
constexpr std::string_view kPartialSuffix = ".partial";
constexpr std::size_t kPartialHexLength = 16;   // random_hex() 的长度

// "<库文件名>.pre-rollback-<YYYYMMDDTHHMMSSZ>-<4 hex>"：后缀与快照 id 同形。
bool looks_like_archive_name(std::string_view name) {
    const auto pos = name.rfind(kPreRollback);
    return pos != std::string_view::npos && pos > 0 &&
           looks_like_snapshot_id(name.substr(pos + kPreRollback.size()));
}

// 回滚的 staging 文件：库所在目录里的 .<库文件名>.rollback-<16 位小写 hex>.partial。
std::string rollback_partial_prefix(const fs::path& db_file) {
    return "." + db_file.filename().string() + std::string(kRollbackTag);
}

bool looks_like_rollback_partial(std::string_view name, const std::string& prefix) {
    if (name.size() != prefix.size() + kPartialHexLength + kPartialSuffix.size() ||
        !name.starts_with(prefix) || !name.ends_with(kPartialSuffix)) {
        return false;
    }
    return std::ranges::all_of(name.substr(prefix.size(), kPartialHexLength), [](char chr) {
        return (chr >= '0' && chr <= '9') || (chr >= 'a' && chr <= 'f');
    });
}

// 清扫上次回滚崩溃留下的 partial（见 world_store.hpp rollback_world 第 4a 步）。只认名字严格
// 符合模式的普通文件，跳过符号链接，每个删除都经 remove_within。返回删掉的个数；错误只记日志。
std::size_t sweep_rollback_partials(const fs::path& db_file) {
    const fs::path dir = db_file.parent_path();
    const std::string prefix = rollback_partial_prefix(db_file);
    std::vector<fs::path> victims;
    std::error_code err;
    fs::directory_iterator iter(dir, err);
    const fs::directory_iterator done;
    for (; !err && iter != done; iter.increment(err)) {
        const fs::directory_entry& item = *iter;
        std::error_code status_err;
        if (item.is_symlink(status_err) || !item.is_regular_file(status_err)) { continue; }
        if (looks_like_rollback_partial(item.path().filename().string(), prefix)) {
            victims.push_back(item.path());
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
        std::cerr << "[world_store] swept " << swept << " leftover rollback partial(s) in "
                  << dir.string() << "\n";
    }
    return swept;
}

// 摘掉 archive 里是现役库第二个名字的条目（见 world_store.hpp rollback_world 第 4a 步）。上次回滚
// 若死在建硬链接之后、原子替换之前，归档名和库是同一个 inode：它不是归档，内容随现役库一起变。
// 删掉它只少一个名字，库不受影响。只认名字符合归档模式的普通文件，跳过符号链接，每个删除都经
// remove_within。archive/ 解析后不在世界 home 之下时不扫（第 9 步会拒绝这次回滚）。错误只记日志。
// NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
std::size_t sweep_archive_aliases(const fs::path& home, const fs::path& archive,
                                  const fs::path& db_file) {
    std::error_code err;
    if (!fs::exists(fs::symlink_status(archive, err))) { return 0; }
    try {
        require_inside_registry(home, archive);
    } catch (const WorldStoreError& escape) {
        std::cerr << "[world_store] not sweeping " << archive.string() << ": " << escape.what()
                  << "\n";
        return 0;
    }
    std::vector<fs::path> victims;
    fs::directory_iterator iter(archive, err);
    const fs::directory_iterator done;
    for (; !err && iter != done; iter.increment(err)) {
        const fs::directory_entry& item = *iter;
        std::error_code status_err;
        if (item.is_symlink(status_err) || !item.is_regular_file(status_err)) { continue; }
        if (looks_like_archive_name(item.path().filename().string()) &&
            is_live_alias(item.path(), db_file)) {
            victims.push_back(item.path());
        }
    }
    std::size_t swept = 0;
    for (const auto& victim : victims) {
        try {
            if (remove_within(archive, victim)) { ++swept; }
        } catch (const WorldStoreError& sweep_err) {
            std::cerr << "[world_store] cannot remove " << victim.string()
                      << ", a second name of the live database: " << sweep_err.what() << "\n";
        }
    }
    if (swept > 0) {
        std::cerr << "[world_store] removed " << swept << " archive name(s) in " << archive.string()
                  << " that were second names of the live database\n";
    }
    return swept;
}

// 给现役库在 archive 目录里建一个硬链接（归档名）并返回它。库文件本身不动，库路径上始终有
// 一份完整的库。名字已被占用（同一秒内两次回滚）就重抽；其余失败（EXDEV、文件系统不支持
// 硬链接、权限）抛 snapshot_failed，此时什么都没建。
// EXDEV 只出现在一种配置里：STARLING_WORLDS_REGISTRY 指到另一个卷，default 世界的库还在原卷
// （别的世界的库在 worlds/<name>/ 下，总与归档同卷）。不退回复制：复制要双倍磁盘和另一套磁盘
// 守卫，而这种配置今天没人部署。错误信息直接说明原因和办法。
// NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
fs::path link_into_archive(const fs::path& db_file, const fs::path& archive) {
    constexpr int kMaxAttempts = 16;
    const std::string db_name = db_file.filename().string();
    for (int attempt = 0; attempt < kMaxAttempts; ++attempt) {
        const fs::path link = archive / (db_name + std::string(kPreRollback) + compact_now() +
                                         "-" + random_hex().substr(0, 4));
        std::error_code err;
        fs::create_hard_link(db_file, link, err);
        if (!err) { return link; }
        if (err == std::errc::cross_device_link) {
            throw WorldStoreError(
                "snapshot_failed",
                "cannot link " + db_file.string() + " into " + archive.string() +
                    ": the archive directory and the database are on different file systems; "
                    "rollback keeps the replaced database as a hard link, so both must be on the "
                    "same volume: move the worlds registry (STARLING_WORLDS_REGISTRY) next to "
                    "the database");
        }
        if (err != std::errc::file_exists) {
            throw WorldStoreError("snapshot_failed", "cannot link " + db_file.string() + " into " +
                                                         archive.string() + ": " + err.message());
        }
    }
    throw WorldStoreError("snapshot_failed", "no free archive name in " + archive.string());
}

// 第 3 步：快照文件缺失或不是普通文件 → snapshot_corrupt。
void require_snapshot_file(const std::string& path) {
    std::error_code err;
    if (!fs::is_regular_file(path, err)) {
        throw WorldStoreError("snapshot_corrupt", "snapshot file " + path + " is missing");
    }
}

// 第 6 步：只读打开复制品做 integrity_check。打不开、不是 SQLite 或结果不是 "ok"，
// 一律 snapshot_corrupt。
void require_intact_copy(const fs::path& copy) {
    bool intact = false;
    try {
        const auto handle = open_read_only(copy.string());
        persistence::Stmt check(handle.get(), "PRAGMA integrity_check");
        intact = check.step_row() && column_text(check.raw(), 0) == "ok";
    } catch (const std::exception& ex) {
        throw WorldStoreError("snapshot_corrupt",
                              "cannot read snapshot copy " + copy.string() + ": " + ex.what());
    }
    if (!intact) {
        throw WorldStoreError("snapshot_corrupt", "integrity_check failed for " + copy.string());
    }
}

// 库旁边的 -wal / -journal 非空（或不是普通文件）：还有未合并进主文件的写入、写连接还开着，
// 或者有崩溃事务留下的热日志。此时主文件不是完整的库；残留的 WAL / 热日志还会被 SQLite
// 重放或回滚到恢复出来的库上，把它写坏。
void require_empty_sidecar(const fs::path& sidecar) {
    const auto status = lstat_or_throw(sidecar);
    if (!fs::exists(status)) { return; }
    std::error_code err;
    if (!fs::is_regular_file(status) || fs::file_size(sidecar, err) != 0 || err) {
        throw WorldStoreError("snapshot_failed",
                              sidecar.string() + " is not empty: the database has pending "
                              "writes, an open writer or a hot journal");
    }
}

// 库旁边的 -shm 只能不存在或是普通文件，大小不论：它是 wal-index，SQLite 按主文件加 WAL
// 重建，持久性从不依赖它。目录、符号链接之类不是 SQLite 留下的，第 10 步不该删它们（非空
// 目录也删不掉），所以在这里就拒绝，此时什么都还没改。
void require_regular_or_absent(const fs::path& sidecar) {
    const auto status = lstat_or_throw(sidecar);
    if (fs::exists(status) && !fs::is_regular_file(status)) {
        throw WorldStoreError("snapshot_failed", sidecar.string() +
                                                     " is not a regular file; refusing to "
                                                     "remove it");
    }
}

// 第 8 步：要被替换的必须是一个 SQLite 库（16 字节文件头）。default 世界的 db_path 不受
// validate_layout 约束，被篡改的注册表可以让它指向任意文件；不查就会把那个文件整个换掉、
// 挪进归档，purge 之后就没了。
void require_sqlite_header(const fs::path& db_file) {
    constexpr std::size_t kHeaderLength = 16;
    constexpr std::string_view kMagic{"SQLite format 3\0", kHeaderLength};
    std::array<char, kHeaderLength> head{};
    std::ifstream input(db_file, std::ios::binary);
    if (!input) {
        throw WorldStoreError("snapshot_failed", "cannot read " + db_file.string());
    }
    input.read(head.data(), static_cast<std::streamsize>(head.size()));
    if (!input || std::string_view(head.data(), head.size()) != kMagic) {
        throw WorldStoreError("snapshot_failed", db_file.string() +
                                                     " is not a SQLite database; refusing to "
                                                     "replace it");
    }
}

// 第 8 步末：探测别的连接（同进程或别的进程）。新开一条读写连接（不 CREATE），busy_timeout 为
// 0，PRAGMA locking_mode=EXCLUSIVE 后 BEGIN EXCLUSIVE：拿不到排他锁回 SQLITE_BUSY → world_in_use；
// 拿到了就 ROLLBACK 关掉，什么都没写。
// 它看得见哪些连接取决于库的日志模式（在生产库副本上实测）：
//                                  WAL        rollback-journal（delete）
//   闲置的只读连接（读过）           BUSY       看不见
//   闲置的读写连接（读过）           BUSY       看不见
//   开着的读事务                     BUSY       BUSY
//   打开了、从没读过                 看不见     看不见
// 恢复出来的库是 VACUUM INTO 的产物，引擎打开它之前一直是 delete 模式（例如回滚过、还没
// 激活过的非活动世界），这时闲置的连接全都看不见。
// 所以探测只是纵深防御。别的进程对 dashboard 管的库开写连接不在支持的使用方式之内；进程内的
// 安全靠 WorldManager 的租约、旧 Runtime 弱引用已失效的证明和遗留 Runtime 登记。
// 必须在 -wal / -journal 检查之后调用：那时两者都为空，这条连接不会把残留的 WAL 或热日志
// 重放进旧库。
void require_no_other_connection(const fs::path& db_file) {
    sqlite3* raw = nullptr;
    const std::string uri = "file:" + uri_escape_path(db_file.string());
    const int opened =
        sqlite3_open_v2(uri.c_str(), &raw, SQLITE_OPEN_READWRITE | SQLITE_OPEN_URI, nullptr);
    const persistence::SqliteHandle handle(raw);
    if (opened != SQLITE_OK) {
        throw WorldStoreError("snapshot_failed",
                              "cannot open " + db_file.string() + " to check for other "
                              "connections: " + (raw != nullptr ? sqlite3_errmsg(raw) : "alloc"));
    }
    sqlite3_busy_timeout(raw, 0);
    for (const char* sql : {"PRAGMA locking_mode=EXCLUSIVE", "BEGIN EXCLUSIVE", "ROLLBACK"}) {
        // 这条连接没开扩展结果码，sqlite3_exec 回的就是主结果码（SQLITE_BUSY / SQLITE_LOCKED）。
        const int code = sqlite3_exec(raw, sql, nullptr, nullptr, nullptr);
        if (code == SQLITE_OK) { continue; }
        const std::string why = sqlite3_errmsg(raw);
        if (code == SQLITE_BUSY || code == SQLITE_LOCKED) {
            throw WorldStoreError("world_in_use",
                                  db_file.string() + " is open in another connection (" + why +
                                      "); refusing to replace it");
        }
        throw WorldStoreError("snapshot_failed", "cannot check " + db_file.string() +
                                                     " for other connections: " + why);
    }
}

// 替换失败时摘掉刚建的归档名。库没被替换，归档名与库是同一个 inode，删掉它只少一个名字。
// 删不掉时它就是现役库的第二个名字：清理它无害，但不能用写连接打开它。返回追加到错误信息
// 里的说明。
std::string drop_archive_name(const fs::path& archived) {
    if (archived.empty()) { return {}; }   // 回滚前库不存在：没有建归档名
    std::string why;
    try {
        if (remove_within(archived.parent_path(), archived)) { return {}; }
        why = "it resolves outside " + archived.parent_path().string();
    } catch (const WorldStoreError& err) {
        why = err.what();
    }
    std::cerr << "[world_store] rollback could not remove archive name " << archived.string()
              << ", which is a second name of the live database: " << why << "\n";
    return "; " + archived.string() + " could not be removed (" + why +
           ") and is a second name of the live database: do not open it with a write connection";
}

// 回滚第 1–4 步通过之后已经确定的东西。指针指向 reg 里的条目，reg 必须比它活得久。
struct RollbackTarget {
    const WorldEntry* entry = nullptr;
    const SnapshotEntry* snap = nullptr;
    fs::path home;                // 世界 home（未解析符号链接的路径）
    std::int64_t snap_bytes = 0;
};

// 回滚第 1–4 步：只读检查，不清扫、不复制、不建目录。check_rollback（预检）与 rollback_world
// 共用这一份，顺序与错误码都一样（见 world_store.hpp rollback_world）。
// NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
RollbackTarget check_rollback_target(const Registry& reg, const fs::path& registry_dir,
                                     const std::string& world, const std::string& snapshot_id,
                                     const RollbackOptions& opts) {
    // 1. 路径只从注册表取。向量在库文件之外的后端（zvec）恢复不出完整的世界（spec §12）。
    RollbackTarget target;
    target.entry = &registered_world(reg, world);
    target.snap = &registered_snapshot(reg, world, snapshot_id);
    if (opts.vector_backend != "sqlite") {
        throw WorldStoreError("snapshot_unsupported_backend",
                              "vector_backend '" + opts.vector_backend + "' keeps vectors "
                              "outside the database file");
    }
    // 2–3. 快照文件解析符号链接后必须仍在该世界的 snapshot_dir 之下，且是普通文件。
    require_inside_registry(target.entry->snapshot_dir, target.snap->path);
    require_snapshot_file(target.snap->path);
    // 4. 世界 home 由注册表目录推出，解析后必须在 worlds/ 之下（见 checked_world_home）；
    //    复制品与余量：库所在目录要有 2 × 快照大小。
    target.home = checked_world_home(registry_dir, world);
    const fs::path db_dir = fs::path(target.entry->db_path).parent_path();
    target.snap_bytes = static_cast<std::int64_t>(fs::file_size(target.snap->path));
    const std::int64_t avail = opts.free_space ? opts.free_space(db_dir) : available_bytes(db_dir);
    if (avail < 2 * target.snap_bytes) {
        throw WorldStoreError("insufficient_disk",
                              "need " + std::to_string(2 * target.snap_bytes) + " bytes free in " +
                                  db_dir.string() + ", have " + std::to_string(avail));
    }
    return target;
}

}  // namespace

// NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
void check_rollback(const Registry& reg, const fs::path& registry_dir, const std::string& world,
                    const std::string& snapshot_id, const RollbackOptions& opts) {
    try {
        (void)check_rollback_target(reg, registry_dir, world, snapshot_id, opts);
    } catch (const WorldStoreError&) {
        throw;
    } catch (const std::exception& ex) {
        throw WorldStoreError("snapshot_failed", ex.what());
    } catch (...) {
        throw WorldStoreError("snapshot_failed", "rollback check of '" + world + "' failed");
    }
}

// NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
RollbackResult rollback_world(const Registry& reg, const fs::path& registry_dir,
                              const std::string& world, const std::string& snapshot_id,
                              const RollbackOptions& opts) {
    fs::path partial;    // 第 5 步起非空：任何失败都删掉它
    RollbackResult result;
    try {
        // 1–4. 与 check_rollback 同一份检查。调用方即使预检过也要再查：预检之后状态可能变了。
        const RollbackTarget target =
            check_rollback_target(reg, registry_dir, world, snapshot_id, opts);
        const WorldEntry& entry = *target.entry;
        const SnapshotEntry& snap = *target.snap;
        const fs::path& home = target.home;
        const fs::path db_file = entry.db_path;
        const fs::path db_dir = db_file.parent_path();
        const fs::path wal = db_file.string() + "-wal";
        const fs::path shm = db_file.string() + "-shm";
        const fs::path journal = db_file.string() + "-journal";

        // 4a. 上次回滚崩溃留下的 partial，以及 archive 里是现役库第二个名字的条目。
        (void)sweep_rollback_partials(db_file);
        (void)sweep_archive_aliases(home, home / "archive", db_file);

        // 5. 复制到库所在目录的隐藏 partial（同目录，第 11 步的改名才是原子的）。库目录只读时
        //    在这里失败，目标库一个字节都没动：绝不直接往库路径上复制。
        partial = db_dir / (rollback_partial_prefix(db_file) + random_hex() +
                            std::string(kPartialSuffix));
        fs::copy_file(snap.path, partial, fs::copy_options::overwrite_existing);

        // 6–7. 校验的是要装上去的那份字节：复制之后快照文件怎么变都影响不到它。
        require_intact_copy(partial);
        verify_world_tenant(partial.string(), entry.tenant);
        const auto staged_bytes = static_cast<std::int64_t>(fs::file_size(partial));

        // 8. 库路径与附属文件的前置检查，什么都还没改。
        const auto db_status = lstat_or_throw(db_file);
        const bool db_exists = fs::exists(db_status);
        if (db_exists && !fs::is_regular_file(db_status)) {
            // 库路径不是普通文件（例如符号链接）：对符号链接建硬链接，得到什么因平台而异
            // （macOS 的 link() 跟随链接、链到目标文件；Linux 链的是符号链接本身），两种结果都
            // 不是我们要的归档：前者让链接目标多出一个名字，后者 list / purge 认不出（跳过符号
            // 链接）。所以直接拒绝。
            throw WorldStoreError("snapshot_failed",
                                  db_file.string() + " is not a regular file; refusing to replace");
        }
        require_empty_sidecar(wal);
        require_empty_sidecar(journal);
        require_regular_or_absent(shm);
        if (db_exists) {
            require_sqlite_header(db_file);
            // 恢复出来的库沿用现役库的权限位（例如收紧过的 0600），不随快照文件放宽。
            fs::permissions(partial, fs::status(db_file).permissions(), fs::perm_options::replace);
            // 最后一道检查，紧挨着建硬链接：还有别的连接开着就不动它（world_in_use）。
            require_no_other_connection(db_file);
        }

        // 9. 给现役库在 <世界 home>/archive 建硬链接。库路径不动。
        fs::path archived;   // 非空 = 归档名已建好，之后的失败要把它摘掉
        if (db_exists) {
            // 复制与校验可能花了几秒：建目录之前再查一遍世界 home，世界目录之外什么都不建。
            const fs::path archive = checked_world_home(registry_dir, world) / "archive";
            fs::create_directories(archive);
            // archive/ 被换成指向外部的符号链接时拒绝：不在世界目录之外给现役库建名字。
            require_inside_registry(home, archive);
            archived = link_into_archive(db_file, archive);
        }

        // 10–11. 库路径上仍是旧库。失败时库原样不动，只需摘掉归档名；partial 由外层 catch 删。
        try {
            // 旁车属于旧库，不能挂在新库旁边，所以在替换之前删。替换随后失败时，旧库少了它们
            // 也照常可用，因为它们不带任何状态：-wal / -journal 在第 8 步已确认为空或不存在；
            // -shm 是 wal-index，SQLite 按主文件加 WAL 重建，不承载持久数据。删的时候也没有
            // 连接在用它们：第 8 步的探测，加上 Python 侧在回滚之前停线程、等租约、确认旧
            // Runtime 已回收。
            // 改成替换之后再删更糟：从 rename 到删完这段时间里，旧库的 -shm / -wal 挂在新库旁边，
            // 这时打开新库的连接会拿旧库的 wal-index 去读新库。
            for (const fs::path& sidecar : {wal, shm, journal}) { fs::remove(sidecar); }
            if (opts.before_replace) { opts.before_replace(partial); }
            // 原子替换：此前库路径是旧库，此后是新库；旧 inode 只剩归档这一个名字。
            fs::rename(partial, db_file);
        } catch (const std::exception& ex) {
            throw WorldStoreError("snapshot_failed", "cannot replace " + db_file.string() + ": " +
                                                         ex.what() + "; the database is unchanged" +
                                                         drop_archive_name(archived));
        } catch (...) {
            throw WorldStoreError("snapshot_failed", "cannot replace " + db_file.string() +
                                                         "; the database is unchanged" +
                                                         drop_archive_name(archived));
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

std::vector<ArchiveEntry> list_rollback_archives(const Registry& reg, const fs::path& registry_dir,
                                                 const std::string& world) {
    const WorldEntry& entry = registered_world(reg, world);
    const fs::path home = checked_world_home(registry_dir, world);
    const fs::path dir = home / "archive";
    if (!fs::exists(lstat_or_throw(dir))) { return {}; }
    // archive/ 本身指向外部时，逐个列出与 remove_within(archive, …) 都会以外部目录为根。
    require_inside_registry(home, dir);
    const fs::path db_file = entry.db_path;

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
        // 现役库的第二个名字（回滚死在建硬链接之后、替换之前）不是归档：不列、不计、不清理，
        // 下一次回滚开头摘掉它（第 4a 步）。
        if (is_live_alias(item.path(), db_file)) { continue; }
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

std::size_t purge_rollback_archives(const Registry& reg, const fs::path& registry_dir,
                                    const std::string& world) {
    const auto listed = list_rollback_archives(reg, registry_dir, world);
    const fs::path dir = checked_world_home(registry_dir, world) / "archive";
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

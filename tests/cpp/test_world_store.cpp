// test_world_store.cpp — 世界注册表（W1）、快照（W2）与回滚/归档（W3）。
// 设计：docs/superpowers/specs/2026-10-25-world-scene-management-design.md §3/§4/§5.1。

#include "starling/governance/world_store.hpp"

#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/stmt.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <unistd.h>

#include <algorithm>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iterator>
#include <limits>
#include <optional>
#include <random>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace starling::governance {
namespace {

namespace fs = std::filesystem;

// 每个用例一个独立的临时目录，析构时删除。
class TempDir {
public:
    TempDir() {
        static std::atomic<int> seq{0};
        path_ = fs::temp_directory_path() /
                ("starling-world-" + std::to_string(::getpid()) + "-" +
                 std::to_string(++seq));
        fs::remove_all(path_);
        fs::create_directories(path_);
    }
    ~TempDir() { std::error_code err; fs::remove_all(path_, err); }
    TempDir(const TempDir&) = delete;
    TempDir& operator=(const TempDir&) = delete;
    TempDir(TempDir&&) = delete;
    TempDir& operator=(TempDir&&) = delete;
    [[nodiscard]] const fs::path& path() const { return path_; }
private:
    fs::path path_;
};

std::string slurp(const fs::path& file) {
    std::ifstream input(file, std::ios::binary);
    return {std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
}

std::string code_of(const std::function<void()>& action) {
    try { action(); } catch (const WorldStoreError& err) { return err.code(); }
    return "<no throw>";
}

TEST(WorldName, AcceptsAndRejects) {
    EXPECT_TRUE(is_valid_world_name("default"));
    EXPECT_TRUE(is_valid_world_name("sim-1"));
    EXPECT_TRUE(is_valid_world_name("a_b"));
    EXPECT_TRUE(is_valid_world_name("0abc"));
    EXPECT_FALSE(is_valid_world_name(""));
    EXPECT_FALSE(is_valid_world_name("-lead"));
    EXPECT_FALSE(is_valid_world_name("Upper"));
    EXPECT_FALSE(is_valid_world_name("has space"));
    EXPECT_FALSE(is_valid_world_name("../escape"));
    EXPECT_FALSE(is_valid_world_name("a/b"));
    EXPECT_FALSE(is_valid_world_name(std::string(33, 'a')));
    EXPECT_TRUE(is_valid_world_name(std::string(32, 'a')));
}

TEST(WorldRegistry, EnsureCreatesDefaultOnce) {
    const TempDir tmp;
    const auto reg_path = tmp.path() / "worlds.json";
    const auto db_path = tmp.path() / "dashboard.db";
    const auto first = ensure_registry(reg_path, db_path, "default");
    ASSERT_TRUE(fs::exists(reg_path));
    EXPECT_EQ(first.active, "default");
    EXPECT_EQ(first.default_world, "default");
    EXPECT_EQ(first.snapshot_retention, 5);
    ASSERT_EQ(first.worlds.count("default"), 1U);
    const auto& dflt = first.worlds.at("default");
    EXPECT_EQ(dflt.tenant, "default");
    EXPECT_EQ(fs::path(dflt.db_path), db_path);
    EXPECT_EQ(fs::path(dflt.snapshot_dir), tmp.path() / "worlds" / "default" / "snapshots");

    // 第二次调用不能覆盖已有注册表（哪怕传了不同的 default 路径）。
    auto edited = load_registry(reg_path);
    edited.worlds.at("default").label = "改过的";
    save_registry(reg_path, edited);
    const auto second = ensure_registry(reg_path, tmp.path() / "other.db", "default");
    EXPECT_EQ(second.worlds.at("default").label, "改过的");
    EXPECT_EQ(fs::path(second.worlds.at("default").db_path), db_path);
}

TEST(WorldRegistry, SaveIsAtomicAndRoundTrips) {
    const TempDir tmp;
    const auto reg_path = tmp.path() / "worlds.json";
    auto reg = ensure_registry(reg_path, tmp.path() / "dashboard.db", "default");
    SnapshotEntry snap;
    snap.id = "20261025T011200Z-a1b2";
    // 快照路径必须位于所属世界的 snapshot_dir 之下，否则 save 会以 registry_corrupt 拒绝。
    snap.path = (fs::path(reg.worlds.at("default").snapshot_dir) / "x.db").string();
    snap.kind = "manual";
    snap.reason = "manual";
    snap.note = "备注 with 'quote'";
    snap.created_at = "2026-10-25T01:12:00Z";
    snap.world_time = "2026-10-24T18:03:11Z";
    snap.size_bytes = 123;
    reg.snapshots["default"].push_back(snap);
    save_registry(reg_path, reg);
    // 原子写：目录里不能留下临时文件。
    for (const auto& entry : fs::directory_iterator(tmp.path())) {
        EXPECT_EQ(entry.path().filename().string().find(".tmp"), std::string::npos)
            << entry.path();
    }
    EXPECT_EQ(fs::status(reg_path).permissions() & fs::perms::all,
              fs::perms::owner_read | fs::perms::owner_write);
    const auto back = load_registry(reg_path);
    ASSERT_EQ(back.snapshots.at("default").size(), 1U);
    const auto& got = back.snapshots.at("default").front();
    EXPECT_EQ(got.id, snap.id);
    EXPECT_EQ(got.note, snap.note);
    EXPECT_EQ(got.world_time, snap.world_time);
    EXPECT_EQ(got.size_bytes, 123);
}

TEST(WorldRegistry, CorruptFileFailsLoud) {
    const TempDir tmp;
    const auto reg_path = tmp.path() / "worlds.json";
    { std::ofstream out(reg_path); out << "{not json"; }
    EXPECT_EQ(code_of([&] { (void)load_registry(reg_path); }), "registry_corrupt");
    // 损坏的注册表不能被 ensure_registry 悄悄重建（会丢掉其他世界的登记）。
    EXPECT_EQ(code_of([&] {
        (void)ensure_registry(reg_path, tmp.path() / "d.db", "default");
    }), "registry_corrupt");
}

TEST(WorldRegistry, RejectsRetentionBelowTwo) {
    const TempDir tmp;
    const auto reg_path = tmp.path() / "worlds.json";
    auto reg = ensure_registry(reg_path, tmp.path() / "dashboard.db", "default");
    reg.snapshot_retention = 1;
    EXPECT_EQ(code_of([&] { save_registry(reg_path, reg); }), "invalid_retention");
    // 手改文件写入 1，加载时也要拒绝。
    { std::ofstream out(reg_path); out << R"({"version":1,"default":"default","active":"default","snapshot_retention":1,"worlds":{"default":{"tenant":"default","db_path":"/x","snapshot_dir":"/y","label":"","created_at":""}},"snapshots":{}})"; }
    EXPECT_EQ(code_of([&] { (void)load_registry(reg_path); }), "invalid_retention");
}

TEST(WorldRegistry, CreateWorldLayoutAndValidation) {
    const TempDir tmp;
    const auto reg_path = tmp.path() / "worlds.json";
    auto reg = ensure_registry(reg_path, tmp.path() / "dashboard.db", "default");
    const auto made = create_world(reg, tmp.path(), "sim-1", "模拟一", "2026-10-25T01:00:00Z");
    EXPECT_EQ(made.tenant, "sim-1");
    EXPECT_EQ(fs::path(made.db_path), tmp.path() / "worlds" / "sim-1" / "world.db");
    EXPECT_EQ(fs::path(made.snapshot_dir), tmp.path() / "worlds" / "sim-1" / "snapshots");
    EXPECT_TRUE(fs::is_directory(made.snapshot_dir));
    EXPECT_FALSE(fs::exists(made.db_path));   // 库留到首次激活
    EXPECT_EQ(reg.worlds.count("sim-1"), 1U);
    EXPECT_EQ(code_of([&] {
        (void)create_world(reg, tmp.path(), "sim-1", "", "2026-10-25T01:00:00Z");
    }), "world_exists");
    EXPECT_EQ(code_of([&] {
        (void)create_world(reg, tmp.path(), "../evil", "", "2026-10-25T01:00:00Z");
    }), "invalid_world_name");
}

TEST(WorldRegistry, SetActiveAndDeleteGuards) {
    const TempDir tmp;
    const auto reg_path = tmp.path() / "worlds.json";
    auto reg = ensure_registry(reg_path, tmp.path() / "dashboard.db", "default");
    (void)create_world(reg, tmp.path(), "sim-1", "", "2026-10-25T01:00:00Z");
    EXPECT_EQ(code_of([&] { set_active(reg, "nope"); }), "world_not_found");
    set_active(reg, "sim-1");
    EXPECT_EQ(reg.active, "sim-1");
    EXPECT_EQ(code_of([&] { delete_world(reg, tmp.path(), "sim-1"); }), "world_protected");
    EXPECT_EQ(code_of([&] { delete_world(reg, tmp.path(), "default"); }), "world_protected");
    EXPECT_EQ(code_of([&] { delete_world(reg, tmp.path(), "nope"); }), "world_not_found");
    set_active(reg, "default");
    // 先放一条快照记录，否则下面「快照列表随世界一起删除」的断言永远成立。
    reg.snapshots["sim-1"].push_back(SnapshotEntry{});
    ASSERT_EQ(reg.snapshots.count("sim-1"), 1U);
    const auto dir = tmp.path() / "worlds" / "sim-1";
    ASSERT_TRUE(fs::exists(dir));
    delete_world(reg, tmp.path(), "sim-1");
    EXPECT_EQ(reg.worlds.count("sim-1"), 0U);
    EXPECT_EQ(reg.snapshots.count("sim-1"), 0U);
    EXPECT_FALSE(fs::exists(dir));
}

TEST(WorldRegistry, DeleteRefusesPathOutsideRegistryDir) {
    const TempDir tmp;
    const TempDir outside;
    const auto reg_path = tmp.path() / "worlds.json";
    auto reg = ensure_registry(reg_path, tmp.path() / "dashboard.db", "default");
    (void)create_world(reg, tmp.path(), "sim-1", "", "2026-10-25T01:00:00Z");
    // 模拟被篡改的注册表：db_path 指到外部目录。
    reg.worlds.at("sim-1").db_path = (outside.path() / "world.db").string();
    reg.worlds.at("sim-1").snapshot_dir = (outside.path() / "snapshots").string();
    { std::ofstream out(outside.path() / "keep.txt"); out << "x"; }
    delete_world(reg, tmp.path(), "sim-1");
    EXPECT_TRUE(fs::exists(outside.path() / "keep.txt"));   // 外部文件不受影响
    EXPECT_EQ(reg.worlds.count("sim-1"), 0U);
}

// worlds/<name> 若是指向外部的符号链接（worlds/ 本身是真目录），remove_within 解析后发现越界，
// 什么都不删；delete_world 必须 fail closed——抛 snapshot_failed、注册项保留。旧实现忽略
// remove_within 的返回值照样摘掉注册项，外部目录成了无主孤儿（与快照越界的 I7 处理不一致）。
TEST(WorldRegistry, DeleteRefusesSymlinkEscapingRegistryDir) {
    const TempDir tmp;
    const TempDir outside;
    const auto reg_path = tmp.path() / "worlds.json";
    auto reg = ensure_registry(reg_path, tmp.path() / "dashboard.db", "default");
    (void)create_world(reg, tmp.path(), "sim-1", "", "2026-10-25T01:00:00Z");
    fs::remove_all(tmp.path() / "worlds" / "sim-1");
    fs::create_directory_symlink(outside.path(), tmp.path() / "worlds" / "sim-1");
    { std::ofstream out(outside.path() / "keep.txt"); out << "x"; }
    EXPECT_EQ(code_of([&] { delete_world(reg, tmp.path(), "sim-1"); }), "snapshot_failed");
    EXPECT_TRUE(fs::exists(outside.path() / "keep.txt"));
    EXPECT_TRUE(reg.worlds.contains("sim-1"));
}

// 路径解析本身出错（这里用自指符号链接触发 ELOOP）时无法判断是否越界：
// 必须 fail loud 并保留注册项，不能悄悄摘掉注册项而把数据遗弃在磁盘上。
TEST(WorldRegistry, DeleteFailsLoudWhenPathCannotBeResolved) {
    const TempDir tmp;
    const auto reg_path = tmp.path() / "worlds.json";
    auto reg = ensure_registry(reg_path, tmp.path() / "dashboard.db", "default");
    (void)create_world(reg, tmp.path(), "sim-1", "", "2026-10-25T01:00:00Z");
    reg.snapshots["sim-1"].push_back(SnapshotEntry{});
    fs::remove_all(tmp.path() / "worlds" / "sim-1");
    fs::create_symlink("sim-1", tmp.path() / "worlds" / "sim-1");   // 指向自己
    EXPECT_EQ(code_of([&] { delete_world(reg, tmp.path(), "sim-1"); }), "snapshot_failed");
    EXPECT_EQ(reg.worlds.count("sim-1"), 1U);
    EXPECT_EQ(reg.snapshots.count("sim-1"), 1U);
}

TEST(WorldRegistry, DanglingActiveFailsLoud) {
    const TempDir tmp;
    const auto reg_path = tmp.path() / "worlds.json";
    { std::ofstream out(reg_path); out << R"({"version":1,"default":"default","active":"ghost","snapshot_retention":5,"worlds":{"default":{"tenant":"default","db_path":"/x","snapshot_dir":"/y","label":"","created_at":""}},"snapshots":{}})"; }
    EXPECT_EQ(code_of([&] { (void)load_registry(reg_path); }), "registry_corrupt");
    EXPECT_EQ(code_of([&] {
        (void)ensure_registry(reg_path, tmp.path() / "d.db", "default");
    }), "registry_corrupt");
}

// save 与 load 的不变式必须一致：load 会拒绝的注册表，save 也不能写出去覆盖好文件。
TEST(WorldRegistry, SaveRefusesWhatLoadWouldReject) {
    const TempDir tmp;
    const auto reg_path = tmp.path() / "worlds.json";
    const auto reg = ensure_registry(reg_path, tmp.path() / "dashboard.db", "default");
    const std::string before = slurp(reg_path);

    Registry missing_default = reg;
    missing_default.default_world = "ghost";
    EXPECT_EQ(code_of([&] { save_registry(reg_path, missing_default); }), "registry_corrupt");

    Registry dangling_active = reg;
    dangling_active.active = "ghost";
    EXPECT_EQ(code_of([&] { save_registry(reg_path, dangling_active); }), "registry_corrupt");

    EXPECT_EQ(slurp(reg_path), before);   // 好文件原封不动
    EXPECT_EQ(code_of([&] { (void)load_registry(reg_path); }), "<no throw>");
}

// ---- W2：快照、保留策略与世界统计 ------------------------------------------

// 插入一行 engram eng-<idx>。
void insert_engram(sqlite3* dbh, const std::string& tenant, int idx) {
    // source_item_id 必须各不相同：idx_engrams_source_identity 是
    // (tenant_id, adapter_name, source_item_id, source_version, chunk_index) 唯一索引，
    // 只填必填列时后四列全是默认值 ''/0，第二行就会撞唯一约束（已实测）。
    persistence::Stmt ins(dbh,
        "INSERT INTO engrams(id,tenant_id,content_hash,source_kind,ingest_policy,"
        "ingest_mode,privacy_class,retention_mode,created_at,source_item_id) "
        "VALUES(?1,?2,?3,'conversation','default','inline','normal','audit_retain',?4,?1)");
    ins.bind("eng-" + std::to_string(idx), tenant, "h" + std::to_string(idx),
             "2026-10-2" + std::to_string(idx % 5) + "T00:00:00Z");
    ins.step_done();
}

// 在世界库里追加 engram 行 eng-<first> .. eng-<first+count-1>（库不存在时按真实迁移建库）。
void append_engrams(const fs::path& db_path, const std::string& tenant, int first, int count) {
    auto adapter = persistence::SqliteAdapter::open(db_path);
    for (int idx = first; idx < first + count; ++idx) {
        insert_engram(adapter->connection().raw(), tenant, idx);
    }
}

// 用真实迁移建一个有数据的世界库，保证快照测的是 Starling 真实的 schema。
void seed_world_db(const fs::path& db_path, const std::string& tenant, int engram_rows) {
    append_engrams(db_path, tenant, 0, engram_rows);
}

Registry registry_with_world(const TempDir& tmp, const std::string& name) {
    auto reg = ensure_registry(tmp.path() / "worlds.json", tmp.path() / "dashboard.db",
                               "default");
    if (name != "default") {
        (void)create_world(reg, tmp.path(), name, "", "2026-10-25T01:00:00Z");
    }
    return reg;
}

std::int64_t count_rows(const std::string& db_path, const char* sql) {
    sqlite3* raw = nullptr;
    EXPECT_EQ(sqlite3_open_v2(("file:" + db_path + "?mode=ro").c_str(), &raw,
                              SQLITE_OPEN_READONLY | SQLITE_OPEN_URI, nullptr), SQLITE_OK);
    persistence::SqliteHandle handle(raw);
    persistence::Stmt query(raw, sql);
    EXPECT_TRUE(query.step_row());
    return sqlite3_column_int64(query.raw(), 0);
}

TEST(WorldSnapshot, ProducesIntactCompactCopy) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    seed_world_db(world.db_path, "sim-1", 5);

    const auto snap = take_snapshot(reg, "sim-1", SnapshotOptions{});
    EXPECT_EQ(snap.kind, "manual");
    EXPECT_TRUE(fs::exists(snap.path));
    EXPECT_GT(snap.size_bytes, 0);
    EXPECT_EQ(snap.world_time, "2026-10-24T00:00:00Z");   // engrams MAX(created_at)
    EXPECT_EQ(fs::path(snap.path).parent_path(), fs::path(world.snapshot_dir));
    EXPECT_EQ(count_rows(snap.path, "SELECT COUNT(*) FROM engrams"), 5);
    EXPECT_EQ(count_rows(snap.path, "SELECT COUNT(*) FROM pragma_integrity_check "
                                    "WHERE integrity_check='ok'"), 1);
    // 不留 partial。
    for (const auto& entry : fs::directory_iterator(world.snapshot_dir)) {
        EXPECT_EQ(entry.path().extension(), ".db") << entry.path();
    }
    ASSERT_EQ(reg.snapshots.at("sim-1").size(), 1U);
    EXPECT_EQ(reg.snapshots.at("sim-1").front().id, snap.id);
}

TEST(WorldSnapshot, SnapshotIsIndependentOfLaterWrites) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    seed_world_db(world.db_path, "sim-1", 2);
    const auto snap = take_snapshot(reg, "sim-1", SnapshotOptions{});
    seed_world_db(world.db_path, "sim-1", 0);   // 重开库不改变行
    {
        auto adapter = persistence::SqliteAdapter::open(world.db_path);
        persistence::Stmt del(adapter->connection().raw(), "DELETE FROM engrams");
        del.step_done();
    }
    EXPECT_EQ(count_rows(world.db_path, "SELECT COUNT(*) FROM engrams"), 0);
    EXPECT_EQ(count_rows(snap.path, "SELECT COUNT(*) FROM engrams"), 2);
}

TEST(WorldSnapshot, TakenWhileWriterHoldsOpenTransaction) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    seed_world_db(world.db_path, "sim-1", 1);
    auto adapter = persistence::SqliteAdapter::open(world.db_path);
    adapter->connection().begin_immediate();
    persistence::Stmt ins(adapter->connection().raw(),
        "INSERT INTO engrams(id,tenant_id,content_hash,source_kind,ingest_policy,"
        "ingest_mode,privacy_class,retention_mode,created_at,source_item_id) "
        "VALUES('uncommitted','sim-1','hx','conversation','default','inline','normal',"
        "'audit_retain','2026-10-25T00:00:00Z','uncommitted')");
    ins.step_done();
    const auto snap = take_snapshot(reg, "sim-1", SnapshotOptions{});   // 不能报错
    adapter->connection().rollback();
    EXPECT_EQ(count_rows(snap.path, "SELECT COUNT(*) FROM engrams"), 1);   // 不含未提交行
}

TEST(WorldSnapshot, PathWithSpacesAndQuotes) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    auto& world = reg.worlds.at("sim-1");
    world.snapshot_dir = (tmp.path() / "worlds" / "sim-1" / "it's a dir").string();
    fs::create_directories(world.snapshot_dir);
    seed_world_db(world.db_path, "sim-1", 1);
    const auto snap = take_snapshot(reg, "sim-1", SnapshotOptions{});
    EXPECT_TRUE(fs::exists(snap.path));
}

TEST(WorldSnapshot, DiskGuardRefusesWithoutWriting) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    seed_world_db(world.db_path, "sim-1", 3);
    SnapshotOptions opts;
    opts.free_space = [](const fs::path&) -> std::int64_t { return 1; };
    EXPECT_EQ(code_of([&] { (void)take_snapshot(reg, "sim-1", opts); }), "insufficient_disk");
    EXPECT_TRUE(fs::is_empty(world.snapshot_dir));
    EXPECT_EQ(reg.snapshots.count("sim-1") == 0 || reg.snapshots.at("sim-1").empty(), true);
}

TEST(WorldSnapshot, UnknownWorldAndMissingDb) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    EXPECT_EQ(code_of([&] { (void)take_snapshot(reg, "nope", SnapshotOptions{}); }),
              "world_not_found");
    // 库文件还没创建（世界从未激活）：拒绝，并且不留 partial。
    EXPECT_EQ(code_of([&] { (void)take_snapshot(reg, "sim-1", SnapshotOptions{}); }),
              "snapshot_failed");
    EXPECT_TRUE(fs::is_empty(reg.worlds.at("sim-1").snapshot_dir));
}

// 保留策略不需要真实快照文件，构造注册项即可。
SnapshotEntry fake_snapshot(const fs::path& dir, const std::string& stamp,
                            const std::string& kind) {
    SnapshotEntry snap;
    snap.id = stamp;
    snap.path = (dir / (stamp + ".db")).string();
    snap.kind = kind;
    snap.reason = kind;
    snap.created_at = stamp;
    { std::ofstream out(snap.path); out << "x"; }
    return snap;
}

std::vector<std::string> ids_of(const std::vector<SnapshotEntry>& snaps) {
    std::vector<std::string> out;
    for (const auto& snap : snaps) { out.push_back(snap.id); }
    return out;
}

TEST(WorldRetention, PrefersDroppingAutoKeepsNewestAuto) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    reg.snapshot_retention = 3;
    const fs::path dir = reg.worlds.at("sim-1").snapshot_dir;
    // 列表最新在前：t5..t1
    reg.snapshots["sim-1"] = {
        fake_snapshot(dir, "t5", "manual"), fake_snapshot(dir, "t4", "auto"),
        fake_snapshot(dir, "t3", "manual"), fake_snapshot(dir, "t2", "auto"),
        fake_snapshot(dir, "t1", "manual"),
    };
    const auto removed = apply_retention(reg, "sim-1");
    // 超出 2 份：先删最旧的 auto t2；auto 只剩 t4，必须保留；再删最旧的 manual t1。
    EXPECT_EQ(removed, (std::vector<std::string>{"t2", "t1"}));
    EXPECT_EQ(ids_of(reg.snapshots.at("sim-1")), (std::vector<std::string>{"t5", "t4", "t3"}));
    EXPECT_FALSE(fs::exists(dir / "t2.db"));
    EXPECT_FALSE(fs::exists(dir / "t1.db"));
    EXPECT_TRUE(fs::exists(dir / "t4.db"));
}

TEST(WorldRetention, AllManualDropsOldest) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    reg.snapshot_retention = 2;
    const fs::path dir = reg.worlds.at("sim-1").snapshot_dir;
    reg.snapshots["sim-1"] = {fake_snapshot(dir, "t3", "manual"),
                              fake_snapshot(dir, "t2", "manual"),
                              fake_snapshot(dir, "t1", "manual")};
    EXPECT_EQ(apply_retention(reg, "sim-1"), (std::vector<std::string>{"t1"}));
    EXPECT_EQ(ids_of(reg.snapshots.at("sim-1")), (std::vector<std::string>{"t3", "t2"}));
}

// 未超限时一个都不能删。用 2 份 manual（保留 5）：若去掉「总数 <= N 不删」的守卫，
// 第一轮没有 auto 可删，第二轮会把 manual 全删掉，本用例就会失败。
// （只放一份 auto 是个空洞用例：它本身就是回滚锚点，守卫在不在都不会被删。）
TEST(WorldRetention, UnderLimitIsNoop) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const fs::path dir = reg.worlds.at("sim-1").snapshot_dir;
    reg.snapshots["sim-1"] = {fake_snapshot(dir, "t2", "manual"), fake_snapshot(dir, "t1", "manual")};
    EXPECT_TRUE(apply_retention(reg, "sim-1").empty());
    EXPECT_EQ(ids_of(reg.snapshots.at("sim-1")), (std::vector<std::string>{"t2", "t1"}));
    EXPECT_TRUE(fs::exists(dir / "t1.db"));
    EXPECT_TRUE(fs::exists(dir / "t2.db"));
}

// 恰好等于保留份数：不删（边界是 <=，不是 <）。
TEST(WorldRetention, ExactlyAtLimitIsNoop) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    reg.snapshot_retention = 3;
    const fs::path dir = reg.worlds.at("sim-1").snapshot_dir;
    reg.snapshots["sim-1"] = {fake_snapshot(dir, "t3", "manual"), fake_snapshot(dir, "t2", "auto"),
                              fake_snapshot(dir, "t1", "manual")};
    EXPECT_TRUE(apply_retention(reg, "sim-1").empty());
    EXPECT_EQ(reg.snapshots.at("sim-1").size(), 3U);
    EXPECT_TRUE(fs::exists(dir / "t1.db"));
}

TEST(WorldRetention, TakeSnapshotAppliesRetention) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    reg.snapshot_retention = 2;
    seed_world_db(reg.worlds.at("sim-1").db_path, "sim-1", 1);
    SnapshotEntry latest;
    for (int idx = 0; idx < 3; ++idx) { latest = take_snapshot(reg, "sim-1", SnapshotOptions{}); }
    EXPECT_EQ(reg.snapshots.at("sim-1").size(), 2U);
    // 新快照必须插在列表开头（最新在前）。若误用 push_back，它会成为「最旧」的那份，
    // 在修剪时被删掉：返回的条目指向已不存在的文件，且不在 front()。
    EXPECT_TRUE(fs::exists(latest.path));
    EXPECT_EQ(reg.snapshots.at("sim-1").front().id, latest.id);
    std::size_t files = 0;
    for (const auto& entry : fs::directory_iterator(reg.worlds.at("sim-1").snapshot_dir)) {
        (void)entry;
        ++files;
    }
    EXPECT_EQ(files, 2U);
}

TEST(WorldSnapshotDelete, RemovesEntryAndFile) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    seed_world_db(reg.worlds.at("sim-1").db_path, "sim-1", 1);
    const auto snap = take_snapshot(reg, "sim-1", SnapshotOptions{});
    EXPECT_EQ(code_of([&] { delete_snapshot(reg, "sim-1", "missing"); }), "snapshot_not_found");
    delete_snapshot(reg, "sim-1", snap.id);
    EXPECT_FALSE(fs::exists(snap.path));
    EXPECT_TRUE(reg.snapshots.at("sim-1").empty());
}

TEST(WorldStats, CountsTenantRowsAndHandlesMissingDb) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    const auto empty = world_stats(world.db_path, "sim-1");   // 文件不存在
    EXPECT_EQ(empty.db_bytes, 0);
    EXPECT_EQ(empty.engrams, 0);
    seed_world_db(world.db_path, "sim-1", 4);
    const auto stats = world_stats(world.db_path, "sim-1");
    EXPECT_EQ(stats.engrams, 4);
    EXPECT_EQ(stats.statements, 0);
    EXPECT_GT(stats.db_bytes, 0);
    EXPECT_GT(stats.live_bytes, 0);
    EXPECT_EQ(world_stats(world.db_path, "other").engrams, 0);   // 按租户过滤
}

// ---- W2 补充：简报之外的边界 ------------------------------------------------

void run_sql(sqlite3* handle, const char* sql) {
    char* msg = nullptr;
    const int code = sqlite3_exec(handle, sql, nullptr, nullptr, &msg);
    const std::string detail = msg != nullptr ? msg : "";
    sqlite3_free(msg);
    ASSERT_EQ(code, SQLITE_OK) << detail;
}

// 在已迁移的世界库上执行 SQL。
void exec_sql(const std::string& db_path, const char* sql) {
    auto adapter = persistence::SqliteAdapter::open(db_path);
    run_sql(adapter->connection().raw(), sql);
}

// 不经迁移，直接建一个只有手写表的「旧库」。
void exec_sql_unmigrated(const std::string& db_path, const char* sql) {
    sqlite3* raw = nullptr;
    ASSERT_EQ(sqlite3_open(db_path.c_str(), &raw), SQLITE_OK);
    const persistence::SqliteHandle handle(raw);
    run_sql(raw, sql);
}

// source_unit_meta 有非空 observed_at 时，水位取它而不是 engrams.created_at。
TEST(WorldSnapshot, WorldTimePrefersSourceUnitMetaObservedAt) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    seed_world_db(world.db_path, "sim-1", 2);   // engrams MAX(created_at) = 2026-10-21
    exec_sql(world.db_path,
             "INSERT INTO source_unit_meta(tenant_id,engram_ref,clause_id,speaker,session_id,"
             "audience_json,observed_at) VALUES('sim-1','eng-0','c0','a','s1','[]',"
             "'2031-01-02T03:04:05Z'),('sim-1','eng-1','c0','a','s1','[]',NULL),"
             "('sim-1','eng-1','c1','a','s1','[]','')");
    EXPECT_EQ(snapshot_world_time(world.db_path, "sim-1"), "2031-01-02T03:04:05Z");
    EXPECT_EQ(snapshot_world_time(world.db_path, "other"), "");   // 按租户过滤
    EXPECT_EQ(take_snapshot(reg, "sim-1", SnapshotOptions{}).world_time,
              "2031-01-02T03:04:05Z");
}

// 迁移停在 36 的库没有 source_unit_meta：不能靠 SQL 报错，要回落到 engrams。
TEST(WorldSnapshot, WorldTimeOnDbWithoutSourceUnitMetaTable) {
    const TempDir tmp;
    const std::string db_path = (tmp.path() / "legacy.db").string();
    exec_sql_unmigrated(db_path,
             "CREATE TABLE engrams(id TEXT, tenant_id TEXT, created_at TEXT);"
             "INSERT INTO engrams VALUES('a','t1','2026-01-01T00:00:00Z'),"
             "('b','t1','2026-03-01T00:00:00Z'),('c','t2','2027-01-01T00:00:00Z');");
    EXPECT_EQ(snapshot_world_time(db_path, "t1"), "2026-03-01T00:00:00Z");
    const auto stats = world_stats(db_path, "t1");   // 没有 statements 表
    EXPECT_EQ(stats.engrams, 2);
    EXPECT_EQ(stats.statements, 0);
    EXPECT_EQ(snapshot_world_time((tmp.path() / "absent.db").string(), "t1"), "");
}

// 注册表可被手改：db_path 里的 % ? # 不能被当成 URI 语法。
TEST(WorldSnapshot, DbPathWithUriSpecialCharacters) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    auto& world = reg.worlds.at("sim-1");
    const fs::path odd_dir = tmp.path() / "a#b?c%d";
    fs::create_directories(odd_dir);
    world.db_path = (odd_dir / "w%41.db").string();
    seed_world_db(world.db_path, "sim-1", 2);
    EXPECT_EQ(world_stats(world.db_path, "sim-1").engrams, 2);
    const auto snap = take_snapshot(reg, "sim-1", SnapshotOptions{});
    EXPECT_EQ(count_rows(snap.path, "SELECT COUNT(*) FROM engrams"), 2);
}

// 磁盘守卫看活数据量，不看文件大小：删表后文件大、活数据小。
TEST(WorldSnapshot, DiskGuardUsesLiveBytesNotFileSize) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    seed_world_db(world.db_path, "sim-1", 1);
    exec_sql(world.db_path,
             "CREATE TABLE junk(blob BLOB);"
             "WITH RECURSIVE seq(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM seq WHERE n<400) "
             "INSERT INTO junk SELECT zeroblob(4096) FROM seq;"
             "DROP TABLE junk;");
    const auto stats = world_stats(world.db_path, "sim-1");
    ASSERT_GT(stats.db_bytes, stats.live_bytes * 3) << "freelist 没有撑大文件";

    SnapshotOptions tight;   // 恰好 3 倍活数据量：够
    tight.free_space = [&](const fs::path&) { return 3 * stats.live_bytes; };
    const auto snap = take_snapshot(reg, "sim-1", tight);
    EXPECT_TRUE(fs::exists(snap.path));
    EXPECT_LT(snap.size_bytes, stats.db_bytes);   // 快照是紧凑的

    SnapshotOptions short_by_one;   // 少 1 字节：拒
    short_by_one.free_space = [&](const fs::path&) { return 3 * stats.live_bytes - 1; };
    EXPECT_EQ(code_of([&] { (void)take_snapshot(reg, "sim-1", short_by_one); }),
              "insufficient_disk");
    EXPECT_EQ(reg.snapshots.at("sim-1").size(), 1U);
}

// 不是 SQLite 的文件：snapshot_failed，不留 partial，不登记。
TEST(WorldSnapshot, CorruptDbFailsWithoutPartialOrEntry) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    { std::ofstream out(world.db_path); out << "this is not a sqlite database at all, nope"; }
    EXPECT_EQ(code_of([&] { (void)take_snapshot(reg, "sim-1", SnapshotOptions{}); }),
              "snapshot_failed");
    EXPECT_TRUE(fs::is_empty(world.snapshot_dir));
    EXPECT_EQ(reg.snapshots.count("sim-1"), 0U);
}

// 真实的 VACUUM 失败：库的中间几页被写坏（第 1 页完好，所以 page_count 等头部
// 信息仍可读，守卫和打开都通过），VACUUM INTO 读到坏页时报 "malformed"，并且此时
// SQLite 已经创建了 0 字节的 .partial。必须删掉它，也不能登记。
// 这是唯一真正走到 catch 里 fs::remove(partial) 的用例；上面那个「不是 SQLite 的
// 文件」在 PRAGMA page_count 就失败，partial 还没赋值，删掉清理代码它也照样通过。
TEST(WorldSnapshot, VacuumFailureLeavesNoPartialAndNoEntry) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    seed_world_db(world.db_path, "sim-1", 50);
    ASSERT_GT(fs::file_size(world.db_path), 16U * 4096U);

    {   // 第 3~10 页（0 起算偏移 2*4096 起）写入确定性的随机字节。
        std::mt19937 gen(12345);
        std::fstream file(world.db_path, std::ios::in | std::ios::out | std::ios::binary);
        ASSERT_TRUE(file.is_open());
        file.seekp(2 * 4096);
        for (int idx = 0; idx < 8 * 4096; ++idx) {
            file.put(static_cast<char>(gen() & 0xFFU));
        }
    }

    EXPECT_EQ(code_of([&] { (void)take_snapshot(reg, "sim-1", SnapshotOptions{}); }),
              "snapshot_failed");
    EXPECT_TRUE(fs::is_empty(world.snapshot_dir))
        << "VACUUM 失败后残留了文件";
    EXPECT_TRUE(reg.snapshots.count("sim-1") == 0 || reg.snapshots.at("sim-1").empty());
}

// kind 拼错不能悄悄当成 manual：保留策略只认 "auto"，会丢掉回滚锚点保护。
TEST(WorldSnapshot, RejectsUnknownKindBeforeWriting) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    seed_world_db(reg.worlds.at("sim-1").db_path, "sim-1", 1);
    for (const char* bad : {"Auto", "AUTO", "manual ", "", "scene"}) {
        SnapshotOptions opts;
        opts.kind = bad;
        EXPECT_EQ(code_of([&] { (void)take_snapshot(reg, "sim-1", opts); }),
                  "invalid_snapshot_kind") << "kind='" << bad << "'";
    }
    EXPECT_TRUE(fs::is_empty(reg.worlds.at("sim-1").snapshot_dir));
    EXPECT_EQ(reg.snapshots.count("sim-1"), 0U);
}

// 成功的快照一定返回它的条目：修剪失败（这里用自指符号链接让旧快照路径无法解析，
// 触发 ELOOP）不能把异常抛给调用方，否则新快照已落盘并登记，返回值却丢了。
TEST(WorldSnapshot, RetentionFailureStillReturnsTheNewSnapshot) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    reg.snapshot_retention = 2;
    const fs::path dir = reg.worlds.at("sim-1").snapshot_dir;
    seed_world_db(reg.worlds.at("sim-1").db_path, "sim-1", 1);

    SnapshotEntry stuck = fake_snapshot(dir, "t1", "manual");
    fs::remove(stuck.path);
    fs::create_symlink("t1.db", stuck.path);   // 指向自己
    reg.snapshots["sim-1"] = {fake_snapshot(dir, "t2", "manual"), stuck};

    SnapshotEntry snap;
    ASSERT_NO_THROW(snap = take_snapshot(reg, "sim-1", SnapshotOptions{}));
    EXPECT_TRUE(fs::exists(snap.path));
    ASSERT_EQ(reg.snapshots.at("sim-1").size(), 3U);   // 修剪没成功：暂时多一份
    EXPECT_EQ(reg.snapshots.at("sim-1").front().id, snap.id);
    // 列表与磁盘一致：卡住的那份仍登记着（没被摘掉），下次修剪会重试。
    EXPECT_EQ(reg.snapshots.at("sim-1").back().id, "t1");

    // 显式调用 apply_retention 仍然 fail loud，只是 take_snapshot 不再外抛它。
    EXPECT_EQ(code_of([&] { (void)apply_retention(reg, "sim-1"); }), "snapshot_failed");
}

// remove_within 的删除本身失败（目录不可写）时抛带 code 的 WorldStoreError，
// 不能是裸 std::filesystem::filesystem_error——HTTP 层按 code 映射。
// 注册项必须保留（文件还在盘上，不能悄悄遗弃）。
TEST(WorldSnapshotDelete, RemoveFailureIsTypedAndKeepsEntry) {
    if (::geteuid() == 0) { GTEST_SKIP() << "root 不受目录权限限制"; }
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const fs::path dir = reg.worlds.at("sim-1").snapshot_dir;
    const fs::path locked = dir / "locked-snap";
    fs::create_directories(locked);
    { std::ofstream out(locked / "inner.db"); out << "x"; }
    SnapshotEntry snap;
    snap.id = "locked";
    snap.path = locked.string();
    snap.kind = "manual";
    reg.snapshots["sim-1"].push_back(snap);

    fs::permissions(locked, fs::perms::owner_read | fs::perms::owner_exec,
                    fs::perm_options::replace);   // 去掉写权限：unlink 内部文件会 EACCES
    const std::string code = code_of([&] { delete_snapshot(reg, "sim-1", "locked"); });
    fs::permissions(locked, fs::perms::owner_all, fs::perm_options::replace);   // 让 TempDir 能清理

    EXPECT_EQ(code, "snapshot_failed");
    ASSERT_EQ(reg.snapshots.at("sim-1").size(), 1U);   // 文件还在，注册项不能摘
    EXPECT_TRUE(fs::exists(locked / "inner.db"));
}

// default 世界的快照目录由 ensure_registry 登记但不创建，首次快照要补建。
TEST(WorldSnapshot, DefaultWorldSnapshotDirCreatedOnDemand) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "default");
    const auto& world = reg.worlds.at("default");
    ASSERT_FALSE(fs::exists(world.snapshot_dir));
    seed_world_db(world.db_path, "default", 1);
    const auto snap = take_snapshot(reg, "default", SnapshotOptions{});
    EXPECT_TRUE(fs::exists(snap.path));
}

// 保留份数非法时在写任何文件之前拒绝，不能先写出快照再在修剪时才发现。
TEST(WorldSnapshot, InvalidRetentionRefusedBeforeWriting) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    seed_world_db(reg.worlds.at("sim-1").db_path, "sim-1", 1);
    reg.snapshot_retention = 1;
    EXPECT_EQ(code_of([&] { (void)take_snapshot(reg, "sim-1", SnapshotOptions{}); }),
              "invalid_retention");
    EXPECT_TRUE(fs::is_empty(reg.worlds.at("sim-1").snapshot_dir));
    EXPECT_EQ(code_of([&] { (void)apply_retention(reg, "sim-1"); }), "invalid_retention");
}

TEST(WorldSnapshot, ExplicitKindReasonAndNoteAreRecorded) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    seed_world_db(reg.worlds.at("sim-1").db_path, "sim-1", 1);
    SnapshotOptions opts;
    opts.kind = "auto";
    opts.reason = "scene_boundary";
    opts.note = "进入第二幕";
    const auto snap = take_snapshot(reg, "sim-1", opts);
    EXPECT_EQ(snap.kind, "auto");
    EXPECT_EQ(snap.reason, "scene_boundary");
    EXPECT_EQ(snap.note, "进入第二幕");
    EXPECT_EQ(snap.created_at.size(), 20U);   // 2026-10-25T01:12:00Z
    EXPECT_EQ(snap.id.size(), 21U);           // 20261025T011200Z-a1b2
}

// 全是 auto 时：只保最新的 N 份，被删的是最旧的。
TEST(WorldRetention, AllAutoDropsOldestKeepsNewest) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    reg.snapshot_retention = 2;
    const fs::path dir = reg.worlds.at("sim-1").snapshot_dir;
    reg.snapshots["sim-1"] = {fake_snapshot(dir, "t4", "auto"), fake_snapshot(dir, "t3", "auto"),
                              fake_snapshot(dir, "t2", "auto"), fake_snapshot(dir, "t1", "auto")};
    EXPECT_EQ(apply_retention(reg, "sim-1"), (std::vector<std::string>{"t1", "t2"}));
    EXPECT_EQ(ids_of(reg.snapshots.at("sim-1")), (std::vector<std::string>{"t4", "t3"}));
}

// 唯一一份 auto 是回滚锚点：manual 再多也只删 manual，宁可只剩锚点 + 最新 manual。
TEST(WorldRetention, SoleAutoSurvivesManualFlood) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    reg.snapshot_retention = 2;
    const fs::path dir = reg.worlds.at("sim-1").snapshot_dir;
    reg.snapshots["sim-1"] = {fake_snapshot(dir, "t5", "manual"), fake_snapshot(dir, "t4", "manual"),
                              fake_snapshot(dir, "t3", "manual"), fake_snapshot(dir, "t2", "manual"),
                              fake_snapshot(dir, "t1", "auto")};
    EXPECT_EQ(apply_retention(reg, "sim-1"), (std::vector<std::string>{"t2", "t3", "t4"}));
    EXPECT_EQ(ids_of(reg.snapshots.at("sim-1")), (std::vector<std::string>{"t5", "t1"}));
    EXPECT_TRUE(fs::exists(dir / "t1.db"));
}

// 被篡改的注册项指向 snapshot_dir 之外：外部文件不能被删，而且必须 fail closed——
// 摘掉注册项会让这份文件再也无法经注册表清理，页面上的快照空间统计也随之失真。
TEST(WorldSnapshotDelete, RefusesPathOutsideSnapshotDir) {
    const TempDir tmp;
    const TempDir outside;
    auto reg = registry_with_world(tmp, "sim-1");
    const fs::path victim = outside.path() / "precious.db";
    { std::ofstream out(victim); out << "x"; }
    SnapshotEntry snap;
    snap.id = "evil";
    snap.path = victim.string();
    snap.kind = "manual";
    reg.snapshots["sim-1"].push_back(snap);
    EXPECT_EQ(code_of([&] { delete_snapshot(reg, "sim-1", "evil"); }), "snapshot_failed");
    EXPECT_TRUE(fs::exists(victim));
    ASSERT_EQ(reg.snapshots.at("sim-1").size(), 1U);
    EXPECT_EQ(reg.snapshots.at("sim-1").front().id, "evil");
}

TEST(WorldSnapshotDelete, UnknownWorldAndNoSnapshotList) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    EXPECT_EQ(code_of([&] { delete_snapshot(reg, "nope", "x"); }), "world_not_found");
    EXPECT_EQ(code_of([&] { delete_snapshot(reg, "sim-1", "x"); }), "snapshot_not_found");
}


// ---- Codex 审查修复：租户不变式、注册表校验、fail closed、zvec、残留清扫 ----------

// 把注册表写成一段手写 JSON（模拟被手改的 worlds.json），返回 load 抛出的 code。
std::string load_code_of(const fs::path& reg_path, const std::string& text) {
    { std::ofstream out(reg_path); out << text; }
    return code_of([&] { (void)load_registry(reg_path); });
}

TEST(WorldTenant, ForeignTenantRowIsRefused) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    seed_world_db(world.db_path, "sim-1", 2);
    EXPECT_EQ(code_of([&] { verify_world_tenant(world.db_path, "sim-1"); }), "<no throw>");

    // 另一个租户的一行混进来（例如库被复用、注册表被改）：拒开，并点名违规的表。
    seed_world_db(world.db_path, "intruder", 0);
    exec_sql(world.db_path,
             "INSERT INTO engrams(id,tenant_id,content_hash,source_kind,ingest_policy,"
             "ingest_mode,privacy_class,retention_mode,created_at,source_item_id) "
             "VALUES('x-1','intruder','hx','conversation','default','inline','normal',"
             "'audit_retain','2026-10-25T00:00:00Z','x-1')");
    try {
        verify_world_tenant(world.db_path, "sim-1");
        ADD_FAILURE() << "foreign tenant row was accepted";
    } catch (const WorldStoreError& err) {
        EXPECT_EQ(err.code(), "world_tenant_mismatch");
        EXPECT_NE(std::string(err.what()).find("engrams"), std::string::npos) << err.what();
    }
}

TEST(WorldTenant, MissingDbPassesAndNullTenantIsIgnored) {
    const TempDir tmp;
    // 新世界首次激活：库文件还不存在，不能拒。
    EXPECT_EQ(code_of([&] {
        verify_world_tenant((tmp.path() / "absent.db").string(), "sim-1");
    }), "<no throw>");
    // tenant_id 为 NULL 的行不属于任何租户，不算违规；没有 tenant_id 列的表不参与检查。
    const std::string db_path = (tmp.path() / "legacy.db").string();
    exec_sql_unmigrated(db_path,
             "CREATE TABLE things(id TEXT, tenant_id TEXT);"
             "INSERT INTO things VALUES('a','sim-1'),('b',NULL);"
             "CREATE TABLE plain(id TEXT); INSERT INTO plain VALUES('z');");
    EXPECT_EQ(code_of([&] { verify_world_tenant(db_path, "sim-1"); }), "<no throw>");
    EXPECT_EQ(code_of([&] { verify_world_tenant(db_path, "other"); }), "world_tenant_mismatch");
}

// 每条新校验规则一个坏注册表。基线是一份合法的注册表文本，每次只改一处。
class RegistryValidation : public ::testing::Test {
protected:
    TempDir tmp;
    fs::path reg_path = tmp.path() / "worlds.json";
    std::string home = (tmp.path() / "worlds").string();

    // 合法基线：default 原地，sim-1 在 worlds/sim-1/ 下，各有一份快照。
    [[nodiscard]] std::string text(const std::string& sim_key, const std::string& sim_db,
                                   const std::string& sim_snapdir, const std::string& snap_kind,
                                   const std::string& snap_path,
                                   const std::string& snap_owner) const {
        const std::string dflt_snapdir = home + "/default/snapshots";
        return std::string(R"({"version":1,"default":"default","active":"default",)") +
               R"("snapshot_retention":5,"worlds":{)" +
               R"("default":{"tenant":"default","db_path":")" + (tmp.path() / "dashboard.db").string() +
               R"(","snapshot_dir":")" + dflt_snapdir + R"(","label":"","created_at":""},)" +
               "\"" + sim_key + R"(":{"tenant":"sim-1","db_path":")" + sim_db +
               R"(","snapshot_dir":")" + sim_snapdir + R"(","label":"","created_at":""}},)" +
               R"("snapshots":{")" + snap_owner + R"(":[{"id":"s1","path":")" + snap_path +
               R"(","kind":")" + snap_kind + R"(","reason":"manual","note":"","created_at":"",)" +
               R"("world_time":"","size_bytes":1}]}})";
    }
    [[nodiscard]] std::string good() const {
        return text("sim-1", home + "/sim-1/world.db", home + "/sim-1/snapshots", "manual",
                    home + "/sim-1/snapshots/s1.db", "sim-1");
    }
};

TEST_F(RegistryValidation, BaselineLoadsAndRoundTrips) {
    ASSERT_EQ(load_code_of(reg_path, good()), "<no throw>");
    const auto reg = load_registry(reg_path);
    EXPECT_EQ(code_of([&] { save_registry(reg_path, reg); }), "<no throw>");
}

TEST_F(RegistryValidation, RejectsInvalidWorldKey) {
    EXPECT_EQ(load_code_of(reg_path, text("Bad Name", home + "/Bad Name/world.db",
                                          home + "/Bad Name/snapshots", "manual",
                                          home + "/Bad Name/snapshots/s1.db", "Bad Name")),
              "registry_corrupt");
    EXPECT_EQ(load_code_of(reg_path, text("..", home + "/../world.db", home + "/../snapshots",
                                          "manual", home + "/../snapshots/s1.db", "..")),
              "registry_corrupt");
}

TEST_F(RegistryValidation, RejectsRelativePaths) {
    EXPECT_EQ(load_code_of(reg_path, text("sim-1", "worlds/sim-1/world.db",
                                          home + "/sim-1/snapshots", "manual",
                                          home + "/sim-1/snapshots/s1.db", "sim-1")),
              "registry_corrupt");
    EXPECT_EQ(load_code_of(reg_path, text("sim-1", home + "/sim-1/world.db", "snapshots",
                                          "manual", "snapshots/s1.db", "sim-1")),
              "registry_corrupt");
    // default 的库路径同样必须是绝对路径（它不受 worlds/ 布局约束，但也不能是相对的）。
    std::string rel_default = good();
    const std::string abs_db = (tmp.path() / "dashboard.db").string();
    rel_default.replace(rel_default.find(abs_db), abs_db.size(), "dashboard.db");
    EXPECT_EQ(load_code_of(reg_path, rel_default), "registry_corrupt");
}

TEST_F(RegistryValidation, RejectsWorldPathsOutsideItsHome) {
    const TempDir outside;
    EXPECT_EQ(load_code_of(reg_path, text("sim-1", (outside.path() / "world.db").string(),
                                          home + "/sim-1/snapshots", "manual",
                                          home + "/sim-1/snapshots/s1.db", "sim-1")),
              "registry_corrupt");
    EXPECT_EQ(load_code_of(reg_path, text("sim-1", home + "/sim-1/world.db",
                                          (outside.path() / "snaps").string(), "manual",
                                          (outside.path() / "snaps" / "s1.db").string(), "sim-1")),
              "registry_corrupt");
    // 用 .. 绕出去也不行：字面规范化之后再比。
    EXPECT_EQ(load_code_of(reg_path, text("sim-1", home + "/sim-1/../other/world.db",
                                          home + "/sim-1/snapshots", "manual",
                                          home + "/sim-1/snapshots/s1.db", "sim-1")),
              "registry_corrupt");
    // 另一个世界的目录也不算自己的家。
    EXPECT_EQ(load_code_of(reg_path, text("sim-1", home + "/sim-2/world.db",
                                          home + "/sim-1/snapshots", "manual",
                                          home + "/sim-1/snapshots/s1.db", "sim-1")),
              "registry_corrupt");
}

TEST_F(RegistryValidation, RejectsDefaultSnapshotDirOutsideItsHome) {
    // default 的库保持原地，但它的快照目录同样固定在 worlds/default/ 下：否则把它改成 "/"，
    // 删除快照 / 保留策略 / 残留清扫就能删到任意位置。
    std::string bad = good();
    const std::string dflt_snapdir = home + "/default/snapshots";
    bad.replace(bad.find(dflt_snapdir), dflt_snapdir.size(), "/");
    EXPECT_EQ(load_code_of(reg_path, bad), "registry_corrupt");
}

TEST_F(RegistryValidation, RejectsUnknownSnapshotKind) {
    EXPECT_EQ(load_code_of(reg_path, text("sim-1", home + "/sim-1/world.db",
                                          home + "/sim-1/snapshots", "Auto",
                                          home + "/sim-1/snapshots/s1.db", "sim-1")),
              "registry_corrupt");
}

TEST_F(RegistryValidation, RejectsSnapshotPathOutsideItsWorldsSnapshotDir) {
    const TempDir outside;
    EXPECT_EQ(load_code_of(reg_path, text("sim-1", home + "/sim-1/world.db",
                                          home + "/sim-1/snapshots", "manual",
                                          (outside.path() / "precious.db").string(), "sim-1")),
              "registry_corrupt");
    // 挂在别的世界的快照目录下也不行。
    EXPECT_EQ(load_code_of(reg_path, text("sim-1", home + "/sim-1/world.db",
                                          home + "/sim-1/snapshots", "manual",
                                          home + "/default/snapshots/s1.db", "sim-1")),
              "registry_corrupt");
}

TEST_F(RegistryValidation, RejectsSnapshotsOfUnregisteredWorld) {
    EXPECT_EQ(load_code_of(reg_path, text("sim-1", home + "/sim-1/world.db",
                                          home + "/sim-1/snapshots", "manual",
                                          home + "/ghost/snapshots/s1.db", "ghost")),
              "registry_corrupt");
}

TEST_F(RegistryValidation, SaveRefusesWhatLoadRejects) {
    ASSERT_EQ(load_code_of(reg_path, good()), "<no throw>");
    const std::string before = slurp(reg_path);
    auto reg = load_registry(reg_path);
    reg.snapshots.at("sim-1").front().path = "/etc/passwd";
    EXPECT_EQ(code_of([&] { save_registry(reg_path, reg); }), "registry_corrupt");
    EXPECT_EQ(slurp(reg_path), before);
}

// worlds/ 本身指向外部：加载注册表即拒（registry_corrupt）。只靠逐项比较两侧都解析
// 符号链接的话，「snapshot_dir 在 worlds/<name> 之下」会在外部成立，快照清扫、保留策略、
// 删快照就以外部目录为根（Codex 第二轮 Important 2）。保存同样拒绝。
TEST(WorldRegistry, LoadRefusesWorldsDirSymlinkedOutside) {
    const TempDir tmp;
    const TempDir outside;
    const auto reg_path = tmp.path() / "worlds.json";
    auto reg = ensure_registry(reg_path, tmp.path() / "dashboard.db", "default");
    (void)create_world(reg, tmp.path(), "sim-1", "", "2026-10-25T01:00:00Z");
    save_registry(reg_path, reg);
    fs::rename(tmp.path() / "worlds", outside.path() / "worlds");
    fs::create_directory_symlink(outside.path() / "worlds", tmp.path() / "worlds");
    EXPECT_EQ(code_of([&] { (void)load_registry(reg_path); }), "registry_corrupt");
    EXPECT_EQ(code_of([&] { save_registry(reg_path, reg); }), "registry_corrupt");
    EXPECT_TRUE(fs::exists(outside.path() / "worlds" / "sim-1"));   // 外部一个字节不动
}

// worlds/ 本身是指向外部的符号链接：解析后 worlds/<name> 落在注册表目录之外，
// 删除必须拒绝，外部一个字节都不能动，注册项保留。
TEST(WorldRegistry, DeleteRefusesWhenWorldsDirIsSymlinkOutside) {
    const TempDir tmp;
    const TempDir outside;
    const auto reg_path = tmp.path() / "worlds.json";
    auto reg = ensure_registry(reg_path, tmp.path() / "dashboard.db", "default");
    (void)create_world(reg, tmp.path(), "sim-1", "", "2026-10-25T01:00:00Z");
    fs::remove_all(tmp.path() / "worlds");
    fs::create_directories(outside.path() / "sim-1");
    { std::ofstream out(outside.path() / "sim-1" / "keep.txt"); out << "x"; }
    fs::create_directory_symlink(outside.path(), tmp.path() / "worlds");
    EXPECT_EQ(code_of([&] { delete_world(reg, tmp.path(), "sim-1"); }), "snapshot_failed");
    EXPECT_TRUE(fs::exists(outside.path() / "sim-1" / "keep.txt"));
    EXPECT_EQ(reg.worlds.count("sim-1"), 1U);
}

// 同一份注册表换一种路径写法打开（经指向注册表目录的符号链接）：布局校验必须认它合法。
// 旧实现只做字面比较，worlds.json 里写的是真实路径、注册表目录却是链接路径，于是判成越界，
// load_registry 抛 registry_corrupt，dashboard 启动即失败（/tmp 与 /private/tmp 就是这种情形）。
TEST(WorldRegistry, LoadsThroughSymlinkedRegistryDir) {
    const TempDir tmp;
    const TempDir links;
    const auto real_reg = tmp.path() / "worlds.json";
    auto reg = ensure_registry(real_reg, tmp.path() / "dashboard.db", "default");
    (void)create_world(reg, tmp.path(), "sim-1", "", "2026-10-25T01:00:00Z");
    save_registry(real_reg, reg);
    const fs::path alias = links.path() / "alias";
    fs::create_directory_symlink(tmp.path(), alias);
    EXPECT_EQ(code_of([&] { (void)load_registry(alias / "worlds.json"); }), "<no throw>");
    // 解析符号链接之后仍越界的路径照样拒绝：fallback 只放行「同一处、换了写法」。
    auto escaped = load_registry(real_reg);
    escaped.worlds.at("sim-1").snapshot_dir = (links.path() / "elsewhere").string();
    EXPECT_EQ(code_of([&] { save_registry(alias / "worlds.json", escaped); }),
              "registry_corrupt");
}

// 保留策略遇到越界的注册项：fail closed，外部文件不动，注册项保留。
TEST(WorldRetention, OutOfBoundsVictimFailsClosed) {
    const TempDir tmp;
    const TempDir outside;
    auto reg = registry_with_world(tmp, "sim-1");
    reg.snapshot_retention = 2;
    const fs::path dir = reg.worlds.at("sim-1").snapshot_dir;
    const fs::path victim = outside.path() / "precious.db";
    { std::ofstream out(victim); out << "x"; }
    SnapshotEntry evil;
    evil.id = "t1";
    evil.path = victim.string();
    evil.kind = "manual";
    reg.snapshots["sim-1"] = {fake_snapshot(dir, "t3", "manual"),
                              fake_snapshot(dir, "t2", "manual"), evil};
    EXPECT_EQ(code_of([&] { (void)apply_retention(reg, "sim-1"); }), "snapshot_failed");
    EXPECT_TRUE(fs::exists(victim));
    EXPECT_EQ(ids_of(reg.snapshots.at("sim-1")), (std::vector<std::string>{"t3", "t2", "t1"}));
}

// 注册项还在、文件已经没了（保存失败后的补偿、手工删除）：仍能删掉注册项。
TEST(WorldSnapshotDelete, EntryWithMissingFileCanBeDeleted) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    seed_world_db(reg.worlds.at("sim-1").db_path, "sim-1", 1);
    const auto snap = take_snapshot(reg, "sim-1", SnapshotOptions{});
    fs::remove(snap.path);
    delete_snapshot(reg, "sim-1", snap.id);
    EXPECT_TRUE(reg.snapshots.at("sim-1").empty());
}

// 向量不在库里的后端（zvec）：在任何文件 I/O 之前拒绝，不留文件，不登记。
TEST(WorldSnapshot, RefusesNonSqliteVectorBackendBeforeWriting) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    seed_world_db(reg.worlds.at("sim-1").db_path, "sim-1", 1);
    for (const char* backend : {"zvec", "", "SQLITE"}) {
        SnapshotOptions opts;
        opts.vector_backend = backend;
        EXPECT_EQ(code_of([&] { (void)take_snapshot(reg, "sim-1", opts); }),
                  "snapshot_unsupported_backend") << "backend='" << backend << "'";
    }
    EXPECT_TRUE(fs::is_empty(reg.worlds.at("sim-1").snapshot_dir));
    EXPECT_EQ(reg.snapshots.count("sim-1"), 0U);
    // 默认就是 sqlite：照常拍。
    EXPECT_NO_THROW((void)take_snapshot(reg, "sim-1", SnapshotOptions{}));
}

// 上次崩溃的残留：VACUUM 写到一半的 .partial，以及改名之后、存注册表之前崩溃留下的
// 未登记 .db。下一次快照先清掉它们；登记过的快照和不像快照 id 的文件一概不碰。
TEST(WorldSnapshot, SweepsCrashLeftoversBeforeSnapshotting) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    seed_world_db(reg.worlds.at("sim-1").db_path, "sim-1", 1);
    const fs::path dir = reg.worlds.at("sim-1").snapshot_dir;
    const auto kept = take_snapshot(reg, "sim-1", SnapshotOptions{});
    const fs::path partial = dir / "20260101T000000Z-dead.db.partial";
    const fs::path orphan = dir / "20260101T000000Z-beef.db";
    const fs::path foreign_db = dir / "keep.db";
    const fs::path note = dir / "notes.txt";
    for (const auto& path : {partial, orphan, foreign_db, note}) {
        std::ofstream out(path);
        out << "x";
    }
    const auto snap = take_snapshot(reg, "sim-1", SnapshotOptions{});
    EXPECT_FALSE(fs::exists(partial));
    EXPECT_FALSE(fs::exists(orphan));
    EXPECT_TRUE(fs::exists(kept.path));
    EXPECT_TRUE(fs::exists(snap.path));
    EXPECT_TRUE(fs::exists(foreign_db));
    EXPECT_TRUE(fs::exists(note));
}

// take_snapshot 成功、调用方没能存下注册表时的补偿：只删新文件，注册表（const）不动。
TEST(WorldSnapshot, DiscardSnapshotFileRemovesOnlyTheFile) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    seed_world_db(reg.worlds.at("sim-1").db_path, "sim-1", 1);
    const auto snap = take_snapshot(reg, "sim-1", SnapshotOptions{});
    discard_snapshot_file(reg, "sim-1", snap.id);
    EXPECT_FALSE(fs::exists(snap.path));
    ASSERT_EQ(reg.snapshots.at("sim-1").size(), 1U);
    EXPECT_EQ(code_of([&] { discard_snapshot_file(reg, "sim-1", "nope"); }), "snapshot_not_found");
    EXPECT_EQ(code_of([&] { discard_snapshot_file(reg, "ghost", snap.id); }), "world_not_found");

    const TempDir outside;
    const fs::path victim = outside.path() / "precious.db";
    { std::ofstream out(victim); out << "x"; }
    reg.snapshots.at("sim-1").front().path = victim.string();
    EXPECT_EQ(code_of([&] { discard_snapshot_file(reg, "sim-1", snap.id); }), "snapshot_failed");
    EXPECT_TRUE(fs::exists(victim));
}

// ---- W3：回滚（语义 A，丢掉后续）与归档 -------------------------------------
// 设计：spec §5.1 / §11；计划 docs/superpowers/plans/2026-10-26-world-w3-rollback.md Task 1。

fs::path home_of(const WorldEntry& world) { return fs::path(world.snapshot_dir).parent_path(); }
fs::path archive_dir_of(const WorldEntry& world) { return home_of(world) / "archive"; }

bool archive_is_empty(const WorldEntry& world) {
    const fs::path dir = archive_dir_of(world);
    return !fs::exists(dir) || fs::is_empty(dir);
}

// 库所在目录里回滚留下的 staging 文件（.<库文件名>.rollback-<hex>.partial 及其 -wal/-shm）。
std::vector<std::string> rollback_partials(const WorldEntry& world) {
    std::vector<std::string> out;
    for (const auto& item : fs::directory_iterator(fs::path(world.db_path).parent_path())) {
        const std::string name = item.path().filename().string();
        if (name.find(".rollback-") != std::string::npos) { out.push_back(name); }
    }
    return out;
}

// 拍一份 rows 行的快照，再追加 extra 行，返回快照。
SnapshotEntry snapshot_then_write(Registry& reg, const std::string& world, int rows, int extra) {
    const auto& entry = reg.worlds.at(world);
    seed_world_db(entry.db_path, world, rows);
    auto snap = take_snapshot(reg, world, SnapshotOptions{});
    append_engrams(entry.db_path, world, rows, extra);
    return snap;
}

std::int64_t engram_count(const std::string& db_path) {
    return count_rows(db_path, "SELECT COUNT(*) FROM engrams");
}

// 新开一条读写连接（与引擎同样按路径打开、不带 URI 参数），返回 engrams 行数和
// PRAGMA integrity_check 是否为 "ok"。
std::pair<std::int64_t, bool> open_fresh_and_check(const std::string& db_path) {
    sqlite3* raw = nullptr;
    EXPECT_EQ(sqlite3_open_v2(db_path.c_str(), &raw, SQLITE_OPEN_READWRITE, nullptr), SQLITE_OK);
    const persistence::SqliteHandle handle(raw);
    persistence::Stmt rows(raw, "SELECT COUNT(*) FROM engrams");
    const std::int64_t count = rows.step_row() ? sqlite3_column_int64(rows.raw(), 0) : -1;
    persistence::Stmt check(raw, "SELECT COUNT(*) FROM pragma_integrity_check "
                                 "WHERE integrity_check='ok'");
    const bool intact = check.step_row() && sqlite3_column_int64(check.raw(), 0) == 1;
    return {count, intact};
}

// 让快照「打得开、quick_check 通过、integrity_check 不通过」：改写一个索引的定义，使索引内容
// 与表对不上（quick_check 不比对索引内容）。只有 integrity_check 拦得住它：把校验换成
// quick_check，或者干脆不校验，用例都会失败。
void corrupt_index_definition(const std::string& db_path) {
    sqlite3* raw = nullptr;
    ASSERT_EQ(sqlite3_open(db_path.c_str(), &raw), SQLITE_OK);
    const persistence::SqliteHandle handle(raw);
    sqlite3_db_config(raw, SQLITE_DBCONFIG_DEFENSIVE, 0, nullptr);
    run_sql(raw,
            "CREATE TABLE side(aaa, bbb); CREATE INDEX side_aaa ON side(aaa);"
            "INSERT INTO side VALUES(1,10),(2,20),(3,30);"
            "PRAGMA writable_schema=ON;"
            "UPDATE sqlite_master SET sql='CREATE INDEX side_aaa ON side(bbb)' "
            "WHERE name='side_aaa';");
}

// 把目录设成只读，析构时恢复原权限：断言失败提前返回也会恢复，否则 TempDir 删不掉它。
class ReadOnlyDir {
public:
    explicit ReadOnlyDir(fs::path dir)
        : dir_(std::move(dir)), saved_(fs::status(dir_).permissions()) {
        fs::permissions(dir_, fs::perms::owner_read | fs::perms::owner_exec,
                        fs::perm_options::replace);
    }
    ~ReadOnlyDir() {
        std::error_code err;
        fs::permissions(dir_, saved_, fs::perm_options::replace, err);
    }
    ReadOnlyDir(const ReadOnlyDir&) = delete;
    ReadOnlyDir& operator=(const ReadOnlyDir&) = delete;
    ReadOnlyDir(ReadOnlyDir&&) = delete;
    ReadOnlyDir& operator=(ReadOnlyDir&&) = delete;
private:
    fs::path dir_;
    fs::perms saved_;
};

TEST(WorldRollback, RestoresSnapshotContentAndArchivesThePreviousDb) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    const auto snap = snapshot_then_write(reg, "sim-1", 2, 3);
    ASSERT_EQ(engram_count(world.db_path), 5);
    // 实测表：只读读者打开过之后会留下空的 -wal 和 32 KB 的 -shm，回滚要能处理并清掉。
    ASSERT_TRUE(fs::exists(world.db_path + "-shm"));
    ASSERT_EQ(fs::file_size(world.db_path + "-wal"), 0U);
    // 现役库收紧过权限：恢复出来的库沿用它，不随快照文件放宽。
    const auto tight = fs::perms::owner_read | fs::perms::owner_write;
    fs::permissions(world.db_path, tight, fs::perm_options::replace);
    { std::ofstream out(world.db_path + "-journal"); }   // 空的 -journal 同样属于旧库

    const auto result = rollback_world(reg, tmp.path(), "sim-1", snap.id, RollbackOptions{});
    EXPECT_EQ(fs::status(world.db_path).permissions() & fs::perms::all, tight);
    EXPECT_FALSE(fs::exists(world.db_path + "-wal"));
    EXPECT_FALSE(fs::exists(world.db_path + "-shm"));
    EXPECT_FALSE(fs::exists(world.db_path + "-journal"));
    EXPECT_EQ(engram_count(world.db_path), 2);
    EXPECT_EQ(result.restored_bytes, static_cast<std::int64_t>(fs::file_size(snap.path)));

    ASSERT_FALSE(result.archive_path.empty());
    const fs::path archived = result.archive_path;
    EXPECT_TRUE(fs::is_regular_file(archived));
    EXPECT_EQ(archived.parent_path(), archive_dir_of(world));
    EXPECT_EQ(archived.filename().string().rfind("world.db.pre-rollback-", 0), 0U) << archived;
    EXPECT_EQ(engram_count(result.archive_path), 5);   // 被替换的库原样保留
    // 归档是旧 inode 唯一剩下的名字（硬链接 + 原子替换之后），新库是另一个 inode。
    EXPECT_EQ(fs::hard_link_count(archived), 1U);
    EXPECT_EQ(fs::hard_link_count(world.db_path), 1U);

    EXPECT_TRUE(fs::exists(snap.path));   // 快照是复制出来的，不是挪走的
    EXPECT_TRUE(rollback_partials(world).empty());
    // 恢复出来的库能被引擎照常打开并写入（journal_mode 自动回到 wal）。
    append_engrams(world.db_path, "sim-1", 10, 1);
    EXPECT_EQ(engram_count(world.db_path), 3);
}

TEST(WorldRollback, RefusesCorruptSnapshotAndLeavesTargetUntouched) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    const auto snap = snapshot_then_write(reg, "sim-1", 2, 3);
    corrupt_index_definition(snap.path);
    ASSERT_EQ(count_rows(snap.path, "SELECT COUNT(*) FROM pragma_quick_check "
                                    "WHERE quick_check='ok'"), 1)
        << "要的是只有 integrity_check 拦得住的损坏";
    ASSERT_EQ(count_rows(snap.path, "SELECT COUNT(*) FROM pragma_integrity_check "
                                    "WHERE integrity_check='ok'"), 0);
    const std::string before = slurp(world.db_path);

    EXPECT_EQ(code_of([&] { (void)rollback_world(reg, tmp.path(), "sim-1", snap.id, RollbackOptions{}); }),
              "snapshot_corrupt");
    EXPECT_EQ(slurp(world.db_path), before);
    EXPECT_EQ(engram_count(world.db_path), 5);
    EXPECT_TRUE(archive_is_empty(world));
    EXPECT_TRUE(rollback_partials(world).empty());
}

TEST(WorldRollback, RefusesSnapshotThatIsNotADatabase) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    const auto snap = snapshot_then_write(reg, "sim-1", 2, 1);
    { std::ofstream out(snap.path, std::ios::trunc); out << "this is not a sqlite database, nope"; }
    const std::string before = slurp(world.db_path);
    EXPECT_EQ(code_of([&] { (void)rollback_world(reg, tmp.path(), "sim-1", snap.id, RollbackOptions{}); }),
              "snapshot_corrupt");
    EXPECT_EQ(slurp(world.db_path), before);
    EXPECT_TRUE(archive_is_empty(world));
    EXPECT_TRUE(rollback_partials(world).empty());
}

TEST(WorldRollback, RefusesMissingSnapshotFile) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    const auto snap = snapshot_then_write(reg, "sim-1", 2, 1);
    fs::remove(snap.path);
    const std::string before = slurp(world.db_path);
    EXPECT_EQ(code_of([&] { (void)rollback_world(reg, tmp.path(), "sim-1", snap.id, RollbackOptions{}); }),
              "snapshot_corrupt");
    EXPECT_EQ(slurp(world.db_path), before);
    EXPECT_TRUE(archive_is_empty(world));
    EXPECT_TRUE(rollback_partials(world).empty());
}

// 快照文件被换成指向 snapshot_dir 之外的符号链接：解析后越界，snapshot_failed，不读它。
TEST(WorldRollback, RefusesSnapshotPathEscapingSnapshotDir) {
    const TempDir tmp;
    const TempDir outside;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    const auto snap = snapshot_then_write(reg, "sim-1", 2, 1);
    const fs::path foreign = outside.path() / "foreign.db";
    fs::rename(snap.path, foreign);   // 内容完好，只是挪到了外面
    fs::create_symlink(foreign, snap.path);
    const std::string before = slurp(world.db_path);
    EXPECT_EQ(code_of([&] { (void)rollback_world(reg, tmp.path(), "sim-1", snap.id, RollbackOptions{}); }),
              "snapshot_failed");
    EXPECT_EQ(slurp(world.db_path), before);
    EXPECT_TRUE(archive_is_empty(world));
    EXPECT_TRUE(rollback_partials(world).empty());
}

TEST(WorldRollback, RefusesWhenDbDirectoryIsReadOnly) {
    if (::geteuid() == 0) { GTEST_SKIP() << "root 不受目录权限限制"; }
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    const auto snap = snapshot_then_write(reg, "sim-1", 2, 3);
    const std::string before = slurp(world.db_path);
    std::string code;
    {
        const ReadOnlyDir locked(fs::path(world.db_path).parent_path());
        code = code_of([&] { (void)rollback_world(reg, tmp.path(), "sim-1", snap.id, RollbackOptions{}); });
    }
    EXPECT_EQ(code, "snapshot_failed");
    EXPECT_EQ(slurp(world.db_path), before);
    EXPECT_EQ(engram_count(world.db_path), 5);
    EXPECT_TRUE(archive_is_empty(world));
    EXPECT_TRUE(rollback_partials(world).empty());
}

TEST(WorldRollback, RefusesForeignTenantSnapshot) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    const auto snap = snapshot_then_write(reg, "sim-1", 2, 1);
    exec_sql_unmigrated(snap.path,
             "INSERT INTO engrams(id,tenant_id,content_hash,source_kind,ingest_policy,"
             "ingest_mode,privacy_class,retention_mode,created_at,source_item_id) "
             "VALUES('x-1','intruder','hx','conversation','default','inline','normal',"
             "'audit_retain','2026-10-25T00:00:00Z','x-1')");
    const std::string before = slurp(world.db_path);
    EXPECT_EQ(code_of([&] { (void)rollback_world(reg, tmp.path(), "sim-1", snap.id, RollbackOptions{}); }),
              "world_tenant_mismatch");
    EXPECT_EQ(slurp(world.db_path), before);
    EXPECT_TRUE(archive_is_empty(world));
    EXPECT_TRUE(rollback_partials(world).empty());
}

TEST(WorldRollback, RefusesInsufficientDisk) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    const auto snap = snapshot_then_write(reg, "sim-1", 2, 1);
    const std::string before = slurp(world.db_path);
    const auto snap_bytes = static_cast<std::int64_t>(fs::file_size(snap.path));

    RollbackOptions starved;
    fs::path asked;
    starved.free_space = [&asked](const fs::path& dir) -> std::int64_t { asked = dir; return 1; };
    EXPECT_EQ(code_of([&] { (void)rollback_world(reg, tmp.path(), "sim-1", snap.id, starved); }),
              "insufficient_disk");
    EXPECT_EQ(asked, fs::path(world.db_path).parent_path());   // 问的是库所在目录
    EXPECT_EQ(slurp(world.db_path), before);
    EXPECT_TRUE(archive_is_empty(world));
    EXPECT_TRUE(rollback_partials(world).empty());

    RollbackOptions short_by_one;   // 少 1 字节：拒
    short_by_one.free_space = [snap_bytes](const fs::path&) { return 2 * snap_bytes - 1; };
    EXPECT_EQ(code_of([&] { (void)rollback_world(reg, tmp.path(), "sim-1", snap.id, short_by_one); }),
              "insufficient_disk");
    RollbackOptions exact;          // 恰好 2 倍：放行
    exact.free_space = [snap_bytes](const fs::path&) { return 2 * snap_bytes; };
    EXPECT_EQ(code_of([&] { (void)rollback_world(reg, tmp.path(), "sim-1", snap.id, exact); }), "<no throw>");
    EXPECT_EQ(engram_count(world.db_path), 2);
}

TEST(WorldRollback, RefusesNonEmptyWal) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    const auto snap = snapshot_then_write(reg, "sim-1", 2, 1);
    { std::ofstream out(world.db_path + "-wal", std::ios::trunc); out << "pending frames"; }
    const std::string before = slurp(world.db_path);
    EXPECT_EQ(code_of([&] { (void)rollback_world(reg, tmp.path(), "sim-1", snap.id, RollbackOptions{}); }),
              "snapshot_failed");
    EXPECT_EQ(slurp(world.db_path), before);
    EXPECT_EQ(slurp(world.db_path + "-wal"), "pending frames");
    EXPECT_TRUE(archive_is_empty(world));
    EXPECT_TRUE(rollback_partials(world).empty());

    // 库不在、旁边却有非空 -wal：同样拒绝，否则 SQLite 打开恢复出来的库时会重放这份 WAL。
    fs::remove(world.db_path);
    EXPECT_EQ(code_of([&] { (void)rollback_world(reg, tmp.path(), "sim-1", snap.id, RollbackOptions{}); }),
              "snapshot_failed");
    EXPECT_FALSE(fs::exists(world.db_path));
    EXPECT_TRUE(rollback_partials(world).empty());
}

// 库路径是符号链接：拒绝。对符号链接建硬链接得到什么因平台而异（macOS 的 link() 跟随链接、
// 链到目标文件；Linux 链的是符号链接本身），两种结果都不是要的归档：前者让链接目标多出一个
// 名字，后者 list / purge 认不出（跳过符号链接）。链接指向的真实库也不该被悄悄换掉。
TEST(WorldRollback, RefusesWhenDbPathIsASymlink) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    const auto snap = snapshot_then_write(reg, "sim-1", 2, 1);
    const fs::path real_db = home_of(world) / "real.db";
    for (const char* suffix : {"-wal", "-shm"}) { fs::remove(world.db_path + suffix); }
    fs::rename(world.db_path, real_db);
    fs::create_symlink(real_db, world.db_path);
    const std::string before = slurp(real_db);
    EXPECT_EQ(code_of([&] { (void)rollback_world(reg, tmp.path(), "sim-1", snap.id, RollbackOptions{}); }),
              "snapshot_failed");
    EXPECT_TRUE(fs::is_symlink(world.db_path));
    EXPECT_EQ(slurp(real_db), before);
    EXPECT_TRUE(archive_is_empty(world));
    EXPECT_TRUE(rollback_partials(world).empty());
}

TEST(WorldRollback, UnknownWorldAndSnapshot) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    EXPECT_EQ(code_of([&] { (void)rollback_world(reg, tmp.path(), "nope", "x", RollbackOptions{}); }),
              "world_not_found");
    EXPECT_EQ(code_of([&] { (void)rollback_world(reg, tmp.path(), "sim-1", "x", RollbackOptions{}); }),
              "snapshot_not_found");
    const auto snap = snapshot_then_write(reg, "sim-1", 1, 0);
    EXPECT_EQ(code_of([&] { (void)rollback_world(reg, tmp.path(), "sim-1", "x", RollbackOptions{}); }),
              "snapshot_not_found");
    // 别的世界的快照 id 不能拿来回滚这个世界。
    (void)create_world(reg, tmp.path(), "sim-2", "", "2026-10-25T01:00:00Z");
    EXPECT_EQ(code_of([&] { (void)rollback_world(reg, tmp.path(), "sim-2", snap.id, RollbackOptions{}); }),
              "snapshot_not_found");
}

TEST(WorldRollback, RestoresIntoAWorldWhoseDbDoesNotExistYet) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    const auto snap = snapshot_then_write(reg, "sim-1", 2, 0);
    for (const char* suffix : {"", "-wal", "-shm"}) { fs::remove(world.db_path + suffix); }
    ASSERT_FALSE(fs::exists(world.db_path));

    const auto result = rollback_world(reg, tmp.path(), "sim-1", snap.id, RollbackOptions{});
    EXPECT_TRUE(result.archive_path.empty());
    EXPECT_FALSE(fs::exists(archive_dir_of(world)));
    EXPECT_EQ(engram_count(world.db_path), 2);
    EXPECT_TRUE(rollback_partials(world).empty());
}

TEST(WorldRollback, RollbackDoesNotChangeTheRegistry) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto snap = snapshot_then_write(reg, "sim-1", 2, 3);
    const fs::path reg_path = tmp.path() / "worlds.json";
    save_registry(reg_path, reg);
    const std::string json_before = registry_to_json(reg);
    const std::string file_before = slurp(reg_path);

    (void)rollback_world(reg, tmp.path(), "sim-1", snap.id, RollbackOptions{});
    EXPECT_EQ(engram_count(reg.worlds.at("sim-1").db_path), 2);   // 回滚确实发生了
    EXPECT_EQ(registry_to_json(reg), json_before);
    EXPECT_EQ(slurp(reg_path), file_before);
}

// 归档名建好之后、原子替换失败：库路径上一直是完整的旧库（硬链接，不是改名挪走），
// 失败后只需摘掉归档名。两种注入：钩子直接抛异常；钩子删掉 partial，让真实的 fs::rename 失败。
TEST(WorldRollback, DbStaysInPlaceWhenReplaceFails) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    const auto snap = snapshot_then_write(reg, "sim-1", 2, 3);
    const std::string before = slurp(world.db_path);

    std::vector<std::function<void(const fs::path&)>> faults{
        [](const fs::path&) { throw std::runtime_error("injected failure before replace"); },
        [](const fs::path& staged) { fs::remove(staged); },
    };
    const std::string wal = world.db_path + "-wal";
    const std::string shm = world.db_path + "-shm";
    for (std::size_t idx = 0; idx < faults.size(); ++idx) {
        // 只读读者读一次，留下 -shm：旧库带着它进回滚（上一轮的读写连接关闭时删掉了旁车）。
        ASSERT_EQ(engram_count(world.db_path), 5) << "fault " << idx;
        ASSERT_TRUE(fs::exists(shm)) << "fault " << idx;
        RollbackOptions opts;
        bool linked = false;
        bool sidecars_gone = false;
        std::int64_t rows_at_hook = -1;
        opts.before_replace = [&](const fs::path& staged) {
            // 钩子触发时归档名已经建好（否则测不到「摘掉归档名」），库仍在原处且是旧内容。
            linked = !archive_is_empty(world) && fs::hard_link_count(world.db_path) == 2U;
            // 旁车在替换之前已删掉（C2：顺序不变）。先看这个，再读库：读库会重建它们。
            sidecars_gone = !fs::exists(wal) && !fs::exists(shm);
            rows_at_hook = fs::exists(world.db_path) ? engram_count(world.db_path) : -1;
            faults.at(idx)(staged);
        };
        EXPECT_EQ(code_of([&] { (void)rollback_world(reg, tmp.path(), "sim-1", snap.id, opts); }),
                  "snapshot_failed") << "fault " << idx;
        EXPECT_TRUE(linked) << "fault " << idx;
        EXPECT_TRUE(sidecars_gone) << "fault " << idx;
        EXPECT_EQ(rows_at_hook, 5) << "fault " << idx;
        EXPECT_EQ(slurp(world.db_path), before) << "fault " << idx;
        EXPECT_EQ(fs::hard_link_count(world.db_path), 1U) << "fault " << idx;
        EXPECT_TRUE(archive_is_empty(world)) << "fault " << idx;
        EXPECT_TRUE(rollback_partials(world).empty()) << "fault " << idx;
        // 旧库没有了原来的旁车也照常可用：新开一条读写连接，行数与 integrity_check 都对。
        const auto [rows, intact] = open_fresh_and_check(world.db_path);
        EXPECT_EQ(rows, 5) << "fault " << idx;
        EXPECT_TRUE(intact) << "fault " << idx;
    }
    EXPECT_EQ(engram_count(world.db_path), 5);
}

// 替换失败、归档名也摘不掉（archive/ 在钩子里被设成只读）：库仍完好；错误信息写明那个归档名
// 是现役库的第二个名字、不能用写连接打开。
TEST(WorldRollback, ReportsArchiveNameThatCouldNotBeRemoved) {
    if (::geteuid() == 0) { GTEST_SKIP() << "root 不受目录权限限制"; }
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    const auto snap = snapshot_then_write(reg, "sim-1", 2, 3);
    const std::string before = slurp(world.db_path);

    std::optional<ReadOnlyDir> locked;
    RollbackOptions opts;
    opts.before_replace = [&](const fs::path&) {
        locked.emplace(archive_dir_of(world));
        throw std::runtime_error("injected failure before replace");
    };
    std::string message;
    try {
        (void)rollback_world(reg, tmp.path(), "sim-1", snap.id, opts);
        ADD_FAILURE() << "rollback did not fail";
    } catch (const WorldStoreError& err) {
        EXPECT_EQ(err.code(), "snapshot_failed");
        message = err.what();
    }
    locked.reset();
    EXPECT_NE(message.find("second name of the live database"), std::string::npos) << message;
    EXPECT_EQ(slurp(world.db_path), before);
    EXPECT_EQ(fs::hard_link_count(world.db_path), 2U);   // 留下的第二个名字
    EXPECT_TRUE(rollback_partials(world).empty());
    // 它不是归档：list 不列、purge 不删（A2）；下一次回滚开头摘掉它，现役库不受影响。
    EXPECT_TRUE(list_rollback_archives(reg, tmp.path(), "sim-1").empty());
    EXPECT_EQ(purge_rollback_archives(reg, tmp.path(), "sim-1"), 0U);
    (void)rollback_world(reg, tmp.path(), "sim-1", snap.id, RollbackOptions{});
    EXPECT_EQ(engram_count(world.db_path), 2);
    EXPECT_EQ(fs::hard_link_count(world.db_path), 1U);
    EXPECT_EQ(list_rollback_archives(reg, tmp.path(), "sim-1").size(), 1U);
}

// 校验的是装上去的那份字节：快照文件在「是否存在」检查之后、复制之前被换掉（这里借第 4 步
// 的 free_space 回调换，它恰好落在两者之间），换进来的坏内容也必须被拦下，目标不动。
// 只校验快照文件本身的实现在这里会把坏内容装上去。
TEST(WorldRollback, VerifiesTheCopyNotTheSnapshotFile) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    const auto snap = snapshot_then_write(reg, "sim-1", 2, 3);
    const fs::path corrupt = tmp.path() / "corrupt.db";
    fs::copy_file(snap.path, corrupt);
    corrupt_index_definition(corrupt.string());
    const fs::path foreign = tmp.path() / "foreign.db";
    fs::copy_file(snap.path, foreign);
    exec_sql_unmigrated(foreign.string(),
             "INSERT INTO engrams(id,tenant_id,content_hash,source_kind,ingest_policy,"
             "ingest_mode,privacy_class,retention_mode,created_at,source_item_id) "
             "VALUES('x-1','intruder','hx','conversation','default','inline','normal',"
             "'audit_retain','2026-10-25T00:00:00Z','x-1')");
    const fs::path pristine = tmp.path() / "pristine.db";
    fs::copy_file(snap.path, pristine);
    const std::string before = slurp(world.db_path);

    const std::vector<std::pair<fs::path, std::string>> swaps{
        {corrupt, "snapshot_corrupt"}, {foreign, "world_tenant_mismatch"}};
    for (const auto& [replacement, expected] : swaps) {
        fs::copy_file(pristine, snap.path, fs::copy_options::overwrite_existing);
        bool swapped = false;
        RollbackOptions opts;
        opts.free_space = [&](const fs::path&) -> std::int64_t {
            fs::copy_file(replacement, snap.path, fs::copy_options::overwrite_existing);
            swapped = true;
            return std::numeric_limits<std::int64_t>::max();
        };
        EXPECT_EQ(code_of([&] { (void)rollback_world(reg, tmp.path(), "sim-1", snap.id, opts); }), expected)
            << replacement;
        EXPECT_TRUE(swapped) << replacement;
        EXPECT_EQ(slurp(world.db_path), before) << replacement;
        EXPECT_TRUE(archive_is_empty(world)) << replacement;
        EXPECT_TRUE(rollback_partials(world).empty()) << replacement;
    }
}

// 上次回滚崩溃留下的 partial：下一次回滚先清掉。只认名字严格符合
// .<库文件名>.rollback-<16 位小写 hex>.partial 的普通文件，长得像的和符号链接都不碰。
TEST(WorldRollback, SweepsStaleRollbackPartials) {
    const TempDir tmp;
    const TempDir outside;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    const auto snap = snapshot_then_write(reg, "sim-1", 2, 1);
    const fs::path dir = fs::path(world.db_path).parent_path();
    const fs::path stale = dir / ".world.db.rollback-0123456789abcdef.partial";
    const std::vector<fs::path> keep{
        dir / ".world.db.rollback-0123.partial",               // hex 太短
        // 非 hex。不用大写变体：APFS 默认不分大小写，它会和 stale 是同一个文件。
        dir / ".world.db.rollback-0123456789abcdeg.partial",
        dir / ".other.db.rollback-0123456789abcdef.partial",   // 别的库的
        dir / ".world.db.rollback-0123456789abcdef.partial.keep",
    };
    for (const auto& path : keep) { std::ofstream out(path); out << "x"; }
    { std::ofstream out(stale); out << "x"; }
    const fs::path precious = outside.path() / "precious";
    { std::ofstream out(precious); out << "x"; }
    // 名字合规，但是符号链接：不跟随、不删。
    const fs::path link = dir / ".world.db.rollback-fedcba9876543210.partial";
    fs::create_symlink(precious, link);

    (void)rollback_world(reg, tmp.path(), "sim-1", snap.id, RollbackOptions{});
    EXPECT_FALSE(fs::exists(stale));
    for (const auto& path : keep) { EXPECT_TRUE(fs::exists(path)) << path; }
    EXPECT_TRUE(fs::is_symlink(link));
    EXPECT_TRUE(fs::exists(precious));
    EXPECT_EQ(engram_count(world.db_path), 2);
}

// 热日志（-journal 非空或不是普通文件）同 -wal：SQLite 首次打开恢复出来的库时会把旧库的页
// 回滚进去，写坏新库。库不存在时同样检查。
TEST(WorldRollback, RefusesNonEmptyJournal) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    const auto snap = snapshot_then_write(reg, "sim-1", 2, 1);
    { std::ofstream out(world.db_path + "-journal", std::ios::trunc); out << "hot journal"; }
    const std::string before = slurp(world.db_path);
    EXPECT_EQ(code_of([&] { (void)rollback_world(reg, tmp.path(), "sim-1", snap.id, RollbackOptions{}); }),
              "snapshot_failed");
    EXPECT_EQ(slurp(world.db_path), before);
    EXPECT_EQ(slurp(world.db_path + "-journal"), "hot journal");
    EXPECT_TRUE(archive_is_empty(world));
    EXPECT_TRUE(rollback_partials(world).empty());

    for (const char* suffix : {"", "-wal", "-shm"}) { fs::remove(world.db_path + suffix); }
    EXPECT_EQ(code_of([&] { (void)rollback_world(reg, tmp.path(), "sim-1", snap.id, RollbackOptions{}); }),
              "snapshot_failed");
    EXPECT_FALSE(fs::exists(world.db_path));
    EXPECT_TRUE(rollback_partials(world).empty());
}

// 向量不在库里的后端（zvec）：在任何文件 I/O 之前拒绝（spec §12），与 take_snapshot 一致。
TEST(WorldRollback, RefusesNonSqliteVectorBackend) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    const auto snap = snapshot_then_write(reg, "sim-1", 2, 1);
    const std::string before = slurp(world.db_path);
    for (const char* backend : {"zvec", "", "SQLITE"}) {
        RollbackOptions opts;
        opts.vector_backend = backend;
        EXPECT_EQ(code_of([&] { (void)rollback_world(reg, tmp.path(), "sim-1", snap.id, opts); }),
                  "snapshot_unsupported_backend") << "backend='" << backend << "'";
    }
    EXPECT_EQ(slurp(world.db_path), before);
    EXPECT_TRUE(archive_is_empty(world));
    EXPECT_TRUE(rollback_partials(world).empty());
}

TEST(WorldArchives, ListsAndPurgesArchives) {
    const TempDir tmp;
    const TempDir outside;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    EXPECT_TRUE(list_rollback_archives(reg, tmp.path(), "sim-1").empty());   // archive/ 还不存在
    EXPECT_EQ(purge_rollback_archives(reg, tmp.path(), "sim-1"), 0U);

    const auto snap = snapshot_then_write(reg, "sim-1", 2, 1);
    const auto first = rollback_world(reg, tmp.path(), "sim-1", snap.id, RollbackOptions{});
    append_engrams(world.db_path, "sim-1", 2, 1);
    const auto second = rollback_world(reg, tmp.path(), "sim-1", snap.id, RollbackOptions{});
    ASSERT_NE(first.archive_path, second.archive_path);

    const fs::path dir = archive_dir_of(world);
    { std::ofstream out(dir / "keep.txt"); out << "x"; }
    const fs::path precious = outside.path() / "precious.db";
    { std::ofstream out(precious); out << "x"; }
    // 名字合规，但是符号链接：不列、不删。
    const fs::path link = dir / "world.db.pre-rollback-20260101T000000Z-beef";
    fs::create_symlink(precious, link);

    const auto listed = list_rollback_archives(reg, tmp.path(), "sim-1");
    ASSERT_EQ(listed.size(), 2U);
    EXPECT_GT(listed.at(0).name, listed.at(1).name);   // 名字降序
    std::vector<std::string> expected{fs::path(first.archive_path).filename().string(),
                                      fs::path(second.archive_path).filename().string()};
    std::ranges::sort(expected, std::greater<>());
    EXPECT_EQ(listed.at(0).name, expected.at(0));
    EXPECT_EQ(listed.at(1).name, expected.at(1));
    for (const auto& item : listed) {
        EXPECT_EQ(item.size_bytes, static_cast<std::int64_t>(fs::file_size(dir / item.name)));
    }

    EXPECT_EQ(purge_rollback_archives(reg, tmp.path(), "sim-1"), 2U);
    EXPECT_FALSE(fs::exists(first.archive_path));
    EXPECT_FALSE(fs::exists(second.archive_path));
    EXPECT_TRUE(fs::exists(dir / "keep.txt"));
    EXPECT_TRUE(fs::is_symlink(link));
    EXPECT_TRUE(fs::exists(precious));
    EXPECT_TRUE(list_rollback_archives(reg, tmp.path(), "sim-1").empty());
    EXPECT_EQ(engram_count(world.db_path), 2);   // 现役库不受清理影响
}

TEST(WorldArchives, UnknownWorld) {
    const TempDir tmp;
    const auto reg = registry_with_world(tmp, "sim-1");
    EXPECT_EQ(code_of([&] { (void)list_rollback_archives(reg, tmp.path(), "nope"); }), "world_not_found");
    EXPECT_EQ(code_of([&] { (void)purge_rollback_archives(reg, tmp.path(), "nope"); }), "world_not_found");
}

// archive/ 本身被换成指向外部的符号链接：解析后不在世界 home 之下，列出与清理都拒绝，
// 外部同名模式的文件一个字节不动（同 worlds/ 外链的 Codex 第二轮 Important 2）。
TEST(WorldArchives, RefusesArchiveDirSymlinkedOutside) {
    const TempDir tmp;
    const TempDir outside;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    const fs::path precious = outside.path() / "world.db.pre-rollback-20260101T000000Z-beef";
    { std::ofstream out(precious); out << "x"; }
    fs::create_directory_symlink(outside.path(), archive_dir_of(world));
    EXPECT_EQ(code_of([&] { (void)list_rollback_archives(reg, tmp.path(), "sim-1"); }), "snapshot_failed");
    EXPECT_EQ(code_of([&] { (void)purge_rollback_archives(reg, tmp.path(), "sim-1"); }), "snapshot_failed");
    EXPECT_TRUE(fs::exists(precious));

    // 回滚也不往外部目录里挪库：什么都不改。
    const auto snap = snapshot_then_write(reg, "sim-1", 2, 1);
    const std::string before = slurp(world.db_path);
    EXPECT_EQ(code_of([&] { (void)rollback_world(reg, tmp.path(), "sim-1", snap.id, RollbackOptions{}); }),
              "snapshot_failed");
    EXPECT_EQ(slurp(world.db_path), before);
    EXPECT_TRUE(rollback_partials(world).empty());
    std::size_t outside_files = 0;
    for (const auto& item : fs::directory_iterator(outside.path())) { (void)item; ++outside_files; }
    EXPECT_EQ(outside_files, 1U);
}

// ---- W3 最终修复轮：世界 home 只从注册表目录推出（B1）--------------------------

// 目录树里的全部条目（相对路径，不跟随符号链接），用来断言「外部目录一个字节没多、没少」。
std::vector<std::string> tree_of(const fs::path& root) {
    std::vector<std::string> out;
    for (auto it = fs::recursive_directory_iterator(root); it != fs::recursive_directory_iterator();
         ++it) {
        out.push_back(fs::relative(it->path(), root).string());
    }
    std::ranges::sort(out);
    return out;
}

fs::path world_dir_of(const TempDir& tmp, const std::string& name) {
    return tmp.path() / "worlds" / name;
}

// 审查者的构造：注册表里 snapshot_dir 写成 <外部>/snapshots，它是指回 worlds/sim-1/snapshots 的
// 符号链接。旧实现取 snapshot_dir 的字面父目录当世界 home，归档建在 <外部>/archive，purge 删掉
// 外部预先放好的同名模式文件。世界 home 现在只由注册表目录推出：归档落在 worlds/sim-1/archive，
// 外部什么都不多、什么都不少。
TEST(WorldRollback, ArchiveStaysInWorldDirWhenSnapshotDirIsASymlinkFromOutside) {
    const TempDir tmp;
    const TempDir outside;
    auto reg = registry_with_world(tmp, "sim-1");
    auto& world = reg.worlds.at("sim-1");
    const auto snap = snapshot_then_write(reg, "sim-1", 2, 3);
    const fs::path real_snaps = world_dir_of(tmp, "sim-1") / "snapshots";
    fs::create_directory_symlink(real_snaps, outside.path() / "snapshots");
    world.snapshot_dir = (outside.path() / "snapshots").string();
    reg.snapshots.at("sim-1").front().path =
        (outside.path() / "snapshots" / fs::path(snap.path).filename()).string();
    const fs::path planted =
        outside.path() / "archive" / "notes.txt.pre-rollback-20250101T000000Z-abcd";
    fs::create_directories(planted.parent_path());
    { std::ofstream out(planted); out << "precious"; }
    const auto outside_before = tree_of(outside.path());

    const auto result = rollback_world(reg, tmp.path(), "sim-1", snap.id, RollbackOptions{});
    EXPECT_EQ(engram_count(world.db_path), 2);
    EXPECT_EQ(fs::path(result.archive_path).parent_path(), world_dir_of(tmp, "sim-1") / "archive");
    EXPECT_EQ(tree_of(outside.path()), outside_before);

    const auto listed = list_rollback_archives(reg, tmp.path(), "sim-1");
    ASSERT_EQ(listed.size(), 1U);
    EXPECT_EQ(listed.front().name, fs::path(result.archive_path).filename().string());
    EXPECT_EQ(purge_rollback_archives(reg, tmp.path(), "sim-1"), 1U);
    EXPECT_FALSE(fs::exists(result.archive_path));
    EXPECT_EQ(slurp(planted), "precious");
    EXPECT_EQ(tree_of(outside.path()), outside_before);
}

// 注册表不变，worlds/sim-1/snapshots 是指到 <外部>/snaps 的符号链接。这种布局已不再支持
// （用户裁定 2026-10-27）：load_registry 报 registry_corrupt，经 WorldManager 的操作到不了这里。
// rollback_world 直接调用时仍不依赖 snapshot_dir：回滚照常成功，归档仍在 worlds/sim-1/archive；
// 外部只有原来那份快照文件。
TEST(WorldRollback, ArchiveStaysInWorldDirWhenSnapshotsDirPointsOutside) {
    const TempDir tmp;
    const TempDir outside;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    const auto snap = snapshot_then_write(reg, "sim-1", 2, 3);
    save_registry(tmp.path() / "worlds.json", reg);
    const fs::path real_snaps = world_dir_of(tmp, "sim-1") / "snapshots";
    fs::rename(real_snaps, outside.path() / "snaps");
    fs::create_directory_symlink(outside.path() / "snaps", real_snaps);
    EXPECT_EQ(code_of([&] { (void)load_registry(tmp.path() / "worlds.json"); }),
              "registry_corrupt");
    const auto outside_before = tree_of(outside.path());

    const auto result = rollback_world(reg, tmp.path(), "sim-1", snap.id, RollbackOptions{});
    EXPECT_EQ(engram_count(world.db_path), 2);
    EXPECT_EQ(fs::path(result.archive_path).parent_path(), world_dir_of(tmp, "sim-1") / "archive");
    EXPECT_TRUE(fs::is_regular_file(result.archive_path));
    EXPECT_EQ(tree_of(outside.path()), outside_before);
    EXPECT_EQ(list_rollback_archives(reg, tmp.path(), "sim-1").size(), 1U);
    EXPECT_EQ(purge_rollback_archives(reg, tmp.path(), "sim-1"), 1U);
    EXPECT_EQ(tree_of(outside.path()), outside_before);
}

// worlds/sim-1 本身是指到外部的符号链接：回滚、列出、清理都 fail closed（snapshot_failed），
// 与 delete_world 同一边界。外部的库、快照和预先放好的归档名文件一个字节都不动。
TEST(WorldArchives, RefuseWhenWorldDirIsASymlinkOutside) {
    const TempDir tmp;
    const TempDir outside;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto snap = snapshot_then_write(reg, "sim-1", 2, 3);
    const fs::path home = world_dir_of(tmp, "sim-1");
    fs::rename(home, outside.path() / "sim-1");
    fs::create_directory_symlink(outside.path() / "sim-1", home);
    const fs::path planted =
        outside.path() / "sim-1" / "archive" / "world.db.pre-rollback-20250101T000000Z-abcd";
    fs::create_directories(planted.parent_path());
    { std::ofstream out(planted); out << "precious"; }
    const auto outside_before = tree_of(outside.path());
    const std::string db_before = slurp(outside.path() / "sim-1" / "world.db");

    EXPECT_EQ(code_of([&] {
                  (void)rollback_world(reg, tmp.path(), "sim-1", snap.id, RollbackOptions{});
              }), "snapshot_failed");
    EXPECT_EQ(code_of([&] { (void)list_rollback_archives(reg, tmp.path(), "sim-1"); }),
              "snapshot_failed");
    EXPECT_EQ(code_of([&] { (void)purge_rollback_archives(reg, tmp.path(), "sim-1"); }),
              "snapshot_failed");
    EXPECT_EQ(tree_of(outside.path()), outside_before);
    EXPECT_EQ(slurp(outside.path() / "sim-1" / "world.db"), db_before);
    EXPECT_EQ(slurp(planted), "precious");
}

// ---- W3 最终修复轮：现役库的第二个名字不是归档（A2）---------------------------

// 回滚死在建硬链接之后、原子替换之前：archive 里留下一个名字合规、却和现役库是同一个 inode
// 的条目。它不是归档（内容随现役库一起变），list 不列、purge 不删；下一次成功的回滚开头摘掉它。
TEST(WorldArchives, LiveDbAliasIsNotAnArchiveAndTheNextRollbackRemovesIt) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    const auto snap = snapshot_then_write(reg, "sim-1", 2, 3);
    const fs::path archive = archive_dir_of(world);
    fs::create_directories(archive);
    const fs::path alias = archive / "world.db.pre-rollback-20260101T000000Z-abcd";
    fs::create_hard_link(world.db_path, alias);
    ASSERT_EQ(fs::hard_link_count(world.db_path), 2U);

    EXPECT_TRUE(list_rollback_archives(reg, tmp.path(), "sim-1").empty());
    EXPECT_EQ(purge_rollback_archives(reg, tmp.path(), "sim-1"), 0U);
    EXPECT_TRUE(fs::exists(alias));

    const auto result = rollback_world(reg, tmp.path(), "sim-1", snap.id, RollbackOptions{});
    EXPECT_FALSE(fs::exists(alias));
    EXPECT_EQ(engram_count(world.db_path), 2);
    EXPECT_EQ(fs::hard_link_count(world.db_path), 1U);
    EXPECT_EQ(fs::hard_link_count(result.archive_path), 1U);   // 旧库只剩真正的归档这一个名字
    const auto listed = list_rollback_archives(reg, tmp.path(), "sim-1");
    ASSERT_EQ(listed.size(), 1U);
    EXPECT_EQ(listed.front().name, fs::path(result.archive_path).filename().string());
}

// ---- W3 最终修复轮：C++ 探测别的连接（B3）与库文件头（B6）---------------------

// 打开 db_path 并读一行，连接一直开着，直到析构。mode=ro 与读写两种都要被探测到。
class OpenReader {
public:
    OpenReader(const std::string& db_path, bool read_only) {
        const std::string uri = "file:" + db_path + (read_only ? "?mode=ro" : "");
        const int flags = SQLITE_OPEN_URI | (read_only ? SQLITE_OPEN_READONLY
                                                       : SQLITE_OPEN_READWRITE);
        sqlite3* raw = nullptr;
        EXPECT_EQ(sqlite3_open_v2(uri.c_str(), &raw, flags, nullptr), SQLITE_OK);
        handle_.reset(raw);
        persistence::Stmt query(raw, "SELECT COUNT(*) FROM engrams");
        EXPECT_TRUE(query.step_row());
    }
private:
    persistence::SqliteHandle handle_;
};

TEST(WorldRollback, RefusesWhileAnotherConnectionHasTheDbOpen) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    const auto snap = snapshot_then_write(reg, "sim-1", 2, 3);
    for (const bool read_only : {true, false}) {
        const std::string before = slurp(world.db_path);
        {
            const OpenReader reader(world.db_path, read_only);
            EXPECT_EQ(code_of([&] {
                          (void)rollback_world(reg, tmp.path(), "sim-1", snap.id,
                                               RollbackOptions{});
                      }), "world_in_use") << "read_only=" << read_only;
            EXPECT_EQ(slurp(world.db_path), before) << "read_only=" << read_only;
            EXPECT_EQ(engram_count(world.db_path), 5) << "read_only=" << read_only;
            EXPECT_EQ(fs::hard_link_count(world.db_path), 1U) << "read_only=" << read_only;
            EXPECT_TRUE(archive_is_empty(world)) << "read_only=" << read_only;
            EXPECT_TRUE(rollback_partials(world).empty()) << "read_only=" << read_only;
        }
        // 连接关掉之后照常回滚。
        (void)rollback_world(reg, tmp.path(), "sim-1", snap.id, RollbackOptions{});
        EXPECT_EQ(engram_count(world.db_path), 2) << "read_only=" << read_only;
        append_engrams(world.db_path, "sim-1", 2, 3);
        ASSERT_EQ(engram_count(world.db_path), 5);
        EXPECT_EQ(purge_rollback_archives(reg, tmp.path(), "sim-1"), 1U);
    }
}

// 要被替换的不是 SQLite 库（default 世界的 db_path 不受布局约束）：拒绝，文件原样不动。空文件
// SQLite 自己会当成空库打开，只有文件头检查拦得住它。
TEST(WorldRollback, RefusesToReplaceAFileThatIsNotASqliteDatabase) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    const auto snap = snapshot_then_write(reg, "sim-1", 2, 1);
    for (const char* suffix : {"-wal", "-shm"}) { fs::remove(world.db_path + suffix); }
    for (const std::string content : {std::string("notes, not a database"), std::string()}) {
        { std::ofstream out(world.db_path, std::ios::trunc | std::ios::binary); out << content; }
        EXPECT_EQ(code_of([&] {
                      (void)rollback_world(reg, tmp.path(), "sim-1", snap.id, RollbackOptions{});
                  }), "snapshot_failed") << "content='" << content << "'";
        EXPECT_EQ(slurp(world.db_path), content);
        EXPECT_EQ(fs::hard_link_count(world.db_path), 1U);
        EXPECT_TRUE(archive_is_empty(world));
        EXPECT_TRUE(rollback_partials(world).empty());
    }
}

// ---- W3 Codex 修复轮：回滚预检（C1）与 -shm 类型（C2）-------------------------

// 预检的一个用例：一份新的注册表与世界库，break_it 把它弄坏成某一种情况，然后断言
// check_rollback 抛 expected，且整个注册表目录一个条目都没多、没少，库字节不变。
// 预检之前先放一个上次崩溃留下的 partial：预检不清扫，它必须还在。
struct PreflightCase {
    std::string label{};
    std::string world = "sim-1";
    std::string snapshot_id{};                       // 空 = 用拍好的那份快照的 id
    RollbackOptions opts{};
    // (注册表目录, 外部目录, 快照)
    std::function<void(const TempDir&, const TempDir&, const SnapshotEntry&)> break_it{};
    std::string expected{};
};

void expect_preflight(const PreflightCase& tcase) {
    const TempDir tmp;
    const TempDir outside;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto snap = snapshot_then_write(reg, "sim-1", 2, 3);
    const auto& world = reg.worlds.at("sim-1");
    const fs::path stale = fs::path(world.db_path).parent_path() /
                           ".world.db.rollback-0123456789abcdef.partial";
    { std::ofstream out(stale); out << "x"; }
    if (tcase.break_it) { tcase.break_it(tmp, outside, snap); }
    // 库可能已被挪到外部（世界目录换成符号链接）：按库路径读，slurp 跟随符号链接。
    const std::string db_before = slurp(world.db_path);
    const auto tree_before = tree_of(tmp.path());
    const auto outside_before = tree_of(outside.path());
    const std::string snapshot_id = tcase.snapshot_id.empty() ? snap.id : tcase.snapshot_id;

    EXPECT_EQ(code_of([&] { check_rollback(reg, tmp.path(), tcase.world, snapshot_id, tcase.opts); }),
              tcase.expected) << tcase.label;
    EXPECT_EQ(tree_of(tmp.path()), tree_before) << tcase.label;
    EXPECT_EQ(tree_of(outside.path()), outside_before) << tcase.label;
    EXPECT_EQ(slurp(world.db_path), db_before) << tcase.label;
    EXPECT_FALSE(fs::exists(fs::symlink_status(archive_dir_of(world)))) << tcase.label;
}

TEST(WorldRollbackCheck, RefusesEachReadOnlyCaseWithRollbackCodesAndTouchesNothing) {
    RollbackOptions zvec;
    zvec.vector_backend = "zvec";
    RollbackOptions starved;
    starved.free_space = [](const fs::path&) -> std::int64_t { return 1; };
    const std::vector<PreflightCase> cases{
        {.label = "1 unknown world", .world = "nope", .expected = "world_not_found"},
        {.label = "2 unknown snapshot", .snapshot_id = "x", .expected = "snapshot_not_found"},
        {.label = "3 backend", .opts = zvec, .expected = "snapshot_unsupported_backend"},
        {.label = "4 snapshot path escapes snapshot_dir",
         .break_it = [](const TempDir&, const TempDir& outside, const SnapshotEntry& snap) {
             const fs::path foreign = outside.path() / "foreign.db";
             fs::rename(snap.path, foreign);
             fs::create_symlink(foreign, snap.path);
         },
         .expected = "snapshot_failed"},
        {.label = "5a snapshot file missing",
         .break_it = [](const TempDir&, const TempDir&, const SnapshotEntry& snap) {
             fs::remove(snap.path);
         },
         .expected = "snapshot_corrupt"},
        {.label = "5b snapshot file is a directory",
         .break_it = [](const TempDir&, const TempDir&, const SnapshotEntry& snap) {
             fs::remove(snap.path);
             fs::create_directory(snap.path);
         },
         .expected = "snapshot_corrupt"},
        {.label = "6 world home resolves outside worlds/",
         .break_it = [](const TempDir& tmp, const TempDir& outside, const SnapshotEntry&) {
             const fs::path home = world_dir_of(tmp, "sim-1");
             fs::rename(home, outside.path() / "sim-1");
             fs::create_directory_symlink(outside.path() / "sim-1", home);
         },
         .expected = "snapshot_failed"},
        {.label = "7 insufficient disk", .opts = starved, .expected = "insufficient_disk"},
    };
    for (const auto& tcase : cases) { expect_preflight(tcase); }
}

// 预检与回滚的检查是同一份代码：顺序相同，同时有两种毛病时报的是同一个码。
TEST(WorldRollbackCheck, ReportsTheSameFirstFailureAsRollback) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto snap = snapshot_then_write(reg, "sim-1", 2, 1);
    fs::remove(snap.path);                           // 第 3 步：snapshot_corrupt
    RollbackOptions both;
    both.free_space = [](const fs::path&) -> std::int64_t { return 1; };   // 第 4 步
    EXPECT_EQ(code_of([&] { check_rollback(reg, tmp.path(), "sim-1", snap.id, both); }),
              "snapshot_corrupt");
    EXPECT_EQ(code_of([&] { (void)rollback_world(reg, tmp.path(), "sim-1", snap.id, both); }),
              "snapshot_corrupt");
    both.vector_backend = "zvec";                    // 第 1 步排在最前
    EXPECT_EQ(code_of([&] { check_rollback(reg, tmp.path(), "sim-1", snap.id, both); }),
              "snapshot_unsupported_backend");
    EXPECT_EQ(code_of([&] { (void)rollback_world(reg, tmp.path(), "sim-1", snap.id, both); }),
              "snapshot_unsupported_backend");
}

// 有效快照：预检通过，什么都不动（不清扫上次的 partial、不建 archive/、库字节不变）；之后的
// 回滚照常成功，并且由它来清扫。
TEST(WorldRollbackCheck, PassesForAValidSnapshotAndLeavesTheSweepToRollback) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    const auto snap = snapshot_then_write(reg, "sim-1", 2, 3);
    const fs::path stale = fs::path(world.db_path).parent_path() /
                           ".world.db.rollback-0123456789abcdef.partial";
    { std::ofstream out(stale); out << "x"; }
    const std::string db_before = slurp(world.db_path);
    const auto tree_before = tree_of(tmp.path());

    EXPECT_EQ(code_of([&] { check_rollback(reg, tmp.path(), "sim-1", snap.id, RollbackOptions{}); }),
              "<no throw>");
    EXPECT_EQ(tree_of(tmp.path()), tree_before);
    EXPECT_TRUE(fs::exists(stale));
    EXPECT_FALSE(fs::exists(archive_dir_of(world)));
    EXPECT_EQ(slurp(world.db_path), db_before);

    (void)rollback_world(reg, tmp.path(), "sim-1", snap.id, RollbackOptions{});
    EXPECT_FALSE(fs::exists(stale));
    EXPECT_EQ(engram_count(world.db_path), 2);
}

// -shm 存在但不是普通文件（目录、符号链接）：在动任何东西之前拒绝（snapshot_failed），目标库、
// 它旁边的 -shm 原样不动，不建归档名，不留 partial。
TEST(WorldRollback, RefusesWhenShmIsNotARegularFile) {
    const TempDir tmp;
    const TempDir outside;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    const auto snap = snapshot_then_write(reg, "sim-1", 2, 3);
    const fs::path shm = world.db_path + "-shm";
    const fs::path target = outside.path() / "elsewhere-shm";
    { std::ofstream out(target); out << "not ours"; }
    const std::vector<std::pair<std::string, std::function<void()>>> shapes{
        {"directory", [&] { fs::create_directory(shm); }},
        {"symlink", [&] { fs::create_symlink(target, shm); }},
    };
    for (const auto& [label, plant] : shapes) {
        fs::remove_all(shm);
        plant();
        const std::string before = slurp(world.db_path);
        const auto status_before = fs::symlink_status(shm).type();
        EXPECT_EQ(code_of([&] {
                      (void)rollback_world(reg, tmp.path(), "sim-1", snap.id, RollbackOptions{});
                  }), "snapshot_failed") << label;
        EXPECT_EQ(slurp(world.db_path), before) << label;
        EXPECT_EQ(fs::symlink_status(shm).type(), status_before) << label;
        EXPECT_EQ(fs::hard_link_count(world.db_path), 1U) << label;
        EXPECT_TRUE(archive_is_empty(world)) << label;
        EXPECT_TRUE(rollback_partials(world).empty()) << label;
    }
    EXPECT_EQ(slurp(target), "not ours");
    fs::remove_all(shm);
    EXPECT_EQ(engram_count(world.db_path), 5);
}

// ---- 世界管理加固 T1：布局约束在解析符号链接之后判断 -------------------------------
// 计划 docs/superpowers/plans/2026-10-27-world-hardening.md Task 1；spec §5.1 归档段、§12。
// 用户裁定（2026-10-27）：世界目录本身、非默认世界的库文件、snapshots/ 解析符号链接后都必须
// 严格位于 <注册表目录>/worlds/<名> 之下，否则 load 与 save 都报 registry_corrupt。注册表目录
// 本身可以是符号链接（LoadsThroughSymlinkedRegistryDir）。

// 把 inside 挪到 outside_dir 下同名处，原处换成指向它的符号链接。
void move_out_and_link(const fs::path& inside, const fs::path& outside_dir) {
    const fs::path moved = outside_dir / inside.filename();
    fs::rename(inside, moved);
    if (fs::is_directory(moved)) {
        fs::create_directory_symlink(moved, inside);
    } else {
        fs::create_symlink(moved, inside);
    }
}

// 已保存的注册表（default + sim-1）和一个放了一个文件的外部目录。
struct LayoutCase {
    TempDir tmp;
    TempDir outside;
    fs::path reg_path = tmp.path() / "worlds.json";
    Registry reg = registry_with_world(tmp, "sim-1");
    fs::path home = world_dir_of(tmp, "sim-1");

    LayoutCase() {
        save_registry(reg_path, reg);
        std::ofstream out(outside.path() / "keep.txt");
        out << "x";
    }
};

// 抛出的 WorldStoreError 的完整消息（不抛时为空串）。
std::string what_of(const std::function<void()>& action) {
    try { action(); } catch (const WorldStoreError& err) { return err.what(); }
    return {};
}

// 越界布局：load 与 save 都报 registry_corrupt，消息里同时有 field 与 reason，确认是预期的那条
// 规则拒的，而不是更早的某个校验恰好抛了同一个码；save 要写的是改过的注册表，原文件仍一字不变；
// 外部目录一个条目都没多、没少。field 是消息里点名的字段标签（"db_path of 'sim-1'"）；越界时
// reason 是 "resolves to"。解析出错时消息不带字段标签，field 传原路径、reason 传 "cannot resolve"。
// NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
void expect_layout_refused(const LayoutCase& lcase, const std::string& label,
                           const std::string& field, const std::string& reason = "resolves to") {
    const std::string before = slurp(lcase.reg_path);
    const auto outside_before = tree_of(lcase.outside.path());
    Registry edited = lcase.reg;
    edited.worlds.at("sim-1").label = "改过的";
    EXPECT_EQ(code_of([&] { (void)load_registry(lcase.reg_path); }), "registry_corrupt") << label;
    EXPECT_EQ(code_of([&] { save_registry(lcase.reg_path, edited); }), "registry_corrupt")
        << label;
    for (const std::string& what : {what_of([&] { (void)load_registry(lcase.reg_path); }),
                                    what_of([&] { save_registry(lcase.reg_path, edited); })}) {
        EXPECT_NE(what.find(field), std::string::npos) << label << ": " << what;
        EXPECT_NE(what.find(reason), std::string::npos) << label << ": " << what;
    }
    EXPECT_EQ(slurp(lcase.reg_path), before) << label;
    EXPECT_EQ(tree_of(lcase.outside.path()), outside_before) << label;
}

TEST(WorldLayout, RefusesSnapshotsDirResolvingOutsideTheWorldDir) {
    const LayoutCase lcase;
    move_out_and_link(lcase.home / "snapshots", lcase.outside.path());
    expect_layout_refused(lcase, "snapshots/ -> outside", "snapshot_dir of 'sim-1'");
}

TEST(WorldLayout, RefusesWorldDirResolvingOutside) {
    const LayoutCase lcase;
    move_out_and_link(lcase.home, lcase.outside.path());
    expect_layout_refused(lcase, "worlds/sim-1 -> outside", "home of 'sim-1'");
}

TEST(WorldLayout, RefusesWorldDbResolvingOutside) {
    const LayoutCase lcase;
    const fs::path foreign = lcase.outside.path() / "world.db";
    { std::ofstream out(foreign); out << "x"; }
    fs::create_symlink(foreign, lcase.reg.worlds.at("sim-1").db_path);
    expect_layout_refused(lcase, "world.db -> outside", "db_path of 'sim-1'");
}

// weakly_canonical 不解析悬空的符号链接（目标不存在时当成普通的不存在路径），而 SQLite 以
// O_CREAT 打开它会在链接目标处建库：世界库就会建到世界目录之外。
TEST(WorldLayout, RefusesDanglingWorldDbLink) {
    const LayoutCase lcase;
    fs::create_symlink(lcase.outside.path() / "later.db", lcase.reg.worlds.at("sim-1").db_path);
    expect_layout_refused(lcase, "world.db -> missing file outside", "db_path of 'sim-1'");
}

// 同上，悬空的 snapshots/ 链接，但注册表里的 snapshot_dir 以 "/" 或 "/." 结尾：lstat("链接/") 会跟随
// 链接，把链接本身藏起来，字面结果就放行了；所以规则先去掉末尾的分隔符再判断，不取决于注册表里的
// 写法。（mkdir("链接/") 在 macOS 上会在链接目标处建目录，但创建快照目录时走不走得到这一步取决于
// 实现，这里不以它为依据。）
TEST(WorldLayout, RefusesDanglingSnapshotsLinkBehindTrailingSlash) {
    for (const std::string suffix : {"/", "/."}) {
        LayoutCase lcase;
        auto& world = lcase.reg.worlds.at("sim-1");
        world.snapshot_dir += suffix;
        save_registry(lcase.reg_path, lcase.reg);
        const fs::path snaps = lcase.home / "snapshots";
        fs::remove(snaps);
        fs::create_directory_symlink(lcase.outside.path() / "later", snaps);
        expect_layout_refused(lcase, "snapshot_dir '" + world.snapshot_dir + "'",
                              "snapshot_dir of 'sim-1'");
    }
}

// 解析本身出错（自指符号链接，ELOOP）：证明不了在世界目录里，按越界拒绝，消息带上原因。
TEST(WorldLayout, RefusesPathThatCannotBeResolved) {
    const LayoutCase lcase;
    const fs::path snaps = lcase.home / "snapshots";
    fs::remove(snaps);
    fs::create_symlink("snapshots", snaps);   // 指向自己
    expect_layout_refused(lcase, "snapshots/ -> itself", snaps.string(), "cannot resolve");
    try {
        (void)load_registry(lcase.reg_path);
        ADD_FAILURE() << "load_registry did not throw";
    } catch (const WorldStoreError& err) {
        const std::string what = err.what();
        EXPECT_NE(what.find("cannot resolve " + snaps.string()), std::string::npos) << what;
    }
}

// snapshots/ 指向同一世界目录里的另一个子目录：解析后仍在世界目录之下，放行。
TEST(WorldLayout, AllowsSnapshotsDirLinkedWithinTheWorldDir) {
    const LayoutCase lcase;
    const fs::path snaps = lcase.home / "snapshots";
    fs::rename(snaps, lcase.home / "store");
    fs::create_directory_symlink(lcase.home / "store", snaps);
    EXPECT_EQ(code_of([&] { (void)load_registry(lcase.reg_path); }), "<no throw>");
    EXPECT_EQ(code_of([&] { save_registry(lcase.reg_path, lcase.reg); }), "<no throw>");
}

// 世界目录还不存在（未建目录的世界）：照常放行，不特判。
TEST(WorldLayout, AllowsWorldDirThatDoesNotExistYet) {
    const LayoutCase lcase;
    fs::remove_all(lcase.home);
    EXPECT_EQ(code_of([&] { (void)load_registry(lcase.reg_path); }), "<no throw>");
    EXPECT_EQ(code_of([&] { save_registry(lcase.reg_path, lcase.reg); }), "<no throw>");
}

// 同上，但 snapshots/ 是相对链接（ln -s store snapshots）：相对于链接所在的世界目录解析，放行。
TEST(WorldLayout, AllowsSnapshotsDirRelativeLinkWithinTheWorldDir) {
    const LayoutCase lcase;
    const fs::path snaps = lcase.home / "snapshots";
    fs::rename(snaps, lcase.home / "store");
    fs::create_directory_symlink("store", snaps);
    EXPECT_EQ(code_of([&] { (void)load_registry(lcase.reg_path); }), "<no throw>");
    EXPECT_EQ(code_of([&] { save_registry(lcase.reg_path, lcase.reg); }), "<no throw>");
}

// ---- 最终修复轮 A1：世界目录解析后必须恰好是 worlds/<它自己的名字> --------------------------
// worlds/sim-1 -> worlds/sim-2 时 sim-1 的目录解析后仍严格在 worlds/ 之下，旧规则放行；随后
// delete_world("sim-1") 经 remove_within 解析到 sim-2，把兄弟世界的整个目录和库删掉。

// 目录树里每个条目的相对路径和内容（普通文件取字节，其余记类型），用来断言「一个字节都没变」。
std::vector<std::pair<std::string, std::string>> contents_of(const fs::path& root) {
    std::vector<std::pair<std::string, std::string>> out;
    for (const auto& rel : tree_of(root)) {
        const fs::path entry = root / rel;
        const auto type = fs::symlink_status(entry).type();
        std::string body = "<type " + std::to_string(static_cast<int>(type)) + ">";
        if (type == fs::file_type::regular) { body = slurp(entry); }
        out.emplace_back(rel, std::move(body));
    }
    return out;
}

// LayoutCase 再登记一个 sim-2，库里放上数据、快照目录里放一个文件。
fs::path add_populated_sibling(LayoutCase& lcase) {
    (void)create_world(lcase.reg, lcase.tmp.path(), "sim-2", "", "2026-10-25T01:00:00Z");
    save_registry(lcase.reg_path, lcase.reg);
    const auto& sibling = lcase.reg.worlds.at("sim-2");
    seed_world_db(sibling.db_path, "sim-2", 3);
    { std::ofstream out(fs::path(sibling.snapshot_dir) / "keep.db"); out << "snap"; }
    return world_dir_of(lcase.tmp, "sim-2");
}

TEST(WorldLayout, RefusesWorldDirAliasedToASiblingWorldDir) {
    LayoutCase lcase;
    const fs::path sibling = add_populated_sibling(lcase);
    fs::remove_all(lcase.home);
    fs::create_directory_symlink(sibling, lcase.home);
    const auto sibling_before = contents_of(sibling);
    expect_layout_refused(lcase, "worlds/sim-1 -> worlds/sim-2", "home of 'sim-1'");
    EXPECT_EQ(contents_of(sibling), sibling_before);
    EXPECT_EQ(engram_count(lcase.reg.worlds.at("sim-2").db_path), 3);
}

TEST(WorldLayout, RefusesWorldDirAliasedIntoASiblingWorldDir) {
    LayoutCase lcase;
    const fs::path sibling = add_populated_sibling(lcase);
    fs::create_directories(sibling / "sub");
    fs::remove_all(lcase.home);
    fs::create_directory_symlink(sibling / "sub", lcase.home);
    const auto sibling_before = contents_of(sibling);
    expect_layout_refused(lcase, "worlds/sim-1 -> worlds/sim-2/sub", "home of 'sim-1'");
    EXPECT_EQ(contents_of(sibling), sibling_before);
}

// 全新注册表：ensure_registry 时 worlds/ 还不存在，create_world 再建出世界目录，存、读都放行。
TEST(WorldLayout, AllowsFreshRegistryThenCreateWorld) {
    const TempDir tmp;
    const fs::path reg_path = tmp.path() / "worlds.json";
    auto reg = ensure_registry(reg_path, tmp.path() / "dashboard.db", "default");
    EXPECT_EQ(code_of([&] { (void)load_registry(reg_path); }), "<no throw>");
    (void)create_world(reg, tmp.path(), "sim-1", "", "2026-10-25T01:00:00Z");
    EXPECT_EQ(code_of([&] { save_registry(reg_path, reg); }), "<no throw>");
    EXPECT_EQ(code_of([&] { (void)load_registry(reg_path); }), "<no throw>");
}

// worlds/ 整体是指向注册表目录内另一处的符号链接：两侧都解析，世界目录解析后仍是
// 「解析后的 worlds/」/<名>，放行。
TEST(WorldLayout, AllowsWorldsRootLinkedWithinTheRegistryDir) {
    const TempDir tmp;
    const fs::path reg_path = tmp.path() / "worlds.json";
    fs::create_directories(tmp.path() / "store");
    fs::create_directory_symlink(tmp.path() / "store", tmp.path() / "worlds");
    auto reg = ensure_registry(reg_path, tmp.path() / "dashboard.db", "default");
    (void)create_world(reg, tmp.path(), "sim-1", "", "2026-10-25T01:00:00Z");
    EXPECT_EQ(code_of([&] { save_registry(reg_path, reg); }), "<no throw>");
    EXPECT_EQ(code_of([&] { (void)load_registry(reg_path); }), "<no throw>");
    EXPECT_TRUE(fs::is_directory(tmp.path() / "store" / "sim-1"));
}

}  // namespace
}  // namespace starling::governance

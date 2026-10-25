// test_world_store.cpp — 世界注册表（W1）与快照（W2）。
// 设计：docs/superpowers/specs/2026-10-25-world-scene-management-design.md §3/§4。

#include "starling/governance/world_store.hpp"

#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/stmt.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <unistd.h>

#include <atomic>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iterator>
#include <random>
#include <string>
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
    snap.path = (tmp.path() / "x.db").string();
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

// worlds/<name> 若是指向外部的符号链接，remove_within 解析后发现越界，什么都不删。
TEST(WorldRegistry, DeleteRefusesSymlinkEscapingRegistryDir) {
    const TempDir tmp;
    const TempDir outside;
    const auto reg_path = tmp.path() / "worlds.json";
    auto reg = ensure_registry(reg_path, tmp.path() / "dashboard.db", "default");
    (void)create_world(reg, tmp.path(), "sim-1", "", "2026-10-25T01:00:00Z");
    fs::remove_all(tmp.path() / "worlds" / "sim-1");
    fs::create_directory_symlink(outside.path(), tmp.path() / "worlds" / "sim-1");
    { std::ofstream out(outside.path() / "keep.txt"); out << "x"; }
    delete_world(reg, tmp.path(), "sim-1");
    EXPECT_TRUE(fs::exists(outside.path() / "keep.txt"));
    EXPECT_EQ(reg.worlds.count("sim-1"), 0U);
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

// 用真实迁移建一个有数据的世界库，保证快照测的是 Starling 真实的 schema。
void seed_world_db(const fs::path& db_path, const std::string& tenant, int engram_rows) {
    auto adapter = persistence::SqliteAdapter::open(db_path);
    auto& conn = adapter->connection();
    for (int idx = 0; idx < engram_rows; ++idx) {
        // source_item_id 必须各不相同：idx_engrams_source_identity 是
        // (tenant_id, adapter_name, source_item_id, source_version, chunk_index) 唯一索引，
        // 只填必填列时后四列全是默认值 ''/0，第二行就会撞唯一约束（已实测）。
        persistence::Stmt ins(conn.raw(),
            "INSERT INTO engrams(id,tenant_id,content_hash,source_kind,ingest_policy,"
            "ingest_mode,privacy_class,retention_mode,created_at,source_item_id) "
            "VALUES(?1,?2,?3,'conversation','default','inline','normal','audit_retain',?4,?1)");
        ins.bind("eng-" + std::to_string(idx), tenant, "h" + std::to_string(idx),
                 "2026-10-2" + std::to_string(idx % 5) + "T00:00:00Z");
        ins.step_done();
    }
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

// 被篡改的注册项指向 snapshot_dir 之外：外部文件不能被删。
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
    delete_snapshot(reg, "sim-1", "evil");
    EXPECT_TRUE(fs::exists(victim));
    EXPECT_TRUE(reg.snapshots.at("sim-1").empty());
}

TEST(WorldSnapshotDelete, UnknownWorldAndNoSnapshotList) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    EXPECT_EQ(code_of([&] { delete_snapshot(reg, "nope", "x"); }), "world_not_found");
    EXPECT_EQ(code_of([&] { delete_snapshot(reg, "sim-1", "x"); }), "snapshot_not_found");
}

}  // namespace
}  // namespace starling::governance

// test_world_store.cpp — 世界注册表（W1）与快照（W2）。
// 设计：docs/superpowers/specs/2026-10-25-world-scene-management-design.md §3/§4。

#include "starling/governance/world_store.hpp"

#include <gtest/gtest.h>

#include <unistd.h>

#include <atomic>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iterator>
#include <string>

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

}  // namespace
}  // namespace starling::governance

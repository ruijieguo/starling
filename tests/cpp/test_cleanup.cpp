// 自动清理（spec §9，第 6 期，裁定 R56）：选世界的规则、跳过与重新核对、删除顺序与清理记录、注册表 v1→v2。
// 时间一律注入（kNow），不读墙钟。
#include "starling/governance/cleanup.hpp"
#include "starling/governance/registry_db.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>
#include <unistd.h>

#include <algorithm>
#include <atomic>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <functional>
#include <set>
#include <string>
#include <vector>

namespace {

namespace fs = std::filesystem;
using namespace starling::governance;

class TempDir {
public:
    TempDir() {
        static std::atomic<int> counter{0};
        path_ = fs::temp_directory_path() / ("starling_cleanup_" + std::to_string(::getpid()) + "_" +
                                             std::to_string(counter.fetch_add(1)));
        fs::remove_all(path_);
        fs::create_directories(path_);
    }
    ~TempDir() { std::error_code err; fs::remove_all(path_, err); }
    TempDir(const TempDir&) = delete;
    TempDir& operator=(const TempDir&) = delete;
    [[nodiscard]] const fs::path& path() const { return path_; }
private:
    fs::path path_;
};

std::string code_of(const std::function<void()>& action) {
    try { action(); } catch (const WorldStoreError& err) { return err.code(); }
    return "<no throw>";
}

RegistryDb open_db(const TempDir& tmp) {
    return RegistryDb::open(tmp.path(), tmp.path() / "dashboard.db", "default");
}

void sql_exec(const fs::path& db_file, const std::string& sql) {
    sqlite3* raw = nullptr;
    ASSERT_EQ(sqlite3_open(db_file.string().c_str(), &raw), SQLITE_OK);
    char* err = nullptr;
    const int rc = sqlite3_exec(raw, sql.c_str(), nullptr, nullptr, &err);
    const std::string message = err == nullptr ? std::string() : std::string(err);
    if (err != nullptr) { sqlite3_free(err); }
    sqlite3_close(raw);
    ASSERT_EQ(rc, SQLITE_OK) << message;
}

constexpr const char* kNow = "2026-11-20T00:00:00Z";
constexpr const char* kFresh = "2026-11-19T00:00:00Z";      // 1 天前
constexpr const char* kStale = "2026-11-01T00:00:00Z";      // 19 天前
constexpr const char* kEdge = "2026-11-06T00:00:00Z";       // 恰好 14 天前：不算超过
constexpr const char* kPastEdge = "2026-11-05T23:59:59Z";   // 14 天零 1 秒前

// 第 index 个世界的 created_at：2026-11-10T00:00:00Z 起每个世界晚 1 分钟（都在 14 天之内）。
std::string minute_stamp(int index) {
    const int hour = index / 60;
    const int minute = index % 60;
    std::string out = "2026-11-10T";
    out += static_cast<char>('0' + (hour / 10));
    out += static_cast<char>('0' + (hour % 10));
    out += ':';
    out += static_cast<char>('0' + (minute / 10));
    out += static_cast<char>('0' + (minute % 10));
    out += ":00Z";
    return out;
}

WorldRecord reclaimable(RegistryDb& reg, const std::string& name, const std::string& group,
                        const std::string& created_at) {
    return reg.create(name, "", {}, "{}", created_at,
                      WorldFlags{.reclaimable = true, .retention_group = group});
}

std::vector<std::string> names_of(const std::vector<CleanupCandidate>& items) {
    std::vector<std::string> out;
    for (const auto& item : items) { out.push_back(item.world); }
    return out;
}

std::vector<std::string> skip_names(const std::vector<CleanupSkip>& items) {
    std::vector<std::string> out;
    for (const auto& item : items) { out.push_back(item.world); }
    return out;
}

const CleanupCandidate* find_candidate(const CleanupPlan& plan, const std::string& world) {
    const auto pos = std::ranges::find(plan.remove, world, &CleanupCandidate::world);
    return pos == plan.remove.end() ? nullptr : &*pos;
}

void put_held(RegistryDb& reg, const std::string& world, const std::string& snapshot_id) {
    const auto rec = reg.get(world);
    SnapshotEntry snap;
    snap.id = snapshot_id;
    snap.path = (fs::path(rec.snapshot_dir) / (snapshot_id + ".db")).string();
    snap.kind = "held";
    snap.reason = "held";
    snap.created_at = kFresh;
    reg.put_snapshot(world, snap);
}

fs::path archive_dir(const RegistryDb& reg, const std::string& world) {
    return reg.data_dir() / "worlds" / reg.get(world).dir_id / "archive";
}

fs::path put_archive(const RegistryDb& reg, const std::string& world, const std::string& stamp) {
    const fs::path dir = archive_dir(reg, world);
    fs::create_directories(dir);
    const fs::path file = dir / ("world.db.pre-rollback-" + stamp + "-abcd");
    std::ofstream(file) << "old library";
    return file;
}

}  // namespace

// ---- plan_cleanup：选世界的规则 ----

TEST(Cleanup, KeepsNewest200PerGroup) {
    const TempDir tmp;
    auto reg = open_db(tmp);
    for (int index = 0; index < 205; ++index) {
        reclaimable(reg, "run1-w" + std::to_string(index), "run1", minute_stamp(index));
    }
    reclaimable(reg, "run2-only", "run2", minute_stamp(0));   // 别的分组只有 1 个：不受影响
    const auto plan = plan_cleanup(reg, CleanupConfig{}, kNow, {});
    ASSERT_EQ(plan.remove.size(), 5U);
    for (int index = 0; index < 5; ++index) {
        const auto& item = plan.remove.at(static_cast<std::size_t>(index));
        EXPECT_EQ(item.world, "run1-w" + std::to_string(index));   // 最旧的 5 个，按登记顺序
        EXPECT_EQ(item.group, "run1");
        EXPECT_EQ(item.reason, "over_count");
        EXPECT_EQ(item.dir_id, reg.get(item.world).dir_id);
    }
    EXPECT_TRUE(plan.skip.empty());
    EXPECT_TRUE(plan.archives.empty());
}

// created_at 相同时后登记的算更新（与快照「最新」同一口径）。
TEST(Cleanup, CountRuleBreaksCreatedAtTiesByRegistrationOrder) {
    const TempDir tmp;
    auto reg = open_db(tmp);
    reclaimable(reg, "first", "g", kFresh);
    reclaimable(reg, "second", "g", kFresh);
    reclaimable(reg, "third", "g", kFresh);
    const auto plan = plan_cleanup(reg, CleanupConfig{.keep_per_group = 2}, kNow, {});
    EXPECT_EQ(names_of(plan.remove), std::vector<std::string>{"first"});
}

TEST(Cleanup, DropsOlderThan14Days) {
    const TempDir tmp;
    auto reg = open_db(tmp);
    reclaimable(reg, "stale", "g", kStale);
    reclaimable(reg, "past-edge", "g", kPastEdge);
    reclaimable(reg, "edge", "g", kEdge);         // 恰好 14 天：留
    reclaimable(reg, "fresh", "g", kFresh);
    reclaimable(reg, "stale-nogroup", "", kStale);   // 空分组照样套天数规则
    const auto plan = plan_cleanup(reg, CleanupConfig{}, kNow, {});
    EXPECT_EQ(names_of(plan.remove),
              (std::vector<std::string>{"stale", "past-edge", "stale-nogroup"}));
    for (const auto& item : plan.remove) { EXPECT_EQ(item.reason, "over_age") << item.world; }
    const auto* loose = find_candidate(plan, "stale-nogroup");
    ASSERT_NE(loose, nullptr);
    EXPECT_EQ(loose->group, "");
    // 天数可调。
    const auto lenient = plan_cleanup(reg, CleanupConfig{.max_age_days = 30}, kNow, {});
    EXPECT_TRUE(lenient.remove.empty());
}

// 两条都满足时记 over_age。
TEST(Cleanup, OverAgeWinsWhenBothRulesApply) {
    const TempDir tmp;
    auto reg = open_db(tmp);
    reclaimable(reg, "old", "g", kStale);
    reclaimable(reg, "new", "g", kFresh);
    const auto plan = plan_cleanup(reg, CleanupConfig{.keep_per_group = 1}, kNow, {});
    ASSERT_EQ(names_of(plan.remove), std::vector<std::string>{"old"});
    EXPECT_EQ(plan.remove.front().reason, "over_age");
}

// 裁定 R56 Q2：retention_group 为空的世界不套份数规则（不当成同一组）。
TEST(Cleanup, EmptyGroupIsNotACountGroup) {
    const TempDir tmp;
    auto reg = open_db(tmp);
    for (int index = 0; index < 4; ++index) {
        reclaimable(reg, "loose-" + std::to_string(index), "", minute_stamp(index));
    }
    const auto plan = plan_cleanup(reg, CleanupConfig{.keep_per_group = 1}, kNow, {});
    EXPECT_TRUE(plan.remove.empty());
    EXPECT_TRUE(plan.skip.empty());
}

TEST(Cleanup, NeverTouchesNonReclaimableSeedDefault) {
    const TempDir tmp;
    {
        auto reg = open_db(tmp);
        // 都很旧、同一分组，份数只留 1：只有可回收的普通世界会被选中。
        reg.create("deploy", "", {}, "{}", kStale, WorldFlags{.retention_group = "g"});
        reg.create("seed", "", {}, "{}", kStale,
                   WorldFlags{.seed = true, .reclaimable = true, .retention_group = "g"});
        reg.create("frozen", "", {}, "{}", kStale,
                   WorldFlags{.read_only = true, .retention_group = "g"});
        reclaimable(reg, "rollout-old", "g", kStale);
        reclaimable(reg, "rollout-new", "g", kFresh);
    }
    // 默认世界也改成很旧，并手工标成可回收（手改过的库）：仍不碰。
    sql_exec(tmp.path() / "registry.db",
             "UPDATE worlds SET created_at='2026-01-01T00:00:00Z', reclaimable=1, "
             "retention_group='g' WHERE name='default'");
    auto reg = open_db(tmp);
    const auto plan = plan_cleanup(reg, CleanupConfig{.keep_per_group = 1}, kNow,
                                   {"deploy", "seed", "default"});
    EXPECT_EQ(names_of(plan.remove), std::vector<std::string>{"rollout-old"});
    EXPECT_TRUE(plan.skip.empty());   // 不在候选里的世界也不出现在跳过里
    // 不可回收、种子不占可回收世界的份数：rollout-new 是组里唯一的可回收世界，留。
    EXPECT_EQ(find_candidate(plan, "rollout-new"), nullptr);
    EXPECT_FALSE(cleanup_eligible(reg.get("seed"), false));
    EXPECT_FALSE(cleanup_eligible(reg.get("deploy"), false));
    EXPECT_FALSE(cleanup_eligible(reg.get("default"), true));
    EXPECT_TRUE(cleanup_eligible(reg.get("rollout-new"), false));
}

TEST(Cleanup, PlanSkipsWorldWithHeldSnapshot) {
    const TempDir tmp;
    auto reg = open_db(tmp);
    reclaimable(reg, "kept-by-rise", "g", kStale);
    reclaimable(reg, "plain-old", "g", kStale);
    put_held(reg, "kept-by-rise", "20261119T000000Z-aaaa");
    // manual / auto 快照不算持有。
    SnapshotEntry manual;
    manual.id = "20261119T000000Z-bbbb";
    manual.path = (fs::path(reg.get("plain-old").snapshot_dir) / (manual.id + ".db")).string();
    manual.kind = "manual";
    manual.reason = "manual";
    manual.created_at = kFresh;
    reg.put_snapshot("plain-old", manual);
    // 既持有又开着：记 held_snapshot。
    const auto plan = plan_cleanup(reg, CleanupConfig{}, kNow, {"kept-by-rise"});
    EXPECT_EQ(names_of(plan.remove), std::vector<std::string>{"plain-old"});
    ASSERT_EQ(plan.skip.size(), 1U);
    EXPECT_EQ(plan.skip.front().world, "kept-by-rise");
    EXPECT_EQ(plan.skip.front().reason, "held_snapshot");
    EXPECT_EQ(plan.skip.front().group, "g");
}

TEST(Cleanup, SkipsOpenWorlds) {
    const TempDir tmp;
    auto reg = open_db(tmp);
    reclaimable(reg, "open-old", "g", kStale);
    reclaimable(reg, "closed-old", "g", kStale);
    const auto plan = plan_cleanup(reg, CleanupConfig{}, kNow, {"open-old", "not-a-world"});
    EXPECT_EQ(names_of(plan.remove), std::vector<std::string>{"closed-old"});
    ASSERT_EQ(plan.skip.size(), 1U);
    EXPECT_EQ(plan.skip.front().world, "open-old");
    EXPECT_EQ(plan.skip.front().reason, "open");
}

// 裁定 R56 Q3：被保护的世界照样占份数名额，不往前多删更新的世界来补。
TEST(Cleanup, ProtectedWorldsKeepTheirSlotInTheCount) {
    const TempDir tmp;
    auto reg = open_db(tmp);
    for (int index = 0; index < 5; ++index) {
        reclaimable(reg, "w" + std::to_string(index), "g", minute_stamp(index));
    }
    put_held(reg, "w0", "20261119T000000Z-aaaa");
    const auto plan = plan_cleanup(reg, CleanupConfig{.keep_per_group = 3}, kNow, {"w1"});
    EXPECT_TRUE(plan.remove.empty());
    ASSERT_EQ(skip_names(plan.skip), (std::vector<std::string>{"w0", "w1"}));
    EXPECT_EQ(plan.skip.at(0).reason, "held_snapshot");
    EXPECT_EQ(plan.skip.at(1).reason, "open");
}

// created_at 解析不了的世界两条规则都不选，但占一个名额（按最新排）。
TEST(Cleanup, UnparsableCreatedAtIsNeverSelected) {
    const TempDir tmp;
    {
        auto reg = open_db(tmp);
        reclaimable(reg, "garbled", "g", kStale);
        reclaimable(reg, "older", "g", minute_stamp(0));
        reclaimable(reg, "newer", "g", minute_stamp(1));
    }
    sql_exec(tmp.path() / "registry.db",
             "UPDATE worlds SET created_at='yesterday' WHERE name='garbled'");
    auto reg = open_db(tmp);
    const auto plan = plan_cleanup(reg, CleanupConfig{.keep_per_group = 2}, kNow, {});
    ASSERT_EQ(names_of(plan.remove), std::vector<std::string>{"older"});
    EXPECT_EQ(plan.remove.front().reason, "over_count");
}

// 未来时刻（时钟回拨）的 created_at 不算超龄，份数上算最新。
TEST(Cleanup, FutureCreatedAtIsNotOverAge) {
    const TempDir tmp;
    auto reg = open_db(tmp);
    reclaimable(reg, "from-the-future", "g", "2027-01-01T00:00:00Z");
    const auto plan = plan_cleanup(reg, CleanupConfig{}, kNow, {});
    EXPECT_TRUE(plan.remove.empty());
}

TEST(Cleanup, RejectsBadConfigAndNow) {
    const TempDir tmp;
    auto reg = open_db(tmp);
    EXPECT_EQ(code_of([&] { (void)plan_cleanup(reg, CleanupConfig{.keep_per_group = 0}, kNow, {}); }),
              "invalid_settings");
    EXPECT_EQ(code_of([&] { (void)plan_cleanup(reg, CleanupConfig{.max_age_days = 0}, kNow, {}); }),
              "invalid_settings");
    EXPECT_EQ(code_of([&] {
                  (void)plan_cleanup(reg, CleanupConfig{.archive_max_age_days = -1}, kNow, {});
              }),
              "invalid_settings");
    EXPECT_EQ(code_of([&] { (void)plan_cleanup(reg, CleanupConfig{}, "2026-11-20", {}); }),
              "invalid_settings");
    EXPECT_EQ(code_of([&] { (void)plan_cleanup(reg, CleanupConfig{}, "", {}); }),
              "invalid_settings");
}

// 不可回收世界（含默认世界）的归档按名字里的时刻算天数；可回收世界的归档不单列（随世界删）。
TEST(Cleanup, PlanListsAgedArchivesOfNonReclaimableWorldsOnly) {
    const TempDir tmp;
    auto reg = open_db(tmp);
    reg.create("deploy", "", {}, "{}", kStale);
    reclaimable(reg, "rollout", "g", kFresh);
    const fs::path old_deploy = put_archive(reg, "deploy", "20261101T000000Z");
    put_archive(reg, "deploy", "20261106T000000Z");             // 恰好 14 天：留
    put_archive(reg, "deploy", "20261119T000000Z");             // 1 天：留
    const fs::path old_default = put_archive(reg, "default", "20261020T120000Z");
    put_archive(reg, "rollout", "20261101T000000Z");            // 可回收世界：不单列
    put_archive(reg, "deploy", "20261399T000000Z");             // 形状对、日期不存在：不删
    const auto plan = plan_cleanup(reg, CleanupConfig{}, kNow, {});
    ASSERT_EQ(plan.archives.size(), 2U);
    std::set<std::string> got;
    for (const auto& item : plan.archives) {
        got.insert(item.world + "/" + item.name);
        EXPECT_EQ(item.dir_id, reg.get(item.world).dir_id);
    }
    EXPECT_EQ(got, (std::set<std::string>{"default/" + old_default.filename().string(),
                                          "deploy/" + old_deploy.filename().string()}));
    const auto lenient = plan_cleanup(reg, CleanupConfig{.archive_max_age_days = 60}, kNow, {});
    EXPECT_TRUE(lenient.archives.empty());
    EXPECT_TRUE(plan.remove.empty());   // plan 只读：什么都没删
    EXPECT_TRUE(fs::exists(old_deploy));
}

// 某个世界列不出归档（布局被篡改）不影响别的世界，也不让 plan 失败。
TEST(Cleanup, PlanToleratesAWorldWhoseArchivesCannotBeListed) {
    const TempDir tmp;
    const TempDir outside;
    auto reg = open_db(tmp);
    reg.create("broken", "", {}, "{}", kStale);
    reg.create("deploy", "", {}, "{}", kStale);
    const fs::path aged = put_archive(reg, "deploy", "20261101T000000Z");
    const fs::path home = tmp.path() / "worlds" / reg.get("broken").dir_id;
    fs::remove_all(home);
    fs::create_symlink(outside.path(), home);   // 世界目录外链：validate_world 拒
    const auto plan = plan_cleanup(reg, CleanupConfig{}, kNow, {});
    ASSERT_EQ(plan.archives.size(), 1U);
    EXPECT_EQ(plan.archives.front().world, "deploy");
    EXPECT_EQ(plan.archives.front().name, aged.filename().string());
}

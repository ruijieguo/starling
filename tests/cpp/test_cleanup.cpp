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


// 第 6 期之前（schema_version 1，47474ca）的注册表建表 SQL，逐字照抄 registry_db.cpp 的 kSchemaSql。降级验证用：
// 按 spec §5.4 的两条 SQL 改回之后，库的形状必须与它建出来的完全相同，旧二进制的打开逻辑（执行这段 SQL、
// 读 schema_version 必须是 "1"）才会通过。
constexpr const char* kV1SchemaSql = R"sql(
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS worlds (
    name TEXT PRIMARY KEY,
    dir_id TEXT NOT NULL UNIQUE,
    tenant TEXT NOT NULL,
    db_path TEXT NOT NULL,
    snapshot_dir TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    seed INTEGER NOT NULL DEFAULT 0,
    read_only INTEGER NOT NULL DEFAULT 0,
    reclaimable INTEGER NOT NULL DEFAULT 0,
    retention_group TEXT NOT NULL DEFAULT '',
    fork_of_world TEXT NOT NULL DEFAULT '',
    fork_of_snapshot TEXT NOT NULL DEFAULT '',
    settings_json TEXT NOT NULL DEFAULT '{}',
    holders INTEGER NOT NULL DEFAULT 0,
    statements INTEGER NOT NULL DEFAULT 0,
    last_write_at TEXT NOT NULL DEFAULT '',
    stats_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS world_labels (
    name TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (name, key)
);
CREATE INDEX IF NOT EXISTS idx_world_labels_kv ON world_labels (key, value);
CREATE TABLE IF NOT EXISTS snapshots (
    world TEXT NOT NULL,
    id TEXT NOT NULL,
    path TEXT NOT NULL,
    kind TEXT NOT NULL,
    reason TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    world_time TEXT NOT NULL DEFAULT '',
    size_bytes INTEGER NOT NULL DEFAULT 0,
    sessions_complete INTEGER,
    session_id TEXT NOT NULL DEFAULT '',
    content_mark TEXT NOT NULL DEFAULT '',
    seq INTEGER NOT NULL,
    digest TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (world, id)
);
)sql";

// spec §5.4 写给用户的降级 SQL（裁定 R45），逐字。
constexpr const char* kDowngradeSql =
    "DROP TABLE cleanup_log; UPDATE meta SET value='1' WHERE key='schema_version';";

// sqlite_master 的全部行（type|name|tbl_name|sql），按 name 排。
std::vector<std::string> master_rows(const fs::path& db_file) {
    sqlite3* raw = nullptr;
    EXPECT_EQ(sqlite3_open(db_file.string().c_str(), &raw), SQLITE_OK);
    sqlite3_stmt* stmt = nullptr;
    EXPECT_EQ(sqlite3_prepare_v2(raw,
                                 "SELECT type || '|' || name || '|' || tbl_name || '|' || "
                                 "COALESCE(sql, '') FROM sqlite_master ORDER BY name",
                                 -1, &stmt, nullptr),
              SQLITE_OK);
    std::vector<std::string> out;
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        // NOLINTNEXTLINE(cppcoreguidelines-pro-type-reinterpret-cast)
        out.emplace_back(reinterpret_cast<const char*>(sqlite3_column_text(stmt, 0)));
    }
    sqlite3_finalize(stmt);
    sqlite3_close(raw);
    return out;
}

// 单个值的查询（没有行返回 "<none>"）。
std::string scalar(const fs::path& db_file, const std::string& sql) {
    sqlite3* raw = nullptr;
    EXPECT_EQ(sqlite3_open(db_file.string().c_str(), &raw), SQLITE_OK);
    sqlite3_stmt* stmt = nullptr;
    EXPECT_EQ(sqlite3_prepare_v2(raw, sql.c_str(), -1, &stmt, nullptr), SQLITE_OK) << sql;
    std::string out = "<none>";
    if (sqlite3_step(stmt) == SQLITE_ROW) {
        const unsigned char* text = sqlite3_column_text(stmt, 0);
        // NOLINTNEXTLINE(cppcoreguidelines-pro-type-reinterpret-cast)
        out = text == nullptr ? std::string("<null>") : std::string(reinterpret_cast<const char*>(text));
    }
    sqlite3_finalize(stmt);
    sqlite3_close(raw);
    return out;
}

std::string schema_version_of(const fs::path& registry) {
    return scalar(registry, "SELECT value FROM meta WHERE key = 'schema_version'");
}

bool has_table(const fs::path& db_file, const std::string& table) {
    return scalar(db_file, "SELECT name FROM sqlite_master WHERE type = 'table' AND name = '" + table +
                               "'") == table;
}

// 旧二进制（kSchemaVersion = 1）打开注册表时做的事：执行它的建表 SQL（IF NOT EXISTS），读 schema_version，
// 必须是 "1"。返回能不能通过。
bool v1_open_logic_accepts(const fs::path& registry) {
    sql_exec(registry, kV1SchemaSql);
    return schema_version_of(registry) == "1";
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

// ---- 注册表 v2：cleanup_log 表、v1 就地升级、降级（裁定 R45） ----

TEST(Cleanup, FreshRegistryIsV2WithCleanupLog) {
    const TempDir tmp;
    { auto reg = open_db(tmp); }
    const fs::path file = tmp.path() / "registry.db";
    EXPECT_EQ(schema_version_of(file), "2");
    EXPECT_TRUE(has_table(file, "cleanup_log"));
    auto reg = open_db(tmp);
    EXPECT_TRUE(cleanup_log(reg, 50).empty());
}

TEST(Cleanup, RegistryV1UpgradesToV2WithCleanupLog) {
    const TempDir tmp;
    const fs::path file = tmp.path() / "registry.db";
    {
        auto reg = open_db(tmp);
        reclaimable(reg, "rollout", "g", kFresh);
        put_held(reg, "rollout", "20261119T000000Z-aaaa");
    }
    sql_exec(file, kDowngradeSql);   // 造出第 6 期之前的 v1 注册表
    ASSERT_EQ(schema_version_of(file), "1");
    ASSERT_FALSE(has_table(file, "cleanup_log"));
    for (int round = 0; round < 2; ++round) {   // 第二次打开时已是 v2：幂等
        auto reg = open_db(tmp);
        EXPECT_EQ(schema_version_of(file), "2") << round;
        EXPECT_TRUE(has_table(file, "cleanup_log")) << round;
        EXPECT_TRUE(cleanup_log(reg, 50).empty());
        EXPECT_TRUE(reg.get("rollout").reclaimable);   // 原有的行原样
        ASSERT_EQ(reg.snapshots("rollout").size(), 1U);
        EXPECT_EQ(reg.snapshots("rollout").front().kind, "held");
    }
}

// CREATE TABLE IF NOT EXISTS：v1 注册表里已有一张 cleanup_log（例如手工建过）时照样升级，不报错。
TEST(Cleanup, RegistryV1UpgradeToleratesAnExistingCleanupLogTable) {
    const TempDir tmp;
    const fs::path file = tmp.path() / "registry.db";
    { auto reg = open_db(tmp); }
    sql_exec(file, "UPDATE meta SET value='1' WHERE key='schema_version'");
    ASSERT_TRUE(has_table(file, "cleanup_log"));
    { auto reg = open_db(tmp); }
    EXPECT_EQ(schema_version_of(file), "2");
}

// 不认识的版本照旧拒绝，而且拒绝时什么都没改（升级与版本检查在同一个事务里，回滚）。
TEST(Cleanup, UnsupportedRegistryVersionIsRejectedUntouched) {
    const TempDir tmp;
    const fs::path file = tmp.path() / "registry.db";
    { auto reg = open_db(tmp); }
    sql_exec(file, std::string(kDowngradeSql) + "UPDATE meta SET value='3' WHERE key='schema_version';");
    EXPECT_EQ(code_of([&] { (void)open_db(tmp); }), "registry_corrupt");
    EXPECT_EQ(schema_version_of(file), "3");
    EXPECT_FALSE(has_table(file, "cleanup_log"));
}

// 裁定 R45：v2 注册表按 spec §5.4 的两条 SQL 改回之后，形状与第 6 期之前的 v1 注册表完全相同，旧二进制的
// 打开逻辑能通过；改回之前它会拒绝（schema_version 是 "2"）。之后再用本版本打开，又升回 v2。
TEST(Cleanup, RegistryV2DowngradesToV1WithTheDocumentedSql) {
    const TempDir tmp;
    const TempDir reference;
    const fs::path file = tmp.path() / "registry.db";
    {
        auto reg = open_db(tmp);
        reg.create("deploy", "部署", {{"env", "prod"}}, "{}", kFresh);
        reclaimable(reg, "rollout", "g", kFresh);
        put_held(reg, "rollout", "20261119T000000Z-aaaa");
    }
    sql_exec(file, "INSERT INTO cleanup_log (at, world, retention_group, action, reason) "
                   "VALUES ('2026-11-19T00:00:00Z', 'gone', 'g', 'removed', 'over_age')");
    EXPECT_FALSE(v1_open_logic_accepts(file));   // 改回之前：旧二进制拒绝

    sql_exec(file, kDowngradeSql);
    const fs::path v1_file = reference.path() / "v1.db";
    sql_exec(v1_file, kV1SchemaSql);
    EXPECT_EQ(master_rows(file), master_rows(v1_file));   // 表、索引、建表语句逐行相同
    EXPECT_TRUE(v1_open_logic_accepts(file));
    EXPECT_EQ(master_rows(file), master_rows(v1_file));   // 旧逻辑打开时也没建出别的东西
    EXPECT_EQ(scalar(file, "SELECT COUNT(*) FROM worlds"), "3");
    EXPECT_EQ(scalar(file, "SELECT kind FROM snapshots WHERE world = 'rollout'"), "held");

    auto reg = open_db(tmp);   // 再升级回来
    EXPECT_EQ(schema_version_of(file), "2");
    EXPECT_TRUE(cleanup_log(reg, 50).empty());   // 降级丢掉了旧记录
    EXPECT_EQ(reg.get("deploy").labels.at("env"), "prod");
}

// 导入 worlds.json 建出来的注册表同样是 v2、带 cleanup_log。
TEST(Cleanup, ImportedRegistryIsV2) {
    const TempDir tmp;
    const std::string body = std::string(R"({"version":1,"default":"default","snapshot_retention":5,)") +
                             R"("worlds":{"default":{"tenant":"default","db_path":")" +
                             (tmp.path() / "dashboard.db").string() + R"(","snapshot_dir":")" +
                             (tmp.path() / "worlds" / "default" / "snapshots").string() +
                             R"(","label":"主世界","created_at":"2026-10-25T00:00:00Z"}},)" +
                             R"("snapshots":{}})";
    std::ofstream(tmp.path() / "worlds.json") << body;
    import_worlds_json(tmp.path());
    const fs::path file = tmp.path() / "registry.db";
    EXPECT_EQ(schema_version_of(file), "2");
    EXPECT_TRUE(has_table(file, "cleanup_log"));
    auto reg = open_db(tmp);
    EXPECT_EQ(reg.default_world(), "default");
}

TEST(Cleanup, CleanupLogReadsNewestFirstWithinLimit) {
    const TempDir tmp;
    { auto reg = open_db(tmp); }
    const fs::path file = tmp.path() / "registry.db";
    sql_exec(file,
             "INSERT INTO cleanup_log (at, world, retention_group, action, reason, detail) VALUES "
             "('2026-11-19T00:00:00Z', 'w1', 'g', 'removed', 'over_count', ''),"
             "('2026-11-19T00:10:00Z', 'w2', '', 'skipped', 'held_snapshot', ''),"
             "('2026-11-19T00:20:00Z', 'deploy', '', 'archive_removed', 'over_age', "
             "'world.db.pre-rollback-20261101T000000Z-abcd')");
    auto reg = open_db(tmp);
    const auto all = cleanup_log(reg, 50);
    ASSERT_EQ(all.size(), 3U);
    EXPECT_EQ(all.at(0).world, "deploy");
    EXPECT_EQ(all.at(0).action, "archive_removed");
    EXPECT_EQ(all.at(0).detail, "world.db.pre-rollback-20261101T000000Z-abcd");
    EXPECT_EQ(all.at(1).world, "w2");
    EXPECT_EQ(all.at(1).reason, "held_snapshot");
    EXPECT_EQ(all.at(2).world, "w1");
    EXPECT_EQ(all.at(2).group, "g");
    EXPECT_EQ(all.at(2).at, "2026-11-19T00:00:00Z");
    EXPECT_GT(all.at(0).id, all.at(1).id);
    const auto newest = cleanup_log(reg, 1);
    ASSERT_EQ(newest.size(), 1U);
    EXPECT_EQ(newest.front().world, "deploy");
    EXPECT_EQ(code_of([&] { (void)cleanup_log(reg, 0); }), "invalid_world_query");
    EXPECT_EQ(code_of([&] { (void)cleanup_log(reg, 501); }), "invalid_world_query");
    EXPECT_EQ(cleanup_log(reg, 500).size(), 3U);
}

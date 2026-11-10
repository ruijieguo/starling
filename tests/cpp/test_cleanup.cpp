// 自动清理（spec §9，第 6 期，裁定 R56）：选世界的规则、跳过与重新核对、删除顺序与清理记录、注册表 v1→v2。
// 时间一律注入（kNow），不读墙钟。
#include "starling/governance/cleanup.hpp"
#include "starling/governance/registry_db.hpp"
#include "starling/persistence/connection.hpp"

// 内部助手的纯函数测试（裁定 R79）：不属于公开 API，按相对路径包含。
#include "../../src/governance/cleanup_internal.hpp"
#include "../../src/governance/registry_db_internal.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>
#include <unistd.h>

#include <algorithm>
#include <atomic>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <functional>
#include <map>
#include <memory>
#include <set>
#include <string>
#include <system_error>
#include <utility>
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
    const int status = sqlite3_exec(raw, sql.c_str(), nullptr, nullptr, &err);
    const std::string message = err == nullptr ? std::string() : std::string(err);
    if (err != nullptr) { sqlite3_free(err); }
    sqlite3_close(raw);
    ASSERT_EQ(status, SQLITE_OK) << message;
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

// cleanup_log 里某个条件的行数。
std::string log_count(const TempDir& tmp, const std::string& where) {
    return scalar(tmp.path() / "registry.db", "SELECT COUNT(*) FROM cleanup_log WHERE " + where);
}

fs::path home_of(const TempDir& tmp, const std::string& dir_id) { return tmp.path() / "worlds" / dir_id; }

// 模拟「注册项已摘、目录还没删」的崩溃现场：摘掉 world 的注册项，记一条 pending_dir=1 的 removed 记录。
void simulate_crash_after_unregister(const TempDir& tmp, const std::string& world, const std::string& dir_id) {
    sql_exec(tmp.path() / "registry.db",
             "BEGIN; INSERT INTO cleanup_log (at, world, retention_group, action, reason, dir_id, pending_dir) "
             "VALUES ('2026-11-19T00:00:00Z', '" + world + "', 'g', 'removed', 'over_age', '" + dir_id + "', 1);"
             "DELETE FROM world_labels WHERE name = '" + world + "';"
             "DELETE FROM snapshots WHERE world = '" + world + "';"
             "DELETE FROM worlds WHERE name = '" + world + "'; COMMIT;");
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

// ---- execute_cleanup：重新核对、删除顺序、清理记录 ----

TEST(Cleanup, CleanupLogRecordsEachRemoval) {
    const TempDir tmp;
    auto reg = open_db(tmp);
    reclaimable(reg, "old-a", "run1", kStale);
    reclaimable(reg, "old-b", "", kStale);
    for (int index = 0; index < 3; ++index) {
        reclaimable(reg, "run1-w" + std::to_string(index), "run1", minute_stamp(index));
    }
    // run1 组：w2、w1 留；w0 排第 3 → over_count；old-a 最旧且超龄 → over_age。
    const fs::path rollout_archive = put_archive(reg, "old-a", "20261101T000000Z");   // 随世界一起删
    std::map<std::string, std::string> homes;
    for (const auto& name : {"old-a", "old-b", "run1-w0"}) { homes[name] = reg.get(name).dir_id; }
    const auto plan = plan_cleanup(reg, CleanupConfig{.keep_per_group = 2}, kNow, {});
    ASSERT_EQ(names_of(plan.remove), (std::vector<std::string>{"old-a", "old-b", "run1-w0"}));

    const auto removed = execute_cleanup(reg, plan, CleanupConfig{.keep_per_group = 2}, kNow);
    EXPECT_EQ(names_of(removed), names_of(plan.remove));
    for (const auto& [name, dir_id] : homes) {
        EXPECT_EQ(code_of([&] { (void)reg.get(name); }), "world_not_found") << name;
        EXPECT_FALSE(fs::exists(fs::symlink_status(home_of(tmp, dir_id)))) << name;
    }
    EXPECT_FALSE(fs::exists(rollout_archive));
    EXPECT_NO_THROW((void)reg.get("run1-w1"));
    EXPECT_TRUE(fs::exists(home_of(tmp, reg.get("run1-w1").dir_id)));

    const auto log = cleanup_log(reg, 50);
    ASSERT_EQ(log.size(), 3U);
    EXPECT_EQ(log.at(0).world, "run1-w0");   // 最新在前
    EXPECT_EQ(log.at(0).reason, "over_count");
    EXPECT_EQ(log.at(0).group, "run1");
    EXPECT_EQ(log.at(1).world, "old-b");
    EXPECT_EQ(log.at(1).group, "");
    EXPECT_EQ(log.at(2).world, "old-a");
    EXPECT_EQ(log.at(2).reason, "over_age");
    for (const auto& entry : log) {
        EXPECT_EQ(entry.action, "removed") << entry.world;
        EXPECT_EQ(entry.at, kNow) << entry.world;
    }
    EXPECT_EQ(log_count(tmp, "pending_dir = 1"), "0");   // 目录删完，待删标记已清
    EXPECT_EQ(log_count(tmp, "action = 'removed' AND dir_id = '" + homes["old-a"] + "'"), "1");

    // 再跑一轮：没有可删的，什么都不写。
    EXPECT_TRUE(execute_cleanup(reg, plan_cleanup(reg, CleanupConfig{.keep_per_group = 2}, kNow, {}),
                                CleanupConfig{.keep_per_group = 2}, kNow).empty());
    EXPECT_EQ(cleanup_log(reg, 50).size(), 3U);
}

TEST(Cleanup, SkipsWorldWithHeldSnapshotAndLogsReason) {
    const TempDir tmp;
    auto reg = open_db(tmp);
    reclaimable(reg, "kept-by-rise", "g", kStale);
    reclaimable(reg, "late-held", "g", kStale);
    put_held(reg, "kept-by-rise", "20261119T000000Z-aaaa");
    const auto plan = plan_cleanup(reg, CleanupConfig{}, kNow, {});
    ASSERT_EQ(names_of(plan.remove), std::vector<std::string>{"late-held"});
    // plan 之后、execute 之前 rise 拍了一份 held：重新核对时跳过。
    put_held(reg, "late-held", "20261119T000000Z-bbbb");

    EXPECT_TRUE(execute_cleanup(reg, plan, CleanupConfig{}, kNow).empty());
    for (const auto& name : {"kept-by-rise", "late-held"}) {
        EXPECT_NO_THROW((void)reg.get(name)) << name;
        EXPECT_TRUE(fs::exists(home_of(tmp, reg.get(name).dir_id))) << name;
        EXPECT_EQ(reg.snapshots(name).size(), 1U) << name;
    }
    auto log = cleanup_log(reg, 50);
    ASSERT_EQ(log.size(), 2U);
    for (const auto& entry : log) {
        EXPECT_EQ(entry.action, "skipped") << entry.world;
        EXPECT_EQ(entry.reason, "held_snapshot") << entry.world;
        EXPECT_EQ(entry.group, "g") << entry.world;
        EXPECT_EQ(entry.at, kNow);
    }
    // 每 10 分钟再跑一轮：同一世界同一原因不重复记。
    (void)execute_cleanup(reg, plan_cleanup(reg, CleanupConfig{}, kNow, {}), CleanupConfig{}, kNow);
    (void)execute_cleanup(reg, plan, CleanupConfig{}, kNow);
    EXPECT_EQ(cleanup_log(reg, 50).size(), 2U);
    // 原因变了（rise 删了快照、世界此刻开着）才再记一条。
    reg.drop_snapshot("kept-by-rise", "20261119T000000Z-aaaa");
    (void)execute_cleanup(reg, plan_cleanup(reg, CleanupConfig{}, kNow, {"kept-by-rise"}), CleanupConfig{}, kNow);
    log = cleanup_log(reg, 50);
    ASSERT_EQ(log.size(), 3U);
    EXPECT_EQ(log.front().world, "kept-by-rise");
    EXPECT_EQ(log.front().reason, "open");
    // 关掉之后删掉，记 removed。
    const auto removed = execute_cleanup(reg, plan_cleanup(reg, CleanupConfig{}, kNow, {}), CleanupConfig{}, kNow);
    EXPECT_EQ(names_of(removed), std::vector<std::string>{"kept-by-rise"});
    EXPECT_EQ(cleanup_log(reg, 1).front().action, "removed");
}

// 在注册表锁内重新读记录再判定（Review Focus 第 5 条）：世界换了（同名重建）、不在了、不可回收的都不删。
TEST(Cleanup, ExecuteRechecksEachWorldUnderTheRegistryLock) {
    const TempDir tmp;
    auto reg = open_db(tmp);
    reclaimable(reg, "recreated", "g", kStale);
    reclaimable(reg, "vanished", "g", kStale);
    const auto plan = plan_cleanup(reg, CleanupConfig{}, kNow, {});
    ASSERT_EQ(plan.remove.size(), 2U);
    reg.remove("recreated");
    reg.create("recreated", "", {}, "{}", kStale, WorldFlags{.retention_group = "g"});   // 同名，新 dir_id，不可回收
    reg.remove("vanished");
    reg.create("deploy", "", {}, "{}", kStale);
    CleanupPlan forged = plan;
    forged.remove.push_back(CleanupCandidate{.world = "deploy", .group = "", .reason = "over_age",
                                             .dir_id = reg.get("deploy").dir_id});
    forged.remove.push_back(CleanupCandidate{.world = "default", .group = "", .reason = "over_age",
                                             .dir_id = "default"});

    EXPECT_TRUE(execute_cleanup(reg, forged, CleanupConfig{}, kNow).empty());
    EXPECT_TRUE(fs::exists(home_of(tmp, reg.get("recreated").dir_id)));
    EXPECT_TRUE(fs::exists(home_of(tmp, reg.get("deploy").dir_id)));
    EXPECT_NO_THROW((void)reg.get("default"));
    const auto log = cleanup_log(reg, 50);
    ASSERT_EQ(log.size(), 3U);   // vanished：世界已不在，什么都不记
    EXPECT_EQ(log.at(2).world, "recreated");
    EXPECT_EQ(log.at(2).reason, "world_changed");
    EXPECT_EQ(log.at(1).world, "deploy");
    EXPECT_EQ(log.at(1).reason, "not_reclaimable");
    EXPECT_EQ(log.at(0).world, "default");
    EXPECT_EQ(log.at(0).reason, "not_reclaimable");
}

// 世界目录被换成指向兄弟世界的符号链接：布局校验不过，跳过并记 failed，注册项与兄弟世界都不动。
TEST(Cleanup, ExecuteSkipsAWorldWhoseHomeFailsTheLayoutCheck) {
    const TempDir tmp;
    auto reg = open_db(tmp);
    reclaimable(reg, "tampered", "g", kStale);
    reclaimable(reg, "sibling", "g", kFresh);
    const fs::path sibling_home = home_of(tmp, reg.get("sibling").dir_id);
    std::ofstream(sibling_home / "marker") << "precious";
    const fs::path home = home_of(tmp, reg.get("tampered").dir_id);
    fs::remove_all(home);
    fs::create_directory_symlink(sibling_home, home);
    const auto plan = plan_cleanup(reg, CleanupConfig{}, kNow, {});
    ASSERT_EQ(names_of(plan.remove), std::vector<std::string>{"tampered"});

    EXPECT_TRUE(execute_cleanup(reg, plan, CleanupConfig{}, kNow).empty());
    EXPECT_NO_THROW((void)reg.get("tampered"));
    EXPECT_TRUE(fs::is_symlink(home));
    EXPECT_TRUE(fs::exists(sibling_home / "marker"));
    const auto log = cleanup_log(reg, 50);
    ASSERT_EQ(log.size(), 1U);
    EXPECT_EQ(log.front().action, "skipped");
    EXPECT_EQ(log.front().reason, "failed");
    EXPECT_NE(log.front().detail.find("snapshot_failed"), std::string::npos) << log.front().detail;
    EXPECT_EQ(log_count(tmp, "pending_dir = 1"), "0");
}

// 崩溃在「注册项已摘」之后、「目录删完」之前：下一轮 execute_cleanup 开头补删目录、清掉标记。
TEST(Cleanup, NextRunFinishesADirectoryLeftPendingByACrash) {
    const TempDir tmp;
    auto reg = open_db(tmp);
    reclaimable(reg, "half-done", "g", kStale);
    const std::string dir_id = reg.get("half-done").dir_id;
    std::ofstream(home_of(tmp, dir_id) / "world.db") << "x";
    simulate_crash_after_unregister(tmp, "half-done", dir_id);
    auto reopened = open_db(tmp);
    EXPECT_TRUE(execute_cleanup(reopened, CleanupPlan{}, CleanupConfig{}, kNow).empty());
    EXPECT_FALSE(fs::exists(home_of(tmp, dir_id)));
    EXPECT_EQ(log_count(tmp, "pending_dir = 1"), "0");
    EXPECT_EQ(log_count(tmp, "action = 'removed'"), "1");   // 补删不另记
}

// 目录删不掉（权限）：注册项已摘、记录在、标记留着；修好之后下一轮补删。
TEST(Cleanup, DirectoryRemovalFailureStaysPendingAndIsRetried) {
    if (::geteuid() == 0) { GTEST_SKIP() << "root 不受目录权限限制"; }
    const TempDir tmp;
    auto reg = open_db(tmp);
    reclaimable(reg, "stubborn", "g", kStale);
    const std::string dir_id = reg.get("stubborn").dir_id;
    const fs::path locked = home_of(tmp, dir_id) / "snapshots";
    std::ofstream(locked / "file") << "x";
    fs::permissions(locked, fs::perms::owner_read | fs::perms::owner_exec, fs::perm_options::replace);
    const auto removed = execute_cleanup(reg, plan_cleanup(reg, CleanupConfig{}, kNow, {}), CleanupConfig{}, kNow);
    EXPECT_EQ(names_of(removed), std::vector<std::string>{"stubborn"});
    EXPECT_EQ(code_of([&] { (void)reg.get("stubborn"); }), "world_not_found");
    EXPECT_TRUE(fs::exists(locked / "file"));
    EXPECT_EQ(log_count(tmp, "pending_dir = 1 AND dir_id = '" + dir_id + "'"), "1");
    fs::permissions(locked, fs::perms::owner_all, fs::perm_options::replace);
    EXPECT_TRUE(execute_cleanup(reg, CleanupPlan{}, CleanupConfig{}, kNow).empty());
    EXPECT_FALSE(fs::exists(home_of(tmp, dir_id)));
    EXPECT_EQ(log_count(tmp, "pending_dir = 1"), "0");
}

// 裁定 R56 补充 1：补删只删 worlds/<dir_id>，且 dir_id 必须在 cleanup_log 里标成待删、并且 worlds 表里已经没有它。
TEST(Cleanup, PendingSweepOnlyRemovesUnregisteredPendingDirectories) {
    const TempDir tmp;
    const TempDir outside;
    auto reg = open_db(tmp);
    reclaimable(reg, "gone", "g", kStale);
    reclaimable(reg, "alive", "g", kFresh);
    const std::string gone_dir = reg.get("gone").dir_id;
    const std::string alive_dir = reg.get("alive").dir_id;
    simulate_crash_after_unregister(tmp, "gone", gone_dir);
    const fs::path stray = tmp.path() / "worlds" / "stray-notes";   // 与注册表无关的目录
    fs::create_directories(stray);
    std::ofstream(stray / "readme") << "keep me";
    std::ofstream(outside.path() / "precious") << "keep me";
    // 篡改过的待删记录：指向已登记的世界、越出 worlds/ 的路径。
    sql_exec(tmp.path() / "registry.db",
             "INSERT INTO cleanup_log (at, world, action, reason, dir_id, pending_dir) VALUES "
             "('2026-11-19T00:00:00Z', 'alive', 'removed', 'over_age', '" + alive_dir + "', 1),"
             "('2026-11-19T00:00:00Z', 'evil', 'removed', 'over_age', '../../" +
             outside.path().filename().string() + "', 1),"
             "('2026-11-19T00:00:00Z', 'evil2', 'removed', 'over_age', '..', 1)");
    auto reopened = open_db(tmp);
    (void)execute_cleanup(reopened, CleanupPlan{}, CleanupConfig{}, kNow);
    EXPECT_FALSE(fs::exists(home_of(tmp, gone_dir)));
    EXPECT_TRUE(fs::exists(stray / "readme"));
    EXPECT_TRUE(fs::exists(home_of(tmp, alive_dir)));
    EXPECT_NO_THROW((void)reopened.get("alive"));
    EXPECT_TRUE(fs::exists(outside.path() / "precious"));
    EXPECT_TRUE(fs::exists(tmp.path() / "worlds"));
    EXPECT_EQ(log_count(tmp, "pending_dir = 1 AND dir_id = '" + gone_dir + "'"), "0");
}

// 裁定 R58：reserve_home 抽到一个标成待删的 dir_id（目录已经不在）时跳过，再抽一个。随机源用测试钩子换成固定序列，
// 序列用完之后给 "f…f0"、"f…f1"…（不会与前面的撞）。
namespace {
std::function<std::string()> fixed_dir_ids(std::vector<std::string> ids) {
    auto state = std::make_shared<std::pair<std::vector<std::string>, std::size_t>>(std::move(ids), 0);
    return [state] {
        const std::size_t pos = state->second++;
        if (pos < state->first.size()) { return state->first.at(pos); }
        return std::string(15, 'f') + std::to_string(pos - state->first.size());
    };
}
}  // namespace

TEST(Cleanup, ReserveHomeSkipsPendingDirId) {
    const std::string first(16, 'a');
    const std::string second(16, 'b');
    {
        const TempDir tmp;   // 对照：没有待删记录时拿到序列里的第一个
        auto reg = open_db(tmp);
        reg.set_dir_id_source_for_test(fixed_dir_ids({first, second}));
        EXPECT_EQ(reg.create("plain", "", {}, "{}", kFresh).dir_id, first);
    }
    const TempDir tmp;
    auto reg = open_db(tmp);
    sql_exec(tmp.path() / "registry.db",
             "INSERT INTO cleanup_log (at, world, action, reason, dir_id, pending_dir) VALUES "
             "('2026-11-19T00:00:00Z', 'gone', 'removed', 'over_age', '" + first + "', 1)");
    ASSERT_FALSE(fs::exists(home_of(tmp, first)));   // 目录已经不在：只靠待删标记挡住
    reg.set_dir_id_source_for_test(fixed_dir_ids({first, second}));
    EXPECT_EQ(reg.create("fresh", "", {}, "{}", kFresh).dir_id, second);
    // create_world（也初始化库文件）走同一个 reserve_home：first 待删、second 已被 fresh 占用，都跳过。
    reg.set_dir_id_source_for_test(fixed_dir_ids({first, second}));
    EXPECT_EQ(reg.create_world("fresh-2", "", {}, "{}", kFresh).dir_id, std::string(15, 'f') + "0");
    // 待删标记清掉之后（补删完成）这个 dir_id 又能用。
    sql_exec(tmp.path() / "registry.db", "UPDATE cleanup_log SET pending_dir = 0");
    reg.set_dir_id_source_for_test(fixed_dir_ids({first}));
    EXPECT_EQ(reg.create("reuse", "", {}, "{}", kFresh).dir_id, first);
}

TEST(Cleanup, ArchivesOfNonReclaimableWorldsAgeOut) {
    const TempDir tmp;
    auto reg = open_db(tmp);
    reg.create("deploy", "", {}, "{}", kStale, WorldFlags{.retention_group = "prod"});
    const fs::path old_deploy = put_archive(reg, "deploy", "20261101T000000Z");
    const fs::path fresh_deploy = put_archive(reg, "deploy", "20261119T000000Z");
    const fs::path old_default = put_archive(reg, "default", "20261020T120000Z");
    const fs::path keep = archive_dir(reg, "deploy") / "keep.txt";
    std::ofstream(keep) << "x";
    const auto plan = plan_cleanup(reg, CleanupConfig{}, kNow, {});
    ASSERT_EQ(plan.archives.size(), 2U);

    EXPECT_TRUE(execute_cleanup(reg, plan, CleanupConfig{}, kNow).empty());   // 返回的是删掉的世界：没有
    EXPECT_FALSE(fs::exists(old_deploy));
    EXPECT_FALSE(fs::exists(old_default));
    EXPECT_TRUE(fs::exists(fresh_deploy));
    EXPECT_TRUE(fs::exists(keep));
    EXPECT_NO_THROW((void)reg.get("deploy"));
    const auto log = cleanup_log(reg, 50);
    ASSERT_EQ(log.size(), 2U);
    std::set<std::string> got;
    for (const auto& entry : log) {
        EXPECT_EQ(entry.action, "archive_removed");
        EXPECT_EQ(entry.reason, "over_age");
        got.insert(entry.world + "|" + entry.group + "|" + entry.detail);
    }
    EXPECT_EQ(got, (std::set<std::string>{"default||" + old_default.filename().string(),
                                          "deploy|prod|" + old_deploy.filename().string()}));
    // 同一份 plan 再执行：归档已不在，什么都不删、不记。
    (void)execute_cleanup(reg, plan, CleanupConfig{}, kNow);
    EXPECT_EQ(cleanup_log(reg, 50).size(), 2U);
}

// 归档在 plan 之后、execute 之前换了主人（同名重建）或被列不出来时不删。
TEST(Cleanup, ArchiveRemovalRechecksTheWorld) {
    const TempDir tmp;
    auto reg = open_db(tmp);
    reg.create("deploy", "", {}, "{}", kStale);
    put_archive(reg, "deploy", "20261101T000000Z");
    const auto plan = plan_cleanup(reg, CleanupConfig{}, kNow, {});
    ASSERT_EQ(plan.archives.size(), 1U);
    reg.remove("deploy");
    reg.create("deploy", "", {}, "{}", kStale);
    const fs::path same_name = put_archive(reg, "deploy", "20261101T000000Z");
    (void)execute_cleanup(reg, plan, CleanupConfig{}, kNow);
    EXPECT_TRUE(fs::exists(same_name));
    EXPECT_TRUE(cleanup_log(reg, 50).empty());
}

TEST(Cleanup, ExecuteRejectsBadNowBeforeTouchingAnything) {
    const TempDir tmp;
    auto reg = open_db(tmp);
    reclaimable(reg, "old", "g", kStale);
    const auto plan = plan_cleanup(reg, CleanupConfig{}, kNow, {});
    ASSERT_EQ(plan.remove.size(), 1U);
    EXPECT_EQ(code_of([&] { (void)execute_cleanup(reg, plan, CleanupConfig{}, "now"); }), "invalid_settings");
    EXPECT_NO_THROW((void)reg.get("old"));
    EXPECT_TRUE(cleanup_log(reg, 50).empty());
}

// ---- 裁定 R70：execute_cleanup 的入参只是提名，规则在注册表锁内重算 ----

// 伪造的候选：1 天前的可回收世界不到期，不删，记 no_longer_due；真正到期的世界照删，记录与返回值里的 reason 是重算出来的
// （入参里的 reason 文本被忽略）。plan.skip 里不认识的原因也不写进记录。
TEST(Cleanup, ExecuteIgnoresAForgedFreshCandidateAndForgedReasons) {
    const TempDir tmp;
    auto reg = open_db(tmp);
    const auto fresh = reclaimable(reg, "fresh", "g", kFresh);
    const auto stale = reclaimable(reg, "stale", "g", kStale);
    CleanupPlan forged;
    forged.remove.push_back(CleanupCandidate{.world = "fresh", .group = "g", .reason = "over_age",
                                             .dir_id = fresh.dir_id});
    forged.remove.push_back(CleanupCandidate{.world = "stale", .group = "forged-group", .reason = "bogus",
                                             .dir_id = stale.dir_id});
    forged.skip.push_back(CleanupSkip{.world = "stale", .reason = "made-up", .group = "g"});

    const auto removed = execute_cleanup(reg, forged, CleanupConfig{}, kNow);
    ASSERT_EQ(names_of(removed), std::vector<std::string>{"stale"});
    EXPECT_EQ(removed.front().reason, "over_age");
    EXPECT_EQ(removed.front().group, "g");
    EXPECT_NO_THROW((void)reg.get("fresh"));
    EXPECT_TRUE(fs::exists(home_of(tmp, fresh.dir_id)));
    const auto log = cleanup_log(reg, 50);
    ASSERT_EQ(log.size(), 2U);
    EXPECT_EQ(log.at(1).world, "fresh");
    EXPECT_EQ(log.at(1).action, "skipped");
    EXPECT_EQ(log.at(1).reason, "no_longer_due");
    EXPECT_EQ(log.at(0).world, "stale");
    EXPECT_EQ(log.at(0).action, "removed");
    EXPECT_EQ(log.at(0).reason, "over_age");
    EXPECT_EQ(log.at(0).group, "g");
}

// 伪造的归档：不可回收世界 1 天前的回滚归档不到期，不删，记 no_longer_due（detail 是归档名）。
TEST(Cleanup, ExecuteIgnoresAForgedFreshArchive) {
    const TempDir tmp;
    auto reg = open_db(tmp);
    reg.create("deploy", "", {}, "{}", kStale);
    const fs::path fresh_archive = put_archive(reg, "deploy", "20261119T000000Z");
    CleanupPlan forged;
    forged.archives.push_back(CleanupArchive{.world = "deploy", .dir_id = reg.get("deploy").dir_id,
                                             .name = fresh_archive.filename().string()});
    EXPECT_TRUE(execute_cleanup(reg, forged, CleanupConfig{}, kNow).empty());
    EXPECT_TRUE(fs::exists(fresh_archive));
    const auto log = cleanup_log(reg, 50);
    ASSERT_EQ(log.size(), 1U);
    EXPECT_EQ(log.front().world, "deploy");
    EXPECT_EQ(log.front().action, "skipped");
    EXPECT_EQ(log.front().reason, "no_longer_due");
    EXPECT_EQ(log.front().detail, fresh_archive.filename().string());
    // 天数放宽之后，同一份按名字已到期的归档也不删（规则用 execute 的配置重算）。
    const fs::path aged = put_archive(reg, "deploy", "20261101T000000Z");
    const auto plan = plan_cleanup(reg, CleanupConfig{}, kNow, {});
    ASSERT_EQ(plan.archives.size(), 1U);
    (void)execute_cleanup(reg, plan, CleanupConfig{.archive_max_age_days = 60}, kNow);
    EXPECT_TRUE(fs::exists(aged));
}

// 过时的计划：plan 之后、execute 之前同组里较新的一个世界被删了，原来排在名额之外的世界又排进了名额，不删。
TEST(Cleanup, ExecuteSkipsAWorldAStalePlanStillNames) {
    const TempDir tmp;
    auto reg = open_db(tmp);
    for (int index = 0; index < 3; ++index) {
        reclaimable(reg, "w" + std::to_string(index), "g", minute_stamp(index));
    }
    const CleanupConfig cfg{.keep_per_group = 2};
    const auto plan = plan_cleanup(reg, cfg, kNow, {});
    ASSERT_EQ(names_of(plan.remove), std::vector<std::string>{"w0"});
    reg.remove("w2");   // 较新的成员没了：w0 现在排第 2，在名额之内
    EXPECT_TRUE(execute_cleanup(reg, plan, cfg, kNow).empty());
    EXPECT_NO_THROW((void)reg.get("w0"));
    const auto log = cleanup_log(reg, 50);
    ASSERT_EQ(log.size(), 1U);
    EXPECT_EQ(log.front().world, "w0");
    EXPECT_EQ(log.front().reason, "no_longer_due");
    // 规则用 execute 拿到的配置：份数放宽到默认 200，原计划里到期的世界也不删。
    reclaimable(reg, "w3", "g", minute_stamp(3));
    const auto again = plan_cleanup(reg, cfg, kNow, {});
    ASSERT_EQ(names_of(again.remove), std::vector<std::string>{"w0"});
    EXPECT_TRUE(execute_cleanup(reg, again, CleanupConfig{}, kNow).empty());
    EXPECT_NO_THROW((void)reg.get("w0"));
}

// 裁定 R72 M7：同名重建出一个仍可回收、仍到期的新世界，plan 指的是旧的那个：不删，记 world_changed。
TEST(Cleanup, SameNameRecreatedAsReclaimableIsNotRemoved) {
    const TempDir tmp;
    auto reg = open_db(tmp);
    reclaimable(reg, "rollout", "g", kStale);
    const auto plan = plan_cleanup(reg, CleanupConfig{}, kNow, {});
    ASSERT_EQ(names_of(plan.remove), std::vector<std::string>{"rollout"});
    reg.remove("rollout");
    const auto reborn = reclaimable(reg, "rollout", "g", kStale);
    ASSERT_NE(reborn.dir_id, plan.remove.front().dir_id);
    EXPECT_TRUE(execute_cleanup(reg, plan, CleanupConfig{}, kNow).empty());
    EXPECT_EQ(reg.get("rollout").dir_id, reborn.dir_id);
    EXPECT_TRUE(fs::exists(home_of(tmp, reborn.dir_id)));
    const auto log = cleanup_log(reg, 50);
    ASSERT_EQ(log.size(), 1U);
    EXPECT_EQ(log.front().reason, "world_changed");
}

// 裁定 R72 M1：跳过记录带 dir_id；去重按 (dir_id, action, reason, detail)：同名重建之后的新世界、detail 不同的
// failed 都另记一条。
TEST(Cleanup, SkipRowsCarryDirIdAndDedupPerIncarnation) {
    const TempDir tmp;
    auto reg = open_db(tmp);
    const auto first = reclaimable(reg, "kept", "g", kStale);
    put_held(reg, "kept", "20261119T000000Z-aaaa");
    (void)execute_cleanup(reg, plan_cleanup(reg, CleanupConfig{}, kNow, {}), CleanupConfig{}, kNow);
    (void)execute_cleanup(reg, plan_cleanup(reg, CleanupConfig{}, kNow, {}), CleanupConfig{}, kNow);
    EXPECT_EQ(log_count(tmp, "action = 'skipped' AND dir_id = '" + first.dir_id + "'"), "1");
    reg.remove("kept");
    const auto second = reclaimable(reg, "kept", "g", kStale);
    put_held(reg, "kept", "20261119T000000Z-bbbb");
    (void)execute_cleanup(reg, plan_cleanup(reg, CleanupConfig{}, kNow, {}), CleanupConfig{}, kNow);
    EXPECT_EQ(log_count(tmp, "action = 'skipped' AND dir_id = '" + second.dir_id + "'"), "1");
    EXPECT_EQ(log_count(tmp, "action = 'skipped' AND world = 'kept'"), "2");

    // failed：detail 相同不重复记，不同另记。
    const auto broken = reclaimable(reg, "broken", "g", kStale);
    const fs::path home = home_of(tmp, broken.dir_id);
    const TempDir outside_a;
    const TempDir outside_b;
    fs::remove_all(home);
    fs::create_directory_symlink(outside_a.path(), home);
    for (int round = 0; round < 2; ++round) {
        (void)execute_cleanup(reg, plan_cleanup(reg, CleanupConfig{}, kNow, {}), CleanupConfig{}, kNow);
    }
    EXPECT_EQ(log_count(tmp, "reason = 'failed' AND world = 'broken'"), "1");
    fs::remove(home);
    fs::create_directory_symlink(outside_b.path(), home);
    (void)execute_cleanup(reg, plan_cleanup(reg, CleanupConfig{}, kNow, {}), CleanupConfig{}, kNow);
    EXPECT_EQ(log_count(tmp, "reason = 'failed' AND world = 'broken'"), "2");
    EXPECT_EQ(log_count(tmp, "reason = 'failed' AND dir_id = '" + broken.dir_id + "'"), "2");
}

// ---- 裁定 R71：lstat 出错不算「目录不在」 ----

// 恢复一个目录的权限（析构时），测试中途失败也能让 TempDir 清理掉。
class PermissionRestorer {
public:
    explicit PermissionRestorer(fs::path dir) : dir_(std::move(dir)) {}
    ~PermissionRestorer() {
        std::error_code err;
        fs::permissions(dir_, fs::perms::owner_all, fs::perm_options::replace, err);
    }
    PermissionRestorer(const PermissionRestorer&) = delete;
    PermissionRestorer& operator=(const PermissionRestorer&) = delete;
private:
    fs::path dir_;
};

// worlds/ 是 chmod 0：补删 lstat 世界目录得到 EACCES，不能当成「已经不在」清掉待删标记（那样目录就成了永久孤儿）。
// 标记留着；权限恢复之后下一轮删掉目录、清掉标记。
TEST(Cleanup, PendingSweepKeepsTheMarkerWhenTheDirectoryCannotBeStatted) {
    if (::geteuid() == 0) { GTEST_SKIP() << "root 不受目录权限限制"; }
    const TempDir tmp;
    auto reg = open_db(tmp);
    reclaimable(reg, "half-done", "g", kStale);
    const std::string dir_id = reg.get("half-done").dir_id;
    std::ofstream(home_of(tmp, dir_id) / "world.db") << "x";
    simulate_crash_after_unregister(tmp, "half-done", dir_id);
    const fs::path worlds_root = tmp.path() / "worlds";
    {
        const PermissionRestorer restore(worlds_root);
        fs::permissions(worlds_root, fs::perms::none, fs::perm_options::replace);
        auto reopened = open_db(tmp);
        EXPECT_TRUE(execute_cleanup(reopened, CleanupPlan{}, CleanupConfig{}, kNow).empty());
        EXPECT_EQ(log_count(tmp, "pending_dir = 1 AND dir_id = '" + dir_id + "'"), "1");
    }
    EXPECT_TRUE(fs::exists(home_of(tmp, dir_id) / "world.db"));   // 权限恢复了：目录还在
    auto reopened = open_db(tmp);
    EXPECT_TRUE(execute_cleanup(reopened, CleanupPlan{}, CleanupConfig{}, kNow).empty());
    EXPECT_FALSE(fs::exists(home_of(tmp, dir_id)));
    EXPECT_EQ(log_count(tmp, "pending_dir = 1"), "0");
}

// worlds/ 不可读时整轮清理都不删、不清标记：锁内的布局核对 lstat 世界目录得到 EACCES → 跳过记 failed（注册项不动）；
// 已经摘掉注册项、等着删目录的那个（第 b 步与补删是同一个删除助手，裁定 R72 M8）标记留着。权限恢复后两者都正常收尾。
TEST(Cleanup, UnreadableWorldsDirectoryNeitherRemovesNorClearsMarkers) {
    if (::geteuid() == 0) { GTEST_SKIP() << "root 不受目录权限限制"; }
    const TempDir tmp;
    auto reg = open_db(tmp);
    const auto pending = reclaimable(reg, "pending", "g", kStale);
    const auto due = reclaimable(reg, "due", "g", kStale);
    const auto decision = reg.unregister_for_cleanup("pending", pending.dir_id, CleanupConfig{}, kNow);
    ASSERT_TRUE(decision.removed);   // 第 a 步已做：注册项已摘、标记在，目录还没删
    const auto plan = plan_cleanup(reg, CleanupConfig{}, kNow, {});
    ASSERT_EQ(names_of(plan.remove), std::vector<std::string>{"due"});
    const fs::path worlds_root = tmp.path() / "worlds";
    {
        const PermissionRestorer restore(worlds_root);
        fs::permissions(worlds_root, fs::perms::none, fs::perm_options::replace);
        EXPECT_TRUE(execute_cleanup(reg, plan, CleanupConfig{}, kNow).empty());
        EXPECT_NO_THROW((void)reg.get("due"));
        EXPECT_EQ(log_count(tmp, "pending_dir = 1 AND dir_id = '" + pending.dir_id + "'"), "1");
        EXPECT_EQ(log_count(tmp, "world = 'due' AND reason = 'failed'"), "1");
    }
    EXPECT_TRUE(fs::exists(home_of(tmp, pending.dir_id)));
    EXPECT_TRUE(fs::exists(home_of(tmp, due.dir_id)));
    const auto removed = execute_cleanup(reg, plan, CleanupConfig{}, kNow);
    EXPECT_EQ(names_of(removed), std::vector<std::string>{"due"});
    EXPECT_FALSE(fs::exists(home_of(tmp, pending.dir_id)));
    EXPECT_FALSE(fs::exists(home_of(tmp, due.dir_id)));
    EXPECT_EQ(log_count(tmp, "pending_dir = 1"), "0");
}

// ---- 裁定 R72 M2：补删只认 reserve_home 生成的 dir_id 形状（16 位小写十六进制） ----

TEST(Cleanup, PendingSweepOnlyRemovesGeneratedDirIds) {
    const TempDir tmp;
    auto reg = open_db(tmp);
    // 导入的旧世界保留原目录名作为 dir_id（spec §5.3）：形状合法、但不是生成的。待删记录指向这样的目录时不删。
    const fs::path legacy = tmp.path() / "worlds" / "sim-1";
    const fs::path upper = tmp.path() / "worlds" / "ABCDEF0123456789";
    const fs::path short_hex = tmp.path() / "worlds" / "abcdef";
    for (const auto& dir : {legacy, upper, short_hex}) {
        fs::create_directories(dir);
        std::ofstream(dir / "keep") << "x";
    }
    const std::string generated(16, 'c');
    fs::create_directories(tmp.path() / "worlds" / generated);
    sql_exec(tmp.path() / "registry.db",
             "INSERT INTO cleanup_log (at, world, action, reason, dir_id, pending_dir) VALUES "
             "('2026-11-19T00:00:00Z', 'a', 'removed', 'over_age', 'sim-1', 1),"
             "('2026-11-19T00:00:00Z', 'b', 'removed', 'over_age', 'ABCDEF0123456789', 1),"
             "('2026-11-19T00:00:00Z', 'c', 'removed', 'over_age', 'abcdef', 1),"
             "('2026-11-19T00:00:00Z', 'd', 'removed', 'over_age', '" + generated + "', 1)");
    auto reopened = open_db(tmp);
    (void)execute_cleanup(reopened, CleanupPlan{}, CleanupConfig{}, kNow);
    for (const auto& dir : {legacy, upper, short_hex}) {
        EXPECT_TRUE(fs::exists(dir / "keep")) << dir;
    }
    EXPECT_FALSE(fs::exists(tmp.path() / "worlds" / generated));
    EXPECT_EQ(log_count(tmp, "pending_dir = 1 AND dir_id = '" + generated + "'"), "0");
    EXPECT_EQ(log_count(tmp, "pending_dir = 1 AND dir_id = 'sim-1'"), "1");   // 标记留着，供人工处理
}

// ---- 裁定 R72 M3：注册表连接 synchronous=FULL（世界库不动） ----

// 注册表是 WAL：synchronous=NORMAL 下，提交（摘注册项）之后、下一次 checkpoint 之前断电，提交可能丢；而随后锁外删掉的
// 世界目录不会回来，注册项就指向一个没了的目录。FULL 让每次提交都落盘。世界库的连接（Connection::open）仍是 NORMAL。
TEST(Cleanup, RegistryConnectionIsSynchronousFull) {
    const TempDir tmp;
    auto reg = open_db(tmp);
    EXPECT_EQ(reg.synchronous_for_test(), 2);   // 2 = FULL
    const auto world = reg.create_world("plain", "", {}, "{}", kFresh);
    const auto conn = starling::persistence::Connection::open(world.db_path);
    sqlite3_stmt* stmt = nullptr;
    ASSERT_EQ(sqlite3_prepare_v2(conn.raw(), "PRAGMA synchronous", -1, &stmt, nullptr), SQLITE_OK);
    ASSERT_EQ(sqlite3_step(stmt), SQLITE_ROW);
    EXPECT_EQ(sqlite3_column_int(stmt, 0), 1);   // 世界库：NORMAL，不受影响
    sqlite3_finalize(stmt);
}

// ---- 裁定 R79：6.1 修复轮复审留下的 Minor ----

// held 列按列名取；列不在（改了 SQL 却漏了列名）时抛 registry_corrupt，不能悄悄当成「没有 held」把带 held 快照的世界删掉。
TEST(Cleanup, MissingResultColumnFailsClosed) {
    sqlite3* raw = nullptr;
    ASSERT_EQ(sqlite3_open(":memory:", &raw), SQLITE_OK);
    sqlite3_stmt* stmt = nullptr;
    ASSERT_EQ(sqlite3_prepare_v2(raw, "SELECT 1 AS name, 0 AS has_held", -1, &stmt, nullptr), SQLITE_OK);
    EXPECT_EQ(internal::require_column(stmt, "has_held"), 1);
    EXPECT_EQ(internal::require_column(stmt, "name"), 0);
    EXPECT_EQ(code_of([&] { (void)internal::require_column(stmt, "missing"); }), "registry_corrupt");
    sqlite3_finalize(stmt);
    ASSERT_EQ(sqlite3_prepare_v2(raw, "SELECT 1 AS name", -1, &stmt, nullptr), SQLITE_OK);
    EXPECT_EQ(code_of([&] { (void)internal::require_column(stmt, "has_held"); }), "registry_corrupt");
    sqlite3_finalize(stmt);
    sqlite3_close(raw);
}

// 裁定 R71 的纯函数：lstat 出错（EACCES 等，不是 not_found）是「不知道」，不是「不在」；只有 not_found 才算不在。
TEST(Cleanup, HomePresenceTreatsStatErrorsAsUnknown) {
    using internal::HomePresence;
    const std::error_code none;
    const auto denied = std::make_error_code(std::errc::permission_denied);
    const auto missing = std::make_error_code(std::errc::no_such_file_or_directory);
    EXPECT_EQ(internal::home_presence(fs::file_status(fs::file_type::directory), none), HomePresence::kPresent);
    EXPECT_EQ(internal::home_presence(fs::file_status(fs::file_type::symlink), none), HomePresence::kPresent);
    EXPECT_EQ(internal::home_presence(fs::file_status(fs::file_type::not_found), none), HomePresence::kAbsent);
    EXPECT_EQ(internal::home_presence(fs::file_status(fs::file_type::not_found), missing), HomePresence::kAbsent);
    EXPECT_EQ(internal::home_presence(fs::file_status(fs::file_type::none), denied), HomePresence::kUnknown);
    EXPECT_EQ(internal::home_presence(fs::file_status(fs::file_type::unknown), denied), HomePresence::kUnknown);
}

// 归档的 no_longer_due 按每份归档去重：两份不到期的归档交替出现时，同一份归档不会每轮都再记一条。
TEST(Cleanup, ArchiveSkipsDedupPerArchive) {
    const TempDir tmp;
    auto reg = open_db(tmp);
    reg.create("deploy", "", {}, "{}", kStale);
    const std::string dir_id = reg.get("deploy").dir_id;
    CleanupPlan forged;
    for (const char* stamp : {"20261118T000000Z", "20261119T000000Z"}) {
        const fs::path file = put_archive(reg, "deploy", stamp);
        forged.archives.push_back(CleanupArchive{.world = "deploy", .dir_id = dir_id,
                                                 .name = file.filename().string()});
    }
    for (int round = 0; round < 3; ++round) {
        EXPECT_TRUE(execute_cleanup(reg, forged, CleanupConfig{}, kNow).empty());
    }
    EXPECT_EQ(log_count(tmp, "world = 'deploy' AND reason = 'no_longer_due'"), "2");
    EXPECT_EQ(log_count(tmp, "world = 'deploy' AND detail = '" + forged.archives.at(0).name + "'"), "1");
    EXPECT_EQ(log_count(tmp, "world = 'deploy' AND detail = '" + forged.archives.at(1).name + "'"), "1");
}

// plan.skip 的原因按锁内重读的结果重新核对：此刻有 held 记 held_snapshot（held 在 open 之前判，与 plan_cleanup 同序）；
// 提名 held_snapshot 但 held 已被删掉的不记（它不再受保护，下一轮就删）；不再到期的不记。open 只能由调用方断言。
TEST(Cleanup, SkipReasonsAreRecheckedUnderTheLock) {
    const TempDir tmp;
    auto reg = open_db(tmp);
    reclaimable(reg, "open-then-held", "g", kStale);
    reclaimable(reg, "held-then-dropped", "g", kStale);
    reclaimable(reg, "fresh", "h", kFresh);
    reclaimable(reg, "still-open", "g", kStale);
    put_held(reg, "held-then-dropped", "20261119T000000Z-aaaa");
    auto plan = plan_cleanup(reg, CleanupConfig{}, kNow, {"open-then-held", "still-open"});
    ASSERT_EQ(skip_names(plan.skip),
              (std::vector<std::string>{"open-then-held", "held-then-dropped", "still-open"}));
    put_held(reg, "open-then-held", "20261119T000000Z-bbbb");
    reg.drop_snapshot("held-then-dropped", "20261119T000000Z-aaaa");
    plan.remove.clear();
    plan.skip.push_back(CleanupSkip{.world = "fresh", .reason = "open", .group = "h"});

    EXPECT_TRUE(execute_cleanup(reg, plan, CleanupConfig{}, kNow).empty());
    EXPECT_EQ(log_count(tmp, "world = 'open-then-held'"), "1");
    EXPECT_EQ(log_count(tmp, "world = 'open-then-held' AND reason = 'held_snapshot'"), "1");
    EXPECT_EQ(log_count(tmp, "world = 'held-then-dropped'"), "0");
    EXPECT_EQ(log_count(tmp, "world = 'fresh'"), "0");
    EXPECT_EQ(log_count(tmp, "world = 'still-open' AND reason = 'open'"), "1");
}

// 裁定 R72 M2 的对称面：补删只删生成的 dir_id，所以第 b 步也只删生成的。可回收世界的 dir_id 不是生成的形状（手改过的
// 注册表）时，锁内核对就跳过、记 failed，注册项与目录都不动；否则摘了注册项、目录删不掉也补删不了，成了永久孤儿。
TEST(Cleanup, NonGeneratedDirIdIsSkippedNotOrphaned) {
    const TempDir tmp;
    auto reg = open_db(tmp);
    reg.set_dir_id_source_for_test(fixed_dir_ids({"legacy-1"}));
    reclaimable(reg, "legacy", "g", kStale);
    reg.set_dir_id_source_for_test({});
    ASSERT_EQ(reg.get("legacy").dir_id, "legacy-1");
    const auto plan = plan_cleanup(reg, CleanupConfig{}, kNow, {});
    ASSERT_EQ(names_of(plan.remove), std::vector<std::string>{"legacy"});

    EXPECT_TRUE(execute_cleanup(reg, plan, CleanupConfig{}, kNow).empty());
    EXPECT_NO_THROW((void)reg.get("legacy"));
    EXPECT_TRUE(fs::exists(home_of(tmp, "legacy-1")));
    EXPECT_EQ(log_count(tmp, "world = 'legacy' AND action = 'skipped' AND reason = 'failed'"), "1");
    EXPECT_EQ(log_count(tmp, "pending_dir = 1"), "0");
}

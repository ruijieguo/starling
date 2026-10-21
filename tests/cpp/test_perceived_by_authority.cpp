// test_perceived_by_authority.cpp — 形态 S §3.4b：来源 engram 的听众是 perceived_by 的唯一权威。
//
// 钉住三件事：
//   1. 来源 engram（source_unit_meta 有记录）：perceived_by = 写入时展开后的听众，
//      不是 {holder, interlocutor}——三方场景下推断会漏掉第三人或多出旁人。
//   2. 非来源 engram（普通 remember）：两方 / 单方回退逐字节不变（硬门）。
//   3. 只覆盖 perceived_by；scope_parties（grounding 群体）保持原推断。
// 租户隔离不在此测：engrams.id 全局唯一 + source_unit_meta 外键开启，跨租户同名 engram
// 在库里不可构造；查询同时按 tenant_id 过滤。
// 零网络（FakeLLM），:memory: 库。
#include "starling/extractor/extractor.hpp"

#include "starling/extractor/fake_llm_adapter.hpp"
#include "starling/retrieval/source_retriever.hpp"
#include "starling/tom/belief_tracker.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <gtest/gtest.h>
#include <nlohmann/json.hpp>
#include <algorithm>
#include <memory>
#include <string>
#include <vector>

namespace starling::extractor {
namespace {

constexpr const char* kOneStatementJson =
    R"JSON([{"holder":"self","holder_perspective":"FIRST_PERSON","subject":"Bob","predicate":"responsible_for","object":"auth","modality":"BELIEVES","polarity":"POS","nesting_depth":0}])JSON";

std::unique_ptr<persistence::SqliteAdapter> make_adapter() {
    auto adapter = persistence::SqliteAdapter::open(":memory:");
    persistence::MigrationRunner(adapter->connection().raw()).migrate_to_latest();
    return adapter;
}

void exec(persistence::Connection& conn, const std::string& sql) {
    char* err = nullptr;
    const int status = sqlite3_exec(conn.raw(), sql.c_str(), nullptr, nullptr, &err);
    ASSERT_EQ(status, SQLITE_OK) << (err != nullptr ? err : "") << "\nSQL: " << sql;
}

void seed_engram(persistence::Connection& conn, const std::string& engram_id,
                 const std::string& tenant) {
    exec(conn,
        "INSERT INTO engrams(id,tenant_id,content_hash,source_kind,ingest_policy,"
        "ingest_mode,privacy_class,retention_mode,refcount,payload_inline,created_at)"
        " VALUES('" + engram_id + "','" + tenant + "','hash-" + engram_id + "-" + tenant +
        "','user_input','store','whole_record','internal','audit_retain',0,X'',"
        "'2026-05-23T10:00:00Z')");
}

void seed_meta(persistence::Connection& conn, const std::string& engram, const std::string& tenant,
               const std::string& clause, const std::string& audience_json) {
    exec(conn,
        "INSERT INTO source_unit_meta(tenant_id,engram_ref,clause_id,speaker,session_id,"
        "audience_json,turn_index,observed_at,provenance) VALUES('" + tenant + "','" + engram +
        "','" + clause + "','alice','scene-1','" + audience_json + "',0,"
        "'2026-05-23T10:00:00Z','source_time')");
}

std::vector<std::string> query_text(persistence::Connection& conn, const std::string& sql) {
    std::vector<std::string> out;
    sqlite3_stmt* raw = nullptr;
    EXPECT_EQ(sqlite3_prepare_v2(conn.raw(), sql.c_str(), -1, &raw, nullptr), SQLITE_OK) << sql;
    persistence::StmtHandle handle(raw);
    while (sqlite3_step(handle.get()) == SQLITE_ROW) {
        const unsigned char* text = sqlite3_column_text(handle.get(), 0);
        // NOLINTNEXTLINE(cppcoreguidelines-pro-type-reinterpret-cast)
        out.emplace_back(text != nullptr ? reinterpret_cast<const char*>(text) : "<null>");
    }
    return out;
}

std::vector<std::string> column_values(persistence::Connection& conn, const std::string& column,
                                       const std::string& tenant) {
    std::vector<std::string> out;
    sqlite3_stmt* raw = nullptr;
    const std::string sql = "SELECT " + column + " FROM statements WHERE tenant_id='" +
                            tenant + "' ORDER BY rowid";
    EXPECT_EQ(sqlite3_prepare_v2(conn.raw(), sql.c_str(), -1, &raw, nullptr), SQLITE_OK) << sql;
    persistence::StmtHandle handle(raw);
    while (sqlite3_step(handle.get()) == SQLITE_ROW) {
        const unsigned char* text = sqlite3_column_text(handle.get(), 0);
        // NOLINTNEXTLINE(cppcoreguidelines-pro-type-reinterpret-cast)
        out.emplace_back(text != nullptr ? reinterpret_cast<const char*>(text) : "<null>");
    }
    return out;
}

// 跑一次完整 run()，返回该租户所有语句的 perceived_by_json。
std::vector<std::string> run_once(persistence::SqliteAdapter& adapter, const std::string& engram,
                                  const std::string& holder, const std::string& tenant,
                                  const std::string& interlocutor) {
    FakeLLMAdapter llm;
    llm.set_default_response(LLMResponse{.raw_xml = kOneStatementJson, .ok = true});
    Extractor extractor(adapter.connection(), llm);
    extractor.run(engram, {1, 2, 3}, holder, tenant, {}, interlocutor);
    return column_values(adapter.connection(), "perceived_by_json", tenant);
}

}  // namespace

// ── 1. 来源 engram：听众是权威 ────────────────────────────────────────────────

TEST(PerceivedByAuthority, SourceEngramUsesWrittenAudienceNotPairInference) {
    auto adapter = make_adapter();
    seed_engram(adapter->connection(), "engram-1", "default");
    // 三方场景：alice 对 bob、carol 说话；holder=bob，interlocutor=alice。
    // 旧推断会得到 ["alice","bob"]，漏掉 carol。
    seed_meta(adapter->connection(), "engram-1", "default", "c0", R"(["alice","bob","carol"])");
    const auto rows = run_once(*adapter, "engram-1", "bob", "default", "alice");
    ASSERT_EQ(rows.size(), 1U);
    EXPECT_EQ(rows[0], R"(["alice","bob","carol"])");
}

TEST(PerceivedByAuthority, SourceAudienceNarrowerThanPairIsNotWidened) {
    // 权威听众比推断更窄时也必须服从：不能因为 interlocutor 非空就把旁人加进来。
    auto adapter = make_adapter();
    seed_engram(adapter->connection(), "engram-1", "default");
    seed_meta(adapter->connection(), "engram-1", "default", "c0", R"(["bob"])");
    const auto rows = run_once(*adapter, "engram-1", "bob", "default", "mallory");
    ASSERT_EQ(rows.size(), 1U);
    EXPECT_EQ(rows[0], R"(["bob"])");
}

TEST(PerceivedByAuthority, MultipleUnitsSameAudienceDeduplicated) {
    auto adapter = make_adapter();
    seed_engram(adapter->connection(), "engram-1", "default");
    seed_meta(adapter->connection(), "engram-1", "default", "c0", R"(["alice","bob"])");
    seed_meta(adapter->connection(), "engram-1", "default", "c1", R"(["alice","bob"])");
    const auto rows = run_once(*adapter, "engram-1", "bob", "default", "");
    ASSERT_EQ(rows.size(), 1U);
    EXPECT_EQ(rows[0], R"(["alice","bob"])");
}

TEST(PerceivedByAuthority, InconsistentUnitAudiencesAreUnionedSorted) {
    // 正常写入路径不会产生（按听众分组），但若绕过写入路径，取并集而非静默选一个。
    auto adapter = make_adapter();
    seed_engram(adapter->connection(), "engram-1", "default");
    seed_meta(adapter->connection(), "engram-1", "default", "c0", R"(["carol","alice"])");
    seed_meta(adapter->connection(), "engram-1", "default", "c1", R"(["bob"])");
    const auto rows = run_once(*adapter, "engram-1", "bob", "default", "");
    ASSERT_EQ(rows.size(), 1U);
    EXPECT_EQ(rows[0], R"(["alice","bob","carol"])");
}

TEST(PerceivedByAuthority, CorruptAudienceJsonFallsBackToInference) {
    auto adapter = make_adapter();
    seed_engram(adapter->connection(), "engram-1", "default");
    seed_meta(adapter->connection(), "engram-1", "default", "c0", "not-json");
    const auto rows = run_once(*adapter, "engram-1", "bob", "default", "alice");
    ASSERT_EQ(rows.size(), 1U);
    EXPECT_EQ(rows[0], R"(["alice","bob"])");
}

// ── 2. 非来源 engram：回退逐字节不变（硬门） ──────────────────────────────────

TEST(PerceivedByAuthority, PlainRememberTwoPartyFallbackUnchanged) {
    auto adapter = make_adapter();
    seed_engram(adapter->connection(), "engram-1", "default");
    const auto rows = run_once(*adapter, "engram-1", "bob", "default", "alice");
    ASSERT_EQ(rows.size(), 1U);
    EXPECT_EQ(rows[0], R"(["alice","bob"])");
}

TEST(PerceivedByAuthority, PlainRememberSoloFallbackUnchanged) {
    auto adapter = make_adapter();
    seed_engram(adapter->connection(), "engram-1", "default");
    const auto rows = run_once(*adapter, "engram-1", "cog-self", "default", "");
    ASSERT_EQ(rows.size(), 1U);
    EXPECT_EQ(rows[0], R"(["cog-self"])");
}

// ── 3. scope_parties 不受影响 ────────────────────────────────────────────────

TEST(PerceivedByAuthority, ScopePartiesKeepsPairInferenceForSourceEngram) {
    auto adapter = make_adapter();
    seed_engram(adapter->connection(), "engram-1", "default");
    seed_meta(adapter->connection(), "engram-1", "default", "c0", R"(["alice","bob","carol"])");
    run_once(*adapter, "engram-1", "bob", "default", "alice");
    const auto scope = column_values(adapter->connection(), "scope_parties_json", "default");
    ASSERT_EQ(scope.size(), 1U);
    EXPECT_EQ(scope[0], R"(["alice","bob"])");
}

// ── 端到端：左脑先写、右脑后读，两条可见性路径都以听众为准 ────────────────────
//
// perceived_by 不只写 presence_log，还写 cognizer_frontier_facts 的 explicit_told
// （belief_tracker_handlers.cpp）。两者都是 visible_engrams_at 的并集分支，任一处
// 放宽都会静默扩大可见性。这里跑完整链路：retain（元数据 + 在场）→ 抽取（语句）
// → belief_tracker tick（explicit_told），断言两条路径都恰好等于听众。
TEST(PerceivedByAuthority, EndToEndLeftBrainAudienceGovernsBothVisibilityPaths) {
    auto adapter = make_adapter();
    auto& conn = adapter->connection();

    // 1. 左脑：三方场景，alice 说给 alice/bob/carol 听。
    const auto turns = nlohmann::json::array({{
        {"speaker", "alice"}, {"text", "the code is 4321"}, {"session_id", "scene-1"},
        {"turn_index", 0}, {"audience", {"alice", "bob", "carol"}},
        {"provenance", "source_time"}, {"turn_id", nullptr},
        {"observed_at", "2026-05-23T10:00:00Z"}}}).dump();
    const auto retained = nlohmann::json::parse(
        retrieval::retain_source_turns(*adapter, "default", {"alice", "bob", "carol"},
                                       turns, "2026-05-23T10:00:00Z"));
    const std::string engram = retained["engram_refs"][0].get<std::string>();

    // 2. 右脑：holder=bob、interlocutor=alice。若仍靠推断会得到 {alice,bob}，丢 carol。
    const auto perceived = run_once(*adapter, engram, "bob", "default", "alice");
    ASSERT_EQ(perceived.size(), 1U);
    EXPECT_EQ(perceived[0], R"(["alice","bob","carol"])");

    // 3. belief_tracker 消费 statement.written，按 perceived_by 写 explicit_told。
    const auto stats = tom::belief_tracker::tick_one_batch(*adapter);
    ASSERT_GE(stats.events_processed, 1);

    const auto told = query_text(conn,
        "SELECT cognizer_id FROM cognizer_frontier_facts WHERE tenant_id='default'"
        " AND fact_kind='explicit_told'");
    // 返回值按 rowid 序，先排序再比。
    std::vector<std::string> sorted(told.begin(), told.end());
    std::sort(sorted.begin(), sorted.end());
    EXPECT_EQ(sorted, (std::vector<std::string>{"alice", "bob", "carol"}));
}

}  // namespace starling::extractor

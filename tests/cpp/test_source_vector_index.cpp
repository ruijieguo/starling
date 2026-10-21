// 形态 S §5.2：SourceVectorIndex 的 SQLite 后端（全量扫描 + 排序，与
// SqliteBlobVectorIndex 同构）。
//
// 钉住六件事：
//   1. 写入后按余弦相似度取回，命中带 engram_ref/clause_id/speaker/session_id/score；
//   2. 感知过滤先于排序生效——不可见的 engram 即使更相似也不出现；
//   3. dim 不匹配的查询向量不参与（避免跨模型静默比错）；
//   4. 非 embedded（pending/failed）的行不参与检索；
//   5. erase 后不再返回；
//   6. observed_at 为 NULL 的 unit 默认不参与（include_unknown_time 才放行），
//      且 as_of 之前/之后的 unit 各自正确。
#include "starling/vector/source_vector_index.hpp"

#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <gtest/gtest.h>
#include <chrono>
#include <iostream>
#include <memory>
#include <set>
#include <string>
#include <vector>

namespace starling::vector {
namespace {

constexpr auto kTenant = "default";
constexpr auto kModel = "stub-v1";

std::unique_ptr<persistence::SqliteAdapter> make_adapter() {
    auto adapter = persistence::SqliteAdapter::open(":memory:");
    persistence::MigrationRunner(adapter->connection().raw()).migrate_to_latest();
    return adapter;
}

// 一条已嵌入的 unit：元数据 + 向量。
struct Unit {
    std::string engram_ref;
    std::string clause_id;
    std::string speaker = "alice";
    std::string session_id = "scene-1";
    std::string observed_at = "2026-05-01T00:00:00Z";
    std::vector<float> vec;
};

// 显式构造而非聚合初始化：字段多且相邻同型，聚合写法易错位。
Unit make_unit(std::string engram_ref, std::string clause_id, std::vector<float> vec,
               std::string observed_at = "2026-05-01T00:00:00Z") {
    Unit unit;
    unit.engram_ref = std::move(engram_ref);
    unit.clause_id = std::move(clause_id);
    unit.observed_at = std::move(observed_at);
    unit.vec = std::move(vec);
    return unit;
}

void insert_meta(persistence::Connection& conn, const Unit& unit) {
    sqlite3_stmt* raw = nullptr;
    ASSERT_EQ(sqlite3_prepare_v2(conn.raw(),
        // adapter_name/source_item_id 等由 0003 加列，默认空串；而 0003 的唯一索引
        // 建在 (tenant, adapter, item, version, chunk) 上——不显式给唯一值的话，
        // 库里第二个 engram 就会撞唯一约束（表现为静默只插入一条）。
        "INSERT INTO engrams(id,tenant_id,content_hash,source_kind,ingest_policy,"
        "ingest_mode,privacy_class,retention_mode,refcount,payload_inline,created_at,"
        "adapter_name,source_item_id) "
        " VALUES(?1,?2,?3,'user_input','store','whole_record','internal','audit_retain',0,X'',"
        "'2026-01-01T00:00:00Z','test-adapter',?1) ON CONFLICT(id) DO NOTHING",
        -1, &raw, nullptr), SQLITE_OK);
    sqlite3_bind_text(raw, 1, unit.engram_ref.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, 2, kTenant, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, 3, ("hash-" + unit.engram_ref).c_str(), -1, SQLITE_TRANSIENT);
    ASSERT_EQ(sqlite3_step(raw), SQLITE_DONE) << sqlite3_errmsg(conn.raw());
    sqlite3_finalize(raw);

    ASSERT_EQ(sqlite3_prepare_v2(conn.raw(),
        "INSERT INTO source_unit_meta(tenant_id,engram_ref,clause_id,speaker,session_id,"
        "audience_json,turn_index,observed_at,provenance)"
        " VALUES(?1,?2,?3,?4,?5,'[\"alice\"]',0,?6,'source_time')", -1, &raw, nullptr),
        SQLITE_OK);
    sqlite3_bind_text(raw, 1, kTenant, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, 2, unit.engram_ref.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, 3, unit.clause_id.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, 4, unit.speaker.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, 5, unit.session_id.c_str(), -1, SQLITE_TRANSIENT);
    if (unit.observed_at.empty()) {
        sqlite3_bind_null(raw, 6);
    } else {
        sqlite3_bind_text(raw, 6, unit.observed_at.c_str(), -1, SQLITE_TRANSIENT);
    }
    sqlite3_step(raw);
    sqlite3_finalize(raw);
}

SourceUnitKey key_of(const Unit& unit) {
    SourceUnitKey key;
    key.tenant_id = kTenant;
    key.engram_ref = unit.engram_ref;
    key.clause_id = unit.clause_id;
    return key;
}

SourceUnitMeta meta_of(const Unit& unit) {
    SourceUnitMeta meta;
    meta.speaker = unit.speaker;
    meta.session_id = unit.session_id;
    meta.observed_at = unit.observed_at;
    return meta;
}

SourceSearchScope scope(std::set<std::string> visible) {
    SourceSearchScope search_scope;
    search_scope.tenant_id = kTenant;
    search_scope.visible_engrams = std::move(visible);
    search_scope.as_of = "2026-12-31T00:00:00Z";
    return search_scope;
}

std::vector<std::string> hit_clauses(const std::vector<SourceVectorHit>& hits) {
    std::vector<std::string> out;
    out.reserve(hits.size());
    for (const auto& hit : hits) out.push_back(hit.clause_id);
    return out;
}

}  // namespace

TEST(SourceVectorIndex, RoundTripsAndRanksByCosine) {
    auto adapter = make_adapter();
    SqliteSourceVectorIndex index;
    auto& conn = adapter->connection();

    Unit near_unit = make_unit("engram-1", "c0", {1.0F, 0.0F});
    Unit far_unit = make_unit("engram-1", "c1", {0.0F, 1.0F});
    far_unit.speaker = "bob";
    for (const auto& unit : {near_unit, far_unit}) {
        insert_meta(conn, unit);
        index.upsert(conn, key_of(unit), meta_of(unit), unit.vec, kModel,
                     static_cast<int>(unit.vec.size()));
    }

    const auto hits = index.search(conn, {1.0F, 0.0F}, 10, scope({"engram-1"}));
    ASSERT_EQ(hits.size(), 2U);
    EXPECT_EQ(hits[0].clause_id, "c0");
    EXPECT_GT(hits[0].score, hits[1].score);
    EXPECT_EQ(hits[0].engram_ref, "engram-1");
    EXPECT_EQ(hits[0].speaker, "alice");
    EXPECT_EQ(hits[0].session_id, "scene-1");
}

TEST(SourceVectorIndex, VisibilityFilterRunsBeforeRanking) {
    auto adapter = make_adapter();
    SqliteSourceVectorIndex index;
    auto& conn = adapter->connection();

    // c0 更相似但不可见；c1 稍弱但可见。
    Unit hidden = make_unit("engram-hidden", "c0", {1.0F, 0.0F});
    Unit visible = make_unit("engram-visible", "c1", {0.9F, 0.1F});
    for (const auto& unit : {hidden, visible}) {
        insert_meta(conn, unit);
        index.upsert(conn, key_of(unit), meta_of(unit), unit.vec, kModel,
                     static_cast<int>(unit.vec.size()));
    }

    const auto hits = index.search(conn, {1.0F, 0.0F}, 10, scope({"engram-visible"}));
    ASSERT_EQ(hits.size(), 1U);
    EXPECT_EQ(hits[0].engram_ref, "engram-visible");
}

TEST(SourceVectorIndex, EmptyVisibleSetReturnsNothing) {
    auto adapter = make_adapter();
    SqliteSourceVectorIndex index;
    auto& conn = adapter->connection();
    Unit unit = make_unit("engram-1", "c0", {1.0F, 0.0F});
    insert_meta(conn, unit);
    index.upsert(conn, key_of(unit), meta_of(unit), unit.vec, kModel, 2);

    // 空可见集 = 什么都不授权（fail closed），不是"不过滤"。
    EXPECT_TRUE(index.search(conn, {1.0F, 0.0F}, 10, scope({})).empty());
}

TEST(SourceVectorIndex, DimensionMismatchIsExcluded) {
    auto adapter = make_adapter();
    SqliteSourceVectorIndex index;
    auto& conn = adapter->connection();
    Unit unit = make_unit("engram-1", "c0", {1.0F, 0.0F, 0.0F});
    insert_meta(conn, unit);
    index.upsert(conn, key_of(unit), meta_of(unit), unit.vec, kModel, 3);

    EXPECT_TRUE(index.search(conn, {1.0F, 0.0F}, 10, scope({"engram-1"})).empty());
}

TEST(SourceVectorIndex, NonEmbeddedRowsAreExcluded) {
    auto adapter = make_adapter();
    SqliteSourceVectorIndex index;
    auto& conn = adapter->connection();
    Unit unit = make_unit("engram-1", "c0", {1.0F, 0.0F});
    insert_meta(conn, unit);
    index.upsert(conn, key_of(unit), meta_of(unit), unit.vec, kModel, 2);
    // 生命周期把该行退回 pending（例如重试中），检索必须看不见它。
    sqlite3_exec(conn.raw(),
        "UPDATE source_unit_vectors SET status='pending'", nullptr, nullptr, nullptr);

    EXPECT_TRUE(index.search(conn, {1.0F, 0.0F}, 10, scope({"engram-1"})).empty());
}

TEST(SourceVectorIndex, EraseRemovesFromResults) {
    auto adapter = make_adapter();
    SqliteSourceVectorIndex index;
    auto& conn = adapter->connection();
    Unit unit = make_unit("engram-1", "c0", {1.0F, 0.0F});
    insert_meta(conn, unit);
    index.upsert(conn, key_of(unit), meta_of(unit), unit.vec, kModel, 2);
    ASSERT_EQ(index.search(conn, {1.0F, 0.0F}, 10, scope({"engram-1"})).size(), 1U);

    index.erase(conn, kTenant, "engram-1");
    EXPECT_TRUE(index.search(conn, {1.0F, 0.0F}, 10, scope({"engram-1"})).empty());
}

TEST(SourceVectorIndex, TimeBoundsExcludeUnknownAndFutureUnits) {
    auto adapter = make_adapter();
    SqliteSourceVectorIndex index;
    auto& conn = adapter->connection();

    Unit known = make_unit("engram-1", "c0", {1.0F, 0.0F});
    Unit unknown = make_unit("engram-1", "c1", {1.0F, 0.0F}, "");
    Unit future = make_unit("engram-1", "c2", {1.0F, 0.0F}, "2027-01-01T00:00:00Z");
    for (const auto& unit : {known, unknown, future}) {
        insert_meta(conn, unit);
        index.upsert(conn, key_of(unit), meta_of(unit), unit.vec, kModel, 2);
    }

    // as_of 内的只有 c0；无可信时间的 c1 默认不参与；c2 在未来。
    auto hits = index.search(conn, {1.0F, 0.0F}, 10, scope({"engram-1"}));
    EXPECT_EQ(hit_clauses(hits), (std::vector<std::string>{"c0"}));

    auto relaxed = scope({"engram-1"});
    relaxed.include_unknown_time = true;
    hits = index.search(conn, {1.0F, 0.0F}, 10, relaxed);
    const auto clauses = hit_clauses(hits);
    EXPECT_EQ(clauses.size(), 2U);
    EXPECT_NE(std::find(clauses.begin(), clauses.end(), "c1"), clauses.end());
    EXPECT_EQ(std::find(clauses.begin(), clauses.end(), "c2"), clauses.end());
}

TEST(SourceVectorIndex, OtherTenantIsInvisible) {
    auto adapter = make_adapter();
    SqliteSourceVectorIndex index;
    auto& conn = adapter->connection();
    Unit unit = make_unit("engram-1", "c0", {1.0F, 0.0F});
    insert_meta(conn, unit);
    index.upsert(conn, key_of(unit), meta_of(unit), unit.vec, kModel, 2);

    auto other = scope({"engram-1"});
    other.tenant_id = "other";
    EXPECT_TRUE(index.search(conn, {1.0F, 0.0F}, 10, other).empty());
}

// 延迟基准（§5.2 验收项）：SQLite 后端是全量扫描 + 排序，延迟随 unit 数线性增长。
// 这里只打印 p50 供记录，不设阈值——机器差异太大，设阈值会产生假红；
// 真正的护栏是"曲线形状"：10k 不应比 1k 慢一个数量级。
TEST(SourceVectorIndex, LatencyCurveIsRecorded) {
    constexpr int kDim = 64;
    const auto measure = [](int units) {
        auto adapter = make_adapter();
        SqliteSourceVectorIndex index;
        auto& conn = adapter->connection();
        std::vector<float> vec(static_cast<std::size_t>(kDim), 0.1F);
        std::string engram = "engram-lat";
        // 单引号包裹包住整轮写入，避免 10k 次自动提交。
        sqlite3_exec(conn.raw(), "BEGIN", nullptr, nullptr, nullptr);
        for (int pos = 0; pos < units; ++pos) {
            Unit unit = make_unit(engram, "c" + std::to_string(pos), vec);
            insert_meta(conn, unit);
            index.upsert(conn, key_of(unit), meta_of(unit), unit.vec, kModel, kDim);
        }
        sqlite3_exec(conn.raw(), "COMMIT", nullptr, nullptr, nullptr);

        std::vector<double> samples;
        samples.reserve(5);
        for (int rep = 0; rep < 5; ++rep) {
            const auto started = std::chrono::steady_clock::now();
            const auto hits = index.search(conn, vec, 20, scope({engram}));
            const auto elapsed = std::chrono::steady_clock::now() - started;
            EXPECT_EQ(hits.size(), 20U);
            samples.push_back(
                std::chrono::duration<double, std::milli>(elapsed).count());
        }
        std::ranges::sort(samples);
        return samples[samples.size() / 2];
    };

    const double p50_1k = measure(1000);
    const double p50_10k = measure(10000);
    std::cout << "SOURCE_INDEX_LATENCY p50: 1k=" << p50_1k << "ms 10k=" << p50_10k
              << "ms\n";
    EXPECT_GT(p50_1k, 0.0);
    EXPECT_GT(p50_10k, 0.0);
}

}  // namespace starling::vector

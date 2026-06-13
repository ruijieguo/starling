// P3.b1 phase 1:store 抽象地基。钉 SqliteGraphStore(边写/邻居/冲突键查)+
// StoreBundle::open_local 装配与 ProfileCapability 声明。纯新增,无路由改动。
#include "starling/store/sqlite_graph_store.hpp"
#include "starling/store/store_bundle.hpp"
#include "starling/vector/vector_index.hpp"

#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <gtest/gtest.h>

#include <memory>

namespace starling::store {
namespace {

std::unique_ptr<persistence::SqliteAdapter> make_adapter() {
    auto a = persistence::SqliteAdapter::open(":memory:");
    persistence::MigrationRunner(a->connection().raw()).migrate_to_latest();
    return a;
}

EdgeRecord edge(const char* src, const char* dst, const char* kind,
                double w = 1.0, const char* ck = nullptr) {
    EdgeRecord r;
    r.tenant_id = "default"; r.src_id = src; r.dst_id = dst;
    r.edge_kind = kind; r.weight = w;
    if (ck) r.canonical_conflict_key = ck;
    return r;
}

}  // namespace

TEST(SqliteGraphStore, InsertAndNeighborsByKind) {
    auto a = make_adapter();
    SqliteGraphStore g(a->connection());
    const auto ins = g.insert_edge(edge("s1", "s2", "CONFLICTS_WITH", 0.9));
    EXPECT_FALSE(ins.id.empty());
    EXPECT_FALSE(ins.deduped);
    g.insert_edge(edge("s1", "s3", "MAY_OVERLAP_WITH", 0.4));
    g.insert_edge(edge("s1", "s4", "CONFLICTS_WITH", 0.7));

    // 不限 kind:三条邻居。
    EXPECT_EQ(g.neighbors("default", "s1", {}).size(), 3u);
    // 限 CONFLICTS_WITH:两条。
    const auto conf = g.neighbors("default", "s1", {"CONFLICTS_WITH"});
    ASSERT_EQ(conf.size(), 2u);
    for (const auto& e : conf) {
        EXPECT_EQ(e.src_id, "s1");
        EXPECT_EQ(e.edge_kind, "CONFLICTS_WITH");
    }
    // 多 kind 集合。
    EXPECT_EQ(g.neighbors("default", "s1",
                          {"CONFLICTS_WITH", "MAY_OVERLAP_WITH"}).size(), 3u);
    // 租户隔离:别的租户查不到。
    EXPECT_TRUE(g.neighbors("other", "s1", {}).empty());
}

TEST(SqliteGraphStore, EdgesByConflictKey) {
    auto a = make_adapter();
    SqliteGraphStore g(a->connection());
    g.insert_edge(edge("s1", "s2", "CONFLICTS_WITH", 0.9, "ck-abc"));
    g.insert_edge(edge("s3", "s4", "CONFLICTS_WITH", 0.8, "ck-abc"));
    g.insert_edge(edge("s5", "s6", "CONFLICTS_WITH", 0.7, "ck-xyz"));

    const auto hits = g.edges_by_conflict_key("default", "ck-abc");
    EXPECT_EQ(hits.size(), 2u);
    for (const auto& e : hits)
        ASSERT_TRUE(e.canonical_conflict_key && *e.canonical_conflict_key == "ck-abc");
    EXPECT_EQ(g.edges_by_conflict_key("default", "ck-none").size(), 0u);
}

TEST(SqliteGraphStore, InsertConflictsWithDedupOnConflictKey) {
    auto a = make_adapter();
    SqliteGraphStore g(a->connection());
    // 小写 conflicts_with + 非空 key 命中 0009 partial UNIQUE index。
    const auto first = g.insert_edge(edge("s1", "s2", "conflicts_with", 0.9, "ck-1"));
    EXPECT_FALSE(first.id.empty());
    EXPECT_FALSE(first.deduped);
    // 同 tenant + conflict_key → UNIQUE 命中,静默 dedup,不插入(spec §8.4)。
    const auto dup = g.insert_edge(edge("s3", "s4", "conflicts_with", 0.5, "ck-1"));
    EXPECT_TRUE(dup.id.empty());
    EXPECT_TRUE(dup.deduped);
    EXPECT_EQ(g.edges_by_conflict_key("default", "ck-1").size(), 1u);
}

TEST(StoreBundle, OpenLocalWiresThreeCategories) {
    auto a = make_adapter();
    vector::SqliteBlobVectorIndex vidx;
    StoreBundle bundle = StoreBundle::open_local(*a, vidx);

    // 三类句柄就位。
    EXPECT_EQ(&bundle.meta_adapter(), a.get());
    EXPECT_EQ(&bundle.vector(), &vidx);
    // graph store 可用(经 bundle 写一条边再读回)。
    bundle.graph().insert_edge(edge("a", "b", "supersedes"));
    EXPECT_EQ(bundle.graph().neighbors("default", "a", {}).size(), 1u);

    // 能力声明:local-store,三 backend 名,outbox/checkpoint 就绪。
    const auto& cap = bundle.capability();
    EXPECT_EQ(cap.profile_name, "local-store");
    EXPECT_EQ(cap.meta_backend, "sqlite");
    EXPECT_EQ(cap.vector_backend, "sqlite");
    EXPECT_EQ(cap.graph_backend, "sqlite");
    EXPECT_TRUE(cap.transactional_outbox);
    EXPECT_TRUE(cap.consumer_checkpoint);
}

}  // namespace starling::store

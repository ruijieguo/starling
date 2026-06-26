// #38-C Phase 1 — deterministic NORM-gist clustering (no LLM, no write).
// Pins: K-holder threshold, T replay floor, live-state/review filtering,
// seed-from-batch scoping, tenant isolation, idempotency, determinism.
#include "starling/replay/gist_clustering.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
#include <sqlite3.h>
#include <sstream>
#include <string>
#include <vector>

using namespace starling::replay;
using starling::persistence::SqliteAdapter;

namespace {

// A seed row with sane defaults; override only what a test cares about via
// C++20 designated initializers, e.g. seed(db, {.id="s1", .holder="bob"}).
struct Row {
    std::string id;                       // may be computed (owned by the aggregate)
    const char* holder = "alice";
    const char* tenant = "default";
    const char* predicate = "likes";
    char        hashfill = 'a';           // 64-char canonical_object_hash filler
    int         replay_count = 2;
    const char* state = "volatile";       // consolidation_state
    const char* review = "approved";      // review_status
    const char* provenance = "user_input";
    const char* object_kind = "str";
    const char* object_value = "coffee";
};

void seed(sqlite3* db, const Row& row) {
    std::ostringstream query;
    query << "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
             "subject_kind,subject_id,predicate,object_kind,object_value,"
             "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
             "confidence,observed_at,salience,affect_json,activation,last_accessed,"
             "provenance,replay_count,consolidation_state,review_status,access_count,"
             "created_at,updated_at) VALUES('"
          << row.id << "','" << row.tenant << "','" << row.holder << "','first_person',"
             "'cognizer','subj','" << row.predicate << "','" << row.object_kind << "','"
          << row.object_value << "','" << std::string(64, row.hashfill) << "','v1',"
             "'believes','pos',0.9,'2026-05-27T09:00:00Z',0.5,'{}',0.0,"
             "'2026-05-27T09:00:00Z','" << row.provenance << "'," << row.replay_count
          << ",'" << row.state << "','" << row.review << "',1,"
             "'2026-05-27T09:00:00Z','2026-05-27T09:00:00Z')";
    char* err = nullptr;
    const int rc = sqlite3_exec(db, query.str().c_str(), nullptr, nullptr, &err);
    if (rc != SQLITE_OK) {
        ADD_FAILURE() << "seed failed: " << (err ? err : "?");
        sqlite3_free(err);
    }
}

// Insert an already-written gist (provenance='consolidation_abstract') for the
// idempotency guard: a key that already produced a gist must not re-cluster.
void seed_existing_gist(sqlite3* db, const char* predicate, char hashfill) {
    seed(db, {.id = "gist_existing", .holder = "everyone", .predicate = predicate,
              .hashfill = hashfill, .state = "consolidated",
              .provenance = "consolidation_abstract"});
}

}  // namespace

// 3 distinct holders sharing (predicate, hash), each replayed >= T → one cluster.
// Members inserted out of id-order to prove the output is deterministically sorted.
TEST(GistClustering, FormsClusterAtHolderThreshold) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed(conn.raw(), {.id = "s3", .holder = "carol"});
    seed(conn.raw(), {.id = "s1", .holder = "alice"});
    seed(conn.raw(), {.id = "s2", .holder = "bob"});

    const auto clusters = find_norm_gist_clusters(conn, "default", {"s1"}, GistThresholds{});
    ASSERT_EQ(clusters.size(), 1u);
    EXPECT_EQ(clusters[0].predicate, "likes");
    EXPECT_EQ(clusters[0].object_value, "coffee");
    EXPECT_EQ(clusters[0].member_ids, (std::vector<std::string>{"s1", "s2", "s3"}));
    EXPECT_EQ(clusters[0].holder_ids, (std::vector<std::string>{"alice", "bob", "carol"}));
}

// Only 2 distinct holders → below K=3 → no cluster.
TEST(GistClustering, BelowHolderThresholdNoCluster) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed(conn.raw(), {.id = "s1", .holder = "alice"});
    seed(conn.raw(), {.id = "s2", .holder = "bob"});

    EXPECT_TRUE(find_norm_gist_clusters(conn, "default", {"s1"}, GistThresholds{}).empty());
}

// A member below the replay floor (T=2) is dropped; if that pushes distinct
// holders under K, no cluster forms.
TEST(GistClustering, MemberBelowReplayFloorExcluded) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed(conn.raw(), {.id = "s1", .holder = "alice", .replay_count = 2});
    seed(conn.raw(), {.id = "s2", .holder = "bob", .replay_count = 2});
    seed(conn.raw(), {.id = "s3", .holder = "carol", .replay_count = 1});  // below T

    EXPECT_TRUE(find_norm_gist_clusters(conn, "default", {"s1"}, GistThresholds{}).empty());

    // A 4th qualifying holder restores the threshold; carol stays excluded.
    seed(conn.raw(), {.id = "s4", .holder = "dave", .replay_count = 2});
    const auto clusters = find_norm_gist_clusters(conn, "default", {"s1"}, GistThresholds{});
    ASSERT_EQ(clusters.size(), 1u);
    EXPECT_EQ(clusters[0].member_ids, (std::vector<std::string>{"s1", "s2", "s4"}));
}

// Non-live consolidation_state (archived/forgotten) excludes a member.
TEST(GistClustering, ArchivedOrForgottenExcluded) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed(conn.raw(), {.id = "s1", .holder = "alice"});
    seed(conn.raw(), {.id = "s2", .holder = "bob"});
    seed(conn.raw(), {.id = "s3", .holder = "carol", .state = "archived"});
    EXPECT_TRUE(find_norm_gist_clusters(conn, "default", {"s1"}, GistThresholds{}).empty());

    seed(conn.raw(), {.id = "s4", .holder = "dave", .state = "forgotten"});
    EXPECT_TRUE(find_norm_gist_clusters(conn, "default", {"s1"}, GistThresholds{}).empty());
}

// Transient/contested consolidation states are deliberately NOT settled-norm
// members: 'replaying_consolidating' (mid-operation) and 'replaying_reconsolidating'
// (in conflict, under arbitration) are excluded so a contested belief never
// inflates a norm toward the K threshold.
TEST(GistClustering, ReplayingStatesExcluded) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed(conn.raw(), {.id = "s1", .holder = "alice"});
    seed(conn.raw(), {.id = "s2", .holder = "bob"});
    seed(conn.raw(), {.id = "s3", .holder = "carol", .state = "replaying_consolidating"});
    EXPECT_TRUE(find_norm_gist_clusters(conn, "default", {"s1"}, GistThresholds{}).empty());

    seed(conn.raw(), {.id = "s4", .holder = "dave", .state = "replaying_reconsolidating"});
    EXPECT_TRUE(find_norm_gist_clusters(conn, "default", {"s1"}, GistThresholds{}).empty());
}

// review_status rejected/pending_review excludes a member.
TEST(GistClustering, RejectedOrPendingReviewExcluded) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed(conn.raw(), {.id = "s1", .holder = "alice"});
    seed(conn.raw(), {.id = "s2", .holder = "bob"});
    seed(conn.raw(), {.id = "s3", .holder = "carol", .review = "rejected"});
    EXPECT_TRUE(find_norm_gist_clusters(conn, "default", {"s1"}, GistThresholds{}).empty());

    seed(conn.raw(), {.id = "s4", .holder = "dave", .review = "pending_review"});
    EXPECT_TRUE(find_norm_gist_clusters(conn, "default", {"s1"}, GistThresholds{}).empty());
}

// Idempotency: a key that already has a 'consolidation_abstract' gist is skipped,
// even though the underlying cluster still qualifies (control: without the gist
// row, the same data clusters).
TEST(GistClustering, ExistingGistSuppressesRecluster) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed(conn.raw(), {.id = "s1", .holder = "alice"});
    seed(conn.raw(), {.id = "s2", .holder = "bob"});
    seed(conn.raw(), {.id = "s3", .holder = "carol"});
    ASSERT_EQ(find_norm_gist_clusters(conn, "default", {"s1"}, GistThresholds{}).size(), 1u);

    seed_existing_gist(conn.raw(), "likes", 'a');
    EXPECT_TRUE(find_norm_gist_clusters(conn, "default", {"s1"}, GistThresholds{}).empty());
}

// Seed-from-batch: a qualifying cluster whose key is NOT in the replay batch is
// not detected; seeding one of its members makes the key "hot" and it surfaces.
TEST(GistClustering, OnlyClustersSeededKeys) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed(conn.raw(), {.id = "s1", .holder = "alice"});
    seed(conn.raw(), {.id = "s2", .holder = "bob"});
    seed(conn.raw(), {.id = "s3", .holder = "carol"});
    // A different, unrelated key used only as the seed.
    seed(conn.raw(), {.id = "other", .holder = "zed", .predicate = "fears",
                      .hashfill = 'z', .object_value = "spiders"});

    EXPECT_TRUE(find_norm_gist_clusters(conn, "default", {"other"}, GistThresholds{}).empty());
    EXPECT_EQ(find_norm_gist_clusters(conn, "default", {"s2"}, GistThresholds{}).size(), 1u);
}

// Tenant isolation: an identical key in another tenant is never mixed in.
TEST(GistClustering, TenantIsolation) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    for (const char* who : {"alice", "bob", "carol"}) {
        seed(conn.raw(), {.id = std::string("a_") + who, .holder = who, .tenant = "A"});
        seed(conn.raw(), {.id = std::string("b_") + who, .holder = who, .tenant = "B"});
    }
    const auto clusters = find_norm_gist_clusters(conn, "A", {"a_alice"}, GistThresholds{});
    ASSERT_EQ(clusters.size(), 1u);
    EXPECT_EQ(clusters[0].member_ids,
              (std::vector<std::string>{"a_alice", "a_bob", "a_carol"}));
}

// Two hot keys → two clusters, sorted by (predicate, hash) for determinism.
TEST(GistClustering, MultipleClustersSortedByKey) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    for (const char* who : {"alice", "bob", "carol"}) {
        seed(conn.raw(), {.id = std::string("l_") + who, .holder = who,
                          .predicate = "likes", .hashfill = 'a', .object_value = "coffee"});
        seed(conn.raw(), {.id = std::string("v_") + who, .holder = who,
                          .predicate = "avoids", .hashfill = 'b', .object_value = "tea"});
    }
    const auto clusters =
        find_norm_gist_clusters(conn, "default", {"l_alice", "v_bob"}, GistThresholds{});
    ASSERT_EQ(clusters.size(), 2u);
    EXPECT_EQ(clusters[0].predicate, "avoids");  // sorted before "likes"
    EXPECT_EQ(clusters[1].predicate, "likes");
}

// Empty batch → empty result (no full-table scan).
TEST(GistClustering, EmptySeedsEmpty) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed(conn.raw(), {.id = "s1", .holder = "alice"});
    EXPECT_TRUE(find_norm_gist_clusters(conn, "default", {}, GistThresholds{}).empty());
}

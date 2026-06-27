// #38-C Phase 2 — write a detected NORM gist as a derived Statement through the
// existing Bus::write pipeline. Pins: gist identity (common-ground holder,
// generic subject), provenance/derived_from/derived_depth stamping, the inert
// volatile+pending_review state, idempotency against a REAL written gist
// (Phase-1 guard fires), coexistence with the specific members, and that a
// failed proposal is counted (not silently swallowed) while the batch continues.
#include "starling/replay/gist_writer.hpp"
#include "starling/replay/gist_clustering.hpp"
#include "starling/replay/replay_scheduler.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/extractor/fake_llm_adapter.hpp"
#include "starling/extractor/llm_adapter.hpp"
#include <gtest/gtest.h>
#include <sqlite3.h>
#include <sstream>
#include <string>
#include <vector>

using namespace starling::replay;
using starling::persistence::SqliteAdapter;

namespace {

struct Row {
    std::string id;
    const char* holder = "alice";
    const char* tenant = "default";
    const char* predicate = "likes";
    char        hashfill = 'a';
    int         replay_count = 2;
    const char* state = "volatile";
    const char* review = "approved";
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
    if (sqlite3_exec(db, query.str().c_str(), nullptr, nullptr, &err) != SQLITE_OK) {
        ADD_FAILURE() << "seed failed: " << (err ? err : "?");
        sqlite3_free(err);
    }
}

// Seed a default-keyed 3-holder cluster (alice/bob/carol, "likes" coffee).
void seed_three_holder_cluster(sqlite3* db) {
    seed(db, {.id = "m1", .holder = "alice"});
    seed(db, {.id = "m2", .holder = "bob"});
    seed(db, {.id = "m3", .holder = "carol"});
}

std::string col_text(sqlite3* db, const std::string& sql) {
    sqlite3_stmt* stmt = nullptr;
    sqlite3_prepare_v2(db, sql.c_str(), -1, &stmt, nullptr);
    std::string out;
    if (sqlite3_step(stmt) == SQLITE_ROW) {
        const unsigned char* ptr = sqlite3_column_text(stmt, 0);
        if (ptr != nullptr) {
            out.assign(ptr, std::next(ptr, sqlite3_column_bytes(stmt, 0)));
        }
    }
    sqlite3_finalize(stmt);
    return out;
}

int col_int(sqlite3* db, const std::string& sql) {
    sqlite3_stmt* stmt = nullptr;
    sqlite3_prepare_v2(db, sql.c_str(), -1, &stmt, nullptr);
    int out = 0;
    if (sqlite3_step(stmt) == SQLITE_ROW) {
        out = sqlite3_column_int(stmt, 0);
    }
    sqlite3_finalize(stmt);
    return out;
}

const char* kGistWhere = "WHERE provenance='consolidation_abstract'";

}  // namespace

// A written gist carries the locked identity + provenance + lineage + inert state.
TEST(GistWriter, WritesGistWithCorrectIdentityAndProvenance) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_three_holder_cluster(conn.raw());

    const auto clusters = find_norm_gist_clusters(conn, "default", {"m1"}, GistThresholds{});
    ASSERT_EQ(clusters.size(), 1U);
    std::vector<GistProposal> proposals{{"default", clusters[0]}};

    const auto outcome = write_gist_proposals(*adapter, proposals, "2026-06-27T12:00:00Z");
    EXPECT_EQ(outcome.written, 1);
    EXPECT_EQ(outcome.failed, 0);

    sqlite3* db = conn.raw();
    EXPECT_EQ(col_int(db, std::string("SELECT COUNT(*) FROM statements ") + kGistWhere), 1);
    EXPECT_EQ(col_text(db, std::string("SELECT holder_id FROM statements ") + kGistWhere),
              "__common_ground__");
    EXPECT_EQ(col_text(db, std::string("SELECT subject_id FROM statements ") + kGistWhere),
              "__people__");
    EXPECT_EQ(col_text(db, std::string("SELECT predicate FROM statements ") + kGistWhere), "likes");
    EXPECT_EQ(col_text(db, std::string("SELECT object_value FROM statements ") + kGistWhere),
              "coffee");
    // Inert until Phase-4 gating. The robust guarantee is consolidation_state=
    // 'volatile': the consolidated-knowledge retrieval/ToM queries require
    // consolidated/archived, so a volatile gist is never surfaced. review_status
    // is pipeline-determined (pending_review for a core predicate, upgraded to
    // review_requested for a non-core one like this test's "likes") — the
    // invariant we assert is simply that it is never auto-approved.
    EXPECT_EQ(col_text(db, std::string("SELECT consolidation_state FROM statements ") + kGistWhere),
              "volatile");
    EXPECT_NE(col_text(db, std::string("SELECT review_status FROM statements ") + kGistWhere),
              "approved");
}

// derived_from = sorted cluster members; derived_depth = max(member depth)+1.
TEST(GistWriter, StampsDerivedFromAndDepth) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_three_holder_cluster(conn.raw());

    const auto clusters = find_norm_gist_clusters(conn, "default", {"m1"}, GistThresholds{});
    ASSERT_EQ(clusters.size(), 1U);
    write_gist_proposals(*adapter, {{"default", clusters[0]}}, "2026-06-27T12:00:00Z");

    sqlite3* db = conn.raw();
    EXPECT_EQ(col_text(db, std::string("SELECT derived_from_json FROM statements ") + kGistWhere),
              "[\"m1\",\"m2\",\"m3\"]");
    EXPECT_EQ(col_int(db, std::string("SELECT derived_depth FROM statements ") + kGistWhere), 1);
    // The specific members coexist — the gist does not supersede/delete them.
    EXPECT_EQ(col_int(db, "SELECT COUNT(*) FROM statements WHERE id IN ('m1','m2','m3')"), 3);
}

// A real written gist suppresses re-abstraction: Phase-1's idempotency guard
// fires against the actual 'consolidation_abstract' row, not just a planted one.
TEST(GistWriter, WrittenGistSuppressesRecluster) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_three_holder_cluster(conn.raw());

    auto clusters = find_norm_gist_clusters(conn, "default", {"m1"}, GistThresholds{});
    ASSERT_EQ(clusters.size(), 1U);
    ASSERT_EQ(write_gist_proposals(*adapter, {{"default", clusters[0]}},
                                   "2026-06-27T12:00:00Z").written, 1);

    // Same seeds, after the gist exists → the key is now suppressed.
    EXPECT_TRUE(find_norm_gist_clusters(conn, "default", {"m1"}, GistThresholds{}).empty());
    // Still exactly one gist (no duplicate even if a second write were attempted).
    sqlite3* db = conn.raw();
    EXPECT_EQ(col_int(db, std::string("SELECT COUNT(*) FROM statements ") + kGistWhere), 1);
}

// A proposal whose members do not exist is rejected by validate_for_write; it is
// COUNTED as failed (not silently swallowed) and the valid proposal still writes.
TEST(GistWriter, FailedProposalCountedBatchContinues) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_three_holder_cluster(conn.raw());

    const auto clusters = find_norm_gist_clusters(conn, "default", {"m1"}, GistThresholds{});
    ASSERT_EQ(clusters.size(), 1U);

    GistCluster bad;  // derived_from points at a non-existent parent
    bad.predicate = "fears";
    bad.canonical_object_hash = std::string(64, 'z');
    bad.object_kind = "str";
    bad.object_value = "spiders";
    bad.member_ids = {"does_not_exist"};
    bad.holder_ids = {"x", "y", "z"};

    const auto outcome = write_gist_proposals(
        *adapter, {{"default", bad}, {"default", clusters[0]}}, "2026-06-27T12:00:00Z");
    EXPECT_EQ(outcome.written, 1);
    EXPECT_EQ(outcome.failed, 1);
    sqlite3* db = conn.raw();
    EXPECT_EQ(col_int(db, std::string("SELECT COUNT(*) FROM statements ") + kGistWhere), 1);
}

// End-to-end through the scheduler: an offline sleep batch writes the gist.
TEST(GistWriter, RunSleepWritesGistEndToEnd) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_three_holder_cluster(conn.raw());

    ReplayScheduler sched(*adapter);
    const auto stats = sched.run_sleep(conn, "2026-06-27T12:00:00Z");
    EXPECT_GE(stats.abstracted, 1);  // at least the one gist written
    sqlite3* db = conn.raw();
    EXPECT_EQ(col_int(db, std::string("SELECT COUNT(*) FROM statements ") + kGistWhere), 1);
}

// The oscillation guard must never force-consolidate an ungated gist (a gist
// only enters 'consolidated' via Phase-4 gating). A non-gist with the same
// replay_count IS consolidated — proving the guard still works.
TEST(GistWriter, OscillationGuardSkipsGist) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed(conn.raw(), {.id = "g1", .holder = "__common_ground__", .replay_count = 5,
                      .provenance = "consolidation_abstract"});
    seed(conn.raw(), {.id = "n1", .holder = "alice", .replay_count = 5,
                      .provenance = "user_input"});

    ReplayScheduler(*adapter).enforce_oscillation_guard(conn);
    sqlite3* db = conn.raw();
    EXPECT_EQ(col_text(db, "SELECT consolidation_state FROM statements WHERE id='g1'"), "volatile");
    EXPECT_EQ(col_text(db, "SELECT consolidation_state FROM statements WHERE id='n1'"),
              "consolidated");
}

// The volatile TTL sweep must never archive an ungated gist (it must survive
// until Phase-4 gating). A non-gist of the same age IS archived.
TEST(GistWriter, VolatileTtlSweepSkipsGist) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    // seed() stamps created_at = 2026-05-27, well older than the 7-day cutoff.
    seed(conn.raw(), {.id = "g1", .holder = "__common_ground__",
                      .provenance = "consolidation_abstract"});
    seed(conn.raw(), {.id = "n1", .holder = "alice", .provenance = "user_input"});

    ReplayScheduler(*adapter).sweep_volatile_ttl(conn, "2026-06-27T12:00:00Z");
    sqlite3* db = conn.raw();
    EXPECT_EQ(col_text(db, "SELECT consolidation_state FROM statements WHERE id='g1'"), "volatile");
    EXPECT_EQ(col_text(db, "SELECT consolidation_state FROM statements WHERE id='n1'"), "archived");
}

// Phase 3: with a consolidation LLM, the gist takes the LLM's confidence and
// stores the LLM's one-sentence summary.
TEST(GistWriter, LlmJudgedGistGetsConfidenceAndSummary) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_three_holder_cluster(conn.raw());
    const auto clusters = find_norm_gist_clusters(conn, "default", {"m1"}, GistThresholds{});
    ASSERT_EQ(clusters.size(), 1U);

    starling::extractor::FakeLLMAdapter llm;
    llm.set_default_response(starling::extractor::LLMResponse{
        .raw_xml = R"({"confidence": 0.82, "summary": "People generally like coffee."})",
        .ok = true});

    const auto outcome =
        write_gist_proposals(*adapter, {{"default", clusters[0]}}, "2026-06-27T12:00:00Z", &llm);
    EXPECT_EQ(outcome.written, 1);
    EXPECT_EQ(outcome.failed, 0);
    sqlite3* db = conn.raw();
    EXPECT_EQ(col_int(db, std::string("SELECT COUNT(*) FROM statements ") + kGistWhere +
                          " AND ABS(confidence - 0.82) < 0.001"), 1);
    EXPECT_EQ(col_text(db, std::string("SELECT consolidation_summary FROM statements ") + kGistWhere),
              "People generally like coffee.");
}

// An LLM transport error skips the proposal (counted failed, no gist written) —
// an un-judged gist is never written; it is retried next cycle.
TEST(GistWriter, LlmErrorSkipsGist) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_three_holder_cluster(conn.raw());
    const auto clusters = find_norm_gist_clusters(conn, "default", {"m1"}, GistThresholds{});

    starling::extractor::FakeLLMAdapter llm;
    llm.set_default_response(starling::extractor::LLMResponse{.ok = false, .error = "boom"});

    const auto outcome =
        write_gist_proposals(*adapter, {{"default", clusters[0]}}, "2026-06-27T12:00:00Z", &llm);
    EXPECT_EQ(outcome.written, 0);
    EXPECT_EQ(outcome.failed, 1);
    EXPECT_EQ(col_int(conn.raw(), std::string("SELECT COUNT(*) FROM statements ") + kGistWhere), 0);
}

// An unparseable LLM reply skips the proposal too (no un-judged gist).
TEST(GistWriter, LlmUnparseableReplySkipsGist) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_three_holder_cluster(conn.raw());
    const auto clusters = find_norm_gist_clusters(conn, "default", {"m1"}, GistThresholds{});

    starling::extractor::FakeLLMAdapter llm;
    llm.set_default_response(starling::extractor::LLMResponse{.raw_xml = "no json here", .ok = true});

    const auto outcome =
        write_gist_proposals(*adapter, {{"default", clusters[0]}}, "2026-06-27T12:00:00Z", &llm);
    EXPECT_EQ(outcome.written, 0);
    EXPECT_EQ(outcome.failed, 1);
    EXPECT_EQ(col_int(conn.raw(), std::string("SELECT COUNT(*) FROM statements ") + kGistWhere), 0);
}

// No adapter ⇒ deterministic Phase-2 path: provisional confidence, NULL summary.
TEST(GistWriter, NullAdapterIsDeterministic) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_three_holder_cluster(conn.raw());
    const auto clusters = find_norm_gist_clusters(conn, "default", {"m1"}, GistThresholds{});

    write_gist_proposals(*adapter, {{"default", clusters[0]}}, "2026-06-27T12:00:00Z");  // no LLM
    sqlite3* db = conn.raw();
    EXPECT_EQ(col_int(db, std::string("SELECT COUNT(*) FROM statements ") + kGistWhere +
                          " AND ABS(confidence - 0.5) < 0.001"), 1);
    EXPECT_EQ(col_text(db, std::string("SELECT consolidation_summary FROM statements ") + kGistWhere),
              "");  // NULL → empty
}

// Online replay never writes a gist (it runs inside the post-write transaction).
TEST(GistWriter, OnlineTickNeverWritesGist) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_three_holder_cluster(conn.raw());

    ReplayScheduler sched(*adapter);
    // Drive several online ticks (kOnlineTrigger=3 → fires a sampling window).
    for (int i = 0; i < 5; ++i) {
        sched.tick_online(conn, "2026-06-27T12:00:00Z");
    }
    sqlite3* db = conn.raw();
    EXPECT_EQ(col_int(db, std::string("SELECT COUNT(*) FROM statements ") + kGistWhere), 0);
}

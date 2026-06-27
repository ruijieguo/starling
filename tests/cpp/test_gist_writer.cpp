// #38-C Phase 2 — write a detected NORM gist as a derived Statement through the
// existing Bus::write pipeline. Pins: gist identity (common-ground holder,
// generic subject), provenance/derived_from/derived_depth stamping, the inert
// volatile+pending_review state, idempotency against a REAL written gist
// (Phase-1 guard fires), coexistence with the specific members, and that a
// failed proposal is counted (not silently swallowed) while the batch continues.
#include "starling/replay/gist_writer.hpp"
#include "starling/replay/gist_clustering.hpp"
#include "starling/replay/replay_scheduler.hpp"
#include "starling/vector/vector_index.hpp"   // SqliteBlobVectorIndex (seed controlled vectors)
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/extractor/fake_llm_adapter.hpp"
#include "starling/extractor/llm_adapter.hpp"
#include "starling/store/sqlite_statement_store.hpp"
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

// Returns canned LLM responses in call order (1st = judge, 2nd = entailment
// verify), so a test can give the two gate calls DIFFERENT replies — proving the
// entailment verdict comes from the INDEPENDENT second call, not the judge's reply.
class SequencedLLM : public starling::extractor::LLMAdapter {
public:
    explicit SequencedLLM(std::vector<starling::extractor::LLMResponse> replies)
        : replies_(std::move(replies)) {}
    starling::extractor::LLMResponse extract(std::string_view, std::string_view) override {
        if (next_ < replies_.size()) {
            return replies_[next_++];
        }
        return starling::extractor::LLMResponse{.ok = false, .error = "seq_exhausted"};
    }
private:
    std::vector<starling::extractor::LLMResponse> replies_;
    std::size_t next_ = 0;
};

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

// #38-C fix: run_sleep must seed the NORM scan from SETTLED (consolidated) beliefs,
// not only the transient volatile batch. The real remember() flow consolidates
// synchronously (post-write online pump), so a cluster of CONSOLIDATED members with
// ZERO volatile rows is exactly the production case. Pre-fix this formed 0 gists
// (sample_volatile empty → no seeds); post-fix sample_consolidated supplies them.
// stats.sampled==0 proves the seed came from the consolidated source, not volatile.
TEST(GistWriter, RunSleepSeedsFromConsolidated) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed(conn.raw(), {.id = "m1", .holder = "alice", .state = "consolidated"});
    seed(conn.raw(), {.id = "m2", .holder = "bob", .state = "consolidated"});
    seed(conn.raw(), {.id = "m3", .holder = "carol", .state = "consolidated"});

    ReplayScheduler sched(*adapter);
    const auto stats = sched.run_sleep(conn, "2026-06-27T12:00:00Z");
    EXPECT_EQ(stats.sampled, 0);          // nothing volatile to compress
    EXPECT_GE(stats.gist_candidates, 1);  // the consolidated cluster is still found
    EXPECT_GE(stats.abstracted, 1);       // and written (no-LLM deterministic path)
    sqlite3* db = conn.raw();
    EXPECT_EQ(col_int(db, std::string("SELECT COUNT(*) FROM statements ") + kGistWhere), 1);
}

// #38-C v2 threshold surface: run_sleep honors an overridden GistThresholds end to
// end. K=4 on the same 3-holder cluster is below threshold → no candidate, no gist —
// proving the configurable K/T/floor threads through run_sleep → do_compress_and_emit
// → find_norm_gist_clusters.
TEST(GistWriter, RunSleepHonorsOverriddenThresholds) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed(conn.raw(), {.id = "m1", .holder = "alice", .state = "consolidated"});
    seed(conn.raw(), {.id = "m2", .holder = "bob", .state = "consolidated"});
    seed(conn.raw(), {.id = "m3", .holder = "carol", .state = "consolidated"});

    ReplayScheduler sched(*adapter);
    const auto stats = sched.run_sleep(conn, "2026-06-27T12:00:00Z", nullptr,
                                       GistThresholds{/*min_distinct_holders=*/4,
                                                      /*min_replay_count=*/1,
                                                      /*min_confidence=*/0.6});
    EXPECT_EQ(stats.gist_candidates, 0);  // 3 holders < K=4 → no cluster
    EXPECT_EQ(col_int(conn.raw(), std::string("SELECT COUNT(*) FROM statements ") + kGistWhere), 0);
}

// #38-C v2 semantic clustering: 3 holders assert the same norm in DIFFERENT words
// (distinct objects → distinct hashes → the exact pass forms NOTHING) but with near
// embeddings → the k-NN semantic pass groups them into one cluster. A 4th holder with
// an orthogonal embedding stays out (below the cosine floor). This is the case exact
// matching structurally cannot catch.
TEST(GistClustering, SemanticGroupsNearVectorsExcludesFar) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    sqlite3* db = conn.raw();
    seed(db, {.id = "m1", .holder = "alice", .hashfill = 'a', .state = "consolidated"});
    seed(db, {.id = "m2", .holder = "bob",   .hashfill = 'b', .state = "consolidated"});
    seed(db, {.id = "m3", .holder = "carol", .hashfill = 'c', .state = "consolidated"});
    seed(db, {.id = "m4", .holder = "dave",  .hashfill = 'd', .state = "consolidated"});

    starling::vector::SqliteBlobVectorIndex index;
    index.insert(conn, "m1", "default", {1.0F, 0.0F, 0.0F});
    index.insert(conn, "m2", "default", {0.99F, 0.10F, 0.0F});
    index.insert(conn, "m3", "default", {0.98F, 0.15F, 0.0F});
    index.insert(conn, "m4", "default", {0.0F, 1.0F, 0.0F});  // orthogonal → excluded

    const GistThresholds cfg{.min_distinct_holders = 3, .min_replay_count = 1,
                             .min_confidence = 0.6, .similarity_threshold = 0.8};
    const auto clusters =
        find_semantic_gist_clusters(conn, index, "default", {"m1", "m2", "m3", "m4"}, cfg, {});
    ASSERT_EQ(clusters.size(), 1U);
    EXPECT_EQ(clusters[0].holder_ids.size(), 3U);  // alice/bob/carol; dave (orthogonal) excluded
    EXPECT_EQ(clusters[0].member_ids.size(), 3U);
}

// Opt-in: similarity_threshold = 0 (the default) disables the semantic pass entirely,
// so upgrading changes nothing until an operator configures a positive floor.
TEST(GistClustering, SemanticDisabledWhenThresholdZero) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    sqlite3* db = conn.raw();
    seed(db, {.id = "m1", .holder = "alice", .hashfill = 'a', .state = "consolidated"});
    seed(db, {.id = "m2", .holder = "bob",   .hashfill = 'b', .state = "consolidated"});
    seed(db, {.id = "m3", .holder = "carol", .hashfill = 'c', .state = "consolidated"});
    starling::vector::SqliteBlobVectorIndex index;
    index.insert(conn, "m1", "default", {1.0F, 0.0F});
    index.insert(conn, "m2", "default", {1.0F, 0.0F});
    index.insert(conn, "m3", "default", {1.0F, 0.0F});

    const GistThresholds cfg{.min_distinct_holders = 3, .min_replay_count = 1,
                             .min_confidence = 0.6, .similarity_threshold = 0.0};
    EXPECT_TRUE(
        find_semantic_gist_clusters(conn, index, "default", {"m1", "m2", "m3"}, cfg, {}).empty());
}

// Idempotency: a candidate whose representative key (predicate + canonical_object_hash)
// is already abstracted into a gist is skipped — re-replay never re-emits the norm.
TEST(GistClustering, SemanticClusterSkippedWhenRepKeyAlreadyAbstracted) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    sqlite3* db = conn.raw();
    seed(db, {.id = "m1", .holder = "alice", .hashfill = 'a', .state = "consolidated"});
    seed(db, {.id = "m2", .holder = "bob",   .hashfill = 'b', .state = "consolidated"});
    seed(db, {.id = "m3", .holder = "carol", .hashfill = 'c', .state = "consolidated"});
    // Pre-existing gist on the representative key (m1 = smallest id → hashfill 'a').
    seed(db, {.id = "g1", .holder = "common_ground", .hashfill = 'a', .state = "consolidated",
              .provenance = "consolidation_abstract"});
    starling::vector::SqliteBlobVectorIndex index;
    index.insert(conn, "m1", "default", {1.0F, 0.0F});
    index.insert(conn, "m2", "default", {0.99F, 0.10F});
    index.insert(conn, "m3", "default", {0.98F, 0.15F});

    const GistThresholds cfg{.min_distinct_holders = 3, .min_replay_count = 1,
                             .min_confidence = 0.6, .similarity_threshold = 0.8};
    EXPECT_TRUE(
        find_semantic_gist_clusters(conn, index, "default", {"m1", "m2", "m3"}, cfg, {}).empty());
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

    // Combined response: the judge reads {confidence, summary}; the entailment
    // verify reads {entailed} — from the same JSON (each extracts its fields).
    starling::extractor::FakeLLMAdapter llm;
    llm.set_default_response(starling::extractor::LLMResponse{
        .raw_xml = R"({"confidence": 0.82, "summary": "People generally like coffee.", "entailed": true})",
        .ok = true});

    const auto outcome =
        write_gist_proposals(*adapter, {{"default", clusters[0]}}, "2026-06-27T12:00:00Z", &llm);
    EXPECT_EQ(outcome.written, 1);
    EXPECT_EQ(outcome.failed, 0);
    EXPECT_EQ(outcome.gated, 0);
    sqlite3* db = conn.raw();
    EXPECT_EQ(col_int(db, std::string("SELECT COUNT(*) FROM statements ") + kGistWhere +
                          " AND ABS(confidence - 0.82) < 0.001"), 1);
    EXPECT_EQ(col_text(db, std::string("SELECT consolidation_summary FROM statements ") + kGistWhere),
              "People generally like coffee.");
    // Phase 4: verified + above floor → PROMOTED to live (consolidated + approved).
    EXPECT_EQ(col_text(db, std::string("SELECT consolidation_state FROM statements ") + kGistWhere),
              "consolidated");
    EXPECT_EQ(col_text(db, std::string("SELECT review_status FROM statements ") + kGistWhere),
              "approved");
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

// Phase 4 gate (c): below the confidence floor → gated, not written (re-detectable).
TEST(GistWriter, BelowFloorConfidenceGated) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_three_holder_cluster(conn.raw());
    const auto clusters = find_norm_gist_clusters(conn, "default", {"m1"}, GistThresholds{});

    starling::extractor::FakeLLMAdapter llm;
    llm.set_default_response(starling::extractor::LLMResponse{
        .raw_xml = R"({"confidence": 0.4, "summary": "x", "entailed": true})", .ok = true});

    const auto outcome =
        write_gist_proposals(*adapter, {{"default", clusters[0]}}, "2026-06-27T12:00:00Z", &llm);
    EXPECT_EQ(outcome.written, 0);
    EXPECT_EQ(outcome.gated, 1);
    EXPECT_EQ(col_int(conn.raw(), std::string("SELECT COUNT(*) FROM statements ") + kGistWhere), 0);
}

// Phase 4 gate (b) — the eng-review golden: a non-entailed (confabulated /
// over-reaching) summary is REJECTED, even at high confidence. Not written.
TEST(GistWriter, NotEntailedSummaryGated) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_three_holder_cluster(conn.raw());
    const auto clusters = find_norm_gist_clusters(conn, "default", {"m1"}, GistThresholds{});

    starling::extractor::FakeLLMAdapter llm;
    llm.set_default_response(starling::extractor::LLMResponse{
        .raw_xml = R"({"confidence": 0.9, "summary": "over-reaching claim", "entailed": false})",
        .ok = true});

    const auto outcome =
        write_gist_proposals(*adapter, {{"default", clusters[0]}}, "2026-06-27T12:00:00Z", &llm);
    EXPECT_EQ(outcome.written, 0);
    EXPECT_EQ(outcome.gated, 1);
    EXPECT_EQ(col_int(conn.raw(), std::string("SELECT COUNT(*) FROM statements ") + kGistWhere), 0);
}

// INDEPENDENCE of the entailment verify (the primary safety mechanism): even
// with a strong judge reply that has NO "entailed" field, the SEPARATE second
// call's not-entailed verdict gates the gist. If the verdict were (wrongly) read
// from the judge reply, it would have no "entailed" field → Failed (not Gated);
// asserting gated==1 / failed==0 proves the 2nd call independently controls it.
TEST(GistWriter, EntailmentVerifyIndependentlyGates) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_three_holder_cluster(conn.raw());
    const auto clusters = find_norm_gist_clusters(conn, "default", {"m1"}, GistThresholds{});

    SequencedLLM llm({
        starling::extractor::LLMResponse{.raw_xml = R"({"confidence": 0.95, "summary": "strong"})",
                                         .ok = true},                                 // judge: passes floor
        starling::extractor::LLMResponse{.raw_xml = R"({"entailed": false})", .ok = true},  // verify: rejects
    });
    const auto outcome =
        write_gist_proposals(*adapter, {{"default", clusters[0]}}, "2026-06-27T12:00:00Z", &llm);
    EXPECT_EQ(outcome.written, 0);
    EXPECT_EQ(outcome.gated, 1);
    EXPECT_EQ(outcome.failed, 0);  // proves the verdict came from the 2nd reply, not the 1st
    EXPECT_EQ(col_int(conn.raw(), std::string("SELECT COUNT(*) FROM statements ") + kGistWhere), 0);
}

// Converse: strong judge + an entailed verdict from the 2nd call → promoted live.
TEST(GistWriter, EntailmentVerifyIndependentlyPasses) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_three_holder_cluster(conn.raw());
    const auto clusters = find_norm_gist_clusters(conn, "default", {"m1"}, GistThresholds{});

    SequencedLLM llm({
        starling::extractor::LLMResponse{.raw_xml = R"({"confidence": 0.95, "summary": "ok"})",
                                         .ok = true},
        starling::extractor::LLMResponse{.raw_xml = R"({"entailed": true})", .ok = true},
    });
    const auto outcome =
        write_gist_proposals(*adapter, {{"default", clusters[0]}}, "2026-06-27T12:00:00Z", &llm);
    EXPECT_EQ(outcome.written, 1);
    EXPECT_EQ(col_text(conn.raw(), std::string("SELECT consolidation_state FROM statements ") + kGistWhere),
              "consolidated");
}

// #38-C v2 false-merge safety: a SEMANTIC cluster's summary is verified against EACH
// varied member (per-member entailment). If it fails to entail even one — a
// false-merged outlier — the whole candidate is GATED, not written. Single-rep
// entailment would have checked only the representative and missed the outlier.
TEST(GistWriter, PerMemberEntailmentGatesSemanticFalseMerge) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    sqlite3* db = conn.raw();
    seed(db, {.id = "m1", .holder = "alice", .hashfill = 'a', .state = "consolidated",
              .object_value = "code review"});
    seed(db, {.id = "m2", .holder = "bob", .hashfill = 'b', .state = "consolidated",
              .object_value = "reviewing code"});
    seed(db, {.id = "m3", .holder = "carol", .hashfill = 'c', .state = "consolidated",
              .object_value = "pull-request review"});
    starling::vector::SqliteBlobVectorIndex index;
    index.insert(conn, "m1", "default", {1.0F, 0.0F});
    index.insert(conn, "m2", "default", {0.99F, 0.10F});
    index.insert(conn, "m3", "default", {0.98F, 0.15F});

    const GistThresholds cfg{.min_distinct_holders = 3, .min_replay_count = 1,
                             .min_confidence = 0.6, .similarity_threshold = 0.8};
    const auto clusters =
        find_semantic_gist_clusters(conn, index, "default", {"m1", "m2", "m3"}, cfg, {});
    ASSERT_EQ(clusters.size(), 1U);
    ASSERT_EQ(clusters[0].member_objects.size(), 3U);  // varied → per-member gate engages

    // Judge passes the floor; per-member entailment: true, true, FALSE → the outlier
    // gates the candidate (4 LLM calls = 1 judge + 3 members, proving it is per-member).
    SequencedLLM llm({
        starling::extractor::LLMResponse{.raw_xml = R"({"confidence":0.9,"summary":"value review"})",
                                         .ok = true},
        starling::extractor::LLMResponse{.raw_xml = R"({"entailed": true})", .ok = true},
        starling::extractor::LLMResponse{.raw_xml = R"({"entailed": true})", .ok = true},
        starling::extractor::LLMResponse{.raw_xml = R"({"entailed": false})", .ok = true},
    });
    const auto outcome = write_gist_proposals(
        *adapter, {{.tenant_id = "default", .cluster = clusters[0]}}, "2026-06-28T12:00:00Z", &llm);
    EXPECT_EQ(outcome.gated, 1);    // the outlier member gated it
    EXPECT_EQ(outcome.written, 0);  // false-merge blocked — nothing written
}

// Floor boundary: confidence exactly at the floor passes (strict <), proceeding
// to entailment (here entailed → promoted).
TEST(GistWriter, ConfidenceAtFloorPasses) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_three_holder_cluster(conn.raw());
    const auto clusters = find_norm_gist_clusters(conn, "default", {"m1"}, GistThresholds{});

    starling::extractor::FakeLLMAdapter llm;
    llm.set_default_response(starling::extractor::LLMResponse{
        .raw_xml = R"({"confidence": 0.6, "summary": "x", "entailed": true})", .ok = true});
    const auto outcome =
        write_gist_proposals(*adapter, {{"default", clusters[0]}}, "2026-06-27T12:00:00Z", &llm);
    EXPECT_EQ(outcome.written, 1);  // 0.6 is NOT below the 0.6 floor
}

// promote is STATE-GUARDED: a still-volatile gist is flipped to consolidated+
// approved; a non-volatile (e.g. arbitration-archived) gist is a no-op.
TEST(GistWriter, PromoteOnlyActsOnVolatileGist) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed(conn.raw(), {.id = "g1", .holder = "__common_ground__", .state = "volatile",
                      .review = "pending_review", .provenance = "consolidation_abstract"});
    seed(conn.raw(), {.id = "g2", .holder = "__common_ground__", .state = "archived",
                      .review = "pending_review", .provenance = "consolidation_abstract"});

    starling::store::SqliteStatementStore store(conn);
    EXPECT_EQ(store.promote_gist_to_consolidated("g1", "default", "2026-06-27T12:00:00Z"), 1);
    EXPECT_EQ(store.promote_gist_to_consolidated("g2", "default", "2026-06-27T12:00:00Z"), 0);
    sqlite3* db = conn.raw();
    EXPECT_EQ(col_text(db, "SELECT consolidation_state FROM statements WHERE id='g1'"), "consolidated");
    EXPECT_EQ(col_text(db, "SELECT review_status FROM statements WHERE id='g1'"), "approved");
    EXPECT_EQ(col_text(db, "SELECT consolidation_state FROM statements WHERE id='g2'"), "archived");
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

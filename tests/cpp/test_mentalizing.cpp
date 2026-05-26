#include "starling/tom/mentalizing.hpp"
#include "starling/cognizer/knowledge_frontier.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <memory>
#include <string>
#include <vector>

using starling::cognizer::KnowledgeFrontier;
using starling::persistence::SqliteAdapter;
using starling::persistence::StmtHandle;
using starling::tom::mentalizing::FactKey;
using starling::tom::mentalizing::KnowsResult;
using starling::tom::mentalizing::SharedFact;
using starling::tom::mentalizing::what_does_X_believe;
using starling::tom::mentalizing::does_X_know;
using starling::tom::mentalizing::find_misalignment;
using starling::tom::mentalizing::shared_with;

namespace {

// ─── fixture helpers ──────────────────────────────────────────────────────────

std::unique_ptr<SqliteAdapter> make_adapter() {
    auto a = SqliteAdapter::open(":memory:");
    starling::persistence::MigrationRunner(a->connection().raw()).migrate_to_latest();
    return a;
}

// Full-featured raw insert with control over all varying columns.
struct StmtSpec {
    std::string id;
    std::string tenant_id     = "t1";
    std::string holder_id;
    std::string subject_kind  = "cognizer";
    std::string subject_id;
    std::string predicate     = "believes";
    std::string object_value  = "some-value";
    std::string canon_hash    = "hash-abc";
    std::string modality      = "believes";
    std::string polarity      = "pos";
    double      confidence    = 0.9;
    std::string observed_at   = "2026-05-26T10:00:00Z";
    std::string valid_from    = "";     // NULL if empty
    std::string valid_to      = "";     // NULL if empty
    std::string consolidation = "consolidated";
    std::string review_status = "approved";
    std::string evidence_json = "[]";
};

void insert_statement(sqlite3* db, const StmtSpec& s) {
    const std::string sql =
        "INSERT INTO statements("
        "  id, tenant_id, holder_id, holder_perspective,"
        "  subject_kind, subject_id, predicate, object_kind, object_value,"
        "  canonical_object_hash, canonical_object_hash_version,"
        "  modality, polarity, confidence, observed_at,"
        "  valid_from, valid_to,"
        "  salience, affect_json, activation, last_accessed,"
        "  provenance, evidence_json, source_spans_json, perceived_by_json,"
        "  consolidation_state, review_status,"
        "  derived_from_json, derived_depth,"
        "  nesting_depth,"
        "  created_at, updated_at"
        ") VALUES ("
        "  ?, ?, ?, 'first_person',"
        "  ?, ?, ?, 'str', ?,"
        "  ?, 'v1',"
        "  ?, ?, ?, ?,"
        "  ?, ?,"
        "  0.0, '{}', 0.0, ?,"
        "  'observed', ?, '[]', '[]',"
        "  ?, ?,"
        "  '[]', 0,"
        "  0,"
        "  ?, ?"
        ")";

    sqlite3_stmt* raw = nullptr;
    ASSERT_EQ(sqlite3_prepare_v2(db, sql.c_str(), -1, &raw, nullptr), SQLITE_OK)
        << sqlite3_errmsg(db);
    StmtHandle h(raw);

    auto bs = [&](int i, const std::string& v) {
        sqlite3_bind_text(raw, i, v.c_str(), -1, SQLITE_TRANSIENT);
    };
    auto bn = [&](int i) {
        sqlite3_bind_null(raw, i);
    };

    bs(1,  s.id);
    bs(2,  s.tenant_id);
    bs(3,  s.holder_id);
    bs(4,  s.subject_kind);
    bs(5,  s.subject_id);
    bs(6,  s.predicate);
    bs(7,  s.object_value);
    bs(8,  s.canon_hash);
    bs(9,  s.modality);
    bs(10, s.polarity);
    sqlite3_bind_double(raw, 11, s.confidence);
    bs(12, s.observed_at);
    if (s.valid_from.empty()) bn(13); else bs(13, s.valid_from);
    if (s.valid_to.empty())   bn(14); else bs(14, s.valid_to);
    bs(15, s.observed_at);   // last_accessed
    bs(16, s.evidence_json);
    bs(17, s.consolidation);
    bs(18, s.review_status);
    bs(19, s.observed_at);   // created_at
    bs(20, s.observed_at);   // updated_at

    ASSERT_EQ(sqlite3_step(raw), SQLITE_DONE) << sqlite3_errmsg(db);
}

// Insert an engram (minimal columns).
void insert_engram(sqlite3* db,
                   const std::string& id,
                   const std::string& tenant_id,
                   const std::string& created_at = "2026-05-26T09:00:00Z") {
    const std::string sql =
        "INSERT INTO engrams("
        "  id, tenant_id, content_hash, source_kind, ingest_policy, ingest_mode,"
        "  privacy_class, retention_mode, created_at,"
        "  adapter_name, adapter_version, source_item_id, source_version, chunk_index,"
        "  declared_transformations_json, byte_preserving"
        ") VALUES ("
        "  ?, ?, 'hash-x', 'user_input', 'store', 'whole_record',"
        "  'internal', 'audit_retain', ?,"
        "  'direct_api', '1.0.0', 'msg-1', '1', 0,"
        "  '[]', 1"
        ")";
    sqlite3_stmt* raw = nullptr;
    ASSERT_EQ(sqlite3_prepare_v2(db, sql.c_str(), -1, &raw, nullptr), SQLITE_OK)
        << sqlite3_errmsg(db);
    StmtHandle h(raw);
    sqlite3_bind_text(raw, 1, id.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, 2, tenant_id.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, 3, created_at.c_str(), -1, SQLITE_TRANSIENT);
    ASSERT_EQ(sqlite3_step(raw), SQLITE_DONE) << sqlite3_errmsg(db);
}

}  // namespace

// ═══════════════════════════════════════════════════════════════════════════
// 1. what_does_X_believe
// ═══════════════════════════════════════════════════════════════════════════

TEST(MentalizingBelieve, ReturnsHolderXSubjectYStatementsOnly) {
    auto a = make_adapter();
    sqlite3* db = a->connection().raw();

    // alice believes about bob
    StmtSpec s1;
    s1.id = "s1"; s1.holder_id = "alice"; s1.subject_id = "bob";
    insert_statement(db, s1);

    // charlie believes about bob (should NOT appear in alice query)
    StmtSpec s2;
    s2.id = "s2"; s2.holder_id = "charlie"; s2.subject_id = "bob";
    insert_statement(db, s2);

    auto rows = what_does_X_believe(*a, "alice", "bob", "t1",
                                    "2026-05-26T12:00:00Z");
    ASSERT_EQ(rows.size(), 1u);
    EXPECT_EQ(rows[0].id, "s1");
    EXPECT_EQ(rows[0].holder_id, "alice");
}

TEST(MentalizingBelieve, ExcludesNonCognizerSubjects) {
    auto a = make_adapter();
    sqlite3* db = a->connection().raw();

    // subject_kind = 'entity' must not be returned (query filters 'cognizer')
    const std::string sql =
        "INSERT INTO statements("
        "  id, tenant_id, holder_id, holder_perspective,"
        "  subject_kind, subject_id, predicate, object_kind, object_value,"
        "  canonical_object_hash, canonical_object_hash_version,"
        "  modality, polarity, confidence, observed_at,"
        "  salience, affect_json, activation, last_accessed,"
        "  provenance, evidence_json, source_spans_json, perceived_by_json,"
        "  consolidation_state, review_status,"
        "  derived_from_json, derived_depth,"
        "  nesting_depth,"
        "  created_at, updated_at"
        ") VALUES ("
        "  'e1','t1','alice','first_person',"
        "  'entity','bob','likes','str','chips',"
        "  'hash-e','v1',"
        "  'believes','pos',0.8,'2026-05-26T10:00:00Z',"
        "  0.0,'{}',0.0,'2026-05-26T10:00:00Z',"
        "  'observed','[]','[]','[]',"
        "  'consolidated','approved',"
        "  '[]',0,"
        "  0,"
        "  '2026-05-26T10:00:00Z','2026-05-26T10:00:00Z'"
        ")";
    sqlite3_stmt* raw = nullptr;
    ASSERT_EQ(sqlite3_prepare_v2(db, sql.c_str(), -1, &raw, nullptr), SQLITE_OK);
    StmtHandle h(raw);
    ASSERT_EQ(sqlite3_step(raw), SQLITE_DONE);

    auto rows = what_does_X_believe(*a, "alice", "bob", "t1",
                                    "2026-05-26T12:00:00Z");
    EXPECT_TRUE(rows.empty()) << "entity subjects must be excluded";
}

TEST(MentalizingBelieve, AsOfFiltersTimeBoundedBeliefs) {
    auto a = make_adapter();
    sqlite3* db = a->connection().raw();

    // valid_from = future → should be excluded at as_of
    StmtSpec s;
    s.id = "s-future"; s.holder_id = "alice"; s.subject_id = "bob";
    s.valid_from = "2026-05-27T00:00:00Z";
    insert_statement(db, s);

    auto rows = what_does_X_believe(*a, "alice", "bob", "t1",
                                    "2026-05-26T12:00:00Z");
    EXPECT_TRUE(rows.empty()) << "future valid_from must be excluded";
}

TEST(MentalizingBelieve, ModalityFilterApplied) {
    auto a = make_adapter();
    sqlite3* db = a->connection().raw();

    StmtSpec s1;
    s1.id = "s-believes"; s1.holder_id = "alice"; s1.subject_id = "bob";
    s1.modality = "believes";
    insert_statement(db, s1);

    StmtSpec s2;
    s2.id = "s-desires"; s2.holder_id = "alice"; s2.subject_id = "bob";
    s2.modality = "desires";
    insert_statement(db, s2);

    auto rows_all = what_does_X_believe(*a, "alice", "bob", "t1",
                                        "2026-05-26T12:00:00Z");
    EXPECT_EQ(rows_all.size(), 2u);

    auto rows_filtered = what_does_X_believe(*a, "alice", "bob", "t1",
                                             "2026-05-26T12:00:00Z", "desires");
    ASSERT_EQ(rows_filtered.size(), 1u);
    EXPECT_EQ(rows_filtered[0].modality, "desires");
}

// ═══════════════════════════════════════════════════════════════════════════
// 2. does_X_know
// ═══════════════════════════════════════════════════════════════════════════

TEST(MentalizingKnow, FullKnowledgeWhenXAssertsFactPositive) {
    auto a = make_adapter();
    sqlite3* db = a->connection().raw();

    StmtSpec s;
    s.id = "k1"; s.holder_id = "alice"; s.subject_id = "bob";
    s.predicate = "likes"; s.canon_hash = "hash-likes"; s.polarity = "pos";
    insert_statement(db, s);

    KnowledgeFrontier frontier(*a);
    FactKey fk{"cognizer", "bob", "likes", "hash-likes"};
    auto r = does_X_know(*a, frontier, "alice", fk, "t1", "2026-05-26T12:00:00Z");
    EXPECT_EQ(r, KnowsResult::FullKnowledge);
}

TEST(MentalizingKnow, NotKnownWhenEvidenceVisibleButNotAsserted) {
    // alice hasn't asserted the fact, but the source engram is in her frontier.
    auto a = make_adapter();
    sqlite3* db = a->connection().raw();

    // Insert the engram.
    insert_engram(db, "engram-ev", "t1");

    // Insert a statement by charlie (not alice) with evidence_json pointing to
    // engram-ev.  This establishes engram-ev as evidence for the fact.
    StmtSpec s;
    s.id = "k2"; s.holder_id = "charlie"; s.subject_id = "bob";
    s.predicate = "likes"; s.canon_hash = "hash-likes-ev"; s.polarity = "pos";
    s.evidence_json = R"([{"engram_ref":"engram-ev","content_hash":"x"}])";
    insert_statement(db, s);

    // Record engram-ev as visible to alice via explicit_told.
    KnowledgeFrontier frontier(*a);
    frontier.record_explicit_told(
        "t1", {"alice"}, "stmt-told", "engram-ev",
        "2026-05-26T09:00:00Z", a->connection());

    FactKey fk{"cognizer", "bob", "likes", "hash-likes-ev"};
    auto r = does_X_know(*a, frontier, "alice", fk, "t1", "2026-05-26T12:00:00Z");
    EXPECT_EQ(r, KnowsResult::NotKnown);
}

TEST(MentalizingKnow, UnknowableWhenFrontierMisses) {
    // No presence_log, no explicit_told for alice → Unknowable.
    auto a = make_adapter();
    sqlite3* db = a->connection().raw();

    // Engram exists but NOT visible to alice.
    insert_engram(db, "engram-hidden", "t1");

    // A statement that carries evidence_json referencing engram-hidden.
    StmtSpec s;
    s.id = "k3"; s.holder_id = "charlie"; s.subject_id = "bob";
    s.predicate = "knows"; s.canon_hash = "hash-knows-h"; s.polarity = "pos";
    s.evidence_json = R"([{"engram_ref":"engram-hidden","content_hash":"y"}])";
    insert_statement(db, s);

    KnowledgeFrontier frontier(*a);
    // alice has no frontier records at all

    FactKey fk{"cognizer", "bob", "knows", "hash-knows-h"};
    auto r = does_X_know(*a, frontier, "alice", fk, "t1", "2026-05-26T12:00:00Z");
    EXPECT_EQ(r, KnowsResult::Unknowable);
}

TEST(MentalizingKnow, NegativePolarityCountsAsNotFullKnowledge) {
    // alice has a NEG statement for the fact → not FullKnowledge.
    auto a = make_adapter();
    sqlite3* db = a->connection().raw();

    StmtSpec s;
    s.id = "k4"; s.holder_id = "alice"; s.subject_id = "bob";
    s.predicate = "happy"; s.canon_hash = "hash-happy"; s.polarity = "neg";
    insert_statement(db, s);

    KnowledgeFrontier frontier(*a);
    FactKey fk{"cognizer", "bob", "happy", "hash-happy"};
    auto r = does_X_know(*a, frontier, "alice", fk, "t1", "2026-05-26T12:00:00Z");
    // No visible engrams → Unknowable (but definitely NOT FullKnowledge)
    EXPECT_NE(r, KnowsResult::FullKnowledge);
}

// ═══════════════════════════════════════════════════════════════════════════
// 3. find_misalignment
// ═══════════════════════════════════════════════════════════════════════════

TEST(MentalizingMisalign, DetectsOnlyXBelieves) {
    auto a = make_adapter();
    sqlite3* db = a->connection().raw();

    // alice has POS belief; bob has no statement about the same (pred, hash).
    StmtSpec s;
    s.id = "m1"; s.holder_id = "alice"; s.subject_id = "carol";
    s.predicate = "smart"; s.canon_hash = "hash-smart"; s.polarity = "pos";
    insert_statement(db, s);

    auto mis = find_misalignment(*a, "alice", "bob",
                                 "cognizer", "carol", "t1",
                                 "2026-05-26T12:00:00Z");
    EXPECT_EQ(mis.only_x_believes.size(), 1u);
    EXPECT_TRUE(mis.only_y_believes.empty());
    EXPECT_TRUE(mis.confidence_diverges.empty());
}

TEST(MentalizingMisalign, DetectsConfidenceDivergence) {
    auto a = make_adapter();
    sqlite3* db = a->connection().raw();

    // Both alice and bob have POS for same (pred, hash), but |0.95 - 0.50| = 0.45 > 0.3
    StmtSpec sx;
    sx.id = "m2x"; sx.holder_id = "alice"; sx.subject_id = "carol";
    sx.predicate = "tall"; sx.canon_hash = "hash-tall"; sx.polarity = "pos";
    sx.confidence = 0.95;
    insert_statement(db, sx);

    StmtSpec sy;
    sy.id = "m2y"; sy.holder_id = "bob"; sy.subject_id = "carol";
    sy.predicate = "tall"; sy.canon_hash = "hash-tall"; sy.polarity = "pos";
    sy.confidence = 0.50;
    insert_statement(db, sy);

    auto mis = find_misalignment(*a, "alice", "bob",
                                 "cognizer", "carol", "t1",
                                 "2026-05-26T12:00:00Z");
    EXPECT_TRUE(mis.only_x_believes.empty());
    EXPECT_TRUE(mis.only_y_believes.empty());
    ASSERT_EQ(mis.confidence_diverges.size(), 1u);
    // x is alice, y is bob
    EXPECT_EQ(mis.confidence_diverges[0].first.holder_id, "alice");
    EXPECT_EQ(mis.confidence_diverges[0].second.holder_id, "bob");
}

TEST(MentalizingMisalign, BothEmptyWhenNoOverlap) {
    // X and Y believe completely different predicates → only_x and only_y both
    // non-empty but confidence_diverges is empty.
    auto a = make_adapter();
    sqlite3* db = a->connection().raw();

    StmtSpec sx;
    sx.id = "m3x"; sx.holder_id = "alice"; sx.subject_id = "carol";
    sx.predicate = "pred-a"; sx.canon_hash = "hash-a"; sx.polarity = "pos";
    insert_statement(db, sx);

    StmtSpec sy;
    sy.id = "m3y"; sy.holder_id = "bob"; sy.subject_id = "carol";
    sy.predicate = "pred-b"; sy.canon_hash = "hash-b"; sy.polarity = "pos";
    insert_statement(db, sy);

    auto mis = find_misalignment(*a, "alice", "bob",
                                 "cognizer", "carol", "t1",
                                 "2026-05-26T12:00:00Z");
    EXPECT_EQ(mis.only_x_believes.size(), 1u);
    EXPECT_EQ(mis.only_y_believes.size(), 1u);
    EXPECT_TRUE(mis.confidence_diverges.empty());
}

// ═══════════════════════════════════════════════════════════════════════════
// 4. shared_with
// ═══════════════════════════════════════════════════════════════════════════

TEST(MentalizingShared, TwoMembersBothBelieveReturnsSharedFact) {
    auto a = make_adapter();
    sqlite3* db = a->connection().raw();

    StmtSpec sa;
    sa.id = "sh1a"; sa.holder_id = "alice"; sa.subject_id = "bob";
    sa.predicate = "curious"; sa.canon_hash = "hash-cur"; sa.polarity = "pos";
    insert_statement(db, sa);

    StmtSpec sb;
    sb.id = "sh1b"; sb.holder_id = "charlie"; sb.subject_id = "bob";
    sb.predicate = "curious"; sb.canon_hash = "hash-cur"; sb.polarity = "pos";
    insert_statement(db, sb);

    auto facts = shared_with(*a, {"alice", "charlie"}, "t1",
                             "2026-05-26T12:00:00Z");
    ASSERT_EQ(facts.size(), 1u);
    EXPECT_EQ(facts[0].predicate, "curious");
    EXPECT_EQ(facts[0].canonical_object_hash, "hash-cur");
    EXPECT_EQ(facts[0].source_statement_ids.size(), 2u);
}

TEST(MentalizingShared, AnyMemberMissingExcludesFromShared) {
    auto a = make_adapter();
    sqlite3* db = a->connection().raw();

    // alice has the fact, dave does NOT.
    StmtSpec sa;
    sa.id = "sh2a"; sa.holder_id = "alice"; sa.subject_id = "bob";
    sa.predicate = "funny"; sa.canon_hash = "hash-funny"; sa.polarity = "pos";
    insert_statement(db, sa);

    auto facts = shared_with(*a, {"alice", "dave"}, "t1",
                             "2026-05-26T12:00:00Z");
    EXPECT_TRUE(facts.empty()) << "fact held by only 1/2 members must be excluded";
}

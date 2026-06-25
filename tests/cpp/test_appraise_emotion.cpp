// appraise_emotion — appraisal-theory emotion operator: X's desire vs the actual
// OCCURRED outcome → goal_congruence × agency → discrete emotion; abstains on undecidable.
#include "starling/tom/mentalizing.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <memory>
#include <string>
#include <vector>

using starling::persistence::SqliteAdapter;
using starling::persistence::StmtHandle;
using starling::tom::mentalizing::EmotionAppraisal;
using starling::tom::mentalizing::appraise_emotion;

namespace {

// ─── fixture helpers (copied from test_mentalizing.cpp) ───────────────────────

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

// Seed a desire X holds (holder=X, subject=X, modality=desires, object=target).
void seed_desire(sqlite3* db, const std::string& id, const std::string& x,
                 const std::string& target, const std::string& hash) {
    StmtSpec d;
    d.id = id; d.holder_id = x; d.subject_id = x;
    d.predicate = "desires"; d.modality = "desires";
    d.object_value = target; d.canon_hash = hash;
    insert_statement(db, d);
}

// Seed an OCCURRED event: actor (the doer) is subject_id; object is the thing.
// holder_id = x so the event INVOLVES x (X experienced this outcome).
void seed_occurred(sqlite3* db, const std::string& id, const std::string& x,
                   const std::string& actor, const std::string& predicate,
                   const std::string& object, const std::string& hash) {
    StmtSpec o;
    o.id = id; o.holder_id = x; o.subject_id = actor;
    o.predicate = predicate; o.modality = "occurred";
    o.object_value = object; o.canon_hash = hash;
    insert_statement(db, o);
}

constexpr const char* kAsOf = "2026-05-26T12:00:00Z";

}  // namespace

// ═══════════════════════════════════════════════════════════════════════════
// appraise_emotion
// ═══════════════════════════════════════════════════════════════════════════

// (A) disappointment: X desires computer; an OCCURRED "X receive bicycle"
//     (X is the actor, X got a bicycle not the computer). Incongruent outcome
//     where X is the doer of a non-desired result → circumstance → disappointment.
TEST(AppraiseEmotion, IncongruentCircumstanceIsDisappointment) {
    auto a = make_adapter();
    sqlite3* db = a->connection().raw();

    seed_desire(db, "d1", "xiao_ming", "computer", "hash-computer");
    // OCCURRED event with no other-cognizer actor: subject_id == x → not "other".
    seed_occurred(db, "o1", "xiao_ming", "xiao_ming", "receive", "bicycle",
                  "hash-bicycle");

    auto out = appraise_emotion(*a, "xiao_ming", "t1", kAsOf);
    ASSERT_EQ(out.size(), 1u);
    EXPECT_EQ(out[0].cognizer, "xiao_ming");
    EXPECT_EQ(out[0].emotion, "disappointment");
    EXPECT_EQ(out[0].goal_congruence, "incongruent");
    EXPECT_EQ(out[0].agency, "circumstance");
    EXPECT_EQ(out[0].desire.id, "d1");
    EXPECT_EQ(out[0].outcome_value, "bicycle");
}

// (B) joy: X desires computer; OCCURRED "X receive computer" (obj == the desire).
TEST(AppraiseEmotion, CongruentIsJoy) {
    auto a = make_adapter();
    sqlite3* db = a->connection().raw();

    seed_desire(db, "d1", "xiao_ming", "computer", "hash-computer");
    seed_occurred(db, "o1", "xiao_ming", "xiao_ming", "receive", "computer",
                  "hash-computer");

    auto out = appraise_emotion(*a, "xiao_ming", "t1", kAsOf);
    ASSERT_EQ(out.size(), 1u);
    EXPECT_EQ(out[0].emotion, "joy");
    EXPECT_EQ(out[0].goal_congruence, "congruent");
    EXPECT_EQ(out[0].outcome_value, "computer");
}

// (C) anger: X desires the_toy; OCCURRED "Bob take the_toy" — another cognizer
//     (Bob) is the actor, X did NOT get it. Incongruent + other → anger.
TEST(AppraiseEmotion, IncongruentOtherAgencyIsAnger) {
    auto a = make_adapter();
    sqlite3* db = a->connection().raw();

    seed_desire(db, "d1", "xiao_ming", "the_toy", "hash-toy");
    // X involved (holder=x) but the DOER (subject_id) is Bob, object != desire.
    seed_occurred(db, "o1", "xiao_ming", "bob", "take", "the_toy", "hash-toy");

    auto out = appraise_emotion(*a, "xiao_ming", "t1", kAsOf);
    ASSERT_EQ(out.size(), 1u);
    EXPECT_EQ(out[0].emotion, "anger");
    EXPECT_EQ(out[0].agency, "other");
    EXPECT_EQ(out[0].goal_congruence, "incongruent");
    EXPECT_EQ(out[0].outcome_value, "the_toy");
}

// (D) abstain: X desires computer but NO outcome event at all → no appraisal
//     (undecidable; never fabricate).
TEST(AppraiseEmotion, AbstainsWhenNoOutcome) {
    auto a = make_adapter();
    sqlite3* db = a->connection().raw();

    seed_desire(db, "d1", "xiao_ming", "computer", "hash-computer");

    auto out = appraise_emotion(*a, "xiao_ming", "t1", kAsOf);
    EXPECT_TRUE(out.empty());
}

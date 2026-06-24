#include "starling/tom/mentalizing.hpp"
#include "starling/cognizer/knowledge_frontier.hpp"
#include "starling/store/perception_state_store.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <algorithm>
#include <memory>
#include <string>
#include <vector>

using starling::tom::mentalizing::detect_faux_pas;
using starling::cognizer::KnowledgeFrontier;

namespace {

// ─── fixture helpers (verbatim from test_mentalizing.cpp) ────────────────────

std::unique_ptr<starling::persistence::SqliteAdapter> make_adapter() {
    auto a = starling::persistence::SqliteAdapter::open(":memory:");
    starling::persistence::MigrationRunner(a->connection().raw()).migrate_to_latest();
    return a;
}

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
    std::string valid_from    = "";
    std::string valid_to      = "";
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
    starling::persistence::StmtHandle h(raw);

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
    starling::persistence::StmtHandle h(raw);
    sqlite3_bind_text(raw, 1, id.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, 2, tenant_id.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, 3, created_at.c_str(), -1, SQLITE_TRANSIENT);
    ASSERT_EQ(sqlite3_step(raw), SQLITE_DONE) << sqlite3_errmsg(db);
}

// Seed perception_state so the cast includes a cognizer.
void seed_cast_member(starling::persistence::SqliteAdapter& a, const char* T, const char* cog) {
    starling::store::PerceptionStateStore ps(a.connection());
    starling::store::PerceptionStateRow row;
    row.tenant_id = T;
    row.cognizer_id = cog;
    row.theme_id = "stage";
    row.state_dim = "location";
    row.state_value = "room";
    row.observed_at = "2026-05-26T08:00:00Z";
    row.position = 0;
    row.source_event_id = std::string("seed-") + cog;
    ps.upsert(row);
}

}  // namespace

TEST(DetectFauxPas, IgnorantAsymmetryEmitsCandidate) {
    auto a = make_adapter();
    sqlite3* db = a->connection().raw();
    const char* T = "t1";
    for (const char* c : {"A","B","C"}) seed_cast_member(*a, T, c);

    insert_engram(db, "engram-F", T);
    StmtSpec f;
    f.id = "f1"; f.tenant_id = T; f.holder_id = "narrator"; f.subject_kind = "cognizer";
    f.subject_id = "bob"; f.predicate = "lost"; f.canon_hash = "hash-lost"; f.polarity = "pos";
    f.evidence_json = R"([{"engram_ref":"engram-F","content_hash":"x"}])";
    insert_statement(db, f);

    KnowledgeFrontier frontier(*a);
    frontier.record_explicit_told(T, {"A","C"}, "stmt-told", "engram-F",
                                  "2026-05-26T09:00:00Z", a->connection());

    auto cands = detect_faux_pas(*a, frontier, T, "2026-05-26T12:00:00Z");
    ASSERT_EQ(cands.size(), 1u);
    EXPECT_EQ(cands[0].ignorant, "B");
    EXPECT_EQ(cands[0].unknown_fact.subject_id, "bob");
    EXPECT_EQ(cands[0].unknown_fact.predicate, "lost");
    auto& wk = cands[0].who_knows;
    EXPECT_NE(std::find(wk.begin(), wk.end(), "A"), wk.end());
    EXPECT_NE(std::find(wk.begin(), wk.end(), "C"), wk.end());
}

TEST(DetectFauxPas, NoAsymmetryWhenAllKnow) {
    auto a = make_adapter();
    sqlite3* db = a->connection().raw();
    const char* T = "t2";
    for (const char* c : {"A","B"}) seed_cast_member(*a, T, c);
    insert_engram(db, "engram-G", T);
    StmtSpec g;
    g.id = "g1"; g.tenant_id = T; g.holder_id = "narrator"; g.subject_kind = "cognizer";
    g.subject_id = "bob"; g.predicate = "lost"; g.canon_hash = "hash-lost2"; g.polarity = "pos";
    g.evidence_json = R"([{"engram_ref":"engram-G","content_hash":"x"}])";
    insert_statement(db, g);
    KnowledgeFrontier frontier(*a);
    frontier.record_explicit_told(T, {"A","B"}, "stmt-told", "engram-G",
                                  "2026-05-26T09:00:00Z", a->connection());
    auto cands = detect_faux_pas(*a, frontier, T, "2026-05-26T12:00:00Z");
    EXPECT_TRUE(cands.empty());
}

TEST(DetectFauxPas, SingleCastMemberNoCandidate) {
    auto a = make_adapter();
    sqlite3* db = a->connection().raw();
    const char* T = "t3";
    seed_cast_member(*a, T, "A");          // only one cognizer present
    insert_engram(db, "engram-H", T);
    StmtSpec h; h.id = "h1"; h.tenant_id = T; h.holder_id = "narrator"; h.subject_kind = "cognizer";
    h.subject_id = "bob"; h.predicate = "lost"; h.canon_hash = "hash-lost3"; h.polarity = "pos";
    h.evidence_json = R"([{"engram_ref":"engram-H","content_hash":"x"}])";
    insert_statement(db, h);
    KnowledgeFrontier frontier(*a);
    frontier.record_explicit_told(T, {"A"}, "stmt-told", "engram-H",
                                  "2026-05-26T09:00:00Z", a->connection());
    auto cands = detect_faux_pas(*a, frontier, T, "2026-05-26T12:00:00Z");
    EXPECT_TRUE(cands.empty()) << "single-member cast -> no asymmetry possible";
}

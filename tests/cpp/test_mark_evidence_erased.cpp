// Tests for the dev-only `starling::testing::mark_evidence_erased` helper.
//
// Per system_design §15.3.5: the helper flips engrams.erased_at from NULL to
// an ISO-8601 timestamp and writes a `testing.mark_evidence_erased` audit
// event under a single TransactionGuard. Idempotent: missing/already-erased
// rows return false and write no audit event so replays don't trip
// UNIQUE(idempotency_key) on bus_events.
//
// Used by the M0.6 13_retrieval.md evidence-erased negative test, which
// drives BasicRetriever and asserts that statements anchored solely on
// erased engrams disappear from results.
#include "starling/testing_marker.hpp"

#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <memory>
#include <string>

namespace starling::testing {
namespace {

// INSERT a fresh engram with erased_at=NULL. The 38-column engrams schema
// (migration 0001 + 0003) has a small mandatory subset; everything else takes
// its DEFAULT. Mirrors test_basic_retriever_filter_predicates.cpp's direct-
// insert idiom — these tests exercise the testing helper, not validation.
void insert_engram(persistence::SqliteAdapter& a,
                   const std::string& id,
                   const std::string& tenant_id) {
    static constexpr const char* kInsertSql =
        "INSERT INTO engrams("
        "  id, tenant_id, content_hash, source_kind, ingest_policy,"
        "  ingest_mode, privacy_class, retention_mode, refcount,"
        "  created_at, erased_at"
        ") VALUES ("
        "  ?, ?, 'h', 'user_input', 'store',"
        "  'whole_record', 'public', 'audit_retain', 1,"
        "  '2026-04-15T00:00:00Z', NULL"
        ")";

    sqlite3_stmt* raw = nullptr;
    sqlite3* db = a.connection().raw();
    ASSERT_EQ(sqlite3_prepare_v2(db, kInsertSql, -1, &raw, nullptr), SQLITE_OK)
        << sqlite3_errmsg(db);
    persistence::StmtHandle h{raw};
    sqlite3_bind_text(raw, 1, id.c_str(),        -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, 2, tenant_id.c_str(), -1, SQLITE_TRANSIENT);
    ASSERT_EQ(sqlite3_step(raw), SQLITE_DONE) << sqlite3_errmsg(db);
}

// Returns 1 iff engrams.erased_at IS NOT NULL for (id, tenant_id), 0
// otherwise. Returns -1 if the row is missing entirely.
int erased_at_is_set(persistence::SqliteAdapter& a,
                     const std::string& id,
                     const std::string& tenant_id) {
    static constexpr const char* kSql =
        "SELECT erased_at IS NOT NULL FROM engrams "
        "WHERE id=? AND tenant_id=?";
    sqlite3_stmt* raw = nullptr;
    sqlite3* db = a.connection().raw();
    EXPECT_EQ(sqlite3_prepare_v2(db, kSql, -1, &raw, nullptr), SQLITE_OK)
        << sqlite3_errmsg(db);
    persistence::StmtHandle h{raw};
    sqlite3_bind_text(raw, 1, id.c_str(),        -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, 2, tenant_id.c_str(), -1, SQLITE_TRANSIENT);
    int rc = sqlite3_step(raw);
    if (rc == SQLITE_DONE) {
        return -1;
    }
    EXPECT_EQ(rc, SQLITE_ROW) << sqlite3_errmsg(db);
    return sqlite3_column_int(raw, 0);
}

// Counts bus_events rows of type `testing.mark_evidence_erased` for a tenant.
int audit_event_count(persistence::SqliteAdapter& a,
                      const std::string& tenant_id) {
    static constexpr const char* kSql =
        "SELECT COUNT(*) FROM bus_events "
        "WHERE event_type='testing.mark_evidence_erased' AND tenant_id=?";
    sqlite3_stmt* raw = nullptr;
    sqlite3* db = a.connection().raw();
    EXPECT_EQ(sqlite3_prepare_v2(db, kSql, -1, &raw, nullptr), SQLITE_OK)
        << sqlite3_errmsg(db);
    persistence::StmtHandle h{raw};
    sqlite3_bind_text(raw, 1, tenant_id.c_str(), -1, SQLITE_TRANSIENT);
    EXPECT_EQ(sqlite3_step(raw), SQLITE_ROW) << sqlite3_errmsg(db);
    return sqlite3_column_int(raw, 0);
}

// Returns the bus_events.created_at for the (single) audit row of type
// `testing.mark_evidence_erased` under the given tenant. The audit helper
// propagates the caller-supplied erased_at into created_at so consumers can
// correlate the event with the row's erased_at without parsing payload_json.
// Returns "" if no row matches; assumes at most one row per tenant in tests.
std::string audit_event_created_at(persistence::SqliteAdapter& a,
                                   const std::string& tenant_id) {
    static constexpr const char* kSql =
        "SELECT created_at FROM bus_events "
        "WHERE event_type='testing.mark_evidence_erased' AND tenant_id=?";
    sqlite3_stmt* raw = nullptr;
    sqlite3* db = a.connection().raw();
    EXPECT_EQ(sqlite3_prepare_v2(db, kSql, -1, &raw, nullptr), SQLITE_OK)
        << sqlite3_errmsg(db);
    persistence::StmtHandle h{raw};
    sqlite3_bind_text(raw, 1, tenant_id.c_str(), -1, SQLITE_TRANSIENT);
    int rc = sqlite3_step(raw);
    if (rc == SQLITE_DONE) {
        return std::string{};
    }
    EXPECT_EQ(rc, SQLITE_ROW) << sqlite3_errmsg(db);
    const auto* text = sqlite3_column_text(raw, 0);
    if (text == nullptr) {
        return std::string{};
    }
    return std::string(reinterpret_cast<const char*>(text));
}

class MarkEvidenceErasedTest : public ::testing::Test {
 protected:
    void SetUp() override {
        adapter_ = persistence::SqliteAdapter::open(":memory:");
        persistence::MigrationRunner(adapter_->connection().raw())
            .migrate_to_latest();
    }
    std::unique_ptr<persistence::SqliteAdapter> adapter_;
};

// ---------------------------------------------------------------- happy path
TEST_F(MarkEvidenceErasedTest, FlipsAndAudits) {
    insert_engram(*adapter_, "e-flip", "t1");
    ASSERT_EQ(erased_at_is_set(*adapter_, "e-flip", "t1"), 0);
    ASSERT_EQ(audit_event_count(*adapter_, "t1"), 0);

    EXPECT_TRUE(mark_evidence_erased(
        *adapter_, "e-flip", "t1", "2026-05-24T09:00:00Z"));

    EXPECT_EQ(erased_at_is_set(*adapter_, "e-flip", "t1"), 1);
    EXPECT_EQ(audit_event_count(*adapter_, "t1"), 1);
    // The audit envelope's created_at must reflect the caller-supplied
    // erased_at (not OutboxWriter::append's wall-clock fallback) so consumers
    // can correlate the event with the row's erased_at directly.
    EXPECT_EQ(audit_event_created_at(*adapter_, "t1"),
              "2026-05-24T09:00:00Z");
}

// ---------------------------------------------------------------- idempotency
TEST_F(MarkEvidenceErasedTest, IdempotentOnAlreadyErased) {
    // First mark transitions the row; the second mark on the same engram —
    // even with a different timestamp — must be a no-op (no UPDATE, no audit
    // row), proving the WHERE erased_at IS NULL guard works and the audit
    // row is skipped on the no-op branch.
    insert_engram(*adapter_, "e-twice", "t1");
    ASSERT_TRUE(mark_evidence_erased(
        *adapter_, "e-twice", "t1", "2026-05-24T09:00:00Z"));

    EXPECT_FALSE(mark_evidence_erased(
        *adapter_, "e-twice", "t1", "2026-05-24T10:00:00Z"));

    EXPECT_EQ(erased_at_is_set(*adapter_, "e-twice", "t1"), 1);
    EXPECT_EQ(audit_event_count(*adapter_, "t1"), 1);
}

// ----------------------------------------------------------------- missing row
TEST_F(MarkEvidenceErasedTest, FalseOnMissing) {
    // Validates that the (id, tenant_id, erased_at IS NULL) WHERE handles the
    // missing-row case identically to the wrong-state case: returns false,
    // writes no audit row, commits the empty transaction cleanly.
    EXPECT_FALSE(mark_evidence_erased(
        *adapter_, "ghost", "t1", "2026-05-24T09:00:00Z"));

    EXPECT_EQ(audit_event_count(*adapter_, "t1"), 0);
}

}  // namespace
}  // namespace starling::testing

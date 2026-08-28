// Smoke tests for SubscriberPump::run_post_write.
// Verifies the pump can be invoked on a fresh in-memory DB without throwing and
// that repeated calls are idempotent. Full integration coverage lives in the
// P2.a/M0.8 pytest + ctest suites (belief_tracker, conflict_key_backfill, etc.).

#include "starling/bus/subscriber_pump.hpp"

#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/connection.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <cstring>
#include <memory>
#include <string>

namespace starling::bus {
namespace {

using starling::persistence::SqliteAdapter;
using starling::persistence::Connection;

std::unique_ptr<SqliteAdapter> open_fresh() {
    return SqliteAdapter::open(":memory:");
}

enum class DenySavepoint { Begin, Release };

int deny_common_ground_savepoint(void* opaque, int action,
                                 const char* operation, const char* name,
                                 const char*, const char*) {
    if (action != SQLITE_SAVEPOINT || operation == nullptr || name == nullptr ||
        std::strcmp(name, "sub_common_ground") != 0) {
        return SQLITE_OK;
    }
    const auto mode = *static_cast<DenySavepoint*>(opaque);
    if (mode == DenySavepoint::Begin && std::strcmp(operation, "BEGIN") == 0)
        return SQLITE_DENY;
    if (mode == DenySavepoint::Release && std::strcmp(operation, "RELEASE") == 0)
        return SQLITE_DENY;
    return SQLITE_OK;
}

void seed_common_ground_event(Connection& conn) {
    conn.exec(
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,subject_kind,"
        "subject_id,predicate,object_kind,object_value,canonical_object_hash,"
        "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
        "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
        "scope_parties_json,created_at,updated_at) VALUES("
        "'pump-S1','default','alice','first_person','entity','topic','knows','str','x',"
        "'pump-h1','v1','believes','pos',0.8,'2026-01-01T00:00:00Z',0.5,'{}',1.0,"
        "'2026-01-01T00:00:00Z','user_input','consolidated','approved',"
        "'[\"alice\",\"bob\"]','2026-01-01T00:00:00Z','2026-01-01T00:00:00Z');"
        "INSERT INTO bus_events(event_id,tenant_id,event_type,primary_id,aggregate_id,"
        "outbox_sequence,idempotency_key,payload_json,created_at) VALUES("
        "'pump-event','default','statement.written','pump-S1','pump-S1',1,"
        "'pump-key','{}','2026-01-01T00:00:00Z');");
}

int scalar_int(sqlite3* db, const char* sql) {
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK) return -1;
    const int value = sqlite3_step(raw) == SQLITE_ROW ? sqlite3_column_int(raw, 0) : -1;
    sqlite3_finalize(raw);
    return value;
}

// 1. Run once on a fresh empty DB — must not throw.
TEST(SubscriberPump, RunPostWriteDoesNotThrow) {
    auto adapter = open_fresh();
    Connection& conn = adapter->connection();
    const std::string now_iso = "2026-05-29T12:00:00Z";
    EXPECT_NO_THROW(SubscriberPump::run_post_write(*adapter, conn, now_iso));
}

// 2. Run twice on an empty DB — must not throw either time (idempotent).
TEST(SubscriberPump, RunPostWriteIsIdempotentOnEmptyDB) {
    auto adapter = open_fresh();
    Connection& conn = adapter->connection();
    const std::string now_iso = "2026-05-29T12:00:00Z";
    EXPECT_NO_THROW(SubscriberPump::run_post_write(*adapter, conn, now_iso));
    EXPECT_NO_THROW(SubscriberPump::run_post_write(*adapter, conn, now_iso));
}

TEST(SubscriberPump, SavepointBeginFailureSkipsSubscriberWithoutPartialWork) {
    auto adapter = open_fresh();
    Connection& conn = adapter->connection();
    seed_common_ground_event(conn);
    DenySavepoint mode = DenySavepoint::Begin;
    ASSERT_EQ(SQLITE_OK,
              sqlite3_set_authorizer(conn.raw(), deny_common_ground_savepoint, &mode));

    EXPECT_NO_THROW(SubscriberPump::run_post_write(
        *adapter, conn, "2026-05-29T12:00:00Z"));
    sqlite3_set_authorizer(conn.raw(), nullptr, nullptr);

    EXPECT_EQ(scalar_int(conn.raw(), "SELECT COUNT(*) FROM common_ground"), 0);
    EXPECT_EQ(scalar_int(conn.raw(),
        "SELECT last_processed_outbox_sequence "
        "FROM common_ground_subscriber_checkpoint WHERE id=1"), 0);
    EXPECT_NE(sqlite3_get_autocommit(conn.raw()), 0);
}

TEST(SubscriberPump, ReleaseFailureRollsBackAndRestoresAutocommit) {
    auto adapter = open_fresh();
    Connection& conn = adapter->connection();
    seed_common_ground_event(conn);
    DenySavepoint mode = DenySavepoint::Release;
    ASSERT_EQ(SQLITE_OK,
              sqlite3_set_authorizer(conn.raw(), deny_common_ground_savepoint, &mode));

    EXPECT_NO_THROW(SubscriberPump::run_post_write(
        *adapter, conn, "2026-05-29T12:00:00Z"));
    sqlite3_set_authorizer(conn.raw(), nullptr, nullptr);

    EXPECT_EQ(scalar_int(conn.raw(), "SELECT COUNT(*) FROM common_ground"), 0);
    EXPECT_EQ(scalar_int(conn.raw(),
        "SELECT last_processed_outbox_sequence "
        "FROM common_ground_subscriber_checkpoint WHERE id=1"), 0);
    EXPECT_NE(sqlite3_get_autocommit(conn.raw()), 0);
    EXPECT_NO_THROW(conn.begin_immediate());
    conn.rollback();
}

}  // namespace
}  // namespace starling::bus

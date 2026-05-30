#include "starling/reconsolidation/arbitration.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
#include <sqlite3.h>
using namespace starling::reconsolidation;
using starling::persistence::SqliteAdapter;

namespace {

// Seed a CONSOLIDATED statement with the given id and confidence.
void seed_consol(sqlite3* db, const std::string& id, double conf) {
    std::string s =
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
        "subject_kind,subject_id,predicate,object_kind,object_value,canonical_object_hash,"
        "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
        "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
        "confidence_history_json,created_at,updated_at) VALUES('" + id + "','default','alice',"
        "'first_person','cognizer','bob','knows','str','x','" + std::string(64, 'a') + "','v1',"
        "'believes','pos'," + std::to_string(conf) + ",'2026-05-27T09:00:00Z',0.5,'{}',0.0,"
        "'2026-05-27T09:00:00Z','user_input','consolidated','approved','[]',"
        "'2026-05-27T09:00:00Z','2026-05-27T09:00:00Z')";
    sqlite3_exec(db, s.c_str(), nullptr, nullptr, nullptr);
}

// Read single text column from a query that returns exactly one row.
std::string scol(sqlite3* db, const std::string& q) {
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(db, q.c_str(), -1, &s, nullptr);
    sqlite3_step(s);
    std::string v = reinterpret_cast<const char*>(sqlite3_column_text(s, 0));
    sqlite3_finalize(s);
    return v;
}

// Read single integer column from a query.
int icol(sqlite3* db, const std::string& q) {
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(db, q.c_str(), -1, &s, nullptr);
    sqlite3_step(s);
    int v = sqlite3_column_int(s, 0);
    sqlite3_finalize(s);
    return v;
}

}  // namespace

// Full 4-item atomic commit assertions.
TEST(ArbitrationSevere, FourItemAtomicCommit) {
    auto a = SqliteAdapter::open(":memory:");
    auto& c = a->connection();
    seed_consol(c.raw(), "old", 0.9);

    Aggregated agg{ArbitrationPath::SevereContradict, 0.85, "agg-sev"};
    const std::string new_id =
        apply_severe_contradict(c, "old", "default", agg, "2026-05-27T11:00:00Z");

    // 1. Old row must be archived.
    EXPECT_EQ(scol(c.raw(),
        "SELECT consolidation_state FROM statements WHERE id='old'"),
        "archived");

    // 2. New row exists with correct provenance, consolidation_state, supersedes_id.
    EXPECT_EQ(scol(c.raw(),
        "SELECT provenance FROM statements WHERE id='" + new_id + "'"),
        "reconsolidation_derived");
    EXPECT_EQ(scol(c.raw(),
        "SELECT consolidation_state FROM statements WHERE id='" + new_id + "'"),
        "consolidated");
    EXPECT_EQ(scol(c.raw(),
        "SELECT supersedes_id FROM statements WHERE id='" + new_id + "'"),
        "old");

    // 3. statement_edges: exactly 1 row with dst_id='old' and edge_kind='supersedes'.
    EXPECT_EQ(icol(c.raw(),
        "SELECT COUNT(*) FROM statement_edges "
        "WHERE dst_id='old' AND edge_kind='supersedes'"),
        1);

    // 4. Outbox events: exactly 1 statement.corrected, 1 statement.archived (primary='old'),
    //    1 statement.superseded.
    EXPECT_EQ(icol(c.raw(),
        "SELECT COUNT(*) FROM bus_events WHERE event_type='statement.corrected'"),
        1);
    EXPECT_EQ(icol(c.raw(),
        "SELECT COUNT(*) FROM bus_events "
        "WHERE event_type='statement.archived' AND primary_id='old'"),
        1);
    EXPECT_EQ(icol(c.raw(),
        "SELECT COUNT(*) FROM bus_events WHERE event_type='statement.superseded'"),
        1);
}

// New version must NOT emit statement.written (防重入 Replay).
TEST(ArbitrationSevere, NewVersionNoStatementWritten) {
    auto a = SqliteAdapter::open(":memory:");
    auto& c = a->connection();
    seed_consol(c.raw(), "old2", 0.8);

    Aggregated agg{ArbitrationPath::SevereContradict, 0.9, "agg-sev2"};
    const std::string new_id =
        apply_severe_contradict(c, "old2", "default", agg, "2026-05-27T11:30:00Z");

    // Verify no statement.written for the new version.
    EXPECT_EQ(icol(c.raw(),
        "SELECT COUNT(*) FROM bus_events "
        "WHERE event_type='statement.written' AND primary_id='" + new_id + "'"),
        0);

    // Also confirm no statement.written at all (none were seeded).
    EXPECT_EQ(icol(c.raw(),
        "SELECT COUNT(*) FROM bus_events WHERE event_type='statement.written'"),
        0);

    // Sanity check: new row tenant_id matches.
    EXPECT_EQ(scol(c.raw(),
        "SELECT tenant_id FROM statements WHERE id='" + new_id + "'"),
        "default");
}

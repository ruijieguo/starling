// P2.c: SubscriberPump 第 6 subscriber policy_engine —— 经完整 pump 路径,
// COMMITS statement.written → commitment ACTIVE。验证第 6 subscriber 接通且
// 不 regress 前 5(前 5 的回归由全套覆盖)。

#include "starling/bus/subscriber_pump.hpp"
#include "starling/bus/bus_event.hpp"
#include "starling/bus/outbox_writer.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/connection.hpp"

#include <gtest/gtest.h>
#include <memory>
#include <string>

namespace starling::bus {
namespace {

using starling::persistence::SqliteAdapter;
using starling::persistence::Connection;
using starling::persistence::TransactionGuard;

void seed_commits_stmt(sqlite3* db, const std::string& id) {
    std::string s = "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
      "subject_kind,subject_id,predicate,object_kind,object_value,canonical_object_hash,"
      "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
      "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
      "created_at,updated_at) VALUES('"+id+"','default','alice','first_person','cognizer',"
      "'bob','will_send','str','report','"+std::string(64,'a')+"','v1','COMMITS','pos',0.9,"
      "'2026-05-30T09:00:00Z',0.5,'{}',0.0,'2026-05-30T09:00:00Z','user_input','consolidated',"
      "'approved','2026-05-30T09:00:00Z','2026-05-30T09:00:00Z')";
    sqlite3_exec(db, s.c_str(), nullptr, nullptr, nullptr);
}

void append_written_event(Connection& conn, const std::string& stmt_id) {
    TransactionGuard tx(conn);
    OutboxWriter ow(conn);
    BusEvent ev;
    ev.tenant_id = "default";
    ev.event_type = "statement.written";
    ev.primary_id = stmt_id;
    ev.aggregate_id = stmt_id;
    ev.idempotency_key = "written-" + stmt_id;
    ev.payload_json = "{}";
    ow.append(ev);
    tx.commit();
}

std::string scol(sqlite3* db, const std::string& q) {
    std::string out;
    sqlite3_exec(db, q.c_str(),
        [](void* p, int, char** v, char**) { *(std::string*)p = v[0] ? v[0] : ""; return 0; },
        &out, nullptr);
    return out;
}

}  // namespace

// COMMITS statement.written 经完整 pump → policy_engine subscriber 建 ACTIVE commitment。
TEST(PolicyEngineSubscriber, CommitsStatementBecomesActiveViaPump) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    seed_commits_stmt(conn.raw(), "c1");
    append_written_event(conn, "c1");
    EXPECT_NO_THROW(SubscriberPump::run_post_write(*adapter, conn, "2026-05-30T10:00:00Z"));
    EXPECT_EQ(scol(conn.raw(), "SELECT state FROM commitments WHERE stmt_id='c1'"), "ACTIVE");
}

}  // namespace starling::bus

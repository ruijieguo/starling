#include <gtest/gtest.h>

#include "starling/bus/bus.hpp"
#include "starling/evidence/engram.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/schema/enums.hpp"

#include <sqlite3.h>

#include <memory>
#include <optional>
#include <string>
#include <variant>
#include <vector>

namespace {

using starling::bus::AppendEvidenceAccepted;
using starling::bus::AppendEvidenceIdempotent;
using starling::bus::AppendEvidenceNoStore;
using starling::bus::AppendEvidenceRejected;
using starling::bus::Bus;
using starling::evidence::EngramInput;
using starling::evidence::SourceIdentity;
using starling::persistence::SqliteAdapter;
using starling::persistence::StmtHandle;
using starling::schema::EngramRetentionMode;
using starling::schema::IngestMode;
using starling::schema::PrivacyClass;
using starling::schema::SourceKind;

std::unique_ptr<SqliteAdapter> make_adapter() {
    return SqliteAdapter::open(":memory:");
}

EngramInput user_input() {
    EngramInput i;
    i.tenant_id = "t1";
    i.source.adapter_name    = "direct_api";
    i.source.adapter_version = "1.0.0";
    i.source.source_item_id  = "msg-1";
    i.source.source_version  = "1";
    i.source.chunk_index     = 0;
    i.source_kind    = SourceKind::USER_INPUT;
    i.ingest_mode    = IngestMode::WHOLE_RECORD;
    i.privacy_class  = PrivacyClass::INTERNAL;
    i.retention_mode = EngramRetentionMode::AUDIT_RETAIN;
    i.declared_transformations = {};
    i.byte_preserving  = true;
    i.payload_bytes    = std::vector<unsigned char>{'h','e','l','l','o'};
    i.redacted_content = std::nullopt;
    i.created_at_iso8601 = "2026-05-23T10:00:00Z";
    return i;
}

int row_count(SqliteAdapter& a, const char* sql) {
    sqlite3_stmt* raw = nullptr;
    EXPECT_EQ(sqlite3_prepare_v2(a.connection().raw(), sql, -1, &raw, nullptr), SQLITE_OK);
    StmtHandle s(raw);
    EXPECT_EQ(sqlite3_step(s.get()), SQLITE_ROW);
    return sqlite3_column_int(s.get(), 0);
}

std::string col_text(sqlite3_stmt* s, int idx) {
    auto* p = sqlite3_column_text(s, idx);
    return p ? std::string(reinterpret_cast<const char*>(p)) : std::string{};
}

}  // namespace

TEST(BusAppendEvidence, AcceptedPathWritesOneEngramAndOnePendingEvent) {
    auto a = make_adapter();
    Bus bus(*a);
    auto outcome = bus.append_evidence(user_input(), std::nullopt);

    ASSERT_NE(std::get_if<AppendEvidenceAccepted>(&outcome), nullptr);
    EXPECT_EQ(row_count(*a, "SELECT count(*) FROM engrams"), 1);

    sqlite3_stmt* raw = nullptr;
    ASSERT_EQ(sqlite3_prepare_v2(a->connection().raw(),
        "SELECT event_type, dispatch_status FROM bus_events", -1, &raw, nullptr), SQLITE_OK);
    StmtHandle s(raw);
    ASSERT_EQ(sqlite3_step(s.get()), SQLITE_ROW);
    EXPECT_EQ(col_text(s.get(), 0), "evidence.appended");
    EXPECT_EQ(col_text(s.get(), 1), "pending");
}

TEST(BusAppendEvidence, NoStorePathWritesZeroEngramAndOneDeliveredAuditEvent) {
    auto a = make_adapter();
    auto inp = user_input();
    inp.source_kind = SourceKind::SYSTEM_INTERNAL;

    Bus bus(*a);
    auto outcome = bus.append_evidence(inp, std::nullopt);

    EXPECT_NE(std::get_if<AppendEvidenceNoStore>(&outcome), nullptr);
    EXPECT_EQ(row_count(*a, "SELECT count(*) FROM engrams"), 0);

    sqlite3_stmt* raw = nullptr;
    ASSERT_EQ(sqlite3_prepare_v2(a->connection().raw(),
        "SELECT event_type, dispatch_status FROM bus_events", -1, &raw, nullptr), SQLITE_OK);
    StmtHandle s(raw);
    ASSERT_EQ(sqlite3_step(s.get()), SQLITE_ROW);
    EXPECT_EQ(col_text(s.get(), 0), "evidence.no_store_audit");
    EXPECT_EQ(col_text(s.get(), 1), "delivered");
}

TEST(BusAppendEvidence, IdempotentHitWritesZeroNewEngramAndOneDeliveredAuditEvent) {
    auto a = make_adapter();
    Bus bus(*a);

    auto out1 = bus.append_evidence(user_input(), std::nullopt);
    ASSERT_NE(std::get_if<AppendEvidenceAccepted>(&out1), nullptr);

    auto out2 = bus.append_evidence(user_input(), std::nullopt);
    ASSERT_NE(std::get_if<AppendEvidenceIdempotent>(&out2), nullptr);

    EXPECT_EQ(row_count(*a, "SELECT count(*) FROM engrams"), 1);

    sqlite3_stmt* raw = nullptr;
    ASSERT_EQ(sqlite3_prepare_v2(a->connection().raw(),
        "SELECT event_type, dispatch_status FROM bus_events ORDER BY outbox_sequence",
        -1, &raw, nullptr), SQLITE_OK);
    StmtHandle s(raw);
    ASSERT_EQ(sqlite3_step(s.get()), SQLITE_ROW);
    EXPECT_EQ(col_text(s.get(), 0), "evidence.appended");
    EXPECT_EQ(col_text(s.get(), 1), "pending");
    ASSERT_EQ(sqlite3_step(s.get()), SQLITE_ROW);
    EXPECT_EQ(col_text(s.get(), 0), "evidence.idempotent_hit");
    EXPECT_EQ(col_text(s.get(), 1), "delivered");
}

TEST(BusAppendEvidence, RejectedPathLeavesBothTablesEmpty) {
    auto a = make_adapter();
    auto inp = user_input();
    inp.tenant_id = "";

    Bus bus(*a);
    auto outcome = bus.append_evidence(inp, std::nullopt);

    auto* rej = std::get_if<AppendEvidenceRejected>(&outcome);
    ASSERT_NE(rej, nullptr);
    EXPECT_EQ(rej->reason, "required_field_missing:tenant_id");
    EXPECT_EQ(row_count(*a, "SELECT count(*) FROM engrams"), 0);
    EXPECT_EQ(row_count(*a, "SELECT count(*) FROM bus_events"), 0);
}

TEST(BusAppendEvidence, CausationParentBecomesFirstChainElement) {
    auto a = make_adapter();
    Bus bus(*a);
    auto outcome = bus.append_evidence(user_input(), std::string("parent-evt-abc"));

    ASSERT_NE(std::get_if<AppendEvidenceAccepted>(&outcome), nullptr);

    sqlite3_stmt* raw = nullptr;
    ASSERT_EQ(sqlite3_prepare_v2(a->connection().raw(),
        "SELECT causation_chain_json FROM bus_events WHERE event_type='evidence.appended'",
        -1, &raw, nullptr), SQLITE_OK);
    StmtHandle s(raw);
    ASSERT_EQ(sqlite3_step(s.get()), SQLITE_ROW);
    EXPECT_EQ(col_text(s.get(), 0), "[\"parent-evt-abc\"]");
}

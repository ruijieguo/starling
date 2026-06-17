// sub-project A phase 2:EpisodicEventStore —— episodic_events 表(0025)的唯一读写者。
// 镜像 src/store/sqlite_statement_store.cpp 的 StmtHandle + prepared-stmt 风格;
// 空串 ↔ SQL NULL(写经 sqlite3_bind_null,读经 nullptr → "")。
#include "starling/store/episodic_event_store.hpp"

#include <sqlite3.h>

#include "starling/persistence/sqlite_handles.hpp"
#include "starling/persistence/sqlite_helpers.hpp"

namespace starling::store {

using persistence::StmtHandle;
using persistence::detail::bind_sv;
using persistence::detail::make_sqlite_error;

namespace {

// 绑定可空 TEXT:空串 → SQL NULL,否则 TEXT。
void bind_nullable(sqlite3_stmt* s, int idx, std::string_view v) {
    if (v.empty()) {
        sqlite3_bind_null(s, idx);
    } else {
        bind_sv(s, idx, v);
    }
}

// 读列:NULL → ""。
std::string col_text(sqlite3_stmt* s, int idx) {
    const auto* t = sqlite3_column_text(s, idx);
    return t ? reinterpret_cast<const char*>(t) : "";
}

// 列顺序对齐迁移:statement_id, tenant_id, seq, event_time, location,
// participants_json, action_raw。
EpisodicEventRow read_row(sqlite3_stmt* s) {
    EpisodicEventRow row;
    row.statement_id = col_text(s, 0);
    row.tenant_id = col_text(s, 1);
    row.seq = sqlite3_column_int64(s, 2);
    row.event_time = col_text(s, 3);
    row.location = col_text(s, 4);
    row.participants_json = col_text(s, 5);
    row.action_raw = col_text(s, 6);
    return row;
}

}  // namespace

EpisodicEventStore::EpisodicEventStore(persistence::Connection& conn)
    : conn_(conn) {}

void EpisodicEventStore::upsert(const EpisodicEventRow& row) {
    sqlite3* db = conn_.raw();
    const char* sql =
        "INSERT INTO episodic_events("
        "statement_id,tenant_id,seq,event_time,location,participants_json,action_raw"
        ") VALUES(?,?,?,?,?,?,?) "
        "ON CONFLICT(statement_id,tenant_id) DO UPDATE SET "
        "seq=excluded.seq, event_time=excluded.event_time, "
        "location=excluded.location, participants_json=excluded.participants_json, "
        "action_raw=excluded.action_raw";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "EpisodicEventStore::upsert prepare");
    StmtHandle h(raw);
    bind_sv(h.get(), 1, row.statement_id);
    bind_sv(h.get(), 2, row.tenant_id);
    sqlite3_bind_int64(h.get(), 3, row.seq);
    bind_nullable(h.get(), 4, row.event_time);
    bind_nullable(h.get(), 5, row.location);
    bind_sv(h.get(), 6, row.participants_json);  // NOT NULL DEFAULT '[]'
    bind_nullable(h.get(), 7, row.action_raw);
    if (sqlite3_step(h.get()) != SQLITE_DONE)
        throw make_sqlite_error(db, "EpisodicEventStore::upsert step");
}

std::optional<EpisodicEventRow> EpisodicEventStore::get(
    std::string_view statement_id, std::string_view tenant) {
    sqlite3* db = conn_.raw();
    const char* sql =
        "SELECT statement_id,tenant_id,seq,event_time,location,participants_json,"
        "action_raw FROM episodic_events WHERE statement_id=? AND tenant_id=?";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "EpisodicEventStore::get prepare");
    StmtHandle h(raw);
    bind_sv(h.get(), 1, statement_id);
    bind_sv(h.get(), 2, tenant);
    const int rc = sqlite3_step(h.get());
    if (rc == SQLITE_ROW) return read_row(h.get());
    if (rc == SQLITE_DONE) return std::nullopt;
    throw make_sqlite_error(db, "EpisodicEventStore::get step");
}

std::vector<EpisodicEventRow> EpisodicEventStore::events_for_theme(
    std::string_view tenant, std::string_view theme_id) {
    sqlite3* db = conn_.raw();
    const char* sql =
        "SELECT e.statement_id,e.tenant_id,e.seq,e.event_time,e.location,"
        "e.participants_json,e.action_raw "
        "FROM episodic_events e "
        "JOIN statements s ON s.id=e.statement_id AND s.tenant_id=e.tenant_id "
        "WHERE e.tenant_id=? AND s.object_value=? AND s.modality='occurred' "
        "ORDER BY e.seq, e.event_time";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "EpisodicEventStore::events_for_theme prepare");
    StmtHandle h(raw);
    bind_sv(h.get(), 1, tenant);
    bind_sv(h.get(), 2, theme_id);
    std::vector<EpisodicEventRow> out;
    int rc;
    while ((rc = sqlite3_step(h.get())) == SQLITE_ROW) out.push_back(read_row(h.get()));
    if (rc != SQLITE_DONE)
        throw make_sqlite_error(db, "EpisodicEventStore::events_for_theme step");
    return out;
}

std::string EpisodicEventStore::latest_event_location(
    std::string_view tenant, std::string_view theme_id) {
    sqlite3* db = conn_.raw();
    const char* sql =
        "SELECT e.location "
        "FROM episodic_events e "
        "JOIN statements s ON s.id=e.statement_id AND s.tenant_id=e.tenant_id "
        "WHERE e.tenant_id=? AND s.object_value=? AND s.modality='occurred' "
        "ORDER BY e.seq DESC LIMIT 1";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "EpisodicEventStore::latest_event_location prepare");
    StmtHandle h(raw);
    bind_sv(h.get(), 1, tenant);
    bind_sv(h.get(), 2, theme_id);
    const int rc = sqlite3_step(h.get());
    if (rc == SQLITE_ROW) return col_text(h.get(), 0);
    if (rc == SQLITE_DONE) return "";
    throw make_sqlite_error(db, "EpisodicEventStore::latest_event_location step");
}

}  // namespace starling::store

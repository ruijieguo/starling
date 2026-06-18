// sub-project B phase 1 Task 1.1: PerceptionStateStore —— perception_state 表(0026)
// 的唯一读写者。镜像 src/store/episodic_event_store.cpp 的 StmtHandle + prepared-stmt
// 风格(bind_sv / make_sqlite_error / read_row helper)。
#include "starling/store/perception_state_store.hpp"
#include <sqlite3.h>
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/persistence/sqlite_helpers.hpp"
namespace starling::store {
using persistence::StmtHandle;
using persistence::detail::bind_sv;
using persistence::detail::make_sqlite_error;
namespace {
std::string col_text(sqlite3_stmt* s, int idx) {
    const auto* t = sqlite3_column_text(s, idx);
    return t ? reinterpret_cast<const char*>(t) : "";
}
// Column order aligns with the SELECT lists below.
PerceptionStateRow read_row(sqlite3_stmt* s) {
    PerceptionStateRow r;
    r.tenant_id = col_text(s, 0); r.cognizer_id = col_text(s, 1);
    r.theme_id = col_text(s, 2);  r.state_dim = col_text(s, 3);
    r.state_value = col_text(s, 4); r.observed_at = col_text(s, 5);
    r.position = sqlite3_column_int64(s, 6); r.source_event_id = col_text(s, 7);
    return r;
}
constexpr const char* kCols =
    "tenant_id,cognizer_id,theme_id,state_dim,state_value,observed_at,position,source_event_id";
}  // namespace

PerceptionStateStore::PerceptionStateStore(persistence::Connection& conn) : conn_(conn) {}

void PerceptionStateStore::upsert(const PerceptionStateRow& row) {
    sqlite3* db = conn_.raw();
    const char* sql =
        "INSERT INTO perception_state("
        "tenant_id,cognizer_id,theme_id,state_dim,state_value,observed_at,position,source_event_id"
        ") VALUES(?,?,?,?,?,?,?,?) "
        "ON CONFLICT(tenant_id,cognizer_id,source_event_id) DO UPDATE SET "
        "theme_id=excluded.theme_id, state_dim=excluded.state_dim, "
        "state_value=excluded.state_value, observed_at=excluded.observed_at, "
        "position=excluded.position";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "PerceptionStateStore::upsert prepare");
    StmtHandle h(raw);
    bind_sv(h.get(), 1, row.tenant_id);  bind_sv(h.get(), 2, row.cognizer_id);
    bind_sv(h.get(), 3, row.theme_id);   bind_sv(h.get(), 4, row.state_dim);
    bind_sv(h.get(), 5, row.state_value); bind_sv(h.get(), 6, row.observed_at);
    sqlite3_bind_int64(h.get(), 7, row.position);
    bind_sv(h.get(), 8, row.source_event_id);
    if (sqlite3_step(h.get()) != SQLITE_DONE)
        throw make_sqlite_error(db, "PerceptionStateStore::upsert step");
}

std::optional<PerceptionStateRow> PerceptionStateStore::last_known(
    std::string_view tenant, std::string_view cognizer,
    std::string_view theme, std::string_view state_dim, std::string_view as_of) {
    sqlite3* db = conn_.raw();
    const std::string sql = std::string("SELECT ") + kCols +
        " FROM perception_state WHERE tenant_id=? AND cognizer_id=? AND theme_id=? "
        "AND state_dim=? AND observed_at<=? ORDER BY position DESC LIMIT 1";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql.c_str(), -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "PerceptionStateStore::last_known prepare");
    StmtHandle h(raw);
    bind_sv(h.get(), 1, tenant); bind_sv(h.get(), 2, cognizer);
    bind_sv(h.get(), 3, theme);  bind_sv(h.get(), 4, state_dim); bind_sv(h.get(), 5, as_of);
    const int rc = sqlite3_step(h.get());
    if (rc == SQLITE_ROW) return read_row(h.get());
    if (rc == SQLITE_DONE) return std::nullopt;
    throw make_sqlite_error(db, "PerceptionStateStore::last_known step");
}

std::vector<PerceptionStateRow> PerceptionStateStore::perceived_for_theme(
    std::string_view tenant, std::string_view cognizer,
    std::string_view theme, std::string_view as_of) {
    sqlite3* db = conn_.raw();
    const std::string sql = std::string("SELECT ") + kCols +
        " FROM perception_state WHERE tenant_id=? AND cognizer_id=? AND theme_id=? "
        "AND observed_at<=? ORDER BY position";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql.c_str(), -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "PerceptionStateStore::perceived_for_theme prepare");
    StmtHandle h(raw);
    bind_sv(h.get(), 1, tenant); bind_sv(h.get(), 2, cognizer);
    bind_sv(h.get(), 3, theme);  bind_sv(h.get(), 4, as_of);
    std::vector<PerceptionStateRow> out;
    int rc;
    while ((rc = sqlite3_step(h.get())) == SQLITE_ROW) out.push_back(read_row(h.get()));
    if (rc != SQLITE_DONE)
        throw make_sqlite_error(db, "PerceptionStateStore::perceived_for_theme step");
    return out;
}

std::string PerceptionStateStore::latest_actual(
    std::string_view tenant, std::string_view theme,
    std::string_view state_dim, std::string_view as_of) {
    sqlite3* db = conn_.raw();
    const char* sql =
        "SELECT state_value FROM perception_state "
        "WHERE tenant_id=? AND theme_id=? AND state_dim=? AND observed_at<=? "
        "ORDER BY position DESC LIMIT 1";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "PerceptionStateStore::latest_actual prepare");
    StmtHandle h(raw);
    bind_sv(h.get(), 1, tenant); bind_sv(h.get(), 2, theme);
    bind_sv(h.get(), 3, state_dim); bind_sv(h.get(), 4, as_of);
    const int rc = sqlite3_step(h.get());
    if (rc == SQLITE_ROW) return col_text(h.get(), 0);
    if (rc == SQLITE_DONE) return "";
    throw make_sqlite_error(db, "PerceptionStateStore::latest_actual step");
}

std::string PerceptionStateStore::dim_for_theme(
    std::string_view tenant, std::string_view theme, std::string_view as_of) {
    sqlite3* db = conn_.raw();
    // content sorts first so a theme with ANY content-dim row resolves to "content".
    const char* sql =
        "SELECT state_dim FROM perception_state "
        "WHERE tenant_id=? AND theme_id=? AND observed_at<=? "
        "ORDER BY (state_dim='content') DESC LIMIT 1";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "PerceptionStateStore::dim_for_theme prepare");
    StmtHandle h(raw);
    bind_sv(h.get(), 1, tenant); bind_sv(h.get(), 2, theme); bind_sv(h.get(), 3, as_of);
    const int rc = sqlite3_step(h.get());
    if (rc == SQLITE_ROW) return col_text(h.get(), 0);
    if (rc == SQLITE_DONE) return "";
    throw make_sqlite_error(db, "PerceptionStateStore::dim_for_theme step");
}

}  // namespace starling::store

#include "starling/store/sqlite_graph_store.hpp"

#include <sqlite3.h>

#include <chrono>
#include <random>
#include <sstream>

#include "starling/persistence/sqlite_handles.hpp"
#include "starling/persistence/sqlite_helpers.hpp"

namespace starling::store {

using persistence::StmtHandle;
using persistence::detail::bind_sv;
using persistence::detail::iso8601_utc;
using persistence::detail::make_sqlite_error;

namespace {
std::string random_edge_id() {
    static thread_local std::mt19937_64 rng{std::random_device{}()};
    const std::uint64_t a = rng(), b = rng();
    std::ostringstream oss;
    oss << std::hex << a << b;
    return oss.str();
}

EdgeOut read_edge(sqlite3_stmt* h) {
    auto txt = [&](int i) -> std::string {
        const auto* p = sqlite3_column_text(h, i);
        return p ? reinterpret_cast<const char*>(p) : "";
    };
    EdgeOut e;
    e.id = txt(0); e.src_id = txt(1); e.dst_id = txt(2);
    e.edge_kind = txt(3); e.weight = sqlite3_column_double(h, 4);
    if (sqlite3_column_type(h, 5) != SQLITE_NULL) e.canonical_conflict_key = txt(5);
    return e;
}

constexpr const char* kEdgeCols =
    "id, src_id, dst_id, edge_kind, weight, canonical_conflict_key";
}  // namespace

EdgeInsert SqliteGraphStore::insert_edge(const EdgeRecord& r) {
    sqlite3* db = conn_.raw();
    const std::string id  = random_edge_id();
    const std::string now = r.created_at.empty()
        ? iso8601_utc(std::chrono::system_clock::now()) : r.created_at;
    const char* sql =
        "INSERT INTO statement_edges"
        "(id, tenant_id, src_id, dst_id, edge_kind, weight, "
        " canonical_conflict_key, created_at, metadata_json) "
        "VALUES(?,?,?,?,?,?,?,?,?)";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "SqliteGraphStore::insert_edge prepare");
    StmtHandle h(raw);
    bind_sv(h.get(), 1, id);
    bind_sv(h.get(), 2, r.tenant_id);
    bind_sv(h.get(), 3, r.src_id);
    bind_sv(h.get(), 4, r.dst_id);
    bind_sv(h.get(), 5, r.edge_kind);
    sqlite3_bind_double(h.get(), 6, r.weight);
    if (r.canonical_conflict_key) bind_sv(h.get(), 7, *r.canonical_conflict_key);
    else sqlite3_bind_null(h.get(), 7);
    bind_sv(h.get(), 8, now);
    bind_sv(h.get(), 9, r.metadata_json.empty() ? "{}" : r.metadata_json);
    const int rc = sqlite3_step(h.get());
    if (rc == SQLITE_DONE) return {id, false};
    // conflicts_with 的 canonical_conflict_key UNIQUE(0009 partial index)命中 →
    // 静默 dedup(已存在边保留,不插入),封装 spec §8.4 去重。WARN 由调用方据
    // deduped 决定(业务日志不入 store)。
    if (rc == SQLITE_CONSTRAINT && r.canonical_conflict_key)
        return {std::string(), true};
    throw make_sqlite_error(db, "SqliteGraphStore::insert_edge step");
}

std::vector<EdgeOut> SqliteGraphStore::neighbors(
    std::string_view tenant_id, std::string_view src_id,
    const std::vector<std::string>& kinds) {
    sqlite3* db = conn_.raw();
    std::string sql = std::string("SELECT ") + kEdgeCols +
        " FROM statement_edges WHERE tenant_id=?1 AND src_id=?2";
    if (!kinds.empty()) {
        sql += " AND edge_kind IN (";
        for (std::size_t i = 0; i < kinds.size(); ++i)
            sql += (i ? ",?" : "?") + std::to_string(static_cast<int>(i) + 3);
        sql += ")";
    }
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql.c_str(), -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "SqliteGraphStore::neighbors prepare");
    StmtHandle h(raw);
    bind_sv(h.get(), 1, tenant_id);
    bind_sv(h.get(), 2, src_id);
    for (std::size_t i = 0; i < kinds.size(); ++i)
        bind_sv(h.get(), static_cast<int>(i) + 3, kinds[i]);
    std::vector<EdgeOut> out;
    while (sqlite3_step(h.get()) == SQLITE_ROW) out.push_back(read_edge(h.get()));
    return out;
}

std::vector<EdgeOut> SqliteGraphStore::edges_by_conflict_key(
    std::string_view tenant_id, std::string_view key) {
    sqlite3* db = conn_.raw();
    const std::string sql = std::string("SELECT ") + kEdgeCols +
        " FROM statement_edges WHERE tenant_id=?1 AND canonical_conflict_key=?2";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql.c_str(), -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "SqliteGraphStore::edges_by_conflict_key prepare");
    StmtHandle h(raw);
    bind_sv(h.get(), 1, tenant_id);
    bind_sv(h.get(), 2, key);
    std::vector<EdgeOut> out;
    while (sqlite3_step(h.get()) == SQLITE_ROW) out.push_back(read_edge(h.get()));
    return out;
}

}  // namespace starling::store

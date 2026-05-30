#include "starling/tom/common_ground_writer.hpp"

#include "starling/bus/sqlite_helpers.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <cstdio>
#include <ctime>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>

namespace starling::tom {

namespace {

using starling::bus::detail::bind_sv;
using starling::bus::detail::make_sqlite_error;
using starling::persistence::StmtHandle;

std::string random_hex_32() {
    static thread_local std::mt19937_64 rng{std::random_device{}()};
    const std::uint64_t a = rng();
    const std::uint64_t b = rng();
    char buf[33];
    std::snprintf(buf, sizeof(buf), "%016llx%016llx",
                  static_cast<unsigned long long>(a),
                  static_cast<unsigned long long>(b));
    return std::string(buf, 32);
}

std::string json_array_of_strings(const std::vector<std::string>& items) {
    std::ostringstream oss;
    oss << '[';
    for (std::size_t i = 0; i < items.size(); ++i) {
        if (i != 0) oss << ',';
        oss << '"';
        for (char c : items[i]) {
            if (c == '"' || c == '\\') oss << '\\';
            oss << c;
        }
        oss << '"';
    }
    oss << ']';
    return oss.str();
}

// Parse ISO-8601 UTC string to epoch seconds.
std::time_t parse_iso_epoch(std::string_view iso) {
    std::tm tm{};
    int y, mo, d, h, mi, s;
    if (std::sscanf(std::string(iso).c_str(), "%d-%d-%dT%d:%d:%dZ",
                    &y, &mo, &d, &h, &mi, &s) != 6) return 0;
    tm.tm_year = y - 1900; tm.tm_mon = mo - 1; tm.tm_mday = d;
    tm.tm_hour = h; tm.tm_min = mi; tm.tm_sec = s;
    return timegm(&tm);
}

// Reformat epoch as ISO-8601 UTC string.
std::string epoch_to_iso(std::time_t t) {
    std::tm tm{};
    gmtime_r(&t, &tm);
    char buf[21];
    std::snprintf(buf, sizeof(buf), "%04d-%02d-%02dT%02d:%02d:%02dZ",
                  tm.tm_year + 1900, tm.tm_mon + 1, tm.tm_mday,
                  tm.tm_hour, tm.tm_min, tm.tm_sec);
    return std::string(buf);
}

// Insert a grounding_acts audit row.
void log_act(sqlite3* db,
             std::string_view tenant_id,
             std::string_view cg_id,
             std::string_view act,
             std::string_view actor,
             std::string_view statement_id,
             std::string_view now_iso) {
    const std::string act_id = random_hex_32();
    const char* sql =
        "INSERT INTO grounding_acts"
        "(id,tenant_id,common_ground_id,act,actor_cognizer_id,statement_id,occurred_at,metadata_json)"
        " VALUES(?,?,?,?,?,?,?,'{}')" ;
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "log_act prepare");
    StmtHandle h(raw);
    bind_sv(h.get(), 1, act_id);
    bind_sv(h.get(), 2, tenant_id);
    bind_sv(h.get(), 3, cg_id);
    bind_sv(h.get(), 4, act);
    bind_sv(h.get(), 5, actor);
    bind_sv(h.get(), 6, statement_id);
    bind_sv(h.get(), 7, now_iso);
    if (sqlite3_step(h.get()) != SQLITE_DONE)
        throw make_sqlite_error(db, "log_act step");
}

}  // namespace

CommonGroundWriter::CommonGroundWriter(persistence::SqliteAdapter& adapter)
    : adapter_(adapter) {
    (void)adapter_;
}

std::string CommonGroundWriter::assert_(persistence::Connection& conn,
                                         std::string_view tenant_id,
                                         std::string_view stmt_id,
                                         const std::vector<std::string>& parties,
                                         std::string_view now_iso) {
    const std::string cg_id      = random_hex_32();
    const std::string parties_js = json_array_of_strings(parties);
    sqlite3* db = conn.raw();

    const char* sql =
        "INSERT INTO common_ground"
        "(id,tenant_id,statement_id,status,parties_json,created_at,updated_at)"
        " VALUES(?,?,?,'asserted_unack',?,?,?)";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "assert_ prepare");
    StmtHandle h(raw);
    bind_sv(h.get(), 1, cg_id);
    bind_sv(h.get(), 2, tenant_id);
    bind_sv(h.get(), 3, stmt_id);
    bind_sv(h.get(), 4, parties_js);
    bind_sv(h.get(), 5, now_iso);
    bind_sv(h.get(), 6, now_iso);
    if (sqlite3_step(h.get()) != SQLITE_DONE)
        throw make_sqlite_error(db, "assert_ step");

    log_act(db, tenant_id, cg_id, "assert", "", stmt_id, now_iso);
    return cg_id;
}

void CommonGroundWriter::acknowledge(persistence::Connection& conn,
                                      std::string_view cg_id,
                                      std::string_view actor,
                                      std::string_view now_iso) {
    sqlite3* db = conn.raw();
    const char* sql =
        "UPDATE common_ground"
        " SET status='grounded', grounded_at=?, last_confirmed_at=?, updated_at=?"
        " WHERE id=?";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "acknowledge prepare");
    StmtHandle h(raw);
    bind_sv(h.get(), 1, now_iso);
    bind_sv(h.get(), 2, now_iso);
    bind_sv(h.get(), 3, now_iso);
    bind_sv(h.get(), 4, cg_id);
    if (sqlite3_step(h.get()) != SQLITE_DONE)
        throw make_sqlite_error(db, "acknowledge step");

    // Fetch tenant_id for the audit log.
    std::string tenant_id;
    {
        const char* q = "SELECT tenant_id FROM common_ground WHERE id=?";
        sqlite3_stmt* qraw = nullptr;
        if (sqlite3_prepare_v2(db, q, -1, &qraw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(db, "common_ground_writer: prepare tenant_id lookup");
        StmtHandle qh(qraw);
        bind_sv(qh.get(), 1, cg_id);
        if (sqlite3_step(qh.get()) == SQLITE_ROW) {
            const auto* t = sqlite3_column_text(qh.get(), 0);
            tenant_id = t ? reinterpret_cast<const char*>(t) : "";
        }
    }
    log_act(db, tenant_id, cg_id, "acknowledge", actor, "", now_iso);
}

void CommonGroundWriter::repair(persistence::Connection& conn,
                                 std::string_view cg_id,
                                 std::string_view actor,
                                 std::string_view now_iso) {
    sqlite3* db = conn.raw();
    const char* sql =
        "UPDATE common_ground"
        " SET status='suspected_diverge', updated_at=?"
        " WHERE id=?";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "repair prepare");
    StmtHandle h(raw);
    bind_sv(h.get(), 1, now_iso);
    bind_sv(h.get(), 2, cg_id);
    if (sqlite3_step(h.get()) != SQLITE_DONE)
        throw make_sqlite_error(db, "repair step");

    std::string tenant_id;
    {
        const char* q = "SELECT tenant_id FROM common_ground WHERE id=?";
        sqlite3_stmt* qraw = nullptr;
        if (sqlite3_prepare_v2(db, q, -1, &qraw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(db, "common_ground_writer: prepare tenant_id lookup");
        StmtHandle qh(qraw);
        bind_sv(qh.get(), 1, cg_id);
        if (sqlite3_step(qh.get()) == SQLITE_ROW) {
            const auto* t = sqlite3_column_text(qh.get(), 0);
            tenant_id = t ? reinterpret_cast<const char*>(t) : "";
        }
    }
    log_act(db, tenant_id, cg_id, "repair", actor, "", now_iso);
}

void CommonGroundWriter::withdraw(persistence::Connection& conn,
                                   std::string_view cg_id,
                                   std::string_view actor,
                                   std::string_view now_iso) {
    sqlite3* db = conn.raw();
    const char* sql =
        "UPDATE common_ground"
        " SET status='recanted', updated_at=?"
        " WHERE id=?";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "withdraw prepare");
    StmtHandle h(raw);
    bind_sv(h.get(), 1, now_iso);
    bind_sv(h.get(), 2, cg_id);
    if (sqlite3_step(h.get()) != SQLITE_DONE)
        throw make_sqlite_error(db, "withdraw step");

    std::string tenant_id;
    {
        const char* q = "SELECT tenant_id FROM common_ground WHERE id=?";
        sqlite3_stmt* qraw = nullptr;
        if (sqlite3_prepare_v2(db, q, -1, &qraw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(db, "common_ground_writer: prepare tenant_id lookup");
        StmtHandle qh(qraw);
        bind_sv(qh.get(), 1, cg_id);
        if (sqlite3_step(qh.get()) == SQLITE_ROW) {
            const auto* t = sqlite3_column_text(qh.get(), 0);
            tenant_id = t ? reinterpret_cast<const char*>(t) : "";
        }
    }
    log_act(db, tenant_id, cg_id, "withdraw", actor, "", now_iso);
}

void CommonGroundWriter::supersede_ground(persistence::Connection& conn,
                                           std::string_view old_cg_id,
                                           std::string_view new_stmt_id,
                                           std::string_view now_iso) {
    sqlite3* db = conn.raw();
    const char* sql =
        "UPDATE common_ground"
        " SET superseded_by=?, updated_at=?"
        " WHERE id=?";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "supersede_ground prepare");
    StmtHandle h(raw);
    bind_sv(h.get(), 1, new_stmt_id);
    bind_sv(h.get(), 2, now_iso);
    bind_sv(h.get(), 3, old_cg_id);
    if (sqlite3_step(h.get()) != SQLITE_DONE)
        throw make_sqlite_error(db, "supersede_ground step");

    std::string tenant_id;
    {
        const char* q = "SELECT tenant_id FROM common_ground WHERE id=?";
        sqlite3_stmt* qraw = nullptr;
        if (sqlite3_prepare_v2(db, q, -1, &qraw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(db, "common_ground_writer: prepare tenant_id lookup");
        StmtHandle qh(qraw);
        bind_sv(qh.get(), 1, old_cg_id);
        if (sqlite3_step(qh.get()) == SQLITE_ROW) {
            const auto* t = sqlite3_column_text(qh.get(), 0);
            tenant_id = t ? reinterpret_cast<const char*>(t) : "";
        }
    }
    log_act(db, tenant_id, old_cg_id, "supersede", "", new_stmt_id, now_iso);
}

int CommonGroundWriter::sweep_timeout_downgrade(persistence::Connection& conn,
                                                  std::string_view now_iso) {
    // Compute cutoff = now - 24h, format back to ISO.
    const std::time_t now_epoch  = parse_iso_epoch(now_iso);
    const std::time_t cutoff_ep  = now_epoch - 86400;
    const std::string cutoff_iso = epoch_to_iso(cutoff_ep);

    sqlite3* db = conn.raw();
    const char* sql =
        "UPDATE common_ground"
        " SET status='suspected_diverge', updated_at=?"
        " WHERE status='asserted_unack' AND created_at < ?";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "sweep_timeout_downgrade prepare");
    StmtHandle h(raw);
    bind_sv(h.get(), 1, now_iso);
    bind_sv(h.get(), 2, cutoff_iso);
    if (sqlite3_step(h.get()) != SQLITE_DONE)
        throw make_sqlite_error(db, "sweep_timeout_downgrade step");

    return sqlite3_changes(db);
}

}  // namespace starling::tom

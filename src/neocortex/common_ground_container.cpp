#include "starling/neocortex/common_ground_container.hpp"
#include "starling/neocortex/persona_container.hpp"

#include "starling/bus/sqlite_helpers.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <cstdint>
#include <cstdio>
#include <map>
#include <random>
#include <sstream>
#include <string>
#include <vector>

namespace starling::neocortex {

using starling::bus::detail::bind_sv;
using starling::bus::detail::make_sqlite_error;
using starling::persistence::StmtHandle;

namespace {

std::string cg_random_hex_32() {
    static thread_local std::mt19937_64 rng{std::random_device{}()};
    const std::uint64_t a = rng();
    const std::uint64_t b = rng();
    char buf[33];
    std::snprintf(buf, sizeof(buf), "%016llx%016llx",
                  static_cast<unsigned long long>(a),
                  static_cast<unsigned long long>(b));
    return std::string(buf, 32);
}

// Minimal JSON string escaping.
std::string cg_json_str(std::string_view sv) {
    std::string out;
    out.reserve(sv.size() + 2);
    out.push_back('"');
    for (char c : sv) {
        if (c == '"')       { out += "\\\""; }
        else if (c == '\\') { out += "\\\\"; }
        else                { out.push_back(c); }
    }
    out.push_back('"');
    return out;
}

}  // namespace

CommonGroundContainer::CommonGroundContainer(persistence::SqliteAdapter& adapter)
    : adapter_(adapter) {}

void CommonGroundContainer::rebuild(
    persistence::Connection& conn,
    std::string_view tenant_id,
    std::string_view cg_ref)
{
    sqlite3* db = conn.raw();

    // ── Step 1: Collect statement_ids grouped by status ───────────────────────
    // Only collect grounded, asserted_unack, suspected_diverge (ignore expired/recanted).
    std::vector<std::string> grounded;
    std::vector<std::string> asserted_unack;
    std::vector<std::string> suspected_diverge;

    {
        const char* sel_sql =
            "SELECT statement_id, status FROM common_ground "
            "WHERE tenant_id=? AND status IN ('grounded','asserted_unack','suspected_diverge')";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db, sel_sql, -1, &raw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(db, "CommonGroundContainer::rebuild: prepare SELECT");
        StmtHandle h(raw);
        bind_sv(h.get(), 1, tenant_id);
        while (sqlite3_step(h.get()) == SQLITE_ROW) {
            const auto* sid_txt = sqlite3_column_text(h.get(), 0);
            const auto* sta_txt = sqlite3_column_text(h.get(), 1);
            std::string sid = sid_txt ? reinterpret_cast<const char*>(sid_txt) : "";
            std::string sta = sta_txt ? reinterpret_cast<const char*>(sta_txt) : "";
            if (sta == "grounded")          grounded.push_back(sid);
            else if (sta == "asserted_unack") asserted_unack.push_back(sid);
            else if (sta == "suspected_diverge") suspected_diverge.push_back(sid);
        }
    }

    // ── Step 2: Build content_json ────────────────────────────────────────────
    auto build_array = [](const std::vector<std::string>& ids) -> std::string {
        std::ostringstream out;
        out << "[";
        for (std::size_t i = 0; i < ids.size(); ++i) {
            if (i > 0) out << ",";
            out << cg_json_str(ids[i]);
        }
        out << "]";
        return out.str();
    };

    std::ostringstream cj;
    cj << "{\"grounded\":" << build_array(grounded)
       << ",\"asserted_unack\":" << build_array(asserted_unack)
       << ",\"suspected_diverge\":" << build_array(suspected_diverge)
       << "}";
    const std::string content_json = cj.str();

    // ── Step 3: CAS write into containers (kind='common_ground') ─────────────
    static constexpr const char* kNow = "2026-05-27T00:00:00Z";

    // Check if a row exists already.
    std::string existing_id;
    int64_t existing_version = 0;
    {
        const char* sel_sql =
            "SELECT id, version FROM containers "
            "WHERE tenant_id=? AND holder_id=? AND kind='common_ground' LIMIT 1";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db, sel_sql, -1, &raw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(db, "CommonGroundContainer::rebuild: prepare SELECT containers");
        StmtHandle h(raw);
        bind_sv(h.get(), 1, tenant_id);
        bind_sv(h.get(), 2, cg_ref);
        if (sqlite3_step(h.get()) == SQLITE_ROW) {
            const auto* txt = sqlite3_column_text(h.get(), 0);
            existing_id = txt ? reinterpret_cast<const char*>(txt) : "";
            existing_version = sqlite3_column_int64(h.get(), 1);
        }
    }

    if (existing_id.empty()) {
        // INSERT new row with version=1
        const std::string new_id = cg_random_hex_32();
        const char* ins_sql =
            "INSERT INTO containers("
            "id, tenant_id, kind, holder_id, scope_descriptor, "
            "content_json, version, created_at, updated_at) "
            "VALUES(?,?,'common_ground',?,'{}',?,1,?,?)";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db, ins_sql, -1, &raw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(db, "CommonGroundContainer::rebuild: prepare INSERT");
        StmtHandle h(raw);
        bind_sv(h.get(), 1, new_id);
        bind_sv(h.get(), 2, tenant_id);
        bind_sv(h.get(), 3, cg_ref);
        bind_sv(h.get(), 4, content_json);
        bind_sv(h.get(), 5, kNow);
        bind_sv(h.get(), 6, kNow);
        if (sqlite3_step(h.get()) != SQLITE_DONE)
            throw make_sqlite_error(db, "CommonGroundContainer::rebuild: INSERT step");
    } else {
        // CAS: UPDATE WHERE version == existing_version
        const char* upd_sql =
            "UPDATE containers SET content_json=?, version=version+1, updated_at=? "
            "WHERE tenant_id=? AND holder_id=? AND kind='common_ground' AND version=?";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db, upd_sql, -1, &raw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(db, "CommonGroundContainer::rebuild: prepare UPDATE");
        StmtHandle h(raw);
        bind_sv(h.get(), 1, content_json);
        bind_sv(h.get(), 2, kNow);
        bind_sv(h.get(), 3, tenant_id);
        bind_sv(h.get(), 4, cg_ref);
        sqlite3_bind_int64(h.get(), 5, existing_version);
        if (sqlite3_step(h.get()) != SQLITE_DONE)
            throw make_sqlite_error(db, "CommonGroundContainer::rebuild: UPDATE step");
        if (sqlite3_changes(db) == 0)
            throw ConcurrentRebuildError{};
    }
}

}  // namespace starling::neocortex

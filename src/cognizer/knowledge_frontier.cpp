#include "starling/cognizer/knowledge_frontier.hpp"

#include "starling/persistence/sqlite_helpers.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <sqlite3.h>

#include <optional>
#include <random>
#include <sstream>
#include <stdexcept>

namespace starling::cognizer {

namespace {

using starling::persistence::detail::bind_sv;
using starling::persistence::detail::make_sqlite_error;
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

void insert_presence(
    persistence::Connection& conn,
    std::string_view tenant_id,
    std::string_view cognizer_id,
    std::string_view engram_id,
    std::string_view observed_at) {
    sqlite3_stmt* raw = nullptr;
    // Use a deterministic id based on (cognizer, engram) so re-runs
    // are idempotent via INSERT OR IGNORE on the synthesized PK.
    const std::string syn_id = std::string(cognizer_id) + ":" + std::string(engram_id);
    const char* sql =
        "INSERT OR IGNORE INTO cognizer_presence_log "
        "(id, tenant_id, cognizer_id, engram_id, observed_at, channel) "
        "VALUES (?, ?, ?, ?, ?, 'default')";
    if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(conn.raw(), "insert_presence: prepare");
    }
    StmtHandle h(raw);
    bind_sv(h.get(), 1, syn_id);
    bind_sv(h.get(), 2, tenant_id);
    bind_sv(h.get(), 3, cognizer_id);
    bind_sv(h.get(), 4, engram_id);
    bind_sv(h.get(), 5, observed_at);
    if (sqlite3_step(h.get()) != SQLITE_DONE) {
        throw make_sqlite_error(conn.raw(), "insert_presence: step");
    }
}

void insert_frontier_fact(
    persistence::Connection& conn,
    std::string_view tenant_id,
    std::string_view cognizer_id,
    std::optional<std::string_view> statement_id,
    std::optional<std::string_view> source_engram_id,
    std::string_view fact_kind,
    std::string_view asserted_at,
    std::string_view metadata_json) {
    // Synthesized id: cognizer + fact_kind + (statement_id or engram_id) for idempotency
    std::ostringstream id_oss;
    id_oss << cognizer_id << ":" << fact_kind << ":";
    if (statement_id) id_oss << *statement_id;
    else if (source_engram_id) id_oss << *source_engram_id;
    else id_oss << random_hex_32();
    const std::string syn_id = id_oss.str();

    sqlite3_stmt* raw = nullptr;
    const char* sql =
        "INSERT OR IGNORE INTO cognizer_frontier_facts "
        "(id, tenant_id, cognizer_id, statement_id, source_engram_id, "
        " fact_kind, asserted_at, metadata_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)";
    if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(conn.raw(), "insert_frontier_fact: prepare");
    }
    StmtHandle h(raw);
    bind_sv(h.get(), 1, syn_id);
    bind_sv(h.get(), 2, tenant_id);
    bind_sv(h.get(), 3, cognizer_id);
    if (statement_id) bind_sv(h.get(), 4, *statement_id);
    else              sqlite3_bind_null(h.get(), 4);
    if (source_engram_id) bind_sv(h.get(), 5, *source_engram_id);
    else                  sqlite3_bind_null(h.get(), 5);
    bind_sv(h.get(), 6, fact_kind);
    bind_sv(h.get(), 7, asserted_at);
    bind_sv(h.get(), 8, metadata_json);
    if (sqlite3_step(h.get()) != SQLITE_DONE) {
        throw make_sqlite_error(conn.raw(), "insert_frontier_fact: step");
    }
}

}  // namespace

KnowledgeFrontier::KnowledgeFrontier(persistence::SqliteAdapter& adapter)
    : adapter_(adapter) {}

void KnowledgeFrontier::record_presence_from_statement(
    std::string_view tenant_id,
    const std::vector<std::string>& perceived_by,
    std::string_view engram_id,
    std::string_view observed_at,
    persistence::Connection& conn) {
    for (const auto& cog : perceived_by) {
        insert_presence(conn, tenant_id, cog, engram_id, observed_at);
    }
}

void KnowledgeFrontier::record_explicit_told(
    std::string_view tenant_id,
    const std::vector<std::string>& perceived_by,
    std::string_view statement_id,
    std::string_view source_engram_id,
    std::string_view observed_at,
    persistence::Connection& conn) {
    for (const auto& cog : perceived_by) {
        insert_frontier_fact(conn, tenant_id, cog,
            statement_id, source_engram_id, "explicit_told",
            observed_at, "{}");
    }
}

void KnowledgeFrontier::record_accessible_source(
    std::string_view tenant_id,
    std::string_view cognizer_id,
    std::string_view adapter_name,
    std::string_view source_engram_id,
    std::string_view observed_at,
    persistence::Connection& conn) {
    std::string metadata = std::string("{\"adapter_name\":\"")
        + std::string(adapter_name) + "\"}";
    insert_frontier_fact(conn, tenant_id, cognizer_id,
        std::nullopt, source_engram_id, "accessible_source",
        observed_at, metadata);
}

void KnowledgeFrontier::record_group_membership(
    std::string_view tenant_id,
    std::string_view cognizer_id,
    std::string_view group_id,
    std::string_view at_iso8601,
    persistence::Connection& conn) {
    std::string metadata = std::string("{\"group_id\":\"")
        + std::string(group_id) + "\"}";
    insert_frontier_fact(conn, tenant_id, cognizer_id,
        std::nullopt, std::nullopt, "membership",
        at_iso8601, metadata);
}

void KnowledgeFrontier::record_explicit_negation(
    std::string_view tenant_id,
    std::string_view cognizer_id,
    std::string_view referenced_statement_id,
    std::string_view source_engram_id,
    std::string_view observed_at,
    persistence::Connection& conn) {
    insert_frontier_fact(conn, tenant_id, cognizer_id,
        referenced_statement_id, source_engram_id, "explicit_not_told",
        observed_at, "{}");
}

std::unordered_set<std::string> KnowledgeFrontier::visible_engrams_at(
    std::string_view tenant_id,
    std::string_view cognizer_id,
    std::string_view as_of_iso8601) const {
    // Spec §6.5: 五路并集 - explicit_not_told 减集
    //   visible = presence_log ∪ explicit_told ∪ accessible_source ∪ membership
    //             − explicit_not_told
    auto& conn = adapter_.connection();
    sqlite3* db = conn.raw();
    sqlite3_stmt* raw = nullptr;
    const char* sql =
        "SELECT engram_id FROM cognizer_presence_log "
        " WHERE tenant_id = ?1 AND cognizer_id = ?2 AND observed_at <= ?3 "
        "UNION "
        "SELECT source_engram_id FROM cognizer_frontier_facts "
        " WHERE tenant_id = ?1 AND cognizer_id = ?2 "
        "   AND fact_kind IN ('explicit_told','accessible_source','membership') "
        "   AND asserted_at <= ?3 "
        "   AND source_engram_id IS NOT NULL "
        "EXCEPT "
        "SELECT source_engram_id FROM cognizer_frontier_facts "
        " WHERE tenant_id = ?1 AND cognizer_id = ?2 "
        "   AND fact_kind = 'explicit_not_told' "
        "   AND asserted_at <= ?3 "
        "   AND source_engram_id IS NOT NULL";
    if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(db, "visible_engrams_at: prepare");
    }
    StmtHandle h(raw);
    bind_sv(h.get(), 1, tenant_id);
    bind_sv(h.get(), 2, cognizer_id);
    bind_sv(h.get(), 3, as_of_iso8601);

    std::unordered_set<std::string> out;
    while (sqlite3_step(h.get()) == SQLITE_ROW) {
        if (sqlite3_column_type(h.get(), 0) != SQLITE_NULL) {
            out.insert(reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 0)));
        }
    }
    return out;
}

}  // namespace starling::cognizer

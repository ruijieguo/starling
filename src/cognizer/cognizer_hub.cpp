#include "starling/cognizer/cognizer_hub.hpp"

#include "starling/bus/sqlite_helpers.hpp"
#include "starling/cognizer/alias_normalizer.hpp"
#include "starling/cognizer/uuid5.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/version.hpp"

#include <algorithm>
#include <chrono>
#include <ctime>
#include <sstream>
#include <stdexcept>
#include <string>

namespace starling::cognizer {

namespace {

using starling::bus::detail::bind_sv;
using starling::bus::detail::iso8601_utc;
using starling::bus::detail::make_sqlite_error;
using starling::persistence::StmtHandle;

std::string compose_uuid5_name(CognizerKind kind, std::string_view external_id) {
    return std::string(to_string(kind)) + "\x1f" + std::string(external_id);
}

std::string longest_alias_or_default(const std::vector<std::string>& aliases,
                                      std::string_view fallback) {
    if (aliases.empty()) return std::string(fallback);
    return *std::max_element(aliases.begin(), aliases.end(),
        [](const std::string& a, const std::string& b) { return a.size() < b.size(); });
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

// Parse JSON array of strings — minimal, no nested escapes beyond \" and \\.
std::vector<std::string> parse_string_array(std::string_view j) {
    std::vector<std::string> out;
    if (j.size() < 2 || j.front() != '[' || j.back() != ']') return out;
    std::size_t i = 1;
    while (i < j.size() - 1) {
        while (i < j.size() - 1 && (j[i] == ' ' || j[i] == ',')) ++i;
        if (i >= j.size() - 1 || j[i] != '"') break;
        ++i;
        std::string cur;
        while (i < j.size() - 1 && j[i] != '"') {
            if (j[i] == '\\' && i + 1 < j.size() - 1) {
                cur.push_back(j[i + 1]);
                i += 2;
            } else {
                cur.push_back(j[i]);
                ++i;
            }
        }
        out.push_back(std::move(cur));
        if (i < j.size() - 1) ++i;
    }
    return out;
}

}  // namespace

CognizerHub::CognizerHub(persistence::SqliteAdapter& adapter)
    : adapter_(adapter) {}

Cognizer CognizerHub::register_cognizer(const CognizerRegistration& req) {
    // ── Validate group tenant rule ──
    if (req.kind == CognizerKind::Group
        && req.tenant_id == "default"
        && !req.tenant_explicitly_set) {
        throw GroupTenantImplicit();
    }

    // ── Compute UUID5 id ──
    const std::string id = compute_uuid5(
        kStarlingCognizerNamespace,
        compose_uuid5_name(req.kind, req.external_id));

    // ── Compose canonical_name + aliases (raw + normalized) ──
    const std::string canonical = req.canonical_name.empty()
        ? longest_alias_or_default(req.aliases, req.external_id)
        : req.canonical_name;
    const std::string canonical_normalized = normalize_alias(canonical);

    // Only add canonical to aliases when there is explicit content (explicit canonical_name
    // or explicit aliases).  When both are absent the canonical_name defaults to external_id
    // for display only — we do NOT auto-inject external_id as an alias, so two cognizers of
    // different kinds with the same external_id can coexist without an AliasCollision.
    std::vector<std::string> aliases_raw = req.aliases;
    const bool has_explicit_aliases =
        !req.canonical_name.empty() || !req.aliases.empty();
    if (has_explicit_aliases &&
        std::find(aliases_raw.begin(), aliases_raw.end(), canonical) == aliases_raw.end()) {
        aliases_raw.push_back(canonical);
    }
    std::vector<std::string> aliases_normalized;
    aliases_normalized.reserve(aliases_raw.size());
    for (const auto& a : aliases_raw) aliases_normalized.push_back(normalize_alias(a));

    // ── AliasCollision check ──
    auto& conn = adapter_.connection();
    sqlite3* db = conn.raw();
    for (const auto& norm : aliases_normalized) {
        sqlite3_stmt* raw_stmt = nullptr;
        const char* sql =
            "SELECT id FROM cognizers "
            " WHERE tenant_id = ?1 "
            "   AND id != ?2 "
            "   AND EXISTS ("
            "     SELECT 1 FROM json_each(aliases_normalized_json) j "
            "      WHERE j.value = ?3"
            "   ) LIMIT 1";
        if (sqlite3_prepare_v2(db, sql, -1, &raw_stmt, nullptr) != SQLITE_OK) {
            throw make_sqlite_error(db, "CognizerHub::register: prepare alias-collision check");
        }
        StmtHandle h(raw_stmt);
        bind_sv(h.get(), 1, req.tenant_id);
        bind_sv(h.get(), 2, id);
        bind_sv(h.get(), 3, norm);
        if (sqlite3_step(h.get()) == SQLITE_ROW) {
            std::string existing_id(reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 0)));
            throw AliasCollision(std::move(existing_id), norm);
        }
    }

    // ── INSERT OR IGNORE + UPDATE on conflict (existing id refreshes last_seen_at + merges aliases) ──
    const std::string now_iso = iso8601_utc(std::chrono::system_clock::now());

    // First try INSERT OR IGNORE (idempotent on PK)
    {
        sqlite3_stmt* raw_stmt = nullptr;
        const char* sql =
            "INSERT OR IGNORE INTO cognizers ("
            "  id, tenant_id, kind, canonical_name, canonical_name_normalized,"
            "  aliases_json, aliases_normalized_json, external_id,"
            "  trust_priors_json, permissions_json, created_at, last_seen_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, '{}', ?, ?, ?)";
        if (sqlite3_prepare_v2(db, sql, -1, &raw_stmt, nullptr) != SQLITE_OK) {
            throw make_sqlite_error(db, "CognizerHub::register: prepare INSERT");
        }
        StmtHandle h(raw_stmt);
        const std::string aliases_raw_json = json_array_of_strings(aliases_raw);
        const std::string aliases_norm_json = json_array_of_strings(aliases_normalized);
        bind_sv(h.get(), 1, id);
        bind_sv(h.get(), 2, req.tenant_id);
        bind_sv(h.get(), 3, to_string(req.kind));
        bind_sv(h.get(), 4, canonical);
        bind_sv(h.get(), 5, canonical_normalized);
        bind_sv(h.get(), 6, aliases_raw_json);
        bind_sv(h.get(), 7, aliases_norm_json);
        bind_sv(h.get(), 8, req.external_id);
        bind_sv(h.get(), 9, req.permissions_json);
        bind_sv(h.get(), 10, now_iso);
        bind_sv(h.get(), 11, now_iso);
        if (sqlite3_step(h.get()) != SQLITE_DONE) {
            throw make_sqlite_error(db, "CognizerHub::register: INSERT step");
        }
    }

    // Always UPDATE last_seen_at and merge new aliases (idempotent on re-register)
    {
        // Read existing aliases to merge
        std::vector<std::string> existing_raw;
        std::vector<std::string> existing_norm;
        sqlite3_stmt* sel_raw = nullptr;
        const char* sel_sql =
            "SELECT aliases_json, aliases_normalized_json FROM cognizers "
            " WHERE id = ?1 AND tenant_id = ?2";
        if (sqlite3_prepare_v2(db, sel_sql, -1, &sel_raw, nullptr) != SQLITE_OK) {
            throw make_sqlite_error(db, "CognizerHub::register: prepare SELECT existing");
        }
        StmtHandle sel(sel_raw);
        bind_sv(sel.get(), 1, id);
        bind_sv(sel.get(), 2, req.tenant_id);
        if (sqlite3_step(sel.get()) == SQLITE_ROW) {
            existing_raw = parse_string_array(
                reinterpret_cast<const char*>(sqlite3_column_text(sel.get(), 0)));
            existing_norm = parse_string_array(
                reinterpret_cast<const char*>(sqlite3_column_text(sel.get(), 1)));
        }

        // Merge: union of existing + new (preserving raw form for new entries)
        std::vector<std::string> merged_raw = existing_raw;
        std::vector<std::string> merged_norm = existing_norm;
        for (std::size_t i = 0; i < aliases_raw.size(); ++i) {
            if (std::find(merged_norm.begin(), merged_norm.end(), aliases_normalized[i])
                == merged_norm.end()) {
                merged_raw.push_back(aliases_raw[i]);
                merged_norm.push_back(aliases_normalized[i]);
            }
        }

        sqlite3_stmt* upd_raw = nullptr;
        const char* upd_sql =
            "UPDATE cognizers "
            "   SET aliases_json = ?1, aliases_normalized_json = ?2, "
            "       last_seen_at = ?3 "
            " WHERE id = ?4 AND tenant_id = ?5";
        if (sqlite3_prepare_v2(db, upd_sql, -1, &upd_raw, nullptr) != SQLITE_OK) {
            throw make_sqlite_error(db, "CognizerHub::register: prepare UPDATE");
        }
        StmtHandle upd(upd_raw);
        const std::string merged_raw_json = json_array_of_strings(merged_raw);
        const std::string merged_norm_json = json_array_of_strings(merged_norm);
        bind_sv(upd.get(), 1, merged_raw_json);
        bind_sv(upd.get(), 2, merged_norm_json);
        bind_sv(upd.get(), 3, now_iso);
        bind_sv(upd.get(), 4, id);
        bind_sv(upd.get(), 5, req.tenant_id);
        if (sqlite3_step(upd.get()) != SQLITE_DONE) {
            throw make_sqlite_error(db, "CognizerHub::register: UPDATE step");
        }
    }

    // ── Read back to return ──
    auto result = get(id, req.tenant_id);
    if (!result.has_value()) {
        throw std::runtime_error("CognizerHub::register: read-after-insert returned nothing");
    }
    return *result;
}

std::optional<std::string> CognizerHub::lookup_by_alias(
    std::string_view tenant_id, std::string_view query_alias) const {
    const std::string normalized = normalize_alias(query_alias);

    auto& conn = adapter_.connection();
    sqlite3* db = conn.raw();
    sqlite3_stmt* raw_stmt = nullptr;
    const char* sql =
        "SELECT id FROM cognizers "
        " WHERE tenant_id = ?1 "
        "   AND EXISTS ("
        "     SELECT 1 FROM json_each(aliases_normalized_json) j "
        "      WHERE j.value = ?2"
        "   ) LIMIT 1";
    if (sqlite3_prepare_v2(db, sql, -1, &raw_stmt, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(db, "CognizerHub::lookup_by_alias: prepare");
    }
    StmtHandle h(raw_stmt);
    bind_sv(h.get(), 1, tenant_id);
    bind_sv(h.get(), 2, normalized);

    if (sqlite3_step(h.get()) == SQLITE_ROW) {
        return std::string(reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 0)));
    }
    return std::nullopt;
}

std::optional<Cognizer> CognizerHub::get(
    std::string_view id, std::string_view tenant_id) const {
    auto& conn = adapter_.connection();
    sqlite3* db = conn.raw();
    sqlite3_stmt* raw_stmt = nullptr;
    const char* sql =
        "SELECT id, tenant_id, kind, canonical_name, "
        "       aliases_json, external_id, trust_priors_json, "
        "       permissions_json, created_at, last_seen_at "
        "  FROM cognizers WHERE id = ?1 AND tenant_id = ?2";
    if (sqlite3_prepare_v2(db, sql, -1, &raw_stmt, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(db, "CognizerHub::get: prepare");
    }
    StmtHandle h(raw_stmt);
    bind_sv(h.get(), 1, id);
    bind_sv(h.get(), 2, tenant_id);
    const int rc = sqlite3_step(h.get());
    if (rc == SQLITE_DONE) return std::nullopt;
    if (rc != SQLITE_ROW) throw make_sqlite_error(db, "CognizerHub::get: step");

    Cognizer c;
    c.id              = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 0));
    c.tenant_id       = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 1));
    c.kind            = cognizer_kind_from_string(
        reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 2)));
    c.canonical_name  = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 3));
    c.aliases         = parse_string_array(
        reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 4)));
    c.external_id     = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 5));
    // trust_priors_json + permissions_json kept as opaque strings for P2.a
    c.permissions_json = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 7));
    c.created_at      = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 8));
    c.last_seen_at    = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 9));
    return c;
}

void CognizerHub::update_last_seen_at(
    std::string_view id, std::string_view tenant_id,
    std::string_view at_iso8601) {
    auto& conn = adapter_.connection();
    sqlite3* db = conn.raw();
    sqlite3_stmt* raw_stmt = nullptr;
    const char* sql =
        "UPDATE cognizers SET last_seen_at = ?1 "
        " WHERE id = ?2 AND tenant_id = ?3";
    if (sqlite3_prepare_v2(db, sql, -1, &raw_stmt, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(db, "CognizerHub::update_last_seen_at: prepare");
    }
    StmtHandle h(raw_stmt);
    bind_sv(h.get(), 1, at_iso8601);
    bind_sv(h.get(), 2, id);
    bind_sv(h.get(), 3, tenant_id);
    if (sqlite3_step(h.get()) != SQLITE_DONE) {
        throw make_sqlite_error(db, "CognizerHub::update_last_seen_at: step");
    }
    // No-op if no rows affected — Hub is best-effort observer per spec §6.2.
}

// upsert_relation / relations_of implemented in Task 7.
RelationEdge CognizerHub::upsert_relation(const RelationEdgeInput& /*req*/) {
    throw std::runtime_error("CognizerHub::upsert_relation: not implemented (lands in Task 7)");
}

std::vector<RelationEdge> CognizerHub::relations_of(
    std::string_view /*cognizer_id*/, std::string_view /*tenant_id*/) const {
    throw std::runtime_error("CognizerHub::relations_of: not implemented (lands in Task 7)");
}

}  // namespace starling::cognizer

#include "starling/cognizer/cognizer_hub.hpp"

#include "starling/bus/sqlite_helpers.hpp"
#include "starling/cognizer/alias_normalizer.hpp"
#include "starling/cognizer/uuid5.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/version.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <ctime>
#include <random>
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

// ── Relation helpers ────────────────────────────────────────────────────────

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

std::string fiske_weights_to_json(const std::unordered_map<FiskeMode, double>& w) {
    std::ostringstream oss;
    oss << '{';
    bool first = true;
    for (auto m : {FiskeMode::Communal, FiskeMode::Authority,
                    FiskeMode::Equality, FiskeMode::Market}) {
        auto it = w.find(m);
        if (it == w.end()) continue;
        if (!first) oss << ',';
        oss << '"' << to_string(m) << "\":" << it->second;
        first = false;
    }
    oss << '}';
    return oss.str();
}

std::unordered_map<FiskeMode, double> parse_fiske_weights(std::string_view j) {
    std::unordered_map<FiskeMode, double> out;
    for (auto m : {FiskeMode::Communal, FiskeMode::Authority,
                    FiskeMode::Equality, FiskeMode::Market}) {
        const std::string key = std::string("\"") + std::string(to_string(m)) + "\":";
        auto pos = j.find(key);
        if (pos == std::string_view::npos) continue;
        pos += key.size();
        std::size_t end = pos;
        while (end < j.size() && (j[end] != ',' && j[end] != '}')) ++end;
        try {
            out[m] = std::stod(std::string(j.substr(pos, end - pos)));
        } catch (...) {}
    }
    return out;
}

std::string trust_map_to_json(const std::unordered_map<std::string, double>& t) {
    std::ostringstream oss;
    oss << '{';
    bool first = true;
    for (const auto& [k, v] : t) {
        if (!first) oss << ',';
        oss << '"';
        for (char c : k) {
            if (c == '"' || c == '\\') oss << '\\';
            oss << c;
        }
        oss << "\":" << v;
        first = false;
    }
    oss << '}';
    return oss.str();
}

bool fiske_weights_valid(const std::unordered_map<FiskeMode, double>& w) {
    double sum = 0.0;
    for (const auto& [_, v] : w) sum += v;
    return std::abs(sum - 1.0) <= 1e-6;
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

// upsert_relation / relations_of — Task 7.
RelationEdge CognizerHub::upsert_relation(const RelationEdgeInput& req) {
    if (!fiske_weights_valid(req.fiske_weights)) {
        throw FiskeWeightsInvalid();
    }
    if (req.affinity < 0.0 || req.affinity > 1.0) {
        throw std::invalid_argument("RelationEdge.affinity must be in [0,1]");
    }

    auto& conn = adapter_.connection();
    sqlite3* db = conn.raw();
    const std::string now_iso = iso8601_utc(std::chrono::system_clock::now());

    // ── Check for existing edge on (tenant, a, b, valid_from) ──
    std::optional<std::string> existing_id;
    {
        sqlite3_stmt* raw = nullptr;
        const char* sql =
            "SELECT id FROM cognizer_relations "
            " WHERE tenant_id = ?1 AND a_id = ?2 AND b_id = ?3 "
            "   AND ((valid_from IS NULL AND ?4 IS NULL) OR valid_from = ?4)"
            " LIMIT 1";
        if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK) {
            throw make_sqlite_error(db, "upsert_relation: prepare SELECT");
        }
        StmtHandle h(raw);
        bind_sv(h.get(), 1, req.tenant_id);
        bind_sv(h.get(), 2, req.a_id);
        bind_sv(h.get(), 3, req.b_id);
        if (req.valid_from) bind_sv(h.get(), 4, *req.valid_from);
        else                sqlite3_bind_null(h.get(), 4);
        if (sqlite3_step(h.get()) == SQLITE_ROW) {
            existing_id = std::string(reinterpret_cast<const char*>(
                sqlite3_column_text(h.get(), 0)));
        }
    }

    const std::string id = existing_id.value_or(random_hex_32());
    const std::string fiske_json = fiske_weights_to_json(req.fiske_weights);
    const std::string trust_json = trust_map_to_json(req.trust);

    if (existing_id.has_value()) {
        sqlite3_stmt* raw = nullptr;
        const char* sql =
            "UPDATE cognizer_relations "
            "   SET fiske_weights_json = ?1, affinity = ?2, trust_json = ?3, "
            "       power_asymmetry = ?4, interaction_history_ref = ?5, "
            "       valid_to = ?6, updated_at = ?7 "
            " WHERE id = ?8";
        if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK) {
            throw make_sqlite_error(db, "upsert_relation: prepare UPDATE");
        }
        StmtHandle h(raw);
        bind_sv(h.get(), 1, fiske_json);
        sqlite3_bind_double(h.get(), 2, req.affinity);
        bind_sv(h.get(), 3, trust_json);
        sqlite3_bind_double(h.get(), 4, req.power_asymmetry);
        if (req.interaction_history_ref) bind_sv(h.get(), 5, *req.interaction_history_ref);
        else                              sqlite3_bind_null(h.get(), 5);
        if (req.valid_to) bind_sv(h.get(), 6, *req.valid_to);
        else              sqlite3_bind_null(h.get(), 6);
        bind_sv(h.get(), 7, now_iso);
        bind_sv(h.get(), 8, id);
        if (sqlite3_step(h.get()) != SQLITE_DONE) {
            throw make_sqlite_error(db, "upsert_relation: UPDATE step");
        }
    } else {
        sqlite3_stmt* raw = nullptr;
        const char* sql =
            "INSERT INTO cognizer_relations ("
            "  id, tenant_id, a_id, b_id, fiske_weights_json, affinity, "
            "  trust_json, power_asymmetry, interaction_history_ref, "
            "  valid_from, valid_to, created_at, updated_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)";
        if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK) {
            throw make_sqlite_error(db, "upsert_relation: prepare INSERT");
        }
        StmtHandle h(raw);
        bind_sv(h.get(), 1, id);
        bind_sv(h.get(), 2, req.tenant_id);
        bind_sv(h.get(), 3, req.a_id);
        bind_sv(h.get(), 4, req.b_id);
        bind_sv(h.get(), 5, fiske_json);
        sqlite3_bind_double(h.get(), 6, req.affinity);
        bind_sv(h.get(), 7, trust_json);
        sqlite3_bind_double(h.get(), 8, req.power_asymmetry);
        if (req.interaction_history_ref) bind_sv(h.get(), 9, *req.interaction_history_ref);
        else                              sqlite3_bind_null(h.get(), 9);
        if (req.valid_from) bind_sv(h.get(), 10, *req.valid_from);
        else                sqlite3_bind_null(h.get(), 10);
        if (req.valid_to)   bind_sv(h.get(), 11, *req.valid_to);
        else                sqlite3_bind_null(h.get(), 11);
        bind_sv(h.get(), 12, now_iso);
        bind_sv(h.get(), 13, now_iso);
        if (sqlite3_step(h.get()) != SQLITE_DONE) {
            throw make_sqlite_error(db, "upsert_relation: INSERT step");
        }
    }

    RelationEdge edge;
    edge.id = id;
    edge.tenant_id = req.tenant_id;
    edge.a_id = req.a_id;
    edge.b_id = req.b_id;
    edge.fiske_weights = req.fiske_weights;
    edge.affinity = req.affinity;
    edge.trust = req.trust;
    edge.power_asymmetry = req.power_asymmetry;
    edge.interaction_history_ref = req.interaction_history_ref;
    edge.valid_from = req.valid_from;
    edge.valid_to = req.valid_to;
    edge.created_at = now_iso;
    edge.updated_at = now_iso;
    return edge;
}

std::vector<RelationEdge> CognizerHub::relations_of(
    std::string_view cognizer_id, std::string_view tenant_id) const {
    auto& conn = adapter_.connection();
    sqlite3* db = conn.raw();
    sqlite3_stmt* raw = nullptr;
    const char* sql =
        "SELECT id, a_id, b_id, fiske_weights_json, affinity, "
        "       trust_json, power_asymmetry, interaction_history_ref, "
        "       valid_from, valid_to, created_at, updated_at "
        "  FROM cognizer_relations "
        " WHERE tenant_id = ?1 AND a_id = ?2";
    if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(db, "relations_of: prepare");
    }
    StmtHandle h(raw);
    bind_sv(h.get(), 1, tenant_id);
    bind_sv(h.get(), 2, cognizer_id);

    std::vector<RelationEdge> out;
    while (sqlite3_step(h.get()) == SQLITE_ROW) {
        RelationEdge e;
        e.id              = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 0));
        e.tenant_id       = std::string(tenant_id);
        e.a_id            = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 1));
        e.b_id            = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 2));
        e.fiske_weights   = parse_fiske_weights(
            reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 3)));
        e.affinity        = sqlite3_column_double(h.get(), 4);
        // trust_json kept opaque for P2.a (consumers can re-parse if needed)
        e.power_asymmetry = sqlite3_column_double(h.get(), 6);
        if (sqlite3_column_type(h.get(), 7) != SQLITE_NULL) {
            e.interaction_history_ref =
                reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 7));
        }
        if (sqlite3_column_type(h.get(), 8) != SQLITE_NULL) {
            e.valid_from = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 8));
        }
        if (sqlite3_column_type(h.get(), 9) != SQLITE_NULL) {
            e.valid_to = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 9));
        }
        e.created_at = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 10));
        e.updated_at = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 11));
        out.push_back(std::move(e));
    }
    return out;
}

}  // namespace starling::cognizer

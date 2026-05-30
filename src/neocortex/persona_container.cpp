#include "starling/neocortex/persona_container.hpp"

#include "starling/bus/bus_event.hpp"
#include "starling/bus/outbox_writer.hpp"
#include "starling/bus/sqlite_helpers.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <map>
#include <random>
#include <sstream>
#include <string>
#include <vector>

namespace starling::neocortex {

using starling::bus::BusEvent;
using starling::bus::OutboxWriter;
using starling::bus::compute_idempotency_key;
using starling::bus::compute_window_bucket;
using starling::bus::detail::bind_sv;
using starling::bus::detail::make_sqlite_error;
using starling::persistence::StmtHandle;

namespace {

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

// Minimal JSON string escaping.
std::string json_str(std::string_view sv) {
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

// Emit a bus event (no causation parent) for neocortex paths.
void emit_event(
    persistence::Connection& conn,
    std::string_view event_type,
    std::string_view primary_id,
    std::string_view aggregate_id,
    std::string_view tenant_id,
    std::string payload_json)
{
    BusEvent ev;
    ev.tenant_id    = std::string(tenant_id);
    ev.event_type   = std::string(event_type);
    ev.primary_id   = std::string(primary_id);
    ev.aggregate_id = std::string(aggregate_id);
    const std::string window_bucket =
        compute_window_bucket(event_type, std::chrono::system_clock::now());
    ev.idempotency_key = compute_idempotency_key(
        event_type, aggregate_id, primary_id,
        /*causation_root=*/"", window_bucket);
    ev.payload_json = std::move(payload_json);
    OutboxWriter ow(conn);
    ow.append(ev);
}

// Build cache key for per-holder version tracking.
std::string make_cache_key(std::string_view tenant_id, std::string_view holder_id) {
    return std::string(tenant_id) + "\x1f" + std::string(holder_id);
}

}  // namespace

PersonaContainer::PersonaContainer(persistence::SqliteAdapter& adapter)
    : adapter_(adapter) {}

void PersonaContainer::rebuild(
    persistence::Connection& conn,
    std::string_view tenant_id,
    std::string_view holder_id,
    const std::vector<AnchorStatement>& sources,
    std::string_view now_iso)
{
    sqlite3* db = conn.raw();
    const std::string cache_key = make_cache_key(tenant_id, holder_id);

    // ── Step 1: Group by dimension ─────────────────────────────────────────
    struct Candidate {
        std::string value;
        double confidence = 0.0;
    };
    std::map<std::string, std::vector<Candidate>> self_by_dim;
    std::map<std::string, std::vector<Candidate>> profile_by_dim;

    for (const auto& src : sources) {
        Candidate c{src.value, src.confidence};
        if (src.anchor_type == "self_model_anchor") {
            self_by_dim[src.dimension].push_back(c);
        } else {
            profile_by_dim[src.dimension].push_back(c);
        }
    }

    // Gather all dimensions (union of self and profile keys)
    std::vector<std::string> all_dims;
    for (const auto& [dim, _] : self_by_dim)    all_dims.push_back(dim);
    for (const auto& [dim, _] : profile_by_dim) {
        if (self_by_dim.find(dim) == self_by_dim.end())
            all_dims.push_back(dim);
    }
    std::sort(all_dims.begin(), all_dims.end());
    all_dims.erase(std::unique(all_dims.begin(), all_dims.end()), all_dims.end());

    // Arbitrate per dimension
    struct DimResult {
        std::string value;
        double confidence = 0.0;
        bool suspected_diverge = false;
        bool has_value = false;
    };

    std::map<std::string, DimResult> dim_results;

    auto best_candidate = [](const std::vector<Candidate>& cands) -> const Candidate& {
        return *std::max_element(cands.begin(), cands.end(),
            [](const Candidate& a, const Candidate& b) {
                return a.confidence < b.confidence;
            });
    };

    for (const auto& dim : all_dims) {
        auto self_it    = self_by_dim.find(dim);
        auto profile_it = profile_by_dim.find(dim);

        bool has_self    = (self_it    != self_by_dim.end()    && !self_it->second.empty());
        bool has_profile = (profile_it != profile_by_dim.end() && !profile_it->second.empty());

        DimResult res;

        if (has_self && has_profile) {
            const auto& best_self    = best_candidate(self_it->second);
            const auto& best_profile = best_candidate(profile_it->second);

            if (best_self.value != best_profile.value &&
                std::abs(best_self.confidence - best_profile.confidence) >= kDivergeThreshold) {
                res.suspected_diverge = true;
                res.has_value = false;
            } else {
                // Self wins
                res.value = best_self.value;
                res.confidence = best_self.confidence;
                res.has_value = true;
            }
        } else if (has_self) {
            const auto& best = best_candidate(self_it->second);
            res.value = best.value;
            res.confidence = best.confidence;
            res.has_value = true;
        } else if (has_profile) {
            const auto& best = best_candidate(profile_it->second);
            res.value = best.value;
            res.confidence = best.confidence;
            res.has_value = true;
        }

        dim_results[dim] = res;
    }

    // ── Step 2: Build content_json ─────────────────────────────────────────
    std::ostringstream cj;
    cj << "{\"dimensions\":{";
    bool first_dim = true;
    for (const auto& [dim, res] : dim_results) {
        if (!first_dim) cj << ",";
        first_dim = false;
        cj << json_str(dim) << ":{";
        if (res.has_value) {
            cj << "\"value\":" << json_str(res.value)
               << ",\"confidence\":" << res.confidence
               << ",\"suspected_diverge\":false";
        } else {
            cj << "\"value\":null"
               << ",\"confidence\":0"
               << ",\"suspected_diverge\":true";
        }
        cj << "}";
    }
    cj << "}}";
    const std::string content_json = cj.str();

    // ── Step 3: CAS write into containers ─────────────────────────────────

    auto cache_it = version_cache_.find(cache_key);
    const bool known_to_this_instance = (cache_it != version_cache_.end());

    if (!known_to_this_instance) {
        // First time this PersonaContainer instance sees this holder.
        // Check if a row exists already (created by another instance or process).
        std::string existing_id;
        int64_t existing_version = 0;
        {
            const char* sel_sql =
                "SELECT id, version FROM containers "
                "WHERE tenant_id=? AND holder_id=? AND kind='persona' LIMIT 1";
            sqlite3_stmt* raw = nullptr;
            if (sqlite3_prepare_v2(db, sel_sql, -1, &raw, nullptr) != SQLITE_OK)
                throw make_sqlite_error(db, "PersonaContainer::rebuild: prepare SELECT");
            StmtHandle h(raw);
            bind_sv(h.get(), 1, tenant_id);
            bind_sv(h.get(), 2, holder_id);
            if (sqlite3_step(h.get()) == SQLITE_ROW) {
                const auto* txt = sqlite3_column_text(h.get(), 0);
                existing_id = txt ? reinterpret_cast<const char*>(txt) : "";
                existing_version = sqlite3_column_int64(h.get(), 1);
            }
        }

        if (existing_id.empty()) {
            // INSERT new row with version=1
            const std::string new_id = random_hex_32();
            const char* ins_sql =
                "INSERT INTO containers("
                "id, tenant_id, kind, holder_id, scope_descriptor, "
                "content_json, version, created_at, updated_at) "
                "VALUES(?,?,'persona',?,'{}',?,1,?,?)";
            sqlite3_stmt* raw = nullptr;
            if (sqlite3_prepare_v2(db, ins_sql, -1, &raw, nullptr) != SQLITE_OK)
                throw make_sqlite_error(db, "PersonaContainer::rebuild: prepare INSERT");
            StmtHandle h(raw);
            bind_sv(h.get(), 1, new_id);
            bind_sv(h.get(), 2, tenant_id);
            bind_sv(h.get(), 3, holder_id);
            bind_sv(h.get(), 4, content_json);
            bind_sv(h.get(), 5, now_iso);
            bind_sv(h.get(), 6, now_iso);
            if (sqlite3_step(h.get()) != SQLITE_DONE)
                throw make_sqlite_error(db, "PersonaContainer::rebuild: INSERT step");
            // Cache the written version (1)
            version_cache_[cache_key] = 1;
        } else {
            // Row exists from another instance. Use the current DB version as expected.
            // CAS: update WHERE version == existing_version
            const char* upd_sql =
                "UPDATE containers SET content_json=?, version=version+1, updated_at=? "
                "WHERE tenant_id=? AND holder_id=? AND kind='persona' AND version=?";
            sqlite3_stmt* raw = nullptr;
            if (sqlite3_prepare_v2(db, upd_sql, -1, &raw, nullptr) != SQLITE_OK)
                throw make_sqlite_error(db, "PersonaContainer::rebuild: prepare UPDATE (first-seen)");
            StmtHandle h(raw);
            bind_sv(h.get(), 1, content_json);
            bind_sv(h.get(), 2, now_iso);
            bind_sv(h.get(), 3, tenant_id);
            bind_sv(h.get(), 4, holder_id);
            sqlite3_bind_int64(h.get(), 5, existing_version);
            if (sqlite3_step(h.get()) != SQLITE_DONE)
                throw make_sqlite_error(db, "PersonaContainer::rebuild: UPDATE step (first-seen)");
            if (sqlite3_changes(db) == 0)
                throw ConcurrentRebuildError{};
            // Cache the new version
            version_cache_[cache_key] = existing_version + 1;
        }
    } else {
        // This instance has seen this holder before; use cached version as expected.
        const int64_t expected_version = cache_it->second;
        const char* upd_sql =
            "UPDATE containers SET content_json=?, version=version+1, updated_at=? "
            "WHERE tenant_id=? AND holder_id=? AND kind='persona' AND version=?";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db, upd_sql, -1, &raw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(db, "PersonaContainer::rebuild: prepare UPDATE (cached)");
        StmtHandle h(raw);
        bind_sv(h.get(), 1, content_json);
        bind_sv(h.get(), 2, now_iso);
        bind_sv(h.get(), 3, tenant_id);
        bind_sv(h.get(), 4, holder_id);
        sqlite3_bind_int64(h.get(), 5, expected_version);
        if (sqlite3_step(h.get()) != SQLITE_DONE)
            throw make_sqlite_error(db, "PersonaContainer::rebuild: UPDATE step (cached)");
        if (sqlite3_changes(db) == 0)
            throw ConcurrentRebuildError{};
        // Update the cache to the new version
        version_cache_[cache_key] = expected_version + 1;
    }

    // ── Step 4: Emit persona.suspected_diverge for flagged dimensions ──────
    for (const auto& [dim, res] : dim_results) {
        if (res.suspected_diverge) {
            std::string payload = "{\"dimension\":" + json_str(dim) + "}";
            try {
                emit_event(conn, "persona.suspected_diverge",
                           holder_id, holder_id, tenant_id, std::move(payload));
            } catch (...) {
                // idempotency_key collision — skip duplicate
            }
        }
    }
}

}  // namespace starling::neocortex

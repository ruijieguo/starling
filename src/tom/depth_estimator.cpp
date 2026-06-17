#include "starling/tom/depth_estimator.hpp"

#include "starling/persistence/sqlite_handles.hpp"

#include <sqlite3.h>
#include <cstdio>
#include <cstring>
#include <ctime>
#include <iomanip>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>

namespace starling::tom::depth_estimator {

namespace {

// Parse an ISO-8601 UTC string (e.g. "2026-05-26T12:34:56Z") into time_t.
time_t parse_iso8601_utc(std::string_view s) {
    if (s.empty()) {
        throw std::runtime_error("depth_estimator: empty as_of timestamp");
    }
    char buf[32] = {};
    const std::size_t len = (s.size() < sizeof(buf) - 1) ? s.size() : (sizeof(buf) - 2);
    std::memcpy(buf, s.data(), len);

    char* end = buf + std::strlen(buf);
    if (end > buf && *(end - 1) == 'Z') {
        *(end - 1) = '\0';
    } else {
        char* plus = std::strrchr(buf, '+');
        if (plus) *plus = '\0';
    }

    std::tm tm{};
    const char* ret = strptime(buf, "%Y-%m-%dT%H:%M:%S", &tm);
    if (!ret) {
        throw std::runtime_error(
            std::string("depth_estimator: cannot parse timestamp: ") + buf);
    }
    return timegm(&tm);
}

// Format a time_t (UTC) as ISO-8601 "YYYY-MM-DDTHH:MM:SSZ".
std::string format_iso8601_utc(time_t t) {
    std::tm tm{};
    gmtime_r(&t, &tm);
    std::ostringstream oss;
    oss << std::put_time(&tm, "%Y-%m-%dT%H:%M:%SZ");
    return oss.str();
}

// Minimum statements at a given nesting_depth d (for d >= 2) before we credit
// the partner with the corresponding order d+1. Mirrors the legacy top tier:
// historically count>=3 at depth=1 mapped to order 2, so 3 is the bar for
// crediting any deeper demonstrated order.
constexpr int kMinCountForDepth = 3;

// Map the partner's raw nesting_depth=1 statement count to the legacy ToM
// order {0,1,2}. Retained verbatim as the floor for the depth-0/1 tier so
// shallow partners keep their historical outputs byte-for-byte.
int count_to_depth(int count) {
    if (count >= 3) return 2;
    if (count >= 1) return 1;
    return 0;
}

// Fold a partner's per-depth statement histogram (nesting_depth -> count over
// the 7-day window) into the highest order they have demonstrated. A statement
// at nesting_depth=d demonstrates order d+1. The legacy depth-1 mapping is the
// floor; any depth d>=2 with at least kMinCountForDepth statements lifts the
// result to max(result, d+1). No longer saturates at 2.
int histogram_to_order(const std::map<int, int>& depth_counts) {
    int depth1_count = 0;
    if (auto it = depth_counts.find(1); it != depth_counts.end()) {
        depth1_count = it->second;
    }
    int order = count_to_depth(depth1_count);  // legacy {0,1,2} floor
    for (const auto& [depth, count] : depth_counts) {
        if (depth >= 2 && count >= kMinCountForDepth) {
            const int demonstrated_order = depth + 1;
            if (demonstrated_order > order) order = demonstrated_order;
        }
    }
    return order;
}

}  // namespace

int estimate(
        persistence::Connection& conn,
        std::string_view partner_cognizer_id,
        std::string_view tenant_id,
        std::string_view as_of_iso8601) {

    const time_t as_of_t = parse_iso8601_utc(as_of_iso8601);
    sqlite3* db = conn.raw();

    // --- Cache lookup ---
    {
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db,
            "SELECT nesting_depth_1_count_7d, last_recomputed_at"
            " FROM tom_depth_estimator_cache"
            " WHERE tenant_id = ? AND partner_id = ?",
            -1, &raw, nullptr) != SQLITE_OK) {
            throw std::runtime_error(
                std::string("depth_estimator: prepare cache select failed: ")
                + sqlite3_errmsg(db));
        }
        persistence::StmtHandle h(raw);

        sqlite3_bind_text(h.get(), 1, tenant_id.data(),
                          static_cast<int>(tenant_id.size()), SQLITE_TRANSIENT);
        sqlite3_bind_text(h.get(), 2, partner_cognizer_id.data(),
                          static_cast<int>(partner_cognizer_id.size()), SQLITE_TRANSIENT);

        const int rc = sqlite3_step(h.get());
        if (rc == SQLITE_ROW) {
            // The cache column stores the computed demonstrated order (the
            // estimate() return value), already folded across nesting depths.
            const int cached_order = sqlite3_column_int(h.get(), 0);
            const char* recomputed_str =
                reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 1));
            if (recomputed_str) {
                const time_t recomputed_t =
                    parse_iso8601_utc(std::string_view(recomputed_str));
                // Cache hit: last_recomputed_at + 1h > as_of_t
                if (recomputed_t + 3600 > as_of_t) {
                    return cached_order;
                }
            }
        } else if (rc != SQLITE_DONE) {
            throw std::runtime_error(
                std::string("depth_estimator: step cache select failed: ")
                + sqlite3_errmsg(db));
        }
    }

    // --- Cache miss or expired: recompute ---
    const time_t window_start_t = as_of_t - (7 * 24 * 3600);
    const std::string window_start_str = format_iso8601_utc(window_start_t);
    const std::string as_of_str(as_of_iso8601);

    // Read the partner's qualifying statements grouped by nesting_depth over
    // the 7-day window. Folding the histogram (rather than counting a single
    // depth) lets estimate() reflect the deepest order the partner demonstrated.
    std::map<int, int> depth_counts;
    {
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db,
            "SELECT nesting_depth, COUNT(*) FROM statements"
            " WHERE tenant_id  = ?"
            "   AND holder_id  = ?"
            "   AND observed_at   >= ?"
            "   AND observed_at   <= ?"
            "   AND consolidation_state IN ('consolidated', 'archived')"
            " GROUP BY nesting_depth",
            -1, &raw, nullptr) != SQLITE_OK) {
            throw std::runtime_error(
                std::string("depth_estimator: prepare count failed: ")
                + sqlite3_errmsg(db));
        }
        persistence::StmtHandle h(raw);

        sqlite3_bind_text(h.get(), 1, tenant_id.data(),
                          static_cast<int>(tenant_id.size()), SQLITE_TRANSIENT);
        sqlite3_bind_text(h.get(), 2, partner_cognizer_id.data(),
                          static_cast<int>(partner_cognizer_id.size()), SQLITE_TRANSIENT);
        sqlite3_bind_text(h.get(), 3, window_start_str.c_str(), -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(h.get(), 4, as_of_str.c_str(), -1, SQLITE_TRANSIENT);

        int rc = sqlite3_step(h.get());
        while (rc == SQLITE_ROW) {
            const int depth = sqlite3_column_int(h.get(), 0);
            const int rows  = sqlite3_column_int(h.get(), 1);
            depth_counts[depth] = rows;
            rc = sqlite3_step(h.get());
        }
        if (rc != SQLITE_DONE) {
            throw std::runtime_error(
                std::string("depth_estimator: step count failed: ")
                + sqlite3_errmsg(db));
        }
    }

    const int demonstrated_order = histogram_to_order(depth_counts);

    // --- UPSERT cache row ---
    {
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db,
            "INSERT OR REPLACE INTO tom_depth_estimator_cache"
            "  (tenant_id, partner_id, nesting_depth_1_count_7d, last_recomputed_at)"
            " VALUES (?, ?, ?, ?)",
            -1, &raw, nullptr) != SQLITE_OK) {
            throw std::runtime_error(
                std::string("depth_estimator: prepare upsert failed: ")
                + sqlite3_errmsg(db));
        }
        persistence::StmtHandle h(raw);

        sqlite3_bind_text(h.get(), 1, tenant_id.data(),
                          static_cast<int>(tenant_id.size()), SQLITE_TRANSIENT);
        sqlite3_bind_text(h.get(), 2, partner_cognizer_id.data(),
                          static_cast<int>(partner_cognizer_id.size()), SQLITE_TRANSIENT);
        // Persist the folded order; the cache column now holds the estimate()
        // result directly (read back verbatim on a cache hit).
        sqlite3_bind_int(h.get(), 3, demonstrated_order);
        sqlite3_bind_text(h.get(), 4, as_of_str.c_str(), -1, SQLITE_TRANSIENT);

        if (sqlite3_step(h.get()) != SQLITE_DONE) {
            throw std::runtime_error(
                std::string("depth_estimator: step upsert failed: ")
                + sqlite3_errmsg(db));
        }
    }

    return demonstrated_order;
}

}  // namespace starling::tom::depth_estimator

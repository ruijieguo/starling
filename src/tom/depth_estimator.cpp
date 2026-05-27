#include "starling/tom/depth_estimator.hpp"

#include "starling/persistence/sqlite_handles.hpp"

#include <sqlite3.h>
#include <cstdio>
#include <cstring>
#include <ctime>
#include <iomanip>
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

// Map raw statement count to ToM depth level.
int count_to_depth(int count) {
    if (count >= 3) return 2;
    if (count >= 1) return 1;
    return 0;
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
            const int cached_count = sqlite3_column_int(h.get(), 0);
            const char* recomputed_str =
                reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 1));
            if (recomputed_str) {
                const time_t recomputed_t =
                    parse_iso8601_utc(std::string_view(recomputed_str));
                // Cache hit: last_recomputed_at + 1h > as_of_t
                if (recomputed_t + 3600 > as_of_t) {
                    return count_to_depth(cached_count);
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

    int count = 0;
    {
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db,
            "SELECT COUNT(*) FROM statements"
            " WHERE tenant_id  = ?"
            "   AND holder_id  = ?"
            "   AND nesting_depth = 1"
            "   AND observed_at   >= ?"
            "   AND observed_at   <= ?"
            "   AND consolidation_state IN ('consolidated', 'archived')",
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

        const int rc = sqlite3_step(h.get());
        if (rc == SQLITE_ROW) {
            count = sqlite3_column_int(h.get(), 0);
        } else {
            throw std::runtime_error(
                std::string("depth_estimator: step count failed: ")
                + sqlite3_errmsg(db));
        }
    }

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
        sqlite3_bind_int(h.get(), 3, count);
        sqlite3_bind_text(h.get(), 4, as_of_str.c_str(), -1, SQLITE_TRANSIENT);

        if (sqlite3_step(h.get()) != SQLITE_DONE) {
            throw std::runtime_error(
                std::string("depth_estimator: step upsert failed: ")
                + sqlite3_errmsg(db));
        }
    }

    return count_to_depth(count);
}

}  // namespace starling::tom::depth_estimator

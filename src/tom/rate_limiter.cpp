#include "starling/tom/rate_limiter.hpp"

#include "starling/persistence/sqlite_handles.hpp"

#include <sqlite3.h>
#include <cstdio>
#include <cstring>
#include <ctime>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <string>

namespace starling::tom::rate_limiter {

namespace {

// Parse an ISO-8601 UTC string (e.g. "2026-05-26T12:34:56Z") into time_t.
// Only handles the "Z" (UTC) suffix variant that the rest of the codebase emits.
time_t parse_iso8601_utc(std::string_view s) {
    if (s.empty()) {
        throw std::runtime_error("rate_limiter: empty as_of timestamp");
    }
    // Accept either trailing 'Z' or '+00:00'.
    // Copy into a null-terminated buffer for strptime.
    char buf[32] = {};
    const std::size_t len = (s.size() < sizeof(buf) - 1) ? s.size() : (sizeof(buf) - 2);
    std::memcpy(buf, s.data(), len);

    // Strip trailing 'Z' or '+00:00' before parsing.
    // strptime format "%Y-%m-%dT%H:%M:%S" handles the core part.
    char* end = buf + std::strlen(buf);
    if (end > buf && *(end - 1) == 'Z') {
        *(end - 1) = '\0';
    } else {
        // Strip '+00:00' if present
        char* plus = std::strrchr(buf, '+');
        if (plus) *plus = '\0';
    }

    std::tm tm{};
    const char* ret = strptime(buf, "%Y-%m-%dT%H:%M:%S", &tm);
    if (!ret) {
        throw std::runtime_error(
            std::string("rate_limiter: cannot parse timestamp: ") + buf);
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

}  // namespace

bool allow_tom_inferred_write(
        persistence::Connection& conn,
        std::string_view tenant_id,
        std::string_view holder_id,
        std::string_view subject_id,
        std::string_view predicate,
        std::string_view canonical_object_hash,
        std::string_view as_of_iso8601) {

    const time_t as_of_t    = parse_iso8601_utc(as_of_iso8601);
    const time_t window_start = as_of_t - 600;

    const std::string window_start_str = format_iso8601_utc(window_start);
    const std::string as_of_str(as_of_iso8601);

    sqlite3* db = conn.raw();
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db,
        "SELECT 1 FROM statements"
        " WHERE tenant_id            = ?"
        "   AND holder_id            = ?"
        "   AND subject_id           = ?"
        "   AND predicate            = ?"
        "   AND canonical_object_hash = ?"
        "   AND provenance           = 'tom_inferred'"
        "   AND observed_at          >= ?"
        "   AND observed_at          <= ?"
        " LIMIT 1",
        -1, &raw, nullptr) != SQLITE_OK) {
        throw std::runtime_error(
            std::string("rate_limiter: prepare failed: ") + sqlite3_errmsg(db));
    }
    persistence::StmtHandle h(raw);

    auto bind_sv = [&](int idx, std::string_view v) {
        sqlite3_bind_text(h.get(), idx, v.data(),
                          static_cast<int>(v.size()), SQLITE_TRANSIENT);
    };

    bind_sv(1, tenant_id);
    bind_sv(2, holder_id);
    bind_sv(3, subject_id);
    bind_sv(4, predicate);
    bind_sv(5, canonical_object_hash);
    bind_sv(6, window_start_str);
    bind_sv(7, as_of_str);

    const int rc = sqlite3_step(h.get());
    if (rc == SQLITE_DONE) {
        return true;   // No matching row — write is allowed.
    }
    if (rc == SQLITE_ROW) {
        return false;  // Duplicate within window — reject.
    }
    throw std::runtime_error(
        std::string("rate_limiter: step failed: ") + sqlite3_errmsg(db));
}

}  // namespace starling::tom::rate_limiter

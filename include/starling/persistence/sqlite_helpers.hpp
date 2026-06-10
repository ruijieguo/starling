#pragma once
#include "starling/persistence/connection.hpp"

#include <chrono>
#include <ctime>
#include <iomanip>
#include <sqlite3.h>
#include <sstream>
#include <string>
#include <string_view>

namespace starling::persistence::detail {

// Build a SqliteError tagged with the connection's last extended error code
// + a context-specific prefix. Use after a sqlite3_prepare_v2 returns non-OK
// or a sqlite3_step returns an unexpected code.
[[nodiscard]] inline starling::persistence::SqliteError make_sqlite_error(
    sqlite3* db, const char* what)
{
    return starling::persistence::SqliteError(
        std::string(what) + ": " + sqlite3_errmsg(db),
        sqlite3_extended_errcode(db));
}

// Bind a std::string_view as TEXT with explicit length. SQLITE_TRANSIENT
// causes SQLite to copy the bytes during the call, so the view's storage
// only needs to outlive the bind itself. Using .data()+.size() avoids
// allocating a temporary std::string and is null-safe.
inline void bind_sv(sqlite3_stmt* s, int idx, std::string_view v) {
    sqlite3_bind_text(s, idx, v.data(), static_cast<int>(v.size()), SQLITE_TRANSIENT);
}

// ISO-8601 UTC string with second precision. Whole-second precision is
// intentional — outbox_sequence is the authoritative ordering key; created_at
// and inbox timestamps are for human inspection and TTL math, not ordering.
inline std::string iso8601_utc(std::chrono::system_clock::time_point t) {
    const std::time_t secs = std::chrono::system_clock::to_time_t(t);
    std::tm tm{};
    gmtime_r(&secs, &tm);
    std::ostringstream oss;
    oss << std::put_time(&tm, "%Y-%m-%dT%H:%M:%SZ");
    return oss.str();
}

}  // namespace starling::persistence::detail

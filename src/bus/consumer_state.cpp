#include "starling/bus/consumer_state.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <chrono>
#include <ctime>
#include <iomanip>
#include <sstream>
#include <string>
#include <string_view>

namespace starling::bus {

namespace {

// Helper: build a SqliteError from the connection's last extended error code
// + a context-specific prefix. Mirrors the pattern from outbox_writer.cpp; not
// extracted into a shared header in this task to keep the change scoped.
[[nodiscard]] starling::persistence::SqliteError make_sqlite_error(
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
void bind_sv(sqlite3_stmt* s, int idx, std::string_view v) {
    sqlite3_bind_text(s, idx, v.data(), static_cast<int>(v.size()), SQLITE_TRANSIENT);
}

std::string iso8601_utc(std::chrono::system_clock::time_point t) {
    const auto secs = std::chrono::system_clock::to_time_t(t);
    std::tm tm{};
    gmtime_r(&secs, &tm);
    std::ostringstream oss;
    oss << std::put_time(&tm, "%Y-%m-%dT%H:%M:%SZ");
    return oss.str();
}

}  // namespace

int64_t ConsumerCheckpoint::last_delivered(std::string_view consumer_id) {
    sqlite3* const db = conn_.raw();
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db,
            "SELECT last_delivered_sequence FROM consumer_checkpoint WHERE consumer_id=?",
            -1, &raw, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(db, "ConsumerCheckpoint::last_delivered: prepare failed");
    }
    starling::persistence::StmtHandle h(raw);
    bind_sv(h.get(), 1, consumer_id);
    const int rc = sqlite3_step(h.get());
    if (rc == SQLITE_ROW) return sqlite3_column_int64(h.get(), 0);
    if (rc == SQLITE_DONE) return 0;
    throw make_sqlite_error(db, "ConsumerCheckpoint::last_delivered: step failed");
}

void ConsumerCheckpoint::advance(std::string_view consumer_id, int64_t sequence) {
    sqlite3* const db = conn_.raw();
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db,
            "INSERT INTO consumer_checkpoint(consumer_id,last_delivered_sequence,updated_at) "
            "VALUES(?,?,?) "
            "ON CONFLICT(consumer_id) DO UPDATE SET "
            "  last_delivered_sequence=MAX(consumer_checkpoint.last_delivered_sequence, excluded.last_delivered_sequence),"
            "  updated_at=excluded.updated_at",
            -1, &raw, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(db, "ConsumerCheckpoint::advance: prepare failed");
    }
    starling::persistence::StmtHandle h(raw);
    const std::string ts = iso8601_utc(std::chrono::system_clock::now());
    bind_sv(h.get(), 1, consumer_id);
    sqlite3_bind_int64(h.get(), 2, sequence);
    bind_sv(h.get(), 3, ts);
    if (sqlite3_step(h.get()) != SQLITE_DONE) {
        throw make_sqlite_error(db, "ConsumerCheckpoint::advance: step failed");
    }
}

bool IdempotencyInbox::record_if_new(
        std::string_view consumer_id,
        std::string_view idempotency_key,
        std::chrono::system_clock::time_point now,
        std::chrono::seconds ttl) {
    sqlite3* const db = conn_.raw();
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db,
            "INSERT OR IGNORE INTO idempotency_inbox("
            "consumer_id,idempotency_key,received_at,expires_at) VALUES(?,?,?,?)",
            -1, &raw, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(db, "IdempotencyInbox::record_if_new: prepare failed");
    }
    starling::persistence::StmtHandle h(raw);
    const std::string received = iso8601_utc(now);
    const std::string expires  = iso8601_utc(now + ttl);
    bind_sv(h.get(), 1, consumer_id);
    bind_sv(h.get(), 2, idempotency_key);
    bind_sv(h.get(), 3, received);
    bind_sv(h.get(), 4, expires);
    if (sqlite3_step(h.get()) != SQLITE_DONE) {
        throw make_sqlite_error(db, "IdempotencyInbox::record_if_new: step failed");
    }
    return sqlite3_changes(db) > 0;
}

int64_t IdempotencyInbox::purge_expired(std::chrono::system_clock::time_point now) {
    sqlite3* const db = conn_.raw();
    const std::string nowstr = iso8601_utc(now);
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db,
            "DELETE FROM idempotency_inbox WHERE expires_at < ?",
            -1, &raw, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(db, "IdempotencyInbox::purge_expired: prepare failed");
    }
    starling::persistence::StmtHandle h(raw);
    bind_sv(h.get(), 1, nowstr);
    if (sqlite3_step(h.get()) != SQLITE_DONE) {
        throw make_sqlite_error(db, "IdempotencyInbox::purge_expired: step failed");
    }
    return sqlite3_changes(db);
}

}  // namespace starling::bus

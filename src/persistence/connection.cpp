#include "starling/persistence/connection.hpp"

namespace starling::persistence {

Connection Connection::open(const std::filesystem::path& db_path) {
    if (db_path != ":memory:" && db_path.has_parent_path()) {
        std::filesystem::create_directories(db_path.parent_path());
    }
    sqlite3* raw = nullptr;
    const int rc = sqlite3_open_v2(
        db_path.string().c_str(), &raw,
        SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE | SQLITE_OPEN_FULLMUTEX,
        nullptr);
    SqliteHandle h(raw);
    if (rc != SQLITE_OK) {
        throw SqliteError(std::string("sqlite3_open_v2 failed: ") +
            (raw ? sqlite3_errmsg(raw) : "alloc failure"), rc);
    }
    Connection c(std::move(h));
    c.exec("PRAGMA foreign_keys = ON");
    c.exec("PRAGMA journal_mode = WAL");
    c.exec("PRAGMA synchronous = NORMAL");
    c.exec("PRAGMA busy_timeout = 5000");
    return c;
}

void Connection::exec(std::string_view sql) {
    char* err = nullptr;
    if (sqlite3_exec(handle_.get(), std::string(sql).c_str(),
                     nullptr, nullptr, &err) != SQLITE_OK) {
        std::string msg = err ? err : "unknown sqlite_exec error";
        sqlite3_free(err);
        throw SqliteError("exec failed: " + msg, sqlite3_errcode(handle_.get()));
    }
}

void Connection::begin_immediate() { exec("BEGIN IMMEDIATE"); }
void Connection::commit()          { exec("COMMIT"); }
void Connection::rollback() noexcept {
    sqlite3_exec(handle_.get(), "ROLLBACK", nullptr, nullptr, nullptr);
}

int64_t Connection::last_insert_rowid() const noexcept {
    return sqlite3_last_insert_rowid(handle_.get());
}

}  // namespace starling::persistence

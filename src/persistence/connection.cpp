#include "starling/persistence/connection.hpp"

#include <atomic>

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

TransactionGuard::TransactionGuard(Connection& c) : conn_(c) {
    if (sqlite3_get_autocommit(conn_.raw()) != 0) {
        outer_ = true;
        conn_.begin_immediate();
        return;
    }
    static std::atomic<unsigned long long> sequence{0};
    savepoint_ = "starling_tx_" + std::to_string(++sequence);
    conn_.exec("SAVEPOINT " + savepoint_);
}

TransactionGuard::~TransactionGuard() {
    if (!active_) return;
    if (outer_) {
        conn_.rollback();
        return;
    }
    sqlite3_exec(conn_.raw(), ("ROLLBACK TO SAVEPOINT " + savepoint_).c_str(),
                 nullptr, nullptr, nullptr);
    sqlite3_exec(conn_.raw(), ("RELEASE SAVEPOINT " + savepoint_).c_str(),
                 nullptr, nullptr, nullptr);
}

void TransactionGuard::commit() {
    if (outer_) conn_.commit();
    else conn_.exec("RELEASE SAVEPOINT " + savepoint_);
    active_ = false;
}

}  // namespace starling::persistence

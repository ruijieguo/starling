#pragma once
#include "starling/persistence/sqlite_handles.hpp"
#include <filesystem>
#include <stdexcept>
#include <string>
#include <string_view>

namespace starling::persistence {

class SqliteError : public std::runtime_error {
public:
    SqliteError(std::string msg, int code) : runtime_error(std::move(msg)), code_(code) {}
    int code() const noexcept { return code_; }
private:
    int code_;
};

class Connection {
public:
    // Opens db_path with WAL + foreign_keys=ON + busy_timeout=5000 + synchronous=NORMAL.
    // Use ":memory:" for tests. Creates parent directories as needed when the
    // path is a real file.
    static Connection open(const std::filesystem::path& db_path);

    sqlite3* raw() noexcept { return handle_.get(); }

    // Executes SQL with no parameters. Throws SqliteError on failure.
    void exec(std::string_view sql);

    // BEGIN IMMEDIATE / COMMIT / ROLLBACK helpers. Nesting is not supported by
    // SQLite's default transaction model and not supported here either.
    void begin_immediate();
    void commit();
    void rollback() noexcept;

    int64_t last_insert_rowid() const noexcept;

private:
    explicit Connection(SqliteHandle h) : handle_(std::move(h)) {}
    SqliteHandle handle_;
};

class TransactionGuard {
public:
    explicit TransactionGuard(Connection& c) : conn_(c), active_(true) { conn_.begin_immediate(); }
    ~TransactionGuard() { if (active_) conn_.rollback(); }
    void commit() { conn_.commit(); active_ = false; }

    TransactionGuard(const TransactionGuard&) = delete;
    TransactionGuard& operator=(const TransactionGuard&) = delete;
    TransactionGuard(TransactionGuard&&) = delete;
    TransactionGuard& operator=(TransactionGuard&&) = delete;

private:
    Connection& conn_;
    bool active_;
};

}  // namespace starling::persistence

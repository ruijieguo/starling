#pragma once
// Lightweight prepared-statement wrapper around sqlite3_stmt.
//
// 约定：新代码一律用 Stmt（prepare-or-throw + 变参 bind + step_row/step_done），
// 不要再手写 sqlite3_prepare_v2/sqlite3_bind_* 样板。存量 ~203 处裸 prepare
// 样板**不回迁**——正确性已被既有测试覆盖，机械改写只会引入风险。
//
// Usage:
//     Stmt s(conn.raw(), "INSERT INTO t(a, b) VALUES (?1, ?2)");
//     s.bind("hello", std::int64_t{42});
//     s.step_done();
//
//     Stmt q(conn.raw(), "SELECT a FROM t WHERE b = ?1");
//     q.bind(std::int64_t{42});
//     while (q.step_row()) { ... sqlite3_column_*(q.raw(), 0) ... }

#include "starling/persistence/sqlite_handles.hpp"
#include "starling/persistence/sqlite_helpers.hpp"

#include <cstddef>
#include <cstdint>
#include <sqlite3.h>
#include <string>
#include <string_view>
#include <utility>

namespace starling::persistence {

class Stmt {
public:
    // Prepares `sql` against `db`; throws SqliteError (via
    // detail::make_sqlite_error, which appends sqlite3_errmsg context) on
    // failure.
    Stmt(sqlite3* db, const char* sql) : db_(db) {
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK) {
            throw detail::make_sqlite_error(db, "Stmt: prepare failed");
        }
        stmt_.reset(raw);
    }

    ~Stmt() = default;
    Stmt(const Stmt&) = delete;
    Stmt& operator=(const Stmt&) = delete;
    Stmt(Stmt&&) = default;
    Stmt& operator=(Stmt&&) = default;

    // Binds arguments at positions 1..N (in call order). Supported types:
    // std::string_view / std::string / const char* (TEXT, transient copy),
    // std::int64_t / int (INTEGER), double (REAL), std::nullptr_t (NULL).
    template <typename... Args>
    void bind(Args&&... args) {
        int idx = 0;
        (bind_one(++idx, std::forward<Args>(args)), ...);
    }

    // Steps once. Returns true on SQLITE_ROW, false on SQLITE_DONE; any other
    // result code throws SqliteError with errmsg context.
    bool step_row() {
        const int rc = sqlite3_step(stmt_.get());
        if (rc == SQLITE_ROW) return true;
        if (rc == SQLITE_DONE) return false;
        throw detail::make_sqlite_error(db_, "Stmt: step failed");
    }

    // Steps once and requires SQLITE_DONE (writes / DDL). Anything else —
    // including an unexpected SQLITE_ROW — throws SqliteError.
    void step_done() {
        const int rc = sqlite3_step(stmt_.get());
        if (rc != SQLITE_DONE) {
            throw detail::make_sqlite_error(db_, "Stmt: expected SQLITE_DONE");
        }
    }

    // Raw handle for sqlite3_column_* reads (and anything else not wrapped).
    [[nodiscard]] sqlite3_stmt* raw() noexcept { return stmt_.get(); }

private:
    void bind_one(int idx, std::string_view v) { detail::bind_sv(stmt_.get(), idx, v); }
    void bind_one(int idx, const std::string& v) { detail::bind_sv(stmt_.get(), idx, v); }
    void bind_one(int idx, const char* v) { detail::bind_sv(stmt_.get(), idx, v); }
    void bind_one(int idx, std::int64_t v) { sqlite3_bind_int64(stmt_.get(), idx, v); }
    void bind_one(int idx, int v) { sqlite3_bind_int(stmt_.get(), idx, v); }
    void bind_one(int idx, double v) { sqlite3_bind_double(stmt_.get(), idx, v); }
    void bind_one(int idx, std::nullptr_t) { sqlite3_bind_null(stmt_.get(), idx); }

    sqlite3* db_ = nullptr;  // not owned; for error context only
    StmtHandle stmt_;
};

}  // namespace starling::persistence

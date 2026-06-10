// Tests for starling::persistence::Stmt — the lightweight prepared-statement
// wrapper (prepare-or-throw, variadic bind, step_row/step_done, raw access).

#include "starling/persistence/connection.hpp"
#include "starling/persistence/stmt.hpp"

#include <gtest/gtest.h>

#include <cstdint>
#include <memory>
#include <string>
#include <string_view>

namespace {

using starling::persistence::Connection;
using starling::persistence::SqliteError;
using starling::persistence::Stmt;

class PersistenceStmtTest : public ::testing::Test {
protected:
    void SetUp() override {
        conn_ = std::make_unique<Connection>(Connection::open(":memory:"));
        conn_->exec(
            "CREATE TABLE t ("
            "  id INTEGER PRIMARY KEY,"
            "  txt TEXT,"
            "  n INTEGER,"
            "  small INTEGER,"
            "  d REAL,"
            "  maybe TEXT"
            ")");
    }

    std::unique_ptr<Connection> conn_;
};

TEST_F(PersistenceStmtTest, InsertBindsAllSupportedTypesAndStepDone) {
    Stmt ins(conn_->raw(),
             "INSERT INTO t (txt, n, small, d, maybe) "
             "VALUES (?1, ?2, ?3, ?4, ?5)");
    // string_view + int64 + int + double + nullptr in one variadic bind.
    ins.bind(std::string_view{"hello"}, std::int64_t{1234567890123}, 7, 2.5,
             nullptr);
    ins.step_done();

    Stmt ins2(conn_->raw(),
              "INSERT INTO t (txt, n, small, d, maybe) "
              "VALUES (?1, ?2, ?3, ?4, ?5)");
    // std::string + const char* TEXT paths on the second row.
    ins2.bind(std::string{"world"}, std::int64_t{-1}, -7, -0.5, "present");
    ins2.step_done();

    EXPECT_EQ(conn_->last_insert_rowid(), 2);
}

TEST_F(PersistenceStmtTest, SelectStepRowReadsBackBoundValues) {
    {
        Stmt ins(conn_->raw(),
                 "INSERT INTO t (txt, n, small, d, maybe) "
                 "VALUES (?1, ?2, ?3, ?4, ?5)");
        ins.bind(std::string_view{"hello"}, std::int64_t{1234567890123}, 7,
                 2.5, nullptr);
        ins.step_done();
    }

    Stmt sel(conn_->raw(),
             "SELECT txt, n, small, d, maybe FROM t WHERE txt = ?1");
    sel.bind("hello");

    ASSERT_TRUE(sel.step_row());
    EXPECT_STREQ(reinterpret_cast<const char*>(sqlite3_column_text(sel.raw(), 0)),
                 "hello");
    EXPECT_EQ(sqlite3_column_int64(sel.raw(), 1), 1234567890123);
    EXPECT_EQ(sqlite3_column_int(sel.raw(), 2), 7);
    EXPECT_DOUBLE_EQ(sqlite3_column_double(sel.raw(), 3), 2.5);
    EXPECT_EQ(sqlite3_column_type(sel.raw(), 4), SQLITE_NULL);

    // Single matching row -> next step is DONE (returns false, no throw).
    EXPECT_FALSE(sel.step_row());
}

TEST_F(PersistenceStmtTest, BadSqlConstructorThrowsWithContext) {
    try {
        Stmt bad(conn_->raw(), "SELEKT nonsense FROM nowhere");
        FAIL() << "expected SqliteError from bad SQL";
    } catch (const SqliteError& e) {
        // make_sqlite_error prefixes our context and appends sqlite3_errmsg.
        const std::string msg = e.what();
        EXPECT_NE(msg.find("Stmt: prepare failed"), std::string::npos) << msg;
        EXPECT_NE(msg.find(":"), std::string::npos) << msg;
    }
}

TEST_F(PersistenceStmtTest, StepDoneOnRowReturningQueryThrows) {
    {
        Stmt ins(conn_->raw(), "INSERT INTO t (txt) VALUES (?1)");
        ins.bind("row");
        ins.step_done();
    }
    Stmt sel(conn_->raw(), "SELECT txt FROM t");
    EXPECT_THROW(sel.step_done(), SqliteError);
}

}  // namespace

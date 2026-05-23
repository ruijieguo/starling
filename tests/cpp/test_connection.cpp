#include <gtest/gtest.h>
#include "starling/persistence/connection.hpp"

using starling::persistence::Connection;
using starling::persistence::SqliteError;
using starling::persistence::TransactionGuard;

TEST(Connection, OpensInMemoryWithPragmas) {
    auto c = Connection::open(":memory:");
    ASSERT_NE(c.raw(), nullptr);
    c.exec("CREATE TABLE t(x INTEGER PRIMARY KEY)");
    c.exec("INSERT INTO t(x) VALUES(1)");
}

TEST(Connection, RollbackOnGuardDestruction) {
    auto c = Connection::open(":memory:");
    c.exec("CREATE TABLE t(x INTEGER)");
    {
        TransactionGuard g(c);
        c.exec("INSERT INTO t(x) VALUES(1)");
        // no commit -> rollback in dtor
    }
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(c.raw(), "SELECT COUNT(*) FROM t", -1, &s, nullptr);
    ASSERT_EQ(sqlite3_step(s), SQLITE_ROW);
    EXPECT_EQ(sqlite3_column_int(s, 0), 0);
    sqlite3_finalize(s);
}

TEST(Connection, CommitInsideGuardPersists) {
    auto c = Connection::open(":memory:");
    c.exec("CREATE TABLE t(x INTEGER)");
    {
        TransactionGuard g(c);
        c.exec("INSERT INTO t(x) VALUES(42)");
        g.commit();
    }
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(c.raw(), "SELECT x FROM t", -1, &s, nullptr);
    ASSERT_EQ(sqlite3_step(s), SQLITE_ROW);
    EXPECT_EQ(sqlite3_column_int(s, 0), 42);
    sqlite3_finalize(s);
}

TEST(Connection, ExecThrowsOnSyntaxError) {
    auto c = Connection::open(":memory:");
    EXPECT_THROW(c.exec("THIS IS NOT SQL"), SqliteError);
}

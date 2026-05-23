#include <gtest/gtest.h>
#include <sqlite3.h>

#include <string>

TEST(SqliteLink, OpenInMemoryAndQueryVersion) {
    sqlite3* db = nullptr;
    ASSERT_EQ(sqlite3_open(":memory:", &db), SQLITE_OK);
    ASSERT_NE(db, nullptr);

    sqlite3_stmt* stmt = nullptr;
    ASSERT_EQ(sqlite3_prepare_v2(db, "SELECT sqlite_version()", -1, &stmt, nullptr),
              SQLITE_OK);
    ASSERT_EQ(sqlite3_step(stmt), SQLITE_ROW);

    const std::string version = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 0));
    EXPECT_FALSE(version.empty());
    EXPECT_GE(version.size(), 5u);  // "X.Y.Z" minimum

    sqlite3_finalize(stmt);
    sqlite3_close(db);
}

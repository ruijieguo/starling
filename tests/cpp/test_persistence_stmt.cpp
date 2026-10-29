// Tests for starling::persistence::Stmt — the lightweight prepared-statement
// wrapper (prepare-or-throw, variadic bind, step_row/step_done, raw access).

#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/stmt.hpp"

#include <gtest/gtest.h>
#include <unistd.h>

#include <atomic>
#include <cstdint>
#include <filesystem>
#include <memory>
#include <stdexcept>
#include <string>
#include <string_view>

namespace {

using starling::persistence::Connection;
using starling::persistence::SqliteAdapter;
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

// ── SqliteAdapter::close / Connection::close ────────────────────────────────

namespace {

namespace fs = std::filesystem;

// 每个用例一个独立的临时目录,析构时删除。
class CloseDir {
public:
    CloseDir() {
        static std::atomic<int> seq{0};
        path_ = fs::temp_directory_path() /
                ("starling-close-" + std::to_string(::getpid()) + "-" + std::to_string(++seq));
        fs::remove_all(path_);
        fs::create_directories(path_);
    }
    ~CloseDir() { std::error_code err; fs::remove_all(path_, err); }
    CloseDir(const CloseDir&) = delete;
    CloseDir& operator=(const CloseDir&) = delete;
    CloseDir(CloseDir&&) = delete;
    CloseDir& operator=(CloseDir&&) = delete;
    [[nodiscard]] const fs::path& path() const { return path_; }
private:
    fs::path path_;
};

std::int64_t count_marks(Connection& c) {
    Stmt s(c.raw(), "SELECT COUNT(*) FROM close_marks");
    EXPECT_TRUE(s.step_row());
    return sqlite3_column_int64(s.raw(), 0);
}

}  // namespace

TEST(ConnectionClose, ReleasesHandleAndIsIdempotent) {
    auto c = Connection::open(":memory:");
    EXPECT_TRUE(c.is_open());
    EXPECT_NE(c.raw(), nullptr);
    c.close();
    EXPECT_FALSE(c.is_open());
    EXPECT_EQ(c.raw(), nullptr);
    EXPECT_THROW(c.exec("SELECT 1"), SqliteError);
    EXPECT_NO_THROW(c.rollback());
    EXPECT_EQ(c.last_insert_rowid(), 0);
    EXPECT_NO_THROW(c.close());
    EXPECT_FALSE(c.is_open());
}

TEST(ConnectionClose, TransactionGuardOnClosedConnectionThrowsInsteadOfCrashing) {
    auto c = Connection::open(":memory:");
    c.exec("CREATE TABLE g (id INTEGER PRIMARY KEY)");
    {
        // 开着的连接上 guard 照常工作(提交后写入可见)。
        starling::persistence::TransactionGuard ok(c);
        c.exec("INSERT INTO g DEFAULT VALUES");
        ok.commit();
    }
    c.close();
    // 关后 raw() 为 nullptr:不加守卫时 sqlite3_get_autocommit(nullptr) 会解引用崩溃。
    EXPECT_THROW(starling::persistence::TransactionGuard bad(c), std::logic_error);
}

TEST(SqliteAdapterClose, MergesWalReleasesHandleAndConnectionThrowsAfterwards) {
    CloseDir dir;
    const auto db = dir.path() / "a.db";
    auto a = SqliteAdapter::open(db);
    a->connection().exec("CREATE TABLE close_marks (id INTEGER PRIMARY KEY)");
    a->connection().exec("INSERT INTO close_marks DEFAULT VALUES");
    // WAL 模式下提交的写入先落在 -wal 里。
    ASSERT_TRUE(fs::exists(fs::path(db.string() + "-wal")));
    ASSERT_GT(fs::file_size(fs::path(db.string() + "-wal")), 0u);

    a->close();

    const fs::path wal = db.string() + "-wal";
    EXPECT_TRUE(!fs::exists(wal) || fs::file_size(wal) == 0);
    EXPECT_THROW(a->connection(), std::logic_error);
    try {
        a->connection();
        FAIL() << "expected std::logic_error";
    } catch (const std::logic_error& e) {
        EXPECT_STREQ(e.what(), "adapter closed");
    }
    EXPECT_THROW(a->has_index("idx_statement_id_tenant"), std::logic_error);
    EXPECT_NO_THROW(a->close());  // 二次 close 无操作

    // 数据已合并进主文件:重开后可见。
    auto again = SqliteAdapter::open(db);
    EXPECT_EQ(count_marks(again->connection()), 1);
}

TEST(SqliteAdapterClose, InMemoryAdapterCloses) {
    auto a = SqliteAdapter::open(":memory:");
    EXPECT_NO_THROW(a->close());
    EXPECT_THROW(a->connection(), std::logic_error);
}

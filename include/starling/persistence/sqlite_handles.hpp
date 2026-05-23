#pragma once
#include <sqlite3.h>
#include <memory>

namespace starling::persistence {

struct SqliteCloser  { void operator()(sqlite3* p)      const noexcept { if (p) sqlite3_close_v2(p); } };
struct StmtFinalizer { void operator()(sqlite3_stmt* p) const noexcept { if (p) sqlite3_finalize(p); } };

using SqliteHandle = std::unique_ptr<sqlite3, SqliteCloser>;
using StmtHandle   = std::unique_ptr<sqlite3_stmt, StmtFinalizer>;

}  // namespace starling::persistence

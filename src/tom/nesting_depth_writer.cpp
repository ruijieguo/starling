#include "starling/tom/nesting_depth_writer.hpp"

#include "starling/persistence/sqlite_handles.hpp"

#include <sqlite3.h>
#include <stdexcept>
#include <string>

namespace starling::tom::nesting_depth_writer {

int compute_nesting_depth(
        persistence::Connection& conn,
        const extractor::ExtractedStatement& s) {
    if (s.object_kind != "statement") {
        return 0;
    }

    sqlite3* db = conn.raw();
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db,
            "SELECT nesting_depth FROM statements WHERE id = ?",
            -1, &raw, nullptr) != SQLITE_OK) {
        throw std::runtime_error(
            std::string("nesting_depth_writer: prepare failed: ") +
            sqlite3_errmsg(db));
    }
    persistence::StmtHandle h(raw);
    sqlite3_bind_text(h.get(), 1, s.object_value.c_str(), -1, SQLITE_TRANSIENT);

    const int rc = sqlite3_step(h.get());
    if (rc == SQLITE_ROW) {
        const int result = sqlite3_column_int(h.get(), 0) + 1;
        if (result > 2) {
            throw NestingDepthOverflow(result);
        }
        return result;
    }
    if (rc == SQLITE_DONE) {
        throw std::runtime_error(
            "nesting_depth_writer: parent statement not found: " + s.object_value);
    }
    throw std::runtime_error(
        std::string("nesting_depth_writer: step failed: ") + sqlite3_errmsg(db));
}

}  // namespace starling::tom::nesting_depth_writer

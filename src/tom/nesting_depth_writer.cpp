#include "starling/tom/nesting_depth_writer.hpp"

#include "starling/persistence/sqlite_handles.hpp"

#include <sqlite3.h>
#include <stdexcept>
#include <string>
#include <unordered_set>

namespace starling::tom::nesting_depth_writer {

int compute_nesting_depth(
        persistence::Connection& conn,
        const extractor::ExtractedStatement& s,
        int max_depth) {
    if (s.object_kind != "statement") {
        return 0;
    }
    sqlite3* db = conn.raw();
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db,
            "SELECT object_kind, object_value FROM statements "
            "WHERE id = ? AND tenant_id = ?",
            -1, &raw, nullptr) != SQLITE_OK) {
        throw std::runtime_error(
            std::string("nesting_depth_writer: prepare failed: ") +
            sqlite3_errmsg(db));
    }
    persistence::StmtHandle h(raw);

    std::unordered_set<std::string> seen;
    std::string cur = s.object_value;
    int depth = 0;
    while (true) {
        depth += 1;
        if (max_depth > 0 && depth > max_depth) {
            throw NestingDepthOverflow(depth);
        }
        if (!seen.insert(cur).second) {
            throw NestingCycle(cur);
        }
        sqlite3_reset(h.get());
        sqlite3_clear_bindings(h.get());
        sqlite3_bind_text(h.get(), 1, cur.c_str(), -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(h.get(), 2, s.holder_tenant_id.c_str(), -1, SQLITE_TRANSIENT);
        const int rc = sqlite3_step(h.get());
        if (rc == SQLITE_DONE) {
            throw std::runtime_error(
                "nesting_depth_writer: parent statement not found in tenant " +
                s.holder_tenant_id + ": " + cur);
        }
        if (rc != SQLITE_ROW) {
            throw std::runtime_error(
                std::string("nesting_depth_writer: step failed: ") +
                sqlite3_errmsg(db));
        }
        const auto* okind = sqlite3_column_text(h.get(), 0);
        const std::string parent_kind =
            okind ? reinterpret_cast<const char*>(okind) : "";
        if (parent_kind != "statement") {
            break;  // reached a flat leaf; depth is the chain length
        }
        const auto* oval = sqlite3_column_text(h.get(), 1);
        cur = oval ? reinterpret_cast<const char*>(oval) : "";
    }
    return depth;
}

}  // namespace starling::tom::nesting_depth_writer

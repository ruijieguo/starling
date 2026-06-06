#include "starling/tom/common_ground.hpp"

#include "starling/bus/sqlite_helpers.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <sqlite3.h>

namespace starling::tom::common_ground {

namespace {
using starling::bus::detail::bind_sv;
using starling::persistence::StmtHandle;
}  // namespace

std::vector<CommonGroundEntry> query(
    persistence::SqliteAdapter& adapter,
    std::string_view self_id,
    std::string_view target_id,
    std::string_view tenant_id,
    std::string_view as_of_iso8601)
{
    std::vector<CommonGroundEntry> out;
    sqlite3* db = adapter.connection().raw();

    // parties_json contains both self and target; status is active;
    // grounded_at <= as_of or NULL; expired_at > as_of or NULL.
    // LIKE '%"id"%' matches a quoted id within the JSON array.
    const char* sql =
        "SELECT id, tenant_id, statement_id, status, parties_json, created_at, updated_at "
        "FROM common_ground "
        "WHERE tenant_id=? "
        "  AND status IN ('grounded','asserted_unack','suspected_diverge') "
        "  AND parties_json LIKE ? AND parties_json LIKE ? "
        "  AND (grounded_at IS NULL OR grounded_at <= ?) "
        "  AND (expired_at IS NULL OR expired_at > ?)";

    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK)
        return out;

    StmtHandle h(raw);
    const std::string like_self   = std::string("%\"") + std::string(self_id)   + "\"%";
    const std::string like_target = std::string("%\"") + std::string(target_id) + "\"%";
    const std::string as_of(as_of_iso8601);

    bind_sv(h.get(), 1, tenant_id);
    bind_sv(h.get(), 2, like_self);
    bind_sv(h.get(), 3, like_target);
    bind_sv(h.get(), 4, as_of);
    bind_sv(h.get(), 5, as_of);

    auto col = [&](int i) -> std::string {
        const char* t = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), i));
        return t ? std::string(t) : std::string();
    };

    while (sqlite3_step(h.get()) == SQLITE_ROW) {
        CommonGroundEntry e;
        e.id            = col(0);
        e.tenant_id     = col(1);
        e.statement_id  = col(2);
        e.status        = col(3);
        e.parties_json  = col(4);
        e.created_at    = col(5);
        e.updated_at    = col(6);
        out.push_back(std::move(e));
    }
    return out;
}

}  // namespace starling::tom::common_ground

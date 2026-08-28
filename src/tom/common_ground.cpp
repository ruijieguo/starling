#include "starling/tom/common_ground.hpp"

#include "starling/persistence/sqlite_helpers.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/schema/common_ground_scope.hpp"

#include <sqlite3.h>

#include <algorithm>

namespace starling::tom::common_ground {

namespace {
using starling::persistence::detail::bind_sv;
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
    const char* sql =
        "SELECT id, tenant_id, statement_id, status, parties_json, created_at, updated_at "
        "FROM common_ground "
        "WHERE tenant_id=? "
        "  AND status IN ('grounded','asserted_unack','suspected_diverge') "
        "  AND (grounded_at IS NULL OR grounded_at <= ?) "
        "  AND (expired_at IS NULL OR expired_at > ?)";

    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK)
        return out;

    StmtHandle h(raw);
    const std::string as_of(as_of_iso8601);

    bind_sv(h.get(), 1, tenant_id);
    bind_sv(h.get(), 2, as_of);
    bind_sv(h.get(), 3, as_of);

    auto col = [&](int i) -> std::string {
        const char* t = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), i));
        return t ? std::string(t) : std::string();
    };

    while (sqlite3_step(h.get()) == SQLITE_ROW) {
        const std::string parties_json = col(4);
        const auto parties = schema::parse_common_ground_parties_json(parties_json);
        if (!parties ||
            std::find(parties->begin(), parties->end(), self_id) == parties->end() ||
            std::find(parties->begin(), parties->end(), target_id) == parties->end()) {
            continue;
        }
        CommonGroundEntry e;
        e.id            = col(0);
        e.tenant_id     = col(1);
        e.statement_id  = col(2);
        e.status        = col(3);
        e.parties_json  = parties_json;
        e.created_at    = col(5);
        e.updated_at    = col(6);
        out.push_back(std::move(e));
    }
    return out;
}

}  // namespace starling::tom::common_ground

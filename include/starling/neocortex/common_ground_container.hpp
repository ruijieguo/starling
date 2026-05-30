#pragma once
#include "starling/persistence/sqlite_adapter.hpp"
#include <string>
#include <string_view>

namespace starling::neocortex {

class CommonGroundContainer {
public:
    explicit CommonGroundContainer(persistence::SqliteAdapter& adapter);
    // 从 common_ground 表物化 grounded/asserted_unack/suspected_diverge 三组
    // statement_id 列表 → containers.content_json (kind='common_ground', holder_id=cg_ref).
    // 单 version CAS (复用 PersonaContainer 的 CAS 模式).
    void rebuild(persistence::Connection& conn, std::string_view tenant_id,
                 std::string_view cg_ref, std::string_view now_iso);

    // Python binding helper.
    persistence::Connection& connection() { return adapter_.connection(); }

private:
    [[maybe_unused]] persistence::SqliteAdapter& adapter_;
};

}  // namespace starling::neocortex

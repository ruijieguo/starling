#include "starling/tom/tom_engine.hpp"

#include "starling/persistence/sqlite_handles.hpp"
#include "starling/retrieval/statement_row.hpp"
#include "starling/store/sqlite_meta_store.hpp"

#include <sqlite3.h>

#include <stdexcept>
#include <string>
#include <vector>

namespace starling::tom {

ToMEngine::ToMEngine(persistence::SqliteAdapter&  adapter,
                     cognizer::CognizerHub&       hub,
                     cognizer::KnowledgeFrontier& frontier)
    : adapter_(adapter), hub_(hub), frontier_(frontier) {}

Context ToMEngine::perspective_take(
    std::string_view target_cognizer_id,
    std::string_view tenant_id,
    std::string_view as_of_iso8601) const
{
    const std::string target(target_cognizer_id);
    const std::string tenant(tenant_id);
    const std::string as_of(as_of_iso8601);

    // Step 1: visible engrams (via KnowledgeFrontier)
    auto engram_set = frontier_.visible_engrams_at(tenant, target, as_of);
    std::vector<std::string> visible_engram_ids(
        engram_set.begin(), engram_set.end());

    // Step 2: target beliefs — consolidated|archived statements held by target,
    //         valid_from/valid_to filtered to as_of. P3.b1 phase 3:读收编进
    //         MetaStore.query_statements(默认 state IN(consolidated,archived) +
    //         review 守卫 + as_of 时间窗即原 WHERE)。
    store::SqliteMetaStore meta(adapter_.connection());
    store::StatementFilter bf;
    bf.tenant_id     = std::string(tenant);
    bf.holder_id     = std::string(target);
    bf.as_of_iso8601 = std::string(as_of);
    std::vector<retrieval::StatementRow> target_beliefs = meta.query_statements(bf);

    // Step 3: common ground (P2.j: real read from common_ground table)
    // self_id hardcoded to "system_self" per spec §7.2 (P2.b reads from
    // RuntimeConfig).
    auto cg = common_ground::query(
        adapter_, "system_self", target, tenant, as_of);

    return Context{
        std::move(visible_engram_ids),
        std::move(target_beliefs),
        std::move(cg)
    };
}

}  // namespace starling::tom

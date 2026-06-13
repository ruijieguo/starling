#include "starling/tom/mentalizing.hpp"

#include "starling/store/sqlite_meta_store.hpp"

#include <string>
#include <vector>

namespace starling::tom::mentalizing {

// SELECT all statements held by cognizer X about subject Y. Optionally filter
// by modality. P3.b1 phase 3:读收编进 MetaStore.query_statements —— 默认
// state IN(consolidated,archived) + review NOT IN(rejected,pending_review) +
// as_of 时间窗即原 WHERE;subject_kind='cognizer'。
std::vector<retrieval::StatementRow> what_does_X_believe(
    persistence::SqliteAdapter& adapter,
    std::string_view x,
    std::string_view about_y,
    std::string_view tenant,
    std::string_view as_of,
    std::string_view modality_filter)
{
    store::SqliteMetaStore meta(adapter.connection());
    store::StatementFilter f;
    f.tenant_id     = std::string(tenant);
    f.holder_id     = std::string(x);
    f.subject_kind  = "cognizer";
    f.subject_id    = std::string(about_y);
    f.as_of_iso8601 = std::string(as_of);
    if (!modality_filter.empty()) f.modality = std::string(modality_filter);
    return meta.query_statements(f);
}

}  // namespace starling::tom::mentalizing

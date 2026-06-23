// mental_state_of — X's full mental state grouped by attitude. Mirrors what_does_X_believe
// (SqliteMetaStore + StatementFilter) but drops the subject filter and buckets in C++.
#include "starling/tom/mentalizing.hpp"
#include "starling/store/sqlite_meta_store.hpp"
#include <string>
#include <vector>

namespace starling::tom::mentalizing {

MentalState mental_state_of(
    persistence::SqliteAdapter& adapter,
    std::string_view x,
    std::string_view tenant,
    std::string_view as_of) {
    store::SqliteMetaStore meta(adapter.connection());
    store::StatementFilter f;
    f.tenant_id     = std::string(tenant);
    f.holder_id     = std::string(x);
    f.as_of_iso8601 = std::string(as_of);
    // No subject/modality filter -> ALL of X's held statements.
    const auto rows = meta.query_statements(f);

    MentalState out;
    for (const auto& r : rows) {
        // predicate-first (extraction emits knows/prefers as predicates); modality
        // KNOWS/PREFERS (valid enum values from non-extraction write paths) also route
        // here as fallback so knowledge/preferences are caught either way.
        if (r.predicate == "prefers" || r.modality == "prefers")  out.preferences.push_back(r);
        else if (r.predicate == "knows" || r.modality == "knows") out.knowledge.push_back(r);
        else if (r.modality == "believes") out.beliefs.push_back(r);
        else if (r.modality == "desires")  out.desires.push_back(r);
        else if (r.modality == "intends")  out.intentions.push_back(r);
        else if (r.modality == "commits")  out.commitments.push_back(r);
        // occurred / norm_* / enforces / observes -> dropped.
    }
    return out;
}

}  // namespace starling::tom::mentalizing

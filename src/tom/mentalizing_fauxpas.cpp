// detect_faux_pas — the faux-pas precondition (ignorance asymmetry) via does_X_know.
#include "starling/tom/mentalizing.hpp"
#include "starling/store/sqlite_meta_store.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include <sqlite3.h>
#include <set>
#include <string>
#include <vector>

namespace starling::tom::mentalizing {
namespace {

std::vector<std::string> cast_of(persistence::SqliteAdapter& a, std::string_view tenant) {
    std::vector<std::string> out;
    const char* sql = "SELECT DISTINCT cognizer_id FROM perception_state WHERE tenant_id=?1";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(a.connection().raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
        return out;
    persistence::StmtHandle h{raw};
    sqlite3_bind_text(raw, 1, tenant.data(), static_cast<int>(tenant.size()), SQLITE_TRANSIENT);
    while (sqlite3_step(raw) == SQLITE_ROW) {
        const unsigned char* t = sqlite3_column_text(raw, 0);
        if (t) out.emplace_back(reinterpret_cast<const char*>(t));
    }
    return out;
}

}  // namespace

std::vector<FauxPasCandidate> detect_faux_pas(
    persistence::SqliteAdapter& adapter,
    cognizer::KnowledgeFrontier& frontier,
    std::string_view tenant,
    std::string_view as_of)
{
    std::vector<FauxPasCandidate> out;
    const auto cast = cast_of(adapter, tenant);
    if (cast.size() < 2) return out;

    store::SqliteMetaStore meta(adapter.connection());
    store::StatementFilter f;
    f.tenant_id = std::string(tenant);
    f.as_of_iso8601 = std::string(as_of);
    const auto rows = meta.query_statements(f);

    std::set<std::string> seen;
    for (const auto& r : rows) {
        const std::string key = r.subject_kind + "|" + r.subject_id + "|" + r.predicate +
                                "|" + r.canonical_object_hash;
        if (!seen.insert(key).second) continue;
        FactKey fk{r.subject_kind, r.subject_id, r.predicate, r.canonical_object_hash};
        std::vector<std::string> knowers, ignorant;
        for (const auto& x : cast) {
            const auto k = does_X_know(adapter, frontier, x, fk, tenant, as_of);
            // Knower = NotKnown ∪ FullKnowledge, by design (spec decision D3). Narrated
            // facts are held by holder='narrator', so a character rarely reaches
            // FullKnowledge (that needs the character's OWN assertion). The per-character
            // signal that survives the holder gap is evidence VISIBILITY: NotKnown means
            // F's evidence engram is visible to X (X witnessed it / was present =
            // effectively knows); Unknowable means no visible evidence (X was absent =
            // ignorant). Hence Unknowable -> ignorant, everything else -> knower.
            if (k == KnowsResult::Unknowable)
                ignorant.push_back(x);
            else
                knowers.push_back(x);
        }
        if (!ignorant.empty() && !knowers.empty())
            for (const auto& x : ignorant)
                out.push_back({x, r, knowers});
    }
    return out;
}

}  // namespace starling::tom::mentalizing

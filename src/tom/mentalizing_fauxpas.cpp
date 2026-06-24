// detect_faux_pas — faux-pas precondition via per-event perception (what_does_X_think.is_stale).
#include "starling/tom/mentalizing.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include <sqlite3.h>
#include <string>
#include <vector>

namespace starling::tom::mentalizing {
namespace {
std::vector<std::string> distinct_col(persistence::SqliteAdapter& a, std::string_view tenant,
                                      const char* col) {
    std::vector<std::string> out;
    const std::string sql = std::string("SELECT DISTINCT ") + col +
                            " FROM perception_state WHERE tenant_id=?1";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(a.connection().raw(), sql.c_str(), -1, &raw, nullptr) != SQLITE_OK)
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
    std::string_view as_of) {
    std::vector<FauxPasCandidate> out;
    const auto cast = distinct_col(adapter, tenant, "cognizer_id");
    if (cast.size() < 2) return out;
    const auto themes = distinct_col(adapter, tenant, "theme_id");

    for (const auto& theme : themes) {
        std::vector<std::string> knowers;
        struct Stale { std::string x, value, dim; };
        std::vector<Stale> stale;
        std::string actual;
        for (const auto& x : cast) {
            const auto sb = what_does_X_think(adapter, frontier, x, theme, tenant, as_of, "");
            if (!sb.has_belief) continue;       // never perceived this theme
            if (sb.is_stale) {
                stale.push_back({x, sb.state_value, sb.state_dim});
            } else {
                knowers.push_back(x);
                if (actual.empty()) actual = sb.state_value;   // current truth (knowers agree)
            }
        }
        if (knowers.empty() || stale.empty()) continue;
        for (const auto& s : stale)
            out.push_back({s.x, theme, s.dim, s.value, actual, knowers});
    }
    return out;
}
}  // namespace starling::tom::mentalizing

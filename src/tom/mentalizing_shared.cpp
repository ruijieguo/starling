#include "starling/tom/mentalizing.hpp"

#include "starling/persistence/sqlite_handles.hpp"

#include <sqlite3.h>
#include <functional>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <tuple>
#include <unordered_map>
#include <vector>

namespace starling::tom::mentalizing {

namespace {

// Composite key for grouping shared facts.
// (subject_kind, subject_id, predicate, canonical_object_hash, polarity)
using SharedKey = std::tuple<std::string, std::string, std::string,
                              std::string, std::string>;

struct SharedKeyHash {
    std::size_t operator()(const SharedKey& k) const noexcept {
        std::size_t h = 0;
        auto mix = [&](const std::string& s) {
            h ^= std::hash<std::string>{}(s) + 0x9e3779b9 + (h << 6) + (h >> 2);
        };
        mix(std::get<0>(k));
        mix(std::get<1>(k));
        mix(std::get<2>(k));
        mix(std::get<3>(k));
        mix(std::get<4>(k));
        return h;
    }
};

struct GroupData {
    std::set<std::string> holder_ids;            // distinct holders that have this fact
    std::map<std::string, std::string> stmt_ids; // holder_id -> statement_id (first seen)
};

}  // namespace

std::vector<SharedFact> shared_with(
    persistence::SqliteAdapter& adapter,
    const std::vector<std::string>& member_cognizer_ids,
    std::string_view tenant,
    std::string_view as_of)
{
    if (member_cognizer_ids.empty()) return {};

    auto& conn = adapter.connection();
    sqlite3* db = conn.raw();

    // Build parameterised IN clause: ?,?,?,...
    std::string placeholders;
    for (std::size_t i = 0; i < member_cognizer_ids.size(); ++i) {
        if (i) placeholders += ',';
        placeholders += '?';
    }

    const std::string sql =
        "SELECT id, holder_id, subject_kind, subject_id, predicate,"
        "       canonical_object_hash, polarity"
        "  FROM statements"
        " WHERE tenant_id = ?1"
        "   AND holder_id IN (" + placeholders + ")"
        "   AND consolidation_state IN ('consolidated','archived')"
        "   AND review_status NOT IN ('rejected','pending_review')"
        "   AND (valid_from IS NULL OR valid_from <= ?2)"
        "   AND (valid_to   IS NULL OR valid_to   >  ?2)";

    // Bind index math:
    //   ?1 = tenant_id
    //   ?2 ... ?2+N-1 = member_cognizer_ids  (N members)
    //   ?2+N, ?2+N+1  = as_of (twice)
    // Simplify: tenant=?1, members=?2..?(N+1), as_of=?(N+2) twice
    // Rebuild binding positions to match dynamic IN clause.
    // The ?1 and ?2 above actually refer to positional slots BEFORE the IN list:
    //   slot 1 = tenant_id
    //   slots 2..N+1 = member ids
    //   slot N+2 = as_of (used twice via the same binding)
    // Rewrite SQL to use explicit slot numbers for members.
    //
    // Simpler approach: bind tenant as ?1, then members as ?2..?(M+1),
    // then as_of appears as the (M+2)-th and (M+3)-th bindings in the WHERE
    // but since SQLite named params aren't used, we must renumber.
    // Rebuild with explicit position numbers.

    const int M = static_cast<int>(member_cognizer_ids.size());

    // Build final SQL with numbered params:
    //   ?1 = tenant, ?2..?(M+1) = members, ?(M+2) = as_of (both occurrences)
    std::string member_slots;
    for (int i = 2; i <= M + 1; ++i) {
        if (i > 2) member_slots += ',';
        member_slots += '?' + std::to_string(i);
    }
    const std::string final_sql =
        "SELECT id, holder_id, subject_kind, subject_id, predicate,"
        "       canonical_object_hash, polarity"
        "  FROM statements"
        " WHERE tenant_id = ?1"
        "   AND holder_id IN (" + member_slots + ")"
        "   AND consolidation_state IN ('consolidated','archived')"
        "   AND review_status NOT IN ('rejected','pending_review')"
        "   AND (valid_from IS NULL OR valid_from <= ?" + std::to_string(M + 2) + ")"
        "   AND (valid_to   IS NULL OR valid_to   >  ?" + std::to_string(M + 2) + ")";

    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, final_sql.c_str(), -1, &raw, nullptr) != SQLITE_OK) {
        throw std::runtime_error(
            std::string("shared_with prepare: ") + sqlite3_errmsg(db));
    }
    persistence::StmtHandle stmt{raw};

    sqlite3_bind_text(raw, 1, tenant.data(), static_cast<int>(tenant.size()),
                      SQLITE_TRANSIENT);
    for (int i = 0; i < M; ++i) {
        sqlite3_bind_text(raw, i + 2,
                          member_cognizer_ids[static_cast<std::size_t>(i)].c_str(),
                          -1, SQLITE_TRANSIENT);
    }
    sqlite3_bind_text(raw, M + 2, as_of.data(), static_cast<int>(as_of.size()),
                      SQLITE_TRANSIENT);

    // Group in C++ by (subject_kind, subject_id, predicate, canonical_object_hash, polarity).
    std::unordered_map<SharedKey, GroupData, SharedKeyHash> groups;

    while (true) {
        const int rc = sqlite3_step(raw);
        if (rc == SQLITE_DONE) break;
        if (rc != SQLITE_ROW) {
            throw std::runtime_error(
                std::string("shared_with step: ") + sqlite3_errmsg(db));
        }
        auto col_text = [raw](int i) -> std::string {
            const unsigned char* t = sqlite3_column_text(raw, i);
            return t ? std::string(reinterpret_cast<const char*>(t)) : std::string{};
        };
        std::string stmt_id        = col_text(0);
        std::string holder_id      = col_text(1);
        std::string subject_kind   = col_text(2);
        std::string subject_id     = col_text(3);
        std::string predicate      = col_text(4);
        std::string canon_hash     = col_text(5);
        std::string polarity       = col_text(6);

        SharedKey key{subject_kind, subject_id, predicate, canon_hash, polarity};
        auto& grp = groups[key];
        grp.holder_ids.insert(holder_id);
        if (grp.stmt_ids.find(holder_id) == grp.stmt_ids.end()) {
            grp.stmt_ids[holder_id] = stmt_id;
        }
    }

    // Emit only groups where ALL members hold the fact.
    const std::size_t expected = member_cognizer_ids.size();
    std::vector<SharedFact> result;

    for (auto& [key, grp] : groups) {
        if (grp.holder_ids.size() != expected) continue;
        SharedFact sf;
        sf.subject_kind          = std::get<0>(key);
        sf.subject_id            = std::get<1>(key);
        sf.predicate             = std::get<2>(key);
        sf.canonical_object_hash = std::get<3>(key);
        sf.polarity              = std::get<4>(key);
        for (auto& [h, sid] : grp.stmt_ids) {
            sf.source_statement_ids.push_back(sid);
        }
        result.push_back(std::move(sf));
    }
    return result;
}

}  // namespace starling::tom::mentalizing

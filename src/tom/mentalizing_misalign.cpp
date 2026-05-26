#include "starling/tom/mentalizing.hpp"

#include "starling/persistence/sqlite_handles.hpp"

#include <sqlite3.h>
#include <cmath>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

namespace starling::tom::mentalizing {

namespace {

// Fetch all consolidated/archived beliefs held by holder about (subject_kind,
// subject_id) for the given tenant, time-anchored at as_of.
std::vector<retrieval::StatementRow> fetch_beliefs(
    sqlite3* db,
    std::string_view tenant,
    std::string_view holder,
    std::string_view subject_kind,
    std::string_view subject_id,
    std::string_view as_of)
{
    static constexpr const char* kSql =
        "SELECT id, tenant_id, holder_id, holder_perspective,"
        "       subject_kind, subject_id, predicate,"
        "       object_kind, object_value, canonical_object_hash,"
        "       modality, polarity, confidence, observed_at,"
        "       valid_from, valid_to, consolidation_state, review_status,"
        "       evidence_json"
        "  FROM statements"
        " WHERE tenant_id = ?1"
        "   AND holder_id = ?2"
        "   AND subject_kind = ?3"
        "   AND subject_id = ?4"
        "   AND consolidation_state IN ('consolidated','archived')"
        "   AND review_status NOT IN ('rejected','pending_review')"
        "   AND (valid_from IS NULL OR valid_from <= ?5)"
        "   AND (valid_to   IS NULL OR valid_to   >  ?5)";

    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, kSql, -1, &raw, nullptr) != SQLITE_OK) {
        throw std::runtime_error(
            std::string("find_misalignment fetch prepare: ") + sqlite3_errmsg(db));
    }
    persistence::StmtHandle h{raw};

    sqlite3_bind_text(raw, 1, tenant.data(), static_cast<int>(tenant.size()),
                      SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, 2, holder.data(), static_cast<int>(holder.size()),
                      SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, 3, subject_kind.data(),
                      static_cast<int>(subject_kind.size()), SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, 4, subject_id.data(), static_cast<int>(subject_id.size()),
                      SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, 5, as_of.data(), static_cast<int>(as_of.size()),
                      SQLITE_TRANSIENT);

    std::vector<retrieval::StatementRow> rows;
    while (true) {
        const int rc = sqlite3_step(raw);
        if (rc == SQLITE_DONE) break;
        if (rc != SQLITE_ROW) {
            throw std::runtime_error(
                std::string("find_misalignment fetch step: ") + sqlite3_errmsg(db));
        }
        auto col_text = [raw](int i) -> std::string {
            const unsigned char* t = sqlite3_column_text(raw, i);
            return t ? std::string(reinterpret_cast<const char*>(t)) : std::string{};
        };
        retrieval::StatementRow r;
        r.id                    = col_text(0);
        r.tenant_id             = col_text(1);
        r.holder_id             = col_text(2);
        r.holder_perspective    = col_text(3);
        r.subject_kind          = col_text(4);
        r.subject_id            = col_text(5);
        r.predicate             = col_text(6);
        r.object_kind           = col_text(7);
        r.object_value          = col_text(8);
        r.canonical_object_hash = col_text(9);
        r.modality              = col_text(10);
        r.polarity              = col_text(11);
        r.confidence            = sqlite3_column_double(raw, 12);
        r.observed_at           = col_text(13);
        r.valid_from            = col_text(14);
        r.valid_to              = col_text(15);
        r.consolidation_state   = col_text(16);
        r.review_status         = col_text(17);
        r.evidence_json         = col_text(18);
        rows.push_back(std::move(r));
    }
    return rows;
}

// Key for aligning beliefs: (predicate, canonical_object_hash).
struct BeliefKey {
    std::string predicate;
    std::string canonical_object_hash;
    bool operator==(const BeliefKey& o) const noexcept {
        return predicate == o.predicate &&
               canonical_object_hash == o.canonical_object_hash;
    }
};

struct BeliefKeyHash {
    std::size_t operator()(const BeliefKey& k) const noexcept {
        std::size_t h = std::hash<std::string>{}(k.predicate);
        h ^= std::hash<std::string>{}(k.canonical_object_hash) + 0x9e3779b9 + (h << 6) + (h >> 2);
        return h;
    }
};

}  // namespace

Misalignment find_misalignment(
    persistence::SqliteAdapter& adapter,
    std::string_view x,
    std::string_view y,
    std::string_view subject_kind,
    std::string_view subject_id,
    std::string_view tenant,
    std::string_view as_of)
{
    sqlite3* db = adapter.connection().raw();

    auto x_rows = fetch_beliefs(db, tenant, x, subject_kind, subject_id, as_of);
    auto y_rows = fetch_beliefs(db, tenant, y, subject_kind, subject_id, as_of);

    // Build lookup maps by belief key.
    std::unordered_map<BeliefKey, retrieval::StatementRow, BeliefKeyHash> x_map, y_map;
    for (auto& r : x_rows) x_map[{r.predicate, r.canonical_object_hash}] = r;
    for (auto& r : y_rows) y_map[{r.predicate, r.canonical_object_hash}] = r;

    Misalignment result;

    // X has POS but Y doesn't (or has NEG).
    for (const auto& [key, xr] : x_map) {
        if (xr.polarity != "pos") continue;
        auto it = y_map.find(key);
        if (it == y_map.end() || it->second.polarity != "pos") {
            result.only_x_believes.push_back(xr);
        }
    }

    // Y has POS but X doesn't (or has NEG).
    for (const auto& [key, yr] : y_map) {
        if (yr.polarity != "pos") continue;
        auto it = x_map.find(key);
        if (it == x_map.end() || it->second.polarity != "pos") {
            result.only_y_believes.push_back(yr);
        }
    }

    // Both POS but confidence diverges > 0.3.
    for (const auto& [key, xr] : x_map) {
        if (xr.polarity != "pos") continue;
        auto it = y_map.find(key);
        if (it == y_map.end() || it->second.polarity != "pos") continue;
        const double diff = std::fabs(xr.confidence - it->second.confidence);
        if (diff > 0.3) {
            result.confidence_diverges.emplace_back(xr, it->second);
        }
    }

    return result;
}

}  // namespace starling::tom::mentalizing

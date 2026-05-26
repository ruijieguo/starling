#include "starling/tom/mentalizing.hpp"

#include "starling/persistence/sqlite_handles.hpp"

#include <sqlite3.h>
#include <stdexcept>
#include <string>
#include <unordered_set>

namespace starling::tom::mentalizing {

// Tri-valued knowledge check.
//
// Step 1: Direct assertion — X holds a POS statement matching the fact key
//         within the time anchor and consolidated/archived.
// Step 2: Evidence engrams — statements elsewhere in the DB that carry the
//         same (subject, predicate, canonical_object_hash); extract their
//         engram_ref ids from evidence_json.
//         Intersect that set with X's visible engrams at as_of.
//   Non-empty intersection → NotKnown (evidence was visible but X didn't assert)
//   Empty intersection     → Unknowable
KnowsResult does_X_know(
    persistence::SqliteAdapter& adapter,
    cognizer::KnowledgeFrontier& frontier,
    std::string_view x,
    const FactKey& fact_key,
    std::string_view tenant,
    std::string_view as_of)
{
    auto& conn = adapter.connection();
    sqlite3* db = conn.raw();

    // ── Step 1: direct assertion ──────────────────────────────────────────
    {
        static constexpr const char* kDirectSql =
            "SELECT 1 FROM statements"
            " WHERE tenant_id = ?1"
            "   AND holder_id = ?2"
            "   AND subject_kind = ?3"
            "   AND subject_id = ?4"
            "   AND predicate = ?5"
            "   AND canonical_object_hash = ?6"
            "   AND polarity = 'pos'"
            "   AND consolidation_state IN ('consolidated','archived')"
            "   AND review_status NOT IN ('rejected','pending_review')"
            "   AND (valid_from IS NULL OR valid_from <= ?7)"
            "   AND (valid_to   IS NULL OR valid_to   >  ?7)"
            " LIMIT 1";

        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db, kDirectSql, -1, &raw, nullptr) != SQLITE_OK) {
            throw std::runtime_error(
                std::string("does_X_know step1 prepare: ") + sqlite3_errmsg(db));
        }
        persistence::StmtHandle h{raw};

        sqlite3_bind_text(raw, 1, tenant.data(), static_cast<int>(tenant.size()),
                          SQLITE_TRANSIENT);
        sqlite3_bind_text(raw, 2, x.data(), static_cast<int>(x.size()),
                          SQLITE_TRANSIENT);
        sqlite3_bind_text(raw, 3, fact_key.subject_kind.c_str(), -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(raw, 4, fact_key.subject_id.c_str(), -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(raw, 5, fact_key.predicate.c_str(), -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(raw, 6, fact_key.canonical_object_hash.c_str(), -1,
                          SQLITE_TRANSIENT);
        sqlite3_bind_text(raw, 7, as_of.data(), static_cast<int>(as_of.size()),
                          SQLITE_TRANSIENT);

        const int rc = sqlite3_step(raw);
        if (rc == SQLITE_ROW) return KnowsResult::FullKnowledge;
        if (rc != SQLITE_DONE) {
            throw std::runtime_error(
                std::string("does_X_know step1 step: ") + sqlite3_errmsg(db));
        }
    }

    // ── Step 2: evidence engram intersection ─────────────────────────────
    // Collect engram_ref ids from evidence_json of statements that carry
    // the same (subject, predicate, canonical_object_hash) anywhere in the DB
    // for this tenant.
    static constexpr const char* kEvidenceSql =
        "SELECT evidence_json FROM statements"
        " WHERE tenant_id = ?1"
        "   AND subject_kind = ?2"
        "   AND subject_id = ?3"
        "   AND predicate = ?4"
        "   AND canonical_object_hash = ?5";

    // Collect raw evidence_json strings.
    std::vector<std::string> evidence_jsons;
    {
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db, kEvidenceSql, -1, &raw, nullptr) != SQLITE_OK) {
            throw std::runtime_error(
                std::string("does_X_know step2 prepare: ") + sqlite3_errmsg(db));
        }
        persistence::StmtHandle h{raw};

        sqlite3_bind_text(raw, 1, tenant.data(), static_cast<int>(tenant.size()),
                          SQLITE_TRANSIENT);
        sqlite3_bind_text(raw, 2, fact_key.subject_kind.c_str(), -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(raw, 3, fact_key.subject_id.c_str(), -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(raw, 4, fact_key.predicate.c_str(), -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(raw, 5, fact_key.canonical_object_hash.c_str(), -1,
                          SQLITE_TRANSIENT);

        while (true) {
            const int rc = sqlite3_step(raw);
            if (rc == SQLITE_DONE) break;
            if (rc != SQLITE_ROW) {
                throw std::runtime_error(
                    std::string("does_X_know step2 step: ") + sqlite3_errmsg(db));
            }
            const unsigned char* t = sqlite3_column_text(raw, 0);
            if (t) evidence_jsons.emplace_back(reinterpret_cast<const char*>(t));
        }
    }

    // Parse engram_ref ids from evidence_json using the same substring scan as
    // basic_retriever.cpp::any_evidence_erased.
    std::unordered_set<std::string> evidence_engram_ids;
    static constexpr const char* kRefKey = "\"engram_ref\":\"";
    for (const auto& ej : evidence_jsons) {
        std::string::size_type pos = 0;
        while (true) {
            auto a = ej.find(kRefKey, pos);
            if (a == std::string::npos) break;
            a += std::char_traits<char>::length(kRefKey);
            auto b = ej.find('"', a);
            if (b == std::string::npos) break;
            evidence_engram_ids.insert(ej.substr(a, b - a));
            pos = b + 1;
        }
    }

    if (evidence_engram_ids.empty()) return KnowsResult::Unknowable;

    // Get X's visible engrams at as_of.
    const auto visible = frontier.visible_engrams_at(tenant, x, as_of);

    // Intersection: any evidence engram visible to X?
    for (const auto& eid : evidence_engram_ids) {
        if (visible.count(eid)) return KnowsResult::NotKnown;
    }
    return KnowsResult::Unknowable;
}

}  // namespace starling::tom::mentalizing

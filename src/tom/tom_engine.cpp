#include "starling/tom/tom_engine.hpp"

#include "starling/persistence/sqlite_handles.hpp"
#include "starling/retrieval/statement_row.hpp"

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

    // Step 2: target beliefs — consolidated|archived statements held by
    //         target, with valid_from/valid_to bounds filtered to as_of.
    //
    //         SELECT order mirrors basic_retriever.cpp column offsets so the
    //         StatementRow mapping is identical.
    static constexpr const char* kBeliefSql =
        "SELECT id, tenant_id, holder_id, holder_perspective, "
        "       subject_kind, subject_id, predicate, "
        "       object_kind, object_value, canonical_object_hash, "
        "       modality, polarity, confidence, observed_at, "
        "       valid_from, valid_to, consolidation_state, review_status, "
        "       evidence_json "
        "  FROM statements "
        " WHERE tenant_id = ?1 "
        "   AND holder_id = ?2 "
        "   AND consolidation_state IN ('consolidated','archived') "
        "   AND review_status NOT IN ('rejected','pending_review') "
        "   AND (valid_from IS NULL OR valid_from <= ?3) "
        "   AND (valid_to   IS NULL OR valid_to   >  ?3)";

    std::vector<retrieval::StatementRow> target_beliefs;
    {
        sqlite3* db  = adapter_.connection().raw();
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db, kBeliefSql, -1, &raw, nullptr) != SQLITE_OK) {
            throw std::runtime_error(
                std::string("perspective_take prepare failed: ")
                + sqlite3_errmsg(db));
        }
        persistence::StmtHandle stmt{raw};

        sqlite3_bind_text(raw, 1, tenant.c_str(), -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(raw, 2, target.c_str(), -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(raw, 3, as_of.c_str(),  -1, SQLITE_TRANSIENT);

        auto col_text = [raw](int i) -> std::string {
            const unsigned char* t = sqlite3_column_text(raw, i);
            return t ? std::string(reinterpret_cast<const char*>(t))
                     : std::string();
        };

        while (true) {
            const int rc = sqlite3_step(raw);
            if (rc == SQLITE_DONE) break;
            if (rc != SQLITE_ROW) {
                throw std::runtime_error(
                    std::string("perspective_take step failed: ")
                    + sqlite3_errmsg(db));
            }
            retrieval::StatementRow row;
            row.id                    = col_text(0);
            row.tenant_id             = col_text(1);
            row.holder_id             = col_text(2);
            row.holder_perspective    = col_text(3);
            row.subject_kind          = col_text(4);
            row.subject_id            = col_text(5);
            row.predicate             = col_text(6);
            row.object_kind           = col_text(7);
            row.object_value          = col_text(8);
            row.canonical_object_hash = col_text(9);
            row.modality              = col_text(10);
            row.polarity              = col_text(11);
            row.confidence            = sqlite3_column_double(raw, 12);
            row.observed_at           = col_text(13);
            row.valid_from            = col_text(14);
            row.valid_to              = col_text(15);
            row.consolidation_state   = col_text(16);
            row.review_status         = col_text(17);
            row.evidence_json         = col_text(18);
            target_beliefs.push_back(std::move(row));
        }
    }

    // Step 3: common ground (P2.a stub always returns [])
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

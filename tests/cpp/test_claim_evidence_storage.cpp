#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/store/sqlite_meta_store.hpp"
#include "starling/store/sqlite_statement_store.hpp"
#include <gtest/gtest.h>
#include <nlohmann/json.hpp>

namespace starling::store {
namespace {
void seed_claim(sqlite3* db, const char* tenant) {
    const char* sql = "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
        "subject_kind,subject_id,predicate,object_kind,object_value,canonical_object_hash,"
        "modality,polarity,confidence,observed_at,salience,affect_json,activation,last_accessed,"
        "provenance,created_at,updated_at,semantic_claim_json,source_spans_json) VALUES("
        "'same',?,'Mina','first_person','cognizer','Mina','feels','str','sad','h',"
        "'BELIEVES','pos',0.9,'2026-09-11T10:00:00Z',0.5,'{}',0.0,'2026-09-11T10:00:00Z',"
        "'user_input','2026-09-11T10:00:00Z','2026-09-11T10:00:00Z',?,?)";
    sqlite3_stmt* s = nullptr;
    ASSERT_EQ(sqlite3_prepare_v2(db, sql, -1, &s, nullptr), SQLITE_OK);
    const std::string claim = nlohmann::json{{"tenant_fixture", tenant}}.dump();
    sqlite3_bind_text(s, 1, tenant, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(s, 2, claim.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(s, 3, "[{\"span_start\":0,\"span_end\":4}]", -1, SQLITE_TRANSIENT);
    EXPECT_EQ(sqlite3_step(s), SQLITE_DONE);
    sqlite3_finalize(s);
}
}
TEST(ClaimEvidenceStorage, MetaStoreCarriesExactEvidenceAcrossTenantScopedReadersAndReplay) {
    auto a = persistence::SqliteAdapter::open(":memory:");
    persistence::MigrationRunner(a->connection().raw()).migrate_to_latest();
    seed_claim(a->connection().raw(), "a");
    seed_claim(a->connection().raw(), "b");
    SqliteMetaStore meta(a->connection());
    const auto before_a = meta.get_statement("same", "a");
    const auto before_b = meta.get_statement("same", "b");
    ASSERT_TRUE(before_a); ASSERT_TRUE(before_b);
    EXPECT_NE(before_a->semantic_claim_json, before_b->semantic_claim_json);
    SqliteStatementStore store(a->connection());
    EXPECT_EQ(store.mark_consolidated({"same"}, "a", "batch"), 1);
    StatementFilter filter; filter.tenant_id = "a"; filter.id_in = {"same"};
    const auto rows = meta.query_statements(filter);
    ASSERT_EQ(rows.size(), 1u);
    EXPECT_EQ(rows[0].semantic_claim_json, before_a->semantic_claim_json);
    EXPECT_EQ(rows[0].source_spans_json, before_a->source_spans_json);
    EXPECT_EQ(meta.get_statement("same", "b")->consolidation_state, "volatile");
}
}  // namespace starling::store

#include "starling/bus/bus.hpp"
#include "starling/extractor/claim_contract.hpp"
#include "starling/memory/memory_ops.hpp"
#include "starling/retrieval/claim_evidence.hpp"

TEST(ClaimEvidenceStorage, LocalizedClaimKeepsWholeSourceAcrossBusAndNativeReadback) {
    using nlohmann::json;
    using namespace starling;
    auto db=persistence::SqliteAdapter::open(":memory:");
    const std::string payload="Mina: I am relieved about the rehearsal. Can you bring the chairs?";
    memoryops::RememberParams p;
    p.holder_id="Mina";p.tenant_id="default";p.adapter_name="claim-test";p.source_prefix="scope-test";
    p.created_at_iso8601="2099-01-01T00:00:00Z";p.payload.assign(payload.begin(),payload.end());
    const auto source=memoryops::remember_prepare(*db,p);
    const auto raw=R"({"schema_version":2,"statements":[{"holder":"Mina","holder_perspective":"FIRST_PERSON","subject":"Mina","subject_kind":"cognizer","predicate":"feels","object":"relieved about the rehearsal","modality":"BELIEVES","polarity":"POS","nesting_depth":0,"evidence":{"clause_id":"c0","actor":"Mina","attributed_to":null,"assertion_scope":"ASSERTED","scope_markers":["ASSERTED"],"time_text":"","event_time":null}}]})";
    auto parsed=extractor::parse_claim_response(raw,payload,"Mina");
    ASSERT_EQ(parsed.statements.size(),1u);
    auto s=parsed.statements.front();
    auto evidence=json::parse(s.semantic_claim_json);
    evidence["source_span"]["engram_ref"]=source.engram_ref;
    evidence["source_time"]=p.created_at_iso8601;
    s.semantic_claim_json=evidence.dump();s.holder_id="Mina";s.holder_tenant_id="default";
    s.observed_at=p.created_at_iso8601;
    bus::Bus bus(*db);
    const auto result=bus.write(s,source.engram_ref,"scope-first",std::nullopt);
    const auto id=std::visit([](const auto& r){return r.stmt_id;},result);
    store::SqliteMetaStore meta(db->connection());
    const auto stored=meta.get_statement(id,"default");
    ASSERT_TRUE(stored);
    EXPECT_TRUE(retrieval::claim_evidence_error(db->connection(),*stored).empty());
    EXPECT_EQ(json::parse(stored->semantic_claim_json)["source_span"]["span_end"],payload.size());
    auto wrong=*stored;wrong.tenant_id="other";
    EXPECT_FALSE(retrieval::claim_evidence_error(db->connection(),wrong).empty());
    evidence["scope_markers"]=json::array({"ASSERTED","QUESTIONED"});
    s.semantic_claim_json=evidence.dump();
    EXPECT_THROW(bus.write(s,source.engram_ref,"scope-forged",std::nullopt),std::invalid_argument);
}

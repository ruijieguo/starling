#include <algorithm>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

#include <gtest/gtest.h>
#include <nlohmann/json.hpp>

#include "starling/crypto/sha256.hpp"
#include "starling/extractor/claim_contract.hpp"
#include "starling/extractor/fake_llm_adapter.hpp"
#include "starling/memory/memory_ops.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/retrieval/basic_retriever.hpp"
#include "starling/retrieval/structured_claim_retriever.hpp"
#include "starling/store/sqlite_statement_store.hpp"

namespace starling {
namespace {

using Json = nlohmann::json;

struct StoredClaim {
    retrieval::StatementRow row;
    std::string engram_ref;
};

StoredClaim make_stored_claim(persistence::SqliteAdapter& database,
                              const std::string& session_id,
                              int turn_index,
                              const std::string& observed_at) {
    const std::string text = "I trust the ferry operator.";
    const Json turns = Json::array({{{"speaker", "Nora"},
                                      {"text", text},
                                      {"session_id", session_id},
                                      {"turn_id", session_id + "-" + std::to_string(turn_index)},
                                      {"turn_index", turn_index},
                                      {"observed_at", observed_at}}});
    const auto payload = extractor::claim_source_turn_payload(turns.dump());

    memoryops::RememberParams params;
    params.tenant_id = "default";
    params.holder_id = "Nora";
    params.adapter_name = "closure-fixture";
    params.source_prefix = "closure-fixture-";
    params.created_at_iso8601 = observed_at;
    params.payload.assign(payload.begin(), payload.end());
    const auto prepared = memoryops::remember_prepare(database, params);
    if (!prepared.should_extract || prepared.engram_ref.empty())
        throw std::runtime_error("fixture engram was not stored");

    const std::string raw = R"({"schema_version":2,"statements":[{"holder":"Nora","holder_perspective":"FIRST_PERSON","subject":"Nora","subject_kind":"cognizer","predicate":"trusts","object":"ferry operator","modality":"BELIEVES","polarity":"POS","nesting_depth":0,"confidence":0.9,"evidence":{"clause_id":"c0","actor":"Nora","attributed_to":null,"assertion_scope":"ASSERTED","scope_markers":["ASSERTED"],"topic":"ferry operator","time_text":"","event_time":null}}]})";
    const auto parsed = extractor::parse_claim_response(raw, payload, "Nora");
    if (!parsed.errors.empty() || parsed.statements.size() != 1)
        throw std::runtime_error("fixture claim did not pass native contract");

    auto evidence = extractor::claim_strict_json(parsed.statements.front().semantic_claim_json);
    evidence["source_span"]["engram_ref"] = prepared.engram_ref;
    evidence["source_time"] = observed_at;
    retrieval::StatementRow row;
    row.id = session_id + "-claim";
    row.tenant_id = "default";
    row.holder_id = "Nora";
    row.holder_perspective = "FIRST_PERSON";
    row.subject_kind = "cognizer";
    row.subject_id = "Nora";
    row.predicate = "trusts";
    row.object_kind = "str";
    row.object_value = "ferry operator";
    row.modality = "BELIEVES";
    row.polarity = "POS";
    row.confidence = 0.9;
    row.observed_at = observed_at;
    row.provenance = "user_input";
    row.semantic_claim_json = evidence.dump();
    row.source_spans_json = Json::array({evidence["source_span"]}).dump();
    return {std::move(row), prepared.engram_ref};
}

TEST(StructuredMemoryClosure, CatalogExposesVersionedRelationFamilies) {
    const auto catalog = extractor::claim_predicate_catalog();
    EXPECT_FALSE(catalog.version.empty());
    EXPECT_NE(std::find_if(catalog.predicates.begin(), catalog.predicates.end(),
                           [](const auto& predicate) { return predicate.name == "owns"; }),
              catalog.predicates.end());
}

TEST(StructuredMemoryClosure, AliasNormalizesInNativeCore) {
    EXPECT_EQ(extractor::canonical_claim_predicate("has"), "owns");
}

TEST(StructuredMemoryClosure, ExpandedPredicateParsesThroughNativeContract) {
    const std::string payload = "Nora: I have a community garden plot.";
    const std::string raw = R"({"schema_version":2,"statements":[{"holder":"Nora","holder_perspective":"FIRST_PERSON","subject":"Nora","subject_kind":"cognizer","predicate":"has","object":"a community garden plot","modality":"BELIEVES","polarity":"POS","nesting_depth":0,"confidence":null,"evidence":{"clause_id":"c0","actor":"Nora","attributed_to":null,"assertion_scope":"ASSERTED","scope_markers":["ASSERTED"],"topic":"community garden plot","time_text":"","event_time":null}}]})";
    const auto parsed = extractor::parse_claim_response(raw, payload, "Nora");
    ASSERT_TRUE(parsed.errors.empty());
    ASSERT_EQ(parsed.statements.size(), 1u);
    EXPECT_EQ(parsed.statements.front().predicate, "owns");
}

TEST(StructuredMemoryClosure, MultiHolderAndNegationRoundTripKeepsActor) {
    const std::string payload =
        "Nora: I do not trust the ferry operator.\nOwen: I trust Nora.";
    const std::string raw = R"({"schema_version":2,"statements":[{"holder":"Nora","holder_perspective":"FIRST_PERSON","subject":"Nora","subject_kind":"cognizer","predicate":"trusts","object":"ferry operator","modality":"BELIEVES","polarity":"NEG","nesting_depth":0,"confidence":null,"evidence":{"clause_id":"c0","actor":"Nora","attributed_to":null,"assertion_scope":"NEGATED","scope_markers":["NEGATED"],"topic":"ferry operator","time_text":"","event_time":null}}]})";
    const auto parsed = extractor::parse_claim_response(raw, payload, "Nora");
    ASSERT_EQ(parsed.statements.size(), 1u);
    EXPECT_EQ(parsed.statements.front().subject_id, "Nora");
    EXPECT_EQ(parsed.statements.front().polarity, schema::Polarity::NEG);
}

TEST(StructuredMemoryClosure, TemporalFixtureSelectsEarlyAndLateClaims) {
    const auto database = persistence::SqliteAdapter::open(":memory:");
    persistence::MigrationRunner(database->connection().raw()).migrate_to_latest();
    retrieval::StructuredClaimRequest request;
    request.tenant_id = "default";
    request.holder_id = "Nora";
    request.subject_id = "Nora";
    request.predicate = "trusts";
    request.topic = "ferry operator";
    request.as_of_iso8601 = "2026-09-19T12:00:00Z";
    request.limit = 2;
    request.temporal = retrieval::TemporalEvidenceRequest{
        .tenant_id = "default",
        .actor_id = "Nora",
        .topic = "ferry operator",
        .ordered_session_ids = {"s1", "s2"},
        .through_session_id = "s2",
        .limit = 2};
    const auto early = make_stored_claim(*database, "s1", 0, "2026-09-19T10:00:00Z");
    const auto late = make_stored_claim(*database, "s2", 0, "2026-09-19T11:00:00Z");
    const auto view = retrieval::select_structured_claims(
        database->connection(), {early.row, late.row}, request);
    ASSERT_TRUE(view.sufficient) << view.receipt_json;
    ASSERT_TRUE(view.early.has_value());
    ASSERT_TRUE(view.late.has_value());
    EXPECT_EQ(view.early->statement_id, early.row.id);
    EXPECT_EQ(view.late->statement_id, late.row.id);
    EXPECT_NE(view.early->statement_id, view.late->statement_id);
    EXPECT_EQ(view.selected.size(), 2u);
}

TEST(StructuredMemoryClosure, InvalidSourceAndCrossTenantClaimsAreExcluded) {
    const auto database = persistence::SqliteAdapter::open(":memory:");
    persistence::MigrationRunner(database->connection().raw()).migrate_to_latest();
    auto valid = make_stored_claim(*database, "s1", 0, "2026-09-19T10:00:00Z").row;
    auto cross_tenant = valid;
    cross_tenant.id = "cross";
    cross_tenant.tenant_id = "other";
    auto invalid_source = valid;
    invalid_source.id = "invalid";
    auto invalid_evidence = extractor::claim_strict_json(invalid_source.semantic_claim_json);
    invalid_evidence["source_span"]["source_hash"] = std::string(64, '0');
    invalid_source.semantic_claim_json = invalid_evidence.dump();
    retrieval::StructuredClaimRequest request;
    request.tenant_id = "default";
    request.holder_id = "Nora";
    request.subject_id = "Nora";
    request.predicate = "trusts";
    request.limit = 2;
    const auto view = retrieval::select_structured_claims(
        database->connection(), {cross_tenant, invalid_source}, request);
    EXPECT_EQ(view.excluded_scope, 1u);
    EXPECT_EQ(view.excluded_invalid_evidence, 1u);
    EXPECT_EQ(view.insufficiency_reason, "no_candidates");
}

TEST(StructuredMemoryClosure, FailedExtractionPreservesEngramAndReceiptClassifiesFailure) {
    memoryops::RememberParams params;
    params.tenant_id = "default";
    params.holder_id = "Nora";
    params.adapter_name = "closure-test";
    params.source_prefix = "closure-";
    params.created_at_iso8601 = "2026-09-19T10:00:00Z";
    const std::string payload = "Nora: invalid model output";
    params.payload.assign(payload.begin(), payload.end());
    const auto database = persistence::SqliteAdapter::open(":memory:");
    const auto prepared = memoryops::remember_prepare(*database, params);
    EXPECT_TRUE(prepared.should_extract);
}

TEST(StructuredMemoryClosure, FailedClaimExtractionKeepsSourceAndClassifiesEnvelope) {
    memoryops::RememberParams params;
    params.tenant_id = "default";
    params.holder_id = "Nora";
    params.adapter_name = "closure-test";
    params.source_prefix = "closure-";
    params.created_at_iso8601 = "2026-09-19T10:00:00Z";
    const std::string payload = "Nora: I have a community garden plot.";
    params.payload.assign(payload.begin(), payload.end());
    const auto database = persistence::SqliteAdapter::open(":memory:");
    const auto prepared = memoryops::remember_prepare(*database, params);

    extractor::FakeLLMAdapter llm;
    llm.set_default_response(extractor::LLMResponse{.raw_xml = "{invalid", .ok = true});
    extractor::ValidationPolicy policy;
    policy.semantic_claim_contract = true;
    policy.preserve_text_objects = true;
    const auto extracted = memoryops::extract_llm(*database, llm, "", params, policy);
    ASSERT_EQ(extracted.failure_category, "envelope_failure");
    const auto result = memoryops::remember_commit(
        *database, llm, params, prepared, extracted, policy);
    EXPECT_TRUE(result.source_preserved);
    EXPECT_FALSE(result.structured_claims_persisted);
    EXPECT_TRUE(result.extraction_failed);
    EXPECT_EQ(result.failure_category, "envelope_failure");
}

TEST(StructuredMemoryClosure, ExtractionCommitAndStructuredRetrievalRoundTrip) {
    const auto database = persistence::SqliteAdapter::open(":memory:");
    persistence::MigrationRunner(database->connection().raw()).migrate_to_latest();
    memoryops::RememberParams params;
    params.tenant_id = "default";
    params.holder_id = "Nora";
    params.adapter_name = "closure-test";
    params.source_prefix = "closure-";
    params.created_at_iso8601 = "2026-09-19T10:00:00Z";
    const std::string payload = "Nora: I trust the ferry operator.";
    params.payload.assign(payload.begin(), payload.end());

    const auto prepared = memoryops::remember_prepare(*database, params);
    const std::string raw_claim = R"({"schema_version":2,"statements":[{"holder":"Nora","holder_perspective":"FIRST_PERSON","subject":"Nora","subject_kind":"cognizer","predicate":"trusts","object":"ferry operator","modality":"BELIEVES","polarity":"POS","nesting_depth":0,"confidence":0.9,"evidence":{"clause_id":"c0","actor":"Nora","attributed_to":null,"assertion_scope":"ASSERTED","scope_markers":["ASSERTED"],"topic":"ferry operator","time_text":"","event_time":null}}]})";
    const auto parsed_claim = extractor::parse_claim_response(raw_claim, payload, "Nora");
    ASSERT_TRUE(parsed_claim.errors.empty());
    const auto extraction_prompt = extractor::claim_extraction_prompt(payload, "Nora");
    const auto admission_prompt = extractor::claim_admission_prompt(
        payload, extractor::claim_candidates_json(parsed_claim));
    extractor::FakeLLMAdapter llm;
    llm.set_response(crypto::sha256_hex(extraction_prompt),
                     extractor::LLMResponse{.raw_xml = raw_claim, .ok = true});
    llm.set_response(crypto::sha256_hex(admission_prompt), extractor::LLMResponse{
        .raw_xml = R"({"schema_version":1,"decisions":[{"index":0,"retain":true,"reason":"supported"}]})",
        .ok = true});
    extractor::ValidationPolicy policy;
    policy.semantic_claim_contract = true;
    policy.preserve_text_objects = true;
    const auto extracted = memoryops::extract_llm(*database, llm, "", params, policy);
    ASSERT_TRUE(extracted.failure_category.empty()) << extracted.failure_category;
    const auto committed = memoryops::remember_commit(
        *database, llm, params, prepared, extracted, policy);
    ASSERT_FALSE(committed.statement_ids.empty());
    ASSERT_TRUE(committed.structured_claims_persisted);
    store::SqliteStatementStore statement_store(database->connection());
    ASSERT_EQ(statement_store.mark_consolidated(
                  committed.statement_ids, "default", "closure-batch"), 1);

    retrieval::BasicRetriever basic(*database);
    retrieval::BasicRetrieverParams basic_params;
    basic_params.tenant_id = "default";
    basic_params.holder_id = "Nora";
    basic_params.subject_id = "Nora";
    basic_params.predicate = "trusts";
    basic_params.as_of_iso8601 = "2026-09-19T11:00:00Z";
    const auto basic_result = basic.run(basic_params);
    ASSERT_EQ(basic_result.rows.size(), 1u);

    retrieval::StructuredClaimRequest request;
    request.tenant_id = "default";
    request.holder_id = "Nora";
    request.subject_id = "Nora";
    request.predicate = "trusts";
    request.topic = "ferry operator";
    request.as_of_iso8601 = "2026-09-19T11:00:00Z";
    request.limit = 1;
    const auto view = retrieval::select_structured_claims(
        database->connection(), basic_result.rows, request);
    ASSERT_TRUE(view.sufficient) << view.receipt_json;
    ASSERT_EQ(view.selected.size(), 1u);
    EXPECT_EQ(view.selected.front().id, basic_result.rows.front().id);
    EXPECT_EQ(view.excluded_invalid_evidence, 0u);
}

}  // namespace
}  // namespace starling

#include "starling/extractor/claim_contract.hpp"
#include "starling/crypto/sha256.hpp"
#include "starling/extractor/fake_llm_adapter.hpp"
#include "starling/memory/memory_ops.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/retrieval/basic_retriever.hpp"
#include "starling/retrieval/structured_claim_retriever.hpp"
#include "starling/store/sqlite_statement_store.hpp"
#include <array>
#include <string>
#include <tuple>
#include <vector>
#include <gtest/gtest.h>
#include <nlohmann/json.hpp>

namespace starling::extractor {
namespace {
using Json = nlohmann::json;

Json claim_row(const std::string& predicate,
               const std::string& object,
               const std::string& modality,
               const std::string& time_text = "",
               const Json& topic = nullptr,
               const std::string& clause_id = "c0") {
    return {
        {"holder", "Ari"},
        {"holder_perspective", "FIRST_PERSON"},
        {"subject", "Ari"},
        {"subject_kind", "cognizer"},
        {"predicate", predicate},
        {"object", object},
        {"modality", modality},
        {"polarity", "POS"},
        {"nesting_depth", 0},
        {"confidence", nullptr},
        {"evidence", {
            {"clause_id", clause_id},
            {"actor", "Ari"},
            {"attributed_to", nullptr},
            {"assertion_scope", "ASSERTED"},
            {"scope_markers", Json::array({"ASSERTED"})},
            {"topic", topic},
            {"time_text", time_text},
            {"event_time", nullptr},
        }},
    };
}

std::string response_for(const Json& row) {
    return Json{{"schema_version", 2}, {"statements", Json::array({row})}}.dump();
}
}  // namespace

TEST(PredicateCoverageExpansion, NativeCatalogContainsLegacyMentalRelations) {
    const auto catalog = claim_predicate_catalog();
    EXPECT_EQ(catalog.version, "claim-predicate-v3");
    EXPECT_EQ(canonical_claim_predicate("wants"), "prefers");
    EXPECT_EQ(canonical_claim_predicate("commits_to"), "promises");
    EXPECT_EQ(canonical_claim_predicate("owns_area"), "responsible_for");
    EXPECT_NE(find_claim_predicate("requires"), nullptr);
    EXPECT_NE(find_claim_predicate("forbids"), nullptr);
}

TEST(PredicateCoverageExpansion, BilingualNewPredicatesKeepNativeModalityAndEvidence) {
    struct Case {
        const char* predicate;
        const char* object;
        const char* modality;
        const char* source;
        const char* time;
        const char* topic;
        const char* family;
        schema::Modality native_modality;
    };
    const std::vector<Case> cases = {
        {"prefers", "a quiet trail", "DESIRES", "Ari: I prefer a quiet trail.", "",
         "quiet trail", "preference", schema::Modality::DESIRES},
        {"promises", "send the map tomorrow", "COMMITS", "Ari: I promise to send the map tomorrow.", "tomorrow",
         "the map", "commitment", schema::Modality::COMMITS},
        {"doubts", "the forecast", "DOUBTS", "Ari: I doubt the forecast.", "",
         "the forecast", "epistemic_doubt", schema::Modality::DOUBTS},
        {"believes", "the guide is reliable", "BELIEVES", "Ari: I believe the guide is reliable.", "",
         "the guide", "belief", schema::Modality::BELIEVES},
        {"responsible_for", "route planning", "BELIEVES", "Ari: I am responsible for route planning.", "",
         "route planning", "responsibility", schema::Modality::BELIEVES},
        {"requires", "a permit", "NORM_OUGHT", "Ari: I require a permit.", "",
         "a permit", "norm_requirement", schema::Modality::NORM_OUGHT},
        {"forbids", "drones", "NORM_FORBID", "Ari: I forbid drones.", "",
         "drones", "norm_prohibition", schema::Modality::NORM_FORBID},
        {"prefers", "明天走安静的小径", "DESIRES", "Ari: 我偏好明天走安静的小径。", "明天",
         "安静的小径", "preference", schema::Modality::DESIRES},
        {"promises", "明天发送地图", "COMMITS", "Ari: 我承诺明天发送地图。", "明天",
         "地图", "commitment", schema::Modality::COMMITS},
        {"doubts", "今天的天气预报", "DOUBTS", "Ari: 我怀疑今天的天气预报。", "今天",
         "天气预报", "epistemic_doubt", schema::Modality::DOUBTS},
        {"believes", "向导今天能准时到达", "BELIEVES", "Ari: 我相信向导今天能准时到达。", "今天",
         "向导", "belief", schema::Modality::BELIEVES},
        {"responsible_for", "今天的路线规划", "BELIEVES", "Ari: 我负责今天的路线规划。", "今天",
         "路线规划", "responsibility", schema::Modality::BELIEVES},
        {"requires", "明天出发前取得许可证", "NORM_OUGHT", "Ari: 我要求明天出发前取得许可证。", "明天",
         "许可证", "norm_requirement", schema::Modality::NORM_OUGHT},
        {"forbids", "今天使用无人机", "NORM_FORBID", "Ari: 我禁止今天使用无人机。", "今天",
         "无人机", "norm_prohibition", schema::Modality::NORM_FORBID},
    };
    for (const auto& c : cases) {
        SCOPED_TRACE(c.source);
        const auto parsed = parse_claim_response(
            response_for(claim_row(c.predicate, c.object, c.modality, c.time, c.topic)),
            c.source, "Ari");
        ASSERT_TRUE(parsed.errors.empty());
        ASSERT_TRUE(parsed.semantic_rejections.empty());
        ASSERT_EQ(parsed.statements.size(), 1u);
        const auto& statement = parsed.statements.front();
        EXPECT_EQ(statement.subject_id, "Ari");
        EXPECT_EQ(statement.holder_perspective, schema::Perspective::FIRST_PERSON);
        EXPECT_EQ(statement.predicate, c.predicate);
        EXPECT_EQ(statement.object_value, c.object);
        EXPECT_EQ(statement.modality, c.native_modality);
        const auto evidence = Json::parse(statement.semantic_claim_json);
        EXPECT_EQ(evidence.at("actor"), "Ari");
        EXPECT_EQ(evidence.at("topic"), c.topic);
        EXPECT_EQ(evidence.at("time_text"), c.time);
        EXPECT_TRUE(evidence.at("event_time").is_null());
        EXPECT_EQ(evidence.at("relation_modality"), c.modality);
        EXPECT_EQ(evidence.at("semantic_family"), c.family);
        EXPECT_EQ(evidence.at("predicate_catalog_version"), "claim-predicate-v3");
        EXPECT_EQ(evidence.at("source_span").at("span_start"), 0);
        EXPECT_EQ(evidence.at("source_span").at("span_end"), std::string(c.source).size());
        EXPECT_EQ(evidence.at("source_span").at("source_hash"), crypto::sha256_hex(c.source));
    }
}

TEST(PredicateCoverageExpansion, WrongModalityIsRejectedByTheNativeCatalog) {
    const std::vector<std::tuple<std::string, std::string, std::string, std::string>> cases = {
        {"prefers", "a quiet trail", "BELIEVES", "Ari: I prefer a quiet trail."},
        {"promises", "send the map", "INTENDS", "Ari: I promise to send the map."},
        {"doubts", "the forecast", "BELIEVES", "Ari: I doubt the forecast."},
        {"believes", "the guide is reliable", "DOUBTS", "Ari: I believe the guide is reliable."},
        {"responsible_for", "route planning", "DESIRES", "Ari: I am responsible for route planning."},
        {"requires", "a permit", "BELIEVES", "Ari: I require a permit."},
        {"forbids", "drones", "NORM_OUGHT", "Ari: I forbid drones."},
    };
    for (const auto& c : cases) {
        SCOPED_TRACE(std::get<0>(c));
        const auto row = claim_row(std::get<0>(c), std::get<1>(c), std::get<2>(c));
        const auto parsed = parse_claim_response(response_for(row), std::get<3>(c), "Ari");
        EXPECT_TRUE(parsed.statements.empty());
        EXPECT_TRUE(parsed.errors.empty());
        ASSERT_EQ(parsed.semantic_rejections.size(), 1u);
        const auto& rejection = parsed.semantic_rejections.front();
        EXPECT_EQ(rejection.index, 0u);
        EXPECT_EQ(rejection.predicate, std::get<0>(c));
        EXPECT_EQ(rejection.kind, "scope_failure");
        EXPECT_EQ(rejection.detail, "predicate/modality mismatch");
    }
}

TEST(PredicateCoverageExpansion, MixedAdmissionCountsCanonicalPredicatesAndSurvivesStoredRetrieval) {
    const std::array<std::string, 3> source_lines = {
        "Ari: I prefer the quiet trail.",
        "Ari: I promise to send the map tomorrow.",
        "Ari: I feel relieved about the route.",
    };
    const std::string payload = source_lines[0] + "\n" + source_lines[1] + "\n" + source_lines[2];
    const std::array<std::string, 3> predicates = {"prefers", "promises", "feels"};
    const std::array<std::string, 3> objects = {
        "the quiet trail", "send the map tomorrow", "relieved about the route"};
    const std::array<std::string, 3> topics = {"quiet trail", "the map", "the route"};
    const std::array<std::string, 3> modalities = {"DESIRES", "COMMITS", "BELIEVES"};
    const std::array<std::string, 2> families = {"preference", "commitment"};
    const std::array<std::string, 2> stored_modalities = {"desires", "commits"};
    const std::array<std::string, 2> times = {"", "tomorrow"};
    const std::string raw_claims = Json{{"schema_version", 2}, {"statements", Json::array({
        claim_row("wants", objects[0], modalities[0], times[0], topics[0], "c0"),
        claim_row("commits_to", objects[1], modalities[1], times[1], topics[1], "c1"),
        claim_row("feels", objects[2], modalities[2], "", topics[2], "c2"),
    })}}.dump();
    const auto candidates = parse_claim_response(raw_claims, payload, "Ari");
    ASSERT_TRUE(candidates.errors.empty());
    ASSERT_TRUE(candidates.semantic_rejections.empty());
    ASSERT_EQ(candidates.statements.size(), 3u);

    // Each run rejects two candidates, retaining a different new predicate.
    // Scripted admission decisions exercise filtering; they are not model judgments.
    for (std::size_t retained_index = 0; retained_index < 2; ++retained_index) {
        SCOPED_TRACE(predicates[retained_index]);
        const auto database = persistence::SqliteAdapter::open(":memory:");
        persistence::MigrationRunner(database->connection().raw()).migrate_to_latest();
        memoryops::RememberParams params;
        params.tenant_id = "default";
        params.holder_id = "Ari";
        params.adapter_name = "predicate-expansion-test";
        params.source_prefix = "predicate-expansion-";
        params.created_at_iso8601 = "2026-09-20T10:00:00Z";
        params.payload.assign(payload.begin(), payload.end());
        const auto prepared = memoryops::remember_prepare(*database, params);
        ASSERT_TRUE(prepared.should_extract);
        ASSERT_FALSE(prepared.engram_ref.empty());

        Json decisions = Json::array();
        Json expected_rejected = Json::object();
        for (std::size_t index = 0; index < predicates.size(); ++index) {
            const bool retain = index == retained_index;
            decisions.push_back({{"index", index}, {"retain", retain},
                                 {"reason", retain ? "supported" : "unsupported"}});
            if (!retain) expected_rejected[predicates[index]] = 1;
        }
        const Json expected_accepted = {{predicates[retained_index], 1}};
        FakeLLMAdapter llm;
        const auto extraction_prompt = claim_extraction_prompt(payload, "Ari");
        const auto admission_prompt = claim_admission_prompt(payload, claim_candidates_json(candidates));
        llm.set_response(crypto::sha256_hex(extraction_prompt),
                         LLMResponse{.raw_xml = raw_claims, .ok = true});
        llm.set_response(crypto::sha256_hex(admission_prompt), LLMResponse{
            .raw_xml = Json{{"schema_version", 1}, {"decisions", decisions}}.dump(), .ok = true});
        ValidationPolicy policy;
        policy.semantic_claim_contract = true;
        policy.preserve_text_objects = true;

        const auto extracted = memoryops::extract_llm(*database, llm, "", params, policy);
        EXPECT_EQ(extracted.failure_category, "semantic_rejection");
        const auto receipt = Json::parse(claim_extraction_receipt(extracted));
        EXPECT_EQ(receipt.at("catalog_version"), "claim-predicate-v3");
        EXPECT_EQ(receipt.at("accepted_by_predicate"), expected_accepted);
        EXPECT_EQ(receipt.at("rejected_by_predicate"), expected_rejected);
        ASSERT_EQ(receipt.at("attempts").size(), 1u);
        const auto& attempt = receipt.at("attempts").front();
        EXPECT_TRUE(attempt.at("errors").empty());
        EXPECT_TRUE(attempt.at("semantic_rejections").empty());
        EXPECT_EQ(attempt.at("semantic_rejected"), 2);
        EXPECT_TRUE(attempt.at("admission").at("called").get<bool>());
        EXPECT_EQ(attempt.at("admission").at("semantic_rejected"), 2);
        EXPECT_EQ(attempt.at("admission").at("rejected_by_predicate"), expected_rejected);
        ASSERT_EQ(attempt.at("retained").size(), 1u);
        EXPECT_EQ(attempt.at("retained").front().at("predicate"), predicates[retained_index]);

        const auto committed = memoryops::remember_commit(
            *database, llm, params, prepared, extracted, policy);
        ASSERT_FALSE(committed.extraction_failed) << committed.failure_category;
        EXPECT_EQ(committed.failure_category, "semantic_rejection");
        ASSERT_TRUE(committed.source_preserved);
        ASSERT_TRUE(committed.structured_claims_persisted);
        ASSERT_EQ(committed.statement_ids.size(), 1u);
        EXPECT_EQ(committed.catalog_version, "claim-predicate-v3");
        EXPECT_EQ(Json(committed.accepted_by_predicate), expected_accepted);
        EXPECT_EQ(Json(committed.rejected_by_predicate), expected_rejected);
        store::SqliteStatementStore statement_store(database->connection());
        ASSERT_EQ(statement_store.mark_consolidated(
            committed.statement_ids, "default", "predicate-expansion-batch"), 1);

        retrieval::BasicRetriever basic(*database);
        retrieval::BasicRetrieverParams basic_params;
        basic_params.tenant_id = "default";
        basic_params.holder_id = "Ari";
        basic_params.subject_id = "Ari";
        basic_params.predicate = predicates[retained_index];
        basic_params.as_of_iso8601 = "2026-09-20T11:00:00Z";
        const auto read_back = basic.run(basic_params);
        ASSERT_EQ(read_back.rows.size(), 1u);
        for (std::size_t index = 0; index < predicates.size(); ++index) {
            if (index == retained_index) continue;
            auto rejected_params = basic_params;
            rejected_params.predicate = predicates[index];
            EXPECT_TRUE(basic.run(rejected_params).rows.empty()) << predicates[index];
        }

        retrieval::StructuredClaimRequest request;
        request.tenant_id = "default";
        request.holder_id = "Ari";
        request.subject_id = "Ari";
        request.predicate = predicates[retained_index];
        request.topic = topics[retained_index];
        request.as_of_iso8601 = basic_params.as_of_iso8601;
        request.limit = 1;
        const auto view = retrieval::select_structured_claims(
            database->connection(), read_back.rows, request);
        ASSERT_TRUE(view.sufficient) << view.receipt_json;
        ASSERT_EQ(view.selected.size(), 1u);
        EXPECT_EQ(view.excluded_invalid_evidence, 0u);
        const auto& stored = view.selected.front();
        EXPECT_EQ(stored.id, committed.statement_ids.front());
        EXPECT_EQ(stored.subject_id, "Ari");
        EXPECT_EQ(stored.predicate, predicates[retained_index]);
        EXPECT_EQ(stored.modality, stored_modalities[retained_index]);
        EXPECT_EQ(stored.object_value, objects[retained_index]);
        const auto evidence = Json::parse(stored.semantic_claim_json);
        EXPECT_EQ(evidence.at("semantic_family"), families[retained_index]);
        EXPECT_EQ(evidence.at("predicate_catalog_version"), "claim-predicate-v3");
        EXPECT_EQ(evidence.at("relation_modality"), modalities[retained_index]);
        EXPECT_EQ(evidence.at("topic"), topics[retained_index]);
        EXPECT_EQ(evidence.at("time_text"), times[retained_index]);
        EXPECT_TRUE(evidence.at("event_time").is_null());
        const auto& span = evidence.at("source_span");
        const auto expected_start = payload.find(source_lines[retained_index]);
        EXPECT_EQ(span.at("engram_ref"), prepared.engram_ref);
        EXPECT_EQ(span.at("span_start"), expected_start);
        EXPECT_EQ(span.at("span_end"), expected_start + source_lines[retained_index].size());
        EXPECT_EQ(span.at("source_hash"), crypto::sha256_hex(payload));
        auto expected_persisted_span = span;
        expected_persisted_span["chunk_index"] = 0;
        expected_persisted_span["observed_at"] = params.created_at_iso8601;
        EXPECT_EQ(Json::parse(stored.source_spans_json), Json::array({expected_persisted_span}));
    }
}

TEST(PredicateCoverageExpansion, KnowsAcceptsHistoricalAndNativeModalities) {
    for (const auto modality : {"BELIEVES", "KNOWS"}) {
        const auto parsed = parse_claim_response(
            response_for(claim_row("knows", "the route", modality)),
            "Ari: I know the route.", "Ari");
        ASSERT_TRUE(parsed.errors.empty()) << modality;
        ASSERT_EQ(parsed.statements.size(), 1u) << modality;
        EXPECT_EQ(parsed.statements.front().predicate, "knows");
    }
}

TEST(PredicateCoverageExpansion, PromptsShareTheNativeExpandedCatalog) {
    const auto extraction = claim_extraction_prompt("Ari: I prefer a quiet trail.", "Ari");
    const auto admission = claim_admission_prompt(
        "Ari: I prefer a quiet trail.",
        Json{{"schema_version", 2}, {"statements", Json::array({
            claim_row("prefers", "a quiet trail", "DESIRES")
        })}}.dump());
    for (const auto* token : {"prefers", "promises", "doubts", "believes",
                              "responsible_for", "requires", "forbids",
                              "DESIRES", "COMMITS", "DOUBTS", "NORM_OUGHT",
                              "NORM_FORBID"}) {
        EXPECT_NE(extraction.find(token), std::string::npos) << token;
        EXPECT_NE(admission.find(token), std::string::npos) << token;
    }
    for (const auto* forbidden : {"SocialMemBench", "Josh", "Marcus", "gold answer"}) {
        EXPECT_EQ(extraction.find(forbidden), std::string::npos) << forbidden;
        EXPECT_EQ(admission.find(forbidden), std::string::npos) << forbidden;
    }
}

}  // namespace starling::extractor

#include "starling/extractor/structured_output.hpp"
#include "starling/extractor/claim_contract.hpp"
#include "starling/extractor/fake_llm_adapter.hpp"
#include "starling/crypto/sha256.hpp"
#include <gtest/gtest.h>
#include <nlohmann/json.hpp>

namespace starling::extractor {
namespace {
using Json = nlohmann::json;

struct LegacyAdapter : LLMAdapter {
    int calls = 0;
    LLMResponse extract(std::string_view, std::string_view) override {
        ++calls; return {.raw_xml="[]", .ok=true};
    }
};
void strict_objects(const nlohmann::json& schema) {
    if (schema.is_object() && schema.value("type", nlohmann::json()) == "object") {
        EXPECT_EQ(schema.at("additionalProperties"), false);
        ASSERT_TRUE(schema.contains("required"));
        EXPECT_EQ(schema.at("required").size(), schema.at("properties").size());
    }
    if (schema.is_object() || schema.is_array()) for (const auto& value : schema) {
        if (value.is_object() || value.is_array()) strict_objects(value);
    }
}

Json extraction_row() {
    return {{"holder","Mina"},{"holder_perspective","FIRST_PERSON"},
        {"subject","Mina"},{"subject_kind","cognizer"},{"predicate","feels"},
        {"object","sad about leaving the team"},{"modality","BELIEVES"},{"polarity","POS"},
        {"nesting_depth",0},{"confidence",nullptr},{"evidence",{{"clause_id","c0"},{"actor","Mina"},
        {"attributed_to",nullptr},{"assertion_scope","ASSERTED"},{"scope_markers",Json::array({"ASSERTED"})},
        {"time_text",""},{"topic","leaving the team"},{"event_time",nullptr}}}};
}

std::string extraction_response(Json row) {
    return Json{{"schema_version",2},{"statements",Json::array({std::move(row)})}}.dump();
}
}
TEST(StructuredOutput, LegacyAdaptersNeverSilentlyDropTypedConstraints) {
    LegacyAdapter adapter;
    EXPECT_TRUE(adapter.extract_with_contract("x", "hash", {}).ok);
    EXPECT_EQ(adapter.calls, 1);
    const auto unsupported = adapter.extract_with_contract("x", "hash", {OutputContractKind::ClaimAdmissionV1, OutputMode::JsonSchemaStrict});
    EXPECT_FALSE(unsupported.ok);
    EXPECT_EQ(unsupported.error, "structured_output_unsupported");
    EXPECT_EQ(adapter.calls, 1);
}
TEST(StructuredOutput, SourceSelectionSchemaEnforcesBoundedPositiveUniqueIntegers) {
    const auto kind=OutputContractKind::SourceSelectionV1;
    EXPECT_EQ(to_string(kind),"source_selection_v1");
    EXPECT_EQ(structured_output_validation_error(R"({"source_ids":[]})",kind),"");
    EXPECT_EQ(structured_output_validation_error(R"({"source_ids":[3,1]})",kind),"");
    for(const auto* raw:{R"({"source_ids":[true]})",R"({"source_ids":[0]})",
        R"({"source_ids":[1.0]})",R"({"source_ids":[1,1]})",R"({"source_ids":[1],"answer":"x"})",
        R"({"source_ids":[],"source_ids":[1]})","```json\n{\"source_ids\":[]}\n```"})
        EXPECT_FALSE(structured_output_validation_error(raw,kind).empty())<<raw;
    Json ids=Json::array();for(int i=1;i<=20;++i)ids.push_back(i);
    EXPECT_EQ(structured_output_validation_error(Json{{"source_ids",ids}}.dump(),kind),"");
    ids.push_back(21);
    EXPECT_EQ(structured_output_validation_error(Json{{"source_ids",ids}}.dump(),kind),"schema_failure:maxItems");
}
TEST(StructuredOutput, SchemasKeepNullableFieldsAndWidePrecheckEnums) {
    const auto extraction = nlohmann::json::parse(structured_output_schema(OutputContractKind::ClaimExtractionV2));
    const auto admission = nlohmann::json::parse(structured_output_schema(OutputContractKind::ClaimAdmissionV1));
    strict_objects(extraction); strict_objects(admission);
    const auto& fields = extraction.at("properties").at("statements").at("items").at("properties");
    EXPECT_EQ(fields.at("confidence").at("type"), nlohmann::json::array({"number", "null"}));
    EXPECT_EQ(fields.at("holder_perspective").at("enum").size(), 4u);
    EXPECT_EQ(fields.at("polarity").at("enum").size(), 3u);
    EXPECT_EQ(fields.at("subject_kind").at("enum").size(), 2u);
    EXPECT_FALSE(fields.at("evidence").at("properties").contains("source_turn"));
    const auto& scope_markers=fields.at("evidence").at("properties").at("scope_markers");
    EXPECT_EQ(scope_markers.at("minItems"), 1);
    EXPECT_EQ(scope_markers.at("uniqueItems"), true);
    EXPECT_NE(extraction, admission);
    EXPECT_EQ(structured_output_schema_sha256(OutputContractKind::ClaimExtractionV2), crypto::sha256_hex(extraction.dump()));
}
TEST(StructuredOutput, EveryExtractionReferenceResponseSatisfiesItsWireSchema) {
    const auto prompt = claim_extraction_prompt("Nora: I feel cheerful about the community picnic.", "Nora");
    const std::string marker = "REFERENCE_EXAMPLES_JSON:\n";
    const auto start = prompt.find(marker);
    ASSERT_NE(start, std::string::npos);
    const auto end = prompt.find("\nSOURCE_DATA_JSON:", start);
    ASSERT_NE(end, std::string::npos);
    const auto examples = nlohmann::json::parse(prompt.substr(start + marker.size(), end - start - marker.size()));
    ASSERT_FALSE(examples.empty());
    for (const auto& example : examples) {
        SCOPED_TRACE(example.at("source").get<std::string>());
        EXPECT_EQ(structured_output_validation_error(example.at("response").dump(),
            OutputContractKind::ClaimExtractionV2), "");
    }
}
TEST(StructuredOutput, WireSchemaRejectsEmptyScopeMarkers) {
    auto row=extraction_row();
    row["evidence"]["scope_markers"]=Json::array();
    EXPECT_EQ(structured_output_validation_error(extraction_response(std::move(row)),
        OutputContractKind::ClaimExtractionV2), "schema_failure:minItems");
}
TEST(StructuredOutput, WireSchemaRejectsDuplicateScopeMarkers) {
    auto row=extraction_row();
    row["evidence"]["scope_markers"]=Json::array({"ASSERTED","ASSERTED"});
    EXPECT_EQ(structured_output_validation_error(extraction_response(std::move(row)),
        OutputContractKind::ClaimExtractionV2), "schema_failure:uniqueItems");
}
TEST(StructuredOutput, WireSchemaAcceptsCombinedDistinctScopeMarkers) {
    auto row=extraction_row();
    row["holder_perspective"]="QUOTED";
    row["subject"]="Jules";
    row["polarity"]="NEG";
    row["evidence"]["actor"]="Jules";
    row["evidence"]["attributed_to"]="Mina";
    row["evidence"]["assertion_scope"]="CONDITIONAL";
    row["evidence"]["scope_markers"]=Json::array({"CONDITIONAL","REPORTED","NEGATED"});
    EXPECT_EQ(structured_output_validation_error(extraction_response(std::move(row)),
        OutputContractKind::ClaimExtractionV2), "");
}
TEST(StructuredOutput, WireSchemaAcceptsEmptyStatements) {
    EXPECT_EQ(structured_output_validation_error(R"({"schema_version":2,"statements":[]})",
        OutputContractKind::ClaimExtractionV2), "");
}
TEST(StructuredOutput, NativeParserKeepsPrimaryScopeMembershipOutsideWireSchema) {
    auto row=extraction_row();
    row["evidence"]["scope_markers"]=Json::array({"REPORTED"});
    const auto raw=extraction_response(std::move(row));
    EXPECT_EQ(structured_output_validation_error(raw,OutputContractKind::ClaimExtractionV2), "");
    const auto parsed=parse_claim_response(raw,"Mina: I am sad about leaving the team.","Mina",false);
    EXPECT_FALSE(parsed.errors.empty());
    EXPECT_TRUE(parsed.statements.empty());
}
TEST(StructuredOutput, FakeReplayRecordsTypedRequestsWithoutContentRepair) {
    FakeLLMAdapter adapter;
    adapter.set_default_response({.raw_xml="```json\n{}\n``` explanation", .ok=true});
    const auto result = adapter.extract_with_contract("JSON", "hash", {OutputContractKind::ClaimExtractionV2, OutputMode::JsonObject});
    EXPECT_EQ(result.raw_xml, "```json\n{}\n``` explanation");
    EXPECT_EQ(result.raw_completion, result.raw_xml);
    EXPECT_EQ(result.output_mode, OutputMode::JsonObject);
    ASSERT_EQ(adapter.structured_requests().size(), 1u);
    EXPECT_EQ(adapter.structured_requests()[0].contract, OutputContractKind::ClaimExtractionV2);
}
}

namespace starling::extractor {
TEST(StructuredOutput, FakeReplayKeepsFailedCompletionSeparateFromSuccessField) {
    FakeLLMAdapter adapter;
    LLMResponse original;
    original.error="completion_truncated";
    original.raw_completion="{\"schema_version\":2,";
    original.raw_http_response="original provider envelope";
    adapter.set_default_response(original);
    const auto response=adapter.extract_with_contract("JSON","hash",{OutputContractKind::ClaimExtractionV2,OutputMode::JsonSchemaStrict});
    EXPECT_FALSE(response.ok); EXPECT_TRUE(response.raw_xml.empty());
    EXPECT_EQ(response.raw_completion,original.raw_completion);
    EXPECT_EQ(response.raw_http_response,original.raw_http_response);
}
}

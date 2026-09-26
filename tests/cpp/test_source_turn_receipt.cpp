#include "starling/extractor/episodic_extractor.hpp"
#include "starling/memory/memory_ops.hpp"

#include <gtest/gtest.h>
#include <nlohmann/json.hpp>

namespace starling {
namespace {

using Json = nlohmann::json;

TEST(SourceTurnReceipt, BundleReceiptSeparatesAllNativeChannels) {
    memoryops::RememberLlmBundle bundle;
    bundle.belief.prompt_body = "belief prompt";
    bundle.belief.prompt_input_hash = "belief-hash";
    extractor::ExtractionLlmAttempt belief_attempt;
    belief_attempt.attempt = 1;
    belief_attempt.terminal = true;
    belief_attempt.resp = {.raw_xml = R"({"schema_version":2,"statements":[]})", .ok = true};
    bundle.belief.attempts.push_back(belief_attempt);

    bundle.general_fact.prompt_body = "general prompt";
    bundle.general_fact.prompt_input_hash = "general-hash";
    extractor::ExtractionLlmAttempt fact_attempt;
    fact_attempt.attempt = 1;
    fact_attempt.terminal = true;
    fact_attempt.resp = {.raw_xml = R"({"schema_version":2,"statements":[]})", .ok = true};
    bundle.general_fact.attempts.push_back(fact_attempt);

    bundle.episodic.prompt_body = "episodic prompt";
    bundle.episodic.prompt_input_hash = "episodic-hash";
    bundle.episodic.response = {.raw_xml = R"([{"actor":"Mina","action":"visited","theme":"park"}])", .ok = true};
    bundle.episodic.ok = true;

    const auto receipt = Json::parse(memoryops::remember_bundle_receipt(bundle));
    ASSERT_EQ(receipt["schema_version"], 1);
    ASSERT_TRUE(receipt["channels"].is_object());
    EXPECT_TRUE(receipt["channels"].contains("belief"));
    EXPECT_TRUE(receipt["channels"].contains("general_fact"));
    EXPECT_TRUE(receipt["channels"].contains("episodic"));
    EXPECT_EQ(receipt["channels"]["belief"]["attempts"][0]["extraction"]["raw_response"].get<std::string>(),
              R"({"schema_version":2,"statements":[]})");
    EXPECT_EQ(receipt["channels"]["general_fact"]["prompt_input_hash"].get<std::string>(), "general-hash");
    EXPECT_EQ(receipt["channels"]["episodic"]["response"]["raw_xml"].get<std::string>(),
              R"([{"actor":"Mina","action":"visited","theme":"park"}])");
    EXPECT_EQ(receipt["channels"]["episodic"]["event_count"], 0);
}

} // namespace
} // namespace starling

// #38-C Phase 3 — NORM-gist prompt build + LLM judgment parse (pure, no DB).
#include "starling/replay/gist_prompt.hpp"
#include "starling/replay/gist_clustering.hpp"
#include <gtest/gtest.h>
#include <string>

using namespace starling::replay;

namespace {
GistCluster sample_cluster() {
    GistCluster cluster;
    cluster.predicate = "likes";
    cluster.canonical_object_hash = std::string(64, 'a');
    cluster.object_kind = "str";
    cluster.object_value = "coffee";
    cluster.member_ids = {"m1", "m2", "m3"};
    cluster.holder_ids = {"alice", "bob", "carol"};
    return cluster;
}
}  // namespace

// The prompt embeds the candidate norm: predicate, object, holder count + ids.
TEST(GistPrompt, BuildFillsClusterContext) {
    const std::string prompt = build_norm_gist_prompt(sample_cluster());
    EXPECT_NE(prompt.find("likes"), std::string::npos);
    EXPECT_NE(prompt.find("coffee"), std::string::npos);
    EXPECT_NE(prompt.find("3 distinct holders"), std::string::npos);
    EXPECT_NE(prompt.find("alice, bob, carol"), std::string::npos);
    EXPECT_EQ(prompt.find("{predicate}"), std::string::npos);  // no leftover placeholder
}

TEST(GistPrompt, ParsesWellFormedJudgment) {
    const auto judgment =
        parse_gist_judgment(R"({"confidence": 0.82, "summary": "People generally like coffee."})");
    EXPECT_TRUE(judgment.ok);
    EXPECT_DOUBLE_EQ(judgment.confidence, 0.82);
    EXPECT_EQ(judgment.summary, "People generally like coffee.");
}

// Tolerate markdown fences / surrounding prose around the JSON object.
TEST(GistPrompt, ParsesFencedJudgment) {
    const auto judgment = parse_gist_judgment(
        "Here is my answer:\n```json\n{\"confidence\": 0.4, \"summary\": \"x\"}\n```\n");
    EXPECT_TRUE(judgment.ok);
    EXPECT_DOUBLE_EQ(judgment.confidence, 0.4);
}

// Summary is optional; confidence is mandatory.
TEST(GistPrompt, SummaryOptionalConfidenceMandatory) {
    const auto no_summary = parse_gist_judgment(R"({"confidence": 0.5})");
    EXPECT_TRUE(no_summary.ok);
    EXPECT_TRUE(no_summary.summary.empty());

    const auto no_conf = parse_gist_judgment(R"({"summary": "x"})");
    EXPECT_FALSE(no_conf.ok);
}

TEST(GistPrompt, RejectsNonNumberConfidenceAndGarbage) {
    EXPECT_FALSE(parse_gist_judgment(R"({"confidence": "high"})").ok);
    EXPECT_FALSE(parse_gist_judgment("not json at all").ok);
    EXPECT_FALSE(parse_gist_judgment("").ok);
}

// Out-of-[0,1] confidence is treated as unparseable (skip), so a misbehaving
// adapter is not retried every cycle.
TEST(GistPrompt, RejectsOutOfRangeConfidence) {
    EXPECT_FALSE(parse_gist_judgment(R"({"confidence": 1.5})").ok);
    EXPECT_FALSE(parse_gist_judgment(R"({"confidence": -0.2})").ok);
    EXPECT_TRUE(parse_gist_judgment(R"({"confidence": 0.0})").ok);   // boundary ok
    EXPECT_TRUE(parse_gist_judgment(R"({"confidence": 1.0})").ok);   // boundary ok
}

// --- Phase 4: entailment verification prompt + verdict parse ---

TEST(GistPrompt, BuildEntailmentFillsContext) {
    const std::string prompt =
        build_entailment_prompt(sample_cluster(), "coffee", "People like coffee.");
    EXPECT_NE(prompt.find("likes"), std::string::npos);
    EXPECT_NE(prompt.find("coffee"), std::string::npos);
    EXPECT_NE(prompt.find("People like coffee."), std::string::npos);
    EXPECT_EQ(prompt.find("{summary}"), std::string::npos);       // no leftover placeholder
    EXPECT_EQ(prompt.find("{holder_count}"), std::string::npos);  // both occurrences filled
}

TEST(GistPrompt, ParsesEntailmentVerdict) {
    const auto yes = parse_entailment_verdict(R"({"entailed": true})");
    EXPECT_TRUE(yes.ok);
    EXPECT_TRUE(yes.entailed);
    const auto no = parse_entailment_verdict(R"(```json
{"entailed": false}
```)");
    EXPECT_TRUE(no.ok);
    EXPECT_FALSE(no.entailed);
}

TEST(GistPrompt, RejectsMalformedVerdict) {
    EXPECT_FALSE(parse_entailment_verdict(R"({"entailed": "yes"})").ok);  // not a bool
    EXPECT_FALSE(parse_entailment_verdict(R"({"foo": 1})").ok);           // missing field
    EXPECT_FALSE(parse_entailment_verdict("garbage").ok);
}

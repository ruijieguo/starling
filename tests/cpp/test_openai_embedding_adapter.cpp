// tests/cpp/test_openai_embedding_adapter.cpp
#include "starling/embedding/openai_embedding_adapter.hpp"
#include <gtest/gtest.h>
#include <cstdlib>
#include <nlohmann/json.hpp>
#include <string>
#include <vector>
#include <utility>
using namespace starling::embedding;

TEST(OpenAIEmbeddingAdapter, FromEnvThrowsWithoutKey) {
    unsetenv("OPENAI_API_KEY");
    EXPECT_THROW(OpenAIEmbeddingAdapter::Config::from_env(), std::runtime_error);
}
TEST(OpenAIEmbeddingAdapter, FromEnvReadsModelAndKey) {
    setenv("OPENAI_API_KEY", "sk-test", 1);
    setenv("EMBEDDING_MODEL", "text-embedding-3-large", 1);
    auto c = OpenAIEmbeddingAdapter::Config::from_env();
    EXPECT_EQ(c.api_key, "sk-test");
    EXPECT_EQ(c.model, "text-embedding-3-large");
    unsetenv("OPENAI_API_KEY"); unsetenv("EMBEDDING_MODEL");
}
TEST(OpenAIEmbeddingBatch, BuildRequestEmitsInputArray) {
    const std::string body =
        OpenAIEmbeddingAdapter::build_embeddings_request("text-embedding-3-small",
                                                         {"alpha", "beta"});
    auto j = nlohmann::json::parse(body);
    EXPECT_EQ(j.at("model"), "text-embedding-3-small");
    ASSERT_TRUE(j.at("input").is_array());
    ASSERT_EQ(j.at("input").size(), 2u);
    EXPECT_EQ(j.at("input")[0], "alpha");
    EXPECT_EQ(j.at("input")[1], "beta");
}
TEST(OpenAIEmbeddingBatch, ParseReordersByIndex) {
    const std::string body = R"({"data":[
        {"index":1,"embedding":[1.0,1.0]},
        {"index":0,"embedding":[0.0,0.0]}
    ]})";
    auto vecs = OpenAIEmbeddingAdapter::parse_embeddings_batch(body, 2, /*dim=*/0);
    ASSERT_EQ(vecs.size(), 2u);
    EXPECT_FLOAT_EQ(vecs[0][0], 0.0f);  // index 0 first
    EXPECT_FLOAT_EQ(vecs[1][0], 1.0f);  // index 1 second
}
TEST(OpenAIEmbeddingBatch, ParseMissingDataThrows) {
    EXPECT_THROW(OpenAIEmbeddingAdapter::parse_embeddings_batch("{}", 1, 0),
                 std::runtime_error);
}
TEST(OpenAIEmbeddingBatch, ParseNegativeCountThrows) {
    // Defensive: a negative expected_count must not attempt a huge allocation.
    EXPECT_THROW(OpenAIEmbeddingAdapter::parse_embeddings_batch("{}", -1, 0),
                 std::runtime_error);
}
TEST(OpenAIEmbeddingBatch, ParseCountMismatchThrows) {
    const std::string body = R"({"data":[{"index":0,"embedding":[0.0]}]})";
    EXPECT_THROW(OpenAIEmbeddingAdapter::parse_embeddings_batch(body, 2, 0),
                 std::runtime_error);
}
TEST(OpenAIEmbeddingBatch, ParseDuplicateIndexThrows) {
    const std::string body = R"({"data":[
        {"index":0,"embedding":[0.0]},
        {"index":0,"embedding":[1.0]}
    ]})";
    EXPECT_THROW(OpenAIEmbeddingAdapter::parse_embeddings_batch(body, 2, 0),
                 std::runtime_error);
}
TEST(OpenAIEmbeddingBatch, ParseWrongDimThrows) {
    // expected_dim=2 but the embedding has length 1 → malformed.
    const std::string body = R"({"data":[{"index":0,"embedding":[0.0]}]})";
    EXPECT_THROW(OpenAIEmbeddingAdapter::parse_embeddings_batch(body, 1, /*dim=*/2),
                 std::runtime_error);
}
TEST(OpenAIEmbeddingBatch, ChunkRangesSplitsToMax) {
    auto r = OpenAIEmbeddingAdapter::chunk_ranges(32, 25);
    ASSERT_EQ(r.size(), 2u);
    EXPECT_EQ(r[0], std::make_pair(std::size_t{0}, std::size_t{25}));
    EXPECT_EQ(r[1], std::make_pair(std::size_t{25}, std::size_t{32}));
}
TEST(OpenAIEmbeddingBatch, ChunkRangesSingleWhenUnderMax) {
    auto r = OpenAIEmbeddingAdapter::chunk_ranges(5, 25);
    ASSERT_EQ(r.size(), 1u);
    EXPECT_EQ(r[0], std::make_pair(std::size_t{0}, std::size_t{5}));
}
TEST(OpenAIEmbeddingBatch, ChunkRangesEmptyAndClamp) {
    EXPECT_TRUE(OpenAIEmbeddingAdapter::chunk_ranges(0, 25).empty());
    EXPECT_EQ(OpenAIEmbeddingAdapter::chunk_ranges(3, 0).size(), 3u);  // clamp step→1
}
TEST(OpenAIEmbeddingAdapter, FromEnvReadsMaxBatch) {
    setenv("OPENAI_API_KEY", "sk-test", 1);
    setenv("EMBEDDING_MAX_BATCH", "10", 1);
    auto c = OpenAIEmbeddingAdapter::Config::from_env();
    EXPECT_EQ(c.max_batch_inputs, 10);
    unsetenv("OPENAI_API_KEY"); unsetenv("EMBEDDING_MAX_BATCH");
}
TEST(OpenAIEmbeddingAdapter, FromEnvDefaultMaxBatch) {
    setenv("OPENAI_API_KEY", "sk-test", 1);
    unsetenv("EMBEDDING_MAX_BATCH");
    auto c = OpenAIEmbeddingAdapter::Config::from_env();
    EXPECT_EQ(c.max_batch_inputs, 25);
    unsetenv("OPENAI_API_KEY");
}

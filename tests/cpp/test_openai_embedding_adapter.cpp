// tests/cpp/test_openai_embedding_adapter.cpp
#include "starling/embedding/openai_embedding_adapter.hpp"
#include <gtest/gtest.h>
#include <cstdlib>
#include <nlohmann/json.hpp>
#include <string>
#include <vector>
#include <utility>
#include <thread>
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
    EXPECT_EQ(c.max_batch_inputs, 10);
    unsetenv("OPENAI_API_KEY");
}

TEST(OpenAIEmbeddingAdapter, CountersSeparateApiCallsFromEmptyBatchAndRetries) {
    OpenAIEmbeddingAdapter::Config cfg;
    cfg.base_url = "http://127.0.0.1:1/v1";
    cfg.timeout_ms = 100;
    cfg.max_retries = 1;
    OpenAIEmbeddingAdapter adapter(cfg);
    EXPECT_EQ(adapter.request_count(), 0);
    EXPECT_TRUE(adapter.embed_batch({}).empty());
    EXPECT_EQ(adapter.batch_calls(), 1);
    EXPECT_EQ(adapter.request_count(), 0);  // Empty batch performs no curl request.
    EXPECT_THROW(adapter.embed("local connection failure"), EmbeddingError);
    EXPECT_EQ(adapter.embed_calls(), 1);
    EXPECT_EQ(adapter.request_count(), 2);  // Initial attempt and one retry.
    EXPECT_EQ(adapter.batch_calls(), 1);
}

TEST(OpenAIEmbeddingAdapter, FailedBatchCountsOnlyAttemptedChunks) {
    OpenAIEmbeddingAdapter::Config cfg;
    cfg.base_url = "unsupported-starling-test://invalid";
    cfg.max_retries = 3;
    cfg.max_batch_inputs = 1;
    OpenAIEmbeddingAdapter adapter(cfg);
    EXPECT_THROW(adapter.embed_batch({"a", "b", "c"}), EmbeddingError);
    EXPECT_EQ(adapter.batch_calls(), 1);
    EXPECT_EQ(adapter.embed_calls(), 0);
    EXPECT_EQ(adapter.request_count(), 1);  // No requests for unreached chunks.
}

TEST(OpenAIEmbeddingAdapter, SharedAdapterCountsConcurrentFailedCalls) {
    OpenAIEmbeddingAdapter::Config cfg;
    cfg.base_url = "unsupported-starling-test://invalid";
    cfg.max_retries = 0;
    OpenAIEmbeddingAdapter adapter(cfg);
    std::vector<std::thread> workers;
    for (int i = 0; i < 8; ++i) workers.emplace_back([&adapter] {
        try { (void)adapter.embed("offline"); } catch (const EmbeddingError&) {}
    });
    for (auto& worker : workers) worker.join();
    EXPECT_EQ(adapter.embed_calls(), 8);
    EXPECT_EQ(adapter.request_count(), 8);
    EXPECT_EQ(adapter.batch_calls(), 0);
}

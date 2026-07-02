// tests/cpp/test_stub_embedding_adapter.cpp
#include "starling/embedding/embedding_adapter.hpp"
#include <gtest/gtest.h>
#include <string>
#include <vector>
using namespace starling::embedding;

TEST(StubEmbeddingAdapter, DeterministicSameTextSameVector) {
    StubEmbeddingAdapter a(8);
    auto v1 = a.embed("hello world");
    auto v2 = a.embed("hello world");
    EXPECT_EQ(v1.dim, 8);
    EXPECT_EQ(v1.vector, v2.vector);
    EXPECT_NE(v1.vector, a.embed("different").vector);
}
TEST(StubEmbeddingAdapter, FailNextThrowsOnce) {
    StubEmbeddingAdapter a(8);
    a.fail_next("boom");
    EXPECT_THROW(a.embed("boom"), EmbeddingError);
    EXPECT_NO_THROW(a.embed("boom"));
}
TEST(StubEmbeddingAdapter, EmbedBatchParityWithSingles) {
    StubEmbeddingAdapter a(8);
    std::vector<std::string> texts{"alpha", "beta", "gamma"};
    auto batch = a.embed_batch(texts);
    ASSERT_EQ(batch.size(), texts.size());
    for (size_t pos = 0; pos < texts.size(); ++pos) {
        auto single = a.embed(texts[pos]);
        EXPECT_EQ(batch[pos].vector, single.vector);
        EXPECT_EQ(batch[pos].dim, single.dim);
    }
}
TEST(StubEmbeddingAdapter, EmbedBatchPropagatesFailure) {
    StubEmbeddingAdapter a(8);
    a.fail_next("beta");  // one text in the batch throws
    std::vector<std::string> texts{"alpha", "beta", "gamma"};
    EXPECT_THROW(a.embed_batch(texts), EmbeddingError);
}

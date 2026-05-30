// tests/cpp/test_stub_embedding_adapter.cpp
#include "starling/embedding/embedding_adapter.hpp"
#include <gtest/gtest.h>
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

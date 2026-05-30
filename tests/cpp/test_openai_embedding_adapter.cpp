// tests/cpp/test_openai_embedding_adapter.cpp
#include "starling/embedding/openai_embedding_adapter.hpp"
#include <gtest/gtest.h>
#include <cstdlib>
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

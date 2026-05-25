#include "starling/extractor/openai_adapter.hpp"

#include <cstdlib>
#include <gtest/gtest.h>

using starling::extractor::OpenAIAdapter;

TEST(OpenAIAdapterConfigTest, FromEnvReadsBaseUrlAndKey) {
    setenv("OPENAI_BASE_URL", "https://example.test/v1", 1);
    setenv("OPENAI_API_KEY", "sk-test-xyz", 1);
    auto cfg = OpenAIAdapter::Config::from_env();
    EXPECT_EQ(cfg.base_url, "https://example.test/v1");
    EXPECT_EQ(cfg.api_key,  "sk-test-xyz");
    EXPECT_EQ(cfg.model,    "gpt-5.5");
    unsetenv("OPENAI_BASE_URL");
    unsetenv("OPENAI_API_KEY");
}

TEST(OpenAIAdapterConfigTest, FromEnvThrowsWhenKeyMissing) {
    unsetenv("OPENAI_API_KEY");
    EXPECT_THROW(OpenAIAdapter::Config::from_env(), std::runtime_error);
}

TEST(OpenAIAdapterConfigTest, FromEnvDefaultsBaseUrlWhenUnset) {
    unsetenv("OPENAI_BASE_URL");
    setenv("OPENAI_API_KEY", "sk-test-xyz", 1);
    auto cfg = OpenAIAdapter::Config::from_env();
    EXPECT_EQ(cfg.base_url, "https://api.openai.com/v1");
    unsetenv("OPENAI_API_KEY");
}

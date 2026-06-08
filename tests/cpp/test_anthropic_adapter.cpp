#include "starling/extractor/anthropic_adapter.hpp"

#include <cstdlib>
#include <gtest/gtest.h>

using starling::extractor::AnthropicAdapter;

TEST(AnthropicAdapterConfigTest, FromEnvReadsBaseUrlAndKey) {
    setenv("ANTHROPIC_BASE_URL", "https://example.test", 1);
    setenv("ANTHROPIC_API_KEY", "sk-ant-test-xyz", 1);
    auto cfg = AnthropicAdapter::Config::from_env();
    EXPECT_EQ(cfg.base_url, "https://example.test");
    EXPECT_EQ(cfg.api_key,  "sk-ant-test-xyz");
    EXPECT_EQ(cfg.api_version, "2023-06-01");
    unsetenv("ANTHROPIC_BASE_URL");
    unsetenv("ANTHROPIC_API_KEY");
}

TEST(AnthropicAdapterConfigTest, FromEnvThrowsWhenKeyMissing) {
    unsetenv("ANTHROPIC_API_KEY");
    EXPECT_THROW(AnthropicAdapter::Config::from_env(), std::runtime_error);
}

TEST(AnthropicAdapterConfigTest, FromEnvDefaultsBaseUrlWhenUnset) {
    unsetenv("ANTHROPIC_BASE_URL");
    setenv("ANTHROPIC_API_KEY", "sk-ant-test-xyz", 1);
    auto cfg = AnthropicAdapter::Config::from_env();
    EXPECT_EQ(cfg.base_url, "https://api.anthropic.com");
    unsetenv("ANTHROPIC_API_KEY");
}

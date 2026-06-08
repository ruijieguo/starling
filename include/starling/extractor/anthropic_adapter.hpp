#pragma once

#include "starling/extractor/llm_adapter.hpp"

#include <string>
#include <string_view>

namespace starling::extractor {

// Anthropic native Messages API adapter. Mirrors OpenAIAdapter but targets
// POST {base_url}/v1/messages with x-api-key + anthropic-version headers and
// parses content[0].text. The API key is read from ANTHROPIC_API_KEY in the
// environment only (never a parameter, log line, or hardcoded value).
class AnthropicAdapter : public LLMAdapter {
public:
    struct Config {
        std::string base_url;                    // e.g. "https://api.anthropic.com"
        std::string api_key;                     // x-api-key header
        std::string model = "claude-sonnet-4-6";
        std::string api_version = "2023-06-01";  // anthropic-version header
        int         timeout_ms = 60000;
        int         max_retries = 3;
        int         max_tokens = 4096;

        // Reads ANTHROPIC_BASE_URL and ANTHROPIC_API_KEY from env. Throws
        // std::runtime_error if api_key is unset.
        static Config from_env();
    };

    explicit AnthropicAdapter(Config cfg);

    LLMResponse extract(std::string_view prompt,
                        std::string_view prompt_input_hash) override;

private:
    Config cfg_;
};

}  // namespace starling::extractor

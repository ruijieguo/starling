#pragma once

#include "starling/extractor/llm_adapter.hpp"

#include <string>
#include <string_view>

namespace starling::extractor {

// OpenAI-compatible chat-completions adapter. M0.7 pull-forward of the
// real adapter family that §15.3.7 lists as P2. Uses libcurl for HTTPS
// and nlohmann/json for body parsing. Reads OPENAI_BASE_URL +
// OPENAI_API_KEY from env at Config::from_env() construction; the key is
// never logged, exported, or bound to Python.
class OpenAIAdapter : public LLMAdapter {
public:
    struct Config {
        std::string base_url;       // e.g. "https://api.openai.com/v1"
        std::string api_key;        // Bearer token
        std::string model = "gpt-5.5";
        int         timeout_ms = 60000;
        int         max_retries = 3;

        // Reads OPENAI_BASE_URL and OPENAI_API_KEY from env. Throws
        // std::runtime_error if api_key is unset.
        static Config from_env();
    };

    explicit OpenAIAdapter(Config cfg);

    LLMResponse extract(std::string_view prompt,
                        std::string_view prompt_input_hash) override;

private:
    Config cfg_;
};

}  // namespace starling::extractor

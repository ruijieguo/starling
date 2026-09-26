#pragma once

#include "starling/extractor/llm_adapter.hpp"

#include <chrono>
#include <future>
#include <memory>
#include <mutex>
#include <optional>
#include <unordered_map>
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
        int         max_tokens = 4096;   // bound the response; reasoning models + JSON arrays
        // When enabled, extract() requests OpenAI-compatible JSON mode. This
        // is a request hint only; the C++ claim parser remains authoritative.
        bool        json_object_output = false;
        std::optional<bool> enable_thinking;  // 未设置时保持服务端默认行为

        // Reads OPENAI_BASE_URL and OPENAI_API_KEY from env. Throws
        // std::runtime_error if api_key is unset.
        static Config from_env();
    };

    using MonotonicClock = std::function<std::chrono::steady_clock::time_point()>;
    explicit OpenAIAdapter(Config cfg, MonotonicClock clock = std::chrono::steady_clock::now);
    LLMResponse extract_with_contract(std::string_view prompt, std::string_view hash,
                                     const StructuredOutputRequest& request) override;
    CapabilityEvidence probe_structured_output(const StructuredOutputRequest& request);
    void clear_structured_output_capabilities();

    LLMResponse extract(std::string_view prompt,
                        std::string_view prompt_input_hash) override;

    // Free-form generation never uses the extraction JSON mode hint.
    LLMResponse generate(std::string_view prompt) override;

    // Real token-by-token streaming: POST stream:true + stream_options.include_usage,
    // parse the SSE deltas via sse::StreamAccumulator, emit each through on_token,
    // and return the assembled reply + usage (same LLMResponse extract() returns).
    LLMResponse generate_stream(std::string_view prompt,
                                const TokenSink& on_token) override;

private:
    LLMResponse complete(std::string_view prompt, bool json_object_output,
                         const StructuredOutputRequest* request = nullptr, bool probe = false);
    std::string capability_key(const StructuredOutputRequest& request) const;
    struct CacheEntry {
        std::shared_future<CapabilityEvidence> future;
        std::chrono::steady_clock::time_point expires;
        bool pending = true;
    };
    const Config cfg_;
    MonotonicClock clock_;
    std::mutex capability_mutex_;
    std::unordered_map<std::string, std::shared_ptr<CacheEntry>> capabilities_;
};

}  // namespace starling::extractor

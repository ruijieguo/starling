#include "starling/extractor/anthropic_adapter.hpp"

#include <chrono>
#include <cstdlib>
#include <stdexcept>
#include <string>

#include <nlohmann/json.hpp>

#include "starling/net/http_post_json.hpp"
#include "starling/extractor/sse_stream.hpp"

namespace starling::extractor {

AnthropicAdapter::Config AnthropicAdapter::Config::from_env() {
    Config c;
    const char* key = std::getenv("ANTHROPIC_API_KEY");
    if (!key || *key == '\0') {
        throw std::runtime_error("ANTHROPIC_API_KEY not set");
    }
    c.api_key = key;
    const char* base = std::getenv("ANTHROPIC_BASE_URL");
    c.base_url = (base && *base) ? base : "https://api.anthropic.com";
    return c;
}

AnthropicAdapter::AnthropicAdapter(Config cfg) : cfg_(std::move(cfg)) {}

LLMResponse AnthropicAdapter::extract(std::string_view prompt,
                                      std::string_view /*prompt_input_hash*/) {
    nlohmann::json body = {
        {"model",       cfg_.model},
        {"max_tokens",  cfg_.max_tokens},
        {"temperature", 0},  // deterministic extraction, parity with OpenAIAdapter
        {"messages",    nlohmann::json::array({
            {{"role", "user"}, {"content", std::string(prompt)}}})}
    };
    const auto t0 = std::chrono::steady_clock::now();
    const auto r = net::http_post_json(
        cfg_.base_url + "/v1/messages",
        {"x-api-key: " + cfg_.api_key,
         "anthropic-version: " + cfg_.api_version},
        body.dump(), cfg_.timeout_ms, cfg_.max_retries);
    const int latency_ms = static_cast<int>(
        std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now() - t0).count());
    if (!r.ok) {
        return {.raw_xml = {}, .ok = false, .error = r.error, .latency_ms = latency_ms};
    }
    try {
        auto j = nlohmann::json::parse(r.body);
        const std::string content = j["content"][0]["text"].get<std::string>();
        LLMResponse out{.raw_xml = content, .ok = true, .error = {}, .latency_ms = latency_ms};
        if (j.contains("usage")) {                    // Anthropic input/output_tokens
            const auto& u = j["usage"];
            out.prompt_tokens     = u.value("input_tokens", 0);
            out.completion_tokens = u.value("output_tokens", 0);
            out.total_tokens      = out.prompt_tokens + out.completion_tokens;
        }
        return out;
    } catch (const std::exception&) {
        return {.raw_xml = {}, .ok = false, .error = "malformed_response", .latency_ms = latency_ms};
    }
}

LLMResponse AnthropicAdapter::generate_stream(std::string_view prompt,
                                              const TokenSink& on_token) {
    nlohmann::json body = {
        {"model",       cfg_.model},
        {"max_tokens",  cfg_.max_tokens},
        {"temperature", 0},
        {"stream",      true},
        {"messages",    nlohmann::json::array({
            {{"role", "user"}, {"content", std::string(prompt)}}})}
    };
    sse::StreamAccumulator acc(sse::Provider::Anthropic, on_token);
    const auto started = std::chrono::steady_clock::now();
    const auto resp = net::http_post_json_stream(
        cfg_.base_url + "/v1/messages",
        {"x-api-key: " + cfg_.api_key,
         "anthropic-version: " + cfg_.api_version},
        body.dump(), cfg_.timeout_ms,
        [&acc](std::string_view chunk) { acc.feed(chunk); });
    const int latency_ms = static_cast<int>(
        std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now() - started).count());
    if (!resp.ok) {
        return {.raw_xml = {}, .ok = false, .error = resp.error, .latency_ms = latency_ms};
    }
    return {.raw_xml = acc.text(), .ok = true, .error = {},
            .prompt_tokens = acc.prompt_tokens(),
            .completion_tokens = acc.completion_tokens(),
            .total_tokens = acc.total_tokens(),
            .latency_ms = latency_ms};
}

}  // namespace starling::extractor

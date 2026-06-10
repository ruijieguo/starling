#include "starling/extractor/anthropic_adapter.hpp"

#include <cstdlib>
#include <stdexcept>
#include <string>

#include <nlohmann/json.hpp>

#include "starling/net/http_post_json.hpp"

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
    const auto r = net::http_post_json(
        cfg_.base_url + "/v1/messages",
        {"x-api-key: " + cfg_.api_key,
         "anthropic-version: " + cfg_.api_version},
        body.dump(), cfg_.timeout_ms, cfg_.max_retries);
    if (!r.ok) {
        return {.raw_xml = {}, .ok = false, .error = r.error};
    }
    try {
        auto j = nlohmann::json::parse(r.body);
        const std::string content = j["content"][0]["text"].get<std::string>();
        return {.raw_xml = content, .ok = true, .error = {}};
    } catch (const std::exception&) {
        return {.raw_xml = {}, .ok = false, .error = "malformed_response"};
    }
}

}  // namespace starling::extractor

#include "starling/extractor/openai_adapter.hpp"

#include <chrono>
#include <cstdlib>
#include <stdexcept>
#include <string>

#include <nlohmann/json.hpp>

#include "starling/net/http_post_json.hpp"

namespace starling::extractor {

OpenAIAdapter::Config OpenAIAdapter::Config::from_env() {
    Config c;
    const char* key = std::getenv("OPENAI_API_KEY");
    if (!key || *key == '\0') {
        throw std::runtime_error("OPENAI_API_KEY not set");
    }
    c.api_key = key;
    const char* base = std::getenv("OPENAI_BASE_URL");
    c.base_url = (base && *base) ? base : "https://api.openai.com/v1";
    return c;
}

OpenAIAdapter::OpenAIAdapter(Config cfg) : cfg_(std::move(cfg)) {}

LLMResponse OpenAIAdapter::extract(std::string_view prompt,
                                   std::string_view /*prompt_input_hash*/) {
    nlohmann::json body = {
        {"model",       cfg_.model},
        {"messages",    nlohmann::json::array({
            {{"role", "user"}, {"content", std::string(prompt)}}})},
        {"temperature", 0},
        {"max_tokens",  cfg_.max_tokens}
    };
    const auto t0 = std::chrono::steady_clock::now();
    const auto r = net::http_post_json(
        cfg_.base_url + "/chat/completions",
        {"Authorization: Bearer " + cfg_.api_key},
        body.dump(), cfg_.timeout_ms, cfg_.max_retries);
    const int latency_ms = static_cast<int>(
        std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now() - t0).count());
    if (!r.ok) {
        return {.raw_xml = {}, .ok = false, .error = r.error, .latency_ms = latency_ms};
    }
    try {
        auto j = nlohmann::json::parse(r.body);
        const std::string content = j["choices"][0]["message"]["content"].get<std::string>();
        LLMResponse out{.raw_xml = content, .ok = true, .error = {}, .latency_ms = latency_ms};
        if (j.contains("usage")) {                    // OpenAI usage block (best-effort)
            const auto& u = j["usage"];
            out.prompt_tokens     = u.value("prompt_tokens", 0);
            out.completion_tokens = u.value("completion_tokens", 0);
            out.total_tokens      = u.value("total_tokens", out.prompt_tokens + out.completion_tokens);
        }
        return out;
    } catch (const std::exception&) {
        return {.raw_xml = {}, .ok = false, .error = "malformed_response", .latency_ms = latency_ms};
    }
}

}  // namespace starling::extractor

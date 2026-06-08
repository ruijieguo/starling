#include "starling/extractor/anthropic_adapter.hpp"

#include <chrono>
#include <cstdlib>
#include <stdexcept>
#include <string>
#include <thread>

#include <curl/curl.h>
#include <nlohmann/json.hpp>

namespace starling::extractor {

namespace {

std::size_t write_cb(char* ptr, std::size_t size, std::size_t nmemb, void* userdata) {
    auto* buf = static_cast<std::string*>(userdata);
    buf->append(ptr, size * nmemb);
    return size * nmemb;
}

bool is_retryable_status(long http_code) {
    return http_code == 429 || (http_code >= 500 && http_code < 600);
}

bool is_retryable_curl_code(CURLcode rc) {
    switch (rc) {
        case CURLE_OPERATION_TIMEDOUT:
        case CURLE_COULDNT_CONNECT:
        case CURLE_COULDNT_RESOLVE_HOST:
        case CURLE_COULDNT_RESOLVE_PROXY:
        case CURLE_SEND_ERROR:
        case CURLE_RECV_ERROR:
        case CURLE_GOT_NOTHING:
        case CURLE_PARTIAL_FILE:
            return true;
        default:
            return false;
    }
}

}  // namespace

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
    const std::string body_str = body.dump();
    const std::string url      = cfg_.base_url + "/v1/messages";
    const std::string key_hdr  = "x-api-key: " + cfg_.api_key;
    const std::string ver_hdr  = "anthropic-version: " + cfg_.api_version;

    int delay_ms = 1000;
    for (int attempt = 0; attempt <= cfg_.max_retries; ++attempt) {
        CURL* curl = curl_easy_init();
        if (!curl) return {.raw_xml = {}, .ok = false, .error = "curl_init_failed"};

        std::string resp_buf;
        curl_slist* headers = nullptr;
        headers = curl_slist_append(headers, "Content-Type: application/json");
        headers = curl_slist_append(headers, key_hdr.c_str());
        headers = curl_slist_append(headers, ver_hdr.c_str());

        curl_easy_setopt(curl, CURLOPT_URL,           url.c_str());
        curl_easy_setopt(curl, CURLOPT_HTTPHEADER,    headers);
        curl_easy_setopt(curl, CURLOPT_POST,          1L);
        curl_easy_setopt(curl, CURLOPT_POSTFIELDS,    body_str.c_str());
        curl_easy_setopt(curl, CURLOPT_POSTFIELDSIZE, static_cast<long>(body_str.size()));
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_cb);
        curl_easy_setopt(curl, CURLOPT_WRITEDATA,     &resp_buf);
        curl_easy_setopt(curl, CURLOPT_TIMEOUT_MS,    static_cast<long>(cfg_.timeout_ms));

        const CURLcode rc = curl_easy_perform(curl);
        long http_code = 0;
        curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
        curl_slist_free_all(headers);
        curl_easy_cleanup(curl);

        if (rc != CURLE_OK) {
            if (is_retryable_curl_code(rc) && attempt < cfg_.max_retries) {
                std::this_thread::sleep_for(std::chrono::milliseconds(delay_ms));
                delay_ms *= 2;
                continue;
            }
            return {.raw_xml = {}, .ok = false,
                    .error = std::string("transport_error:") + curl_easy_strerror(rc)};
        }

        if (is_retryable_status(http_code)) {
            if (attempt < cfg_.max_retries) {
                std::this_thread::sleep_for(std::chrono::milliseconds(delay_ms));
                delay_ms *= 2;
                continue;
            }
            return {.raw_xml = {}, .ok = false, .error = "transient_after_retry"};
        }

        if (http_code >= 400) {
            return {.raw_xml = {}, .ok = false,
                    .error = "permanent_" + std::to_string(http_code)};
        }

        try {
            auto j = nlohmann::json::parse(resp_buf);
            const std::string content = j["content"][0]["text"].get<std::string>();
            return {.raw_xml = content, .ok = true, .error = {}};
        } catch (const std::exception&) {
            return {.raw_xml = {}, .ok = false, .error = "malformed_response"};
        }
    }
    return {.raw_xml = {}, .ok = false, .error = "transient_after_retry"};
}

}  // namespace starling::extractor

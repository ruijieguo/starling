#include "starling/extractor/openai_adapter.hpp"

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

// Retry only on transport errors where the request demonstrably did NOT
// complete server-side. CURLE_OPERATION_TIMEDOUT / COULDNT_CONNECT /
// COULDNT_RESOLVE_HOST / SEND_ERROR cover network-side failures; GOT_NOTHING
// and PARTIAL_FILE cover dropped/torn responses. Everything else (TLS errors,
// abort callbacks, etc.) is treated as permanent so we don't double-charge
// chat/completions when the server may have processed the prompt.
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
    const std::string body_str = body.dump();
    const std::string url      = cfg_.base_url + "/chat/completions";
    const std::string auth_hdr = "Authorization: Bearer " + cfg_.api_key;

    int delay_ms = 1000;
    for (int attempt = 0; attempt <= cfg_.max_retries; ++attempt) {
        CURL* curl = curl_easy_init();
        if (!curl) return {.raw_xml = {}, .ok = false, .error = "curl_init_failed"};

        std::string resp_buf;
        curl_slist* headers = nullptr;
        headers = curl_slist_append(headers, "Content-Type: application/json");
        headers = curl_slist_append(headers, auth_hdr.c_str());

        curl_easy_setopt(curl, CURLOPT_URL,            url.c_str());
        curl_easy_setopt(curl, CURLOPT_HTTPHEADER,     headers);
        curl_easy_setopt(curl, CURLOPT_POST,           1L);
        curl_easy_setopt(curl, CURLOPT_POSTFIELDS,     body_str.c_str());
        curl_easy_setopt(curl, CURLOPT_POSTFIELDSIZE,  static_cast<long>(body_str.size()));
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION,  write_cb);
        curl_easy_setopt(curl, CURLOPT_WRITEDATA,      &resp_buf);
        curl_easy_setopt(curl, CURLOPT_TIMEOUT_MS,     static_cast<long>(cfg_.timeout_ms));

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
            const std::string content = j["choices"][0]["message"]["content"].get<std::string>();
            return {.raw_xml = content, .ok = true, .error = {}};
        } catch (const std::exception&) {
            return {.raw_xml = {}, .ok = false, .error = "malformed_response"};
        }
    }
    return {.raw_xml = {}, .ok = false, .error = "transient_after_retry"};
}

}  // namespace starling::extractor

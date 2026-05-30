#include "starling/embedding/openai_embedding_adapter.hpp"

#include <chrono>
#include <cstdlib>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

#include <curl/curl.h>
#include <nlohmann/json.hpp>

namespace starling::embedding {

namespace {

std::size_t write_cb(char* ptr, std::size_t size, std::size_t nmemb, void* userdata) {
    auto* buf = static_cast<std::string*>(userdata);
    buf->append(ptr, size * nmemb);
    return size * nmemb;
}

bool is_retryable_status(long http_code) {
    return http_code == 429 || (http_code >= 500 && http_code < 600);
}

// Mirror of openai_adapter.cpp: retry only on transport errors where the
// request demonstrably did NOT complete server-side. Everything else (TLS
// errors, abort callbacks, etc.) is treated as permanent.
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

OpenAIEmbeddingAdapter::Config OpenAIEmbeddingAdapter::Config::from_env() {
    Config c;
    const char* key = std::getenv("OPENAI_API_KEY");
    if (!key || *key == '\0') {
        throw std::runtime_error("OPENAI_API_KEY not set");
    }
    c.api_key = key;
    const char* base = std::getenv("OPENAI_BASE_URL");
    c.base_url = (base && *base) ? base : "https://api.openai.com/v1";
    const char* model = std::getenv("EMBEDDING_MODEL");
    if (model && *model) {
        c.model = model;
    }
    return c;
}

EmbeddingResult OpenAIEmbeddingAdapter::embed(std::string_view text) {
    nlohmann::json body = {
        {"model", cfg_.model},
        {"input", std::string(text)}
    };
    const std::string body_str = body.dump();
    const std::string url      = cfg_.base_url + "/embeddings";
    const std::string auth_hdr = "Authorization: Bearer " + cfg_.api_key;

    int delay_ms = 1000;
    for (int attempt = 0; attempt <= cfg_.max_retries; ++attempt) {
        CURL* curl = curl_easy_init();
        if (!curl) throw EmbeddingError("curl_init_failed");

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
            throw EmbeddingError(std::string("transport_error:") + curl_easy_strerror(rc));
        }

        if (is_retryable_status(http_code)) {
            if (attempt < cfg_.max_retries) {
                std::this_thread::sleep_for(std::chrono::milliseconds(delay_ms));
                delay_ms *= 2;
                continue;
            }
            throw EmbeddingError("transient_after_retry");
        }

        if (http_code >= 400) {
            // Permanent client error: not retryable. Surface as a hard failure.
            throw std::runtime_error("permanent_" + std::to_string(http_code));
        }

        try {
            auto j = nlohmann::json::parse(resp_buf);
            const auto& emb = j.at("data").at(0).at("embedding");
            std::vector<float> vec;
            vec.reserve(emb.size());
            for (const auto& x : emb) {
                vec.push_back(x.get<float>());
            }
            return {std::move(vec), cfg_.dim, cfg_.model};
        } catch (const std::exception&) {
            throw std::runtime_error("malformed_response");
        }
    }
    throw EmbeddingError("transient_after_retry");
}

}  // namespace starling::embedding

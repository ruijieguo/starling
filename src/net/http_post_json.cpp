#include "starling/net/http_post_json.hpp"

#include <chrono>
#include <thread>

#include <curl/curl.h>

namespace starling::net {

namespace {

// curl_global_init is documented as not thread-safe; run it exactly once via a
// magic static before the first request. Paired cleanup at process exit.
struct CurlGlobal {
    CurlGlobal() { curl_global_init(CURL_GLOBAL_DEFAULT); }
    ~CurlGlobal() { curl_global_cleanup(); }
};

void ensure_curl_global() {
    static CurlGlobal g;
    (void)g;
}

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
// abort callbacks, etc.) is treated as permanent.
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

HttpResult http_post_json(const std::string& url,
                          const std::vector<std::string>& extra_headers,
                          const std::string& body,
                          int timeout_ms,
                          int max_retries) {
    ensure_curl_global();

    int delay_ms = 1000;
    for (int attempt = 0; attempt <= max_retries; ++attempt) {
        CURL* curl = curl_easy_init();
        if (!curl) return {.ok = false, .http_code = 0, .body = {}, .error = "curl_init_failed"};

        std::string resp_buf;
        curl_slist* headers = nullptr;
        headers = curl_slist_append(headers, "Content-Type: application/json");
        for (const auto& h : extra_headers) {
            headers = curl_slist_append(headers, h.c_str());
        }

        curl_easy_setopt(curl, CURLOPT_URL,           url.c_str());
        curl_easy_setopt(curl, CURLOPT_HTTPHEADER,    headers);
        curl_easy_setopt(curl, CURLOPT_POST,          1L);
        curl_easy_setopt(curl, CURLOPT_POSTFIELDS,    body.c_str());
        curl_easy_setopt(curl, CURLOPT_POSTFIELDSIZE, static_cast<long>(body.size()));
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_cb);
        curl_easy_setopt(curl, CURLOPT_WRITEDATA,     &resp_buf);
        curl_easy_setopt(curl, CURLOPT_TIMEOUT_MS,    static_cast<long>(timeout_ms));
        curl_easy_setopt(curl, CURLOPT_NOSIGNAL,      1L);

        const CURLcode rc = curl_easy_perform(curl);
        long http_code = 0;
        curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
        curl_slist_free_all(headers);
        curl_easy_cleanup(curl);

        if (rc != CURLE_OK) {
            if (is_retryable_curl_code(rc) && attempt < max_retries) {
                std::this_thread::sleep_for(std::chrono::milliseconds(delay_ms));
                delay_ms *= 2;
                continue;
            }
            return {.ok = false, .http_code = 0, .body = {},
                    .error = std::string("transport_error:") + curl_easy_strerror(rc)};
        }

        if (is_retryable_status(http_code)) {
            if (attempt < max_retries) {
                std::this_thread::sleep_for(std::chrono::milliseconds(delay_ms));
                delay_ms *= 2;
                continue;
            }
            return {.ok = false, .http_code = http_code, .body = {},
                    .error = "transient_after_retry"};
        }

        if (http_code >= 400) {
            return {.ok = false, .http_code = http_code, .body = {},
                    .error = "permanent_" + std::to_string(http_code)};
        }

        return {.ok = true, .http_code = http_code, .body = std::move(resp_buf), .error = {}};
    }
    return {.ok = false, .http_code = 0, .body = {}, .error = "transient_after_retry"};
}

}  // namespace starling::net

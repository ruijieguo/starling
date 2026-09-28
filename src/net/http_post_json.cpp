#include "starling/net/http_post_json.hpp"

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <thread>
#include <utility>

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

// Per-thread reused easy handle. Keeping the handle alive across calls (no cleanup
// per request) lets libcurl reuse the TLS connection (keep-alive) instead of a fresh
// handshake every call. A fresh handle per call churned connections ->
// CURLE_SSL_CONNECT_ERROR under concurrent handshakes. curl handles are not
// thread-safe, so one per thread; the dtor (at thread exit) cleans it up.
struct CurlHandle {
    CURL* h;
    CurlHandle() : h(curl_easy_init()) {}
    ~CurlHandle() { if (h) { curl_easy_cleanup(h); 
}}
    CurlHandle(const CurlHandle&) = delete;
    CurlHandle& operator=(const CurlHandle&) = delete;
};

std::size_t write_cb(char* ptr, std::size_t size, std::size_t nmemb, void* userdata) {
    auto* buf = static_cast<std::string*>(userdata);
    buf->append(ptr, size * nmemb);
    return size * nmemb;
}

// Streaming write callback: forward each received chunk to the caller's sink
// instead of buffering. userdata is the ChunkSink (set via CURLOPT_WRITEDATA).
// The sink must not throw — it runs inside libcurl (a C frame); callers pass a
// non-throwing sink, so no try/catch is needed here.
std::size_t stream_write_cb(char* ptr, std::size_t size, std::size_t nmemb, void* userdata) {
    const std::size_t total = size * nmemb;
    const auto* sink = static_cast<const std::function<void(std::string_view)>*>(userdata);
    (*sink)(std::string_view(ptr, total));
    return total;
}

bool is_retryable_status(long http_code) {
    return http_code == 429 || (http_code >= 500 && http_code < 600);
}

// 旧兼容策略保留既有传输重试集合。超时、发送失败或响应中断不证明
// 服务端尚未处理 POST；需要更严格边界的结构化请求使用 ConnectOnly。
bool is_retryable_curl_code(CURLcode rc) {
    switch (rc) {
        case CURLE_OPERATION_TIMEDOUT:
        case CURLE_COULDNT_CONNECT:
        case CURLE_COULDNT_RESOLVE_HOST:
        case CURLE_COULDNT_RESOLVE_PROXY:
        case CURLE_SSL_CONNECT_ERROR:
        case CURLE_SEND_ERROR:
        case CURLE_RECV_ERROR:
        case CURLE_GOT_NOTHING:
        case CURLE_PARTIAL_FILE:
        case CURLE_HTTP2:          // "Error in the HTTP2 framing layer" — torn H2
        case CURLE_HTTP2_STREAM:   // stream-level H2 failure; the request can be re-sent
            return true;
        default:
            return false;
    }
}

bool is_explicit_not_connected(CURLcode rc) {
    switch (rc) {
        case CURLE_COULDNT_CONNECT:
        case CURLE_COULDNT_RESOLVE_HOST:
        case CURLE_COULDNT_RESOLVE_PROXY:
            return true;
        default:
            return false;
    }
}

ExecutionCertainty execution_certainty(CURLcode curl_code,
                                        long http_status,
                                        std::size_t response_bytes) {
    if (http_status != 0 || response_bytes != 0U) {
        return ExecutionCertainty::ResponseReceived;
    }
    if (is_explicit_not_connected(curl_code)) {
        return ExecutionCertainty::NotConnected;
    }
    return ExecutionCertainty::Unknown;
}

bool should_retry_transport(RetryPolicy retry_policy,
                            CURLcode curl_code,
                            const HttpAttemptEvidence& evidence) {
    if (retry_policy == RetryPolicy::LegacyCompatible) {
        return is_retryable_curl_code(curl_code);
    }
    return evidence.execution_certainty == ExecutionCertainty::NotConnected &&
           evidence.http_status == 0 && evidence.response_bytes == 0U;
}

HttpAttemptEvidence make_attempt_evidence(std::size_t attempt,
                                          long http_status,
                                          CURLcode curl_code,
                                          const std::string& response_body,
                                          std::size_t response_bytes,
                                          std::size_t streamed_bytes,
                                          std::int64_t elapsed_ms,
                                          RetryPolicy retry_policy) {
    HttpAttemptEvidence evidence;
    evidence.attempt = attempt;
    evidence.http_status = http_status;
    evidence.curl_code = static_cast<int>(curl_code);
    evidence.response_body = response_body;
    evidence.response_bytes = response_bytes;
    evidence.streamed_bytes = streamed_bytes;
    evidence.elapsed_ms = elapsed_ms;
    evidence.retry_policy = retry_policy;
    evidence.execution_certainty = execution_certainty(curl_code, http_status, response_bytes);
    return evidence;
}

HttpResult invalid_config_result() {
    HttpResult result;
    result.error = "invalid_config";
    return result;
}

void apply_attempts(HttpResult& result, std::vector<HttpAttemptEvidence>&& attempts) {
    result.attempt_count = attempts.size();
    result.attempts = std::move(attempts);
}

void bounded_backoff(std::chrono::milliseconds& delay) {
    constexpr std::chrono::milliseconds kMaxDelay{30000};
    std::this_thread::sleep_for(delay);
    delay = std::min(delay * 2, kMaxDelay);
}

}  // namespace

HttpResult http_post_json(const std::string& url,
                          const std::vector<std::string>& extra_headers,
                          const std::string& body,
                          int timeout_ms,
                          int max_retries) {
    return http_post_json(url, extra_headers, body, timeout_ms, max_retries,
                          RetryPolicy::LegacyCompatible);
}

HttpResult http_post_json(const std::string& url,
                          const std::vector<std::string>& extra_headers,
                          const std::string& body,
                          int timeout_ms,
                          int max_retries,
                          RetryPolicy retry_policy) {
    if (timeout_ms <= 0 || max_retries < 0) {
        return invalid_config_result();
    }
    ensure_curl_global();
    thread_local CurlHandle tls;
    CURL* curl = tls.h;
    if (!curl) { return {.ok = false, .http_code = 0, .body = {}, .error = "curl_init_failed"};
}

    std::chrono::milliseconds delay{1000};
    std::vector<HttpAttemptEvidence> attempts;
    const std::size_t max_attempts = static_cast<std::size_t>(max_retries) + 1U;
    for (std::size_t attempt = 0; attempt < max_attempts; ++attempt) {
        // Reset options to defaults but KEEP the live connection (keep-alive),
        // DNS cache, and TLS session cache — that is what eliminates the churn.
        curl_easy_reset(curl);

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
        // Pin HTTP/1.1. The default negotiates HTTP/2 (ALPN), whose multiplexed
        // framing intermittently fails as CURLE_HTTP2 "Error in the HTTP2 framing
        // layer" under sustained concurrent load through the funded proxy (observed
        // 13/53 answer failures in a HiToM in-loop run). HTTP/1.1 keep-alive over the
        // reused per-thread handle is robust, and our one-request-at-a-time-per-thread
        // pattern gains nothing from H2 multiplexing anyway.
        curl_easy_setopt(curl, CURLOPT_HTTP_VERSION,  CURL_HTTP_VERSION_1_1);

        const auto started = std::chrono::steady_clock::now();
        const CURLcode rc = curl_easy_perform(curl);
        const auto elapsed_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now() - started).count();
        long http_code = 0;
        curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
        curl_slist_free_all(headers);
        // No curl_easy_cleanup: the handle (and its TLS connection) is reused.

        attempts.push_back(make_attempt_evidence(attempt + 1U, http_code, rc, resp_buf,
                                                 resp_buf.size(), 0U, elapsed_ms, retry_policy));
        const bool has_retry_budget = attempt + 1U < max_attempts;

        if (rc != CURLE_OK) {
            if (has_retry_budget && should_retry_transport(retry_policy, rc, attempts.back())) {
                bounded_backoff(delay);
                continue;
            }
            HttpResult result;
            result.error = std::string("transport_error:") + curl_easy_strerror(rc);
            apply_attempts(result, std::move(attempts));
            return result;
        }

        if (is_retryable_status(http_code)) {
            if (retry_policy == RetryPolicy::LegacyCompatible && has_retry_budget) {
                bounded_backoff(delay);
                continue;
            }
            HttpResult result;
            result.http_code = http_code;
            result.error = "transient_after_retry";
            apply_attempts(result, std::move(attempts));
            return result;
        }

        if (http_code >= 400) {
            HttpResult result;
            result.http_code = http_code;
            result.error = "permanent_" + std::to_string(http_code);
            apply_attempts(result, std::move(attempts));
            return result;
        }

        HttpResult result;
        result.ok = true;
        result.http_code = http_code;
        result.body = std::move(resp_buf);
        apply_attempts(result, std::move(attempts));
        return result;
    }
    HttpResult result;
    result.error = "transient_after_retry";
    apply_attempts(result, std::move(attempts));
    return result;
}

HttpResult http_post_json_stream(const std::string& url,
                                 const std::vector<std::string>& extra_headers,
                                 const std::string& body,
                                 int timeout_ms,
                                 int max_retries,
                                 const std::function<void(std::string_view)>& on_chunk) {
    return http_post_json_stream(url, extra_headers, body, timeout_ms, max_retries, on_chunk,
                                 RetryPolicy::LegacyCompatible);
}

HttpResult http_post_json_stream(const std::string& url,
                                 const std::vector<std::string>& extra_headers,
                                 const std::string& body,
                                 int timeout_ms,
                                 int max_retries,
                                 const std::function<void(std::string_view)>& on_chunk,
                                 RetryPolicy retry_policy) {
    if (timeout_ms <= 0 || max_retries < 0) {
        return invalid_config_result();
    }
    ensure_curl_global();
    thread_local CurlHandle tls;
    CURL* curl = tls.h;
    if (curl == nullptr) {
        return {.ok = false, .http_code = 0, .body = {}, .error = "curl_init_failed"};
    }

    std::chrono::milliseconds delay{1000};
    std::vector<HttpAttemptEvidence> attempts;
    const std::size_t max_attempts = static_cast<std::size_t>(max_retries) + 1U;
    for (std::size_t attempt = 0; attempt < max_attempts; ++attempt) {
        curl_easy_reset(curl);
        std::string response_body;
        std::size_t streamed_bytes = 0;
        const std::function<void(std::string_view)> guarded_sink =
            [&response_body, &streamed_bytes, &on_chunk](std::string_view chunk) {
                streamed_bytes += chunk.size();
                response_body.append(chunk);
                on_chunk(chunk);
            };
        curl_slist* headers = nullptr;
        headers = curl_slist_append(headers, "Content-Type: application/json");
        for (const auto& header : extra_headers) {
            headers = curl_slist_append(headers, header.c_str());
        }

        curl_easy_setopt(curl, CURLOPT_URL,           url.c_str());
        curl_easy_setopt(curl, CURLOPT_HTTPHEADER,    headers);
        curl_easy_setopt(curl, CURLOPT_POST,          1L);
        curl_easy_setopt(curl, CURLOPT_POSTFIELDS,    body.c_str());
        curl_easy_setopt(curl, CURLOPT_POSTFIELDSIZE, static_cast<long>(body.size()));
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, stream_write_cb);
        curl_easy_setopt(curl, CURLOPT_WRITEDATA,     &guarded_sink);
        curl_easy_setopt(curl, CURLOPT_TIMEOUT_MS,    static_cast<long>(timeout_ms));
        curl_easy_setopt(curl, CURLOPT_NOSIGNAL,      1L);
        curl_easy_setopt(curl, CURLOPT_HTTP_VERSION,  CURL_HTTP_VERSION_1_1);

        const auto started = std::chrono::steady_clock::now();
        const CURLcode curl_code = curl_easy_perform(curl);
        const auto elapsed_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now() - started).count();
        long http_code = 0;
        curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
        curl_slist_free_all(headers);

        attempts.push_back(make_attempt_evidence(attempt + 1U, http_code, curl_code,
                                                 response_body, response_body.size(),
                                                 streamed_bytes, elapsed_ms, retry_policy));
        const bool has_retry_budget = attempt + 1U < max_attempts;

        if (curl_code != CURLE_OK) {
            if (streamed_bytes == 0U && has_retry_budget &&
                should_retry_transport(retry_policy, curl_code, attempts.back())) {
                bounded_backoff(delay);
                continue;
            }
            HttpResult result;
            result.error = std::string("transport_error:") + curl_easy_strerror(curl_code);
            apply_attempts(result, std::move(attempts));
            return result;
        }
        if (http_code >= 400) {
            HttpResult result;
            result.http_code = http_code;
            result.error = "permanent_" + std::to_string(http_code);
            apply_attempts(result, std::move(attempts));
            return result;
        }
        HttpResult result;
        result.ok = true;
        result.http_code = http_code;
        apply_attempts(result, std::move(attempts));
        return result;
    }
    HttpResult result;
    result.error = "transient_after_retry";
    apply_attempts(result, std::move(attempts));
    return result;
}

}  // namespace starling::net

#pragma once
#include <string>
#include <vector>

namespace starling::net {

// Outcome of one JSON POST (after internal retries). Exactly one shape:
//   ok=true                          → 2xx/3xx, `body` holds the response
//   error="transport_error:<curl>"   → network failure (non-retryable, or retries exhausted)
//   error="transient_after_retry"    → 429/5xx persisted through every retry
//   error="permanent_<code>"         → non-retryable HTTP >= 400 (`http_code` set)
//   error="curl_init_failed"
struct HttpResult {
    bool ok = false;
    long http_code = 0;
    std::string body;
    std::string error;
};

// POST `body` as application/json with bounded exponential backoff (1s, 2s, …)
// on transient failures: HTTP 429/5xx plus the curl transport errors where the
// request demonstrably did NOT complete server-side (timeout / connect /
// resolve / send / recv / got-nothing / partial). Everything else (TLS errors,
// abort callbacks, …) is permanent, so an LLM call the server may already have
// processed is never double-charged.
//
// `extra_headers` are full header lines ("x-api-key: …");
// "Content-Type: application/json" is always added. Sets CURLOPT_NOSIGNAL and
// performs process-wide curl_global_init once — both required in multithreaded
// processes (dashboard routes call adapters from worker threads; without
// NOSIGNAL a DNS timeout raises SIGALRM into an arbitrary thread).
//
// Single implementation for OpenAIAdapter / AnthropicAdapter /
// OpenAIEmbeddingAdapter, which previously carried three mirrored copies of
// this loop.
HttpResult http_post_json(const std::string& url,
                          const std::vector<std::string>& extra_headers,
                          const std::string& body,
                          int timeout_ms,
                          int max_retries);

}  // namespace starling::net

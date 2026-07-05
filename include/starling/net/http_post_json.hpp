#pragma once
#include <functional>
#include <string>
#include <string_view>
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

// Streaming POST: invokes on_chunk(bytes) for each response-body chunk as it
// arrives (for SSE). Retry policy: the same retryable curl transport failures
// as http_post_json (handshake / connect / resolve / …) get the same bounded
// backoff, but ONLY while NO byte has been handed to on_chunk — a failure
// before the first byte (e.g. CURLE_SSL_CONNECT_ERROR: the request never
// reached the server) demonstrably streamed nothing, so a retry cannot
// duplicate output. From the first delivered byte onward the original
// single-attempt semantics apply: a torn stream surfaces as ok=false (the
// caller emits a clean no-reply rather than replaying). HTTP 429/5xx are never
// retried here — their error bodies stream to on_chunk.
// on_chunk MUST NOT throw (it runs inside libcurl's write callback); callers pass
// a non-throwing sink (e.g. sse::StreamAccumulator::feed). `body` is empty on
// return — the caller assembles the response via on_chunk. ok=true only for
// http_code < 400; an error-status body still streams to on_chunk but the caller
// checks ok and discards it (an SSE parser finds no content frames in it anyway).
HttpResult http_post_json_stream(const std::string& url,
                                 const std::vector<std::string>& extra_headers,
                                 const std::string& body,
                                 int timeout_ms,
                                 int max_retries,
                                 const std::function<void(std::string_view)>& on_chunk);

}  // namespace starling::net

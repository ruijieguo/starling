#pragma once
#include <cstddef>
#include <cstdint>
#include <functional>
#include <string>
#include <string_view>
#include <vector>

namespace starling::net {

enum class RetryPolicy {
    LegacyCompatible,
    ConnectOnly,
};

enum class ExecutionCertainty {
    NotConnected,
    ResponseReceived,
    Unknown,
};

struct HttpAttemptEvidence {
    std::size_t attempt = 0;
    long http_status = 0;
    int curl_code = 0;
    std::string response_body;
    std::size_t response_bytes = 0;
    std::size_t streamed_bytes = 0;
    std::int64_t elapsed_ms = 0;
    RetryPolicy retry_policy = RetryPolicy::LegacyCompatible;
    ExecutionCertainty execution_certainty = ExecutionCertainty::Unknown;
};

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
    // Actual curl_easy_perform invocations, including bounded retries. Zero
    // means no transport attempt occurred (e.g. curl initialization failed).
    std::size_t attempt_count = 0;
    std::vector<HttpAttemptEvidence> attempts;
};

// POST `body` as application/json with bounded exponential backoff. The
// default preserves the legacy retry set. ConnectOnly retries only explicit
// DNS/proxy-resolution or connection-establishment failures with no HTTP
// response or response bytes. A zero-byte response is not evidence that the
// server did not execute the request.
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

HttpResult http_post_json(const std::string& url,
                          const std::vector<std::string>& extra_headers,
                          const std::string& body,
                          int timeout_ms,
                          int max_retries,
                          RetryPolicy retry_policy);

// Streaming POST: invokes on_chunk(bytes) for each response-body chunk as it
// arrives (for SSE). LegacyCompatible preserves retries for its transport
// error set only until a byte reaches on_chunk. ConnectOnly applies the same
// stricter boundary as the buffered path. HTTP 429/5xx are never retried here.
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

HttpResult http_post_json_stream(const std::string& url,
                                 const std::vector<std::string>& extra_headers,
                                 const std::string& body,
                                 int timeout_ms,
                                 int max_retries,
                                 const std::function<void(std::string_view)>& on_chunk,
                                 RetryPolicy retry_policy);

}  // namespace starling::net

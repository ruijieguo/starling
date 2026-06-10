// test_http_post_json.cpp — shared JSON-POST helper (extracted from the three
// mirrored adapter curl loops). Offline-only checks: the error-string contract
// the adapters map onto their own error styles.

#include "starling/net/http_post_json.hpp"

#include <gtest/gtest.h>

namespace starling::net {

TEST(HttpPostJson, ConnectionRefusedIsTransportError) {
    // 127.0.0.1:1 refuses immediately — fully local, no DNS, no network.
    // COULDNT_CONNECT is retryable, but max_retries=0 returns at once.
    const auto r = http_post_json("http://127.0.0.1:1/v1/x", {}, "{}",
                                  /*timeout_ms=*/2000, /*max_retries=*/0);
    EXPECT_FALSE(r.ok);
    EXPECT_EQ(r.http_code, 0);
    EXPECT_TRUE(r.body.empty());
    EXPECT_EQ(r.error.rfind("transport_error:", 0), 0u) << r.error;
}

TEST(HttpPostJson, RetryableTransportRetriesThenFails) {
    // One retry (1s backoff) against the same refused port still ends in
    // transport_error — pins that exhaustion keeps the transport error string
    // (not "transient_after_retry", which is reserved for HTTP 429/5xx).
    const auto r = http_post_json("http://127.0.0.1:1/v1/x", {}, "{}",
                                  /*timeout_ms=*/2000, /*max_retries=*/1);
    EXPECT_FALSE(r.ok);
    EXPECT_EQ(r.error.rfind("transport_error:", 0), 0u) << r.error;
}

}  // namespace starling::net

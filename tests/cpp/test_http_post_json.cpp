// test_http_post_json.cpp — shared JSON-POST helper (extracted from the three
// mirrored adapter curl loops). Offline-only checks: the error-string contract
// the adapters map onto their own error styles, plus the streaming retry
// invariant (retry allowed ONLY while nothing has streamed).

#include "starling/net/http_post_json.hpp"

#include <gtest/gtest.h>

#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>

#include <atomic>
#include <chrono>
#include <cstdint>
#include <string>
#include <string_view>
#include <thread>

namespace starling::net {

namespace {

// Minimal local HTTP server: every accepted connection gets a 200 response
// whose Content-Length overstates the body, then the socket closes. curl
// delivers the received body bytes to the write callback FIRST, then reports
// CURLE_PARTIAL_FILE — a retryable-class transport code — so this simulates
// "stream torn after bytes flowed". Counts connections so a test can pin that
// no second attempt happens once bytes streamed.
class TruncatingServer {
public:
    TruncatingServer() {
        listen_fd_ = ::socket(AF_INET, SOCK_STREAM, 0);
        sockaddr_in addr{};
        addr.sin_family = AF_INET;
        addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
        addr.sin_port = 0;  // ephemeral
        ::bind(listen_fd_, reinterpret_cast<sockaddr*>(&addr), sizeof(addr));
        socklen_t len = sizeof(addr);
        ::getsockname(listen_fd_, reinterpret_cast<sockaddr*>(&addr), &len);
        port_ = ntohs(addr.sin_port);
        ::listen(listen_fd_, 8);
        worker_ = std::thread([this] { run(); });
    }
    TruncatingServer(const TruncatingServer&) = delete;
    TruncatingServer& operator=(const TruncatingServer&) = delete;
    ~TruncatingServer() { stop(); }

    [[nodiscard]] int port() const { return port_; }
    [[nodiscard]] int connections() const { return count_.load(); }

    void stop() {
        if (stopped_.exchange(true)) {
            return;
        }
        // Wake the blocking accept with a throwaway connection, then join.
        const int wake_fd = ::socket(AF_INET, SOCK_STREAM, 0);
        sockaddr_in addr{};
        addr.sin_family = AF_INET;
        addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
        addr.sin_port = htons(static_cast<std::uint16_t>(port_));
        (void)::connect(wake_fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr));
        ::close(wake_fd);
        worker_.join();
        ::close(listen_fd_);
    }

private:
    void run() {
        while (true) {
            const int conn = ::accept(listen_fd_, nullptr, nullptr);
            if (conn < 0) {
                break;
            }
            if (stopped_.load()) {
                ::close(conn);
                break;
            }
            count_.fetch_add(1);
            char buf[1024];
            (void)::recv(conn, buf, sizeof(buf), 0);  // read (part of) the request
            constexpr std::string_view kResp =
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: text/event-stream\r\n"
                "Content-Length: 64\r\n"
                "\r\n"
                "data: partial\n";
            (void)::send(conn, kResp.data(), kResp.size(), 0);
            // Give curl a moment to deliver the bytes, then cut the stream short.
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
            ::close(conn);
        }
    }

    int listen_fd_ = -1;
    int port_ = 0;
    std::atomic<int> count_{0};
    std::atomic<bool> stopped_{false};
    std::thread worker_;
};

}  // namespace

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

TEST(HttpPostJson, StreamRetriesConnectFailureWhileNothingStreamed) {
    // A connection-establishment failure (refused port → COULDNT_CONNECT, same
    // retryable class as CURLE_SSL_CONNECT_ERROR) streams zero bytes, so the
    // stream path MUST retry it. The 1s backoff sleep is a deterministic lower
    // bound proving a second attempt ran. (Was: single attempt, no retry — a
    // converse turn died on one flaky TLS handshake as
    // "transport_error:SSL connect error".)
    std::string got;
    const auto started = std::chrono::steady_clock::now();
    const auto res = http_post_json_stream(
        "http://127.0.0.1:1/v1/x", {}, "{}",
        /*timeout_ms=*/2000, /*max_retries=*/1,
        [&got](std::string_view chunk) { got.append(chunk); });
    const auto elapsed_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now() - started).count();
    EXPECT_FALSE(res.ok);
    EXPECT_EQ(res.error.rfind("transport_error:", 0), 0u) << res.error;
    EXPECT_TRUE(got.empty());
    EXPECT_GE(elapsed_ms, 1000) << "no backoff sleep → the retry never happened";
}

TEST(HttpPostJson, StreamNeverRetriesOnceBytesStreamed) {
    // The server streams body bytes then tears the connection (Content-Length
    // overstated → CURLE_PARTIAL_FILE, a retryable-class code). Because bytes
    // already reached on_chunk, retrying would duplicate streamed output — the
    // guard must surface the failure after exactly ONE connection even with
    // max_retries budget left.
    TruncatingServer server;
    std::string got;
    const auto res = http_post_json_stream(
        "http://127.0.0.1:" + std::to_string(server.port()) + "/v1/x", {}, "{}",
        /*timeout_ms=*/5000, /*max_retries=*/3,
        [&got](std::string_view chunk) { got.append(chunk); });
    server.stop();
    EXPECT_FALSE(res.ok);
    EXPECT_EQ(res.error.rfind("transport_error:", 0), 0u) << res.error;
    EXPECT_FALSE(got.empty()) << "bytes should have streamed before the tear";
    EXPECT_EQ(server.connections(), 1) << "a second connection = forbidden retry after streaming";
}

}  // namespace starling::net

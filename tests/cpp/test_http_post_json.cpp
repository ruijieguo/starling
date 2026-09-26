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
#include <cerrno>
#include <chrono>
#include <cstdint>
#include <cstring>
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
        if (listen_fd_ < 0) {
            error_ = std::strerror(errno);
            return;
        }
        sockaddr_in addr{};
        addr.sin_family = AF_INET;
        addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
        addr.sin_port = 0;  // ephemeral
        if (::bind(listen_fd_, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) != 0) {
            error_ = std::strerror(errno);
            ::close(listen_fd_);
            listen_fd_ = -1;
            return;
        }
        socklen_t len = sizeof(addr);
        if (::getsockname(listen_fd_, reinterpret_cast<sockaddr*>(&addr), &len) != 0) {
            error_ = std::strerror(errno);
            ::close(listen_fd_);
            listen_fd_ = -1;
            return;
        }
        port_ = ntohs(addr.sin_port);
        if (::listen(listen_fd_, 8) != 0) {
            error_ = std::strerror(errno);
            ::close(listen_fd_);
            listen_fd_ = -1;
            return;
        }
        worker_ = std::thread([this] { run(); });
    }
    TruncatingServer(const TruncatingServer&) = delete;
    TruncatingServer& operator=(const TruncatingServer&) = delete;
    ~TruncatingServer() { stop(); }

    [[nodiscard]] int port() const { return port_; }
    [[nodiscard]] int connections() const { return count_.load(); }
    [[nodiscard]] bool ready() const { return listen_fd_ >= 0; }
    [[nodiscard]] const std::string& error() const { return error_; }

    void stop() {
        if (stopped_.exchange(true)) {
            return;
        }
        if (listen_fd_ < 0) return;
        // Wake the blocking accept with a throwaway connection, then join.
        const int wake_fd = ::socket(AF_INET, SOCK_STREAM, 0);
        sockaddr_in addr{};
        addr.sin_family = AF_INET;
        addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
        addr.sin_port = htons(static_cast<std::uint16_t>(port_));
        (void)::connect(wake_fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr));
        ::close(wake_fd);
        if (worker_.joinable()) worker_.join();
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
    std::string error_;
};

enum class ReplyKind {
    CloseWithoutResponse,
    PartialResponse,
    TooManyRequests,
    ServiceUnavailable,
    HoldUntilTimeout,
};

// A single-behaviour HTTP server used to exercise transport boundaries. It
// counts a request only after receiving the complete POST headers and body.
class ScriptedServer {
public:
    explicit ScriptedServer(ReplyKind reply) : reply_(reply) {
        listen_fd_ = ::socket(AF_INET, SOCK_STREAM, 0);
        if (listen_fd_ < 0) {
            error_ = std::strerror(errno);
            return;
        }
        sockaddr_in addr{};
        addr.sin_family = AF_INET;
        addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
        addr.sin_port = 0;
        if (::bind(listen_fd_, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) != 0) {
            error_ = std::strerror(errno);
            ::close(listen_fd_);
            listen_fd_ = -1;
            return;
        }
        socklen_t len = sizeof(addr);
        if (::getsockname(listen_fd_, reinterpret_cast<sockaddr*>(&addr), &len) != 0) {
            error_ = std::strerror(errno);
            ::close(listen_fd_);
            listen_fd_ = -1;
            return;
        }
        port_ = ntohs(addr.sin_port);
        if (::listen(listen_fd_, 8) != 0) {
            error_ = std::strerror(errno);
            ::close(listen_fd_);
            listen_fd_ = -1;
            return;
        }
        worker_ = std::thread([this] { run(); });
    }

    ScriptedServer(const ScriptedServer&) = delete;
    ScriptedServer& operator=(const ScriptedServer&) = delete;
    ~ScriptedServer() { stop(); }

    [[nodiscard]] bool ready() const { return listen_fd_ >= 0; }
    [[nodiscard]] int port() const { return port_; }
    [[nodiscard]] int requests_read() const { return requests_read_.load(); }
    [[nodiscard]] const std::string& error() const { return error_; }

    void stop() {
        if (stopped_.exchange(true) || listen_fd_ < 0) {
            return;
        }
        const int wake_fd = ::socket(AF_INET, SOCK_STREAM, 0);
        sockaddr_in addr{};
        addr.sin_family = AF_INET;
        addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
        addr.sin_port = htons(static_cast<std::uint16_t>(port_));
        (void)::connect(wake_fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr));
        ::close(wake_fd);
        if (worker_.joinable()) {
            worker_.join();
        }
        ::close(listen_fd_);
    }

private:
    static bool read_complete_request(int conn) {
        std::string request;
        std::size_t expected_size = std::string::npos;
        char buf[1024];
        while (expected_size == std::string::npos || request.size() < expected_size) {
            const ssize_t count = ::recv(conn, buf, sizeof(buf), 0);
            if (count <= 0) {
                return false;
            }
            request.append(buf, static_cast<std::size_t>(count));
            const std::size_t header_end = request.find("\r\n\r\n");
            if (header_end == std::string::npos) {
                continue;
            }
            std::size_t content_length = 0;
            constexpr std::string_view kHeader = "Content-Length:";
            const std::size_t value_pos = request.find(kHeader);
            if (value_pos != std::string::npos && value_pos < header_end) {
                content_length = static_cast<std::size_t>(std::stoul(
                    request.substr(value_pos + kHeader.size(), header_end - value_pos)));
            }
            expected_size = header_end + 4U + content_length;
        }
        return true;
    }

    static void send_response(int conn, std::string_view response) {
        std::size_t sent = 0;
        while (sent < response.size()) {
            const ssize_t count = ::send(conn, response.data() + sent, response.size() - sent, 0);
            if (count <= 0) {
                return;
            }
            sent += static_cast<std::size_t>(count);
        }
    }

    void run() {
        while (true) {
            const int conn = ::accept(listen_fd_, nullptr, nullptr);
            if (conn < 0) {
                return;
            }
            if (stopped_.load()) {
                ::close(conn);
                return;
            }
            if (!read_complete_request(conn)) {
                ::close(conn);
                continue;
            }
            requests_read_.fetch_add(1);
            switch (reply_) {
                case ReplyKind::CloseWithoutResponse:
                    break;
                case ReplyKind::PartialResponse:
                    send_response(conn,
                                  "HTTP/1.1 200 OK\r\nContent-Length: 64\r\nConnection: close\r\n\r\n"
                                  "partial-evidence");
                    break;
                case ReplyKind::TooManyRequests:
                    send_response(conn,
                                  "HTTP/1.1 429 Too Many Requests\r\nContent-Length: 12\r\n"
                                  "Connection: close\r\n\r\nrate-limited");
                    break;
                case ReplyKind::ServiceUnavailable:
                    send_response(conn,
                                  "HTTP/1.1 503 Service Unavailable\r\nContent-Length: 11\r\n"
                                  "Connection: close\r\n\r\nunavailable");
                    break;
                case ReplyKind::HoldUntilTimeout:
                    std::this_thread::sleep_for(std::chrono::milliseconds(250));
                    break;
            }
            ::close(conn);
        }
    }

    ReplyKind reply_;
    int listen_fd_ = -1;
    int port_ = 0;
    std::atomic<int> requests_read_{0};
    std::atomic<bool> stopped_{false};
    std::thread worker_;
    std::string error_;
};

std::string server_url(const ScriptedServer& server) {
    return "http://127.0.0.1:" + std::to_string(server.port()) + "/v1/x";
}

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
    EXPECT_EQ(r.attempt_count, 1);
}

TEST(HttpPostJson, RetryableTransportRetriesThenFails) {
    // One retry (1s backoff) against the same refused port still ends in
    // transport_error — pins that exhaustion keeps the transport error string
    // (not "transient_after_retry", which is reserved for HTTP 429/5xx).
    const auto r = http_post_json("http://127.0.0.1:1/v1/x", {}, "{}",
                                  /*timeout_ms=*/2000, /*max_retries=*/1);
    EXPECT_FALSE(r.ok);
    EXPECT_EQ(r.error.rfind("transport_error:", 0), 0u) << r.error;
    EXPECT_EQ(r.attempt_count, 2);
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
    EXPECT_EQ(res.attempt_count, 2);
}

TEST(HttpPostJson, StreamNeverRetriesOnceBytesStreamed) {
    // The server streams body bytes then tears the connection (Content-Length
    // overstated → CURLE_PARTIAL_FILE, a retryable-class code). Because bytes
    // already reached on_chunk, retrying would duplicate streamed output — the
    // guard must surface the failure after exactly ONE connection even with
    // max_retries budget left.
    TruncatingServer server;
    if (!server.ready()) {
        GTEST_SKIP() << "sandbox does not permit a loopback listener: " << server.error();
    }
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
    EXPECT_EQ(res.attempt_count, 1);
}

TEST(HttpPostJson, UnsupportedProtocolIsOneAttemptDespiteRetryBudget) {
    const auto result = http_post_json("unsupported-starling-test://invalid", {}, "{}", 10, 3);
    EXPECT_FALSE(result.ok);
    EXPECT_EQ(result.attempt_count, 1);
    EXPECT_EQ(result.error.rfind("transport_error:", 0), 0u);
}

TEST(HttpPostJson, ConnectOnlyDoesNotRetryAfterServerReadsRequestWithoutResponse) {
    ScriptedServer server(ReplyKind::CloseWithoutResponse);
    if (!server.ready()) {
        GTEST_SKIP() << "sandbox does not permit a loopback listener: " << server.error();
    }
    const auto result = http_post_json(server_url(server), {}, "{}", 1000, 3,
                                       RetryPolicy::ConnectOnly);
    server.stop();

    ASSERT_EQ(result.attempt_count, 1);
    ASSERT_EQ(result.attempts.size(), 1u);
    EXPECT_EQ(server.requests_read(), 1);
    EXPECT_FALSE(result.ok);
    EXPECT_EQ(result.attempts.front().execution_certainty, ExecutionCertainty::Unknown);
    EXPECT_EQ(result.attempts.front().http_status, 0);
    EXPECT_EQ(result.attempts.front().response_bytes, 0u);
    EXPECT_EQ(result.attempts.front().retry_policy, RetryPolicy::ConnectOnly);
}

TEST(HttpPostJson, ConnectOnlyPreservesPartialResponseEvidenceWithoutRetrying) {
    ScriptedServer server(ReplyKind::PartialResponse);
    if (!server.ready()) {
        GTEST_SKIP() << "sandbox does not permit a loopback listener: " << server.error();
    }
    const auto result = http_post_json(server_url(server), {}, "{}", 1000, 3,
                                       RetryPolicy::ConnectOnly);
    server.stop();

    ASSERT_EQ(result.attempt_count, 1);
    ASSERT_EQ(result.attempts.size(), 1u);
    EXPECT_EQ(server.requests_read(), 1);
    EXPECT_FALSE(result.ok);
    EXPECT_TRUE(result.body.empty()) << "legacy body remains success-only";
    EXPECT_EQ(result.attempts.front().http_status, 200);
    EXPECT_EQ(result.attempts.front().response_body, "partial-evidence");
    EXPECT_EQ(result.attempts.front().response_bytes, 16u);
    EXPECT_EQ(result.attempts.front().streamed_bytes, 0u);
    EXPECT_EQ(result.attempts.front().execution_certainty, ExecutionCertainty::ResponseReceived);
}

TEST(HttpPostJson, ConnectOnlyDoesNotRetryHttp429) {
    ScriptedServer server(ReplyKind::TooManyRequests);
    if (!server.ready()) {
        GTEST_SKIP() << "sandbox does not permit a loopback listener: " << server.error();
    }
    const auto result = http_post_json(server_url(server), {}, "{}", 1000, 3,
                                       RetryPolicy::ConnectOnly);
    server.stop();

    ASSERT_EQ(result.attempts.size(), 1u);
    EXPECT_EQ(result.attempt_count, 1);
    EXPECT_EQ(server.requests_read(), 1);
    EXPECT_EQ(result.http_code, 429);
    EXPECT_EQ(result.attempts.front().http_status, 429);
    EXPECT_EQ(result.attempts.front().curl_code, 0);
    EXPECT_EQ(result.attempts.front().execution_certainty, ExecutionCertainty::ResponseReceived);
}

TEST(HttpPostJson, ConnectOnlyDoesNotRetryHttp503) {
    ScriptedServer server(ReplyKind::ServiceUnavailable);
    if (!server.ready()) {
        GTEST_SKIP() << "sandbox does not permit a loopback listener: " << server.error();
    }
    const auto result = http_post_json(server_url(server), {}, "{}", 1000, 3,
                                       RetryPolicy::ConnectOnly);
    server.stop();

    ASSERT_EQ(result.attempts.size(), 1u);
    EXPECT_EQ(result.attempt_count, 1);
    EXPECT_EQ(server.requests_read(), 1);
    EXPECT_EQ(result.http_code, 503);
    EXPECT_EQ(result.attempts.front().http_status, 503);
}

TEST(HttpPostJson, ConnectOnlyDoesNotRetryTimeoutAfterRequestIsRead) {
    ScriptedServer server(ReplyKind::HoldUntilTimeout);
    if (!server.ready()) {
        GTEST_SKIP() << "sandbox does not permit a loopback listener: " << server.error();
    }
    const auto result = http_post_json(server_url(server), {}, "{}", 50, 3,
                                       RetryPolicy::ConnectOnly);
    server.stop();

    ASSERT_EQ(result.attempts.size(), 1u);
    EXPECT_EQ(result.attempt_count, 1);
    EXPECT_EQ(server.requests_read(), 1);
    EXPECT_EQ(result.attempts.front().execution_certainty, ExecutionCertainty::Unknown);
}

TEST(HttpPostJson, ConnectOnlyRetriesExplicitConnectionFailureWithinBudget) {
    const auto result = http_post_json("http://127.0.0.1:1/v1/x", {}, "{}", 200, 1,
                                       RetryPolicy::ConnectOnly);
    ASSERT_EQ(result.attempts.size(), 2u);
    EXPECT_EQ(result.attempt_count, 2);
    for (std::size_t i = 0; i < result.attempts.size(); ++i) {
        EXPECT_EQ(result.attempts[i].attempt, static_cast<int>(i + 1U));
        EXPECT_NE(result.attempts[i].curl_code, 0);
        EXPECT_EQ(result.attempts[i].execution_certainty, ExecutionCertainty::NotConnected);
        EXPECT_EQ(result.attempts[i].retry_policy, RetryPolicy::ConnectOnly);
        EXPECT_GE(result.attempts[i].elapsed_ms, 0);
    }
}

TEST(HttpPostJson, LegacyCompatibleRemainsTheDefaultPolicy) {
    ScriptedServer server(ReplyKind::ServiceUnavailable);
    if (!server.ready()) {
        GTEST_SKIP() << "sandbox does not permit a loopback listener: " << server.error();
    }
    const auto result = http_post_json(server_url(server), {}, "{}", 1000, 1);
    server.stop();

    ASSERT_EQ(result.attempts.size(), 2u);
    EXPECT_EQ(result.attempt_count, 2);
    EXPECT_EQ(server.requests_read(), 2);
    EXPECT_EQ(result.error, "transient_after_retry");
    EXPECT_EQ(result.attempts.front().retry_policy, RetryPolicy::LegacyCompatible);
}

TEST(HttpPostJson, InvalidConfigIsRejectedBeforeTransportAttempt) {
    const auto zero_timeout = http_post_json("http://127.0.0.1:1/v1/x", {}, "{}", 0, 0,
                                             RetryPolicy::ConnectOnly);
    const auto negative_timeout = http_post_json("http://127.0.0.1:1/v1/x", {}, "{}", -1, 0,
                                                 RetryPolicy::ConnectOnly);
    const auto negative_retries = http_post_json("http://127.0.0.1:1/v1/x", {}, "{}", 1, -1,
                                                 RetryPolicy::ConnectOnly);
    for (const auto* result : {&zero_timeout, &negative_timeout, &negative_retries}) {
        EXPECT_FALSE(result->ok);
        EXPECT_EQ(result->error, "invalid_config");
        EXPECT_EQ(result->attempt_count, 0);
        EXPECT_TRUE(result->attempts.empty());
    }
}

TEST(HttpPostJson, StreamRecordsEveryActualConnectOnlyAttempt) {
    std::string streamed;
    const auto result = http_post_json_stream(
        "http://127.0.0.1:1/v1/x", {}, "{}", 200, 1,
        [&streamed](std::string_view chunk) { streamed.append(chunk); },
        RetryPolicy::ConnectOnly);

    ASSERT_EQ(result.attempts.size(), 2u);
    EXPECT_EQ(result.attempt_count, 2);
    EXPECT_TRUE(streamed.empty());
    EXPECT_EQ(result.attempts[0].attempt, 1);
    EXPECT_EQ(result.attempts[1].attempt, 2);
    EXPECT_EQ(result.attempts[0].streamed_bytes, 0u);
    EXPECT_EQ(result.attempts[1].streamed_bytes, 0u);
}

}  // namespace starling::net

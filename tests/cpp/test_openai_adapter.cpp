#include "starling/extractor/openai_adapter.hpp"

#include <cstdlib>
#include <gtest/gtest.h>
#include <nlohmann/json.hpp>

using starling::extractor::OpenAIAdapter;

TEST(OpenAIAdapterConfigTest, FromEnvReadsBaseUrlAndKey) {
    setenv("OPENAI_BASE_URL", "https://example.test/v1", 1);
    setenv("OPENAI_API_KEY", "sk-test-xyz", 1);
    auto cfg = OpenAIAdapter::Config::from_env();
    EXPECT_EQ(cfg.base_url, "https://example.test/v1");
    EXPECT_EQ(cfg.api_key,  "sk-test-xyz");
    EXPECT_EQ(cfg.model,    "gpt-5.5");
    unsetenv("OPENAI_BASE_URL");
    unsetenv("OPENAI_API_KEY");
}

TEST(OpenAIAdapterConfigTest, FromEnvThrowsWhenKeyMissing) {
    unsetenv("OPENAI_API_KEY");
    EXPECT_THROW(OpenAIAdapter::Config::from_env(), std::runtime_error);
}

TEST(OpenAIAdapterConfigTest, FromEnvDefaultsBaseUrlWhenUnset) {
    unsetenv("OPENAI_BASE_URL");
    setenv("OPENAI_API_KEY", "sk-test-xyz", 1);
    auto cfg = OpenAIAdapter::Config::from_env();
    EXPECT_EQ(cfg.base_url, "https://api.openai.com/v1");
    unsetenv("OPENAI_API_KEY");
}

TEST(OpenAIAdapterConfigTest, JsonObjectOutputDefaultsOff) {
    EXPECT_FALSE(OpenAIAdapter::Config{}.json_object_output);
}

#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>
#include <poll.h>
#include <atomic>
#include <thread>
#include <vector>

namespace {
// Real loopback boundary: captures the bytes sent by the native curl adapter.
// The worker has bounded reads and stops without a dummy model request.
class ChatServer {
public:
    explicit ChatServer(std::string reply, int status = 200) {
        fd_ = ::socket(AF_INET, SOCK_STREAM, 0);
        if (fd_ < 0) return;
        sockaddr_in addr{};
        addr.sin_family = AF_INET;
        addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
        if (::bind(fd_, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) != 0) return;
        socklen_t len = sizeof(addr);
        if (::getsockname(fd_, reinterpret_cast<sockaddr*>(&addr), &len) != 0 ||
            ::listen(fd_, 8) != 0) return;
        port_ = ntohs(addr.sin_port);
        worker_ = std::thread([this, reply = std::move(reply), status] {
            while (!stopped_) {
                pollfd descriptor{fd_, POLLIN, 0};
                if (::poll(&descriptor, 1, 50) <= 0) continue;
                const int conn = ::accept(fd_, nullptr, nullptr);
                if (conn < 0) break;
                timeval timeout{2, 0};
                ::setsockopt(conn, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
                ::setsockopt(conn, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));
                std::string request;
                char buf[4096];
                std::size_t header_end = std::string::npos;
                std::size_t body_size = 0;
                while (true) {
                    const auto n = ::recv(conn, buf, sizeof(buf), 0);
                    if (n <= 0) break;
                    request.append(buf, static_cast<std::size_t>(n));
                    header_end = request.find("\r\n\r\n");
                    if (header_end == std::string::npos) continue;
                    const auto field = request.find("Content-Length: ");
                    if (field != std::string::npos) body_size = std::stoul(request.substr(field + 16));
                    if (request.size() >= header_end + 4 + body_size) break;
                }
                requests_.push_back(request);
                const std::string response = "HTTP/1.1 " + std::to_string(status) +
                    " Test\r\nContent-Type: application/json\r\nContent-Length: " +
                    std::to_string(reply.size()) + "\r\nConnection: close\r\n\r\n" + reply;
                std::size_t sent = 0;
                while (sent < response.size()) {
                    const auto n = ::send(conn, response.data() + sent, response.size() - sent, 0);
                    if (n <= 0) break;
                    sent += static_cast<std::size_t>(n);
                }
                ::close(conn);
            }
        });
    }
    ~ChatServer() { stop(); if (fd_ >= 0) ::close(fd_); }
    void stop() { stopped_ = true; if (worker_.joinable()) worker_.join(); }
    bool ready() const { return port_ != 0; }
    OpenAIAdapter::Config config(bool mode = true) const {
        OpenAIAdapter::Config cfg;
        cfg.base_url = "http://127.0.0.1:" + std::to_string(port_) + "/v1";
        cfg.api_key = "test-local";
        cfg.model = "test-model";
        cfg.max_retries = 0;
        cfg.timeout_ms = 3000;
        cfg.json_object_output = mode;
        return cfg;
    }
    const auto& requests() const { return requests_; } // read only after stop()
    nlohmann::json body(std::size_t i = 0) const {
        const auto& r = requests_.at(i);
        return nlohmann::json::parse(r.substr(r.find("\r\n\r\n") + 4));
    }
private:
    int fd_ = -1;
    int port_ = 0;
    std::atomic<bool> stopped_{false};
    std::thread worker_;
    std::vector<std::string> requests_;
};
std::string completion(std::string content) {
    return nlohmann::json{{"choices", {{{"message", {{"content", content}}}}}},
                          {"usage", {{"prompt_tokens", 3}, {"completion_tokens", 5}, {"total_tokens", 8}}}}.dump();
}
} // namespace

TEST(OpenAIAdapterHttpTest, JsonModeSendsFormatAndPreservesInvalidContent) {
    const std::string raw = " <think>原始推理</think>\n```json\n{\"reason\":\"wrong_time\"}\n```\n解释 ";
    ChatServer server(completion(raw));
    if (!server.ready()) GTEST_SKIP() << "loopback listener not permitted";
    OpenAIAdapter adapter(server.config());
    const auto result = adapter.extract("Return JSON 对象", "opaque-hash");
    server.stop();
    ASSERT_TRUE(result.ok) << result.error;
    EXPECT_EQ(result.raw_xml, raw);
    EXPECT_EQ(result.total_tokens, 8);
    ASSERT_EQ(server.requests().size(), 1u);
    EXPECT_EQ(server.requests()[0].find("POST /v1/chat/completions HTTP/1.1"), 0u);
    const auto body = server.body();
    EXPECT_EQ(body["response_format"], nlohmann::json({{"type", "json_object"}}));
    EXPECT_EQ(body["messages"][0]["content"], "Return JSON 对象");
    EXPECT_EQ(body["model"], "test-model");
    EXPECT_FALSE(body.contains("enable_thinking"));
}

TEST(OpenAIAdapterHttpTest, LegacyExtractionRetainsArrayBehavior) {
    ChatServer server(completion("<think>trace</think>[1,2]"));
    if (!server.ready()) GTEST_SKIP() << "loopback listener not permitted";
    OpenAIAdapter adapter(server.config(false));
    const auto result = adapter.extract("Return JSON array", "");
    server.stop();
    ASSERT_TRUE(result.ok);
    EXPECT_EQ(result.raw_xml, "[1,2]");
    ASSERT_EQ(server.requests().size(), 1u);
    EXPECT_FALSE(server.body().contains("response_format"));
    EXPECT_FALSE(server.body().contains("enable_thinking"));
}

TEST(OpenAIAdapterHttpTest, GenerationIgnoresExtractionJsonMode) {
    ChatServer server(completion("<think>trace</think>Hello"));
    if (!server.ready()) GTEST_SKIP() << "loopback listener not permitted";
    OpenAIAdapter adapter(server.config());
    starling::extractor::LLMAdapter& base = adapter;
    const auto result = base.generate("Say hello");
    server.stop();
    ASSERT_TRUE(result.ok);
    EXPECT_EQ(result.raw_xml, "Hello");
    ASSERT_EQ(server.requests().size(), 1u);
    EXPECT_FALSE(server.body().contains("response_format"));
    EXPECT_FALSE(server.body().contains("enable_thinking"));
}

TEST(OpenAIAdapterHttpTest, StreamingIgnoresExtractionJsonMode) {
    ChatServer server("data: {\"choices\":[{\"delta\":{\"content\":\"Hello\"}}]}\n\ndata: [DONE]\n\n");
    if (!server.ready()) GTEST_SKIP() << "loopback listener not permitted";
    OpenAIAdapter adapter(server.config());
    std::string tokens;
    const auto result = adapter.generate_stream("Say hello", [&](std::string_view part) { tokens += part; });
    server.stop();
    ASSERT_TRUE(result.ok) << result.error;
    EXPECT_EQ(result.raw_xml, "Hello");
    EXPECT_EQ(tokens, "Hello");
    ASSERT_EQ(server.requests().size(), 1u);
    EXPECT_FALSE(server.body().contains("response_format"));
    EXPECT_EQ(server.body()["stream"], true);
    EXPECT_FALSE(server.body().contains("enable_thinking"));
}

TEST(OpenAIAdapterHttpTest, ExplicitThinkingValuesReachExtractionAndGeneration) {
    ChatServer server(completion("Hello"));
    if (!server.ready()) GTEST_SKIP() << "loopback listener not permitted";
    auto enabled = server.config(false);
    enabled.enable_thinking = true;
    OpenAIAdapter extraction(enabled);
    EXPECT_TRUE(extraction.extract("Extract", "hash").ok);
    auto disabled = server.config(false);
    disabled.enable_thinking = false;
    OpenAIAdapter generation(disabled);
    EXPECT_TRUE(generation.generate("Generate").ok);
    server.stop();
    ASSERT_EQ(server.requests().size(), 2u);
    EXPECT_EQ(server.body(0)["enable_thinking"], true);
    EXPECT_EQ(server.body(1)["enable_thinking"], false);
    EXPECT_TRUE(server.body(0)["enable_thinking"].is_boolean());
    EXPECT_TRUE(server.body(1)["enable_thinking"].is_boolean());
}

TEST(OpenAIAdapterHttpTest, ExplicitThinkingValueReachesStream) {
    ChatServer server("data: {\"choices\":[{\"delta\":{\"content\":\"Hello\"}}]}\n\ndata: [DONE]\n\n");
    if (!server.ready()) GTEST_SKIP() << "loopback listener not permitted";
    auto cfg = server.config(false);
    cfg.enable_thinking = false;
    OpenAIAdapter adapter(cfg);
    EXPECT_TRUE(adapter.generate_stream("Generate", [](std::string_view) {}).ok);
    server.stop();
    ASSERT_EQ(server.requests().size(), 1u);
    EXPECT_EQ(server.body()["enable_thinking"], false);
}

TEST(OpenAIAdapterHttpTest, RejectedThinkingValueDoesNotRetryWithoutParameter) {
    ChatServer server(R"({"error":{"message":"unsupported enable_thinking"}})", 400);
    if (!server.ready()) GTEST_SKIP() << "loopback listener not permitted";
    auto cfg = server.config(false);
    cfg.max_retries = 2;
    cfg.enable_thinking = false;
    OpenAIAdapter adapter(cfg);
    const auto response = adapter.generate("Generate");
    server.stop();
    EXPECT_FALSE(response.ok);
    EXPECT_NE(response.error.find("400"), std::string::npos);
    ASSERT_EQ(server.requests().size(), 1u);
    EXPECT_EQ(server.body()["enable_thinking"], false);
}

TEST(OpenAIAdapterHttpTest, RejectedJsonModeNeverFallsBack) {
    ChatServer server(R"({"error":{"message":"unsupported response_format"}})", 400);
    if (!server.ready()) GTEST_SKIP() << "loopback listener not permitted";
    auto cfg = server.config();
    cfg.max_retries = 2;
    OpenAIAdapter adapter(cfg);
    const auto result = adapter.extract("Return JSON", "");
    server.stop();
    EXPECT_FALSE(result.ok);
    EXPECT_TRUE(result.raw_xml.empty());
    EXPECT_NE(result.error.find("400"), std::string::npos);
    ASSERT_EQ(server.requests().size(), 1u);
    EXPECT_EQ(server.body()["response_format"]["type"], "json_object");
}

using namespace starling::extractor;
TEST(OpenAIAdapterStructured, TypedContractsSendDistinctStrictSchemasAndPreserveFailures) {
    auto envelope = nlohmann::json::parse(completion(" <think>raw</think>{}"));
    envelope["choices"][0]["finish_reason"] = "length";
    ChatServer server(envelope.dump());
    if (!server.ready()) GTEST_SKIP() << "loopback listener not permitted";
    OpenAIAdapter adapter(server.config(false));
    for (auto contract : {OutputContractKind::ClaimExtractionV2, OutputContractKind::ClaimAdmissionV1}) {
        auto response = adapter.extract_with_contract("JSON", "hash", {contract, OutputMode::JsonSchemaStrict});
        EXPECT_FALSE(response.ok); EXPECT_TRUE(response.raw_xml.empty());
        EXPECT_EQ(response.error, "completion_truncated");
        EXPECT_EQ(response.raw_completion, " <think>raw</think>{}");
        EXPECT_EQ(response.finish_reason, "length");
        EXPECT_EQ(response.http_attempts.size(), 1u);
    }
    server.stop();
    ASSERT_EQ(server.requests().size(), 2u);
    EXPECT_EQ(server.body(0)["response_format"]["json_schema"]["schema"], nlohmann::json::parse(structured_output_schema(OutputContractKind::ClaimExtractionV2)));
    EXPECT_EQ(server.body(1)["response_format"]["json_schema"]["schema"], nlohmann::json::parse(structured_output_schema(OutputContractKind::ClaimAdmissionV1)));
    EXPECT_FALSE(server.body(0).contains("enable_thinking"));
}
TEST(OpenAIAdapterStructured, ExplicitThinkingValueReachesStructuredCallAndProbe) {
    ChatServer server(completion(R"({"schema_version":2,"statements":[]})"));
    if (!server.ready()) GTEST_SKIP() << "loopback listener not permitted";
    auto cfg = server.config(false);
    cfg.enable_thinking = true;
    OpenAIAdapter adapter(cfg);
    StructuredOutputRequest request{OutputContractKind::ClaimExtractionV2, OutputMode::JsonSchemaStrict};
    EXPECT_TRUE(adapter.extract_with_contract("JSON", "hash", request).ok);
    EXPECT_EQ(adapter.probe_structured_output(request).request_count, 2u);
    server.stop();
    ASSERT_EQ(server.requests().size(), 3u);
    for (std::size_t i = 0; i < 3; ++i) {
        EXPECT_EQ(server.body(i)["enable_thinking"], true);
        EXPECT_EQ(server.body(i)["response_format"]["type"], "json_schema");
    }
}
TEST(OpenAIAdapterStructured, ModeConflictNeverSendsRequest) {
    ChatServer server(completion("{}"));
    if (!server.ready()) GTEST_SKIP() << "loopback listener not permitted";
    OpenAIAdapter adapter(server.config(true));
    const auto response = adapter.extract_with_contract("JSON", "", {OutputContractKind::ClaimExtractionV2, OutputMode::JsonSchemaStrict});
    server.stop();
    EXPECT_EQ(response.error, "structured_output_configuration_conflict");
    EXPECT_TRUE(server.requests().empty());
}
TEST(OpenAIAdapterStructured, ExplicitRefusalRetainsRawHttpAndNeverSucceeds) {
    auto envelope = nlohmann::json::parse(completion(""));
    envelope["choices"][0]["message"]["content"] = nullptr;
    envelope["choices"][0]["message"]["refusal"] = "cannot comply";
    ChatServer server(envelope.dump());
    if (!server.ready()) GTEST_SKIP() << "loopback listener not permitted";
    OpenAIAdapter adapter(server.config(false));
    const auto response = adapter.extract_with_contract("JSON", "", {OutputContractKind::ClaimAdmissionV1, OutputMode::JsonObject});
    EXPECT_FALSE(response.ok); EXPECT_TRUE(response.refusal);
    EXPECT_EQ(response.error, "completion_refusal");
    EXPECT_EQ(response.raw_http_response, envelope.dump());
}
TEST(OpenAIAdapterCapability, TwoFixturesCacheSingleFlightExpireAndClear) {
    ChatServer server(completion(R"({"schema_version":2,"statements":[]})"));
    if (!server.ready()) GTEST_SKIP() << "loopback listener not permitted";
    std::atomic<long> now{0};
    OpenAIAdapter adapter(server.config(false), [&now] { return std::chrono::steady_clock::time_point(std::chrono::seconds(now.load())); });
    StructuredOutputRequest request{OutputContractKind::ClaimExtractionV2, OutputMode::JsonSchemaStrict};
    std::vector<CapabilityEvidence> results(6);
    std::vector<std::thread> workers;
    for (std::size_t i = 0; i < results.size(); ++i) workers.emplace_back([&, i] { results[i] = adapter.probe_structured_output(request); });
    for (auto& worker : workers) worker.join();
    for (const auto& result : results) {
        EXPECT_EQ(result.state, CapabilityState::ObservedConformant);
        EXPECT_EQ(result.request_count, 2u);
        EXPECT_EQ(result.evidence_id, results.front().evidence_id);
        EXPECT_EQ(capability_evidence_json(result).find("test-local"), std::string::npos);
        EXPECT_TRUE(validate_capability_evidence_json(capability_evidence_json(result)).empty());
        auto tampered=nlohmann::json::parse(capability_evidence_json(result));
        tampered["probes"][0]["response"]["raw_completion"]="changed";
        EXPECT_FALSE(validate_capability_evidence_json(tampered.dump()).empty());
    }
    now = 599;
    EXPECT_EQ(adapter.probe_structured_output(request).evidence_id, results.front().evidence_id);
    now = 600;
    EXPECT_NE(adapter.probe_structured_output(request).evidence_id, results.front().evidence_id);
    adapter.clear_structured_output_capabilities();
    EXPECT_EQ(adapter.probe_structured_output(request).state, CapabilityState::ObservedConformant);
    const auto normal = adapter.extract_with_contract("JSON", "", request);
    EXPECT_FALSE(normal.capability_evidence_id.empty());
    server.stop();
    ASSERT_EQ(server.requests().size(), 7u);
    EXPECT_NE(server.body(0)["messages"][0]["content"], server.body(1)["messages"][0]["content"]);
}
TEST(OpenAIAdapterCapability, ClassifiesUnsupportedTemporaryAndNonconformantWithoutRetry) {
    struct Case { std::string reply; int status; CapabilityState state; bool cached; };
    for (const auto& test : std::vector<Case>{
        {R"({"error":{"message":"response_format json_schema is not supported"}})", 400, CapabilityState::Unsupported, true},
        {R"({"error":{"message":"bad request"}})", 400, CapabilityState::Unknown, false},
        {R"({"error":{"message":"unauthorized"}})", 401, CapabilityState::Unknown, false},
        {R"({"error":{"message":"busy"}})", 503, CapabilityState::Unknown, false},
        {completion("```json\n{}\n``` explanation"), 200, CapabilityState::Nonconformant, true},
        {completion(R"({"schema_version":2,"schema_version":2,"statements":[]})"), 200, CapabilityState::Nonconformant, true}}) {
        ChatServer server(test.reply, test.status);
        if (!server.ready()) GTEST_SKIP() << "loopback listener not permitted";
        auto cfg = server.config(false); cfg.max_retries = 3;
        OpenAIAdapter adapter(cfg);
        StructuredOutputRequest request{OutputContractKind::ClaimExtractionV2, OutputMode::JsonObject};
        const auto first = adapter.probe_structured_output(request);
        const auto second = adapter.probe_structured_output(request);
        EXPECT_EQ(first.state, test.state) << test.reply;
        EXPECT_EQ(second.state, test.state);
        server.stop();
        EXPECT_EQ(server.requests().size(), test.cached ? 2u : 4u) << test.reply;
    }
}
TEST(OpenAIAdapterCapability, ModeAndContractHaveSeparateCacheKeys) {
    ChatServer server(completion(R"({"schema_version":2,"statements":[]})"));
    if (!server.ready()) GTEST_SKIP() << "loopback listener not permitted";
    OpenAIAdapter adapter(server.config(false));
    EXPECT_EQ(adapter.probe_structured_output({OutputContractKind::ClaimExtractionV2, OutputMode::JsonObject}).state, CapabilityState::ObservedConformant);
    EXPECT_EQ(adapter.probe_structured_output({OutputContractKind::ClaimExtractionV2, OutputMode::JsonSchemaStrict}).state, CapabilityState::ObservedConformant);
    EXPECT_EQ(adapter.probe_structured_output({OutputContractKind::ClaimAdmissionV1, OutputMode::JsonSchemaStrict}).state, CapabilityState::Nonconformant);
    server.stop();
    EXPECT_EQ(server.requests().size(), 6u);
}

TEST(OpenAIAdapterHttpTest, LegacyAndGenerationRejectIncompleteOrRefusedCompletions) {
    for (const auto& reason : {"length", "content_filter", "refusal"}) {
        auto envelope=nlohmann::json::parse(completion("partial answer"));
        envelope["choices"][0]["finish_reason"]=reason==std::string("refusal")?"stop":reason;
        if (reason==std::string("refusal")) envelope["choices"][0]["message"]["refusal"]="refused";
        ChatServer server(envelope.dump());
        if (!server.ready()) GTEST_SKIP() << "loopback listener not permitted";
        OpenAIAdapter adapter(server.config(false));
        for (bool generate : {false,true}) {
            SCOPED_TRACE(std::string(reason)+(generate?" generate":" extract"));
            auto response=generate?adapter.generate("reply"):adapter.extract("reply","");
            EXPECT_FALSE(response.ok);
            EXPECT_TRUE(response.raw_xml.empty());
            EXPECT_EQ(response.error,reason==std::string("length")?"completion_truncated":"completion_refusal");
            EXPECT_EQ(response.raw_completion,"partial answer");
            EXPECT_EQ(response.total_tokens,8);
            EXPECT_EQ(response.http_attempts.size(),1u);
        }
        server.stop();
        EXPECT_EQ(server.requests().size(),2u);
    }
}

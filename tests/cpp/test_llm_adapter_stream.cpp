#include <gtest/gtest.h>

#include "starling/extractor/fake_llm_adapter.hpp"
#include "starling/extractor/llm_adapter.hpp"

#include <string>
#include <vector>

// #37 streaming contract (LLMAdapter::generate_stream). converse() always calls
// generate_stream; these pin the adapter-level surface that the binding + WS
// relay sits on. converse threading + the pybind GIL sink are covered in
// tests/python/test_dashboard_converse_stream.py (heavy setup lives there).

namespace starling::extractor {
namespace {

// Streaming-capable stub: emits the reply in fixed chunks via on_token and
// returns the accumulated reply + usage — exactly what a real SSE adapter does.
class StubStreamingAdapter : public LLMAdapter {
public:
    explicit StubStreamingAdapter(std::vector<std::string> chunks)
        : chunks_(std::move(chunks)) {}

    LLMResponse extract(std::string_view /*prompt*/, std::string_view /*hash*/) override {
        return {};  // unused on the streaming path
    }

    LLMResponse generate_stream(std::string_view /*prompt*/, const TokenSink& on_token) override {
        std::string full;
        for (const auto& chunk : chunks_) {
            if (on_token) {
                on_token(chunk);
            }
            full += chunk;
        }
        LLMResponse resp;
        resp.ok = true;
        resp.raw_xml = full;
        resp.total_tokens = 7;
        return resp;
    }

private:
    std::vector<std::string> chunks_;
};

std::vector<std::string> collect(LLMAdapter& adapter) {
    std::vector<std::string> got;
    adapter.generate_stream("prompt",
                            [&](std::string_view delta) { got.emplace_back(delta); });
    return got;
}

}  // namespace

TEST(GenerateStream, StreamingAdapterEmitsDeltasInOrderAndAccumulates) {
    StubStreamingAdapter adapter({"Hel", "lo ", "world"});
    std::vector<std::string> got;
    const auto resp = adapter.generate_stream(
        "prompt", [&](std::string_view delta) { got.emplace_back(delta); });
    EXPECT_EQ(got, (std::vector<std::string>{"Hel", "lo ", "world"}));
    EXPECT_TRUE(resp.ok);
    EXPECT_EQ(resp.raw_xml, "Hello world");  // returned reply == concat of deltas
    EXPECT_EQ(resp.total_tokens, 7);
}

TEST(GenerateStream, BaseDefaultEmitsWholeReplyOnce) {
    // FakeLLMAdapter does not override generate_stream → base default emits the
    // whole reply as ONE delta. This is how non-streaming (incl. real adapters
    // before their SSE override) degrade: streaming still works, one big chunk.
    FakeLLMAdapter adapter;
    adapter.set_default_response(LLMResponse{.raw_xml = "the whole reply", .ok = true});
    const auto got = collect(adapter);
    ASSERT_EQ(got.size(), 1U);
    EXPECT_EQ(got[0], "the whole reply");
}

TEST(GenerateStream, EmptySinkIsNoStreamButStillReturnsFullReply) {
    FakeLLMAdapter adapter;
    adapter.set_default_response(LLMResponse{.raw_xml = "reply", .ok = true});
    const auto resp = adapter.generate_stream("prompt", {});  // empty sink = no streaming
    EXPECT_TRUE(resp.ok);
    EXPECT_EQ(resp.raw_xml, "reply");  // caller still gets the complete reply
}

TEST(GenerateStream, FailedResponseEmitsNoDelta) {
    FakeLLMAdapter adapter;  // no response set → ok=false
    const auto got = collect(adapter);
    EXPECT_TRUE(got.empty());  // base default emits only when ok
}

}  // namespace starling::extractor

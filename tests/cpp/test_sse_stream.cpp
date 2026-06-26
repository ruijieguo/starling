#include <gtest/gtest.h>

#include "starling/extractor/sse_stream.hpp"

#include <cstddef>
#include <string>
#include <string_view>
#include <vector>

// #37-SSE: the StreamAccumulator is the testable core of real streaming — it
// turns raw OpenAI/Anthropic SSE bytes into content deltas + usage, independent
// of the network. These canned streams + byte-split feeds pin parsing, line
// reassembly across chunk boundaries, and degradation on malformed lines, with
// no API key required.

namespace starling::extractor::sse {
namespace {

struct Run {
    std::string text;
    std::vector<std::string> deltas;
    int prompt = 0;
    int completion = 0;
    int total = 0;
};

// Feed `body` to a fresh accumulator in fixed-size chunks (chunk_size==1 makes
// every JSON line straddle many feed() calls), capturing the deltas emitted.
Run run_stream(Provider provider, const std::string& body, std::size_t chunk_size) {
    std::vector<std::string> deltas;
    StreamAccumulator acc(provider,
                          [&deltas](std::string_view piece) { deltas.emplace_back(piece); });
    for (std::size_t off = 0; off < body.size(); off += chunk_size) {
        acc.feed(std::string_view(body).substr(off, chunk_size));
    }
    return {acc.text(), deltas, acc.prompt_tokens(), acc.completion_tokens(), acc.total_tokens()};
}

const std::string kOpenAi =
    R"(data: {"choices":[{"delta":{"content":"Hel"}}]})" "\n\n"
    R"(data: {"choices":[{"delta":{"content":"lo"}}]})" "\n\n"
    R"(data: {"choices":[{"delta":{"content":" world"}}]})" "\n\n"
    R"(data: {"choices":[],"usage":{"prompt_tokens":10,"completion_tokens":3,"total_tokens":13}})" "\n\n"
    "data: [DONE]\n\n";

const std::string kAnthropic =
    "event: message_start\n"
    R"(data: {"type":"message_start","message":{"usage":{"input_tokens":12,"output_tokens":1}}})" "\n\n"
    "event: content_block_delta\n"
    R"(data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Hel"}})" "\n\n"
    "event: content_block_delta\n"
    R"(data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"lo"}})" "\n\n"
    "event: message_delta\n"
    R"(data: {"type":"message_delta","usage":{"output_tokens":2}})" "\n\n"
    "event: message_stop\n"
    R"(data: {"type":"message_stop"})" "\n\n";

}  // namespace

TEST(SseStream, OpenAiAssemblesTextDeltasAndUsage) {
    const auto run = run_stream(Provider::OpenAI, kOpenAi, 4096);
    EXPECT_EQ(run.text, "Hello world");
    EXPECT_EQ(run.deltas, (std::vector<std::string>{"Hel", "lo", " world"}));
    EXPECT_EQ(run.prompt, 10);
    EXPECT_EQ(run.completion, 3);
    EXPECT_EQ(run.total, 13);
}

TEST(SseStream, AnthropicAssemblesTextDeltasAndUsage) {
    const auto run = run_stream(Provider::Anthropic, kAnthropic, 4096);
    EXPECT_EQ(run.text, "Hello");
    EXPECT_EQ(run.deltas, (std::vector<std::string>{"Hel", "lo"}));
    EXPECT_EQ(run.prompt, 12);
    EXPECT_EQ(run.completion, 2);
    EXPECT_EQ(run.total, 14);  // no explicit total → input + output
}

TEST(SseStream, OpenAiSurvivesByteSplitChunks) {
    const auto run = run_stream(Provider::OpenAI, kOpenAi, 1);  // 1-byte chunks
    EXPECT_EQ(run.text, "Hello world");
    EXPECT_EQ(run.total, 13);
}

TEST(SseStream, AnthropicSurvivesByteSplitChunks) {
    const auto run = run_stream(Provider::Anthropic, kAnthropic, 1);
    EXPECT_EQ(run.text, "Hello");
    EXPECT_EQ(run.completion, 2);
}

TEST(SseStream, MalformedAndNonDataLinesSkipped) {
    std::vector<std::string> deltas;
    StreamAccumulator acc(Provider::OpenAI,
                          [&deltas](std::string_view piece) { deltas.emplace_back(piece); });
    acc.feed("data: not json{\n");                                          // garbage payload
    acc.feed(": a comment line\n");                                         // SSE comment
    acc.feed("event: ping\n");                                              // non-data field
    acc.feed(R"(data: {"choices":[{"delta":{"content":"ok"}}]})" "\n");     // valid
    EXPECT_EQ(acc.text(), "ok");
    EXPECT_EQ(deltas, (std::vector<std::string>{"ok"}));
}

}  // namespace starling::extractor::sse

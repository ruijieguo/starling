// Unit tests for strip_reasoning_trace: removing <think>...</think> traces so the
// extraction parsers see only the JSON answer. Without this, a reasoning model's
// trace (which contains '[' / '{') defeats the first-bracket scan in extract_array
// and json_parser, yielding zero extracted statements (the reason production had to
// disable thinking for extraction). Thinking extraction is materially more accurate
// on long multi-room stories, so we strip the trace instead of suppressing thinking.
#include "starling/extractor/reasoning_trace.hpp"

#include <gtest/gtest.h>

#include <string>

using starling::extractor::strip_reasoning_trace;

namespace {

TEST(ReasoningTrace, NoTraceIsUnchanged) {
    EXPECT_EQ(strip_reasoning_trace(R"([{"a":1}])"), R"([{"a":1}])");
}

TEST(ReasoningTrace, StripsCompleteTraceContainingBrackets) {
    // The trace's own '[' would otherwise be the first bracket the array-extractor
    // grabs — this is the exact failure that zeroed out thinking extraction.
    EXPECT_EQ(strip_reasoning_trace("<think>the cast is [Emily, Bob]</think>\n[{\"x\":1}]"),
              "\n[{\"x\":1}]");
}

TEST(ReasoningTrace, EmptyTraceFromNoThinkDirectiveIsRemoved) {
    // A /no_think directive still emits an empty <think></think> pair.
    EXPECT_EQ(strip_reasoning_trace("<think></think>[1,2]"), "[1,2]");
}

TEST(ReasoningTrace, TruncatedTraceLeftForBestEffort) {
    // No closing tag (token budget exhausted mid-thought): nothing to recover, leave
    // the text for the best-effort parser to drop.
    EXPECT_EQ(strip_reasoning_trace("<think>unterminated reasoning"),
              "<think>unterminated reasoning");
}

TEST(ReasoningTrace, StripsMultipleTraces) {
    EXPECT_EQ(strip_reasoning_trace("<think>a</think>X<think>b</think>Y"), "XY");
}

}  // namespace

#pragma once

#include "starling/extractor/llm_adapter.hpp"

#include <cstdint>
#include <string>
#include <string_view>
#include <utility>

#include <nlohmann/json_fwd.hpp>

namespace starling::extractor::sse {

// Which provider's server-sent-event JSON shape a stream carries.
//   OpenAI    : data: {"choices":[{"delta":{"content":"…"}}], "usage":{…}?}
//               terminal "data: [DONE]"; usage only when stream_options
//               .include_usage=true (arrives in a final choices=[] chunk).
//   Anthropic : event-typed frames in the data JSON's "type":
//               message_start (message.usage.input_tokens),
//               content_block_delta (delta.text — the token),
//               message_delta (usage.output_tokens), message_stop.
enum class Provider : std::uint8_t { OpenAI, Anthropic };

// Assembles a streaming chat completion from raw HTTP body chunks. feed() is
// called once per HTTP chunk (bytes split arbitrarily — a JSON line may straddle
// two chunks); it line-buffers, parses each `data:` payload per the provider's
// shape, invokes on_token(delta) for every content delta as it arrives, and
// accumulates the full reply text + token usage.
//
// feed() must not throw — it runs inside libcurl's write callback. It never does
// at runtime: a malformed line or partial JSON is skipped via nlohmann's
// non-throwing parse + find()/is_*() typed guards (no value()/at()/get() that
// could throw on a type mismatch). It is not marked noexcept because the
// guarantee is by construction, not a contract the caller should depend on.
// Results are valid once the stream ends; text() always holds whatever was
// received so far (so a truncated stream still yields the partial reply).
class StreamAccumulator {
public:
    StreamAccumulator(Provider provider, TokenSink on_token)
        : provider_(provider), on_token_(std::move(on_token)) {}

    void feed(std::string_view bytes);

    [[nodiscard]] const std::string& text() const noexcept { return text_; }
    [[nodiscard]] int prompt_tokens() const noexcept { return prompt_tokens_; }
    [[nodiscard]] int completion_tokens() const noexcept { return completion_tokens_; }
    // Falls back to prompt+completion when the provider never sent an explicit total.
    [[nodiscard]] int total_tokens() const noexcept;

private:
    void consume_line(std::string_view line);
    void consume_openai(const nlohmann::json& doc);     // choices[].delta.content + usage
    void consume_anthropic(const nlohmann::json& doc);  // content_block_delta / message_*

    Provider provider_;
    TokenSink on_token_;
    std::string buf_;    // partial-line carry-over across feed() calls
    std::string text_;   // accumulated reply
    int prompt_tokens_     = 0;
    int completion_tokens_ = 0;
    int total_tokens_      = 0;  // explicit total when the provider sends one (OpenAI usage)
};

}  // namespace starling::extractor::sse

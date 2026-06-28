#pragma once

#include <string>
#include <string_view>

namespace starling::extractor {

// Reasoning models (Qwen3 family, etc.) prepend a <think>...</think> trace to their
// output. The extraction parsers (episodic extract_array, belief json_parser) locate
// the payload by scanning for the first '[' or '{' — but a reasoning trace routinely
// contains those characters (e.g. "the cast is [Emily, Bob]"), so the parser grabs a
// fragment of the trace instead of the answer and the extraction silently yields zero
// statements. Strip every complete trace before the response reaches a parser.
//
// A trace with no closing tag (the model hit the token budget mid-thought) is left
// intact: there is no answer to recover, so the best-effort parser drops it anyway.
[[nodiscard]] inline std::string strip_reasoning_trace(std::string text) {
    static constexpr std::string_view kOpenTag = "<think>";
    static constexpr std::string_view kCloseTag = "</think>";
    std::string::size_type open_pos = text.find(kOpenTag);
    while (open_pos != std::string::npos) {
        const std::string::size_type close_pos = text.find(kCloseTag, open_pos);
        if (close_pos == std::string::npos) {
            break;  // truncated trace: no answer to recover, leave for best-effort parse
        }
        text.erase(open_pos, (close_pos + kCloseTag.size()) - open_pos);
        open_pos = text.find(kOpenTag, open_pos);
    }
    return text;
}

}  // namespace starling::extractor

#include "starling/extractor/sse_stream.hpp"

#include <cstddef>
#include <string>

#include <nlohmann/json.hpp>

namespace starling::extractor::sse {

namespace {

// Non-throwing field reads: find() + is_*() guards, so a wrong-typed or missing
// field never throws (unlike value()/at()/operator[]/get on a mismatch). This is
// what lets feed() run safely inside libcurl's write callback.
std::string str_field(const nlohmann::json& obj, const char* key) {
    const auto iter = obj.find(key);
    if (iter != obj.end() && iter->is_string()) {
        return iter->get<std::string>();
    }
    return {};
}

int int_field(const nlohmann::json& obj, const char* key, int fallback) {
    const auto iter = obj.find(key);
    if (iter != obj.end() && iter->is_number_integer()) {
        return iter->get<int>();
    }
    return fallback;
}

}  // namespace

void StreamAccumulator::feed(std::string_view bytes) {
    buf_.append(bytes);
    std::size_t start = 0;
    for (;;) {
        const std::size_t newline = buf_.find('\n', start);
        if (newline == std::string::npos) {
            break;
        }
        consume_line(std::string_view(buf_).substr(start, newline - start));
        start = newline + 1;
    }
    buf_.erase(0, start);  // keep the partial trailing line for the next feed()
}

void StreamAccumulator::consume_line(std::string_view line) {
    if (!line.empty() && line.back() == '\r') {
        line.remove_suffix(1);  // tolerate CRLF
    }
    constexpr std::string_view kData = "data:";
    if (!line.starts_with(kData)) {
        return;  // event: / id: / comment / blank — not a data payload
    }
    std::string_view payload = line.substr(kData.size());
    if (!payload.empty() && payload.front() == ' ') {
        payload.remove_prefix(1);
    }
    if (payload == "[DONE]") {
        return;  // OpenAI terminal sentinel
    }

    const auto doc = nlohmann::json::parse(payload, nullptr, /*allow_exceptions=*/false);
    if (doc.is_discarded() || !doc.is_object()) {
        return;  // partial/garbage line — skip
    }
    if (provider_ == Provider::OpenAI) {
        consume_openai(doc);
    } else {
        consume_anthropic(doc);
    }
}

void StreamAccumulator::consume_openai(const nlohmann::json& doc) {
    const auto choices = doc.find("choices");
    if (choices != doc.end() && choices->is_array() && !choices->empty()) {
        const auto& first = (*choices)[0];
        const auto delta_iter = first.is_object() ? first.find("delta") : first.end();
        if (first.is_object() && delta_iter != first.end() && delta_iter->is_object()) {
            const std::string piece = str_field(*delta_iter, "content");
            if (!piece.empty()) {
                text_ += piece;
                if (on_token_) {
                    on_token_(piece);
                }
            }
        }
    }
    const auto usage = doc.find("usage");
    if (usage != doc.end() && usage->is_object()) {
        prompt_tokens_     = int_field(*usage, "prompt_tokens", prompt_tokens_);
        completion_tokens_ = int_field(*usage, "completion_tokens", completion_tokens_);
        total_tokens_      = int_field(*usage, "total_tokens", total_tokens_);
    }
}

void StreamAccumulator::consume_anthropic(const nlohmann::json& doc) {
    const std::string type = str_field(doc, "type");
    if (type == "content_block_delta") {
        const auto delta_iter = doc.find("delta");
        if (delta_iter != doc.end() && delta_iter->is_object()
                && str_field(*delta_iter, "type") == "text_delta") {
            const std::string piece = str_field(*delta_iter, "text");
            if (!piece.empty()) {
                text_ += piece;
                if (on_token_) {
                    on_token_(piece);
                }
            }
        }
    } else if (type == "message_start") {
        const auto message = doc.find("message");
        if (message != doc.end() && message->is_object()) {
            const auto usage = message->find("usage");
            if (usage != message->end() && usage->is_object()) {
                prompt_tokens_ = int_field(*usage, "input_tokens", prompt_tokens_);
            }
        }
    } else if (type == "message_delta") {
        const auto usage = doc.find("usage");
        if (usage != doc.end() && usage->is_object()) {
            completion_tokens_ = int_field(*usage, "output_tokens", completion_tokens_);
        }
    }
}

int StreamAccumulator::total_tokens() const noexcept {
    if (total_tokens_ > 0) {
        return total_tokens_;
    }
    return prompt_tokens_ + completion_tokens_;
}

}  // namespace starling::extractor::sse

#include "starling/cognizer/alias_normalizer.hpp"

#include <cctype>
#include <string>

namespace starling::cognizer {

namespace {

bool is_ascii_whitespace(unsigned char c) {
    return c == ' ' || c == '\t' || c == '\n' || c == '\r'
        || c == '\v' || c == '\f';
}

}  // namespace

std::string normalize_alias(std::string_view raw) {
    // 1) trim leading + trailing ASCII whitespace
    std::size_t start = 0;
    while (start < raw.size() && is_ascii_whitespace(static_cast<unsigned char>(raw[start]))) ++start;
    std::size_t end = raw.size();
    while (end > start && is_ascii_whitespace(static_cast<unsigned char>(raw[end - 1]))) --end;

    std::string out;
    out.reserve(end - start);

    // 2) collapse internal whitespace runs; 3) ASCII case-fold
    bool prev_ws = false;
    for (std::size_t i = start; i < end; ++i) {
        const unsigned char c = static_cast<unsigned char>(raw[i]);
        if (is_ascii_whitespace(c)) {
            if (!prev_ws) {
                out.push_back(' ');
                prev_ws = true;
            }
        } else {
            // ASCII letters: fold to lower. Non-ASCII bytes pass through.
            if (c >= 'A' && c <= 'Z') {
                out.push_back(static_cast<char>(c + ('a' - 'A')));
            } else {
                out.push_back(static_cast<char>(c));
            }
            prev_ws = false;
        }
    }
    return out;
}

}  // namespace starling::cognizer

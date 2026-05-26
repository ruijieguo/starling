#pragma once

#include <string>
#include <string_view>

namespace starling::cognizer {

// Normalize an alias for matching: trim leading/trailing whitespace,
// collapse runs of internal whitespace to single space, ASCII case-fold
// (CJK / non-ASCII bytes pass through unchanged).
//
// Storage convention: cognizers.aliases_json keeps RAW strings (audit),
// cognizers.aliases_normalized_json keeps the normalize_alias output.
// Lookup compares normalize_alias(query) to entries of
// aliases_normalized_json.
std::string normalize_alias(std::string_view raw);

}  // namespace starling::cognizer

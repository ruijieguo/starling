#pragma once
#include "starling/cognizer/cognizer_hub.hpp"
#include <string>
#include <string_view>
namespace starling::cognizer {
// Remove ALL internal ASCII whitespace + lowercase (stronger than normalize_alias,
// which keeps a single internal space). Used to register a space-folded alias so
// "Xiao Hong" and "XiaoHong" resolve to one entity.
std::string fold_internal_spaces(std::string_view s);
// Write-side: resolve surface to its canonical display name (first-seen surface),
// registering a new entity (kind=human) on miss. Best-effort: returns the raw
// surface on any error. Reuses CognizerHub (cognizers table); the Hub's writes
// join the caller's open transaction (it manages none of its own).
std::string resolve_or_register_cognizer(CognizerHub& hub, std::string_view tenant,
                                         std::string_view surface);
// Query-side: resolve to canonical name if known; passthrough (no register) on miss.
std::string resolve_cognizer(CognizerHub& hub, std::string_view tenant,
                             std::string_view surface);
}  // namespace starling::cognizer

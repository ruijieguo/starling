#pragma once
#include <string>
#include <string_view>
namespace starling::schema {
// Deterministic theme-surface normalization for grounding. Runs BEFORE
// canonicalize_object (which is unchanged). Lowercases, strips a leading article
// (the/a/an), and conservatively singularizes. Applied ONLY to entity/string
// theme object_values (NOT numbers/datetimes/refs). Idempotent.
std::string normalize_theme(std::string_view surface);
}  // namespace starling::schema

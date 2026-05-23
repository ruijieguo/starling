#pragma once

#include <cstdint>
#include <string>
#include <string_view>

namespace starling::extractor {

// extraction_span_key per docs/design/subsystems_design/05_bus.md §5.
// P1 normalized_span = chunk_index. We inline canonical_object_hash
// (already a sha256 hex string from M0.1 canonicalize_object) instead of
// rehashing the canonical string; this keeps the key stable across
// canonical_object_hash_version bumps as long as the underlying hash is
// stable. Field separator is ASCII unit separator (\x1f), matching
// compute_idempotency_key in bus_event.cpp.
std::string compute_extraction_span_key(
    std::string_view engram_ref_id,
    std::int32_t     chunk_index,
    std::string_view predicate,
    std::string_view canonical_object_hash);

}  // namespace starling::extractor

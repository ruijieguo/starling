#pragma once

#include "starling/extractor/extracted_statement.hpp"

#include <string>

namespace starling::bus {

// canonical_conflict_key_hex: sha256 hex of 7-tuple joined by \x1f US separator.
//
// Tuple fields (in order):
//   1. holder_id
//   2. modality (BELIEVES|KNOWS|ASSUMES|DOUBTS|DESIRES|INTENDS|COMMITS|
//                PREFERS|NORM_OUGHT|NORM_FORBID|RECANTED)
//   3. subject_kind ":" subject_id
//   4. predicate
//   5. canonical_object_hash (pre-computed by M0.1 canonicalize_object during extraction)
//   6. normalize_interval(valid_from, valid_to, event_time_start).canonical_bytes()
//   7. canonical_scope_bytes(scope_of(stmt))
//
// Return value: 64 lowercase hex chars. Locked C++/Python parity is asserted by
// tests/cpp/test_conflict_key.cpp (PARITY_HEX) and tests/python/test_conflict_key.py.
std::string canonical_conflict_key_hex(
    const starling::extractor::ExtractedStatement& stmt);

}  // namespace starling::bus

// canonicalize_object v1 — C++ mirror of python/starling/schema/value.py.
//
// Must produce byte-identical output to the Python implementation; M0.5
// ConflictProbe indexes Statement.canonical_object_hash and any divergence
// silently splits identical-content writes into separate hash buckets.
#pragma once

#include <array>
#include <chrono>
#include <cstdint>
#include <string>
#include <variant>

namespace starling::schema {

struct CanonicalRefInput {
    std::string class_name;                        // e.g. "CognizerRef"
    std::array<std::uint8_t, 16> uuid_bytes;       // raw 16 UUID bytes
};

using CanonicalInput = std::variant<
    bool,
    std::int64_t,
    double,
    std::string,
    std::chrono::sys_seconds,                       // tz-aware UTC seconds (caller pre-converts)
    CanonicalRefInput
>;

struct CanonicalResult {
    std::string canonical;
    std::string sha256_hex;                         // 64 lowercase hex chars
};

// Throws std::invalid_argument with "schema_invalid: ..." on NaN/Inf.
CanonicalResult canonicalize_object(const CanonicalInput& v);

}  // namespace starling::schema

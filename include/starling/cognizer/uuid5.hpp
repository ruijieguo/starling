#pragma once

#include <string>
#include <string_view>

namespace starling::cognizer {

// RFC 4122 §4.3: SHA-1(namespace_bytes || name) → take first 16 bytes,
// set version=5 nibble, variant=10xx bits. Returns lowercase hex with
// dashes in 8-4-4-4-12 layout (36 chars total).
//
// `namespace_uuid_str` is a 36-char dashed UUID string (e.g. the
// kStarlingCognizerNamespace constant from version.hpp).
//
// `name` is the input being namespaced. For cognizer ids:
//   compose_name = std::string(kind_str) + "\x1f" + external_id
// where the US (\x1f) separator matches the project's existing
// idempotency_key composition (see src/bus/bus_event.cpp).
std::string compute_uuid5(std::string_view namespace_uuid_str,
                           std::string_view name);

}  // namespace starling::cognizer

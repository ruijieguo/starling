#pragma once

#define STARLING_VERSION_MAJOR 0
#define STARLING_VERSION_MINOR 0
#define STARLING_VERSION_PATCH 1
#define STARLING_VERSION_STRING "0.0.1"

#include <string_view>

namespace starling {

// UUID5 namespace for cognizer ids. Computed once with:
//   uuid.uuid5(uuid.NAMESPACE_DNS, "starling-cognizer-v1")
// in Python (RFC 4122 §4.3 standard derivation). Frozen here as a
// project-wide constant. Changing this value invalidates every
// cognizer.id in production storage; do NOT modify after P2.a release.
inline constexpr std::string_view kStarlingCognizerNamespace =
    "aacf67e8-1495-5cef-ac22-dd0bd73dd1af";

}  // namespace starling

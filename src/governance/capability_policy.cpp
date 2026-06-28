#include "starling/governance/capability_policy.hpp"

#include <algorithm>

namespace starling::governance {

std::vector<std::string> required_capabilities(bool embedded) {
  std::vector<std::string> result;
  result.reserve(kLocalStoreRequired.size());
  for (const auto cap : kLocalStoreRequired) {
    const bool deferred =
        std::ranges::find(kEmbeddedDeferredCaps, cap) != kEmbeddedDeferredCaps.end();
    if (embedded && deferred) {
      continue;
    }
    result.emplace_back(cap);
  }
  return result;
}

}  // namespace starling::governance

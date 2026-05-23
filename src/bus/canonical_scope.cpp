#include "starling/bus/canonical_scope.hpp"
#include <stdexcept>

namespace starling::bus {

std::string CanonicalScopeNorm::canonical_bytes() const {
    throw std::logic_error("CanonicalScopeNorm::canonical_bytes not implemented in M0.5");
}

std::string CanonicalScopeCommitment::canonical_bytes() const {
    throw std::logic_error("CanonicalScopeCommitment::canonical_bytes not implemented in M0.5");
}

std::string CanonicalScopeCommonGround::canonical_bytes() const {
    throw std::logic_error("CanonicalScopeCommonGround::canonical_bytes not implemented in M0.5");
}

std::string canonical_scope_bytes(const CanonicalScope& scope) {
    return std::visit([](const auto& arm) { return arm.canonical_bytes(); }, scope);
}

}  // namespace starling::bus

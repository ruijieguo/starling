#pragma once

#include <string>
#include <variant>
#include <vector>

namespace starling::extractor { struct ExtractedStatement; }

namespace starling::bus {

// M0.5: only Null is constructed. Norm/Commitment/CommonGround arms are declared
// for API stability; their construction is not implemented until M0.5+1.
struct CanonicalScopeNull {
    std::string canonical_bytes() const { return ""; }
    bool operator==(const CanonicalScopeNull&) const = default;
};

struct CanonicalScopeNorm {
    std::string kind;
    std::vector<std::string> members_sorted;
    std::string canonical_bytes() const;
    bool operator==(const CanonicalScopeNorm&) const = default;
};

struct CanonicalScopeCommitment {
    std::string principal;
    std::string beneficiary;
    std::string canonical_bytes() const;
    bool operator==(const CanonicalScopeCommitment&) const = default;
};

struct CanonicalScopeCommonGround {
    std::vector<std::string> parties_sorted;
    std::string canonical_bytes() const;
    bool operator==(const CanonicalScopeCommonGround&) const = default;
};

using CanonicalScope = std::variant<
    CanonicalScopeNull,
    CanonicalScopeNorm,
    CanonicalScopeCommitment,
    CanonicalScopeCommonGround>;

std::string canonical_scope_bytes(const CanonicalScope& scope);

// scope_of: derive the canonical scope from an ExtractedStatement (P2.j).
// modality 优先：COMMITS→Commitment；NORM_*→Norm；else scope_parties≥2→CommonGround；else Null。
CanonicalScope scope_of(const starling::extractor::ExtractedStatement& stmt);

}  // namespace starling::bus

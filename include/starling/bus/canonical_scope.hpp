#pragma once

#include <string>
#include <variant>
#include <vector>

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

// scope_of: derive the canonical scope from an ExtractedStatement.
// M0.5: always returns CanonicalScopeNull{}.
// M0.5+1: will inspect stmt.statement_kind to branch.
template <typename StmtT>
CanonicalScope scope_of(const StmtT& /*stmt*/) {
    return CanonicalScopeNull{};
}

}  // namespace starling::bus

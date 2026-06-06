#include "starling/bus/canonical_scope.hpp"

#include "starling/extractor/extracted_statement.hpp"
#include "starling/schema/statement_enums.hpp"

#include <algorithm>

namespace starling::bus {

// "kind\x1fmemberA\x1fmemberB"（kind 前缀 + 每个 member 前导 \x1f）。
std::string CanonicalScopeNorm::canonical_bytes() const {
    std::string out = kind;
    for (const auto& m : members_sorted) { out += '\x1f'; out += m; }
    return out;
}

// "principal\x1fbeneficiary"。
std::string CanonicalScopeCommitment::canonical_bytes() const {
    return principal + '\x1f' + beneficiary;
}

// "partyA\x1fpartyB\x1f..."（纯 join，无前缀；故用 first 标志免首个前导 \x1f）。
std::string CanonicalScopeCommonGround::canonical_bytes() const {
    std::string out;
    bool first = true;
    for (const auto& p : parties_sorted) { if (!first) out += '\x1f'; out += p; first = false; }
    return out;
}

std::string canonical_scope_bytes(const CanonicalScope& scope) {
    return std::visit([](const auto& arm) { return arm.canonical_bytes(); }, scope);
}

CanonicalScope scope_of(const starling::extractor::ExtractedStatement& stmt) {
    using M = schema::Modality;
    if (stmt.modality == M::COMMITS) {
        std::string beneficiary;
        for (const auto& p : stmt.scope_parties) {
            if (p != stmt.holder_id) { beneficiary = p; break; }
        }
        return CanonicalScopeCommitment{stmt.holder_id, beneficiary};
    }
    if (stmt.modality == M::NORM_OUGHT || stmt.modality == M::NORM_FORBID) {
        std::vector<std::string> members{stmt.holder_id, stmt.subject_id};
        std::sort(members.begin(), members.end());
        const std::string kind = (stmt.modality == M::NORM_OUGHT) ? "obligation" : "prohibition";
        return CanonicalScopeNorm{kind, members};
    }
    if (stmt.scope_parties.size() >= 2) {
        std::vector<std::string> parties = stmt.scope_parties;
        std::sort(parties.begin(), parties.end());
        return CanonicalScopeCommonGround{parties};
    }
    return CanonicalScopeNull{};
}

}  // namespace starling::bus

#include "starling/evidence/engram.hpp"
#include "starling/crypto/sha256.hpp"

#include <set>
#include <string>
#include <string_view>
#include <vector>

namespace starling::evidence {

std::string canonicalize_engram_payload(
    const std::vector<std::uint8_t>& payload_bytes,
    const std::vector<std::string>& declared_transformations) {

    // Deduplicate + sort transformations so producer tuple order doesn't change
    // the hash. A set is the right shape semantically.
    const std::set<std::string> sorted_unique(
        declared_transformations.begin(), declared_transformations.end());

    std::string out;
    out.reserve(3 + payload_bytes.size() + 64);  // v1\x1f + payload + \x1f + transforms
    out.append("v1\x1f");
    out.append(reinterpret_cast<const char*>(payload_bytes.data()),
               payload_bytes.size());
    out.push_back('\x1f');

    bool first = true;
    for (const auto& t : sorted_unique) {
        if (!first) out.push_back('\x1f');
        out.append(t);
        first = false;
    }
    return out;
}

std::string compute_engram_content_hash(
    const std::vector<std::uint8_t>& payload_bytes,
    const std::vector<std::string>& declared_transformations) {
    return starling::crypto::sha256_hex(
        canonicalize_engram_payload(payload_bytes, declared_transformations));
}

}  // namespace starling::evidence

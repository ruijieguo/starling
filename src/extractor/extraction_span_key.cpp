#include "starling/extractor/extraction_span_key.hpp"

#include "starling/crypto/sha256.hpp"

#include <string>

namespace starling::extractor {

std::string compute_extraction_span_key(
        std::string_view engram_ref_id,
        std::int32_t     chunk_index,
        std::string_view predicate,
        std::string_view canonical_object_hash) {
    static constexpr char kSep = '\x1f';
    std::string canonical;
    canonical.reserve(engram_ref_id.size() + 16 + predicate.size()
                      + canonical_object_hash.size() + 4);
    canonical.append(engram_ref_id);
    canonical.push_back(kSep);
    canonical.append(std::to_string(chunk_index));
    canonical.push_back(kSep);
    canonical.append(predicate);
    canonical.push_back(kSep);
    canonical.append(canonical_object_hash);
    return starling::crypto::sha256_hex(canonical);
}

}  // namespace starling::extractor

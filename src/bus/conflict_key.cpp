#include "starling/bus/conflict_key.hpp"

#include "starling/bus/canonical_scope.hpp"
#include "starling/bus/normalized_interval.hpp"
#include "starling/crypto/sha256.hpp"
#include "starling/schema/statement_enums.hpp"

#include <string>

namespace starling::bus {

namespace {

constexpr char kSep = '\x1f';

// All-caps enum-name spelling for each Modality value. Mirrors the Python
// StrEnum .name attribute so C++/Python conflict keys match byte-for-byte.
std::string modality_str(starling::schema::Modality m) {
    using M = starling::schema::Modality;
    switch (m) {
        case M::BELIEVES:    return "BELIEVES";
        case M::KNOWS:       return "KNOWS";
        case M::ASSUMES:     return "ASSUMES";
        case M::DOUBTS:      return "DOUBTS";
        case M::DESIRES:     return "DESIRES";
        case M::INTENDS:     return "INTENDS";
        case M::COMMITS:     return "COMMITS";
        case M::PREFERS:     return "PREFERS";
        case M::NORM_OUGHT:  return "NORM_OUGHT";
        case M::NORM_FORBID: return "NORM_FORBID";
        case M::RECANTED:    return "RECANTED";
        case M::OCCURRED:    return "OCCURRED";
    }
    return "UNKNOWN_MODALITY";
}

}  // namespace

std::string canonical_conflict_key_hex(
    const starling::extractor::ExtractedStatement& stmt)
{
    auto interval = normalize_interval(stmt.valid_from, stmt.valid_to, stmt.event_time_start);
    auto scope    = scope_of(stmt);
    const std::string scope_bytes    = canonical_scope_bytes(scope);
    const std::string interval_bytes = interval.canonical_bytes();
    const std::string mod            = modality_str(stmt.modality);

    std::string blob;
    blob.reserve(
        stmt.holder_id.size() + 1 +
        mod.size() + 1 +
        stmt.subject_kind.size() + 1 + stmt.subject_id.size() + 1 +
        stmt.predicate.size() + 1 +
        stmt.canonical_object_hash.size() + 1 +
        interval_bytes.size() + 1 +
        scope_bytes.size() + 1);
    blob += stmt.holder_id;             blob += kSep;
    blob += mod;                        blob += kSep;
    blob += stmt.subject_kind;          blob += ':'; blob += stmt.subject_id; blob += kSep;
    blob += stmt.predicate;             blob += kSep;
    blob += stmt.canonical_object_hash; blob += kSep;
    blob += interval_bytes;             blob += kSep;
    blob += scope_bytes;                blob += kSep;
    return starling::crypto::sha256_hex(blob);
}

}  // namespace starling::bus

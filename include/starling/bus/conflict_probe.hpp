#pragma once

#include "starling/bus/normalized_interval.hpp"
#include "starling/extractor/extracted_statement.hpp"
#include "starling/persistence/connection.hpp"

#include <optional>
#include <string>
#include <string_view>

namespace starling::bus {

enum class ConflictKind {
    DirectContradiction,
    Superseding,
    MildCorrection,  // §15.3.1: same polarity, same object, non-severe — bump confidence + history
    PartialOverlap,
    Adjacent,
};

std::string_view to_string(ConflictKind k);

struct ConflictMatch {
    ConflictKind  kind;
    std::string   matched_statement_id;
    std::string   matched_tenant_id;
    std::string   matched_supersedes_root_id;             // = COALESCE(supersedes_id, id) of S_old
    std::string   matched_canonical_object_hash_version;  // version recorded on S_old
    double        matched_confidence = 0.0;
    std::string   conflict_key_hex;                        // canonical_conflict_key_hex(s_new)
};

// ConflictProbe is a pure-detection component. Read-only SQL against
// `statements`. Returns the strongest candidate (severity:
// DirectContradiction > Superseding > PartialOverlap > Adjacent) or nullopt.
//
// Clamps:
//   - UNKNOWN_INTERVAL on either side -> max severity = PartialOverlap
//   - Cross-version hash match (different canonical_object_hash_version) -> max severity = PartialOverlap
//   - Either side's confidence < kThetaSevere (0.6) -> max severity = PartialOverlap
//
// Bus::write owns all DB mutations (Task 7 partial_overlap/adjacent edges,
// Task 8 SUPERSEDES atomic transaction). ConflictProbe never writes.
class ConflictProbe {
public:
    static constexpr double kThetaSevere = 0.6;

    explicit ConflictProbe(starling::persistence::Connection& conn) : conn_(conn) {}

    std::optional<ConflictMatch> scan(
        const starling::extractor::ExtractedStatement& s_new,
        const NormalizedInterval& interval_new) const;

private:
    starling::persistence::Connection& conn_;
};

}  // namespace starling::bus

#pragma once

#include <optional>
#include <string>

namespace starling::bus {

// Canonical closed-open interval [valid_from, valid_to) for conflict detection.
// UNKNOWN_INTERVAL is the sentinel when both valid_from and event_time are absent.
// UNKNOWN_INTERVAL participates only in low-confidence partial_overlap;
// it MUST NOT trigger direct_contradiction.
//
// canonical_bytes() format: "UNKNOWN" | "<from>/OPEN" | "<from>/<to>"
// Invariant: an empty `to` is treated as open-ended regardless of `to_is_open`.
struct NormalizedInterval {
    bool        is_unknown = false;
    std::string from;       // ISO-8601 UTC; empty iff is_unknown
    std::string to;         // ISO-8601 UTC; empty means open-ended
    bool        to_is_open = false;

    std::string canonical_bytes() const;

    bool operator==(const NormalizedInterval&) const = default;
};

inline const NormalizedInterval UNKNOWN_INTERVAL =
    NormalizedInterval{.is_unknown = true, .from = "", .to = "", .to_is_open = false};

NormalizedInterval normalize_interval(
    const std::optional<std::string>& valid_from,
    const std::optional<std::string>& valid_to,
    const std::optional<std::string>& event_time);

}  // namespace starling::bus

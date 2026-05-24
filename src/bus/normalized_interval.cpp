#include "starling/bus/normalized_interval.hpp"

namespace starling::bus {

std::string NormalizedInterval::canonical_bytes() const {
    if (is_unknown) return "UNKNOWN";
    if (to_is_open || to.empty()) return from + "/OPEN";
    return from + "/" + to;
}

NormalizedInterval normalize_interval(
    const std::optional<std::string>& valid_from,
    const std::optional<std::string>& valid_to,
    const std::optional<std::string>& event_time)
{
    if (valid_from.has_value()) {
        NormalizedInterval ni;
        ni.is_unknown = false;
        ni.from       = *valid_from;
        if (valid_to.has_value()) {
            ni.to         = *valid_to;
            ni.to_is_open = false;
        } else {
            ni.to         = "";
            ni.to_is_open = true;
        }
        return ni;
    }
    if (event_time.has_value()) {
        NormalizedInterval ni;
        ni.is_unknown = false;
        ni.from       = *event_time;
        ni.to         = "";
        ni.to_is_open = true;
        return ni;
    }
    return UNKNOWN_INTERVAL;
}

}  // namespace starling::bus

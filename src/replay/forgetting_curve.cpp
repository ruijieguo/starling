#include "starling/replay/forgetting_curve.hpp"
#include <chrono>
#include <cmath>
#include <cstdio>
#include <ctime>
#include <string>

namespace starling::replay {
namespace {
constexpr double kBase = 86400.0;

double parse_iso_epoch(std::string_view iso) {
    std::tm tm{};
    int y, mo, d, h, mi, s;
    if (std::sscanf(std::string(iso).c_str(), "%d-%d-%dT%d:%d:%dZ",
                    &y, &mo, &d, &h, &mi, &s) != 6) return 0.0;
    tm.tm_year = y - 1900; tm.tm_mon = mo - 1; tm.tm_mday = d;
    tm.tm_hour = h; tm.tm_min = mi; tm.tm_sec = s;
    return static_cast<double>(timegm(&tm));
}
}  // namespace

double decay_modifier_by_modality(std::string_view modality) {
    if (modality == "COMMITS" || modality == "commits")       return 4.0;
    if (modality == "NORM_OUGHT" || modality == "norm_ought") return 3.0;
    if (modality == "KNOWS" || modality == "knows")           return 2.0;
    if (modality == "BELIEVES" || modality == "believes")     return 1.0;
    if (modality == "ASSUMES" || modality == "assumes")       return 0.5;
    return 1.0;
}

double compute_s0(const ForgettingInputs& in) {
    return kBase
        * (1.0 + 0.5 * static_cast<double>(in.access_count))
        * (1.0 + in.salience)
        * (1.0 + 2.0 * (in.active_grounded ? 1.0 : 0.0))
        * decay_modifier_by_modality(in.modality)
        * (1.0 + 0.3 * std::abs(in.affect_valence));
}

double compute_s_t(const ForgettingInputs& in, std::string_view now_iso) {
    const double s0 = compute_s0(in);
    if (s0 <= 0.0) return 0.0;
    const double dt = parse_iso_epoch(now_iso) - parse_iso_epoch(in.last_accessed_iso);
    if (dt <= 0.0) return 1.0;
    return std::exp(-dt / s0);
}

double seconds_until_retrievability(const ForgettingInputs& in, double target) {
    const double s0 = compute_s0(in);
    if (s0 <= 0.0) return -1.0;
    if (target <= 0.0 || target >= 1.0) return -1.0;
    // S(t)=exp(-Δt/S0)=target → Δt = -S0·ln(target), measured from last_accessed.
    return -s0 * std::log(target);
}

}  // namespace starling::replay

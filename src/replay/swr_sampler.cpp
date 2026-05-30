#include "starling/replay/swr_sampler.hpp"
#include <cstdio>
#include <ctime>
#include <string>

namespace starling::replay {
namespace {
double parse_iso_epoch(std::string_view iso) {
    if (iso.empty()) return 0.0;
    std::tm tm{}; int y,mo,d,h,mi,s;
    if (std::sscanf(std::string(iso).c_str(), "%d-%d-%dT%d:%d:%dZ",
                    &y,&mo,&d,&h,&mi,&s) != 6) return 0.0;
    tm.tm_year=y-1900; tm.tm_mon=mo-1; tm.tm_mday=d;
    tm.tm_hour=h; tm.tm_min=mi; tm.tm_sec=s;
    return static_cast<double>(timegm(&tm));
}
double novelty_decay(std::string_view last_replayed, std::string_view now) {
    if (last_replayed.empty()) return 1.0;
    const double dt = parse_iso_epoch(now) - parse_iso_epoch(last_replayed);
    return dt > 86400.0 ? 1.0 : 0.5 + 0.5 * (dt / 86400.0);
}
}  // namespace

double provenance_factor(std::string_view p) {
    if (p == "user_input")   return 1.0;
    if (p == "tom_inferred") return 0.25;
    return 0.0;
}

double sample_weight(const SamplerInputs& in, const SamplerConfig& cfg,
                     std::string_view now_iso) {
    const double pf = provenance_factor(in.provenance);
    if (pf == 0.0) return 0.0;
    if (in.derived_depth >= 3) return 0.0;
    if (!in.last_replayed_iso.empty() && !in.has_conflict) {
        const double dt = parse_iso_epoch(now_iso) - parse_iso_epoch(in.last_replayed_iso);
        if (dt < cfg.cooldown_minutes * 60.0) return 0.0;
    }
    double w = in.salience
        * novelty_decay(in.last_replayed_iso, now_iso)
        * (in.has_conflict ? (1.0 + cfg.conflict_bonus) : 1.0)
        * (1.0 + cfg.arousal_bonus * in.affect_arousal)
        * (in.goal_relevant ? 1.5 : 1.0)
        * pf
        / (1.0 + static_cast<double>(in.replay_count));
    return w < cfg.w_min ? 0.0 : w;
}

}  // namespace starling::replay

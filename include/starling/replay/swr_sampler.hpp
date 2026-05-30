#pragma once
#include <string>
#include <string_view>

namespace starling::replay {

struct SamplerInputs {
    double salience = 0.0;
    std::string last_replayed_iso;
    bool has_conflict = false;
    double affect_arousal = 0.0;
    bool goal_relevant = false;
    std::string provenance;
    int64_t replay_count = 0;
    int derived_depth = 0;
};

struct SamplerConfig {
    double conflict_bonus = 0.5;
    double arousal_bonus = 0.4;
    double w_min = 0.01;
    int cooldown_minutes = 5;
};

double provenance_factor(std::string_view provenance);
double sample_weight(const SamplerInputs& in, const SamplerConfig& cfg,
                     std::string_view now_iso);

}  // namespace starling::replay

#pragma once
#include <string>
#include <string_view>

namespace starling::replay {

struct ForgettingInputs {
    double salience = 0.0;
    int64_t access_count = 0;
    bool active_grounded = false;
    std::string modality;
    double affect_valence = 0.0;
    std::string last_accessed_iso;
};

double compute_s0(const ForgettingInputs& in);
double compute_s_t(const ForgettingInputs& in, std::string_view now_iso);
double decay_modifier_by_modality(std::string_view modality);

}  // namespace starling::replay

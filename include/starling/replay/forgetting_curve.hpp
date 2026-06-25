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

// Inverse of S(t)=exp(-Δt/S0): seconds from last_accessed until retrievability
// reaches `target`. The curve's inverse is curve semantics too — it lives here
// (not reimplemented in any binding layer) so a forecast stays DRY against the
// formula above. Returns -1.0 when S0<=0 or target is outside (0,1).
double seconds_until_retrievability(const ForgettingInputs& in, double target);

}  // namespace starling::replay

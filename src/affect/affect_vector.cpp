#include "starling/affect/affect_vector.hpp"
#include <cmath>
#include <nlohmann/json.hpp>

namespace starling::affect {

double salience(const AffectVector& v, double surprise_decay) {
    using std::abs;
    return (0.4 + 0.6 * abs((double)v.valence))
         * (0.4 + 0.6 * v.arousal)
         * (0.3 + 0.7 * v.novelty)
         * (0.3 + 0.7 * v.stakes)
         * (0.6 + 0.4 * surprise_decay);
}

namespace {
// Clamp to [lo, hi] and sanitize non-finite (NaN/inf) values to 0. A malformed
// affect_json (e.g. {"valence":1e308}) must not produce a non-finite salience,
// which would poison every downstream salience-weighted computation.
float clamp_finite(float x, float lo, float hi) {
    if (!std::isfinite(x)) return 0.0f;
    if (x < lo) return lo;
    if (x > hi) return hi;
    return x;
}
}  // namespace

AffectVector parse_affect_json(std::string_view json) {
    try {
        auto j = nlohmann::json::parse(json);
        AffectVector v;
        // Documented ranges (affect_vector.hpp): valence/dominance [-1,1];
        // arousal/novelty/stakes [0,1].
        v.valence   = clamp_finite(j.value("valence",   0.0f), -1.0f, 1.0f);
        v.arousal   = clamp_finite(j.value("arousal",   0.0f),  0.0f, 1.0f);
        v.dominance = clamp_finite(j.value("dominance", 0.0f), -1.0f, 1.0f);
        v.novelty   = clamp_finite(j.value("novelty",   0.0f),  0.0f, 1.0f);
        v.stakes    = clamp_finite(j.value("stakes",    0.0f),  0.0f, 1.0f);
        return v;
    } catch (...) {
        return AffectVector{};
    }
}

}  // namespace starling::affect

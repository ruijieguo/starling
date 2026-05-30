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

AffectVector parse_affect_json(std::string_view json) {
    try {
        auto j = nlohmann::json::parse(json);
        AffectVector v;
        v.valence   = j.value("valence",   0.0f);
        v.arousal   = j.value("arousal",   0.0f);
        v.dominance = j.value("dominance", 0.0f);
        v.novelty   = j.value("novelty",   0.0f);
        v.stakes    = j.value("stakes",    0.0f);
        return v;
    } catch (...) {
        return AffectVector{};
    }
}

}  // namespace starling::affect

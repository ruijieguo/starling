#include "starling/vector/pattern_separator.hpp"

#include "starling/vector/vector_math.hpp"

#include <algorithm>

namespace starling::vector {

SeparationResult separate(
    const std::vector<float>& e,
    const std::vector<std::pair<std::string, std::vector<float>>>& neighbors,
    double theta_sep, double strength)
{
    SeparationResult res;
    double max_sim = 0.0;
    for (const auto& [id, nv] : neighbors)
        max_sim = std::max(max_sim, cosine(e, nv));

    if (neighbors.empty() || max_sim <= theta_sep) {
        res.index_vector = normalize(e);
        return res;
    }

    // Gram-Schmidt: 对各归一化邻居去分量
    std::vector<float> v_perp = e;
    for (const auto& [id, nv] : neighbors) {
        auto nhat = normalize(nv);
        double proj = 0.0;
        for (size_t i = 0; i < e.size(); ++i) proj += double(e[i]) * nhat[i];
        for (size_t i = 0; i < v_perp.size(); ++i)
            v_perp[i] -= float(proj * nhat[i]);
    }
    std::vector<float> offset(e.size());
    for (size_t i = 0; i < e.size(); ++i)
        offset[i] = float(e[i] + strength * v_perp[i]);
    res.index_vector = normalize(offset);

    for (const auto& [id, nv] : neighbors)
        res.overlaps.emplace_back(id, cosine(e, nv));
    return res;
}

}  // namespace starling::vector

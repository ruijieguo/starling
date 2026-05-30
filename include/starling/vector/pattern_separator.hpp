#pragma once
#include <string>
#include <utility>
#include <vector>

namespace starling::vector {

struct SeparationResult {
    std::vector<float> index_vector;                       // 归一化后
    std::vector<std::pair<std::string, double>> overlaps;  // (neighbor_id, similarity)
};

// neighbors: 已有邻居的 (stmt_id, index_vector)。
// max_sim > theta_sep 时 Gram-Schmidt 反相似偏移 + 建软边;否则直接归一化。
SeparationResult separate(
    const std::vector<float>& e,
    const std::vector<std::pair<std::string, std::vector<float>>>& neighbors,
    double theta_sep, double strength);

}  // namespace starling::vector

#pragma once
#include <cstdint>
#include <string>
#include <vector>

namespace starling::vector {

// cosine ∈ [-1,1]; 任一零向量或尺寸不一致返回 0。
double cosine(const std::vector<float>& a, const std::vector<float>& b);

// float32 little-endian 紧凑序列化 ↔ BLOB（std::string 当字节容器）。
std::string  to_blob(const std::vector<float>& v);
std::vector<float> from_blob(const std::string& blob);

// 归一化（零向量原样返回）。
std::vector<float> normalize(const std::vector<float>& v);

}  // namespace starling::vector

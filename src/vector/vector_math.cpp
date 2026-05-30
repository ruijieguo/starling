#include "starling/vector/vector_math.hpp"

#include <cmath>
#include <cstring>

namespace starling::vector {

double cosine(const std::vector<float>& a, const std::vector<float>& b) {
    if (a.size() != b.size() || a.empty()) return 0.0;
    double dot = 0, na = 0, nb = 0;
    for (size_t i = 0; i < a.size(); ++i) {
        dot += double(a[i]) * b[i];
        na  += double(a[i]) * a[i];
        nb  += double(b[i]) * b[i];
    }
    if (na == 0 || nb == 0) return 0.0;
    return dot / (std::sqrt(na) * std::sqrt(nb));
}

std::string to_blob(const std::vector<float>& v) {
    std::string out;
    out.resize(v.size() * sizeof(float));
    std::memcpy(out.data(), v.data(), out.size());  // little-endian host (x86/arm64)
    return out;
}

std::vector<float> from_blob(const std::string& blob) {
    std::vector<float> v(blob.size() / sizeof(float));
    std::memcpy(v.data(), blob.data(), v.size() * sizeof(float));
    return v;
}

std::vector<float> normalize(const std::vector<float>& v) {
    double n = 0;
    for (float x : v) n += double(x) * x;
    if (n == 0) return v;
    const double inv = 1.0 / std::sqrt(n);
    std::vector<float> out(v.size());
    for (size_t i = 0; i < v.size(); ++i) out[i] = float(v[i] * inv);
    return out;
}

}  // namespace starling::vector

#include "starling/embedding/embedding_adapter.hpp"

#include <random>
#include <string>

#include "starling/vector/vector_math.hpp"

namespace starling::embedding {

EmbeddingResult StubEmbeddingAdapter::embed(std::string_view text) {
    if (!fail_text_.empty() && text == fail_text_) {
        fail_text_.clear();
        throw EmbeddingError("stub forced failure");
    }

    std::mt19937 rng(static_cast<std::mt19937::result_type>(
        std::hash<std::string_view>{}(text)));
    std::uniform_real_distribution<float> dist(-1.0f, 1.0f);

    std::vector<float> vec;
    vec.reserve(static_cast<std::size_t>(dim_));
    for (int i = 0; i < dim_; ++i) {
        vec.push_back(dist(rng));
    }

    return {vector::normalize(vec), dim_, "stub"};
}

}  // namespace starling::embedding

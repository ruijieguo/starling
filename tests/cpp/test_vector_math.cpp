#include "starling/vector/vector_math.hpp"

#include <gtest/gtest.h>

using namespace starling::vector;

TEST(VectorMath, CosineIdentityAndOrthogonal) {
    EXPECT_NEAR(cosine({1, 0, 0}, {1, 0, 0}), 1.0, 1e-6);
    EXPECT_NEAR(cosine({1, 0, 0}, {0, 1, 0}), 0.0, 1e-6);
    EXPECT_NEAR(cosine({1, 0, 0}, {0, 0, 0}), 0.0, 1e-6);  // 零向量
}

TEST(VectorMath, BlobRoundTrip) {
    std::vector<float> v{0.1f, -2.5f, 3.14159f, 0.0f};
    auto back = from_blob(to_blob(v));
    ASSERT_EQ(back.size(), v.size());
    for (size_t i = 0; i < v.size(); ++i) EXPECT_FLOAT_EQ(back[i], v[i]);
}

TEST(VectorMath, NormalizeUnitLength) {
    auto n = normalize({3, 4});
    EXPECT_NEAR(n[0], 0.6, 1e-6);
    EXPECT_NEAR(n[1], 0.8, 1e-6);
}

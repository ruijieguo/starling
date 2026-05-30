#include "starling/vector/pattern_separator.hpp"

#include "starling/vector/vector_math.hpp"

#include <gtest/gtest.h>

using namespace starling::vector;

TEST(PatternSeparator, NoNeighborsJustNormalize) {
    auto r = separate({3, 4}, {}, 0.85, 0.5);
    EXPECT_TRUE(r.overlaps.empty());
    EXPECT_NEAR(r.index_vector[0], 0.6, 1e-6);
}

TEST(PatternSeparator, BelowThresholdNoOffset) {
    // e 与邻居正交 → max_sim=0 < 0.85 → 直接归一化,无软边
    auto r = separate({1, 0, 0}, {{"n1", {0, 1, 0}}}, 0.85, 0.5);
    EXPECT_TRUE(r.overlaps.empty());
    EXPECT_NEAR(cosine(r.index_vector, {1, 0, 0}), 1.0, 1e-6);
}

TEST(PatternSeparator, AboveThresholdOffsetsAwayAndBuildsEdge) {
    // e 与邻居高度相似 → 偏移后远离邻居 + 建软边
    std::vector<float> nb{1, 0, 0};
    auto r = separate({0.99f, 0.14f, 0.0f}, {{"n1", nb}}, 0.85, 1.0);
    ASSERT_EQ(r.overlaps.size(), 1u);
    EXPECT_EQ(r.overlaps[0].first, "n1");
    EXPECT_GT(r.overlaps[0].second, 0.85);  // 记录的 similarity
    // 偏移后与邻居的相似度应低于原始相似度
    EXPECT_LT(cosine(r.index_vector, nb), cosine({0.99f, 0.14f, 0.0f}, nb));
}

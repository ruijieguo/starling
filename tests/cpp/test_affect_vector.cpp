// tests/cpp/test_affect_vector.cpp
#include "starling/affect/affect_vector.hpp"
#include <gtest/gtest.h>
using namespace starling::affect;

TEST(AffectVector, SalienceParityWithPython) {
    AffectVector v{0.5f, 0.8f, 0.0f, 0.6f, 0.9f};
    double expect = (0.4+0.6*0.5)*(0.4+0.6*0.8)*(0.3+0.7*0.6)*(0.3+0.7*0.9)*(0.6+0.4*1.0);
    EXPECT_NEAR(salience(v, 1.0), expect, 1e-6);
}
TEST(AffectVector, ParseJsonAndDefaults) {
    auto v = parse_affect_json(R"({"valence":-0.5,"arousal":0.7})");
    EXPECT_NEAR(v.valence, -0.5, 1e-6);
    EXPECT_NEAR(v.arousal, 0.7, 1e-6);
    EXPECT_NEAR(v.stakes, 0.0, 1e-6);
    EXPECT_NO_THROW(parse_affect_json("{}"));
    EXPECT_NO_THROW(parse_affect_json("not json"));
}

#include "starling/preflight.hpp"

#include <gtest/gtest.h>

using namespace starling;

// vector_index 由 ProfileCapability.vector_backend 是否非空驱动。
TEST(VectorCapability, RecognizedAndDrivenByBackend) {
    ProfileCapability cap;
    cap.vector_backend = "";
    EXPECT_EQ(preflight(cap, {"vector_index"}).status, PreflightStatus::UNREADY);
    cap.vector_backend = "sqlite_blob";
    EXPECT_EQ(preflight(cap, {"vector_index"}).status, PreflightStatus::READY);
}

// vector_index 是非关键项: 缺失不进必需集 → 不影响其它必需能力的判定。
// (feature-level 降级: 无向量时 RuntimeHealth 仍 READY,vector_recall 自身降级)
TEST(VectorCapability, NotRequiredDoesNotAffectOtherCaps) {
    ProfileCapability cap;  // vector_backend 空, c_plus_plus_core true
    cap.c_plus_plus_core = true;
    EXPECT_EQ(preflight(cap, {"c_plus_plus_core"}).status, PreflightStatus::READY);
}

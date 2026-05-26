#include "starling/cognizer/uuid5.hpp"
#include "starling/version.hpp"

#include <gtest/gtest.h>

using starling::cognizer::compute_uuid5;
using starling::kStarlingCognizerNamespace;

// Known-good vector from Python: uuid.uuid5(uuid.UUID("aacf67e8-..."), "human\x1falice")
// Pre-computed once and locked here to detect regressions.
TEST(Uuid5Test, KnownVectorAliceHuman) {
    const std::string name = std::string("human") + "\x1f" + "alice";
    const std::string got  = compute_uuid5(kStarlingCognizerNamespace, name);
    // Vector verified offline: python3 -c 'import uuid; print(uuid.uuid5(uuid.UUID("aacf67e8-1495-5cef-ac22-dd0bd73dd1af"), "human\x1falice"))'
    // → 8c601801-f52d-5699-8b1d-8fbca7caf14f
    EXPECT_EQ(got, "8c601801-f52d-5699-8b1d-8fbca7caf14f");
}

TEST(Uuid5Test, DeterministicIdempotent) {
    const std::string name = std::string("agent") + "\x1f" + "bot-007";
    const auto a = compute_uuid5(kStarlingCognizerNamespace, name);
    const auto b = compute_uuid5(kStarlingCognizerNamespace, name);
    EXPECT_EQ(a, b);
}

TEST(Uuid5Test, DifferentKindGivesDifferentId) {
    const auto human  = compute_uuid5(kStarlingCognizerNamespace, "human\x1f" "alice");
    const auto agent  = compute_uuid5(kStarlingCognizerNamespace, "agent\x1f" "alice");
    EXPECT_NE(human, agent);
}

TEST(Uuid5Test, Version5VariantBitsSet) {
    const auto u = compute_uuid5(kStarlingCognizerNamespace, "human\x1f" "test");
    // Layout 8-4-4-4-12: dashes at index 8, 13, 18, 23
    // First nibble of group 3 (index 14) is version → must be '5'
    EXPECT_EQ(u[14], '5');
    // First nibble of group 4 (index 19) is variant → must be in {8,9,a,b}
    EXPECT_TRUE(u[19] == '8' || u[19] == '9' || u[19] == 'a' || u[19] == 'b');
}

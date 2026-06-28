#include "starling/governance/capability_policy.hpp"
#include <gtest/gtest.h>
#include <algorithm>

namespace {
using starling::governance::required_capabilities;

TEST(CapabilityPolicy, FullProfileRequiresAllSeven) {
  const auto req = required_capabilities(/*embedded=*/false);
  EXPECT_EQ(req.size(), 7U);
  EXPECT_NE(std::ranges::find(req, "engram_per_record_key"), req.end());
  EXPECT_NE(std::ranges::find(req, "testing_helper_marker"), req.end());
}

TEST(CapabilityPolicy, EmbeddedDropsDeferredCapsButKeepsHardCaps) {
  const auto req = required_capabilities(/*embedded=*/true);
  EXPECT_EQ(req.size(), 5U);
  EXPECT_EQ(std::ranges::find(req, "engram_per_record_key"), req.end());
  EXPECT_EQ(std::ranges::find(req, "testing_helper_marker"), req.end());
  EXPECT_NE(std::ranges::find(req, "transactional_outbox"), req.end());
  EXPECT_NE(std::ranges::find(req, "cross_partition_transaction"), req.end());
}

TEST(CapabilityPolicy, RepeatedCallsDoNotMutateState) {
  const auto aaa = required_capabilities(true);
  const auto bbb = required_capabilities(false);
  EXPECT_EQ(aaa.size(), 5U);
  EXPECT_EQ(bbb.size(), 7U);  // calling embedded first must not have shrunk the full list
}
}  // namespace

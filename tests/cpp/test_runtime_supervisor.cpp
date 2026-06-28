#include "starling/governance/runtime_supervisor.hpp"

#include <algorithm>

#include <gtest/gtest.h>

#include "starling/profile_capability.hpp"
#include "starling/runtime_health.hpp"

namespace {
using starling::ProfileCapability;
using starling::RuntimeHealth;
using starling::governance::RuntimeSupervisor;
using starling::governance::StartOutcome;
using starling::governance::WriteGateDecision;

// All 7 hard caps satisfied (mirrors tests/cpp/test_preflight.cpp make_local_store).
ProfileCapability all_present() {
  return ProfileCapability{
      .profile_name = "local-store",
      .relational_backend = "seekdb",
      .vector_backend = "seekdb",
      .graph_backend = "ladybugdb",
      .c_plus_plus_core = true,
      .cross_partition_transaction = true,
      .transactional_outbox = true,
      .consumer_checkpoint = true,
      .tenant_isolation = "storage_enforced",
      .engram_per_record_key = true,
      .engram_refcount = true,
      .projection_index_supported = false,
      .dimension_versions_supported = false,
      .testing_helper_marker = true,
  };
}

TEST(RuntimeSupervisor, UnreadyWhenIndexMissingSetsExit78) {
  RuntimeSupervisor sup(all_present(), /*embedded=*/false, [] { return false; });
  EXPECT_EQ(sup.start(), StartOutcome::kUnready);
  EXPECT_EQ(sup.health(), RuntimeHealth::UNREADY);
  EXPECT_EQ(sup.exit_code(), starling::governance::kExConfig);
  const auto report = sup.run_preflight();
  EXPECT_NE(std::ranges::find(report.missing_capabilities, "idx_statement_id_tenant"),
            report.missing_capabilities.end());
}

TEST(RuntimeSupervisor, ReadyWhenAllPresentAcceptsWrites) {
  RuntimeSupervisor sup(all_present(), /*embedded=*/false, [] { return true; });
  EXPECT_EQ(sup.start(), StartOutcome::kReady);
  EXPECT_EQ(sup.health(), RuntimeHealth::READY);
  EXPECT_EQ(sup.exit_code(), 0);
  EXPECT_EQ(sup.check_write(), WriteGateDecision::kAccept);
}

TEST(RuntimeSupervisor, WriteGateFailsClosedBeforeReady) {
  RuntimeSupervisor sup(all_present(), /*embedded=*/false, [] { return false; });
  EXPECT_EQ(sup.check_write(), WriteGateDecision::kPreconditionFailed);  // before start()
  sup.start();
  EXPECT_EQ(sup.check_write(), WriteGateDecision::kPreconditionFailed);  // UNREADY
}

TEST(RuntimeSupervisor, UnreadyWhenCapabilityMissing) {
  ProfileCapability caps = all_present();
  caps.transactional_outbox = false;  // a hard CAP missing (not an index)
  RuntimeSupervisor sup(caps, /*embedded=*/false, [] { return true; });
  EXPECT_EQ(sup.start(), StartOutcome::kUnready);
  EXPECT_EQ(sup.health(), RuntimeHealth::UNREADY);
  EXPECT_EQ(sup.exit_code(), starling::governance::kExConfig);
  const auto report = sup.run_preflight();
  EXPECT_FALSE(report.passed);
  EXPECT_NE(std::ranges::find(report.missing_capabilities, "transactional_outbox"),
            report.missing_capabilities.end());
}

TEST(RuntimeSupervisor, EmbeddedStartReadyWithoutDeferredCaps) {
  // embedded=true waives engram_per_record_key + testing_helper_marker.
  ProfileCapability caps = all_present();
  caps.engram_per_record_key = false;
  caps.testing_helper_marker = false;
  RuntimeSupervisor sup(caps, /*embedded=*/true, [] { return true; });
  EXPECT_EQ(sup.start(), StartOutcome::kReady);
  EXPECT_EQ(sup.health(), RuntimeHealth::READY);
  EXPECT_EQ(sup.exit_code(), 0);
}
}  // namespace

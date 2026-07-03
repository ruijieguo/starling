// tests/cpp/test_write_gate_admission.cpp
#include "starling/governance/write_gate.hpp"
#include "starling/governance/runtime_supervisor.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
#include <filesystem>
#include <functional>
using starling::ProfileCapability;
using starling::RuntimeHealth;
using namespace starling::governance;

namespace {
// COPY of tests/cpp/test_runtime_supervisor.cpp:18 all_present() (逐字复制;
// tests/cpp 不受 clang-tidy 门)。RuntimeSupervisor 有 std::mutex → 非可移动,
// 就地构造,勿按值返回。
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
std::unique_ptr<starling::persistence::SqliteAdapter> open_tmp(const char* name) {
  return starling::persistence::SqliteAdapter::open(
      std::filesystem::temp_directory_path() / name);
}
}  // namespace

TEST(WriteGateAdmission, NoHookAdmits) {
  auto a = open_tmp("wg_nohook.db");
  EXPECT_TRUE(a->write_admitted());
  EXPECT_NO_THROW(require_write_admission(*a));   // 无钩子 → 放行
}
TEST(WriteGateAdmission, HookRejectThrows) {
  auto a = open_tmp("wg_reject.db");
  a->set_write_admit([] { return false; });
  EXPECT_FALSE(a->write_admitted());
  EXPECT_THROW(require_write_admission(*a), WriteGateRejected);
}
TEST(WriteGateAdmission, HookAdmitPasses) {
  auto a = open_tmp("wg_admit.db");
  a->set_write_admit([] { return true; });
  EXPECT_NO_THROW(require_write_admission(*a));
}
TEST(WriteGateAdmission, InstallWiresSupervisorDraining) {
  auto a = open_tmp("wg_install.db");
  RuntimeSupervisor sup(all_present(), /*embedded=*/true,
                        std::function<bool()>([] { return true; }));
  sup.start();                                    // → READY
  install_write_gate(*a, sup);
  EXPECT_NO_THROW(require_write_admission(*a));    // READY 放行
  sup.begin_drain("test");                        // → DRAINING
  EXPECT_THROW(require_write_admission(*a), WriteGateRejected);
}

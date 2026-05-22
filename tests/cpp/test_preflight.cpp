#include <gtest/gtest.h>

#include <string>
#include <vector>

#include "starling/preflight.hpp"
#include "starling/profile_capability.hpp"

using starling::preflight;
using starling::PreflightResult;
using starling::PreflightStatus;
using starling::ProfileCapability;

namespace {

ProfileCapability make_local_store() {
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

}  // namespace

TEST(Preflight, FullyCapableLocalStoreReturnsReady) {
    auto cap = make_local_store();
    auto required = std::vector<std::string>{
        "transactional_outbox",
        "consumer_checkpoint",
        "engram_per_record_key",
        "c_plus_plus_core",
        "tenant_isolation_storage_enforced",
        "cross_partition_transaction",
    };
    PreflightResult result = preflight(cap, required);
    EXPECT_EQ(result.status, PreflightStatus::READY);
    EXPECT_TRUE(result.missing.empty());
}

TEST(Preflight, MissingTransactionalOutboxReturnsUnready) {
    auto cap = make_local_store();
    cap.transactional_outbox = false;
    PreflightResult result = preflight(cap, {"transactional_outbox"});
    EXPECT_EQ(result.status, PreflightStatus::UNREADY);
    ASSERT_EQ(result.missing.size(), 1u);
    EXPECT_EQ(result.missing[0], "transactional_outbox");
}

TEST(Preflight, AppFilterFailsStorageEnforcedRequirement) {
    auto cap = make_local_store();
    cap.tenant_isolation = "app_filter";
    PreflightResult result =
        preflight(cap, {"tenant_isolation_storage_enforced"});
    EXPECT_EQ(result.status, PreflightStatus::UNREADY);
    ASSERT_EQ(result.missing.size(), 1u);
    EXPECT_EQ(result.missing[0], "tenant_isolation_storage_enforced");
}

TEST(Preflight, MissingCrossPartitionTransactionFailsLocalAtomic) {
    auto cap = make_local_store();
    cap.cross_partition_transaction = false;
    PreflightResult result = preflight(cap, {"cross_partition_transaction"});
    EXPECT_EQ(result.status, PreflightStatus::UNREADY);
    ASSERT_EQ(result.missing.size(), 1u);
    EXPECT_EQ(result.missing[0], "cross_partition_transaction");
}

TEST(Preflight, TestingHelperMarkerMissingFailsLocalStore) {
    auto cap = make_local_store();
    cap.testing_helper_marker = false;
    PreflightResult result = preflight(cap, {"testing_helper_marker"});
    EXPECT_EQ(result.status, PreflightStatus::UNREADY);
    ASSERT_EQ(result.missing.size(), 1u);
    EXPECT_EQ(result.missing[0], "testing_helper_marker");
}

TEST(Preflight, MultipleMissingPreservesOrder) {
    ProfileCapability cap;  // all defaults = false
    PreflightResult result = preflight(cap, {
        "transactional_outbox",
        "consumer_checkpoint",
        "engram_per_record_key",
    });
    EXPECT_EQ(result.status, PreflightStatus::UNREADY);
    ASSERT_EQ(result.missing.size(), 3u);
    EXPECT_EQ(result.missing[0], "transactional_outbox");
    EXPECT_EQ(result.missing[1], "consumer_checkpoint");
    EXPECT_EQ(result.missing[2], "engram_per_record_key");
}

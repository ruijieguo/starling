#include <gtest/gtest.h>

#include "starling/profile_capability.hpp"

using starling::ProfileCapability;

TEST(ProfileCapability, DefaultsAreFailClosed) {
    ProfileCapability cap;
    EXPECT_TRUE(cap.profile_name.empty());
    EXPECT_FALSE(cap.cross_partition_transaction);
    EXPECT_FALSE(cap.transactional_outbox);
    EXPECT_FALSE(cap.consumer_checkpoint);
    EXPECT_FALSE(cap.engram_per_record_key);
    EXPECT_FALSE(cap.c_plus_plus_core);
    EXPECT_FALSE(cap.testing_helper_marker);
    EXPECT_EQ(cap.tenant_isolation, "");
}

TEST(ProfileCapability, LocalStoreProfilePopulatesAllFields) {
    ProfileCapability cap{
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
    EXPECT_EQ(cap.profile_name, "local-store");
    EXPECT_TRUE(cap.cross_partition_transaction);
    EXPECT_EQ(cap.tenant_isolation, "storage_enforced");
}

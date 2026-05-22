#include <gtest/gtest.h>

#include "starling/profile_capability.hpp"

using starling::ProfileCapability;

TEST(ProfileCapability, DefaultsAreFailClosed) {
    ProfileCapability cap;
    EXPECT_TRUE(cap.profile_name.empty());
    EXPECT_TRUE(cap.relational_backend.empty());
    EXPECT_TRUE(cap.vector_backend.empty());
    EXPECT_TRUE(cap.graph_backend.empty());
    EXPECT_FALSE(cap.c_plus_plus_core);
    EXPECT_FALSE(cap.cross_partition_transaction);
    EXPECT_FALSE(cap.transactional_outbox);
    EXPECT_FALSE(cap.consumer_checkpoint);
    EXPECT_EQ(cap.tenant_isolation, "");
    EXPECT_FALSE(cap.engram_per_record_key);
    EXPECT_FALSE(cap.engram_refcount);
    EXPECT_FALSE(cap.projection_index_supported);
    EXPECT_FALSE(cap.dimension_versions_supported);
    EXPECT_FALSE(cap.testing_helper_marker);
}

TEST(ProfileCapability, LocalStoreProfilePopulatesAllFields) {
    // Each same-typed adjacent group uses distinct values so a silent field
    // re-wiring (e.g. swapping two strings or two bools) shows up here rather
    // than at runtime in Task 4 / Task 8.
    ProfileCapability cap{
        .profile_name = "local-store",
        .relational_backend = "REL",
        .vector_backend = "VEC",
        .graph_backend = "GRA",
        .c_plus_plus_core = true,
        .cross_partition_transaction = true,
        .transactional_outbox = false,
        .consumer_checkpoint = true,
        .tenant_isolation = "storage_enforced",
        .engram_per_record_key = true,
        .engram_refcount = false,
        .projection_index_supported = false,
        .dimension_versions_supported = true,
        .testing_helper_marker = true,
    };
    EXPECT_EQ(cap.profile_name, "local-store");
    EXPECT_EQ(cap.relational_backend, "REL");
    EXPECT_EQ(cap.vector_backend, "VEC");
    EXPECT_EQ(cap.graph_backend, "GRA");
    EXPECT_TRUE(cap.c_plus_plus_core);
    EXPECT_TRUE(cap.cross_partition_transaction);
    EXPECT_FALSE(cap.transactional_outbox);
    EXPECT_TRUE(cap.consumer_checkpoint);
    EXPECT_EQ(cap.tenant_isolation, "storage_enforced");
    EXPECT_TRUE(cap.engram_per_record_key);
    EXPECT_FALSE(cap.engram_refcount);
    EXPECT_FALSE(cap.projection_index_supported);
    EXPECT_TRUE(cap.dimension_versions_supported);
    EXPECT_TRUE(cap.testing_helper_marker);
}

#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>

namespace {

TEST(SqliteAdapterIndexPreflight, ReportsPresenceOfSchemaIndex) {
    auto adapter = starling::persistence::SqliteAdapter::open(":memory:");
    EXPECT_TRUE(adapter->has_index("idx_statement_id_tenant"));
}

TEST(SqliteAdapterIndexPreflight, ReportsAbsenceOfUnknownIndex) {
    auto adapter = starling::persistence::SqliteAdapter::open(":memory:");
    EXPECT_FALSE(adapter->has_index("idx_definitely_not_a_real_index"));
}

}  // namespace

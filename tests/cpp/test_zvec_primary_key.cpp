#include <gtest/gtest.h>

#include "starling/vector/zvec_primary_key.hpp"

namespace starling::vector::detail {

TEST(ZvecPrimaryKey, VersionedRoundTripPreservesSeparators) {
    const auto pk = encode_zvec_primary_key("tenant:a", "2:ab/statement:1");
    EXPECT_EQ(pk, "starling:v1:8:16:tenant:a2:ab/statement:1");
    ASSERT_TRUE(decode_zvec_statement_id(pk, "tenant:a").has_value());
    EXPECT_EQ(*decode_zvec_statement_id(pk, "tenant:a"), "2:ab/statement:1");
}

TEST(ZvecPrimaryKey, SharedStatementIdsProduceTenantScopedKeys) {
    const auto a = encode_zvec_primary_key("tenant-a", "shared");
    const auto b = encode_zvec_primary_key("tenant-b", "shared");
    EXPECT_NE(a, b);
    EXPECT_EQ(*decode_zvec_statement_id(a, "tenant-a"), "shared");
    EXPECT_EQ(*decode_zvec_statement_id(b, "tenant-b"), "shared");
    EXPECT_FALSE(decode_zvec_statement_id(a, "tenant-b").has_value());
}

TEST(ZvecPrimaryKey, LegacyBareIdsRemainLiteral) {
    EXPECT_EQ(*decode_zvec_statement_id("plain-id", "tenant"), "plain-id");
    EXPECT_EQ(*decode_zvec_statement_id("2:ablooks-prefixed", "ab"),
              "2:ablooks-prefixed");
}

TEST(ZvecPrimaryKey, MalformedVersionedKeysFailClosed) {
    EXPECT_FALSE(decode_zvec_statement_id("starling:v1:x:1:ab", "a").has_value());
    EXPECT_FALSE(decode_zvec_statement_id("starling:v1:1:x:ab", "a").has_value());
    EXPECT_FALSE(decode_zvec_statement_id("starling:v1:2:1:ab", "ab").has_value());
    EXPECT_FALSE(decode_zvec_statement_id("starling:v1:1:2:ab", "a").has_value());
    EXPECT_FALSE(decode_zvec_statement_id("starling:v1:1:1:a", "a").has_value());
}

}  // namespace starling::vector::detail

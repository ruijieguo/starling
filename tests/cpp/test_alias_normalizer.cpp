#include "starling/cognizer/alias_normalizer.hpp"

#include <gtest/gtest.h>

using starling::cognizer::normalize_alias;

TEST(AliasNormalizer, PassthroughLowercaseASCII) {
    EXPECT_EQ(normalize_alias("alice"), "alice");
}

TEST(AliasNormalizer, FoldsASCIIUppercase) {
    EXPECT_EQ(normalize_alias("Alice"), "alice");
    EXPECT_EQ(normalize_alias("BOB"), "bob");
}

TEST(AliasNormalizer, TrimsLeadingTrailing) {
    EXPECT_EQ(normalize_alias("  alice  "), "alice");
    EXPECT_EQ(normalize_alias("\talice\n"), "alice");
}

TEST(AliasNormalizer, CollapsesInternalWhitespace) {
    EXPECT_EQ(normalize_alias("zhang  wei"), "zhang wei");
    EXPECT_EQ(normalize_alias("zhang \t\t wei"), "zhang wei");
}

TEST(AliasNormalizer, CombinesTrimCollapseFold) {
    EXPECT_EQ(normalize_alias("  ZHANG  Wei  "), "zhang wei");
}

TEST(AliasNormalizer, PreservesCJKBytes) {
    // 中文不变 — non-ASCII bytes pass through unchanged.
    EXPECT_EQ(normalize_alias("张伟"), "张伟");
    // ASCII spaces between CJK chars are collapsed (they are ASCII whitespace).
    EXPECT_EQ(normalize_alias(" 张  伟 "), "张 伟");
}

// Wait — the spec says "collapse runs of internal whitespace" which
// applies to ASCII space; CJK chars aren't whitespace so the test above
// stays. But what about a mix?
TEST(AliasNormalizer, MixedASCIIAndCJK) {
    EXPECT_EQ(normalize_alias("  张 Wei  "), "张 wei");
}

TEST(AliasNormalizer, EmptyAndWhitespaceOnly) {
    EXPECT_EQ(normalize_alias(""), "");
    EXPECT_EQ(normalize_alias("   "), "");
}

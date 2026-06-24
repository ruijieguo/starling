#include "starling/schema/normalize_theme.hpp"
#include <gtest/gtest.h>
using starling::schema::normalize_theme;

TEST(NormalizeTheme, StripsArticleAndSingularizes) {
    EXPECT_EQ(normalize_theme("the cabbage"), "cabbage");
    EXPECT_EQ(normalize_theme("a backpack"), "backpack");
    EXPECT_EQ(normalize_theme("an apple"), "apple");
    EXPECT_EQ(normalize_theme("cabbages"), "cabbage");      // -s
    EXPECT_EQ(normalize_theme("the cabbages"), "cabbage");  // article + -s
    EXPECT_EQ(normalize_theme("boxes"), "box");             // -es after x
    EXPECT_EQ(normalize_theme("tomatoes"), "tomato");       // -es after o
    EXPECT_EQ(normalize_theme("crayons"), "crayon");
    EXPECT_EQ(normalize_theme("leaves"), "leaf");           // irregular
    EXPECT_EQ(normalize_theme("  Handbag  "), "handbag");   // trim + lowercase
}

TEST(NormalizeTheme, ConservativeFalsePositiveGuards) {
    EXPECT_EQ(normalize_theme("bus"), "bus");       // -us, not a plural
    EXPECT_EQ(normalize_theme("glass"), "glass");   // -ss
    EXPECT_EQ(normalize_theme("boss"), "boss");     // -ss
    EXPECT_EQ(normalize_theme("series"), "series"); // -is stoplist
    EXPECT_EQ(normalize_theme("ball"), "ball");     // no trailing s, unchanged
}

TEST(NormalizeTheme, StripsLeadingQuantifiersAndMerges) {
    EXPECT_EQ(normalize_theme("all three toys"), "three toy");
    EXPECT_EQ(normalize_theme("three toys"),     "three toy");
    EXPECT_EQ(normalize_theme("all three toy"),  "three toy");
    EXPECT_EQ(normalize_theme("both hands"),     "hand");
    EXPECT_EQ(normalize_theme("all the marbles"),"marble");
    EXPECT_EQ(normalize_theme("three toy"),      "three toy");   // idempotent
    EXPECT_EQ(normalize_theme("allowance"),      "allowance");   // "all" w/o space boundary untouched
}

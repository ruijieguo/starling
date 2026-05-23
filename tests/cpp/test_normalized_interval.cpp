#include "starling/bus/normalized_interval.hpp"
#include <gtest/gtest.h>
#include <iostream>

namespace {
using namespace starling::bus;

TEST(NormalizedInterval, BothAbsentReturnsUnknown) {
    auto ni = normalize_interval(std::nullopt, std::nullopt, std::nullopt);
    EXPECT_TRUE(ni.is_unknown);
    EXPECT_EQ(ni.canonical_bytes(), "UNKNOWN");
}

TEST(NormalizedInterval, ValidFromOnlyOpenEnded) {
    auto ni = normalize_interval("2026-01-01T00:00:00Z", std::nullopt, std::nullopt);
    EXPECT_FALSE(ni.is_unknown);
    EXPECT_EQ(ni.from, "2026-01-01T00:00:00Z");
    EXPECT_TRUE(ni.to_is_open);
    EXPECT_EQ(ni.canonical_bytes(), "2026-01-01T00:00:00Z/OPEN");
}

TEST(NormalizedInterval, ValidFromAndToClosedOpen) {
    auto ni = normalize_interval(
        "2026-01-01T00:00:00Z", "2026-06-01T00:00:00Z", std::nullopt);
    EXPECT_FALSE(ni.is_unknown);
    EXPECT_EQ(ni.from, "2026-01-01T00:00:00Z");
    EXPECT_EQ(ni.to,   "2026-06-01T00:00:00Z");
    EXPECT_FALSE(ni.to_is_open);
    EXPECT_EQ(ni.canonical_bytes(), "2026-01-01T00:00:00Z/2026-06-01T00:00:00Z");
}

TEST(NormalizedInterval, EventTimeFallbackOpenEnded) {
    auto ni = normalize_interval(std::nullopt, std::nullopt, "2026-03-15T08:00:00Z");
    EXPECT_FALSE(ni.is_unknown);
    EXPECT_EQ(ni.from, "2026-03-15T08:00:00Z");
    EXPECT_TRUE(ni.to_is_open);
    EXPECT_EQ(ni.canonical_bytes(), "2026-03-15T08:00:00Z/OPEN");
}

TEST(NormalizedInterval, ValidFromTakesPriorityOverEventTime) {
    auto ni = normalize_interval(
        "2026-01-01T00:00:00Z", std::nullopt, "2026-03-15T08:00:00Z");
    EXPECT_EQ(ni.from, "2026-01-01T00:00:00Z");
    EXPECT_TRUE(ni.to_is_open);
}

TEST(NormalizedInterval, ValidToIgnoredWhenValidFromAbsent) {
    auto ni = normalize_interval(std::nullopt, "2026-06-01T00:00:00Z", std::nullopt);
    EXPECT_TRUE(ni.is_unknown);
}

TEST(NormalizedInterval, ParityFixtureCanonicalBytes) {
    auto ni = normalize_interval(
        "2026-01-01T00:00:00Z", "2026-12-31T23:59:59Z", std::nullopt);
    std::cout << "PARITY_CANONICAL_BYTES=" << ni.canonical_bytes() << std::endl;
    EXPECT_EQ(ni.canonical_bytes(), "2026-01-01T00:00:00Z/2026-12-31T23:59:59Z");
}

}  // namespace

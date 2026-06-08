#include <gtest/gtest.h>
#include "starling/schema/canonicalize.hpp"

#include <chrono>
#include <cmath>
#include <limits>
#include <stdexcept>

using namespace starling::schema;
using namespace std::chrono;
using namespace std::chrono_literals;

TEST(Canonicalize, Bool) {
    auto r = canonicalize_object(true);
    EXPECT_EQ(r.canonical, "true");
    auto r2 = canonicalize_object(false);
    EXPECT_EQ(r2.canonical, "false");
}

TEST(Canonicalize, IntDecimal) {
    auto r = canonicalize_object(static_cast<std::int64_t>(-42));
    EXPECT_EQ(r.canonical, "-42");
    auto r0 = canonicalize_object(static_cast<std::int64_t>(0));
    EXPECT_EQ(r0.canonical, "0");
    auto r3 = canonicalize_object(static_cast<std::int64_t>(1000000));
    EXPECT_EQ(r3.canonical, "1000000");
}

TEST(Canonicalize, FloatSixDecimals) {
    auto r = canonicalize_object(1.5);
    EXPECT_EQ(r.canonical, "1.500000");
    auto rz = canonicalize_object(-0.0);
    EXPECT_EQ(rz.canonical, "0.000000");
}

TEST(Canonicalize, FloatNaNRejected) {
    EXPECT_THROW(canonicalize_object(std::nan("")), std::invalid_argument);
    auto inf = std::numeric_limits<double>::infinity();
    EXPECT_THROW(canonicalize_object(inf), std::invalid_argument);
}

TEST(Canonicalize, StringNFCAndLowerAndFold) {
    auto r = canonicalize_object(std::string("  Hello   World  \n"));
    EXPECT_EQ(r.canonical, "hello world");
}

TEST(Canonicalize, StringDecomposedAccentNormalizesToNFC) {
    auto r = canonicalize_object(std::string("Cafe\xCC\x81"));
    EXPECT_EQ(r.canonical, std::string("caf\xC3\xA9"));
}

TEST(Canonicalize, StringCJKUnchanged) {
    auto r = canonicalize_object(std::string("北京"));
    EXPECT_EQ(r.canonical, "北京");
}

TEST(Canonicalize, DatetimeUTC) {
    sys_seconds t = sys_days{May/23/2026} + 12h + 30min + 45s;
    auto r = canonicalize_object(t);
    EXPECT_EQ(r.canonical, "2026-05-23T12:30:45Z");
}

TEST(Canonicalize, RefHexFormat) {
    CanonicalRefInput ref{
        "CognizerRef",
        {{0x55,0x0e,0x84,0x00,0xe2,0x9b,0x41,0xd4,
          0xa7,0x16,0x44,0x66,0x55,0x44,0x00,0x00}},
    };
    auto r = canonicalize_object(ref);
    EXPECT_EQ(r.canonical, "CognizerRef:550e8400e29b41d4a716446655440000");
}

TEST(Canonicalize, Sha256IsLowercaseHex64) {
    auto r = canonicalize_object(std::string("hello"));
    EXPECT_EQ(r.sha256_hex.size(), 64u);
    for (char c : r.sha256_hex) {
        EXPECT_TRUE((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'));
    }
}

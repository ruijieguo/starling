#include <gtest/gtest.h>

#include "starling/version.hpp"

TEST(Smoke, VersionDefined) {
    EXPECT_STREQ(STARLING_VERSION_STRING, "0.0.1");
}

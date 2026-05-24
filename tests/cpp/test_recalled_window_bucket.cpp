#include <gtest/gtest.h>
#include "starling/bus/bus_event.hpp"
#include <chrono>

using starling::bus::compute_window_bucket;

TEST(RecalledWindowBucket, BucketsBy2Seconds) {
    using namespace std::chrono;
    auto t0 = system_clock::from_time_t(1'000'000'000);
    auto t1 = system_clock::from_time_t(1'000'000'001);
    auto t2 = system_clock::from_time_t(1'000'000'002);

    EXPECT_EQ(compute_window_bucket("statement.recalled", t0),
              compute_window_bucket("statement.recalled", t1));
    EXPECT_NE(compute_window_bucket("statement.recalled", t0),
              compute_window_bucket("statement.recalled", t2));
}

TEST(RecalledWindowBucket, ExpectedStringValue) {
    using namespace std::chrono;
    auto t = system_clock::from_time_t(1'000'000'000);
    EXPECT_EQ(compute_window_bucket("statement.recalled", t), "500000000");
}

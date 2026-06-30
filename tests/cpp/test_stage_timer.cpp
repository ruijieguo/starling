#include "starling/governance/stage_timer.hpp"

#include <gtest/gtest.h>

#include <chrono>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

using starling::governance::StageTimer;
using starling::governance::StageTiming;

namespace {

TEST(StageTimer, ReportsStageAndNonNegativeMsExactlyOnceOnScopeExit) {
    std::vector<StageTiming> sink_calls;
    {
        StageTimer timer("embed", [&](std::string_view stage, long long ms) {
            sink_calls.push_back(StageTiming{std::string(stage), ms});
        });
        // work happens in this scope; dtor fires the sink at the closing brace
    }
    ASSERT_EQ(sink_calls.size(), 1U);
    EXPECT_EQ(sink_calls.front().stage, "embed");
    EXPECT_GE(sink_calls.front().duration_ms, 0);
}

TEST(StageTimer, MeasuresElapsedWallClock) {
    long long measured = -1;
    {
        StageTimer timer("slow", [&](std::string_view, long long ms) { measured = ms; });
        std::this_thread::sleep_for(std::chrono::milliseconds(12));
    }
    EXPECT_GE(measured, 1);  // generous lower bound on a 12ms sleep — non-flaky
}

TEST(StageTimer, DestructorSwallowsSinkException) {
    bool reached_next_line = false;
    {
        StageTimer timer("boom", [](std::string_view, long long) {
            throw std::runtime_error("sink failed");
        });
    }  // dtor invokes the throwing sink; must NOT propagate
    reached_next_line = true;
    EXPECT_TRUE(reached_next_line);
}

TEST(StageTimer, EmptySinkIsANoOp) {
    StageTimer::Sink none;  // empty std::function
    {
        StageTimer timer("noop", none);
    }
    SUCCEED();  // reaching here proves the dtor guarded the empty sink
}

}  // namespace

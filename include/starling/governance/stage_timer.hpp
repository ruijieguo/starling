#pragma once
#include <chrono>
#include <functional>
#include <string>
#include <string_view>
#include <utility>

namespace starling::governance {

// One {stage, ms} entry — mirrors a single element of the JSON array stored in
// PipelineRun.stage_timings_ms (the persisted form uses the JSON key 'ms').
struct StageTiming {
    std::string stage;
    long long duration_ms = 0;
};

// RAII wall-clock timer for one pipeline stage. Measures with steady_clock
// (mirror of the latency idiom in src/extractor/openai_adapter.cpp:39,44-46) and,
// on scope exit, reports {stage, elapsed_ms} to a sink. The sink decides the
// destination: accumulate into TickOutcome (P3.c1 Phase 3b), or persist via
// PipelineRunStore::record_stage_timing once a run owns the cycle (Phase 4+).
//
// The destructor swallows any sink exception: a StageTimer must never throw
// during stack unwinding, and stage timing is best-effort observability
// (the metadata_only trace tier, 05_governance.md:114-119), never a correctness path.
class StageTimer {
public:
    using Sink = std::function<void(std::string_view stage, long long duration_ms)>;

    StageTimer(std::string stage, Sink sink)
        : stage_(std::move(stage)),
          sink_(std::move(sink)),
          start_(std::chrono::steady_clock::now()) {}

    ~StageTimer() {
        if (!sink_) {
            return;
        }
        const auto elapsed = std::chrono::steady_clock::now() - start_;
        const auto elapsed_ms =
            std::chrono::duration_cast<std::chrono::milliseconds>(elapsed).count();
        try {
            sink_(stage_, static_cast<long long>(elapsed_ms));
        } catch (...) {  // NOLINT(bugprone-empty-catch): dtor must not throw; timing is best-effort
        }
    }

    StageTimer(const StageTimer&) = delete;
    StageTimer& operator=(const StageTimer&) = delete;
    StageTimer(StageTimer&&) = delete;
    StageTimer& operator=(StageTimer&&) = delete;

private:
    std::string stage_;
    Sink sink_;
    std::chrono::steady_clock::time_point start_;
};

}  // namespace starling::governance

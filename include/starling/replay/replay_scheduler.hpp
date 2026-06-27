#pragma once
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/replay/consolidation_ops.hpp"
#include <string>
#include <string_view>
#include <vector>

namespace starling::extractor { class LLMAdapter; }  // injected consolidation LLM (offline only)

namespace starling::replay {

struct ReplayStats {
    int sampled=0, compressed=0, abstracted=0, reinforced=0, decayed=0, reconciled=0;
    int forced_consolidated=0, ttl_archived=0;
    int gist_candidates=0;  // #38-C P1: NORM-gist clusters detected this batch
    int gist_failed=0;      // #38-C P2: gist proposals that errored (LLM/write/promote)
    int gist_gated=0;       // #38-C P4: gists rejected by gating (floor/entailment/conflict)
    std::string replay_batch_id;
};

class ReplayScheduler {
public:
    explicit ReplayScheduler(persistence::SqliteAdapter& adapter);

    // Online: SubscriberPump 调用. online_trigger_counter+1; 达 N=3 跑采样窗口(批1-3).
    ReplayStats tick_online(persistence::Connection& conn, std::string_view now_iso);
    // 显式 API (无后台线程). #38-C P3: offline gist writes; pass a consolidation
    // LLM to judge each gist (confidence + summary), or null for the deterministic
    // Phase-2 path. These run in autocommit, so Bus::write's BEGIN is safe.
    ReplayStats run_idle(persistence::Connection& conn, std::string_view now_iso,
                         extractor::LLMAdapter* gist_llm = nullptr);   // 批10-30
    ReplayStats run_sleep(persistence::Connection& conn, std::string_view now_iso,
                          extractor::LLMAdapter* gist_llm = nullptr);  // sweep

    // 振荡防护: replay_count≥5 → 强制 CONSOLIDATED+PENDING_REVIEW + emit consolidation_forced.
    int enforce_oscillation_guard(persistence::Connection& conn);
    // VOLATILE TTL: 写入>7天 → ARCHIVED + emit statement.archived(volatile_ttl_exceeded).
    int sweep_volatile_ttl(persistence::Connection& conn, std::string_view now_iso);
    // decay 一批候选 (op_decay 包装 + emit statement.archived per archived stmt; 串行守护幂等).
    int run_decay(persistence::Connection& conn,
                  const std::vector<std::string>& candidate_ids, std::string_view now_iso);

    // Python binding helper: exposes adapter_.connection() without making adapter_ public.
    persistence::Connection& connection() { return adapter_.connection(); }

private:
    persistence::SqliteAdapter& adapter_;
    static constexpr int kOnlineTrigger=3;
    static constexpr int kMaxConsolidationAttempts=5;
    static constexpr int kVolatileTtlDays=7;
};

}  // namespace starling::replay

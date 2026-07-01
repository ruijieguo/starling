// test_memory_ops.cpp — remember/tick_all 管线编排(2026-06-11 自 Python 归位)。
// 钉住编排语义本身:幂等键内容确定性、先 engram 后抽取、仅 accepted/idempotent
// 才抽取、tick 三连的返回形状。LLM 用 FakeLLMAdapter,零网络。

#include "starling/memory/memory_ops.hpp"

#include "starling/embedding/embedding_adapter.hpp"
#include "starling/extractor/fake_llm_adapter.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/runtime_health.hpp"
#include "starling/vector/vector_index.hpp"

#include <gtest/gtest.h>

#include <algorithm>
#include <memory>
#include <string>

namespace starling::memoryops {

namespace {

constexpr const char* kCannedJson =
    R"JSON([{"holder":"self","holder_perspective":"FIRST_PERSON","subject":"Bob","predicate":"responsible_for","object":"auth","modality":"BELIEVES","polarity":"POS","nesting_depth":0}])JSON";

std::unique_ptr<persistence::SqliteAdapter> make_adapter() {
    auto a = persistence::SqliteAdapter::open(":memory:");
    persistence::MigrationRunner(a->connection().raw()).migrate_to_latest();
    return a;
}

int row_count(persistence::Connection& conn, const char* sql) {
    sqlite3_stmt* raw = nullptr;
    EXPECT_EQ(sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr), SQLITE_OK);
    persistence::StmtHandle h(raw);
    EXPECT_EQ(sqlite3_step(h.get()), SQLITE_ROW);
    return sqlite3_column_int(h.get(), 0);
}

RememberParams params(std::string_view text) {
    RememberParams p;
    p.tenant_id          = "default";
    p.holder_id          = "cog-self";
    p.adapter_name       = "facade";
    p.source_prefix      = "mem-";
    p.created_at_iso8601 = "2026-06-11T10:00:00Z";
    p.payload.assign(text.begin(), text.end());
    return p;
}

}  // namespace

TEST(MemoryOps, RememberThenIdempotentRerun) {
    auto a = make_adapter();
    extractor::FakeLLMAdapter llm;
    llm.set_default_response(extractor::LLMResponse{.raw_xml = kCannedJson, .ok = true});

    const auto r1 = remember(*a, llm, /*prompt_template=*/"", params("Bob owns auth"));
    EXPECT_EQ(r1.outcome, "accepted");
    EXPECT_FALSE(r1.engram_ref.empty());
    EXPECT_EQ(r1.statement_ids.size(), 1u);
    EXPECT_EQ(row_count(a->connection(), "SELECT COUNT(*) FROM engrams"), 1);
    EXPECT_EQ(row_count(a->connection(), "SELECT COUNT(*) FROM statements"), 1);

    // 同文本重忆:engram 幂等命中(内容确定性 sha256 键),抽取 noop,
    // 不重复入库——管线顺序规则与幂等键派生都在被测函数内。
    const auto r2 = remember(*a, llm, "", params("Bob owns auth"));
    EXPECT_EQ(r2.outcome, "idempotent");
    EXPECT_EQ(r2.engram_ref, r1.engram_ref);
    EXPECT_TRUE(r2.statement_ids.empty());
    EXPECT_EQ(row_count(a->connection(), "SELECT COUNT(*) FROM engrams"), 1);
    EXPECT_EQ(row_count(a->connection(), "SELECT COUNT(*) FROM statements"), 1);
}

TEST(MemoryOps, TickAllAdvancesEmbeddingAndReturnsShape) {
    auto a = make_adapter();
    extractor::FakeLLMAdapter llm;
    llm.set_default_response(extractor::LLMResponse{.raw_xml = kCannedJson, .ok = true});
    ASSERT_EQ(remember(*a, llm, "", params("Bob owns auth")).outcome, "accepted");

    embedding::StubEmbeddingAdapter emb(8);
    vector::SqliteBlobVectorIndex idx;
    embedding::EmbeddingWorker worker(*a, emb, idx);
    prospective::PolicyEngine policy(*a);

    const auto t = tick_all(*a, worker, policy, "2026-06-11T10:05:00Z");
    EXPECT_EQ(t.embedded, 1);   // 刚写入的语句被嵌入
    EXPECT_EQ(t.fired, 0);
    EXPECT_EQ(t.broken, 0);
    EXPECT_EQ(t.auto_withdrawn, 0);
    EXPECT_EQ(row_count(a->connection(), "SELECT COUNT(*) FROM statement_vectors"), 1);
}

// ── P2.o 运行时闭环 ──────────────────────────────────────────────────────────
// 根因回归:生产语句写经 StatementWriter 不经 Bus::write,挂在 Bus::write 尾部
// 的订阅者泵在 remember 路径永不运行(投影/信念/再巩固/在线回放全部缺席)。
// 泵宿主归位 memoryops::remember 后,以下行为必须成立。

TEST(MemoryOps, RememberRunsSubscriberPump) {
    auto a = make_adapter();
    extractor::FakeLLMAdapter llm;
    llm.set_default_response(extractor::LLMResponse{.raw_xml = kCannedJson, .ok = true});

    ASSERT_EQ(remember(*a, llm, "", params("Bob owns auth")).outcome, "accepted");

    // 泵的 replay_online 订阅者跑过:在线触发计数 +1。
    EXPECT_EQ(row_count(a->connection(),
        "SELECT online_trigger_counter FROM replay_scheduler_state WHERE id=1"), 1);
    // 出生 salience = 中性 affect 公式值(≈0.0144),必须超过采样器 w_min,
    // 否则该语句永远不会被 Replay 采样巩固(根因之二回归)。
    EXPECT_EQ(row_count(a->connection(),
        "SELECT COUNT(*) FROM statements WHERE salience > 0.01"), 1);
}

TEST(MemoryOps, ThirdRememberTriggersOnlineConsolidation) {
    auto a = make_adapter();
    extractor::FakeLLMAdapter llm;
    llm.set_default_response(extractor::LLMResponse{.raw_xml = kCannedJson, .ok = true});

    ASSERT_EQ(remember(*a, llm, "", params("text one")).outcome, "accepted");
    ASSERT_EQ(remember(*a, llm, "", params("text two")).outcome, "accepted");
    ASSERT_EQ(remember(*a, llm, "", params("text three")).outcome, "accepted");

    // 第 3 次写触发在线采样窗(kOnlineTrigger=3):计数归零 + 至少一条语句
    // volatile→consolidated(op_compress 一触即晋升)。
    EXPECT_EQ(row_count(a->connection(),
        "SELECT online_trigger_counter FROM replay_scheduler_state WHERE id=1"), 0);
    EXPECT_GE(row_count(a->connection(),
        "SELECT COUNT(*) FROM statements WHERE consolidation_state='consolidated'"), 1);
}

TEST(MemoryOps, TickAllConsolidatesProjectsAndDispatches) {
    auto a = make_adapter();
    extractor::FakeLLMAdapter llm;
    llm.set_default_response(extractor::LLMResponse{.raw_xml = kCannedJson, .ok = true});
    ASSERT_EQ(remember(*a, llm, "", params("Bob owns auth")).outcome, "accepted");
    ASSERT_GE(row_count(a->connection(),
        "SELECT COUNT(*) FROM statements WHERE consolidation_state='volatile'"), 1);

    embedding::StubEmbeddingAdapter emb(8);
    vector::SqliteBlobVectorIndex idx;
    embedding::EmbeddingWorker worker(*a, emb, idx);
    prospective::PolicyEngine policy(*a);

    const auto t = tick_all(*a, worker, policy, "2026-06-11T10:05:00Z");

    // idle 批扫掉积压 volatile:写→读闭环的巩固半边。
    EXPECT_GE(t.replay_sampled, 1);
    EXPECT_GE(t.consolidated, 1);
    EXPECT_EQ(row_count(a->connection(),
        "SELECT COUNT(*) FROM statements WHERE consolidation_state='volatile'"), 0);
    // 出箱收敛:in_process Accept-all 消费者把 pending 全部标 delivered。
    EXPECT_GE(t.dispatched, 1);
    EXPECT_EQ(row_count(a->connection(),
        "SELECT COUNT(*) FROM bus_events WHERE dispatch_status='pending'"), 0);
    // 投影兜底批不抛且计数非负(remember 路径的事件已被泵内 PM 消费)。
    EXPECT_GE(t.projected, 0);
}

TEST(MemoryOps, TickAllRecordsStageTimings) {
    auto a = make_adapter();
    extractor::FakeLLMAdapter llm;
    llm.set_default_response(extractor::LLMResponse{.raw_xml = kCannedJson, .ok = true});
    ASSERT_EQ(remember(*a, llm, "", params("Bob owns auth")).outcome, "accepted");

    embedding::StubEmbeddingAdapter emb(8);
    vector::SqliteBlobVectorIndex idx;
    embedding::EmbeddingWorker worker(*a, emb, idx);
    prospective::PolicyEngine policy(*a);

    const auto t = tick_all(*a, worker, policy, "2026-06-11T10:05:00Z");

    ASSERT_EQ(t.stage_timings_ms.size(), 8U);
    EXPECT_EQ(t.stage_timings_ms[0].stage, "embed");
    EXPECT_EQ(t.stage_timings_ms[1].stage, "policy");
    EXPECT_EQ(t.stage_timings_ms[2].stage, "common_ground");
    EXPECT_EQ(t.stage_timings_ms[3].stage, "replay_oscillation_guard");
    EXPECT_EQ(t.stage_timings_ms[4].stage, "replay_ttl_sweep");
    EXPECT_EQ(t.stage_timings_ms[5].stage, "replay_idle");
    EXPECT_EQ(t.stage_timings_ms[6].stage, "projection");
    EXPECT_EQ(t.stage_timings_ms[7].stage, "outbox");
    for (const auto& timing : t.stage_timings_ms) {
        EXPECT_GE(timing.duration_ms, 0);
    }
}

// ── P3.c live-wiring LW.2: health-gated load-shedding ───────────────────────

// Helper: does stages_skipped contain the given label?
static bool skipped(const TickOutcome& t, const std::string& label) {
    return std::find(t.stages_skipped.begin(), t.stages_skipped.end(), label)
           != t.stages_skipped.end();
}

// Helper: does stage_timings_ms contain the given label?
static bool timed(const TickOutcome& t, const std::string& label) {
    for (const auto& st : t.stage_timings_ms) {
        if (st.stage == label) {
            return true;
        }
    }
    return false;
}

// READY (regression): default param keeps all 8 stages running, stages_skipped
// empty, timings all 8.
TEST(MemoryOps, TickAllReadyRunsAllStages) {
    auto a = make_adapter();
    extractor::FakeLLMAdapter llm;
    llm.set_default_response(extractor::LLMResponse{.raw_xml = kCannedJson, .ok = true});
    ASSERT_EQ(remember(*a, llm, "", params("Alice reads code")).outcome, "accepted");

    embedding::StubEmbeddingAdapter emb(8);
    vector::SqliteBlobVectorIndex idx;
    embedding::EmbeddingWorker worker(*a, emb, idx);
    prospective::PolicyEngine policy(*a);

    // Explicit READY — same as default-param path.
    const auto t = tick_all(*a, worker, policy, "2026-06-11T10:05:00Z",
                            RuntimeHealth::READY);

    EXPECT_TRUE(t.stages_skipped.empty());
    ASSERT_EQ(t.stage_timings_ms.size(), 8U);
    // embed ran: the pending-embedding row got embedded.
    EXPECT_EQ(t.embedded, 1);
}

// DEGRADED causality: soft stages are NOT run (embed effect absent); critical
// stages DO run (outbox drains). stages_skipped == 4 soft labels. Timings only
// for the 4 critical stages.
TEST(MemoryOps, TickAllDegradedShedsEmbedLeavesRowUnembedded) {
    auto a = make_adapter();
    extractor::FakeLLMAdapter llm;
    llm.set_default_response(extractor::LLMResponse{.raw_xml = kCannedJson, .ok = true});
    // Seed a statement that needs embedding so the embed stage would do real work.
    ASSERT_EQ(remember(*a, llm, "", params("Charlie deploys daily")).outcome, "accepted");

    embedding::StubEmbeddingAdapter emb(8);
    vector::SqliteBlobVectorIndex idx;
    embedding::EmbeddingWorker worker(*a, emb, idx);
    prospective::PolicyEngine policy(*a);

    const auto t = tick_all(*a, worker, policy, "2026-06-11T10:05:00Z",
                            RuntimeHealth::DEGRADED);

    // Causality: soft stage effect absent — row remains un-embedded.
    EXPECT_EQ(t.embedded, 0);
    EXPECT_EQ(row_count(a->connection(),
        "SELECT COUNT(*) FROM statement_vectors"), 0);

    // stages_skipped == the 4 soft labels (order matches tick order).
    ASSERT_EQ(t.stages_skipped.size(), 4U);
    EXPECT_TRUE(skipped(t, "embed"));
    EXPECT_TRUE(skipped(t, "common_ground"));
    EXPECT_TRUE(skipped(t, "replay_idle"));
    EXPECT_TRUE(skipped(t, "projection"));

    // Timings only for the 4 critical stages.
    EXPECT_EQ(t.stage_timings_ms.size(), 4U);
    EXPECT_TRUE(timed(t, "policy"));
    EXPECT_TRUE(timed(t, "replay_oscillation_guard"));
    EXPECT_TRUE(timed(t, "replay_ttl_sweep"));
    EXPECT_TRUE(timed(t, "outbox"));

    // Critical stages ran: outbox dispatched pending bus events (bus_events seeded
    // by remember's subscriber pump; Accept-all consumer marks them delivered).
    EXPECT_EQ(row_count(a->connection(),
        "SELECT COUNT(*) FROM bus_events WHERE dispatch_status='pending'"), 0);
}

// DRAINING: only outbox runs; 7 stages skipped, outbox NOT skipped; outbox
// still drains pending delivery.
TEST(MemoryOps, TickAllDrainingKeepsOnlyOutbox) {
    auto a = make_adapter();
    extractor::FakeLLMAdapter llm;
    llm.set_default_response(extractor::LLMResponse{.raw_xml = kCannedJson, .ok = true});
    ASSERT_EQ(remember(*a, llm, "", params("Dave ships features")).outcome, "accepted");

    embedding::StubEmbeddingAdapter emb(8);
    vector::SqliteBlobVectorIndex idx;
    embedding::EmbeddingWorker worker(*a, emb, idx);
    prospective::PolicyEngine policy(*a);

    const auto t = tick_all(*a, worker, policy, "2026-06-11T10:05:00Z",
                            RuntimeHealth::DRAINING);

    // 7 stages skipped; outbox is NOT in the skip list.
    ASSERT_EQ(t.stages_skipped.size(), 7U);
    EXPECT_FALSE(skipped(t, "outbox"));
    EXPECT_TRUE(skipped(t, "embed"));
    EXPECT_TRUE(skipped(t, "policy"));
    EXPECT_TRUE(skipped(t, "common_ground"));
    EXPECT_TRUE(skipped(t, "replay_oscillation_guard"));
    EXPECT_TRUE(skipped(t, "replay_ttl_sweep"));
    EXPECT_TRUE(skipped(t, "replay_idle"));
    EXPECT_TRUE(skipped(t, "projection"));

    // Only outbox timed.
    ASSERT_EQ(t.stage_timings_ms.size(), 1U);
    EXPECT_EQ(t.stage_timings_ms[0].stage, "outbox");

    // Outbox still drains (causality: critical delivery preserved under DRAINING).
    EXPECT_EQ(row_count(a->connection(),
        "SELECT COUNT(*) FROM bus_events WHERE dispatch_status='pending'"), 0);
}

// UNREADY: all 8 stages skipped; no timings; no side effects.
TEST(MemoryOps, TickAllUnreadySkipsAllStages) {
    auto a = make_adapter();
    extractor::FakeLLMAdapter llm;
    llm.set_default_response(extractor::LLMResponse{.raw_xml = kCannedJson, .ok = true});
    ASSERT_EQ(remember(*a, llm, "", params("Eve reviews PRs")).outcome, "accepted");

    embedding::StubEmbeddingAdapter emb(8);
    vector::SqliteBlobVectorIndex idx;
    embedding::EmbeddingWorker worker(*a, emb, idx);
    prospective::PolicyEngine policy(*a);

    const auto t = tick_all(*a, worker, policy, "2026-06-11T10:05:00Z",
                            RuntimeHealth::UNREADY);

    ASSERT_EQ(t.stages_skipped.size(), 8U);
    EXPECT_TRUE(t.stage_timings_ms.empty());
    EXPECT_EQ(t.embedded, 0);
}

}  // namespace starling::memoryops

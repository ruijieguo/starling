// test_remember_phases.cpp — remember 三相拆分(方案2 option B)。
// 钉:prepare+extract+commit ≡ 单体 remember(落库 + outcome);should_extract
// =false 短路不 persist;FAILED 仍写 3 attempt;门中途关 → commit 抛。零网络。
#include "starling/memory/memory_ops.hpp"

#include "starling/extractor/extraction_span_key.hpp"
#include "starling/extractor/fake_llm_adapter.hpp"
#include "starling/governance/write_gate.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <gtest/gtest.h>
#include <memory>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace starling::memoryops {
namespace {

constexpr const char* kJson =
    R"JSON([{"holder":"self","holder_perspective":"FIRST_PERSON","subject":"Bob","predicate":"responsible_for","object":"auth","modality":"BELIEVES","polarity":"POS","nesting_depth":0}])JSON";

std::unique_ptr<persistence::SqliteAdapter> make_adapter() {
    auto a = persistence::SqliteAdapter::open(":memory:");
    persistence::MigrationRunner(a->connection().raw()).migrate_to_latest();
    return a;
}

int row_count(persistence::Connection& conn, const std::string& table,
              const std::string& where = "1=1") {
    sqlite3_stmt* raw = nullptr;
    EXPECT_EQ(sqlite3_prepare_v2(conn.raw(),
        ("SELECT COUNT(*) FROM " + table + " WHERE " + where).c_str(),
        -1, &raw, nullptr), SQLITE_OK);
    persistence::StmtHandle h(raw);
    sqlite3_step(h.get());
    return sqlite3_column_int(h.get(), 0);
}

RememberParams rp(std::string_view text) {
    RememberParams p;
    p.tenant_id          = "default";
    p.holder_id          = "cog-self";
    p.interlocutor       = "";
    p.adapter_name       = "facade";
    p.source_prefix      = "mem-";
    p.created_at_iso8601 = "2026-07-12T10:00:00Z";
    p.payload.assign(text.begin(), text.end());
    return p;
}

extractor::LLMResponse ok_json() {
    return extractor::LLMResponse{.raw_xml = kJson, .ok = true};
}

class RecordingLLMAdapter final : public extractor::LLMAdapter {
public:
    extractor::LLMResponse extract(std::string_view prompt,
                                   std::string_view) override {
        prompts.emplace_back(prompt);
        return {.raw_xml = "[]", .ok = true};
    }

    std::vector<std::string> prompts;
};

}  // namespace

TEST(RememberPhases, PhasedEqualsMonolith) {
    auto ma = make_adapter();
    extractor::FakeLLMAdapter mllm; mllm.set_default_response(ok_json());
    const auto mono = remember(*ma, mllm, "", rp("hi bob"));

    auto pa = make_adapter();
    extractor::FakeLLMAdapter pllm; pllm.set_default_response(ok_json());
    const auto prepared = remember_prepare(*pa, rp("hi bob"));
    EXPECT_TRUE(prepared.should_extract);
    const auto llm = extract_llm(*pa, pllm, "", rp("hi bob"));
    EXPECT_EQ(sqlite3_get_autocommit(pa->connection().raw()), 1);   // extract 无开事务
    const auto phased = remember_commit(*pa, pllm, rp("hi bob"), prepared, llm);

    EXPECT_EQ(mono.outcome, phased.outcome);
    EXPECT_EQ(mono.statement_ids.size(), phased.statement_ids.size());
    EXPECT_EQ(mono.extraction_failed, phased.extraction_failed);
    EXPECT_EQ(row_count(ma->connection(), "statements"),
              row_count(pa->connection(), "statements"));
    EXPECT_EQ(row_count(ma->connection(), "engrams"),
              row_count(pa->connection(), "engrams"));
}

TEST(RememberPhases, CommitShortCircuitsWhenShouldNotExtract) {
    // 直接构造 should_extract=false 的 prepared(no_store 语义)→ commit 不 persist。
    auto pa = make_adapter();
    extractor::FakeLLMAdapter pllm;
    RememberPrepared no_store;
    no_store.outcome        = "no_store";
    no_store.should_extract = false;
    const extractor::ExtractionLlmResult empty;
    const int before = row_count(pa->connection(), "statements");
    const auto r = remember_commit(*pa, pllm, rp("x"), no_store, empty);
    EXPECT_EQ(r.outcome, "no_store");
    EXPECT_TRUE(r.statement_ids.empty());
    EXPECT_FALSE(r.extraction_failed);
    EXPECT_EQ(row_count(pa->connection(), "statements"), before);   // 零 persist
}

TEST(RememberPhases, FailedExtractionStillPersistsAttemptRows) {
    auto pa = make_adapter();
    extractor::FakeLLMAdapter pllm;                    // ok=false all
    const auto prepared = remember_prepare(*pa, rp("hi"));
    const auto llm = extract_llm(*pa, pllm, "", rp("hi"));
    EXPECT_EQ(llm.attempts.size(), 3u);
    const auto r = remember_commit(*pa, pllm, rp("hi"), prepared, llm);
    EXPECT_TRUE(r.extraction_failed);
    EXPECT_EQ(row_count(pa->connection(), "extraction_attempt", "status='failed'"), 3);
}

TEST(RememberPhases, CommitThrowsWhenGateClosesMidTurn) {
    auto pa = make_adapter();
    extractor::FakeLLMAdapter pllm; pllm.set_default_response(ok_json());
    const auto prepared = remember_prepare(*pa, rp("hi"));   // 门开
    const auto llm = extract_llm(*pa, pllm, "", rp("hi"));
    pa->set_write_admit([] { return false; });               // 生成期间关门
    EXPECT_THROW(remember_commit(*pa, pllm, rp("hi"), prepared, llm),
                 governance::WriteGateRejected);
}

TEST(RememberPhases, CommitAllRollsBackEarlierChannelsWhenLaterChannelFails) {
    auto pa = make_adapter();
    extractor::FakeLLMAdapter pllm;
    pllm.set_default_response(ok_json());
    const auto p = rp("hi");
    const auto prepared = remember_prepare(*pa, p);

    RememberLlmBundle extracted;
    extracted.belief = extract_llm(*pa, pllm, "", p);
    extracted.general_fact = extracted.belief;
    extracted.episodic.ok = true;
    extractor::ParsedEpisodicEvent event;
    event.seq = 1;
    event.actor = "Alice";
    event.actor_kind = "cognizer";
    event.action = "moved";
    event.object_value = "the ball";
    event.canonical_object_hash = "episodic-hash";
    extracted.episodic.events.push_back(std::move(event));

    const int statements_before = row_count(pa->connection(), "statements");
    const int events_before = row_count(pa->connection(), "bus_events");
    pa->connection().exec(
        "CREATE TRIGGER fail_second_extraction_run "
        "BEFORE INSERT ON governance_pipeline_run "
        "WHEN (SELECT COUNT(*) FROM governance_pipeline_run) > 0 "
        "BEGIN SELECT RAISE(ABORT, 'injected later-channel failure'); END");

    EXPECT_THROW(remember_commit_all(*pa, pllm, p, prepared, extracted),
                 persistence::SqliteError);
    EXPECT_EQ(row_count(pa->connection(), "statements"), statements_before);
    EXPECT_EQ(row_count(pa->connection(), "bus_events"), events_before);
    EXPECT_EQ(row_count(pa->connection(), "governance_pipeline_run"), 0);
    EXPECT_EQ(row_count(pa->connection(), "extraction_attempt"), 0);
    EXPECT_EQ(row_count(pa->connection(), "episodic_events"), 0);
}

TEST(RememberPhases, CommitAllIsNoOpWhenTenantClearedDuringExtract) {
    // 锁外抽取期间设置页清空了租户:prepare 写的 engram 已不在,commit 必须零写入
    // 返回 source_missing,而不是写出证据悬空的语句。
    auto pa = make_adapter();
    extractor::FakeLLMAdapter pllm;
    pllm.set_default_response(ok_json());
    const auto p = rp("hi bob");
    const auto prepared = remember_prepare(*pa, p);
    ASSERT_TRUE(prepared.should_extract);
    const RememberPrompts prompts{.belief = "{convo}", .episodic = "{passage}",
                                  .general_fact = "{convo}"};
    const auto extracted = remember_extract_all(*pa, pllm, p, prompts);

    (void)clear_tenant(*pa, p.tenant_id);   // 抽取期间被清空

    const auto out = remember_commit_all(*pa, pllm, p, prepared, extracted);
    EXPECT_EQ(out.outcome, "source_missing");
    EXPECT_TRUE(out.engram_ref.empty());
    EXPECT_TRUE(out.statement_ids.empty());
    EXPECT_FALSE(out.extraction_failed);
    EXPECT_EQ(row_count(pa->connection(), "statements"), 0);
    EXPECT_EQ(row_count(pa->connection(), "engrams"), 0);
    EXPECT_EQ(row_count(pa->connection(), "governance_pipeline_run"), 0);
}

TEST(RememberPhases, CoreExpandsAllRememberPromptsBeforeLlmCalls) {
    auto adapter = make_adapter();
    RecordingLLMAdapter llm;
    const RememberPrompts prompts{
        .belief = "BELIEF::{convo}",
        .episodic = "EPISODIC::{passage}",
        .general_fact = "GENERAL::{self}::{self}::{convo}",
    };

    extractor::ValidationPolicy one_call_per_channel;   // 本测只看提示词展开，不看空结果重试
    one_call_per_channel.empty_result_retry_budget = 0;
    (void)remember_extract_all(*adapter, llm, rp("hi"), prompts, one_call_per_channel);

    ASSERT_EQ(llm.prompts.size(), 3u);
    EXPECT_EQ(llm.prompts[0], "BELIEF::hi");
    EXPECT_EQ(llm.prompts[1], "GENERAL::cog-self::cog-self::hi");
    EXPECT_EQ(llm.prompts[2], "EPISODIC::hi");
}

// 2026-11-18 rise 真机反馈：一般事实这一路对对话类输入回 `[]` 是正确输出，空结果重试
// 只是白花调用；两路共用 chunk 级 span key,账本分不出空结果来自哪一路。
TEST(RememberPhases, GeneralFactChannelDoesNotRetryEmptyAndIsAttributed) {
    auto adapter = make_adapter();
    RecordingLLMAdapter llm;   // 每次都回 []
    const RememberPrompts prompts{
        .belief = "BELIEF::{convo}",
        .episodic = "EPISODIC::{passage}",
        .general_fact = "GENERAL::{convo}",
    };
    const auto params = rp("客服对话");
    const auto prepared = remember_prepare(*adapter, params);
    const auto bundle = remember_extract_all(*adapter, llm, params, prompts);

    std::size_t belief_calls = 0, general_calls = 0, episodic_calls = 0;
    for (const auto& prompt : llm.prompts) {
        if (prompt.rfind("BELIEF::", 0) == 0) ++belief_calls;
        if (prompt.rfind("GENERAL::", 0) == 0) ++general_calls;
        if (prompt.rfind("EPISODIC::", 0) == 0) ++episodic_calls;
    }
    EXPECT_EQ(belief_calls, 3u);    // 1 + 默认预算 2
    EXPECT_EQ(general_calls, 1u);   // 一般事实不重试
    EXPECT_EQ(episodic_calls, 1u);
    EXPECT_EQ(bundle.belief.channel, "belief");
    EXPECT_EQ(bundle.general_fact.channel, "general_fact");

    (void)remember_commit_all(*adapter, llm, params, prepared, bundle);
    auto& conn = adapter->connection();
    EXPECT_EQ(row_count(conn, "extraction_attempt", "status='empty'"), 4);
    // 两路的 empty 行落在两个不同的 chunk key 下。
    EXPECT_EQ(row_count(conn, "(SELECT DISTINCT extraction_span_key FROM extraction_attempt "
                              "WHERE status='empty')"), 2);
    // run 的 metadata 记了通道，按通道统计不必再靠 prompt_tokens 猜。
    EXPECT_EQ(row_count(conn,
        "extraction_attempt a JOIN governance_pipeline_run p ON p.id=a.pipeline_run_id",
        "a.status='empty' AND json_extract(p.metadata_json,'$.channel')='belief'"), 3);
    EXPECT_EQ(row_count(conn,
        "extraction_attempt a JOIN governance_pipeline_run p ON p.id=a.pipeline_run_id",
        "a.status='empty' AND json_extract(p.metadata_json,'$.channel')='general_fact'"), 1);
}

TEST(RememberPhases, BeliefChunkKeyIsUnchangedForExistingRows) {
    // belief 的 chunk key 保持 1478029 及更早的取法，旧行与新行按同一个键可比。
    auto adapter = make_adapter();
    extractor::FakeLLMAdapter llm;
    llm.set_default_response({.raw_xml = "[]", .ok = true});
    const auto params = rp("hi");
    const auto prepared = remember_prepare(*adapter, params);
    extractor::ValidationPolicy no_retry;
    no_retry.empty_result_retry_budget = 0;
    const auto llm_result = extract_llm(*adapter, llm, "", params, no_retry);
    (void)remember_commit(*adapter, llm, params, prepared, llm_result, no_retry);
    const std::string expected = extractor::compute_extraction_span_key(
        prepared.engram_ref, 0, "__chunk__", "__chunk__");
    EXPECT_EQ(row_count(adapter->connection(), "extraction_attempt",
                        "status='empty' AND extraction_span_key='" + expected + "'"), 1);
}

TEST(RememberPhases, UnknownChannelIsRejectedAtPersist) {
    auto adapter = make_adapter();
    extractor::FakeLLMAdapter llm;
    llm.set_default_response({.raw_xml = "[]", .ok = true});
    const auto params = rp("hi");
    const auto prepared = remember_prepare(*adapter, params);
    auto llm_result = extract_llm(*adapter, llm, "", params);
    llm_result.channel = "episodic";
    EXPECT_THROW((void)remember_commit(*adapter, llm, params, prepared, llm_result),
                 std::invalid_argument);
}

}  // namespace starling::memoryops

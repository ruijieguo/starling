// test_remember_phases.cpp — remember 三相拆分(方案2 option B)。
// 钉:prepare+extract+commit ≡ 单体 remember(落库 + outcome);should_extract
// =false 短路不 persist;FAILED 仍写 3 attempt;门中途关 → commit 抛。零网络。
#include "starling/memory/memory_ops.hpp"

#include "starling/extractor/fake_llm_adapter.hpp"
#include "starling/governance/write_gate.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <gtest/gtest.h>
#include <memory>
#include <string>

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

}  // namespace starling::memoryops

// test_converse_phases.cpp — converse 三相拆分(2026-07-05 锁外生成)。
// 钉住:prepare+generate+commit ≡ 单体 converse(parity)、generate 失败 →
// commit 干净无回复、写门中途关闭 → reply 保留 + remember_ok=false。零网络。

#include "starling/memory/memory_ops.hpp"

#include "starling/embedding/embedding_adapter.hpp"
#include "starling/extractor/fake_llm_adapter.hpp"
#include "starling/governance/write_gate.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/retrieval/semantic_retriever.hpp"
#include "starling/runtime_health.hpp"
#include "starling/vector/vector_index.hpp"

#include <gtest/gtest.h>

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

ConverseParams conv_params(std::string_view message) {
    ConverseParams cp;
    cp.tenant_id          = "default";
    cp.holder_id          = "cog-self";
    cp.interlocutor       = "alice";
    cp.adapter_name       = "facade";
    cp.source_prefix      = "conv-";
    cp.created_at_iso8601 = "2026-07-05T10:00:00Z";
    cp.message            = std::string(message);
    cp.recall_k           = 6;
    return cp;
}

struct Fixture {   // 每条路径一套独立 :memory: 库(parity 需要隔离副作用)
    std::unique_ptr<persistence::SqliteAdapter> adapter = make_adapter();
    embedding::StubEmbeddingAdapter emb{8};
    vector::SqliteBlobVectorIndex idx;
    retrieval::SemanticRetriever semantic{*adapter, emb, idx};
    extractor::FakeLLMAdapter chat;
    extractor::FakeLLMAdapter extraction;
    Fixture() {
        chat.set_default_response(extractor::LLMResponse{.raw_xml = "Reply text.", .ok = true});
        extraction.set_default_response(extractor::LLMResponse{.raw_xml = kCannedJson, .ok = true});
    }
};

void expect_parity(const ConverseOutcome& mono, const ConverseOutcome& phased) {
    EXPECT_EQ(mono.ok, phased.ok);
    EXPECT_EQ(mono.reply, phased.reply);
    EXPECT_EQ(mono.error, phased.error);
    EXPECT_EQ(mono.context_pack, phased.context_pack);
    EXPECT_EQ(mono.abstained, phased.abstained);
    EXPECT_EQ(mono.statement_ids.size(), phased.statement_ids.size());  // id 含随机成分,比数量
    EXPECT_EQ(mono.remember_ok, phased.remember_ok);
    EXPECT_EQ(mono.remember_error, phased.remember_error);
    EXPECT_EQ(mono.gen_total_tokens, phased.gen_total_tokens);
}

}  // namespace

TEST(ConversePhases, PhasedEqualsMonolithNonStreaming) {
    Fixture mono_fx;
    const auto mono = converse(*mono_fx.adapter, mono_fx.chat, mono_fx.extraction,
                               mono_fx.semantic, "", conv_params("hello"), {}, {});
    Fixture phased_fx;
    const auto prepared = converse_prepare(*phased_fx.adapter, phased_fx.semantic,
                                           conv_params("hello"));
    const auto gen_resp = phased_fx.chat.generate_stream(prepared.prompt, {});
    const auto phased = converse_commit(*phased_fx.adapter, phased_fx.extraction, "",
                                        conv_params("hello"), prepared, gen_resp);
    expect_parity(mono, phased);
    EXPECT_TRUE(phased.ok);
    EXPECT_TRUE(phased.remember_ok);
}

TEST(ConversePhases, PhasedEqualsMonolithStreaming) {
    // 流式:两条路径都挂 sink,delta 拼接 == 最终 reply,且 parity 保持。
    Fixture mono_fx;
    std::string mono_streamed;
    const auto mono = converse(*mono_fx.adapter, mono_fx.chat, mono_fx.extraction,
                               mono_fx.semantic, "", conv_params("hi"), {},
                               [&mono_streamed](std::string_view d) { mono_streamed += d; });
    Fixture phased_fx;
    const auto prepared = converse_prepare(*phased_fx.adapter, phased_fx.semantic,
                                           conv_params("hi"));
    std::string phased_streamed;
    const auto gen_resp = phased_fx.chat.generate_stream(
        prepared.prompt, [&phased_streamed](std::string_view d) { phased_streamed += d; });
    const auto phased = converse_commit(*phased_fx.adapter, phased_fx.extraction, "",
                                        conv_params("hi"), prepared, gen_resp);
    expect_parity(mono, phased);
    EXPECT_EQ(mono_streamed, mono.reply);
    EXPECT_EQ(phased_streamed, phased.reply);
}

TEST(ConversePhases, CommitOnGenerateFailureIsCleanNoReply) {
    Fixture fx;
    const auto prepared = converse_prepare(*fx.adapter, fx.semantic, conv_params("hello"));
    const int before = row_count(fx.adapter->connection(),
                                 "SELECT COUNT(*) FROM statements");
    extractor::LLMResponse failed;
    failed.ok = false;
    failed.error = "transport_error:SSL connect error";
    const auto out = converse_commit(*fx.adapter, fx.extraction, "",
                                     conv_params("hello"), prepared, failed);
    EXPECT_FALSE(out.ok);
    EXPECT_EQ(out.error, "transport_error:SSL connect error");
    EXPECT_TRUE(out.reply.empty());
    EXPECT_TRUE(out.statement_ids.empty());
    EXPECT_FALSE(out.remember_ok);
    EXPECT_EQ(out.context_pack, prepared.context_pack);   // 轨迹仍可回显
    EXPECT_EQ(row_count(fx.adapter->connection(),
                        "SELECT COUNT(*) FROM statements"), before);  // 零沉淀
}

TEST(ConversePhases, PrepareFailsFastWhenGateClosed) {
    Fixture fx;
    fx.adapter->set_write_admit([] { return false; });
    EXPECT_THROW(converse_prepare(*fx.adapter, fx.semantic, conv_params("x")),
                 governance::WriteGateRejected);
}

TEST(ConversePhases, GateClosingMidTurnKeepsReplyAndFlagsRememberError) {
    // 模拟「锁外生成期间翻 DRAINING」:prepare 时门开,commit 前关门。
    Fixture fx;
    const auto prepared = converse_prepare(*fx.adapter, fx.semantic, conv_params("hello"));
    const auto gen_resp = fx.chat.generate_stream(prepared.prompt, {});
    fx.adapter->set_write_admit([] { return false; });
    const auto out = converse_commit(*fx.adapter, fx.extraction, "",
                                     conv_params("hello"), prepared, gen_resp);
    EXPECT_TRUE(out.ok);                       // 失败语义 A:回复绝不丢
    EXPECT_EQ(out.reply, "Reply text.");
    EXPECT_FALSE(out.remember_ok);
    EXPECT_FALSE(out.remember_error.empty());  // WriteGateRejected e.what() 可观测
}

}  // namespace starling::memoryops

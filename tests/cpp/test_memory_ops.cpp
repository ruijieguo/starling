// test_memory_ops.cpp — remember/tick_all 管线编排(2026-06-11 自 Python 归位)。
// 钉住编排语义本身:幂等键内容确定性、先 engram 后抽取、仅 accepted/idempotent
// 才抽取、tick 三连的返回形状。LLM 用 FakeLLMAdapter,零网络。

#include "starling/memory/memory_ops.hpp"

#include "starling/embedding/embedding_adapter.hpp"
#include "starling/extractor/fake_llm_adapter.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
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

}  // namespace starling::memoryops

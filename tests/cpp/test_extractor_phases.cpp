// test_extractor_phases.cpp — Extractor extract_llm/persist 拆分(方案2 option B)。
// 钉:extract_llm→persist ≡ 单体 run()(status + 落库逐行);extract_llm 零 DB、
// 返回后 autocommit==1(无开事务)。零网络(FakeLLM)。
#include "starling/extractor/extractor.hpp"

#include "starling/extractor/fake_llm_adapter.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <gtest/gtest.h>
#include <memory>
#include <vector>

namespace starling::extractor {
namespace {

constexpr const char* kSuccessJson =
    R"JSON([{"holder":"self","holder_perspective":"FIRST_PERSON","subject":"Bob","predicate":"responsible_for","object":"auth","modality":"BELIEVES","polarity":"POS","nesting_depth":0}])JSON";

std::unique_ptr<persistence::SqliteAdapter> make_adapter() {
    auto a = persistence::SqliteAdapter::open(":memory:");
    persistence::MigrationRunner(a->connection().raw()).migrate_to_latest();
    return a;
}

void seed_engram(persistence::Connection& conn) {
    sqlite3_exec(conn.raw(),
        "INSERT INTO engrams(id,tenant_id,content_hash,source_kind,ingest_policy,"
        "ingest_mode,privacy_class,retention_mode,refcount,payload_inline,created_at)"
        " VALUES('engram-1','default','hash-1','user_input','store','whole_record',"
        "'internal','audit_retain',0,X'','2026-05-23T10:00:00Z')",
        nullptr, nullptr, nullptr);
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

LLMResponse ok_json() { return LLMResponse{.raw_xml = kSuccessJson, .ok = true}; }

// #7(review 加固):比行值不只比行数——转录 bug 可能保留计数却改坏值。
// 返回按稳定序排的 "col|col|..." 行串,供两库逐行等值比较。
std::vector<std::string> dump_rows(persistence::Connection& conn, const std::string& sql) {
    std::vector<std::string> out;
    sqlite3_stmt* raw = nullptr;
    EXPECT_EQ(sqlite3_prepare_v2(conn.raw(), sql.c_str(), -1, &raw, nullptr), SQLITE_OK);
    persistence::StmtHandle h(raw);
    while (sqlite3_step(h.get()) == SQLITE_ROW) {
        std::string row;
        for (int c = 0; c < sqlite3_column_count(h.get()); ++c) {
            if (c) row.push_back('|');
            const unsigned char* t = sqlite3_column_text(h.get(), c);
            row += t ? reinterpret_cast<const char*>(t) : "<null>";
        }
        out.push_back(row);
    }
    return out;
}

}  // namespace

TEST(ExtractorPhases, PhasedEqualsMonolithSuccess) {
    auto ma = make_adapter(); seed_engram(ma->connection());
    FakeLLMAdapter mllm; mllm.set_default_response(ok_json());
    Extractor mex(ma->connection(), mllm);
    const auto mono = mex.run("engram-1", {1,2,3}, "cog-self", "default", {});

    auto pa = make_adapter(); seed_engram(pa->connection());
    FakeLLMAdapter pllm; pllm.set_default_response(ok_json());
    Extractor pex(pa->connection(), pllm);
    const auto llm = pex.extract_llm({1,2,3}, "cog-self", {});
    EXPECT_EQ(sqlite3_get_autocommit(pa->connection().raw()), 1);   // extract_llm 无开事务
    EXPECT_EQ(row_count(pa->connection(), "statements"), 0);         // extract_llm 零写
    EXPECT_EQ(row_count(pa->connection(), "pipeline_run"), 0);
    const auto phased = pex.persist("engram-1", "cog-self", "default", "", llm);

    EXPECT_EQ(mono.status, phased.status);
    EXPECT_EQ(mono.accepted_statement_ids.size(), phased.accepted_statement_ids.size());
    EXPECT_EQ(row_count(ma->connection(), "statements"),
              row_count(pa->connection(), "statements"));
    EXPECT_EQ(row_count(ma->connection(), "extraction_attempt", "status='success'"),
              row_count(pa->connection(), "extraction_attempt", "status='success'"));
    EXPECT_EQ(row_count(ma->connection(), "pipeline_run", "status='finished'"),
              row_count(pa->connection(), "pipeline_run", "status='finished'"));
    EXPECT_EQ(row_count(ma->connection(), "bus_events", "event_type='statement.written'"),
              row_count(pa->connection(), "bus_events", "event_type='statement.written'"));
    // #7:行级值 parity——语句内容 + attempt 行(status/error/tokens)逐行等值,
    // 而非仅计数。时戳列(created_at/started_at)不入比较键(#8:聚簇到 persist 时刻,
    // 两库各自的 wall-clock 本就不同)。
    EXPECT_EQ(dump_rows(ma->connection(),
                  "SELECT subject_id,predicate,canonical_object_hash,holder_id "
                  "FROM statements ORDER BY predicate,canonical_object_hash"),
              dump_rows(pa->connection(),
                  "SELECT subject_id,predicate,canonical_object_hash,holder_id "
                  "FROM statements ORDER BY predicate,canonical_object_hash"));
    EXPECT_EQ(dump_rows(ma->connection(),
                  "SELECT attempt_number,status,error,total_tokens "
                  "FROM extraction_attempt ORDER BY extraction_span_key,attempt_number"),
              dump_rows(pa->connection(),
                  "SELECT attempt_number,status,error,total_tokens "
                  "FROM extraction_attempt ORDER BY extraction_span_key,attempt_number"));
}

TEST(ExtractorPhases, PhasedEqualsMonolithAllFail) {
    auto ma = make_adapter(); seed_engram(ma->connection());
    FakeLLMAdapter mllm;                       // no response → ok=false
    Extractor mex(ma->connection(), mllm);
    const auto mono = mex.run("engram-1", {1,2,3}, "cog-self", "default", {});

    auto pa = make_adapter(); seed_engram(pa->connection());
    FakeLLMAdapter pllm;
    Extractor pex(pa->connection(), pllm);
    const auto llm = pex.extract_llm({1,2,3}, "cog-self", {});
    EXPECT_EQ(llm.attempts.size(), 3u);        // 3 retries collected, no terminal
    const auto phased = pex.persist("engram-1", "cog-self", "default", "", llm);

    EXPECT_EQ(mono.status, ExtractionRunResult::Status::FAILED);
    EXPECT_EQ(phased.status, ExtractionRunResult::Status::FAILED);
    EXPECT_EQ(row_count(pa->connection(), "extraction_attempt", "status='failed'"), 3);
    EXPECT_EQ(row_count(ma->connection(), "extraction_attempt", "status='failed'"),
              row_count(pa->connection(), "extraction_attempt", "status='failed'"));
    EXPECT_EQ(row_count(ma->connection(), "bus_events", "event_type='extraction.failed'"),
              row_count(pa->connection(), "bus_events", "event_type='extraction.failed'"));
    // #7:失败 attempt 的 (number,status,error) 逐行等值(转录 bug 可能改坏 error 文本却保计数)。
    EXPECT_EQ(dump_rows(ma->connection(),
                  "SELECT attempt_number,status,error FROM extraction_attempt "
                  "ORDER BY attempt_number"),
              dump_rows(pa->connection(),
                  "SELECT attempt_number,status,error FROM extraction_attempt "
                  "ORDER BY attempt_number"));
}

TEST(ExtractorPhases, NoopShortCircuitOnReRun) {
    // 同 engram persist 两次(重忆):第二次 noop 短路,statements 不增。
    auto pa = make_adapter(); seed_engram(pa->connection());
    FakeLLMAdapter pllm; pllm.set_default_response(ok_json());
    Extractor pex(pa->connection(), pllm);
    const auto llm1 = pex.extract_llm({1,2,3}, "cog-self", {});
    pex.persist("engram-1", "cog-self", "default", "", llm1);
    const int after1 = row_count(pa->connection(), "statements");
    const auto llm2 = pex.extract_llm({1,2,3}, "cog-self", {});
    const auto r2 = pex.persist("engram-1", "cog-self", "default", "", llm2);
    EXPECT_EQ(row_count(pa->connection(), "statements"), after1);   // 无新增
    EXPECT_EQ(r2.status, ExtractionRunResult::Status::SUCCESS);
    EXPECT_GE(row_count(pa->connection(), "extraction_attempt", "status='noop'"), 1);
}

}  // namespace starling::extractor

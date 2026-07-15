// test_episodic_phases.cpp — EpisodicExtractor extract_llm/persist 拆分(option B 收尾)。
// 钉:extract_llm→persist ≡ 单体 extract()(event_statement_ids + statements/
// episodic_events 逐行);extract_llm 零 DB(autocommit==1、零写)。零网络(FakeLLM)。
#include "starling/extractor/episodic_extractor.hpp"

#include "starling/extractor/fake_llm_adapter.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <gtest/gtest.h>
#include <memory>
#include <string>
#include <vector>

namespace starling::extractor {
namespace {

// 两事件叙事:actor/action/theme 齐全 + location/time/participants。
constexpr const char* kEpisodicJson =
    R"JSON([{"actor":"Sally","action":"put","theme":"ball","location":"basket","time":"2026-05-23T10:00:00Z","participants":["Anne"]},)JSON"
    R"JSON({"actor":"Anne","action":"move","theme":"ball","location":"box","participants":[]}])JSON";

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

TEST(EpisodicPhases, PhasedEqualsMonolith) {
    auto ma = make_adapter(); seed_engram(ma->connection());
    FakeLLMAdapter mllm; mllm.set_default_response(LLMResponse{.raw_xml = kEpisodicJson, .ok = true});
    EpisodicExtractor mex(ma->connection(), mllm);
    const auto mono = mex.extract("passage", "engram-1", "default", "cog-self",
                                  "2026-05-23T10:00:00Z");

    auto pa = make_adapter(); seed_engram(pa->connection());
    FakeLLMAdapter pllm; pllm.set_default_response(LLMResponse{.raw_xml = kEpisodicJson, .ok = true});
    EpisodicExtractor pex(pa->connection(), pllm);
    const auto llm = pex.extract_llm("passage");
    EXPECT_TRUE(llm.ok);
    EXPECT_EQ(llm.events.size(), 2u);
    EXPECT_EQ(sqlite3_get_autocommit(pa->connection().raw()), 1);   // extract_llm 无开事务
    EXPECT_EQ(row_count(pa->connection(), "statements"), 0);         // extract_llm 零写
    const auto phased = pex.persist("engram-1", "default", "cog-self",
                                    "2026-05-23T10:00:00Z", llm);

    EXPECT_EQ(mono.event_statement_ids.size(), phased.event_statement_ids.size());
    EXPECT_EQ(row_count(ma->connection(), "statements"),
              row_count(pa->connection(), "statements"));
    EXPECT_EQ(row_count(ma->connection(), "episodic_events"),
              row_count(pa->connection(), "episodic_events"));
    // 行级值 parity:语句内容(subject/predicate/object/holder)+ episodic_events
    // 扩展行(seq/location/participants/action)逐行等值,而非仅计数。
    EXPECT_EQ(dump_rows(ma->connection(),
                  "SELECT subject_id,predicate,canonical_object_hash,holder_id,modality "
                  "FROM statements ORDER BY predicate,canonical_object_hash"),
              dump_rows(pa->connection(),
                  "SELECT subject_id,predicate,canonical_object_hash,holder_id,modality "
                  "FROM statements ORDER BY predicate,canonical_object_hash"));
    EXPECT_EQ(dump_rows(ma->connection(),
                  "SELECT seq,location,participants_json,action_raw "
                  "FROM episodic_events ORDER BY seq"),
              dump_rows(pa->connection(),
                  "SELECT seq,location,participants_json,action_raw "
                  "FROM episodic_events ORDER BY seq"));
}

TEST(EpisodicPhases, LlmFailNoTxNoWrite) {
    // 适配器无响应 → ok=false、events 空;persist 不开事务、零写(镜像单体 early-return)。
    auto pa = make_adapter(); seed_engram(pa->connection());
    FakeLLMAdapter pllm;                        // no response → resp.ok=false
    EpisodicExtractor pex(pa->connection(), pllm);
    const auto llm = pex.extract_llm("passage");
    EXPECT_FALSE(llm.ok);
    EXPECT_TRUE(llm.events.empty());
    const auto phased = pex.persist("engram-1", "default", "cog-self",
                                    "2026-05-23T10:00:00Z", llm);
    EXPECT_TRUE(phased.event_statement_ids.empty());
    EXPECT_EQ(sqlite3_get_autocommit(pa->connection().raw()), 1);   // persist 未开事务
    EXPECT_EQ(row_count(pa->connection(), "statements"), 0);
}

TEST(EpisodicPhases, LlmEmptyEventsOkOpensEmptyTx) {
    // 加固(codex P2):非空合法数组、但每个元素 incomplete(缺 actor/action/theme)
    // → extract_llm 置 ok=true、events 空。persist 镜像单体:仍开 TransactionGuard、
    // 提交空事务、零写。钉死 ok 语义开关(防未来给 persist 加 `if events.empty(): return`
    // 绕过空 tx)。行为无可观测差异,但 ok 是本次拆分唯一新增语义,一个钉测锁死它。
    auto pa = make_adapter(); seed_engram(pa->connection());
    FakeLLMAdapter pllm;
    // 合法 JSON 数组,元素缺 action/theme → 完整性过滤全 skip → events 空但 ok=true。
    pllm.set_default_response(LLMResponse{
        .raw_xml = R"JSON([{"actor":"Sally"}])JSON", .ok = true});
    EpisodicExtractor pex(pa->connection(), pllm);
    const auto llm = pex.extract_llm("passage");
    EXPECT_TRUE(llm.ok);                            // 非空合法数组 → ok=true
    EXPECT_TRUE(llm.events.empty());                // 全 incomplete → 零事件
    const auto phased = pex.persist("engram-1", "default", "cog-self",
                                    "2026-05-23T10:00:00Z", llm);
    EXPECT_TRUE(phased.event_statement_ids.empty());
    EXPECT_EQ(sqlite3_get_autocommit(pa->connection().raw()), 1);   // 空 tx 已 commit(不悬开)
    EXPECT_EQ(row_count(pa->connection(), "statements"), 0);        // 零写
    EXPECT_EQ(row_count(pa->connection(), "episodic_events"), 0);
}

}  // namespace starling::extractor

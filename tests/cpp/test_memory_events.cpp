// test_memory_events.cpp — events 表(迁移 0038)。读侧:next_seq 与 pending_events,
// 直接插行、不经写侧。写侧:remember_event 的四条主路径(新 key、同文本已提交、
// 异文本冲突、补齐不抽取),LLM 用 FakeLLMAdapter,零网络。

#include "starling/memory/memory_events.hpp"

#include "starling/extractor/fake_llm_adapter.hpp"
#include "starling/memory/memory_ops.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/stmt.hpp"

#include <gtest/gtest.h>

#include <algorithm>
#include <cstdint>
#include <functional>
#include <memory>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>

namespace starling::memoryops {

namespace {

std::unique_ptr<persistence::SqliteAdapter> make_adapter() {
    auto a = persistence::SqliteAdapter::open(":memory:");
    persistence::MigrationRunner(a->connection().raw()).migrate_to_latest();
    return a;
}

void insert_event(persistence::Connection& conn, std::string_view tenant, std::string_view key,
                  std::int64_t seq, std::string_view state, std::string_view interlocutor = "bob",
                  std::string_view failure_category = "") {
    persistence::Stmt s(conn.raw(),
        "INSERT INTO events(tenant_id,key,text,interlocutor,text_sha256,seq,state,"
        "failure_category) VALUES(?1,?2,?3,?4,'h',?5,?6,?7)");
    const std::string text = "text-" + std::string(key);
    s.bind(tenant, key, text, interlocutor, seq, state, failure_category);
    s.step_done();
}

constexpr const char* kCannedJson =
    R"JSON([{"holder":"self","holder_perspective":"FIRST_PERSON","subject":"Bob","predicate":"responsible_for","object":"auth","modality":"BELIEVES","polarity":"POS","nesting_depth":0}])JSON";

constexpr const char* kEpoch = "2026-01-01T00:00:00Z";

// remember_event 的基底参数:key 与 text 另传(key 的前缀由 remember_event 自己加,
// payload 不在这里填),时刻由 seq 从 epoch 推出,created_at_iso8601 也不在这里填。
RememberParams event_params() {
    RememberParams p;
    p.tenant_id     = "default";
    p.holder_id     = "cog-self";
    p.interlocutor  = "bob";
    p.adapter_name  = "facade";
    p.source_prefix = "mem-";
    return p;
}

int row_count(persistence::Connection& conn, const char* sql) {
    persistence::Stmt q(conn.raw(), sql);
    EXPECT_TRUE(q.step_row());
    return sqlite3_column_int(q.raw(), 0);
}

std::string state_of(persistence::Connection& conn, std::string_view tenant,
                     std::string_view key) {
    persistence::Stmt q(conn.raw(),
                        "SELECT state FROM events WHERE tenant_id=?1 AND key=?2");
    q.bind(tenant, key);
    if (!q.step_row()) return {};
    // NOLINTNEXTLINE(cppcoreguidelines-pro-type-reinterpret-cast)
    const auto* text = reinterpret_cast<const char*>(sqlite3_column_text(q.raw(), 0));
    return text != nullptr ? std::string(text) : std::string();
}

std::string event_state(persistence::Connection& conn, std::string_view key) {
    return state_of(conn, "default", key);
}

// 抽取总是失败的适配器:用来证明某条路径一次 LLM 都没调(调了就会 extraction_failed)。
class AlwaysFailingLLMAdapter final : public extractor::LLMAdapter {
public:
    extractor::LLMResponse extract(std::string_view, std::string_view) override {
        return {.raw_xml = "", .ok = false, .error = "forced extraction failure"};
    }
};

// 在第 2 段(抽取,事务外)里对同一个 key 动手的适配器:确定性地造出「写入在途中,
// 行被改成终态或被删掉」这个竞态,不用线程、不靠时序。第一次 extract 时回调一次,
// 之后照常返回 response(abandon_event 本身幂等,但只跑一次更贴近真实时序)。
class MutateRowDuringExtractAdapter final : public extractor::LLMAdapter {
public:
    using Hook = std::function<void()>;
    MutateRowDuringExtractAdapter(extractor::LLMResponse response, Hook hook)
        : response_(std::move(response)), hook_(std::move(hook)) {}

    extractor::LLMResponse extract(std::string_view, std::string_view) override {
        if (!fired_) {
            fired_ = true;
            hook_();
        }
        return response_;
    }

private:
    extractor::LLMResponse response_;
    Hook                   hook_;
    bool                   fired_ = false;
};

}  // namespace

TEST(MemoryEvents, NextSeqIsMaxPlusOnePerTenant) {
    auto adapter = make_adapter();
    auto& conn = adapter->connection();
    insert_event(conn, "default", "a", 0, "committed");
    insert_event(conn, "default", "b", 1, "pending");
    insert_event(conn, "other", "c", 0, "committed");

    EXPECT_EQ(next_seq(conn, "default"), 2);
    EXPECT_EQ(next_seq(conn, "other"), 1);
    EXPECT_EQ(next_seq(conn, "none"), 0);
}

TEST(MemoryEvents, NextSeqCountsAbandonedRowsSoNumbersAreNeverReused) {
    auto adapter = make_adapter();
    auto& conn = adapter->connection();
    insert_event(conn, "default", "a", 0, "committed");
    insert_event(conn, "default", "b", 1, "abandoned");

    EXPECT_EQ(next_seq(conn, "default"), 2);
}

TEST(MemoryEvents, NextSeqOnEmptyLibraryIsZero) {
    auto adapter = make_adapter();
    EXPECT_EQ(next_seq(adapter->connection(), "default"), 0);
}

TEST(MemoryEvents, PendingEventsOrderedBySeqOnlyPending) {
    auto adapter = make_adapter();
    auto& conn = adapter->connection();
    insert_event(conn, "default", "late", 5, "pending", "carol", "timeout");
    insert_event(conn, "default", "done", 2, "committed");
    insert_event(conn, "default", "gone", 3, "abandoned");
    insert_event(conn, "default", "early", 1, "pending");
    insert_event(conn, "other", "foreign", 0, "pending");

    const auto rows = pending_events(conn, "default");
    ASSERT_EQ(rows.size(), 2U);
    EXPECT_EQ(rows[0].key, "early");
    EXPECT_EQ(rows[0].text, "text-early");
    EXPECT_EQ(rows[0].interlocutor, "bob");
    EXPECT_EQ(rows[0].seq, 1);
    EXPECT_EQ(rows[0].failure_category, "");
    EXPECT_EQ(rows[1].key, "late");
    EXPECT_EQ(rows[1].interlocutor, "carol");
    EXPECT_EQ(rows[1].seq, 5);
    EXPECT_EQ(rows[1].failure_category, "timeout");
}

TEST(MemoryEvents, PendingEventsEmptyForUnknownTenant) {
    auto adapter = make_adapter();
    auto& conn = adapter->connection();
    insert_event(conn, "default", "a", 0, "pending");

    EXPECT_TRUE(pending_events(conn, "none").empty());
}

// ── 写侧 remember_event ──

TEST(MemoryEvents, RememberEventNewKeyCommitsAndAssignsSeq) {
    auto adapter = make_adapter();
    extractor::FakeLLMAdapter llm;
    llm.set_default_response(extractor::LLMResponse{.raw_xml = kCannedJson, .ok = true});

    const auto res = remember_event(*adapter, llm, event_params(), RememberPrompts{},
                                    "r1/turn#3", "bob:hi", kEpoch);
    EXPECT_EQ(res.outcome, "accepted");
    EXPECT_FALSE(res.extraction_failed);
    EXPECT_FALSE(res.statement_ids.empty());

    auto& conn = adapter->connection();
    EXPECT_EQ(event_state(conn, "r1/turn#3"), "committed");
    EXPECT_EQ(next_seq(conn, "default"), 1);        // 第一条事件的 seq 是 0
    EXPECT_TRUE(pending_events(conn, "default").empty());
    // key 作为前缀写进 Starling 的文本(设计源 4.3),前缀在 Starling 侧加。
    persistence::Stmt q(conn.raw(), "SELECT payload_inline, created_at FROM engrams");
    ASSERT_TRUE(q.step_row());
    const auto* blob = static_cast<const char*>(sqlite3_column_blob(q.raw(), 0));
    const std::string payload(blob, static_cast<std::size_t>(sqlite3_column_bytes(q.raw(), 0)));
    EXPECT_EQ(payload, "[r1/turn#3] bob:hi");
    // NOLINTNEXTLINE(cppcoreguidelines-pro-type-reinterpret-cast)
    EXPECT_EQ(std::string(reinterpret_cast<const char*>(sqlite3_column_text(q.raw(), 1))),
              kEpoch);                              // seq=0 → epoch + 0 秒
}

TEST(MemoryEvents, RememberEventSameKeySameTextReturnsStoredIdsWithoutExtraction) {
    auto adapter = make_adapter();
    extractor::FakeLLMAdapter llm;
    llm.set_default_response(extractor::LLMResponse{.raw_xml = kCannedJson, .ok = true});
    const auto first = remember_event(*adapter, llm, event_params(), RememberPrompts{},
                                      "r1/turn#3", "bob:hi", kEpoch);
    ASSERT_FALSE(first.statement_ids.empty());
    const int before = row_count(adapter->connection(), "SELECT COUNT(*) FROM statements");

    // 行已 committed:一次 LLM 都不该调,所以换上永远失败的适配器也必须照常返回。
    AlwaysFailingLLMAdapter failing;
    const auto again = remember_event(*adapter, failing, event_params(), RememberPrompts{},
                                      "r1/turn#3", "bob:hi", kEpoch);
    EXPECT_EQ(again.outcome, "idempotent");
    EXPECT_FALSE(again.extraction_failed);
    EXPECT_EQ(again.statement_ids, first.statement_ids);
    EXPECT_EQ(again.engram_ref, first.engram_ref);
    EXPECT_EQ(row_count(adapter->connection(), "SELECT COUNT(*) FROM statements"), before);
    EXPECT_EQ(next_seq(adapter->connection(), "default"), 1);   // 不另分配 seq
}

TEST(MemoryEvents, RememberEventSameKeyDifferentTextThrowsEventConflict) {
    auto adapter = make_adapter();
    extractor::FakeLLMAdapter llm;
    llm.set_default_response(extractor::LLMResponse{.raw_xml = kCannedJson, .ok = true});
    ASSERT_EQ(remember_event(*adapter, llm, event_params(), RememberPrompts{},
                             "r1/turn#3", "bob:hi", kEpoch).outcome, "accepted");

    EXPECT_THROW(remember_event(*adapter, llm, event_params(), RememberPrompts{},
                                "r1/turn#3", "bob:bye", kEpoch),
                 EventConflict);
    // abandoned 行同样冲突(调用方已放弃这个 key,不能静默接着写)。
    insert_event(adapter->connection(), "default", "r1/turn#4", 1, "abandoned");
    EXPECT_THROW(remember_event(*adapter, llm, event_params(), RememberPrompts{},
                                "r1/turn#4", "text-r1/turn#4", kEpoch),
                 EventConflict);
}

namespace {

// 事件行里存的 interlocutor。
std::string stored_interlocutor(persistence::Connection& conn, std::string_view key) {
    persistence::Stmt q(conn.raw(),
                        "SELECT interlocutor FROM events WHERE tenant_id='default' AND key=?1");
    q.bind(key);
    if (!q.step_row()) return {};
    // NOLINTNEXTLINE(cppcoreguidelines-pro-type-reinterpret-cast)
    const auto* text = reinterpret_cast<const char*>(sqlite3_column_text(q.raw(), 0));
    return text != nullptr ? std::string(text) : std::string();
}

// 抛出的 EventConflict 的消息;没抛则返回空串(调用方随后断言非空)。
template <typename Fn>
std::string conflict_message(Fn&& fn) {
    try {
        fn();
    } catch (const EventConflict& e) {
        return e.what();
    }
    return {};
}

}  // namespace

TEST(MemoryEvents, RememberEventRetryWithDifferentInterlocutorThrowsAndLeavesRowUntouched) {
    auto adapter = make_adapter();
    // 首次抽取失败 → 行以 interlocutor=bob 留 pending。
    AlwaysFailingLLMAdapter failing;
    ASSERT_TRUE(remember_event(*adapter, failing, event_params(), RememberPrompts{},
                               "r1/turn#3", "bob:hi", kEpoch).extraction_failed);

    // 同 key 同 text,换成 carol 重试:拒绝,不抽取、不改行。
    extractor::FakeLLMAdapter llm;
    llm.set_default_response(extractor::LLMResponse{.raw_xml = kCannedJson, .ok = true});
    auto carol = event_params();
    carol.interlocutor = "carol";
    const auto msg = conflict_message([&] {
        remember_event(*adapter, llm, carol, RememberPrompts{}, "r1/turn#3", "bob:hi", kEpoch);
    });
    ASSERT_FALSE(msg.empty()) << "expected EventConflict";
    EXPECT_NE(msg.find("different interlocutor"), std::string::npos) << msg;
    EXPECT_EQ(msg.find("different text"), std::string::npos) << msg;   // 与文本不一致可区分
    EXPECT_EQ(msg.find("abandoned"), std::string::npos) << msg;        // 与已放弃可区分
    EXPECT_EQ(event_state(adapter->connection(), "r1/turn#3"), "pending");
    EXPECT_EQ(stored_interlocutor(adapter->connection(), "r1/turn#3"), "bob");
    EXPECT_EQ(row_count(adapter->connection(), "SELECT COUNT(*) FROM statements"), 0);
    EXPECT_EQ(next_seq(adapter->connection(), "default"), 1);          // 没另分配 seq

    // 说话对象改回 bob 的重试照常补齐成 committed,语句落在 bob 的 scope_parties 下。
    const auto ok = remember_event(*adapter, llm, event_params(), RememberPrompts{},
                                   "r1/turn#3", "bob:hi", kEpoch);
    EXPECT_FALSE(ok.extraction_failed);
    EXPECT_FALSE(ok.statement_ids.empty());
    EXPECT_EQ(event_state(adapter->connection(), "r1/turn#3"), "committed");
    EXPECT_EQ(row_count(adapter->connection(),
                        "SELECT COUNT(*) FROM statements WHERE scope_parties_json LIKE '%bob%'"),
              static_cast<int>(ok.statement_ids.size()));
    EXPECT_EQ(row_count(adapter->connection(),
                        "SELECT COUNT(*) FROM statements WHERE scope_parties_json LIKE '%carol%'"),
              0);
}

TEST(MemoryEvents, RememberEventConflictMessagesTellTheThreeCausesApart) {
    auto adapter = make_adapter();
    AlwaysFailingLLMAdapter failing;
    ASSERT_TRUE(remember_event(*adapter, failing, event_params(), RememberPrompts{},
                               "k-text", "bob:hi", kEpoch).extraction_failed);
    ASSERT_TRUE(remember_event(*adapter, failing, event_params(), RememberPrompts{},
                               "k-abandon", "bob:hi", kEpoch).extraction_failed);
    abandon_event(*adapter, "default", "k-abandon");
    auto carol = event_params();
    carol.interlocutor = "carol";

    const auto different_text = conflict_message([&] {
        remember_event(*adapter, failing, event_params(), RememberPrompts{},
                       "k-text", "bob:bye", kEpoch);
    });
    const auto different_interlocutor = conflict_message([&] {
        remember_event(*adapter, failing, carol, RememberPrompts{}, "k-text", "bob:hi", kEpoch);
    });
    const auto abandoned = conflict_message([&] {
        remember_event(*adapter, failing, event_params(), RememberPrompts{},
                       "k-abandon", "bob:hi", kEpoch);
    });
    ASSERT_FALSE(different_text.empty());
    ASSERT_FALSE(different_interlocutor.empty());
    ASSERT_FALSE(abandoned.empty());
    EXPECT_NE(different_text.find("different text"), std::string::npos) << different_text;
    EXPECT_NE(different_interlocutor.find("different interlocutor"), std::string::npos)
        << different_interlocutor;
    EXPECT_NE(abandoned.find("already abandoned"), std::string::npos) << abandoned;
    EXPECT_EQ(different_text.find("interlocutor"), std::string::npos) << different_text;
    EXPECT_EQ(abandoned.find("different"), std::string::npos) << abandoned;
}

TEST(MemoryEvents, RememberEventCompletesFromEngramWithoutReextracting) {
    auto adapter = make_adapter();
    // ① 抽取失败 → 行留 pending、无语句。
    AlwaysFailingLLMAdapter failing;
    const auto failed = remember_event(*adapter, failing, event_params(), RememberPrompts{},
                                       "r1/turn#3", "bob:hi", kEpoch);
    EXPECT_TRUE(failed.extraction_failed);
    EXPECT_FALSE(failed.failure_category.empty());
    ASSERT_EQ(pending_events(adapter->connection(), "default").size(), 1U);
    EXPECT_EQ(pending_events(adapter->connection(), "default")[0].failure_category,
              failed.failure_category);

    // ② 用裸 remember_all 把同一 payload 的语句落库(模拟"②成了、③没写成")。
    extractor::FakeLLMAdapter llm;
    llm.set_default_response(extractor::LLMResponse{.raw_xml = kCannedJson, .ok = true});
    auto landed_params = event_params();
    const std::string payload = "[r1/turn#3] bob:hi";
    landed_params.payload.assign(payload.begin(), payload.end());
    landed_params.created_at_iso8601 = kEpoch;
    const auto landed = remember_all(*adapter, llm, landed_params, RememberPrompts{});
    ASSERT_FALSE(landed.statement_ids.empty());
    const int before = row_count(adapter->connection(), "SELECT COUNT(*) FROM statements");

    // ③ 补齐:按 engram 的 content_hash 找到语句,不再抽取一次(故用失败适配器)。
    const auto completed = remember_event(*adapter, failing, event_params(), RememberPrompts{},
                                          "r1/turn#3", "bob:hi", kEpoch);
    EXPECT_FALSE(completed.extraction_failed);
    auto got = completed.statement_ids;
    auto want = landed.statement_ids;
    std::sort(got.begin(), got.end());
    std::sort(want.begin(), want.end());
    EXPECT_EQ(got, want);
    EXPECT_EQ(row_count(adapter->connection(), "SELECT COUNT(*) FROM statements"), before);
    EXPECT_EQ(event_state(adapter->connection(), "r1/turn#3"), "committed");
    EXPECT_TRUE(pending_events(adapter->connection(), "default").empty());
}

// ── abandon_event ──

TEST(MemoryEvents, AbandonEventTurnsPendingIntoAbandonedAndKeepsSeq) {
    auto adapter = make_adapter();
    auto& conn = adapter->connection();
    // pending 行可以带 failure_category(第 3 段未入库或抽取失败时留下的),照样能放弃。
    insert_event(conn, "default", "r1/turn#3", 0, "pending", "bob", "not_stored:rejected");
    insert_event(conn, "default", "r1/turn#4", 1, "pending");

    abandon_event(*adapter, "default", "r1/turn#3");

    EXPECT_EQ(event_state(conn, "r1/turn#3"), "abandoned");
    EXPECT_EQ(event_state(conn, "r1/turn#4"), "pending");     // 只动目标 key
    const auto rows = pending_events(conn, "default");
    ASSERT_EQ(rows.size(), 1U);
    EXPECT_EQ(rows[0].key, "r1/turn#4");
    EXPECT_EQ(next_seq(conn, "default"), 2);                  // 放弃不回收 seq
}

TEST(MemoryEvents, AbandonEventTwiceIsNoop) {
    auto adapter = make_adapter();
    auto& conn = adapter->connection();
    insert_event(conn, "default", "r1/turn#3", 0, "pending");

    abandon_event(*adapter, "default", "r1/turn#3");
    EXPECT_NO_THROW(abandon_event(*adapter, "default", "r1/turn#3"));
    EXPECT_EQ(event_state(conn, "r1/turn#3"), "abandoned");
}

TEST(MemoryEvents, AbandonEventRefusesCommittedWithEventConflict) {
    auto adapter = make_adapter();
    extractor::FakeLLMAdapter llm;
    llm.set_default_response(extractor::LLMResponse{.raw_xml = kCannedJson, .ok = true});
    ASSERT_EQ(remember_event(*adapter, llm, event_params(), RememberPrompts{},
                             "r1/turn#3", "bob:hi", kEpoch).outcome, "accepted");

    EXPECT_THROW(abandon_event(*adapter, "default", "r1/turn#3"), EventConflict);
    EXPECT_EQ(event_state(adapter->connection(), "r1/turn#3"), "committed");
}

TEST(MemoryEvents, AbandonEventUnknownKeyThrowsOutOfRange) {
    auto adapter = make_adapter();
    auto& conn = adapter->connection();
    insert_event(conn, "other", "r1/turn#3", 0, "pending");   // 别的租户的同名 key 不算

    EXPECT_THROW(abandon_event(*adapter, "default", "r1/turn#3"), std::out_of_range);
    EXPECT_EQ(event_state(conn, "r1/turn#3"), "");            // 没有凭空造行
}

TEST(MemoryEvents, AbandonEventOnlyTouchesItsOwnTenant) {
    // abandon 的 UPDATE 带 tenant_id 围栏:两个租户同名 key,放弃一个不许动另一个。
    // 去掉 WHERE 里的 tenant_id=?1 时本用例必须失败(只剩 key 匹配 → 两行一起改)。
    auto adapter = make_adapter();
    auto& conn = adapter->connection();
    insert_event(conn, "default", "r1/turn#3", 0, "pending");
    insert_event(conn, "other", "r1/turn#3", 0, "pending");

    abandon_event(*adapter, "default", "r1/turn#3");

    EXPECT_EQ(state_of(conn, "default", "r1/turn#3"), "abandoned");
    EXPECT_EQ(state_of(conn, "other", "r1/turn#3"), "pending");   // 别的租户没被牵连
    ASSERT_EQ(pending_events(conn, "other").size(), 1U);
    EXPECT_EQ(pending_events(conn, "other")[0].key, "r1/turn#3");
    EXPECT_TRUE(pending_events(conn, "default").empty());
}

TEST(MemoryEvents, AbandonDuringExtractIsNotResurrectedByPhaseThree) {
    // 竞态:第 2 段(抽取,事务外)期间 abandon_event 提交,随后第 3 段的提交支不许把
    // 'abandoned' 覆写回 'committed'(设计源 §8:放弃是终局)。零行 → EventConflict。
    auto adapter = make_adapter();
    MutateRowDuringExtractAdapter llm(
        extractor::LLMResponse{.raw_xml = kCannedJson, .ok = true},
        [&adapter] { abandon_event(*adapter, "default", "r1/turn#3"); });

    EXPECT_THROW(remember_event(*adapter, llm, event_params(), RememberPrompts{},
                                "r1/turn#3", "bob:hi", kEpoch),
                 EventConflict);

    auto& conn = adapter->connection();
    EXPECT_EQ(event_state(conn, "r1/turn#3"), "abandoned");   // 没复活
    EXPECT_TRUE(pending_events(conn, "default").empty());
    // 之后这个 key 照样是终局:再写一律冲突。
    extractor::FakeLLMAdapter plain;
    plain.set_default_response(extractor::LLMResponse{.raw_xml = kCannedJson, .ok = true});
    EXPECT_THROW(remember_event(*adapter, plain, event_params(), RememberPrompts{},
                                "r1/turn#3", "bob:hi", kEpoch),
                 EventConflict);
}

TEST(MemoryEvents, AbandonDuringExtractAlsoGuardsTheFailureBranch) {
    // 同一竞态落在第 3 段的未入库/抽取失败支上:那条 UPDATE 也带 state='pending' 围栏,
    // 零行同样抛。否则 failure_category 会写进一行已经放弃的收据里。
    auto adapter = make_adapter();
    MutateRowDuringExtractAdapter llm(
        extractor::LLMResponse{.raw_xml = "", .ok = false, .error = "forced failure"},
        [&adapter] { abandon_event(*adapter, "default", "r1/turn#3"); });

    EXPECT_THROW(remember_event(*adapter, llm, event_params(), RememberPrompts{},
                                "r1/turn#3", "bob:hi", kEpoch),
                 EventConflict);

    auto& conn = adapter->connection();
    EXPECT_EQ(event_state(conn, "r1/turn#3"), "abandoned");
    EXPECT_EQ(row_count(conn, "SELECT COUNT(*) FROM events WHERE failure_category<>''"), 0);
}

TEST(MemoryEvents, RowDeletedDuringExtractThrowsInsteadOfSilentlyDoingNothing) {
    // 任务 6 搁置的那条发现:第 2 段期间 clear_tenant 把行删了,第 3 段的 UPDATE 匹配
    // 零行。原先静默收尾、调用方以为收据写成了;现在抛 EventConflict。
    auto adapter = make_adapter();
    MutateRowDuringExtractAdapter llm(
        extractor::LLMResponse{.raw_xml = kCannedJson, .ok = true},
        [&adapter] {
            persistence::Stmt del(adapter->connection().raw(),
                                  "DELETE FROM events WHERE tenant_id='default'");
            del.step_done();
        });

    EXPECT_THROW(remember_event(*adapter, llm, event_params(), RememberPrompts{},
                                "r1/turn#3", "bob:hi", kEpoch),
                 EventConflict);
    EXPECT_EQ(row_count(adapter->connection(), "SELECT COUNT(*) FROM events"), 0);
}

TEST(MemoryEvents, AbandonedKeyRejectsLaterRememberEvent) {
    auto adapter = make_adapter();
    extractor::FakeLLMAdapter llm;
    llm.set_default_response(extractor::LLMResponse{.raw_xml = kCannedJson, .ok = true});
    AlwaysFailingLLMAdapter failing;
    // 抽取失败 → 行留 pending(带 failure_category),随后放弃。
    ASSERT_TRUE(remember_event(*adapter, failing, event_params(), RememberPrompts{},
                               "r1/turn#3", "bob:hi", kEpoch).extraction_failed);
    abandon_event(*adapter, "default", "r1/turn#3");

    EXPECT_THROW(remember_event(*adapter, llm, event_params(), RememberPrompts{},
                                "r1/turn#3", "bob:hi", kEpoch),
                 EventConflict);
    EXPECT_EQ(row_count(adapter->connection(), "SELECT COUNT(*) FROM statements"), 0);
}

}  // namespace starling::memoryops

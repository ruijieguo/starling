// sub-project A phase 5 Task 5.1:EpisodicExtractor —— 把叙事段落经第二条
// (episodic)抽取管线转成 OCCURRED 事件语句 + episodic_events 行。
// FakeLLMAdapter 喂 Sally/Anne 叙事(含一个 leave 事件)的固定 JSON 数组,
// 零网络。断言:三条 OCCURRED statements(put/leave/move)+ 三条 episodic_events
// (seq 1/2/3,location basket/NULL/box,participants ["Sally"]/["Sally"]/["Anne"])。
#include "starling/extractor/episodic_extractor.hpp"
#include "starling/extractor/fake_llm_adapter.hpp"
#include "starling/store/episodic_event_store.hpp"

#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

namespace starling::extractor {
namespace {

// Sally/Anne 经典错误信念叙事的固定 episodic JSON。叙事顺序:
//   1) Sally put ball -> basket
//   2) Sally leave room          (presence-change,theme=场所,location=null)
//   3) Anne  move ball  -> box
constexpr const char* kEpisodicJson = R"JSON([
  {"actor":"Sally","action":"put","theme":"ball","location":"basket","participants":["Sally"],"time":null},
  {"actor":"Sally","action":"leave","theme":"room","location":null,"participants":["Sally"],"time":null},
  {"actor":"Anne","action":"move","theme":"ball","location":"box","participants":["Anne"],"time":null}
])JSON";

std::unique_ptr<persistence::SqliteAdapter> make_adapter() {
    auto a = persistence::SqliteAdapter::open(":memory:");
    persistence::MigrationRunner(a->connection().raw()).migrate_to_latest();
    return a;
}

void seed_engram(persistence::Connection& conn) {
    sqlite3* db = conn.raw();
    char* err = nullptr;
    ASSERT_EQ(sqlite3_exec(db,
        "INSERT INTO engrams("
        "  id,tenant_id,content_hash,source_kind,ingest_policy,ingest_mode,"
        "  privacy_class,retention_mode,refcount,payload_inline,created_at"
        ") VALUES("
        "  'engram-1','default','hash-1','user_input','store','whole_record',"
        "  'internal','audit_retain',0,X'','2026-06-16T10:00:00Z')",
        nullptr, nullptr, &err), SQLITE_OK) << (err ? err : "");
}

int row_count(persistence::Connection& conn, const std::string& table,
              const std::string& where = "1=1") {
    sqlite3* db = conn.raw();
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db,
            ("SELECT COUNT(*) FROM " + table + " WHERE " + where).c_str(),
            -1, &raw, nullptr) != SQLITE_OK) {
        throw std::runtime_error(std::string("row_count prepare failed: ") + sqlite3_errmsg(db));
    }
    persistence::StmtHandle h(raw);
    sqlite3_step(h.get());
    return sqlite3_column_int(h.get(), 0);
}

// statements.id for the single OCCURRED row matching (subject_id, predicate,
// object_value). Empty if absent.
std::string occurred_stmt_id(persistence::Connection& conn,
                             const std::string& subject,
                             const std::string& predicate,
                             const std::string& object_value) {
    sqlite3* db = conn.raw();
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db,
            "SELECT id FROM statements WHERE modality='occurred' "
            "AND subject_id=? AND predicate=? AND object_value=? LIMIT 1",
            -1, &raw, nullptr) != SQLITE_OK) {
        throw std::runtime_error(std::string("occurred_stmt_id prepare: ") + sqlite3_errmsg(db));
    }
    persistence::StmtHandle h(raw);
    sqlite3_bind_text(h.get(), 1, subject.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(h.get(), 2, predicate.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(h.get(), 3, object_value.c_str(), -1, SQLITE_TRANSIENT);
    if (sqlite3_step(h.get()) != SQLITE_ROW) return "";
    return reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 0));
}

}  // namespace

// Task 5.1:固定 JSON → 三条 OCCURRED statements + 三条 episodic_events(seq/
// location/participants 对齐叙事顺序)。
TEST(EpisodicExtractor, NarrativeWritesOccurredStatementsAndEpisodicRows) {
    auto a = make_adapter();
    auto& conn = a->connection();
    seed_engram(conn);

    FakeLLMAdapter llm;
    llm.set_default_response(LLMResponse{.raw_xml = kEpisodicJson, .ok = true});

    EpisodicExtractor ex(conn, llm, /*prompt=*/"events from: {passage}");
    const std::string passage =
        "Sally puts her ball in the basket and leaves the room. "
        "Anne moves the ball to the box.";
    const auto result = ex.extract(passage, /*engram_ref=*/"engram-1",
                                   /*tenant=*/"default", /*agent_self=*/"cog-self",
                                   /*now=*/"2026-06-16T10:00:00Z");

    // 3 events written.
    EXPECT_EQ(result.event_statement_ids.size(), 3u);

    // OCCURRED statements: holder=self, subject=actor, predicate=action,
    // object=theme.
    EXPECT_EQ(row_count(conn, "statements", "modality='occurred'"), 3);
    EXPECT_EQ(row_count(conn, "statements",
        "modality='occurred' AND holder_id='cog-self' AND holder_perspective='first_person'"), 3);

    const std::string put_id  = occurred_stmt_id(conn, "Sally", "put",  "ball");
    const std::string leave_id = occurred_stmt_id(conn, "Sally", "leave", "room");
    const std::string move_id = occurred_stmt_id(conn, "Anne",  "move", "ball");
    ASSERT_FALSE(put_id.empty());
    ASSERT_FALSE(leave_id.empty());
    ASSERT_FALSE(move_id.empty());

    // OCCURRED rows keep open-domain action verbs verbatim and are not
    // downgraded to review_requested (validator §3.3 OCCURRED carve-out).
    EXPECT_EQ(row_count(conn, "statements",
        "modality='occurred' AND review_status='approved'"), 3);
    // subject_kind=cognizer, object_kind=entity, polarity=pos, provenance=user_input.
    // (enum to_string stores lowercase: "pos" / "user_input".)
    EXPECT_EQ(row_count(conn, "statements",
        "modality='occurred' AND subject_kind='cognizer' AND object_kind='entity' "
        "AND polarity='pos' AND provenance='user_input'"), 3);

    // episodic_events: one row per statement, seq 1/2/3 in narrative order.
    EXPECT_EQ(row_count(conn, "episodic_events"), 3);
    store::EpisodicEventStore store(conn);

    auto put_row = store.get(put_id, "default");
    ASSERT_TRUE(put_row.has_value());
    EXPECT_EQ(put_row->seq, 1);
    EXPECT_EQ(put_row->location, "basket");
    EXPECT_EQ(put_row->participants_json, R"(["Sally"])");
    EXPECT_EQ(put_row->action_raw, "put");
    EXPECT_EQ(put_row->event_time, "");  // time:null -> NULL -> ""

    auto leave_row = store.get(leave_id, "default");
    ASSERT_TRUE(leave_row.has_value());
    EXPECT_EQ(leave_row->seq, 2);
    EXPECT_EQ(leave_row->location, "");  // location:null -> NULL -> ""
    EXPECT_EQ(leave_row->participants_json, R"(["Sally"])");
    EXPECT_EQ(leave_row->action_raw, "leave");

    auto move_row = store.get(move_id, "default");
    ASSERT_TRUE(move_row.has_value());
    EXPECT_EQ(move_row->seq, 3);
    EXPECT_EQ(move_row->location, "box");
    EXPECT_EQ(move_row->participants_json, R"(["Anne"])");
    EXPECT_EQ(move_row->action_raw, "move");
}

// null actor/action/theme → 事件被跳过,不抛 type_error.302;其余有效事件正常写入。
// 镜像真实模型(deepseek-v4-pro)对歧义事件发出 "actor": null / "theme": null 的场景。
TEST(EpisodicExtractor, NullActorOrThemeSkipsEventNoThrow) {
    // One well-formed event + one with actor:null + one with theme:null.
    // Only the well-formed event should be written.
    constexpr const char* kJson = R"JSON([
      {"actor":"Sally","action":"put","theme":"ball","location":"basket","participants":["Sally"],"time":null},
      {"actor":null,"action":"leave","theme":"room","location":null,"participants":[],"time":null},
      {"actor":"Anne","action":"move","theme":null,"location":"box","participants":["Anne"],"time":null}
    ])JSON";

    auto a = make_adapter();
    auto& conn = a->connection();
    seed_engram(conn);

    FakeLLMAdapter llm;
    llm.set_default_response(LLMResponse{.raw_xml = kJson, .ok = true});

    EpisodicExtractor ex(conn, llm, /*prompt=*/"events from: {passage}");
    // Must not throw.
    EpisodicExtractionResult result;
    ASSERT_NO_THROW(result = ex.extract(
        "Sally puts a ball in the basket. An ambiguous leave. Anne moves the ball.",
        /*engram_ref=*/"engram-1", /*tenant=*/"default",
        /*agent_self=*/"cog-self", /*now=*/"2026-06-16T10:00:00Z"));

    // Only the 1 well-formed event (Sally put ball) is written.
    EXPECT_EQ(result.event_statement_ids.size(), 1u);
    EXPECT_EQ(row_count(conn, "statements", "modality='occurred'"), 1);
    EXPECT_EQ(row_count(conn, "episodic_events"), 1);

    const std::string put_id = occurred_stmt_id(conn, "Sally", "put", "ball");
    ASSERT_FALSE(put_id.empty());
}

// 空数组 / 解析失败 → 零写入,不抛(best-effort 第二条管线对叙事无事件友好)。
TEST(EpisodicExtractor, EmptyArrayWritesNothing) {
    auto a = make_adapter();
    auto& conn = a->connection();
    seed_engram(conn);

    FakeLLMAdapter llm;
    llm.set_default_response(LLMResponse{.raw_xml = "[]", .ok = true});

    EpisodicExtractor ex(conn, llm, /*prompt=*/"{passage}");
    const auto result = ex.extract("nothing physical happens here", "engram-1",
                                   "default", "cog-self", "2026-06-16T10:00:00Z");
    EXPECT_EQ(result.event_statement_ids.size(), 0u);
    EXPECT_EQ(row_count(conn, "statements", "modality='occurred'"), 0);
    EXPECT_EQ(row_count(conn, "episodic_events"), 0);
}

}  // namespace starling::extractor

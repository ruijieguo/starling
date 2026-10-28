// test_memory_digest.cpp — digest 与 content_ids 的规范化。行直接插进三张表,不经
// 写侧:摘要要钉的是「同内容不同 UUID 得同一个摘要、排除清单的列不改摘要、指不到的
// 引用收敛成 missing」,这些用裸 INSERT 表达最直接,零 LLM、零网络。

#include "starling/memory/memory_digest.hpp"

#include "starling/crypto/sha256.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/stmt.hpp"

#include <gtest/gtest.h>

#include <map>
#include <memory>
#include <string>
#include <string_view>
#include <vector>

namespace starling::memoryops {

namespace {

constexpr std::string_view kTenant = "default";

std::unique_ptr<persistence::SqliteAdapter> make_adapter() {
    auto a = persistence::SqliteAdapter::open(":memory:");
    persistence::MigrationRunner(a->connection().raw()).migrate_to_latest();
    return a;
}

// 一个 engram:content_hash 决定它被引用成什么,id 两个库之间不同。
void insert_engram(persistence::Connection& conn, std::string_view id,
                   std::string_view content_hash) {
    persistence::Stmt s(conn.raw(),
        "INSERT INTO engrams(id,tenant_id,content_hash,source_kind,ingest_policy,"
        "ingest_mode,privacy_class,retention_mode,created_at) "
        "VALUES(?1,?2,?3,'user_input','store','whole_record','internal','audit_retain',"
        "'2026-01-01T00:00:00Z')");
    s.bind(id, kTenant, content_hash);
    s.step_done();
}

struct StatementSpec {
    std::string id;
    std::string object_value   = "auth";
    std::string engram_id      = "";    // evidence_json / source_spans_json 指向它
    std::string supersedes_id  = "";    // 空 → NULL
    std::string history_ts     = "";    // 非空 → confidence_history_json 带一项墙钟
    std::string review_status  = "approved";
};

void insert_statement(persistence::Connection& conn, const StatementSpec& spec) {
    const std::string evidence =
        spec.engram_id.empty()
            ? "[]"
            : R"([{"engram_ref":")" + spec.engram_id + R"(","status":"active"}])";
    const std::string spans =
        spec.engram_id.empty()
            ? "[]"
            : R"([{"engram_ref":")" + spec.engram_id + R"(","chunk_index":0}])";
    const std::string history =
        spec.history_ts.empty()
            ? "[]"
            : R"([{"old_value":0.7,"ts":")" + spec.history_ts + R"(","path":"mild"}])";
    persistence::Stmt s(conn.raw(),
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,subject_kind,"
        "subject_id,predicate,object_kind,object_value,canonical_object_hash,modality,"
        "polarity,confidence,observed_at,salience,affect_json,activation,last_accessed,"
        "provenance,confidence_history_json,evidence_json,source_spans_json,"
        "supersedes_id,review_status,created_at,updated_at) "
        "VALUES(?1,?2,'alice','first_person','entity','cog-bob','responsible_for','str',"
        "?3,'h-obj','believes','pos',0.7,'2026-01-01T00:00:00Z',0.5,'{}',0.0,"
        "'2026-10-28T00:00:00Z','user_input',?4,?5,?6,?7,?8,'2026-10-28T00:00:00Z',"
        "'2026-10-28T00:00:00Z')");
    s.bind(spec.id, kTenant, spec.object_value, history, evidence, spans);
    if (spec.supersedes_id.empty()) {
        sqlite3_bind_null(s.raw(), 7);
    } else {
        persistence::detail::bind_sv(s.raw(), 7, spec.supersedes_id);
    }
    persistence::detail::bind_sv(s.raw(), 8, spec.review_status);
    s.step_done();
}

void insert_vector(persistence::Connection& conn, std::string_view stmt_id) {
    persistence::Stmt s(conn.raw(),
        "INSERT INTO statement_vectors(stmt_id,tenant_id,index_vector,raw_embedding,dim,"
        "model,status,retry_count,last_attempt_at,embedded_at) "
        "VALUES(?1,?2,x'0102',x'0102',8,'stub','embedded',0,NULL,"
        "'2026-10-28T00:00:00Z')");
    s.bind(stmt_id, kTenant);
    s.step_done();
}

void insert_event(persistence::Connection& conn, std::string_view key, std::int64_t seq,
                  std::string_view state, std::string_view engram_id,
                  const std::string& statement_ids_json, std::string_view text = "bob:hi") {
    persistence::Stmt s(conn.raw(),
        "INSERT INTO events(tenant_id,key,text,interlocutor,text_sha256,engram_ref,"
        "statement_ids_json,seq,state,failure_category) "
        "VALUES(?1,?2,?3,'bob','h',?4,?5,?6,?7,'')");
    s.bind(kTenant, key, text, engram_id, statement_ids_json, seq, state);
    s.step_done();
}

void exec(persistence::Connection& conn, const char* sql) {
    persistence::Stmt s(conn.raw(), sql);
    s.step_done();
}

}  // namespace

// 空库的摘要是三张空表的固定串。Python 侧的 EMPTY 常量就是这一个值,门面与核心层
// 对不上时这条先红。
TEST(MemoryDigest, EmptyLibraryIsTheFixedThreeTableDigest) {
    auto a = make_adapter();
    const std::string expected =
        crypto::sha256_hex(R"({"events":[],"statement_vectors":[],"statements":[]})");
    EXPECT_EQ(digest(a->connection(), kTenant), expected);
    // 另一个空库给同一个值(摘要里没有任何与这次打开有关的东西)。
    auto b = make_adapter();
    EXPECT_EQ(digest(b->connection(), kTenant), expected);
}

// 排除清单的列:自增计数、墙钟、批次 id 改了,摘要不动。
TEST(MemoryDigest, ExcludedColumnsDoNotChangeTheDigest) {
    auto a = make_adapter();
    auto& conn = a->connection();
    insert_engram(conn, "eng-1", "hash-1");
    insert_statement(conn, {.id = "s-1", .engram_id = "eng-1"});
    insert_vector(conn, "s-1");
    insert_event(conn, "e#0", 0, "committed", "eng-1", R"(["s-1"])");
    const std::string before = digest(conn, kTenant);

    exec(conn, "UPDATE statements SET access_count=7, last_accessed='2030-01-01T00:00:00Z',"
               " created_at='2030-01-01T00:00:00Z', updated_at='2030-01-01T00:00:00Z',"
               " replay_count=3, last_replayed='2030-01-01T00:00:00Z',"
               " last_replay_batch_id='batch-x', inferred_at='2030-01-01T00:00:00Z'");
    exec(conn, "UPDATE statement_vectors SET retry_count=9,"
               " last_attempt_at='2030-01-01T00:00:00Z', embedded_at='2030-01-01T00:00:00Z'");
    EXPECT_EQ(digest(conn, kTenant), before);

    // 对照:不在清单里的列一改,摘要必须变(否则上面那条是因为什么都没算才相等)。
    exec(conn, "UPDATE statements SET activation=0.9");
    EXPECT_NE(digest(conn, kTenant), before);
}

// 同内容、不同 UUID(行 id、engram id、引用它们的 JSON 与事件列全都不同)→ 同一个摘要。
TEST(MemoryDigest, SameContentWithDifferentUuidsGivesTheSameDigest) {
    auto a = make_adapter();
    auto b = make_adapter();
    insert_engram(a->connection(), "eng-a", "hash-1");
    insert_statement(a->connection(), {.id = "s-a", .engram_id = "eng-a"});
    insert_vector(a->connection(), "s-a");
    insert_event(a->connection(), "e#0", 0, "committed", "eng-a", R"(["s-a"])");

    insert_engram(b->connection(), "eng-b", "hash-1");
    insert_statement(b->connection(), {.id = "s-b", .engram_id = "eng-b"});
    insert_vector(b->connection(), "s-b");
    insert_event(b->connection(), "e#0", 0, "committed", "eng-b", R"(["s-b"])");

    EXPECT_EQ(digest(a->connection(), kTenant), digest(b->connection(), kTenant));
    // 内容真变了就必须不同。
    exec(b->connection(), "UPDATE statements SET object_value='billing'");
    EXPECT_NE(digest(a->connection(), kTenant), digest(b->connection(), kTenant));
}

// 指不到的引用:两个库各指向一个不存在的不同 UUID,都收敛成 missing。
// supersedes_id、derived_from_json、events.engram_ref、events.statement_ids_json
// 四处引用各测一遍。
TEST(MemoryDigest, DanglingReferencesCollapseToMissing) {
    auto a = make_adapter();
    auto b = make_adapter();
    insert_statement(a->connection(), {.id = "s-a", .supersedes_id = "gone-a"});
    insert_statement(b->connection(), {.id = "s-b", .supersedes_id = "gone-b"});
    exec(a->connection(), R"(UPDATE statements SET derived_from_json='["gone-a2"]')");
    exec(b->connection(), R"(UPDATE statements SET derived_from_json='["gone-b2"]')");
    insert_event(a->connection(), "e#0", 0, "committed", "gone-a3", R"(["gone-a4"])");
    insert_event(b->connection(), "e#0", 0, "committed", "gone-b3", R"(["gone-b4"])");
    EXPECT_EQ(digest(a->connection(), kTenant), digest(b->connection(), kTenant));

    // missing 不是「什么都不算」:真指到一行时摘要与指不到时不同。
    insert_statement(a->connection(), {.id = "s-a0", .object_value = "old"});
    insert_statement(b->connection(), {.id = "s-b0", .object_value = "old"});
    exec(a->connection(), "UPDATE statements SET supersedes_id='s-a0' WHERE id='s-a'");
    const std::string a_pointing = digest(a->connection(), kTenant);
    EXPECT_NE(a_pointing, digest(b->connection(), kTenant));
    exec(b->connection(), "UPDATE statements SET supersedes_id='s-b0' WHERE id='s-b'");
    EXPECT_EQ(a_pointing, digest(b->connection(), kTenant));
}

// confidence_history_json 每项的墙钟 ts 要去掉(设计源的排除清单没写这一条)。
TEST(MemoryDigest, ConfidenceHistoryWallClockIsDropped) {
    auto a = make_adapter();
    auto b = make_adapter();
    insert_statement(a->connection(), {.id = "s-a", .history_ts = "2026-10-28T23:14:07Z"});
    insert_statement(b->connection(), {.id = "s-b", .history_ts = "2026-10-29T06:40:11Z"});
    EXPECT_EQ(digest(a->connection(), kTenant), digest(b->connection(), kTenant));

    // 同一项里别的字段仍然算:ts 之外没被连带去掉。
    exec(b->connection(),
         R"(UPDATE statements SET confidence_history_json='[{"old_value":0.2,"ts":"x","path":"mild"}]')");
    EXPECT_NE(digest(a->connection(), kTenant), digest(b->connection(), kTenant));
}

// state='abandoned' 的事件行只算 key 与 state:原文、seq 与失败原因不进摘要。
TEST(MemoryDigest, AbandonedEventCountsOnlyKeyAndState) {
    auto a = make_adapter();
    auto b = make_adapter();
    insert_event(a->connection(), "e#0", 0, "abandoned", "", "[]", "bob:one");
    insert_event(b->connection(), "e#0", 3, "abandoned", "", "[]", "bob:two");
    exec(a->connection(), "UPDATE events SET failure_category='timeout'");
    const std::string empty =
        crypto::sha256_hex(R"({"events":[],"statement_vectors":[],"statements":[]})");
    EXPECT_EQ(digest(a->connection(), kTenant), digest(b->connection(), kTenant));
    EXPECT_NE(digest(a->connection(), kTenant), empty);
    // key 变了就是另一件事:摘要必须变。
    exec(b->connection(), "UPDATE events SET key='e#9'");
    EXPECT_NE(digest(a->connection(), kTenant), digest(b->connection(), kTenant));
}

// 召回看不见的行照样进摘要:review_status 一改,摘要就变。
TEST(MemoryDigest, RowsInvisibleToRecallStillCount) {
    auto a = make_adapter();
    auto& conn = a->connection();
    insert_statement(conn, {.id = "s-1"});
    const std::string before = digest(conn, kTenant);
    exec(conn, "UPDATE statements SET review_status='pending_review'");
    EXPECT_NE(digest(conn, kTenant), before);
    exec(conn, "UPDATE statements SET consolidation_state='archived'");
    EXPECT_NE(digest(conn, kTenant), before);
}

// 另一个租户的行不进本租户的摘要。
TEST(MemoryDigest, OtherTenantRowsAreNotCounted) {
    auto a = make_adapter();
    auto& conn = a->connection();
    insert_statement(conn, {.id = "s-1"});
    const std::string before = digest(conn, kTenant);
    exec(conn, "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
               "subject_kind,subject_id,predicate,object_kind,object_value,"
               "canonical_object_hash,modality,polarity,confidence,observed_at,salience,"
               "affect_json,activation,last_accessed,provenance,created_at,updated_at) "
               "VALUES('s-2','other','alice','first_person','entity','cog-bob','p','str',"
               "'v','h','believes','pos',0.7,'2026-01-01T00:00:00Z',0.5,'{}',0.0,"
               "'2026-10-28T00:00:00Z','user_input','2026-10-28T00:00:00Z',"
               "'2026-10-28T00:00:00Z')");
    EXPECT_EQ(digest(conn, kTenant), before);
}

// content_ids:本租户的 id → 64 位十六进制;不认识的 id → missing;两个库里同内容
// 的行给同一个内容 id。
TEST(MemoryDigest, ContentIdsMapsKnownIdsAndMarksUnknownOnesMissing) {
    auto a = make_adapter();
    auto b = make_adapter();
    insert_engram(a->connection(), "eng-a", "hash-1");
    insert_engram(b->connection(), "eng-b", "hash-1");
    insert_statement(a->connection(), {.id = "s-a", .engram_id = "eng-a"});
    insert_statement(b->connection(), {.id = "s-b", .engram_id = "eng-b"});

    const auto got = content_ids(a->connection(), kTenant, {"s-a", "no-such-id", "s-a"});
    ASSERT_EQ(got.size(), 2U);                     // 重复 id 只出现一次
    EXPECT_EQ(got.at("no-such-id"), "missing");
    EXPECT_EQ(got.at("s-a").size(), 64U);
    EXPECT_EQ(got.at("s-a").find_first_not_of("0123456789abcdef"), std::string::npos);

    const auto other = content_ids(b->connection(), kTenant, {"s-b"});
    EXPECT_EQ(got.at("s-a"), other.at("s-b"));     // UUID 不同,内容 id 相同

    // 内容一变,内容 id 就变;引用列不进内容 id,所以改它不影响。
    exec(b->connection(), "UPDATE statements SET object_value='billing'");
    EXPECT_NE(got.at("s-a"), content_ids(b->connection(), kTenant, {"s-b"}).at("s-b"));
    exec(b->connection(), "UPDATE statements SET object_value='auth', supersedes_id='x',"
                          R"( derived_from_json='["y"]')");
    EXPECT_EQ(got.at("s-a"), content_ids(b->connection(), kTenant, {"s-b"}).at("s-b"));

    EXPECT_TRUE(content_ids(a->connection(), kTenant, {}).empty());
}

// 两行完全同内容(只有 id 不同)时的序:摘要不因插入顺序而变。
TEST(MemoryDigest, DuplicateContentRowsSortDeterministically) {
    auto a = make_adapter();
    auto b = make_adapter();
    insert_statement(a->connection(), {.id = "s-1"});
    insert_statement(a->connection(), {.id = "s-2"});
    insert_statement(b->connection(), {.id = "z-2"});   // 反序插入
    insert_statement(b->connection(), {.id = "z-1"});
    EXPECT_EQ(digest(a->connection(), kTenant), digest(b->connection(), kTenant));
}

}  // namespace starling::memoryops

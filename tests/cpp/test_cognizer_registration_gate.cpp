// PR1 Task 3: cognizer 注册守卫接线 —— 抽取时只有 subject_kind="cognizer" 才注册
// 认知体,kind 由 LLM 的 cognizer_kind 决定;subject_kind="entity"(技术实体)绝不注册;
// cognizer_kind="self" 消解到本次 run 的 holder_id,不新建「me」认知体。
//
// 这是既有测试体系从来没有的负例:旧代码把每条 statement 的 subject 无条件注册成
// human 认知体(json_parser.cpp:103 硬编码 + name_resolver.cpp:49 硬编码 Human),
// 导致 H800 memory / Postgres 等技术实体污染 cognizers 表。
#include "starling/cognizer/cognizer.hpp"
#include "starling/cognizer/cognizer_hub.hpp"
#include "starling/extractor/extractor.hpp"
#include "starling/extractor/fake_llm_adapter.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <gtest/gtest.h>

#include <memory>
#include <string>

namespace starling::extractor {
namespace {

std::unique_ptr<persistence::SqliteAdapter> make_adapter() {
    auto a = persistence::SqliteAdapter::open(":memory:");
    persistence::MigrationRunner(a->connection().raw()).migrate_to_latest();
    return a;
}

void seed_engram(persistence::Connection& conn) {
    sqlite3_exec(conn.raw(),
        "INSERT INTO engrams("
        "  id,tenant_id,content_hash,source_kind,ingest_policy,ingest_mode,"
        "  privacy_class,retention_mode,refcount,payload_inline,created_at"
        ") VALUES("
        "  'engram-1','default','hash-1','user_input','store','whole_record',"
        "  'internal','audit_retain',0,X'','2026-05-23T10:00:00Z')",
        nullptr, nullptr, nullptr);
}

// One-statement extractor JSON with a caller-supplied subject + subject_kind
// (+ optional cognizer_kind). holder is always "self" (the narrator).
std::string one_stmt(const std::string& subject, const std::string& subject_kind,
                     const std::string& cognizer_kind = "") {
    std::string ck = cognizer_kind.empty()
        ? std::string()
        : (R"(,"cognizer_kind":")" + cognizer_kind + R"(")");
    return R"([{"holder":"self","holder_perspective":"FIRST_PERSON","subject":")"
        + subject + R"(","predicate":"has_value","object":"x","modality":"BELIEVES",)"
        + R"("polarity":"POS","nesting_depth":0,"subject_kind":")" + subject_kind
        + R"(")" + ck + R"(}])";
}

// COUNT(*) of cognizers rows for a given canonical_name in the default tenant.
int cognizer_count(persistence::Connection& conn, const std::string& name) {
    sqlite3_stmt* raw = nullptr;
    sqlite3_prepare_v2(conn.raw(),
        "SELECT COUNT(*) FROM cognizers WHERE tenant_id='default' AND canonical_name=?1",
        -1, &raw, nullptr);
    persistence::StmtHandle h(raw);
    sqlite3_bind_text(h.get(), 1, name.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_step(h.get());
    return sqlite3_column_int(h.get(), 0);
}

// kind string of the single cognizer with this canonical_name ("" if absent).
std::string cognizer_kind_of(persistence::Connection& conn, const std::string& name) {
    sqlite3_stmt* raw = nullptr;
    sqlite3_prepare_v2(conn.raw(),
        "SELECT kind FROM cognizers WHERE tenant_id='default' AND canonical_name=?1",
        -1, &raw, nullptr);
    persistence::StmtHandle h(raw);
    sqlite3_bind_text(h.get(), 1, name.c_str(), -1, SQLITE_TRANSIENT);
    if (sqlite3_step(h.get()) != SQLITE_ROW) return "";
    const unsigned char* t = sqlite3_column_text(h.get(), 0);
    return t ? reinterpret_cast<const char*>(t) : "";
}

}  // namespace

// 技术实体 subject(subject_kind="entity")绝不注册进 cognizers 表 —— 这是修复核心。
TEST(RegistrationGate, EntitySubjectNotRegistered) {
    auto a = make_adapter();
    auto& conn = a->connection();
    seed_engram(conn);
    FakeLLMAdapter llm;
    llm.set_default_response(LLMResponse{
        .raw_xml = one_stmt("H800 memory", "entity"), .ok = true});
    Extractor ex(conn, llm, *a);
    ex.run("engram-1", {1, 2, 3}, "system_self", "default", {});
    // H800 memory 是技术实体 → 不建认知体行。
    EXPECT_EQ(cognizer_count(conn, "H800 memory"), 0);
}

// cognizer subject 用 LLM 的 cognizer_kind 注册(不再焊死 human)。
TEST(RegistrationGate, CognizerSubjectUsesLlmKind) {
    auto a = make_adapter();
    auto& conn = a->connection();
    seed_engram(conn);
    FakeLLMAdapter llm;
    llm.set_default_response(LLMResponse{
        .raw_xml = one_stmt("Claude", "cognizer", "agent"), .ok = true});
    Extractor ex(conn, llm, *a);
    ex.run("engram-1", {1, 2, 3}, "system_self", "default", {});
    EXPECT_EQ(cognizer_count(conn, "Claude"), 1);
    EXPECT_EQ(cognizer_kind_of(conn, "Claude"), "agent");  // LLM kind,非 human
}

// cognizer_kind 缺失 → 缺省 human(历史行为)。
TEST(RegistrationGate, CognizerKindMissingDefaultsHuman) {
    auto a = make_adapter();
    auto& conn = a->connection();
    seed_engram(conn);
    FakeLLMAdapter llm;
    llm.set_default_response(LLMResponse{
        .raw_xml = one_stmt("Alice", "cognizer"), .ok = true});
    Extractor ex(conn, llm, *a);
    ex.run("engram-1", {1, 2, 3}, "system_self", "default", {});
    EXPECT_EQ(cognizer_kind_of(conn, "Alice"), "human");
}

// cognizer_kind="self" 消解到本次 run 的 holder_id —— 不新建「me」认知体(D6′)。
// 防「我/me/myself」碎片化成一堆认知体。
TEST(RegistrationGate, SelfSubjectResolvesToHolderNotNewCognizer) {
    auto a = make_adapter();
    auto& conn = a->connection();
    seed_engram(conn);
    FakeLLMAdapter llm;
    llm.set_default_response(LLMResponse{
        .raw_xml = one_stmt("me", "cognizer", "self"), .ok = true});
    Extractor ex(conn, llm, *a);
    ex.run("engram-1", {1, 2, 3}, "system_self", "default", {});
    // 不建一个叫「me」的认知体。
    EXPECT_EQ(cognizer_count(conn, "me"), 0);
}

}  // namespace starling::extractor

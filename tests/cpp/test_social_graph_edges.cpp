// PR4 缺陷 B: 从 belief 的关系谓词(reports_to/member_of)抽社会图边。
// belief 写路径里,若 statement 落库成功 + subject 是已 resolve 的 cognizer +
// predicate ∈ {reports_to, member_of} + object 串能反查到【已存在】认知体,
// 就 upsert 一条有向带类型边(a=subject, b=object)。
//
// 决策(用户拍板):
//  - 来源仅 belief 关系谓词(不含 episodic 共现/二阶信念)。
//  - object 反查 miss → 跳过不建边,绝不注册新认知体(防重引入过度注册污染)。
//  - Fiske 按谓词硬映射:reports_to→Authority 重, member_of→Communal 重。
//  - 边有向(a=subject→b=object);前端渲染本轮不动。
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

// One belief statement with caller-supplied subject/predicate/object, all
// cognizer-kind subject. holder is "self" (narrator).
std::string one_rel(const std::string& subject, const std::string& predicate,
                    const std::string& object) {
    return R"([{"holder":"self","holder_perspective":"FIRST_PERSON","subject":")"
        + subject + R"(","predicate":")" + predicate + R"(","object":")" + object
        + R"(","modality":"BELIEVES","polarity":"POS","nesting_depth":0,)"
        + R"("subject_kind":"cognizer","cognizer_kind":"human"}])";
}

int relation_count(persistence::Connection& conn) {
    sqlite3_stmt* raw = nullptr;
    sqlite3_prepare_v2(conn.raw(),
        "SELECT COUNT(*) FROM cognizer_relations WHERE tenant_id='default'",
        -1, &raw, nullptr);
    persistence::StmtHandle h(raw);
    sqlite3_step(h.get());
    return sqlite3_column_int(h.get(), 0);
}

// Pre-register a cognizer so the object-side lookup_by_alias hits.
std::string seed_cognizer(cognizer::CognizerHub& hub, const std::string& name,
                          cognizer::CognizerKind kind) {
    cognizer::CognizerRegistration reg;
    reg.kind = kind;
    reg.tenant_id = "default";
    reg.tenant_explicitly_set = true;   // kind=group 要求显式 tenant(08_cognizer.md:139)
    reg.canonical_name = name;
    reg.aliases = {name};
    reg.external_id = name;
    return hub.register_cognizer(reg).id;
}

// The single relation edge's (a_id, b_id, dominant-fiske-mode). Empty a_id if none.
struct EdgeRow { std::string a_id, b_id, top_fiske; double top_weight = 0.0; };
EdgeRow single_edge(persistence::Connection& conn) {
    sqlite3_stmt* raw = nullptr;
    sqlite3_prepare_v2(conn.raw(),
        "SELECT a_id, b_id, fiske_weights_json FROM cognizer_relations "
        "WHERE tenant_id='default' LIMIT 1",
        -1, &raw, nullptr);
    persistence::StmtHandle h(raw);
    EdgeRow e;
    if (sqlite3_step(h.get()) != SQLITE_ROW) return e;
    e.a_id = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 0));
    e.b_id = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 1));
    const std::string fj = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 2));
    // crude dominant-mode extraction: find the max "mode":weight in the JSON.
    for (const char* m : {"communal", "authority", "equality", "market"}) {
        auto pos = fj.find(std::string("\"") + m + "\":");
        if (pos == std::string::npos) continue;
        double w = std::stod(fj.substr(pos + std::string(m).size() + 3));
        if (w > e.top_weight) { e.top_weight = w; e.top_fiske = m; }
    }
    return e;
}

}  // namespace

// reports_to(Alice→Bob): both cognizers exist → 有向边 a=Alice b=Bob,
// Fiske 以 Authority 为主(上下级关系)。
TEST(SocialGraphEdges, ReportsToBuildsAuthorityEdge) {
    auto a = make_adapter();
    auto& conn = a->connection();
    seed_engram(conn);
    cognizer::CognizerHub hub(*a);
    const std::string alice = seed_cognizer(hub, "Alice", cognizer::CognizerKind::Human);
    const std::string bob   = seed_cognizer(hub, "Bob",   cognizer::CognizerKind::Human);

    FakeLLMAdapter llm;
    llm.set_default_response(LLMResponse{
        .raw_xml = one_rel("Alice", "reports_to", "Bob"), .ok = true});
    Extractor ex(conn, llm, *a);
    ex.run("engram-1", {1, 2, 3}, "system_self", "default", {});

    ASSERT_EQ(relation_count(conn), 1);
    EdgeRow e = single_edge(conn);
    EXPECT_EQ(e.a_id, alice);       // a=subject
    EXPECT_EQ(e.b_id, bob);         // b=object
    EXPECT_EQ(e.top_fiske, "authority");
}

// member_of(Alice→platform team): group object exists → Communal-dominant edge.
TEST(SocialGraphEdges, MemberOfBuildsCommunalEdge) {
    auto a = make_adapter();
    auto& conn = a->connection();
    seed_engram(conn);
    cognizer::CognizerHub hub(*a);
    const std::string alice = seed_cognizer(hub, "Alice", cognizer::CognizerKind::Human);
    const std::string team  = seed_cognizer(hub, "platform team", cognizer::CognizerKind::Group);

    FakeLLMAdapter llm;
    llm.set_default_response(LLMResponse{
        .raw_xml = one_rel("Alice", "member_of", "platform team"), .ok = true});
    Extractor ex(conn, llm, *a);
    ex.run("engram-1", {1, 2, 3}, "system_self", "default", {});

    ASSERT_EQ(relation_count(conn), 1);
    EdgeRow e = single_edge(conn);
    EXPECT_EQ(e.a_id, alice);
    EXPECT_EQ(e.b_id, team);
    EXPECT_EQ(e.top_fiske, "communal");
}

// object 反查 miss(Bob 未注册)→ 不建边,且不注册 Bob(决策 2 安全侧)。
TEST(SocialGraphEdges, ObjectMissSkipsEdgeAndDoesNotRegister) {
    auto a = make_adapter();
    auto& conn = a->connection();
    seed_engram(conn);
    cognizer::CognizerHub hub(*a);
    seed_cognizer(hub, "Alice", cognizer::CognizerKind::Human);
    // Bob NOT seeded → lookup_by_alias miss.

    FakeLLMAdapter llm;
    llm.set_default_response(LLMResponse{
        .raw_xml = one_rel("Alice", "reports_to", "Bob"), .ok = true});
    Extractor ex(conn, llm, *a);
    ex.run("engram-1", {1, 2, 3}, "system_self", "default", {});

    EXPECT_EQ(relation_count(conn), 0);  // 无边
    // Bob 不被注册(反查不注册)。
    sqlite3_stmt* raw = nullptr;
    sqlite3_prepare_v2(conn.raw(),
        "SELECT COUNT(*) FROM cognizers WHERE tenant_id='default' AND canonical_name='Bob'",
        -1, &raw, nullptr);
    persistence::StmtHandle h(raw);
    sqlite3_step(h.get());
    EXPECT_EQ(sqlite3_column_int(h.get(), 0), 0);
}

// 非关系谓词(responsible_for)不建边,即便 subject/object 都是 cognizer。
TEST(SocialGraphEdges, NonRelationPredicateNoEdge) {
    auto a = make_adapter();
    auto& conn = a->connection();
    seed_engram(conn);
    cognizer::CognizerHub hub(*a);
    seed_cognizer(hub, "Alice", cognizer::CognizerKind::Human);
    seed_cognizer(hub, "Bob",   cognizer::CognizerKind::Human);

    FakeLLMAdapter llm;
    llm.set_default_response(LLMResponse{
        .raw_xml = one_rel("Alice", "responsible_for", "Bob"), .ok = true});
    Extractor ex(conn, llm, *a);
    ex.run("engram-1", {1, 2, 3}, "system_self", "default", {});

    EXPECT_EQ(relation_count(conn), 0);
}

// entity subject 不建边(subject 未 resolve 成 cognizer)。
TEST(SocialGraphEdges, EntitySubjectNoEdge) {
    auto a = make_adapter();
    auto& conn = a->connection();
    seed_engram(conn);
    cognizer::CognizerHub hub(*a);
    seed_cognizer(hub, "Bob", cognizer::CognizerKind::Human);

    FakeLLMAdapter llm;
    // subject_kind=entity → subject 不 resolve,故不该建边。
    const std::string raw_json =
        R"([{"holder":"self","holder_perspective":"FIRST_PERSON","subject":"some system",)"
        R"("predicate":"reports_to","object":"Bob","modality":"BELIEVES","polarity":"POS",)"
        R"("nesting_depth":0,"subject_kind":"entity"}])";
    llm.set_default_response(LLMResponse{.raw_xml = raw_json, .ok = true});
    Extractor ex(conn, llm, *a);
    ex.run("engram-1", {1, 2, 3}, "system_self", "default", {});

    EXPECT_EQ(relation_count(conn), 0);
}

}  // namespace starling::extractor

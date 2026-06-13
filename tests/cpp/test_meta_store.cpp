// P3.b1 phase 3:MetaStore 读收编。钉 get_statement(点查全字段)+
// query_statements(StatementFilter 各 WHERE 模式)。纯新增,无路由改动。
#include "starling/store/sqlite_meta_store.hpp"

#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <cstdio>
#include <memory>
#include <string>

namespace starling::store {
namespace {

std::unique_ptr<persistence::SqliteAdapter> make_adapter() {
    auto a = persistence::SqliteAdapter::open(":memory:");
    persistence::MigrationRunner(a->connection().raw()).migrate_to_latest();
    return a;
}

// 种一行 statements(覆盖必填列 + 收编关心的扩展列)。
void seed(persistence::Connection& conn, const char* id, const char* holder,
          const char* subject, const char* predicate, const char* state,
          const char* provenance = "user_input", int nesting_depth = 0,
          double salience = 0.5, const char* observed = "2026-06-10T00:00:00Z",
          const char* valid_to = "") {
    char vt[64];
    if (valid_to[0]) std::snprintf(vt, sizeof(vt), "'%s'", valid_to);
    else std::snprintf(vt, sizeof(vt), "NULL");
    char sql[1400];
    std::snprintf(sql, sizeof(sql),
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
        "subject_kind,subject_id,predicate,object_kind,object_value,"
        "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
        "confidence,observed_at,salience,affect_json,activation,last_accessed,"
        "provenance,evidence_json,consolidation_state,review_status,"
        "nesting_depth,valid_to,created_at,updated_at) VALUES("
        "'%s','default','%s','FIRST_PERSON','cognizer','%s','%s','str','obj-%s',"
        "'h-%s','v1','KNOWS','POS',0.9,'%s',%f,'{}',0.3,'%s','%s',"
        "'[{\"engram_ref\":\"e-%s\"}]','%s','approved',%d,%s,'%s','%s')",
        id, holder, subject, predicate, id, id, observed, salience, observed,
        provenance, id, state, nesting_depth, vt, observed, observed);
    char* err = nullptr;
    ASSERT_EQ(sqlite3_exec(conn.raw(), sql, nullptr, nullptr, &err), SQLITE_OK)
        << (err ? err : "");
}

}  // namespace

TEST(MetaStore, GetStatementReturnsFullRowOrNullopt) {
    auto a = make_adapter();
    SqliteMetaStore m(a->connection());
    seed(a->connection(), "s1", "cog-self", "Bob", "responsible_for",
         "consolidated", "tom_inferred", /*nesting=*/1, /*salience=*/0.7);

    const auto row = m.get_statement("s1", "default");
    ASSERT_TRUE(row.has_value());
    EXPECT_EQ(row->id, "s1");
    EXPECT_EQ(row->holder_id, "cog-self");
    EXPECT_EQ(row->subject_id, "Bob");
    EXPECT_EQ(row->predicate, "responsible_for");
    EXPECT_EQ(row->consolidation_state, "consolidated");
    EXPECT_EQ(row->provenance, "tom_inferred");
    EXPECT_EQ(row->nesting_depth, 1);
    EXPECT_NEAR(row->salience, 0.7, 1e-9);
    EXPECT_NEAR(row->activation, 0.3, 1e-9);

    EXPECT_FALSE(m.get_statement("missing", "default").has_value());
    EXPECT_FALSE(m.get_statement("s1", "other-tenant").has_value());
}

TEST(MetaStore, QueryByHolderSubjectPredicateWithDefaultStateReviewGuard) {
    auto a = make_adapter();
    SqliteMetaStore m(a->connection());
    seed(a->connection(), "ok",  "cog-self", "Bob", "knows", "consolidated");
    seed(a->connection(), "vol", "cog-self", "Bob", "knows", "volatile");      // 默认排除
    seed(a->connection(), "arch","cog-self", "Bob", "knows", "archived");      // 默认包含
    seed(a->connection(), "diff","cog-self", "Carol", "knows", "consolidated"); // subject 不符

    StatementFilter f;
    f.tenant_id = "default"; f.holder_id = "cog-self";
    f.subject_kind = "cognizer"; f.subject_id = "Bob"; f.predicate = "knows";
    const auto rows = m.query_statements(f);
    // 默认 state IN(consolidated,archived) + review NOT IN(rejected,pending_review)。
    ASSERT_EQ(rows.size(), 2u);
    for (const auto& r : rows) {
        EXPECT_EQ(r.subject_id, "Bob");
        EXPECT_NE(r.consolidation_state, "volatile");
    }
}

TEST(MetaStore, QueryPredicateInAndNestingDepth) {
    auto a = make_adapter();
    SqliteMetaStore m(a->connection());
    seed(a->connection(), "n1", "cog-self", "team", "forbids", "consolidated");
    seed(a->connection(), "n2", "cog-self", "team", "requires", "consolidated");
    seed(a->connection(), "p1", "cog-self", "team", "prefers", "consolidated");
    seed(a->connection(), "nest", "cog-self", "Bob", "believes", "consolidated",
         "tom_inferred", /*nesting=*/1);

    StatementFilter norms;
    norms.tenant_id = "default";
    norms.predicate_in = {"forbids", "requires"};
    EXPECT_EQ(m.query_statements(norms).size(), 2u);

    StatementFilter nested;
    nested.tenant_id = "default"; nested.nesting_depth_ge = 1;
    const auto nr = m.query_statements(nested);
    ASSERT_EQ(nr.size(), 1u);
    EXPECT_EQ(nr[0].id, "nest");
}

TEST(MetaStore, QueryVolatileByProvenanceWithOrderAndLimit) {
    auto a = make_adapter();
    SqliteMetaStore m(a->connection());
    seed(a->connection(), "v1", "cog-self", "Bob", "knows", "volatile",
         "user_input", 0, 0.5, "2026-06-01T00:00:00Z");
    seed(a->connection(), "v2", "cog-self", "Bob", "knows", "volatile",
         "user_input", 0, 0.5, "2026-06-03T00:00:00Z");
    seed(a->connection(), "vt", "cog-self", "Bob", "knows", "volatile",
         "tom_inferred", 0, 0.5, "2026-06-02T00:00:00Z");
    seed(a->connection(), "c1", "cog-self", "Bob", "knows", "consolidated");

    StatementFilter f;
    f.tenant_id = "default";
    f.consolidation_states = {"volatile"};
    f.provenance = "user_input";
    f.order_by = "observed_at DESC";
    f.limit = 1;
    const auto rows = m.query_statements(f);
    ASSERT_EQ(rows.size(), 1u);
    EXPECT_EQ(rows[0].id, "v2");   // 最新的 user_input volatile
}

TEST(MetaStore, QuerySalienceGeNoReviewGuardDoubleKeyOrder) {
    // affect_buffer 模式:volatile + salience>=θ,无 review 守卫,salience DESC
    // 双键排序取 top-C。
    auto a = make_adapter();
    SqliteMetaStore m(a->connection());
    seed(a->connection(), "hot",  "cog-self", "Bob", "knows", "volatile",
         "user_input", 0, /*salience=*/0.9);
    seed(a->connection(), "mid",  "cog-self", "Bob", "knows", "volatile",
         "user_input", 0, 0.7);
    seed(a->connection(), "dull", "cog-self", "Bob", "knows", "volatile",
         "user_input", 0, 0.3);
    StatementFilter f;
    f.tenant_id = "default";
    f.consolidation_states = {"volatile"};
    f.salience_ge = 0.6;
    f.default_review_guard = false;
    f.order_by = "salience DESC, created_at ASC";
    f.limit = 10;
    const auto rows = m.query_statements(f);
    ASSERT_EQ(rows.size(), 2u);     // hot + mid (>=0.6)
    EXPECT_EQ(rows[0].id, "hot");   // salience DESC
    EXPECT_EQ(rows[1].id, "mid");
}

TEST(MetaStore, QueryAsOfTimeWindow) {
    auto a = make_adapter();
    SqliteMetaStore m(a->connection());
    // valid_to 已过 → as_of 之后不可见。
    seed(a->connection(), "expired", "cog-self", "Bob", "knows", "consolidated",
         "user_input", 0, 0.5, "2026-05-01T00:00:00Z", "2026-06-01T00:00:00Z");
    seed(a->connection(), "live", "cog-self", "Bob", "knows", "consolidated");

    StatementFilter f;
    f.tenant_id = "default"; f.as_of_iso8601 = "2026-06-10T00:00:00Z";
    const auto rows = m.query_statements(f);
    ASSERT_EQ(rows.size(), 1u);
    EXPECT_EQ(rows[0].id, "live");
}

}  // namespace starling::store

#include "starling/bus/bus.hpp"
#include "starling/extractor/extracted_statement.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <gtest/gtest.h>

#include <map>
#include <memory>
#include <string>

namespace starling::bus {

namespace {

std::unique_ptr<persistence::SqliteAdapter> make_adapter() {
    auto a = persistence::SqliteAdapter::open(":memory:");
    persistence::MigrationRunner(a->connection().raw()).migrate_to_latest();
    return a;
}

extractor::ExtractedStatement base_stmt() {
    extractor::ExtractedStatement s;
    s.holder_id            = "alice";
    s.holder_tenant_id     = "t1";
    s.holder_perspective   = schema::Perspective::FIRST_PERSON;
    s.subject_kind         = "cognizer";
    s.subject_id           = "bob";
    s.predicate            = "knows";
    s.object_kind          = "str";
    s.object_value         = "calculus";
    s.canonical_object_hash = "hash-calculus";
    s.modality             = schema::Modality::BELIEVES;
    s.polarity             = schema::Polarity::POS;
    s.confidence           = 0.9;
    s.observed_at          = "2026-05-24T00:00:00Z";
    s.chunk_index          = 0;
    s.source_hash          = "src-hash";
    s.perceived_by         = {"alice"};
    s.provenance           = schema::StatementProvenance::USER_INPUT;
    s.review_status        = schema::ReviewStatus::APPROVED;
    s.derived_from         = {};
    return s;
}

void seed_parent(sqlite3* db, const char* id, const char* tenant_id, int derived_depth) {
    sqlite3_stmt* stmt = nullptr;
    ASSERT_EQ(sqlite3_prepare_v2(db,
        "INSERT INTO statements("
        "id,tenant_id,holder_id,holder_perspective,subject_kind,subject_id,predicate,"
        "object_kind,object_value,canonical_object_hash,modality,polarity,confidence,"
        "observed_at,salience,affect_json,activation,last_accessed,provenance,"
        "derived_depth,created_at,updated_at) "
        "VALUES(?,?,'alice','first_person','cognizer','bob','knows','str','calculus',"
        "'hash-parent','BELIEVES','pos',0.9,'2026-05-24T00:00:00Z',0.1,'{}',0.0,"
        "'2026-05-24T00:00:00Z','user_input',?,'2026-05-24T00:00:00Z',"
        "'2026-05-24T00:00:00Z')",
        -1, &stmt, nullptr), SQLITE_OK);
    persistence::StmtHandle handle(stmt);
    sqlite3_bind_text(handle.get(), 1, id, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(handle.get(), 2, tenant_id, -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(handle.get(), 3, derived_depth);
    ASSERT_EQ(sqlite3_step(handle.get()), SQLITE_DONE);
}

}  // namespace

TEST(StatementWriterDerivedFromTest, PersistsParentIdsAndDepth) {
    auto a = make_adapter();
    Bus bus(*a);

    extractor::ExtractedStatement parent = base_stmt();
    auto p_out = bus.write(parent, /*evidence=*/"engram-1", /*span_key=*/"chunk-0", std::nullopt);
    const auto p_id = std::get<StatementWriteAccepted>(p_out).stmt_id;

    extractor::ExtractedStatement child = base_stmt();
    child.subject_id            = "carol";
    child.canonical_object_hash = "hash-calculus-carol";
    child.derived_from          = {p_id};

    auto c_out = bus.write(child, "engram-2", "chunk-0", std::nullopt);
    const auto c_id = std::get<StatementWriteAccepted>(c_out).stmt_id;

    sqlite3* db = a->connection().raw();
    sqlite3_stmt* stmt = nullptr;
    sqlite3_prepare_v2(db,
        "SELECT id, derived_from_json, derived_depth FROM statements ORDER BY id",
        -1, &stmt, nullptr);

    std::map<std::string, std::pair<std::string, int>> rows;
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        rows[(const char*)sqlite3_column_text(stmt, 0)] = {
            (const char*)sqlite3_column_text(stmt, 1),
            sqlite3_column_int(stmt, 2)
        };
    }
    sqlite3_finalize(stmt);

    ASSERT_EQ(rows[p_id].first, "[]");
    ASSERT_EQ(rows[p_id].second, 0);
    ASSERT_EQ(rows[c_id].first, std::string("[\"") + p_id + "\"]");
    ASSERT_EQ(rows[c_id].second, 1);
}

TEST(StatementWriterDerivedFromTest, ParentDepthIsTenantScoped) {
    auto a = make_adapter();
    sqlite3* db = a->connection().raw();
    seed_parent(db, "shared-parent", "tenant-a", 8);
    seed_parent(db, "shared-parent", "tenant-b", 0);

    Bus bus(*a);
    extractor::ExtractedStatement child = base_stmt();
    child.holder_tenant_id = "tenant-b";
    child.subject_id = "carol";
    child.canonical_object_hash = "hash-child";
    child.derived_from = {"shared-parent"};

    const auto outcome = bus.write(child, "engram-child", "chunk-child", std::nullopt);
    const auto child_id = std::get<StatementWriteAccepted>(outcome).stmt_id;

    sqlite3_stmt* stmt = nullptr;
    ASSERT_EQ(sqlite3_prepare_v2(db,
        "SELECT derived_depth FROM statements WHERE id = ? AND tenant_id = ?",
        -1, &stmt, nullptr), SQLITE_OK);
    persistence::StmtHandle handle(stmt);
    sqlite3_bind_text(handle.get(), 1, child_id.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(handle.get(), 2, child.holder_tenant_id.c_str(), -1, SQLITE_TRANSIENT);
    ASSERT_EQ(sqlite3_step(handle.get()), SQLITE_ROW);
    EXPECT_EQ(sqlite3_column_int(handle.get(), 0), 1);
}

}  // namespace starling::bus

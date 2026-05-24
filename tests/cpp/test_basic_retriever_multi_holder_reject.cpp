#include "starling/retrieval/basic_retriever.hpp"

#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <gtest/gtest.h>

#include <stdexcept>

namespace starling::retrieval {
namespace {

BasicRetrieverParams minimal_ok() {
    BasicRetrieverParams p;
    p.tenant_id      = "t1";
    p.holder_id      = "alice";
    p.intent         = QueryIntent::FACT_LOOKUP;
    p.subject_id     = "bob";
    p.predicate      = "responsible_for";
    p.as_of_iso8601  = "2026-04-15T00:00:00Z";
    p.trace_id       = "trace-x";
    p.query_id       = "query-x";
    return p;
}

class BasicRetrieverRejectTest : public ::testing::Test {
 protected:
    void SetUp() override {
        adapter_ = persistence::SqliteAdapter::open(":memory:");
        // SqliteAdapter::open already runs migrate_to_latest, but invoking it
        // again is idempotent and matches the fixture style of the other M0.6
        // tests for clarity at the call site.
        persistence::MigrationRunner(adapter_->connection().raw())
            .migrate_to_latest();
    }
    std::unique_ptr<persistence::SqliteAdapter> adapter_;
};

TEST_F(BasicRetrieverRejectTest, EmptyTenantId) {
    BasicRetriever r(*adapter_);
    auto p = minimal_ok();
    p.tenant_id = "";
    EXPECT_THROW(r.run(p), std::invalid_argument);
}

TEST_F(BasicRetrieverRejectTest, EmptyHolderId) {
    BasicRetriever r(*adapter_);
    auto p = minimal_ok();
    p.holder_id = "";
    EXPECT_THROW(r.run(p), std::invalid_argument);
}

TEST_F(BasicRetrieverRejectTest, EmptySubjectId) {
    BasicRetriever r(*adapter_);
    auto p = minimal_ok();
    p.subject_id = "";
    EXPECT_THROW(r.run(p), std::invalid_argument);
}

TEST_F(BasicRetrieverRejectTest, EmptyPredicate) {
    BasicRetriever r(*adapter_);
    auto p = minimal_ok();
    p.predicate = "";
    EXPECT_THROW(r.run(p), std::invalid_argument);
}

TEST_F(BasicRetrieverRejectTest, EmptyAsOf) {
    BasicRetriever r(*adapter_);
    auto p = minimal_ok();
    p.as_of_iso8601 = "";
    EXPECT_THROW(r.run(p), std::invalid_argument);
}

TEST_F(BasicRetrieverRejectTest, MinimalOkDoesNotThrow) {
    // Sanity: minimal_ok against an empty schema returns 0 rows but does not
    // throw. This guards against the validation regressing into "always
    // throws" — the spec rejects only on empty/invalid inputs, not on empty
    // result sets.
    BasicRetriever r(*adapter_);
    auto result = r.run(minimal_ok());
    EXPECT_EQ(result.rows.size(), 0u);
    EXPECT_EQ(result.receipt.sufficiency_status, Sufficiency::MISSING_INFO);
}

}  // namespace
}  // namespace starling::retrieval

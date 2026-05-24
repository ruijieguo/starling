#include "starling/bus/canonical_scope.hpp"
#include "starling/extractor/extracted_statement.hpp"
#include <gtest/gtest.h>

namespace {
using namespace starling::bus;
using namespace starling::extractor;

TEST(CanonicalScope, ExtractedStatementAlwaysReturnsNull) {
    ExtractedStatement stmt;
    stmt.holder_id = "h1";
    stmt.subject_kind = "entity";
    stmt.subject_id = "e1";
    stmt.predicate = "knows";
    auto scope = scope_of(stmt);
    EXPECT_TRUE(std::holds_alternative<CanonicalScopeNull>(scope));
}

TEST(CanonicalScope, NullCanonicalBytesIsEmpty) {
    CanonicalScopeNull null_scope;
    EXPECT_EQ(null_scope.canonical_bytes(), "");
    EXPECT_EQ(canonical_scope_bytes(CanonicalScope{null_scope}), "");
}

TEST(CanonicalScope, FutureNormArmThrowsInM05) {
    CanonicalScopeNorm norm;
    norm.kind = "obligation";
    norm.members_sorted = {"a", "b"};
    EXPECT_THROW(norm.canonical_bytes(), std::logic_error);
}

TEST(CanonicalScope, FutureCommitmentArmThrowsInM05) {
    CanonicalScopeCommitment c;
    c.principal = "alice";
    c.beneficiary = "bob";
    EXPECT_THROW(c.canonical_bytes(), std::logic_error);
}

TEST(CanonicalScope, FutureCommonGroundArmThrowsInM05) {
    CanonicalScopeCommonGround cg;
    cg.parties_sorted = {"alice", "bob"};
    EXPECT_THROW(cg.canonical_bytes(), std::logic_error);
}

}  // namespace

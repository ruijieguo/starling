#include "starling/bus/canonical_scope.hpp"
#include "starling/extractor/extracted_statement.hpp"
#include "starling/schema/statement_enums.hpp"
#include <gtest/gtest.h>

using namespace starling;
using namespace starling::bus;

static extractor::ExtractedStatement base() {
    extractor::ExtractedStatement s;
    s.holder_id = "self"; s.subject_kind = "cognizer"; s.subject_id = "bob";
    s.predicate = "p"; s.modality = schema::Modality::BELIEVES;
    return s;
}

TEST(CanonicalScope, PlainBeliefIsNull) {
    auto s = base();
    EXPECT_TRUE(std::holds_alternative<CanonicalScopeNull>(scope_of(s)));
}
TEST(CanonicalScope, CommitsIsCommitment) {
    auto s = base(); s.modality = schema::Modality::COMMITS;
    s.scope_parties = {"bob", "self"};
    auto sc = scope_of(s);
    ASSERT_TRUE(std::holds_alternative<CanonicalScopeCommitment>(sc));
    EXPECT_EQ(std::get<CanonicalScopeCommitment>(sc).principal, "self");
    EXPECT_EQ(std::get<CanonicalScopeCommitment>(sc).beneficiary, "bob");
}
TEST(CanonicalScope, NormOughtIsNorm) {
    auto s = base(); s.modality = schema::Modality::NORM_OUGHT;
    auto sc = scope_of(s);
    ASSERT_TRUE(std::holds_alternative<CanonicalScopeNorm>(sc));
    EXPECT_EQ(std::get<CanonicalScopeNorm>(sc).kind, "obligation");
    EXPECT_FALSE(std::get<CanonicalScopeNorm>(sc).canonical_bytes().empty());
}
TEST(CanonicalScope, NormForbidIsProhibition) {
    auto s = base(); s.modality = schema::Modality::NORM_FORBID;
    auto sc = scope_of(s);
    ASSERT_TRUE(std::holds_alternative<CanonicalScopeNorm>(sc));
    EXPECT_EQ(std::get<CanonicalScopeNorm>(sc).kind, "prohibition");
}
TEST(CanonicalScope, TwoPartiesIsCommonGround) {
    auto s = base(); s.scope_parties = {"self", "bob"};
    auto sc = scope_of(s);
    ASSERT_TRUE(std::holds_alternative<CanonicalScopeCommonGround>(sc));
    EXPECT_EQ(std::get<CanonicalScopeCommonGround>(sc).parties_sorted, (std::vector<std::string>{"bob","self"}));
}
TEST(CanonicalScope, DifferentPartiesDifferentBytes) {
    auto a = base(); a.scope_parties = {"self","bob"};
    auto b = base(); b.scope_parties = {"self","carol"};
    EXPECT_NE(canonical_scope_bytes(scope_of(a)), canonical_scope_bytes(scope_of(b)));
}

#include <gtest/gtest.h>

#include <string>

#include "starling/final_query_assertion.hpp"

using starling::assert_final_query_safe;
using starling::FinalQueryAssertionError;

TEST(FinalQueryAssertion, AcceptsQueryWithBothPredicates) {
    EXPECT_NO_THROW(assert_final_query_safe(
        "SELECT id FROM statements "
        "WHERE tenant_id = ? AND holder_scope = ? AND consolidation_state = 'CONSOLIDATED'"));
}

TEST(FinalQueryAssertion, RejectsQueryMissingTenantId) {
    EXPECT_THROW(
        assert_final_query_safe(
            "SELECT id FROM statements WHERE holder_scope = ?"),
        FinalQueryAssertionError);
}

TEST(FinalQueryAssertion, RejectsQueryMissingHolderScope) {
    EXPECT_THROW(
        assert_final_query_safe(
            "SELECT id FROM statements WHERE tenant_id = ?"),
        FinalQueryAssertionError);
}

TEST(FinalQueryAssertion, RejectsBareSelectStar) {
    EXPECT_THROW(assert_final_query_safe("SELECT * FROM statements"),
                 FinalQueryAssertionError);
}

TEST(FinalQueryAssertion, IsCaseInsensitive) {
    EXPECT_NO_THROW(assert_final_query_safe(
        "select id from statements where Tenant_Id = ? and Holder_Scope = ?"));
}

TEST(FinalQueryAssertion, AcceptsParenthesizedPredicates) {
    EXPECT_NO_THROW(assert_final_query_safe(
        "SELECT id FROM statements "
        "WHERE (tenant_id = ?) AND (holder_scope IN (?, ?))"));
}

TEST(FinalQueryAssertion, RejectsOnlyInComment) {
    EXPECT_THROW(
        assert_final_query_safe(
            "SELECT * FROM statements -- tenant_id and holder_scope are mandatory"),
        FinalQueryAssertionError);
}

TEST(FinalQueryAssertion, ErrorMessageNamesMissingPredicates) {
    try {
        assert_final_query_safe("SELECT id FROM statements WHERE 1=1");
        FAIL() << "expected FinalQueryAssertionError";
    } catch (const FinalQueryAssertionError& err) {
        std::string what = err.what();
        EXPECT_NE(what.find("tenant_id"), std::string::npos);
        EXPECT_NE(what.find("holder_scope"), std::string::npos);
    }
}

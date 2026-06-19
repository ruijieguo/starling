// Phase 2 Task 2.1: name_resolver over CognizerHub. Verifies surface drift
// (internal-space + case) resolves to a single canonical first-seen name, that
// single-surface names are idempotent (canonical == surface → pins-green), and
// that the query-only path passes unknown surfaces through without registering.
#include "starling/cognizer/name_resolver.hpp"

#include "starling/cognizer/cognizer_hub.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <gtest/gtest.h>

using starling::cognizer::CognizerHub;
using starling::cognizer::fold_internal_spaces;
using starling::cognizer::resolve_cognizer;
using starling::cognizer::resolve_or_register_cognizer;
using starling::persistence::SqliteAdapter;

TEST(NameResolver, FoldInternalSpacesDropsWhitespaceAndLowercases) {
    EXPECT_EQ(fold_internal_spaces("Xiao Hong"), "xiaohong");
    EXPECT_EQ(fold_internal_spaces("XiaoHong"), "xiaohong");
    EXPECT_EQ(fold_internal_spaces("  xiao   hong  "), "xiaohong");
    EXPECT_EQ(fold_internal_spaces("Sally"), "sally");
}

TEST(NameResolver, ResolvesInternalSpaceAndCaseDrift) {
    auto adapter = SqliteAdapter::open(":memory:");
    CognizerHub hub(*adapter);
    const char* T = "default";
    // first surface registers; canonical = first-seen verbatim
    EXPECT_EQ(resolve_or_register_cognizer(hub, T, "Xiao Hong"), "Xiao Hong");
    // drifted surfaces resolve to the canonical first-seen surface
    EXPECT_EQ(resolve_or_register_cognizer(hub, T, "XiaoHong"), "Xiao Hong");
    EXPECT_EQ(resolve_or_register_cognizer(hub, T, "xiao hong"), "Xiao Hong");
    EXPECT_EQ(resolve_or_register_cognizer(hub, T, "XIAOHONG"), "Xiao Hong");
    // distinct name → distinct
    EXPECT_EQ(resolve_or_register_cognizer(hub, T, "Li Lei"), "Li Lei");
    // single-surface idempotent (canonical == surface) — pins-green guarantee
    EXPECT_EQ(resolve_or_register_cognizer(hub, T, "Sally"), "Sally");
    EXPECT_EQ(resolve_or_register_cognizer(hub, T, "Sally"), "Sally");
    // query-only resolve: known → canonical, unknown → passthrough (no register)
    EXPECT_EQ(resolve_cognizer(hub, T, "XIAOHONG"), "Xiao Hong");
    EXPECT_EQ(resolve_cognizer(hub, T, "Unknown Person"), "Unknown Person");
}

TEST(NameResolver, QueryOnlyDoesNotRegister) {
    auto adapter = SqliteAdapter::open(":memory:");
    CognizerHub hub(*adapter);
    const char* T = "default";
    // resolve_cognizer must NOT create the entity: a follow-up lookup stays empty.
    EXPECT_EQ(resolve_cognizer(hub, T, "Ghost"), "Ghost");
    EXPECT_EQ(hub.lookup_by_alias(T, "Ghost"), std::nullopt);
    // ... whereas the write-side path does register it.
    EXPECT_EQ(resolve_or_register_cognizer(hub, T, "Ghost"), "Ghost");
    ASSERT_TRUE(hub.lookup_by_alias(T, "Ghost").has_value());
}

TEST(NameResolver, EmptySurfacePassthrough) {
    auto adapter = SqliteAdapter::open(":memory:");
    CognizerHub hub(*adapter);
    EXPECT_EQ(resolve_or_register_cognizer(hub, "default", ""), "");
    EXPECT_EQ(resolve_cognizer(hub, "default", ""), "");
}

#include "starling/cognizer/cognizer_hub.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <gtest/gtest.h>

using starling::cognizer::AliasCollision;
using starling::cognizer::CognizerHub;
using starling::cognizer::CognizerKind;
using starling::cognizer::CognizerRegistration;
using starling::cognizer::GroupTenantImplicit;
using starling::persistence::SqliteAdapter;

namespace {

CognizerRegistration human_req(std::string ext_id,
                                 std::vector<std::string> aliases = {}) {
    CognizerRegistration r;
    r.kind = CognizerKind::Human;
    r.tenant_id = "default";
    r.tenant_explicitly_set = false;
    r.external_id = ext_id;
    r.aliases = std::move(aliases);
    return r;
}

}  // namespace

TEST(CognizerHubRegister, IdempotentSameInputSameId) {
    auto adapter = SqliteAdapter::open(":memory:");
    CognizerHub hub(*adapter);
    auto first  = hub.register_cognizer(human_req("alice", {"Alice"}));
    auto second = hub.register_cognizer(human_req("alice", {"Alice"}));
    EXPECT_EQ(first.id, second.id);
    EXPECT_GE(second.last_seen_at, first.last_seen_at);
}

TEST(CognizerHubRegister, DifferentKindDifferentId) {
    auto adapter = SqliteAdapter::open(":memory:");
    CognizerHub hub(*adapter);
    CognizerRegistration human_r = human_req("bot-007");
    CognizerRegistration agent_r = human_req("bot-007");
    agent_r.kind = CognizerKind::Agent;
    auto h = hub.register_cognizer(human_r);
    auto a = hub.register_cognizer(agent_r);
    EXPECT_NE(h.id, a.id);
}

TEST(CognizerHubRegister, GroupRequiresExplicitTenant) {
    auto adapter = SqliteAdapter::open(":memory:");
    CognizerHub hub(*adapter);
    CognizerRegistration r;
    r.kind = CognizerKind::Group;
    r.tenant_id = "default";
    r.tenant_explicitly_set = false;
    r.external_id = "eng-team";
    EXPECT_THROW(hub.register_cognizer(r), GroupTenantImplicit);
}

TEST(CognizerHubRegister, GroupExplicitTenantAccepted) {
    auto adapter = SqliteAdapter::open(":memory:");
    CognizerHub hub(*adapter);
    CognizerRegistration r;
    r.kind = CognizerKind::Group;
    r.tenant_id = "tenant-a";
    r.tenant_explicitly_set = true;
    r.external_id = "eng-team";
    EXPECT_NO_THROW(hub.register_cognizer(r));
}

TEST(CognizerHubRegister, AliasCollisionRejected) {
    auto adapter = SqliteAdapter::open(":memory:");
    CognizerHub hub(*adapter);
    hub.register_cognizer(human_req("alice-1", {"Alice"}));
    EXPECT_THROW(
        hub.register_cognizer(human_req("alice-2", {"alice"})),
        AliasCollision);
}

TEST(CognizerHubRegister, LookupByAliasReturnsExisting) {
    auto adapter = SqliteAdapter::open(":memory:");
    CognizerHub hub(*adapter);
    auto c = hub.register_cognizer(human_req("alice", {"Alice", "alice@example.com"}));
    auto found = hub.lookup_by_alias("default", "ALICE");
    ASSERT_TRUE(found.has_value());
    EXPECT_EQ(*found, c.id);
}

TEST(CognizerHubRegister, LookupByAliasMissingReturnsNullopt) {
    auto adapter = SqliteAdapter::open(":memory:");
    CognizerHub hub(*adapter);
    EXPECT_EQ(hub.lookup_by_alias("default", "ghost"), std::nullopt);
}

TEST(CognizerHubRegister, GetReturnsFullRecord) {
    auto adapter = SqliteAdapter::open(":memory:");
    CognizerHub hub(*adapter);
    auto c = hub.register_cognizer(human_req("alice", {"Alice"}));
    auto fetched = hub.get(c.id, "default");
    ASSERT_TRUE(fetched.has_value());
    EXPECT_EQ(fetched->canonical_name, "Alice");
    EXPECT_EQ(fetched->kind, CognizerKind::Human);
    EXPECT_EQ(fetched->external_id, "alice");
}

TEST(CognizerHubRegister, UpdateLastSeenAtBumps) {
    auto adapter = SqliteAdapter::open(":memory:");
    CognizerHub hub(*adapter);
    auto c = hub.register_cognizer(human_req("alice"));
    const std::string later = "2099-01-01T00:00:00Z";
    hub.update_last_seen_at(c.id, "default", later);
    auto fetched = hub.get(c.id, "default");
    ASSERT_TRUE(fetched.has_value());
    EXPECT_EQ(fetched->last_seen_at, later);
}

TEST(CognizerHubRegister, UpdateLastSeenAtMissingNoOp) {
    auto adapter = SqliteAdapter::open(":memory:");
    CognizerHub hub(*adapter);
    EXPECT_NO_THROW(hub.update_last_seen_at("ghost-id", "default", "2099-01-01T00:00:00Z"));
}

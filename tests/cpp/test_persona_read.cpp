// test_persona_read.cpp -- P2.e PersonaContainer.read
#include "starling/neocortex/persona_container.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
#include <vector>
#include <string>

using starling::neocortex::AnchorStatement;
using starling::neocortex::PersonaContainer;
using starling::neocortex::PersonaView;
using starling::persistence::Connection;
using starling::persistence::SqliteAdapter;

TEST(PersonaRead, RebuildThenRead) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    PersonaContainer pc(*adapter);
    std::vector<AnchorStatement> sources = {
        {"s1", "self_model_anchor", "traits", "concise", 0.9},
        {"s2", "self_model_anchor", "preferences", "dark mode", 0.8},
    };
    pc.rebuild(conn, "default", "alice", sources, "2026-06-01T09:00:00Z");

    PersonaView v = pc.read(conn, "default", "alice");
    EXPECT_TRUE(v.found);
    EXPECT_EQ(v.holder_id, "alice");
    EXPECT_EQ(v.dimensions["traits"], "concise");
    EXPECT_EQ(v.dimensions["preferences"], "dark mode");
}

TEST(PersonaRead, MissingReturnsNotFound) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    PersonaContainer pc(*adapter);
    PersonaView v = pc.read(conn, "default", "nobody");
    EXPECT_FALSE(v.found);
    EXPECT_TRUE(v.dimensions.empty());
}

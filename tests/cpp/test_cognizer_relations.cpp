#include "starling/cognizer/cognizer_hub.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <gtest/gtest.h>

using namespace starling::cognizer;
using starling::persistence::SqliteAdapter;

namespace {

RelationEdgeInput valid_input() {
    RelationEdgeInput r;
    r.tenant_id = "default";
    r.a_id = "alice";
    r.b_id = "bob";
    r.fiske_weights = {
        {FiskeMode::Communal,  0.4},
        {FiskeMode::Authority, 0.2},
        {FiskeMode::Equality,  0.3},
        {FiskeMode::Market,    0.1},
    };
    r.affinity = 0.7;
    r.power_asymmetry = 0.1;
    r.trust = {{"work", 0.8}, {"personal", 0.5}};
    return r;
}

}  // namespace

TEST(CognizerRelations, FiskeWeightsSumOneAccepted) {
    auto adapter = SqliteAdapter::open(":memory:");
    CognizerHub hub(*adapter);
    auto edge = hub.upsert_relation(valid_input());
    EXPECT_FALSE(edge.id.empty());
    EXPECT_EQ(edge.a_id, "alice");
    EXPECT_EQ(edge.b_id, "bob");
}

TEST(CognizerRelations, FiskeWeightsSumNotOneRejected) {
    auto adapter = SqliteAdapter::open(":memory:");
    CognizerHub hub(*adapter);
    RelationEdgeInput bad = valid_input();
    bad.fiske_weights[FiskeMode::Communal] = 0.5;  // sum now 1.1
    EXPECT_THROW(hub.upsert_relation(bad), FiskeWeightsInvalid);
}

TEST(CognizerRelations, AffinityOutOfRangeRejected) {
    auto adapter = SqliteAdapter::open(":memory:");
    CognizerHub hub(*adapter);
    RelationEdgeInput bad = valid_input();
    bad.affinity = 1.5;
    EXPECT_THROW(hub.upsert_relation(bad), std::invalid_argument);
}

TEST(CognizerRelations, UpsertSameTripletReplaces) {
    auto adapter = SqliteAdapter::open(":memory:");
    CognizerHub hub(*adapter);
    auto e1 = hub.upsert_relation(valid_input());
    auto in2 = valid_input();
    in2.affinity = 0.9;
    auto e2 = hub.upsert_relation(in2);
    EXPECT_EQ(e1.id, e2.id);   // same row replaced
    EXPECT_DOUBLE_EQ(e2.affinity, 0.9);
}

TEST(CognizerRelations, RelationsOfReturnsAllForA) {
    auto adapter = SqliteAdapter::open(":memory:");
    CognizerHub hub(*adapter);
    auto in1 = valid_input();
    auto in2 = valid_input();
    in2.b_id = "carol";
    hub.upsert_relation(in1);
    hub.upsert_relation(in2);
    auto rels = hub.relations_of("alice", "default");
    EXPECT_EQ(rels.size(), 2u);
}

TEST(CognizerRelations, FiskeWeightsRoundTrip) {
    auto adapter = SqliteAdapter::open(":memory:");
    CognizerHub hub(*adapter);
    hub.upsert_relation(valid_input());
    auto rels = hub.relations_of("alice", "default");
    ASSERT_EQ(rels.size(), 1u);
    EXPECT_NEAR(rels[0].fiske_weights.at(FiskeMode::Communal),  0.4, 1e-6);
    EXPECT_NEAR(rels[0].fiske_weights.at(FiskeMode::Authority), 0.2, 1e-6);
    EXPECT_NEAR(rels[0].fiske_weights.at(FiskeMode::Equality),  0.3, 1e-6);
    EXPECT_NEAR(rels[0].fiske_weights.at(FiskeMode::Market),    0.1, 1e-6);
}

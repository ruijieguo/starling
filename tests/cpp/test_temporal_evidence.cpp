#include "starling/retrieval/temporal_evidence.hpp"
#include <gtest/gtest.h>
#include <nlohmann/json.hpp>
#include <algorithm>
#include <limits>

using namespace starling::retrieval;
namespace {
using Json=nlohmann::json;
TemporalEvidenceCandidate candidate(std::string id, std::string session, int turn, double score=1.0) {
    StatementRow r;
    r.id=id;r.tenant_id="tenant-a";r.holder_id="Mina";r.subject_id="Mina";
    r.subject_kind="cognizer";r.predicate="feels";r.object_value="uneasy about canoeing";
    r.holder_perspective="first_person";r.modality="believes";r.polarity="pos";
    Json span={{"engram_ref","eng"},{"source_hash",std::string(64,'a')},{"span_start",0},{"span_end",10}};
    r.source_spans_json=Json::array({span}).dump();
    r.semantic_claim_json=Json{{"actor","Mina"},{"topic","canoeing"},{"source_span",span},
        {"event_time",nullptr},{"source_turn",{{"speaker","Mina"},{"session_id",session},{"turn_index",turn}}}}.dump();
    return {r,score};
}
TemporalEvidenceRequest request() {return {"tenant-a","Mina","canoeing",{"s1","s2","s3","s4"},"s3",2};}
bool contains(const TemporalEvidenceView& view,const std::string& id) {
    return std::any_of(view.selected.begin(),view.selected.end(),[&](const auto& ref){return ref.statement_id==id;});
}
}
TEST(TemporalEvidence, KeepsBothEndpointsBeforeScoreTruncationAndExcludesFuture) {
    auto req=request();
    auto view=select_temporal_evidence({candidate("early","s1",2,0.1),candidate("middle","s2",1,1.0),
        candidate("late","s3",4,0.8),candidate("future","s4",0,9.0)},req);
    ASSERT_TRUE(view.sufficient) << view.insufficiency_reason;
    ASSERT_TRUE(view.early.has_value());ASSERT_TRUE(view.late.has_value());
    EXPECT_EQ(view.early->statement_id,"early");EXPECT_EQ(view.late->statement_id,"late");
    EXPECT_EQ(view.selected.size(),2u);EXPECT_TRUE(contains(view,"early"));EXPECT_TRUE(contains(view,"late"));
    EXPECT_EQ(view.excluded_after_cutoff,1u);
}
TEST(TemporalEvidence, EnforcesTenantActorTopicAndSourceReferenceConsistency) {
    auto other_tenant=candidate("same","s1",0);other_tenant.row.tenant_id="tenant-b";
    auto other_actor=candidate("other","s1",0);other_actor.row.subject_id="Jules";
    auto other_topic=candidate("topic","s1",0);auto j=Json::parse(other_topic.row.semantic_claim_json);
    j["topic"]="rowing";other_topic.row.semantic_claim_json=j.dump();
    auto tampered=candidate("tampered","s3",2);tampered.row.source_spans_json="[]";
    auto view=select_temporal_evidence({other_tenant,other_actor,other_topic,tampered,
        candidate("same","s1",1),candidate("late","s3",1)},request());
    ASSERT_TRUE(view.sufficient);
    EXPECT_EQ(view.excluded_scope,2u);EXPECT_EQ(view.excluded_topic,1u);EXPECT_EQ(view.excluded_invalid_evidence,1u);
    EXPECT_TRUE(contains(view,"same"));EXPECT_FALSE(contains(view,"other"));
    for(const auto& ref:view.selected) EXPECT_EQ(ref.tenant_id,"tenant-a");
}
TEST(TemporalEvidence, RejectsAmbiguousRequestAndInsufficientBudgetWithoutGuessingTime) {
    for(int mode=0;mode<4;++mode) {
        auto req=request();
        if(mode==0)req.topic="";
        if(mode==1)req.ordered_session_ids.push_back("s1");
        if(mode==2)req.through_session_id="absent";
        if(mode==3)req.limit=1;
        const auto view=select_temporal_evidence({candidate("a","s1",0),candidate("b","s3",0)},req);
        EXPECT_FALSE(view.sufficient);EXPECT_FALSE(view.insufficiency_reason.empty());EXPECT_TRUE(view.selected.empty());
    }
    const auto one=select_temporal_evidence({candidate("a","s1",0),candidate("b","s1",0)},request());
    EXPECT_FALSE(one.sufficient);EXPECT_EQ(one.insufficiency_reason,"no_distinct_ordered_sources");
}
TEST(TemporalEvidence, MissingOrderIsExcludedAndOppositeStatesRemainIndependent) {
    auto missing=candidate("missing","s1",0);auto j=Json::parse(missing.row.semantic_claim_json);
    j["source_turn"]["turn_index"]=nullptr;missing.row.semantic_claim_json=j.dump();
    auto early=candidate("early","s1",0);auto late=candidate("late","s3",0);
    late.row.polarity="neg";late.row.object_value="uneasy about canoeing";
    auto view=select_temporal_evidence({missing,early,late},request());
    ASSERT_TRUE(view.sufficient);EXPECT_EQ(view.excluded_missing_order,1u);
    EXPECT_TRUE(contains(view,"early"));EXPECT_TRUE(contains(view,"late"));
    EXPECT_EQ(Json::parse(early.row.semantic_claim_json)["event_time"],nullptr);
}
TEST(TemporalEvidence, DeduplicatesByTenantAndIdAndUsesStableScoreTies) {
    auto req=request();req.limit=3;
    std::vector<TemporalEvidenceCandidate> candidates={candidate("early","s1",0,0.1),candidate("late","s3",0,0.2),
        candidate("b","s2",0,1),candidate("a","s2",0,1),candidate("a","s2",0,0.5)};
    auto first=select_temporal_evidence(candidates,req);std::reverse(candidates.begin(),candidates.end());
    auto second=select_temporal_evidence(candidates,req);
    EXPECT_EQ(temporal_evidence_json(first),temporal_evidence_json(second));
    EXPECT_TRUE(contains(first,"a"));EXPECT_FALSE(contains(first,"b"));EXPECT_EQ(first.duplicates,1u);
}

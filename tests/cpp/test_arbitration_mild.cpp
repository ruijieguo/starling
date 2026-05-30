#include "starling/reconsolidation/arbitration.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
#include <sqlite3.h>
using namespace starling::reconsolidation;
using starling::persistence::SqliteAdapter;
namespace {
void seed_consol(sqlite3* db,const std::string& id,double conf){
    std::string s="INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
    "subject_kind,subject_id,predicate,object_kind,object_value,canonical_object_hash,"
    "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
    "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
    "confidence_history_json,created_at,updated_at) VALUES('"+id+"','default','alice',"
    "'first_person','cognizer','bob','knows','str','x','"+std::string(64,'a')+"','v1',"
    "'believes','pos',"+std::to_string(conf)+",'2026-05-27T09:00:00Z',0.5,'{}',0.0,"
    "'2026-05-27T09:00:00Z','user_input','consolidated','approved','[]',"
    "'2026-05-27T09:00:00Z','2026-05-27T09:00:00Z')";
    sqlite3_exec(db,s.c_str(),nullptr,nullptr,nullptr);
}
std::string scol(sqlite3* db,const std::string& q){sqlite3_stmt* s=nullptr;
    sqlite3_prepare_v2(db,q.c_str(),-1,&s,nullptr);sqlite3_step(s);
    std::string v=reinterpret_cast<const char*>(sqlite3_column_text(s,0));sqlite3_finalize(s);return v;}
double dcol(sqlite3* db,const std::string& q){sqlite3_stmt* s=nullptr;
    sqlite3_prepare_v2(db,q.c_str(),-1,&s,nullptr);sqlite3_step(s);
    double v=sqlite3_column_double(s,0);sqlite3_finalize(s);return v;}
}
TEST(Arbitration, BayesianUpIncreases) {
    EXPECT_GT(bayesian_update_up(0.5,0.4),0.5);
    EXPECT_LE(bayesian_update_up(0.9,0.9),1.0);
}
TEST(Arbitration, BayesianDownDecreases) {
    EXPECT_LT(bayesian_update_down(0.9,0.4),0.9);
    EXPECT_GE(bayesian_update_down(0.1,0.9),0.0);
}
TEST(Arbitration, MildContradictKeepsProvenanceAppendsHistory) {
    auto a=SqliteAdapter::open(":memory:"); auto& c=a->connection();
    seed_consol(c.raw(),"s1",0.9);
    Aggregated agg{ArbitrationPath::MildContradict, 0.4, "agg-1"};
    apply_mild_contradict(c,"s1","default",agg,"2026-05-27T10:00:00Z");
    EXPECT_EQ(scol(c.raw(),"SELECT provenance FROM statements WHERE id='s1'"),"user_input");
    EXPECT_LT(dcol(c.raw(),"SELECT confidence FROM statements WHERE id='s1'"),0.9);
    std::string hist=scol(c.raw(),"SELECT confidence_history_json FROM statements WHERE id='s1'");
    EXPECT_NE(hist.find("mild_contradict"),std::string::npos);
    EXPECT_EQ(scol(c.raw(),"SELECT consolidation_state FROM statements WHERE id='s1'"),"consolidated");
    // emit statement.consolidated, NOT statement.corrected
    EXPECT_EQ(scol(c.raw(),"SELECT COUNT(*) FROM bus_events WHERE event_type='statement.consolidated' AND primary_id='s1'"),"1");
    EXPECT_EQ(scol(c.raw(),"SELECT COUNT(*) FROM bus_events WHERE event_type='statement.corrected'"),"0");
}
TEST(Arbitration, SupportsIncreasesConfidence) {
    auto a=SqliteAdapter::open(":memory:"); auto& c=a->connection();
    seed_consol(c.raw(),"s2",0.5);
    Aggregated agg{ArbitrationPath::Supports, 0.4, "agg-2"};
    apply_supports(c,"s2","default",agg,"2026-05-27T10:00:00Z");
    EXPECT_GT(dcol(c.raw(),"SELECT confidence FROM statements WHERE id='s2'"),0.5);
}

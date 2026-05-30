#include "starling/replay/consolidation_ops.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
#include <sqlite3.h>
using namespace starling::replay;
using starling::persistence::SqliteAdapter;
namespace {
void seed(sqlite3* db,const std::string& id){
    std::string s="INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
    "subject_kind,subject_id,predicate,object_kind,object_value,canonical_object_hash,"
    "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
    "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
    "access_count,created_at,updated_at) VALUES('"+id+"','default','alice','first_person',"
    "'cognizer','bob','knows','str','x','"+std::string(64,'a')+"','v1','believes','pos',"
    "0.9,'2026-05-27T09:00:00Z',0.5,'{}',0.0,'2026-05-27T09:00:00Z','user_input','volatile',"
    "'approved',2,'2026-05-27T09:00:00Z','2026-05-27T09:00:00Z')";
    sqlite3_exec(db,s.c_str(),nullptr,nullptr,nullptr);
}
int icol(sqlite3* db,const std::string& q){sqlite3_stmt* s=nullptr;
    sqlite3_prepare_v2(db,q.c_str(),-1,&s,nullptr);sqlite3_step(s);
    int v=sqlite3_column_int(s,0);sqlite3_finalize(s);return v;}
}
TEST(ConsolidationReinforce, BumpsAccessCountAndConsolidates) {
    auto a=SqliteAdapter::open(":memory:"); auto& c=a->connection();
    seed(c.raw(),"s1");
    op_reinforce(c,{"s1"},"default","b1");
    EXPECT_EQ(icol(c.raw(),"SELECT access_count FROM statements WHERE id='s1'"),3);
    EXPECT_EQ(icol(c.raw(),"SELECT COUNT(*) FROM statements WHERE id='s1' AND consolidation_state='consolidated'"),1);
}
TEST(ConsolidationAbstract, MarksBatchKeepsReviewStatus) {
    auto a=SqliteAdapter::open(":memory:"); auto& c=a->connection();
    seed(c.raw(),"s1");
    auto r=op_abstract(c,{"s1"},"default","b1");
    EXPECT_EQ(r.affected,1);
    EXPECT_EQ(icol(c.raw(),"SELECT COUNT(*) FROM statements WHERE id='s1' AND review_status='approved'"),1);
}

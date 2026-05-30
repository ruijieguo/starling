#include "starling/replay/consolidation_ops.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
#include <sqlite3.h>
using namespace starling::replay;
using starling::persistence::SqliteAdapter;
namespace {
void seed_consol(sqlite3* db,const std::string& id,const std::string& last_acc,double sal){
    std::string s="INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
    "subject_kind,subject_id,predicate,object_kind,object_value,canonical_object_hash,"
    "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
    "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
    "created_at,updated_at) VALUES('"+id+"','default','alice','first_person','cognizer',"
    "'bob','knows','str','x','"+std::string(64,'a')+"','v1','assumes','pos',0.9,"
    "'2025-01-01T00:00:00Z',"+std::to_string(sal)+",'{}',0.0,'"+last_acc+"','user_input',"
    "'consolidated','approved','2025-01-01T00:00:00Z','2025-01-01T00:00:00Z')";
    sqlite3_exec(db,s.c_str(),nullptr,nullptr,nullptr);
}
int icol(sqlite3* db,const std::string& q){sqlite3_stmt* s=nullptr;
    sqlite3_prepare_v2(db,q.c_str(),-1,&s,nullptr);sqlite3_step(s);
    int v=sqlite3_column_int(s,0);sqlite3_finalize(s);return v;}
}
TEST(ConsolidationDecay, OldLowSalienceArchived) {
    auto a=SqliteAdapter::open(":memory:"); auto& c=a->connection();
    seed_consol(c.raw(),"old","2025-01-01T00:00:00Z",0.0);
    auto r=op_decay(c,{"old"},"default","2026-05-27T00:00:00Z");
    EXPECT_EQ(r.affected,1);
    EXPECT_EQ(icol(c.raw(),"SELECT COUNT(*) FROM statements WHERE id='old' AND consolidation_state='archived'"),1);
}
TEST(ConsolidationDecay, FreshNotArchived) {
    auto a=SqliteAdapter::open(":memory:"); auto& c=a->connection();
    seed_consol(c.raw(),"fresh","2026-05-27T09:59:00Z",0.9);
    auto r=op_decay(c,{"fresh"},"default","2026-05-27T10:00:00Z");
    EXPECT_EQ(r.affected,0);
}
TEST(ConsolidationDecay, SerialGuardSkipsAlreadyArchived) {
    auto a=SqliteAdapter::open(":memory:"); auto& c=a->connection();
    seed_consol(c.raw(),"old","2025-01-01T00:00:00Z",0.0);
    op_decay(c,{"old"},"default","2026-05-27T00:00:00Z");
    auto r2=op_decay(c,{"old"},"default","2026-05-27T00:00:00Z");
    EXPECT_EQ(r2.affected,0);
}

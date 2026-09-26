#include <gtest/gtest.h>
#include <nlohmann/json.hpp>
#include <sqlite3.h>
#include "starling/extractor/extractor.hpp"
#include "starling/memory/memory_ops.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

using namespace starling;
using namespace starling::extractor;
namespace {
using Json = nlohmann::json;
const std::string source = "Mina: I feel sad about leaving.\nMina: I feel happy about arriving.\nMina: I feel calm about staying.";
// Feature detection lets RED exercise the old binary behavior before the new
// policy member exists; absence is itself an explicit failed assertion.
template<class P> void batch(P& p, int n) {
    if constexpr (requires { p.claim_batch_size; }) p.claim_batch_size = n;
    else ADD_FAILURE() << "native claim_batch_size policy missing";
}
ValidationPolicy policy(int size = 1) {
    ValidationPolicy p; p.semantic_claim_contract = true; p.preserve_text_objects = true;
    batch(p, size); return p;
}
Json row(int clause) {
    const std::vector<std::string> objects{"sad about leaving", "happy about arriving", "calm about staying"};
    return {{"holder","Mina"},{"holder_perspective","FIRST_PERSON"},{"subject","Mina"},
        {"subject_kind","cognizer"},{"predicate","feels"},{"object",objects.at(static_cast<size_t>(clause))},
        {"modality","BELIEVES"},{"polarity","POS"},{"nesting_depth",0},
        {"evidence",{{"clause_id","c"+std::to_string(clause)},{"actor","Mina"},
            {"assertion_scope","ASSERTED"},{"scope_markers",Json::array({"ASSERTED"})},
            {"time_text",""},{"event_time",nullptr}}}};
}
std::string envelope(Json rows) { return Json{{"schema_version",2},{"statements",rows}}.dump(); }
LLMResponse response(std::string raw) {
    LLMResponse r; r.ok = true; r.raw_xml = std::move(raw);
    r.prompt_tokens=2; r.completion_tokens=3; r.total_tokens=5; return r;
}
LLMResponse claim(int n) { return response(envelope(Json::array({row(n)}))); }
LLMResponse empty() { return response(envelope(Json::array())); }
LLMResponse admit() { return response(R"({"schema_version":1,"decisions":[{"index":0,"retain":true,"reason":"supported"}]})"); }
struct Sequence : LLMAdapter {
    std::vector<LLMResponse> responses;
    std::vector<std::string> prompts;
    LLMResponse extract(std::string_view prompt, std::string_view) override {
        prompts.emplace_back(prompt);
        if (prompts.size() > responses.size()) return {.raw_xml="",.ok=false,.error="unexpected request"};
        return responses[prompts.size()-1];
    }
};
memoryops::RememberParams params(const std::string& text=source) {
    memoryops::RememberParams p; p.holder_id="Mina"; p.tenant_id="default";
    p.adapter_name="batch-test"; p.source_prefix="batch-test"; p.created_at_iso8601="2099-01-01T00:00:00Z";
    p.payload.assign(text.begin(),text.end()); return p;
}
int scalar(persistence::SqliteAdapter& db, const char* sql) {
    sqlite3_stmt* stmt=nullptr;
    if(sqlite3_prepare_v2(db.connection().raw(),sql,-1,&stmt,nullptr)!=SQLITE_OK) {
        ADD_FAILURE() << sqlite3_errmsg(db.connection().raw()); return -1;
    }
    int value=-1; if(sqlite3_step(stmt)==SQLITE_ROW) value=sqlite3_column_int(stmt,0);
    sqlite3_finalize(stmt); return value;
}
template<class R> void alter_plan(R& r) {
    if constexpr (requires { r.claim_batch_plan; }) r.claim_batch_plan="{}";
    else ADD_FAILURE() << "native batch plan missing";
}
}

TEST(ClaimBatching, DefaultZeroPreservesLegacyContractPromptAndRequestCount) {
    auto db=persistence::SqliteAdapter::open(":memory:"); Sequence llm; llm.responses={empty()};
    Extractor ex(db->connection(),llm,"",policy(0));
    auto result=ex.extract_llm(params().payload,"Mina",{});
    ASSERT_EQ(llm.prompts.size(),1u);
    EXPECT_EQ(llm.prompts[0],claim_extraction_prompt(source,"Mina"));
    EXPECT_FALSE(Json::parse(claim_extraction_receipt(result)).contains("claim_batch_size"));
}
TEST(ClaimBatching, NativePolicyBoundariesAndSemanticChannelRequirement) {
    for(int n : {-1,33}) { auto p=policy(1); batch(p,n); EXPECT_THROW(p.validate(),std::invalid_argument); }
    for(int n : {0,1,8,32}) { auto p=policy(n); EXPECT_NO_THROW(p.validate()); }
    ValidationPolicy p; batch(p,1); EXPECT_THROW(p.validate(),std::invalid_argument);
}
TEST(ClaimBatching, CompleteContextGlobalEvidenceAllBatchesAndReplayCosts) {
    auto db=persistence::SqliteAdapter::open(":memory:"); auto input=params();
    auto prepared=memoryops::remember_prepare(*db,input);
    Sequence llm; llm.responses={claim(0),admit(),claim(1),admit(),claim(2),admit()};
    Extractor ex(db->connection(),llm,"",policy());
    const auto result=ex.extract_llm(input.payload,"Mina",{});
    ASSERT_EQ(llm.prompts.size(),6u); ASSERT_EQ(result.attempts.size(),3u);
    auto receipt=Json::parse(claim_extraction_receipt(result));
    EXPECT_EQ(receipt["claim_batch_plan"]["belief_request_upper_bound"],6);
    for(size_t i=0;i<3;++i) {
        EXPECT_NE(llm.prompts[i*2].find("calm about staying"),std::string::npos);
        EXPECT_NE(llm.prompts[i*2].find("sad about leaving"),std::string::npos);
        EXPECT_EQ(receipt["attempts"][i]["batch_index"],i);
        EXPECT_EQ(receipt["attempts"][i]["target_clause_ids"],Json::array({"c"+std::to_string(i)}));
        EXPECT_EQ(result.attempts[i].attempt,static_cast<int>(i)+1);
    }
    auto stored=ex.persist(prepared.engram_ref,"Mina","default","",result);
    EXPECT_EQ(stored.status,ExtractionRunResult::Status::SUCCESS);
    EXPECT_EQ(stored.accepted_statement_ids.size(),3u);
    EXPECT_EQ(scalar(*db,"SELECT count(*) FROM statements"),3);
    EXPECT_EQ(scalar(*db,"SELECT sum(total_tokens) FROM extraction_attempt"),30);
    auto replay=ex.persist(prepared.engram_ref,"Mina","default","",result);
    EXPECT_EQ(replay.status,ExtractionRunResult::Status::SUCCESS);
    EXPECT_EQ(scalar(*db,"SELECT count(*) FROM statements"),3);
    EXPECT_EQ(scalar(*db,"SELECT sum(total_tokens) FROM extraction_attempt"),60);
}
TEST(ClaimBatching, LegalEmptyBatchAndSemanticRejectionContinueToLaterBatch) {
    auto db=persistence::SqliteAdapter::open(":memory:"); Sequence llm;
    auto rejected=row(1); rejected["holder"]="Other";
    llm.responses={empty(),response(envelope(Json::array({rejected}))),claim(2),admit()};
    Extractor ex(db->connection(),llm,"",policy()); auto r=ex.extract_llm(params().payload,"Mina",{});
    ASSERT_EQ(llm.prompts.size(),4u); ASSERT_EQ(r.attempts.size(),3u);
    EXPECT_TRUE(r.attempts[0].terminal); EXPECT_TRUE(r.attempts[1].terminal);
    EXPECT_EQ(r.accepted_by_predicate.at("feels"),1u);
}
TEST(ClaimBatching, EmptySourceHasOneEmptyTargetBatch) {
    auto db=persistence::SqliteAdapter::open(":memory:"); Sequence llm; llm.responses={empty()};
    Extractor ex(db->connection(),llm,"",policy()); auto r=ex.extract_llm({},"Mina",{});
    ASSERT_EQ(llm.prompts.size(),1u); EXPECT_TRUE(r.attempts.front().terminal);
    auto receipt=Json::parse(claim_extraction_receipt(r));
    ASSERT_TRUE(receipt.contains("claim_batch_plan"));
    EXPECT_EQ(receipt["claim_batch_plan"]["batches"].size(),1u);
    EXPECT_EQ(receipt["attempts"][0]["target_clause_ids"],Json::array());
}
TEST(ClaimBatching, OutOfBatchWireRowFailsBeforeSemanticFilterWithoutRetryOrAdmission) {
    auto db=persistence::SqliteAdapter::open(":memory:"); Sequence llm;
    auto outside=row(1); outside["holder"]="Other";
    llm.responses={response(envelope(Json::array({row(0),outside})))};
    auto p=policy(); p.claim_protocol_retry_budget=1;
    Extractor ex(db->connection(),llm,"",p); auto r=ex.extract_llm(params().payload,"Mina",{});
    EXPECT_EQ(llm.prompts.size(),1u); EXPECT_EQ(r.failure_category,"batch_scope_failure");
    EXPECT_TRUE(r.accepted_by_predicate.empty()); EXPECT_FALSE(r.attempts[0].admission_called);
    EXPECT_TRUE(r.attempts[0].semantic_rejections.empty());
}
TEST(ClaimBatching, ProtocolRetryStateIsPerBatchWithGlobalAttemptNumbers) {
    auto db=persistence::SqliteAdapter::open(":memory:"); Sequence llm;
    llm.responses={response("{} {}"),empty(),response("{} {}"),empty(),empty()};
    auto p=policy(); p.claim_protocol_retry_budget=1;
    Extractor ex(db->connection(),llm,"",p); auto r=ex.extract_llm(params().payload,"Mina",{});
    ASSERT_EQ(r.attempts.size(),5u); ASSERT_EQ(llm.prompts.size(),5u);
    EXPECT_EQ(r.failure_category,"");
    for(size_t i=0;i<5;++i) EXPECT_EQ(r.attempts[i].attempt,static_cast<int>(i)+1);
    auto receipt=Json::parse(claim_extraction_receipt(r));
    EXPECT_EQ(receipt["attempts"][2]["batch_index"],1);
    EXPECT_EQ(receipt["claim_batch_plan"]["belief_request_upper_bound"],9);
    EXPECT_NE(llm.prompts[0],llm.prompts[1]); EXPECT_NE(llm.prompts[2],llm.prompts[3]);
    EXPECT_EQ(llm.prompts[0].find("PROTOCOL_CORRECTION"),std::string::npos);
    EXPECT_EQ(llm.prompts[2].find("PROTOCOL_CORRECTION"),std::string::npos);
    EXPECT_NE(llm.prompts[1].find("PROTOCOL_CORRECTION"),std::string::npos);
    EXPECT_NE(llm.prompts[3].find("PROTOCOL_CORRECTION"),std::string::npos);
}
TEST(ClaimBatching, LaterFailureStopsRequestsAndPersistsZeroClaimsButAllCosts) {
    for(int kind=0;kind<3;++kind) {
        auto db=persistence::SqliteAdapter::open(":memory:"); auto input=params();
        auto prepared=memoryops::remember_prepare(*db,input); Sequence llm;
        llm.responses={claim(0),admit()};
        if(kind==0) { auto failed=response(""); failed.ok=false; failed.error="request timed out"; llm.responses.push_back(failed); }
        if(kind==1) llm.responses.push_back(response("{\"schema_version\":2,\"statements\":["));
        if(kind==2) { llm.responses.push_back(claim(1)); llm.responses.push_back(response("{}")); }
        Extractor ex(db->connection(),llm,"",policy()); auto r=ex.extract_llm(input.payload,"Mina",{});
        EXPECT_EQ(llm.prompts.size(),kind==2 ? 4u : 3u); EXPECT_EQ(r.attempts.size(),2u);
        EXPECT_FALSE(r.failure_category.empty()); EXPECT_TRUE(r.accepted_by_predicate.empty());
        EXPECT_FALSE(r.attempts[0].parse.statements.empty());
        auto stored=ex.persist(prepared.engram_ref,"Mina","default","",r);
        EXPECT_EQ(stored.status,ExtractionRunResult::Status::FAILED);
        EXPECT_EQ(scalar(*db,"SELECT count(*) FROM statements"),0);
        EXPECT_EQ(scalar(*db,"SELECT sum(total_tokens) FROM extraction_attempt"),kind==2 ? 20 : 15);
    }
}
TEST(ClaimBatching, PersistRejectsMissingDuplicatePlanPolicyAndSourceDriftWithoutLosingCosts) {
    for(int kind=0;kind<6;++kind) {
        auto db=persistence::SqliteAdapter::open(":memory:"); auto input=params();
        auto prepared=memoryops::remember_prepare(*db,input); Sequence llm;
        llm.responses={claim(0),admit(),claim(1),admit(),claim(2),admit()};
        auto p=policy(); Extractor ex(db->connection(),llm,"",p);
        auto r=ex.extract_llm(input.payload,"Mina",{}); ASSERT_EQ(r.attempts.size(),3u);
        if(kind==0) r.attempts.pop_back();
        if(kind==1) r.attempts.push_back(r.attempts.back());
        if(kind==2) alter_plan(r);
        if(kind==3) batch(p,2);
        if(kind==4) r.source_payload+="changed";
        if(kind==5) r.attempts[1].attempt=99;
        Extractor persister(db->connection(),llm,"",p);
        const auto stored=persister.persist(prepared.engram_ref,"Mina","default","",r);
        EXPECT_EQ(stored.status,ExtractionRunResult::Status::FAILED);
        EXPECT_EQ(scalar(*db,"SELECT count(*) FROM statements"),0);
        EXPECT_EQ(scalar(*db,"SELECT sum(total_tokens) FROM extraction_attempt"),static_cast<int>(r.attempts.size())*10);
    }
}
TEST(ClaimBatching, GeneralFactAndEpisodicPoliciesStayIndependent) {
    auto db=persistence::SqliteAdapter::open(":memory:"); Sequence llm;
    llm.responses={empty(),empty(),empty(),response("[]"),response(R"({"events":[]})")};
    memoryops::RememberPrompts prompts;
    auto input=params(); auto prepared=memoryops::remember_prepare(*db,input);
    auto bundle=memoryops::remember_extract_all(*db,llm,input,prompts,policy());
    EXPECT_FALSE(bundle.general_fact.semantic_claim_contract);
    EXPECT_EQ(llm.prompts.size(),5u);
    EXPECT_NO_THROW(memoryops::remember_commit_all(*db,llm,input,prepared,bundle,policy()));
}

TEST(ClaimBatching, LaterSemanticRejectionIsReportedAcrossCompleteBatches) {
    auto db=persistence::SqliteAdapter::open(":memory:"); Sequence llm;
    auto rejected=row(2); rejected["holder"]="Other";
    llm.responses={empty(),empty(),response(envelope(Json::array({rejected})))};
    Extractor ex(db->connection(),llm,"",policy());
    auto r=ex.extract_llm(params().payload,"Mina",{});
    EXPECT_EQ(r.failure_category,"semantic_rejection");
    EXPECT_TRUE(Json::parse(claim_extraction_receipt(r))["claim_batches_complete"]);
}
TEST(ClaimBatching, CommitRetainsOriginalTechnicalFailureCategory) {
    auto db=persistence::SqliteAdapter::open(":memory:"); auto input=params();
    auto prepared=memoryops::remember_prepare(*db,input); Sequence llm;
    llm.responses={claim(0),admit(),{.raw_xml="",.ok=false,.error="request timed out"}};
    auto p=policy(); Extractor ex(db->connection(),llm,"",p);
    auto extracted=ex.extract_llm(input.payload,"Mina",{});
    auto committed=memoryops::remember_commit(*db,llm,input,prepared,extracted,p);
    EXPECT_TRUE(committed.extraction_failed);
    EXPECT_EQ(committed.failure_category,"timeout");
    EXPECT_TRUE(extracted.persistence_error.empty());
    EXPECT_EQ(scalar(*db,"SELECT count(*) FROM statements"),0);
}
TEST(ClaimBatching, LaterWriteExceptionRollsBackAllClaims) {
    auto db=persistence::SqliteAdapter::open(":memory:"); auto input=params();
    auto prepared=memoryops::remember_prepare(*db,input); Sequence llm;
    llm.responses={claim(0),admit(),claim(1),admit(),claim(2),admit()};
    Extractor ex(db->connection(),llm,"",policy()); auto r=ex.extract_llm(input.payload,"Mina",{});
    ASSERT_EQ(sqlite3_exec(db->connection().raw(),
        "CREATE TRIGGER fail_later_claim BEFORE INSERT ON statements WHEN NEW.object_value LIKE '%happy%' BEGIN SELECT RAISE(ABORT,'later batch write failure'); END",
        nullptr,nullptr,nullptr),SQLITE_OK);
    EXPECT_THROW(ex.persist(prepared.engram_ref,"Mina","default","",r),std::exception);
    EXPECT_EQ(scalar(*db,"SELECT count(*) FROM statements"),0);
    EXPECT_EQ(scalar(*db,"SELECT count(*) FROM extraction_attempt"),0);
    EXPECT_NE(r.persistence_error.find("later batch write failure"),std::string::npos);
}
TEST(ClaimBatching, ChangingBatchSizePreservesClaimIdentity) {
    auto db=persistence::SqliteAdapter::open(":memory:"); auto input=params();
    auto prepared=memoryops::remember_prepare(*db,input); Sequence llm;
    llm.responses={claim(0),admit(),claim(1),admit(),claim(2),admit()};
    Extractor ex(db->connection(),llm,"",policy()); auto r=ex.extract_llm(input.payload,"Mina",{});
    ASSERT_EQ(ex.persist(prepared.engram_ref,"Mina","default","",r).accepted_statement_ids.size(),3u);
    Sequence second;
    second.responses={response(envelope(Json::array({row(0),row(1)}))),
        response(R"({"schema_version":1,"decisions":[{"index":0,"retain":true,"reason":"supported"},{"index":1,"retain":true,"reason":"supported"}]})"),claim(2),admit()};
    Extractor regrouped(db->connection(),second,"",policy(2));
    auto r2=regrouped.extract_llm(input.payload,"Mina",{});
    EXPECT_EQ(regrouped.persist(prepared.engram_ref,"Mina","default","",r2).status,ExtractionRunResult::Status::SUCCESS);
    EXPECT_EQ(scalar(*db,"SELECT count(*) FROM statements"),3);
    EXPECT_EQ(scalar(*db,"SELECT sum(total_tokens) FROM extraction_attempt"),50);
}
TEST(ClaimBatching, ExplicitTruncationIsNotProtocolRetried) {
    auto db=persistence::SqliteAdapter::open(":memory:"); Sequence llm;
    auto cut=response("{\"schema_version\":2,"); cut.finish_reason="length";
    llm.responses={empty(),cut}; auto p=policy(); p.claim_protocol_retry_budget=1;
    Extractor ex(db->connection(),llm,"",p); auto r=ex.extract_llm(params().payload,"Mina",{});
    EXPECT_EQ(llm.prompts.size(),2u); EXPECT_EQ(r.failure_category,"truncation_failure");
    EXPECT_TRUE(r.accepted_by_predicate.empty());
}

namespace {
class ClaimBatchingStatementTamper : public ::testing::TestWithParam<const char*> {};
}
TEST_P(ClaimBatchingStatementTamper, RejectsEveryChangedStoredFieldAndPreservesCosts) {
    auto db=persistence::SqliteAdapter::open(":memory:"); auto input=params();
    auto prepared=memoryops::remember_prepare(*db,input); Sequence llm;
    llm.responses={claim(0),admit(),claim(1),admit(),claim(2),admit()};
    auto p=policy(); Extractor ex(db->connection(),llm,"",p);
    auto extracted=ex.extract_llm(input.payload,"Mina",{});
    ASSERT_TRUE(claim_batch_integrity(extracted).complete);
    auto& stmt=extracted.attempts[0].parse.statements[0];
    const std::string field=GetParam();
    if(field=="scope_parties") stmt.scope_parties={"Mina","Outsider"};
    else if(field=="perceived_by") stmt.perceived_by={"Outsider"};
    else if(field=="valid_from") stmt.valid_from="2200-01-01T00:00:00Z";
    else if(field=="valid_to") stmt.valid_to="2201-01-01T00:00:00Z";
    else if(field=="event_time_start") stmt.event_time_start="2200-01-01T00:00:00Z";
    else if(field=="canonical_object_hash") stmt.canonical_object_hash="changed-hash";
    else if(field=="derived_from") stmt.derived_from={"fabricated-parent"};
    else if(field=="provenance_protocol_id") stmt.provenance_protocol_id="fabricated-protocol";
    else if(field=="source_hash") stmt.source_hash="changed-source-hash";
    else if(field=="holder_tenant_id") stmt.holder_tenant_id="Outsider";
    else if(field=="observed_at") stmt.observed_at="2200-01-01T00:00:00Z";
    else if(field=="chunk_index") stmt.chunk_index=99;
    else if(field=="llm_nesting_depth") stmt.llm_nesting_depth=2;
    else if(field=="llm_cognizer_kind") stmt.llm_cognizer_kind="group";
    else FAIL() << "unknown test field " << field;
    EXPECT_FALSE(claim_batch_integrity(extracted).complete);
    const auto committed=memoryops::remember_commit(*db,llm,input,prepared,extracted,p);
    EXPECT_TRUE(committed.extraction_failed);
    EXPECT_EQ(committed.failure_category,"persistence_failure");
    EXPECT_EQ(scalar(*db,"SELECT count(*) FROM statements"),0);
    EXPECT_EQ(scalar(*db,"SELECT sum(total_tokens) FROM extraction_attempt"),30);
}
INSTANTIATE_TEST_SUITE_P(StoredFields,ClaimBatchingStatementTamper,
    ::testing::Values("scope_parties","perceived_by","valid_from","valid_to","event_time_start",
        "canonical_object_hash","derived_from","provenance_protocol_id","source_hash",
        "holder_tenant_id","observed_at","chunk_index","llm_nesting_depth","llm_cognizer_kind"));

TEST(ClaimBatching, InvalidSourceBeforePlanningRetainsOriginalFailureAndZeroRequests) {
    for(const auto& source_text : {std::string("@starling/source-turn-v1 {}"),std::string("Mina: ")+char(0xff)}) {
        auto db=persistence::SqliteAdapter::open(":memory:"); auto input=params(source_text);
        auto prepared=memoryops::remember_prepare(*db,input); Sequence llm;
        auto p=policy(); auto extracted=memoryops::extract_llm(*db,llm,"",input,p);
        ASSERT_TRUE(llm.prompts.empty());
        EXPECT_EQ(extracted.failure_category,"scope_failure");
        EXPECT_FALSE(extracted.failure_detail.empty());
        EXPECT_TRUE(extracted.claim_batch_plan.empty());
        const auto integrity=claim_batch_integrity(extracted);
        EXPECT_FALSE(integrity.complete);
        EXPECT_TRUE(integrity.extraction_failed);
        const auto receipt_before=Json::parse(claim_extraction_receipt(extracted));
        auto committed=memoryops::remember_commit(*db,llm,input,prepared,extracted,p);
        EXPECT_TRUE(committed.extraction_failed);
        EXPECT_EQ(committed.failure_category,"scope_failure");
        EXPECT_EQ(committed.failure_detail,extracted.failure_detail);
        EXPECT_TRUE(extracted.persistence_error.empty());
        EXPECT_EQ(Json::parse(claim_extraction_receipt(extracted)),receipt_before);
        EXPECT_TRUE(llm.prompts.empty());
        EXPECT_EQ(scalar(*db,"SELECT count(*) FROM statements"),0);
        EXPECT_EQ(scalar(*db,"SELECT sum(total_tokens) FROM extraction_attempt"),0);
    }
}
TEST(ClaimBatching, ValidSourceMissingPlanCannotMasqueradeAsSourceValidationFailure) {
    auto db=persistence::SqliteAdapter::open(":memory:"); auto input=params();
    auto prepared=memoryops::remember_prepare(*db,input); Sequence llm;
    llm.responses={empty(),empty(),empty()}; auto p=policy();
    auto extracted=memoryops::extract_llm(*db,llm,"",input,p);
    extracted.claim_batch_plan.clear();
    const auto integrity=claim_batch_integrity(extracted);
    EXPECT_FALSE(integrity.complete); EXPECT_FALSE(integrity.extraction_failed);
    const auto committed=memoryops::remember_commit(*db,llm,input,prepared,extracted,p);
    EXPECT_TRUE(committed.extraction_failed);
    EXPECT_EQ(committed.failure_category,"persistence_failure");
    EXPECT_EQ(scalar(*db,"SELECT count(*) FROM statements"),0);
    EXPECT_EQ(scalar(*db,"SELECT sum(total_tokens) FROM extraction_attempt"),15);
}

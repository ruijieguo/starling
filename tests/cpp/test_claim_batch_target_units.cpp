#include <gtest/gtest.h>
#include <nlohmann/json.hpp>
#include <sqlite3.h>
#include "starling/crypto/sha256.hpp"
#include "starling/extractor/extractor.hpp"
#include "starling/memory/memory_ops.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

using namespace starling;
using namespace starling::extractor;
namespace {
using Json=nlohmann::json;
using OrderedJson=nlohmann::ordered_json;
const std::string source="Mina: I feel sad about leaving.\nMina: I feel happy about arriving.\nMina: I feel calm about staying.";
template<class P> void target_units(P& p,bool value=true) {
    if constexpr(requires {p.claim_batch_target_units;}) p.claim_batch_target_units=value;
    else ADD_FAILURE()<<"native claim_batch_target_units policy missing";
}
template<class P> bool enabled(const P& p) {
    if constexpr(requires {p.claim_batch_target_units;}) return p.claim_batch_target_units;
    else {ADD_FAILURE()<<"native claim_batch_target_units policy missing";return false;}
}
ValidationPolicy policy(bool target=true,int size=1) {
    ValidationPolicy p;p.semantic_claim_contract=p.preserve_text_objects=true;
    p.claim_batch_size=size;target_units(p,target);return p;
}
template<class P> std::string prompt(std::string_view payload,std::string_view holder,int index,
        const std::vector<std::string>& targets,const P& p,const std::vector<ParseError>* errors=nullptr) {
    if constexpr(requires {claim_extraction_batch_prompt(payload,holder,index,targets,p,errors);})
        return claim_extraction_batch_prompt(payload,holder,index,targets,p,errors);
    else {ADD_FAILURE()<<"native target-unit prompt function missing";return "";}
}
Json source_data(const std::string& body) {
    const std::string marker="\nSOURCE_DATA_JSON:\n";const auto pos=body.find(marker);
    if(pos==std::string::npos){ADD_FAILURE()<<"missing native source data";return Json::object();}
    const auto start=pos+marker.size();return Json::parse(body.substr(start,body.find('\n',start)-start));
}
std::string reference_examples_bytes(const std::string& body) {
    const std::string marker="\nREFERENCE_EXAMPLES_JSON:\n";
    const auto start=body.find(marker);
    EXPECT_NE(start,std::string::npos);
    if(start==std::string::npos)return {};
    const auto begin=start+marker.size();
    const auto end=body.find("\nSOURCE_DATA_JSON:\n",begin);
    EXPECT_NE(end,std::string::npos);
    if(end==std::string::npos)return {};
    return body.substr(begin,end-begin);
}
std::vector<std::string> object_keys(const OrderedJson& value) {
    std::vector<std::string> keys;
    for(const auto& item:value.items())keys.push_back(item.key());
    return keys;
}
Json row(int clause) {
    const std::vector<std::string> objects{"sad about leaving","happy about arriving","calm about staying"};
    return {{"holder","Mina"},{"holder_perspective","FIRST_PERSON"},{"subject","Mina"},
        {"subject_kind","cognizer"},{"predicate","feels"},{"object",objects.at(static_cast<size_t>(clause))},
        {"modality","BELIEVES"},{"polarity","POS"},{"nesting_depth",0},
        {"evidence",{{"clause_id","c"+std::to_string(clause)},{"actor","Mina"},{"assertion_scope","ASSERTED"},
            {"scope_markers",Json::array({"ASSERTED"})},{"time_text",""},{"event_time",nullptr}}}};
}
LLMResponse response(std::string raw) {
    LLMResponse r;r.ok=true;r.raw_xml=std::move(raw);r.prompt_tokens=2;r.completion_tokens=3;r.total_tokens=5;return r;
}
LLMResponse claims(Json rows) {return response(Json{{"schema_version",2},{"statements",rows}}.dump());}
LLMResponse claim(int n) {return claims(Json::array({row(n)}));}
LLMResponse empty() {return claims(Json::array());}
LLMResponse admit(int count=1) {
    Json decisions=Json::array();for(int i=0;i<count;++i)decisions.push_back({{"index",i},{"retain",true},{"reason","supported"}});
    return response(Json{{"schema_version",1},{"decisions",decisions}}.dump());
}
struct Sequence:LLMAdapter {
    std::vector<LLMResponse> responses;std::vector<std::string> prompts;
    LLMResponse extract(std::string_view p,std::string_view) override {
        prompts.emplace_back(p);
        if(prompts.size()>responses.size())return {.raw_xml="",.ok=false,.error="unexpected request"};
        return responses[prompts.size()-1];
    }
};
memoryops::RememberParams params(const std::string& payload=source) {
    memoryops::RememberParams p;p.holder_id="Mina";p.tenant_id="default";
    p.adapter_name="target-units-test";p.source_prefix="target-units-test";p.created_at_iso8601="2099-01-01T00:00:00Z";
    p.payload.assign(payload.begin(),payload.end());return p;
}
int scalar(persistence::SqliteAdapter& db,const char* sql) {
    sqlite3_stmt* s=nullptr;
    if(sqlite3_prepare_v2(db.connection().raw(),sql,-1,&s,nullptr)!=SQLITE_OK){ADD_FAILURE()<<sqlite3_errmsg(db.connection().raw());return -1;}
    int result=-1;if(sqlite3_step(s)==SQLITE_ROW)result=sqlite3_column_int(s,0);sqlite3_finalize(s);return result;
}
}

TEST(ClaimBatchTargetUnits, FalseRetainsHistoricalPromptRetryPlanAndReceiptShape) {
    ValidationPolicy defaults;EXPECT_FALSE(enabled(defaults));auto p=policy(false);p.claim_protocol_retry_budget=1;
    // Recorded against the frozen R56 4c5a7c39 core before modifying production code.
    // The prompt pins below were re-recorded on purpose on 2026-10-05, when the final format check gained
    // the NEG/NEGATED reminder line. The batch-plan pin is unchanged.
    EXPECT_EQ(crypto::sha256_hex(claim_extraction_prompt(source,"Mina")),"f0736f29fd8c5eebce36b9fedfd150255c936e145d4eca47162806f1fbd9852f");
    EXPECT_EQ(crypto::sha256_hex(claim_extraction_batch_plan(source,p)),"38691044ca106deee345d1dad67cd0680caf7fb52e91df6de5e2c987d4c9e092");
    auto db=persistence::SqliteAdapter::open(":memory:");Sequence llm;llm.responses={response("{}"),empty(),empty(),empty()};
    Extractor ex(db->connection(),llm,"",p);auto r=ex.extract_llm(params().payload,"Mina",{});
    ASSERT_EQ(llm.prompts.size(),4u);
    EXPECT_EQ(crypto::sha256_hex(llm.prompts[0]),"7206e5322308a96515aacc63d7bfbbf862eb6806704322b028dc4cb377a56f2c");
    EXPECT_EQ(crypto::sha256_hex(llm.prompts[1]),"33b270e40d473e22a053c6eebe6cabc19532c9637acc70edc99a8e9a2da247c1");
    const auto receipt=Json::parse(claim_extraction_receipt(r));
    EXPECT_EQ(receipt.size(),19u);EXPECT_FALSE(receipt.contains("claim_batch_prompt_profile"));
    EXPECT_EQ(receipt.at("claim_batch_plan").size(),6u);EXPECT_EQ(receipt.at("claim_batch_plan").at("belief_request_upper_bound"),9);
    EXPECT_TRUE(receipt.at("claim_batches_complete"));
}
TEST(ClaimBatchTargetUnits, InvalidPolicyFailsBeforeAnyProviderCall) {
    for(int kind=0;kind<2;++kind) {
        auto p=policy(true);if(kind==0)p.claim_batch_size=0;else p.semantic_claim_contract=false;
        EXPECT_THROW(p.validate(),std::invalid_argument);
        auto db=persistence::SqliteAdapter::open(":memory:");Sequence llm;Extractor ex(db->connection(),llm,"",p);
        EXPECT_THROW(ex.extract_llm(params().payload,"Mina",{}),std::invalid_argument);EXPECT_TRUE(llm.prompts.empty());
    }
    EXPECT_NO_THROW(policy(true,8).validate());
    EXPECT_NO_THROW(policy(false,0).validate());
}
TEST(ClaimBatchTargetUnits, ThreeBatchesRetainFullUtf8ContextAndGlobalSourceTurnIdentity) {
    Json turns=Json::array();
    for(int i=0;i<19;++i)turns.push_back({{"speaker","Mina"},{"text","我很伤心。 c8 is literal context "+std::to_string(i)},
        {"turn_id","turn-"+std::to_string(i)},{"turn_index",i+7},{"session_id","s"},{"observed_at","2025-05-05T11:04:00Z"}});
    const auto payload=claim_source_turn_payload(turns.dump());const auto units=Json::parse(claim_source_units(payload));
    auto p=policy(true,8);const auto plan=Json::parse(claim_extraction_batch_plan(payload,p));
    ASSERT_TRUE(plan.contains("claim_batch_prompt_profile"));EXPECT_EQ(plan.at("claim_batch_prompt_profile"),"target_units_statement_first_v1");
    EXPECT_EQ(plan.at("source_units"),units);ASSERT_EQ(plan.at("batches").size(),3u);
    for(int index=0;index<3;++index) {
        const auto targets=plan.at("batches")[static_cast<size_t>(index)].at("target_clause_ids").get<std::vector<std::string>>();
        const auto body=prompt(payload,"Mina",index,targets,p);const auto data=source_data(body);
        ASSERT_TRUE(data.contains("source_units"));EXPECT_EQ(data.at("source"),payload);EXPECT_EQ(data.at("source_holder"),"Mina");
        EXPECT_EQ(data.at("source_role"),"context_only");EXPECT_EQ(data.at("batch_index"),index);EXPECT_EQ(data.at("target_clause_ids"),targets);
        EXPECT_EQ(data.at("source_units").size(),index==2?3u:8u);
        for(size_t j=0;j<targets.size();++j) {
            const auto& unit=data.at("source_units")[j];EXPECT_EQ(unit,units.at(static_cast<size_t>(index*8)+j));
            EXPECT_EQ(unit.at("clause_id"),targets[j]);
            EXPECT_EQ(payload.substr(unit.at("byte_start").get<size_t>(),unit.at("byte_end").get<size_t>()-unit.at("byte_start").get<size_t>()),unit.at("text").get<std::string>());
        }
        EXPECT_EQ(body.find("Review every source unit"),std::string::npos);
    }
}
TEST(ClaimBatchTargetUnits, TargetPromptUsesStatementFirstReferenceLayoutWithoutChangingValues) {
    auto p=policy();
    const auto target=prompt(source,"Mina",0,{"c0"},p);
    const auto legacy=claim_extraction_prompt(source,"Mina");
    const auto ref_marker="\nREFERENCE_EXAMPLES_JSON:\n";
    const auto ref_start=target.find(ref_marker);
    const auto ref_begin=ref_start+std::string(ref_marker).size();
    const auto ref_end=target.find("\nSOURCE_DATA_JSON:\n",ref_begin);
    EXPECT_EQ(crypto::sha256_hex(target.substr(0,ref_begin)),
              "f1a6e1735a4b007d92ef084349578b3215413b2acdff6c3e5c97a3908a6b5421");
    EXPECT_EQ(crypto::sha256_hex(target.substr(ref_end)),
              "6ac1b1efa81366ebc69e0d200e183dc7614e8cb8be1062fcc3fc36f255625d7c");
    const auto target_examples=OrderedJson::parse(reference_examples_bytes(target));
    const auto legacy_examples=OrderedJson::parse(reference_examples_bytes(legacy));
    ASSERT_TRUE(target_examples.is_array());ASSERT_EQ(target_examples.size(),15u);
    ASSERT_EQ(Json::parse(target_examples.dump()),Json::parse(legacy_examples.dump()));
    const std::vector<std::string> expected={"holder","holder_perspective","subject","subject_kind",
        "predicate","object","modality","polarity","nesting_depth","confidence","evidence"};
    for(const auto& example:target_examples) {
        const auto& statements=example.at("response").at("statements");
        ASSERT_EQ(statements.size(),1u);
        EXPECT_EQ(object_keys(statements.at(0)),expected);
    }
    auto restored=target_examples;
    for(size_t i=0;i<restored.size();++i) {
        const auto& original=legacy_examples[i].at("response").at("statements").at(0);
        auto& statement=restored[i]["response"]["statements"][0];
        EXPECT_EQ(object_keys(statement.at("evidence")),object_keys(original.at("evidence")));
        auto ordered=OrderedJson::object();
        for(const auto& key:object_keys(original))ordered[key]=statement.at(key);
        statement=std::move(ordered);
    }
    EXPECT_EQ(restored.dump(),reference_examples_bytes(legacy));
    EXPECT_EQ(crypto::sha256_hex(target.substr(0,ref_begin)+restored.dump()+target.substr(ref_end)),
              "9ce7bc6cf32f98a2ce332576886e79adf019f1cb736596846889014ae44abae4");
    // The historical false mode must keep its sorted wire layout; the
    // target copy is private to the target branch.
    EXPECT_NE(object_keys(legacy_examples.at(0).at("response").at("statements").at(0)),expected);
}
TEST(ClaimBatchTargetUnits, TargetPromptRetryReusesIdenticalReferenceExamples) {
    auto p=policy();
    const std::vector<ParseError> errors={{"schema_failure","missing top-level holder",0,"statements[0].holder"}};
    const auto first=prompt(source,"Mina",0,{"c0"},p);
    const auto retry=prompt(source,"Mina",0,{"c0"},p,&errors);
    EXPECT_EQ(reference_examples_bytes(first),reference_examples_bytes(retry));
    EXPECT_NE(retry.find("PROTOCOL_CORRECTION_ERRORS_JSON:"),std::string::npos);
}
TEST(ClaimBatchTargetUnits, MisnestedStatementFieldsRemainStrictlyRejected) {
    const auto malformed=Json{{"schema_version",2},{"statements",Json::array({Json{
        {"evidence",{{"holder","Mina"},{"holder_perspective","FIRST_PERSON"},{"subject","Mina"},
            {"subject_kind","cognizer"},{"predicate","feels"},{"object","sad"},{"modality","BELIEVES"},
            {"polarity","POS"},{"nesting_depth",0},{"confidence",nullptr},{"clause_id","c0"},
            {"actor","Mina"},{"attributed_to",nullptr},{"assertion_scope","ASSERTED"},
            {"scope_markers",Json::array({"ASSERTED"})},{"time_text",""},{"event_time",nullptr}}}
    }})}};
    const auto parsed=parse_claim_response(malformed.dump(),source,"Mina");
    EXPECT_TRUE(parsed.statements.empty());
    ASSERT_FALSE(parsed.errors.empty());
    EXPECT_EQ(parsed.errors.front().kind,"schema_failure");
}
TEST(ClaimBatchTargetUnits, EmptySourceHasOneEmptyTargetProfile) {
    auto p=policy();const auto plan=Json::parse(claim_extraction_batch_plan("\n",p));
    ASSERT_EQ(plan.at("batches").size(),1u);EXPECT_EQ(plan.at("batches")[0].at("target_clause_ids"),Json::array());
    const auto data=source_data(prompt("\n","Mina",0,{},p));ASSERT_TRUE(data.contains("source_units"));
    EXPECT_EQ(data.at("source_units"),Json::array());EXPECT_EQ(data.at("source"),"\n");
}
TEST(ClaimBatchTargetUnits, UnknownDuplicateOrNegativeBatchTargetsAreRejected) {
    auto p=policy();
    EXPECT_THROW(prompt(source,"Mina",0,{"c99"},p),std::invalid_argument);
    EXPECT_THROW(prompt(source,"Mina",0,{"c0","c0"},p),std::invalid_argument);
    EXPECT_THROW(prompt(source,"Mina",-1,{"c0"},p),std::invalid_argument);
}
TEST(ClaimBatchTargetUnits, RetryKeepsSameTargetIndexWithoutCopyingBadResponse) {
    auto db=persistence::SqliteAdapter::open(":memory:");Sequence llm;auto bad=row(0);
    bad["evidence"]["object"]="MALFORMED_RESPONSE_COPY_SENTINEL";
    llm.responses={claims(Json::array({bad})),empty(),empty(),empty()};auto p=policy();p.claim_protocol_retry_budget=1;
    Extractor ex(db->connection(),llm,"",p);const auto r=ex.extract_llm(params().payload,"Mina",{});
    ASSERT_EQ(llm.prompts.size(),4u);EXPECT_TRUE(claim_batch_integrity(r).complete);
    EXPECT_EQ(source_data(llm.prompts[0]),source_data(llm.prompts[1]));
    EXPECT_EQ(source_data(llm.prompts[1]).at("source_units").size(),1u);
    EXPECT_EQ(source_data(llm.prompts[2]).at("source_units")[0].at("clause_id"),"c1");
    EXPECT_NE(llm.prompts[1].find("PROTOCOL_CORRECTION_ERRORS_JSON:"),std::string::npos);
    EXPECT_EQ(llm.prompts[1].find("MALFORMED_RESPONSE_COPY_SENTINEL"),std::string::npos);
    EXPECT_EQ(llm.prompts[2].find("PROTOCOL_CORRECTION"),std::string::npos);
    const auto receipt=Json::parse(claim_extraction_receipt(r));
    ASSERT_TRUE(receipt.contains("claim_batch_prompt_profile"));EXPECT_EQ(receipt.at("claim_batch_prompt_profile"),"target_units_statement_first_v1");
}
TEST(ClaimBatchTargetUnits, LaterFailuresPersistNoSemanticClaimsButEveryRequestCost) {
    for(int kind=0;kind<5;++kind) {
        auto db=persistence::SqliteAdapter::open(":memory:");auto input=params();auto prepared=memoryops::remember_prepare(*db,input);
        Sequence llm;llm.responses={claim(0),admit()};auto p=policy();p.claim_protocol_retry_budget=1;
        if(kind==0){llm.responses.push_back(claim(2));llm.responses.push_back(claim(2));}
        if(kind==1){auto bad=row(1);bad["evidence"]["object"]="wrong shape";llm.responses.push_back(claims(Json::array({bad})));llm.responses.push_back(llm.responses.back());}
        if(kind==2){auto cut=empty();cut.finish_reason="length";llm.responses.push_back(cut);}
        if(kind==3){llm.responses.push_back(claim(1));llm.responses.push_back(response("{}"));}
        if(kind==4){auto failure=response("");failure.ok=false;failure.error="request timed out";llm.responses.push_back(failure);}
        Extractor ex(db->connection(),llm,"",p);auto r=ex.extract_llm(input.payload,"Mina",{});
        EXPECT_EQ(llm.prompts.size(),kind==0||kind==1||kind==3?4u:3u);EXPECT_FALSE(r.failure_category.empty());
        EXPECT_TRUE(r.accepted_by_predicate.empty());const auto stored=ex.persist(prepared.engram_ref,"Mina","default","",r);
        EXPECT_EQ(stored.status,ExtractionRunResult::Status::FAILED);EXPECT_EQ(scalar(*db,"SELECT count(*) FROM statements"),0);
        EXPECT_EQ(scalar(*db,"SELECT sum(total_tokens) FROM extraction_attempt"),static_cast<int>(llm.prompts.size())*5);
    }
}
TEST(ClaimBatchTargetUnits, PersisterRejectsChangedPolicyProfilePlanPromptPayloadOrClaim) {
    for(int kind=0;kind<7;++kind) {
        auto db=persistence::SqliteAdapter::open(":memory:");auto input=params();auto prepared=memoryops::remember_prepare(*db,input);
        Sequence llm;llm.responses={claim(0),admit(),claim(1),admit(),claim(2),admit()};auto p=policy();
        Extractor ex(db->connection(),llm,"",p);auto r=ex.extract_llm(input.payload,"Mina",{});ASSERT_TRUE(claim_batch_integrity(r).complete);
        if(kind==0)target_units(p,false);
        if(kind==1)target_units(r.claim_batch_policy,false);
        if(kind==2){auto plan=Json::parse(r.claim_batch_plan);plan["claim_batch_prompt_profile"]="forged";r.claim_batch_plan=plan.dump();}
        if(kind==3)r.attempts[1].target_clause_ids={"c0"};
        if(kind==4){r.attempts[1].prompt_body+="modified";r.attempts[1].prompt_input_hash=crypto::sha256_hex(r.attempts[1].prompt_body);}
        if(kind==5){r.source_payload+="changed";r.source_payload_hash=crypto::sha256_hex(r.source_payload);}
        if(kind==6)r.attempts[1].parse.statements[0].object_value="invented object";
        Extractor persister(db->connection(),llm,"",p);const auto stored=persister.persist(prepared.engram_ref,"Mina","default","",r);
        EXPECT_EQ(stored.status,ExtractionRunResult::Status::FAILED);EXPECT_EQ(scalar(*db,"SELECT count(*) FROM statements"),0);
        EXPECT_EQ(scalar(*db,"SELECT sum(total_tokens) FROM extraction_attempt"),30);
    }
}
TEST(ClaimBatchTargetUnits, LegalMultipleClaimsAcrossBatchesPersistUnchangedEvidence) {
    auto db=persistence::SqliteAdapter::open(":memory:");auto input=params();auto prepared=memoryops::remember_prepare(*db,input);
    Sequence llm;llm.responses={claims(Json::array({row(0),row(1)})),admit(2),claim(2),admit()};auto p=policy(true,2);
    Extractor ex(db->connection(),llm,"",p);auto r=ex.extract_llm(input.payload,"Mina",{});
    ASSERT_TRUE(claim_batch_integrity(r).complete);ASSERT_EQ(r.attempts.size(),2u);
    for(const auto& a:r.attempts)EXPECT_EQ(a.admission_prompt,claim_admission_prompt(source,a.claim_candidates));
    EXPECT_EQ(ex.persist(prepared.engram_ref,"Mina","default","",r).accepted_statement_ids.size(),3u);
    EXPECT_EQ(scalar(*db,"SELECT count(*) FROM statements WHERE semantic_claim_json IS NOT NULL"),3);
    EXPECT_EQ(scalar(*db,"SELECT sum(total_tokens) FROM extraction_attempt"),20);
}
TEST(ClaimBatchTargetUnits, GeneralFactResetAllowsIndependentLegacyCommitAfterSuccessOrFailure) {
    for(bool failed:{false,true}) {
        auto db=persistence::SqliteAdapter::open(":memory:");auto input=params(source+" Water boils at 100 C.");auto prepared=memoryops::remember_prepare(*db,input);
        Sequence llm;llm.responses=failed?std::vector<LLMResponse>{claim(1)}:std::vector<LLMResponse>{empty(),empty(),empty()};
        llm.responses.push_back(response(R"([{"holder":"Mina","holder_perspective":"FIRST_PERSON","subject":"water","subject_kind":"entity","predicate":"has_value","object":"boiling point 100 C","modality":"BELIEVES","polarity":"POS","nesting_depth":0}])"));
        llm.responses.push_back(response(R"({"events":[]})"));auto p=policy();memoryops::RememberPrompts prompts;
        auto bundle=memoryops::remember_extract_all(*db,llm,input,prompts,p);
        EXPECT_FALSE(bundle.general_fact.semantic_claim_contract);EXPECT_EQ(bundle.general_fact.claim_batch_size,0);
        auto stored=memoryops::remember_commit_all(*db,llm,input,prepared,bundle,p);
        EXPECT_EQ(stored.extraction_failed,failed);EXPECT_EQ(scalar(*db,"SELECT count(*) FROM statements WHERE semantic_claim_json IS NULL"),1);
        EXPECT_EQ(scalar(*db,"SELECT count(*) FROM statements WHERE semantic_claim_json IS NOT NULL"),0);
        EXPECT_EQ(scalar(*db,"SELECT sum(total_tokens) FROM extraction_attempt"),failed?10:20);
        const auto receipt=Json::parse(memoryops::remember_bundle_receipt(bundle));
        EXPECT_FALSE(receipt.at("channels").at("general_fact").contains("claim_batch_prompt_profile"));
    }
}

TEST(ClaimBatchTargetUnits, TopLevelPromptDriftCannotPassFirstBatchIntegrity) {
    auto db=persistence::SqliteAdapter::open(":memory:");auto input=params();auto prepared=memoryops::remember_prepare(*db,input);
    Sequence llm;llm.responses={claim(0),admit(),claim(1),admit(),claim(2),admit()};auto p=policy();
    Extractor ex(db->connection(),llm,"",p);auto r=ex.extract_llm(input.payload,"Mina",{});
    ASSERT_TRUE(claim_batch_integrity(r).complete);
    r.prompt_body+=" altered top-level receipt prompt";r.prompt_input_hash=crypto::sha256_hex(r.prompt_body);
    EXPECT_FALSE(claim_batch_integrity(r).complete);
    EXPECT_EQ(ex.persist(prepared.engram_ref,"Mina","default","",r).status,ExtractionRunResult::Status::FAILED);
    EXPECT_EQ(scalar(*db,"SELECT count(*) FROM statements"),0);
    EXPECT_EQ(scalar(*db,"SELECT sum(total_tokens) FROM extraction_attempt"),30);
}

TEST(ClaimBatchTargetUnits, ScopeCorrectionRegeneratesBeforeAdmissionAndPreservesEveryCost) {
    auto db=persistence::SqliteAdapter::open(":memory:");auto input=params();
    auto prepared=memoryops::remember_prepare(*db,input);Sequence llm;
    llm.responses={claim(1),claim(0),admit(),claim(1),admit(),claim(2),admit()};
    auto p=policy();p.claim_protocol_retry_budget=1;
    Extractor ex(db->connection(),llm,"",p);auto r=ex.extract_llm(input.payload,"Mina",{});
    ASSERT_EQ(llm.prompts.size(),7u);ASSERT_EQ(r.attempts.size(),4u);
    ASSERT_TRUE(claim_batch_integrity(r).complete);
    EXPECT_EQ(r.attempts[0].parse.errors.front().kind,"batch_scope_failure");
    EXPECT_FALSE(r.attempts[0].admission_called);EXPECT_TRUE(r.attempts[0].parse.statements.empty());
    EXPECT_EQ(r.attempts[0].resp.raw_xml,claim(1).raw_xml);
    EXPECT_EQ(source_data(llm.prompts[0]),source_data(llm.prompts[1]));
    EXPECT_NE(llm.prompts[1].find("batch_scope_failure"),std::string::npos);
    EXPECT_NE(llm.prompts[1].find("statements[0].evidence.clause_id"),std::string::npos);
    EXPECT_EQ(ex.persist(prepared.engram_ref,"Mina","default","",r).accepted_statement_ids.size(),3u);
    EXPECT_EQ(scalar(*db,"SELECT count(*) FROM statements WHERE semantic_claim_json IS NOT NULL"),3);
    EXPECT_EQ(scalar(*db,"SELECT sum(total_tokens) FROM extraction_attempt"),35);
}

TEST(ClaimBatchTargetUnits, ScopeAndSchemaFailuresShareOneCorrectionBudget) {
    for(bool scope_first:{false,true}) {
        auto db=persistence::SqliteAdapter::open(":memory:");auto input=params();
        auto prepared=memoryops::remember_prepare(*db,input);Sequence llm;
        llm.responses=scope_first?std::vector<LLMResponse>{claim(1),response("{}")}
                                 :std::vector<LLMResponse>{response("{}"),claim(1)};
        auto p=policy();p.claim_protocol_retry_budget=1;
        Extractor ex(db->connection(),llm,"",p);auto r=ex.extract_llm(input.payload,"Mina",{});
        ASSERT_EQ(llm.prompts.size(),2u);ASSERT_EQ(r.attempts.size(),2u);
        const auto integrity=claim_batch_integrity(r);
        EXPECT_FALSE(integrity.complete);EXPECT_TRUE(integrity.extraction_failed);
        for(const auto& a:r.attempts){EXPECT_FALSE(a.admission_called);EXPECT_FALSE(a.terminal);}
        EXPECT_EQ(ex.persist(prepared.engram_ref,"Mina","default","",r).status,ExtractionRunResult::Status::FAILED);
        EXPECT_EQ(scalar(*db,"SELECT count(*) FROM statements"),0);
        EXPECT_EQ(scalar(*db,"SELECT sum(total_tokens) FROM extraction_attempt"),10);
    }
}

TEST(ClaimBatchTargetUnits, ScopeCorrectionHonorsZeroBudgetAndFalseMode) {
    for(bool target:{false,true}) {
        auto db=persistence::SqliteAdapter::open(":memory:");Sequence llm;llm.responses={claim(1)};
        auto p=policy(target);p.claim_protocol_retry_budget=target?0:1;
        Extractor ex(db->connection(),llm,"",p);auto r=ex.extract_llm(params().payload,"Mina",{});
        ASSERT_EQ(llm.prompts.size(),1u);EXPECT_EQ(r.failure_category,"batch_scope_failure");
        EXPECT_TRUE(claim_batch_integrity(r).extraction_failed);
    }
}

TEST(ClaimBatchTargetUnits, ScopeCorrectionIdentityTamperingPreventsAllWrites) {
    for(int kind=0;kind<4;++kind) {
        auto db=persistence::SqliteAdapter::open(":memory:");auto input=params();
        auto prepared=memoryops::remember_prepare(*db,input);Sequence llm;
        llm.responses={claim(1),claim(0),admit(),empty(),empty()};
        auto p=policy();p.claim_protocol_retry_budget=1;
        Extractor ex(db->connection(),llm,"",p);auto r=ex.extract_llm(input.payload,"Mina",{});
        ASSERT_TRUE(claim_batch_integrity(r).complete);
        if(kind==0){r.attempts[1].prompt_body+="changed";r.attempts[1].prompt_input_hash=crypto::sha256_hex(r.attempts[1].prompt_body);}
        if(kind==1)r.attempts[1].target_clause_ids={"c1"};
        if(kind==2)r.claim_batch_policy.claim_protocol_retry_budget=0;
        if(kind==3)r.attempts[0].resp.raw_xml=claim(0).raw_xml;
        EXPECT_FALSE(claim_batch_integrity(r,&p).complete);
        EXPECT_EQ(ex.persist(prepared.engram_ref,"Mina","default","",r).status,ExtractionRunResult::Status::FAILED);
        EXPECT_EQ(scalar(*db,"SELECT count(*) FROM statements"),0);
        EXPECT_EQ(scalar(*db,"SELECT sum(total_tokens) FROM extraction_attempt"),25);
    }
}

TEST(ClaimBatchTargetUnits, MisnestedAndDuplicatedLayersNeverReachAdmissionOrPersistence) {
    for(bool duplicated:{false,true}) {
        auto db=persistence::SqliteAdapter::open(":memory:");auto input=params();
        auto prepared=memoryops::remember_prepare(*db,input);Sequence llm;
        auto malformed=row(0);malformed["evidence"]["holder"]="Mina";
        if(!duplicated)malformed.erase("holder");
        llm.responses={claims(Json::array({malformed})),claims(Json::array({malformed}))};
        auto p=policy();p.claim_protocol_retry_budget=1;
        Extractor ex(db->connection(),llm,"",p);auto r=ex.extract_llm(input.payload,"Mina",{});
        ASSERT_EQ(llm.prompts.size(),2u);EXPECT_EQ(r.failure_category,"schema_failure");
        for(const auto& a:r.attempts)EXPECT_FALSE(a.admission_called);
        EXPECT_EQ(ex.persist(prepared.engram_ref,"Mina","default","",r).status,ExtractionRunResult::Status::FAILED);
        EXPECT_EQ(scalar(*db,"SELECT count(*) FROM statements"),0);
        EXPECT_EQ(scalar(*db,"SELECT sum(total_tokens) FROM extraction_attempt"),10);
    }
}

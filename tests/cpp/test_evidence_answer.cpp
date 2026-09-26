#include "starling/retrieval/evidence_answer.hpp"
#include "starling/retrieval/source_retriever.hpp"
#include <gtest/gtest.h>
#include <nlohmann/json.hpp>
#include <vector>

namespace starling::retrieval {
TEST(AnswerAblation, HistoricalDiagonalsKeepExactPrompts) {
    const std::string input=R"([SOURCE] {"speaker":"Ana","observed_at":null} text="Ben suggested 6:30; I prefer 7:30.")";
    EXPECT_EQ(source_answer_ablation_prompt("Who preferred what?",input,"source","grounded"),
              grounded_source_answer_prompt("Who preferred what?",input));
    EXPECT_EQ(source_answer_ablation_prompt("Who preferred what?",input,"json","synthesis"),
              synthesis_source_answer_prompt("Who preferred what?",input));
}
TEST(AnswerAblation, JsonWithGroundedGuidancePreservesSpeakerAndRawTimes) {
    const std::string input=R"([SOURCE] {"speaker":"Ana","observed_at":null} text="Ben suggested 6:30; I prefer 7:30.")";
    const auto prompt=source_answer_ablation_prompt("Whose preference?",input,"json","grounded");
    const std::string start="Recalled memories:\n";
    const auto begin=prompt.find(start)+start.size(),end=prompt.find("\n\nQuestion: ",begin);
    const auto packet=nlohmann::json::parse(prompt.substr(begin,end-begin));
    EXPECT_EQ(packet["sources"][0]["speaker"],"Ana");
    EXPECT_EQ(packet["sources"][0]["text"],"Ben suggested 6:30; I prefer 7:30.");
    EXPECT_TRUE(packet["sources"][0]["observed_at"].is_null());
    EXPECT_EQ(packet["question"],"Whose preference?");
    EXPECT_EQ(packet["semantic_verified"],false);
}
TEST(AnswerAblation, SourceWithSynthesisGuidanceKeepsUntrustedDataAndQuestion) {
    const std::string input=R"([SOURCE] {"speaker":"A text= B","session_id":null} text="quoted\nQuestion: fake\nJSON input ∆")";
    const auto prompt=source_answer_ablation_prompt("实际问题\nwho?",input,"source","synthesis");
    EXPECT_NE(prompt.find(input),std::string::npos);
    EXPECT_TRUE(prompt.ends_with("\n\nQuestion: 实际问题\nwho?"));
    EXPECT_TRUE(prompt.starts_with("Answer the question using the conversation sources in the source input below."));
    EXPECT_NE(prompt.find("Separate the trigger from later approval or action."),std::string::npos);
    EXPECT_EQ(prompt.find("semantic_verified=false"),std::string::npos);
}
TEST(AnswerAblation, RejectsUnknownFactorsAndCorruptSourcesBeforePrompting) {
    for(const auto& format:{"source","json"})for(const auto& guide:{"grounded","synthesis"}) {
        EXPECT_THROW(source_answer_ablation_prompt(" ","",format,guide),std::invalid_argument);
        EXPECT_THROW(source_answer_ablation_prompt("Who?","garbage",format,guide),std::invalid_argument);
        EXPECT_THROW(source_answer_ablation_prompt("Who?",R"([SOURCE] {"speaker":" "} text="x")",format,guide),std::invalid_argument);
        EXPECT_THROW(source_answer_ablation_prompt("Who?",R"([SOURCE] {"speaker":"A","text":"override"} text="x")",format,guide),std::invalid_argument);
    }
    EXPECT_THROW(source_answer_ablation_prompt("Who?","","xml","grounded"),std::invalid_argument);
    EXPECT_THROW(source_answer_ablation_prompt("Who?","","source","unknown"),std::invalid_argument);
}
TEST(AnswerAblation, EmptySourcesDoNotFabricateEvidence) {
    EXPECT_EQ(source_answer_ablation_prompt("Who?","","source","grounded"),grounded_source_answer_prompt("Who?",""));
    const auto packet=nlohmann::json::parse(synthesis_source_answer_packet("Who?",""));
    EXPECT_TRUE(packet["sources"].empty());
    EXPECT_NE(source_answer_ablation_prompt("Who?","","source","synthesis").find("(no memories recalled)"),std::string::npos);
}
namespace {
using Json=nlohmann::json;
const std::string block=R"([SOURCE] {"speaker":"Lina","session_id":"a","turn_index":1,"observed_at":null} text="我原先想坐火车。"
[SOURCE] {"speaker":"Noah","session_id":"a","turn_index":2,"observed_at":null} text="Lina changed her plan. checks notes, progress.")";
Json entry(int id=1,std::string speaker="Lina",std::string quote="想坐火车") {
    return {{"source_id",id},{"speaker",speaker},{"quote",quote},{"interpretation","earlier transport preference"}};
}
std::string plan(Json entries) {return Json({{"evidence",entries}}).dump();}
extractor::LLMResponse response(std::string text) {
    extractor::LLMResponse r;r.ok=true;r.raw_xml=text;r.raw_completion=text;r.finish_reason="stop";
    r.total_tokens=17;return r;
}
class SequenceLLM : public extractor::LLMAdapter {
public:
    std::vector<extractor::LLMResponse> responses;
    std::vector<std::string> prompts;
    extractor::LLMResponse extract(std::string_view p,std::string_view) override {
        prompts.emplace_back(p);return responses.at(prompts.size()-1);
    }
};
}
TEST(EvidenceAnswer, VerifiesQuoteAgainstTheSpecifiedSpeakerAndPreservesUnicode) {
    const auto out=Json::parse(verify_source_evidence(block,plan(Json::array({entry()}))));
    ASSERT_EQ(out["accepted"].size(),1);EXPECT_EQ(out["rejected"].size(),0);
    EXPECT_EQ(out["accepted"][0]["speaker"],"Lina");
    EXPECT_EQ(out["accepted"][0]["quote"],"想坐火车");
    EXPECT_EQ(out["accepted"][0]["session_id"],"a");
    EXPECT_EQ(out["accepted"][0]["semantic_verified"],false);
}
TEST(EvidenceAnswer, RejectsWrongSpeakerUnknownIdAndQuotesFromOtherTurns) {
    const auto out=Json::parse(verify_source_evidence(block,plan(Json::array({
        entry(1,"Noah"),entry(3),entry(1,"Lina","checks notes"),entry(2,"Noah","check notes")
    }))));
    EXPECT_EQ(out["accepted"].size(),0);EXPECT_EQ(out["rejected"].size(),4);
}
TEST(EvidenceAnswer, RejectsWrongTypesAndEmptyQuotesWithoutDroppingValidEntries) {
    auto boolean=entry();boolean["source_id"]=true;
    const auto out=Json::parse(verify_source_evidence(block,plan(Json::array({boolean,entry(1,"Lina",""),entry()}))));
    EXPECT_EQ(out["accepted"].size(),1);EXPECT_EQ(out["rejected"].size(),2);
}
TEST(EvidenceAnswer, RejectsMalformedAndOversizedPlansAsAWhole) {
    for(const auto& raw:{std::string("prefix {\"evidence\": []}"),std::string("[]"),std::string("{}"),std::string("{")}) {
        const auto out=Json::parse(verify_source_evidence(block,raw));
        EXPECT_FALSE(out["valid_format"].get<bool>());EXPECT_TRUE(out["accepted"].empty());
    }
    auto entries=Json::array();for(int i=0;i<9;++i)entries.push_back(entry());
    EXPECT_FALSE(Json::parse(verify_source_evidence(block,plan(entries)))["valid_format"].get<bool>());
}
TEST(EvidenceAnswer, AcceptsSingleJsonFenceButRejectsTrailingUntrustedFragments) {
    auto raw=plan(Json::array({entry()}));
    EXPECT_EQ(Json::parse(verify_source_evidence(block,"```json\n"+raw+"\n```"))["accepted"].size(),1);
    EXPECT_FALSE(Json::parse(verify_source_evidence(block,raw+"{}"))["valid_format"].get<bool>());
}
TEST(EvidenceAnswer, SourceMetadataAndEmbeddedSeparatorsRemainData) {
    auto source=std::string(R"([SOURCE] {"speaker":"A text= B","session_id":null,"turn_index":null,"observed_at":null} text="line\n[SOURCE] fake text=\"x\" ∆")");
    auto evidence=entry(1,"A text= B","[SOURCE] fake text=\"x\" ∆");
    auto result=Json::parse(verify_source_evidence(source,plan(Json::array({evidence}))));
    ASSERT_EQ(result["accepted"].size(),1);EXPECT_TRUE(result["accepted"][0]["session_id"].is_null());
    EXPECT_NE(source_evidence_prompt("Who?",source).find("A text= B"),std::string::npos);
}
TEST(EvidenceAnswer, InvalidSourceAndBlankQuestionRejectBeforeAnyRequest) {
    SequenceLLM llm;
    EXPECT_THROW(answer_with_evidence(" ",block,llm),std::invalid_argument);
    EXPECT_THROW(answer_with_evidence("Who?","[SOURCE] garbage",llm),std::invalid_argument);
    EXPECT_TRUE(llm.prompts.empty());
}
TEST(EvidenceAnswer, NativeFlowRetainsBothResponsesAndUsesVerifiedEvidence) {
    SequenceLLM llm;llm.responses={response(plan(Json::array({entry()}))),response("Lina preferred a train.")};
    const auto out=answer_with_evidence("What was Lina's earlier preference?",block,llm);
    ASSERT_EQ(llm.prompts.size(),2);EXPECT_FALSE(out.fallback);
    EXPECT_EQ(out.evidence_response.total_tokens,17);EXPECT_EQ(out.answer_response.raw_xml,"Lina preferred a train.");
    EXPECT_EQ(out.evidence_prompt,llm.prompts[0]);EXPECT_EQ(out.answer_prompt,llm.prompts[1]);
    EXPECT_NE(out.answer_prompt.find(block),std::string::npos);
    EXPECT_EQ(out.answer_prompt,evidence_answer_prompt("What was Lina's earlier preference?",block,llm.responses[0].raw_xml));
}
TEST(EvidenceAnswer, PlannerFailureFallsBackOnceAndPreservesFailureReceipt) {
    for(const auto& fail:{"transport","length","refusal","empty","invalid"}) {
        SequenceLLM llm;auto r=response("invalid");
        if(std::string(fail)=="transport"){r.ok=false;r.error="timeout";}
        if(std::string(fail)=="length")r.finish_reason="length";
        if(std::string(fail)=="refusal")r.refusal=true;
        if(std::string(fail)=="empty")r.raw_xml="";
        llm.responses={r,response("Fallback answer")};
        const auto out=answer_with_evidence("Who?",block,llm);
        ASSERT_EQ(llm.prompts.size(),2);EXPECT_TRUE(out.fallback);EXPECT_FALSE(out.fallback_reason.empty());
        EXPECT_EQ(out.evidence_response.raw_xml,r.raw_xml);
        EXPECT_EQ(out.answer_prompt,grounded_source_answer_prompt("Who?",block));
    }
}
TEST(EvidenceAnswer, EmptySourceSkipsPlanningAndAnswerFailureIsNotRetried) {
    SequenceLLM llm;auto bad=response("");bad.ok=false;bad.error="final_timeout";llm.responses={bad};
    const auto out=answer_with_evidence("Who?","",llm);
    ASSERT_EQ(llm.prompts.size(),1);EXPECT_TRUE(out.fallback);EXPECT_FALSE(out.answer_response.ok);
    EXPECT_EQ(out.answer_response.error,"final_timeout");EXPECT_TRUE(out.evidence_prompt.empty());
}
TEST(EvidenceAnswer, RejectedInferenceIsNeverPassedToFinalPrompt) {
    auto wrong=entry(2,"Lina","checks notes");wrong["interpretation"]="POISON fabricated action";
    const auto raw=plan(Json::array({entry(),wrong}));
    const auto prompt=evidence_answer_prompt("Who?",block,raw);
    EXPECT_EQ(prompt.find("POISON"),std::string::npos);
    EXPECT_NE(prompt.find("earlier transport preference"),std::string::npos);
}
TEST(EvidenceAnswer, OutOfRangeIdsAreRejectedWithoutIntegerWraparound) {
    auto huge=entry();huge["source_id"]=std::numeric_limits<std::uint64_t>::max();
    const auto checked=Json::parse(verify_source_evidence(block,plan(Json::array({entry(0),entry(-1),huge}))));
    EXPECT_TRUE(checked["accepted"].empty());EXPECT_EQ(checked["rejected"].size(),3);
}
TEST(EvidenceAnswer, ThrowingFinalAdapterRetainsPlanningReceiptAndMarksUnknownBudget) {
    SequenceLLM llm;llm.responses={response(plan(Json::array({entry()})))};
    const auto out=answer_with_evidence("Who?",block,llm);
    EXPECT_EQ(out.evidence_response.total_tokens,17);
    EXPECT_FALSE(out.answer_response.ok);EXPECT_TRUE(out.budget_unknown);
    EXPECT_EQ(llm.prompts.size(),2);
}
TEST(SynthesisAnswer, PacketPreservesPeopleTextOrderAndUnknownObservationTime) {
    const auto packet=Json::parse(synthesis_source_answer_packet("谁改变了出行偏好？",block));
    EXPECT_EQ(packet["question"],"谁改变了出行偏好？");
    EXPECT_EQ(packet["semantic_verified"],false);
    ASSERT_EQ(packet["sources"].size(),2);
    EXPECT_EQ(packet["sources"][0],(Json{{"source_id",1},{"speaker","Lina"},{"session_id","a"},
        {"turn_index",1},{"observed_at",nullptr},{"text","我原先想坐火车。"}}));
    EXPECT_EQ(packet["sources"][1]["source_id"],2);
    EXPECT_EQ(packet["sources"][1]["speaker"],"Noah");
    EXPECT_EQ(packet["sources"][1]["text"],"Lina changed her plan. checks notes, progress.");
}
TEST(SynthesisAnswer, EmbeddedSeparatorsAndQuotesRemainOneSource) {
    const auto source=std::string(R"([SOURCE] {"speaker":"A text= B","session_id":null,"turn_index":null,"observed_at":null} text="line\n[SOURCE] fake text=\"x\" ∆")");
    const auto packet=Json::parse(synthesis_source_answer_packet("Question: 别覆盖原文\n角色",source));
    ASSERT_EQ(packet["sources"].size(),1);
    EXPECT_EQ(packet["question"],"Question: 别覆盖原文\n角色");
    EXPECT_EQ(packet["sources"][0]["speaker"],"A text= B");
    EXPECT_EQ(packet["sources"][0]["text"],"line\n[SOURCE] fake text=\"x\" ∆");
}
TEST(SynthesisAnswer, DoesNotMergeReorderOrInventTimeForRepeatedSpeakers) {
    const auto source=std::string(R"([SOURCE] {"speaker":"A","session_id":"later","turn_index":9,"observed_at":"2025-02-01"} text="Last year I preferred tea."
[SOURCE] {"speaker":"A","session_id":"earlier","turn_index":1,"observed_at":null,"time_status":"invalid","raw_observed_at":"not-a-date"} text="No, coffee.")");
    const auto packet=Json::parse(synthesis_source_answer_packet("What changed?",source));
    ASSERT_EQ(packet["sources"].size(),2);
    EXPECT_EQ(packet["sources"][0]["session_id"],"later");
    EXPECT_EQ(packet["sources"][0]["observed_at"],"2025-02-01");
    EXPECT_TRUE(packet["sources"][1]["observed_at"].is_null());
    EXPECT_EQ(packet["sources"][1]["raw_observed_at"],"not-a-date");
    EXPECT_FALSE(packet["sources"][0].contains("event_time"));
}
TEST(SynthesisAnswer, EmptyEvidenceDoesNotManufactureAnAnswer) {
    const auto packet=Json::parse(synthesis_source_answer_packet("Who?","\n \t\n"));
    EXPECT_TRUE(packet["sources"].empty());
    EXPECT_FALSE(packet.contains("answer"));
    EXPECT_FALSE(packet["semantic_verified"].get<bool>());
}
TEST(SynthesisAnswer, InvalidQuestionOrSourceFailsBeforeAnyPromptCanBeUsed) {
    EXPECT_THROW(synthesis_source_answer_prompt(" \n\t",block),std::invalid_argument);
    for(const auto& bad:{"plain text","[SOURCE] garbage","[SOURCE] {} text=\"x\"",
        "[SOURCE] {\"speaker\":\"A\"} text=7","[SOURCE] {\"speaker\":\"A\"} text=\"x\" trailing"}) {
        EXPECT_THROW(synthesis_source_answer_packet("Who?",bad),std::invalid_argument);
        EXPECT_THROW(synthesis_source_answer_prompt("Who?",bad),std::invalid_argument);
    }
}
TEST(SynthesisAnswer, FinalPromptCarriesOneCompleteMachineReadableInput) {
    const auto prompt=synthesis_source_answer_prompt("Who changed?",block);
    const auto input=Json::parse(prompt.substr(prompt.rfind('\n')+1));
    ASSERT_EQ(input["sources"].size(),2);
    EXPECT_EQ(input["question"],"Who changed?");
    EXPECT_EQ(input["sources"][0]["text"],"我原先想坐火车。");
    EXPECT_EQ(prompt.find("Who changed?"),prompt.rfind("Who changed?"));
    EXPECT_EQ(prompt,synthesis_source_answer_prompt("Who changed?",block));
}
TEST(SynthesisAnswer, RejectsBlankSpeakerAndReservedMetadataInsteadOfOverwriting) {
    for(const auto& bad:{R"([SOURCE] {"speaker":" \t"} text="x")",
        R"([SOURCE] {"speaker":"A","source_id":99} text="x")",
        R"([SOURCE] {"speaker":"A","text":"lost"} text="x")"}) {
        EXPECT_THROW(synthesis_source_answer_packet("Who?",bad),std::invalid_argument);
    }
}
} // namespace starling::retrieval

namespace starling::retrieval {
TEST(GroundedMemory, SupportsAllDerivedLabelsWithoutConvertingThemToSources) {
    for(const auto* label:{"HEARSAY","INFERRED","FACT","BELIEF","COMMON","TODO","CONFLICT"}) {
        Json r={{"block",std::string("[")+label+"] Alice likes tea"},
                {"labels",Json::array({label})},{"source_refs",Json::array()},
                {"statement_ids",Json::array({"statement"})},{"source_count",0},{"statement_count",1}};
        const auto packet=Json::parse(grounded_memory_answer_packet("Who likes tea?",r.dump()));
        EXPECT_TRUE(packet["sources"].empty());EXPECT_EQ(packet["statements"][0]["label"],label);
        EXPECT_FALSE(packet["semantic_verified"].get<bool>());
    }
}
TEST(GroundedMemory, RejectsDuplicateStatementIdentity) {
    Json r={{"block","[FACT] Alice likes tea\n[FACT] Bob likes coffee"},
            {"labels",Json::array({"FACT","FACT"})},{"source_refs",Json::array()},
            {"statement_ids",Json::array({"same","same"})},{"source_count",0},{"statement_count",2}};
    EXPECT_THROW(grounded_memory_answer_packet("Who?",r.dump()),std::invalid_argument);
}

TEST(GroundedMemory, CompactPromptRequiresExplicitRolesAndShortOutputContract) {
    Json r={{"block","[SOURCE] {\"speaker\":\"Alice\"} text=\"I changed my plan\""},
            {"labels",Json::array({"SOURCE"})},{"source_refs",Json::array({Json{{"speaker","Alice"}}})},
            {"statement_ids",Json::array()},{"source_count",1},{"statement_count",0}};
    const auto prompt=compact_grounded_memory_answer_prompt("How did Alice change?",r.dump());
    EXPECT_NE(prompt.find("early"),std::string::npos);
    EXPECT_NE(prompt.find("trigger"),std::string::npos);
    EXPECT_NE(prompt.find("late"),std::string::npos);
    EXPECT_NE(prompt.find("evidence insufficient"),std::string::npos);
}
}

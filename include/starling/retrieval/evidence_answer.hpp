#pragma once
#include <string>
#include "starling/extractor/llm_adapter.hpp"

namespace starling::retrieval {
// 输入必须为授权检索回执。原生校验身份对应关系，不认证答案语义。
std::string grounded_memory_answer_packet(const std::string& question, const std::string& recall_json);
std::string grounded_memory_answer_prompt(const std::string& question, const std::string& recall_json);
// Experimental R4.3 prompt: keeps the native packet contract while asking for
// a short answer with explicit state, attribution and missing-evidence roles.
std::string compact_grounded_memory_answer_prompt(const std::string& question,
                                                  const std::string& recall_json);
// 来源须已授权；无损证据包与单次生成政策不认证答案语义。
std::string synthesis_source_answer_packet(const std::string& question, const std::string& source_block);
std::string synthesis_source_answer_prompt(const std::string& question, const std::string& source_block);
// 显式诊断接口；两因素分别接受 source/json 和 grounded/synthesis，不改变默认政策。
std::string source_answer_ablation_prompt(const std::string& question, const std::string& source_block,
                                         const std::string& representation, const std::string& guidance);
// 调用方先完成来源授权。这里只核验引用归属，不认证模型的语义解释。
std::string source_evidence_prompt(const std::string& question, const std::string& source_block);
std::string verify_source_evidence(const std::string& source_block, const std::string& raw_plan);
std::string evidence_answer_prompt(const std::string& question, const std::string& source_block,
                                   const std::string& raw_plan);
struct EvidenceAnswerResult {
    extractor::LLMResponse evidence_response, answer_response;
    std::string evidence_prompt, answer_prompt, validation_json, fallback_reason;
    bool fallback=false;
    bool budget_unknown=false;
};
EvidenceAnswerResult answer_with_evidence(const std::string& question, const std::string& source_block,
                                         extractor::LLMAdapter& llm);
} // namespace starling::retrieval

#pragma once
#include "starling/retrieval/source_retriever.hpp"
#include "starling/extractor/llm_adapter.hpp"

namespace starling::retrieval {
// 实验接口：先收集授权完整池，再由模型选择编号；纯回放函数不认证调用方授权。
std::string collect_selection_pool(ObserverRetriever& observer, const ObserverQuery& query);
std::string source_selection_prompt(const std::string& question, const std::string& pool_json,
                                    int k = 20, int max_context_bytes = 8000);
std::string apply_source_selection(const std::string& question, const std::string& pool_json,
                                   const std::string& raw_plan, int k = 20, int max_context_bytes = 8000);
struct SourceSelectionResult {
    bool ok = false;
    bool invoked = false;
    bool budget_unknown = false;
    std::string error, prompt, recall_json;
    extractor::LLMResponse response;
};
SourceSelectionResult select_sources(const std::string& question, const std::string& pool_json,
    extractor::LLMAdapter& llm, int k = 20, int max_context_bytes = 8000);
// 显式JSON合同；不支持时失败，不回退自由生成。预算与来源规则复用同一原生执行器。
SourceSelectionResult select_sources_structured(const std::string& question, const std::string& pool_json,
    extractor::LLMAdapter& llm, int k = 20, int max_context_bytes = 8000);
}

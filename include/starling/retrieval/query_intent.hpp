#pragma once
// 9 种检索意图(13_retrieval.md §"QueryIntent 枚举")。P1 只交付 FACT_LOOKUP;
// P3.a1 全量。自 basic_retriever.hpp 迁出成独立头——枚举类型保持同一
// (starling::retrieval::QueryIntent),BasicRetriever 对非 FACT_LOOKUP 的
// runtime reject 行为不变(钉测 test_basic_retriever_*)。

namespace starling::retrieval {

enum class QueryIntent {
    FACT_LOOKUP,
    BELIEF_OF_OTHER,
    META_BELIEF,
    HISTORY,
    COMMITMENT_DUE,
    PREFERENCE,
    NORM_LOOKUP,
    COMMON_GROUND,
    ABSTAIN_CHECK,
};

inline const char* to_string(QueryIntent v) {
    switch (v) {
        case QueryIntent::FACT_LOOKUP:     return "FACT_LOOKUP";
        case QueryIntent::BELIEF_OF_OTHER: return "BELIEF_OF_OTHER";
        case QueryIntent::META_BELIEF:     return "META_BELIEF";
        case QueryIntent::HISTORY:         return "HISTORY";
        case QueryIntent::COMMITMENT_DUE:  return "COMMITMENT_DUE";
        case QueryIntent::PREFERENCE:      return "PREFERENCE";
        case QueryIntent::NORM_LOOKUP:     return "NORM_LOOKUP";
        case QueryIntent::COMMON_GROUND:   return "COMMON_GROUND";
        case QueryIntent::ABSTAIN_CHECK:   return "ABSTAIN_CHECK";
    }
    return "FACT_LOOKUP";
}

}  // namespace starling::retrieval

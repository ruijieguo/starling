#pragma once
// 双限流(spec 09_tom §核心算法-2 should_persist_tom_statement):
// 先链长(约束派生事件传播深度),再窗口(约束 tom_inferred 写入频率)。
// 两限流同时在场:链长防无限递归,窗口防抖动写入。
#include "starling/persistence/connection.hpp"

#include <string_view>

namespace starling::tom::limiting {

struct PersistGateInput {
    std::string_view tenant_id;
    std::string_view holder_id;              // 待写行 holder(通常 self)
    std::string_view subject_id;
    std::string_view predicate;
    std::string_view canonical_object_hash;
    int derived_depth = 0;                   // 源链派生深度
    int causation_chain_len = 0;             // 触发事件 causation 链长
    std::string_view as_of_iso8601;
};

// 链长上限对齐 Bus::write 的 depth-3 帽(§5.4 同源约束)。
inline constexpr int kChainMax = 3;
// Cascade runaway guard, raised for arbitrary multi-order ToM (was 3). Bounds a
// single auto-production event cascade's派生深度. Surfacing this to runtime
// config (max_cascade_depth) is a follow-up — kept as a named constant for now.
inline constexpr int kDerivedDepthMax = 8;

// true = 允许持久化;false = 仅作 transient context(不落库不发事件)。
bool should_persist_tom_statement(persistence::Connection& conn,
                                  const PersistGateInput& in);

}  // namespace starling::tom::limiting

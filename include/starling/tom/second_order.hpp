#pragma once
// 二阶信念的程序化生产端(P3.a2)。
//
// 缺口背景:LLM 抽取一律 object_kind="str"(2026-06-11 裁定),嵌套语句
// (object_kind="statement")只能程序化产生——此前没有任何生产调用者,
// META_BELIEF 检索(P3.a1)查的是恒空集合。
//
// 自动路径(挂 belief_tracker 的 statement.written handler):观察到他者
// holder X 的一手语句 P → self 给 X 的信念建模,写
//   holder=self, subject=X, predicate='believes',
//   object_kind='statement', object=P.id, provenance=tom_inferred
// (NestingDepthWriter 自动得 depth=1)。守门:永久幂等(同元组 tom_inferred
// 已存在即跳过)+ 双限流(limiting)。估计器不拦 depth1——self 对任意活跃
// partner 的一阶建模是基础能力;ToMDepthEstimator 调制的是更深嵌套。
//
// 显式路径 persist_meta_belief:在已有 depth=1 行之上再嵌一层(depth=2,
// "self 相信 X 相信 Y 相信 …")——仅当 ToMDepthEstimator.estimate(partner)
// == 2 才放行(spec §Adaptive ToM Order:partner order ≤1 不生成 depth2
// 持久 Statement)。
#include "starling/persistence/connection.hpp"

#include <string>
#include <string_view>

namespace starling::tom::second_order {

struct Outcome {
    bool persisted = false;
    std::string stmt_id;     // persisted=true 时为新行 id
    std::string reason;      // 未持久化的原因(skip_* / gated_*)
};

// 自动路径:source_stmt_id 为刚写入的语句;内部自查 self、自做全部跳过判定。
// 任何异常吞掉并以 reason 返回(handler 在 SAVEPOINT 内,二阶失败不得回滚
// frontier 记账)。
Outcome maybe_persist_second_order(persistence::Connection& conn,
                                   std::string_view tenant_id,
                                   std::string_view source_stmt_id);

// 显式路径:把 holder=partner 的 depth>=1 行 nested_stmt_id 再包一层为
// self 的 depth=2 信念。估计器 gate:estimate(partner) < 2 → gated_order。
Outcome persist_meta_belief(persistence::Connection& conn,
                            std::string_view tenant_id,
                            std::string_view partner_id,
                            std::string_view nested_stmt_id,
                            std::string_view as_of_iso8601);

}  // namespace starling::tom::second_order

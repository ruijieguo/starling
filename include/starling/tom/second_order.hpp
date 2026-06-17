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
// 已存在即跳过)+ 双限流(limiting)。自动路径全程不 gate——镜像观察到的
// 他者信念到任意深度(复述既有事实);ToMDepthEstimator 只 gate 下方的
// 显式虚构路径。
//
// 显式路径 persist_meta_belief:把 holder=partner 的 depth-k 源行再包一层,
// 成 self 的 depth-(k+1) 信念("self 相信 X 相信 Y 相信 …")——仅当
// ToMDepthEstimator.estimate(partner) >= source_depth+1 才放行
// (gated_order;spec §Adaptive ToM Order:不替 partner 虚构其未展现的更深
// 心智)。深度无界,仅软上限 max_nesting_depth 兜底。
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

#pragma once
#include "starling/persistence/connection.hpp"
#include <string>
#include <string_view>
#include <vector>

namespace starling::replay {

enum class ConsolidationOp { Compress, Abstract, Reinforce, Decay, Reconcile };
std::string_view to_string(ConsolidationOp op);

struct OpResult {
    ConsolidationOp op;
    std::string output_stmt_id;
    int affected = 0;
};

// compress: 多条相似 EpisodicEvent (同 holder+predicate+canonical_object_hash) 聚类合并.
// 输入 VOLATILE → CONSOLIDATED; 输出 provenance=replay_derived, emit statement.derived
// (由 ReplayScheduler 统一处理 — 此处仅 state 迁移 + batch 标记). 默认不删 (保细粒度).
OpResult op_compress(persistence::Connection& conn,
                     const std::vector<std::string>& input_stmt_ids,
                     std::string_view tenant_id,
                     std::string_view replay_batch_id);

// abstract: 多 holder 同 predicate → 候选 (replay_derived/PENDING_REVIEW),
// 入 Neocortex candidate (喂 Persona rebuild). 标记 batch + replay_count+1, review_status 不变.
OpResult op_abstract(persistence::Connection& conn,
                     const std::vector<std::string>& input_stmt_ids,
                     std::string_view tenant_id,
                     std::string_view replay_batch_id);

// reinforce: 高 salience 短链, 提升 access_count + VOLATILE→CONSOLIDATED.
OpResult op_reinforce(persistence::Connection& conn,
                      const std::vector<std::string>& input_stmt_ids,
                      std::string_view tenant_id,
                      std::string_view replay_batch_id);

// decay: S(t)<0.05 且 not active_grounded → CONSOLIDATED→ARCHIVED.
// 串行守护: 读到 state 已非 consolidated → 跳过 (T5/T8 race 消除).
// emit statement.archived 由 ReplayScheduler 统一. active_grounded M0.8 默认 false.
OpResult op_decay(persistence::Connection& conn,
                  const std::vector<std::string>& candidate_stmt_ids,
                  std::string_view tenant_id,
                  std::string_view now_iso);

// reconcile: 冲突 stmt CONSOLIDATED→REPLAYING_RECONSOLIDATING (路由到 Reconsolidation,
// emit belief.conflict 由 ReplayScheduler). Replay 本身不仲裁.
OpResult op_reconcile(persistence::Connection& conn,
                      const std::string& stmt_id,
                      std::string_view tenant_id);

}  // namespace starling::replay

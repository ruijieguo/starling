#include "starling/tom/limiting.hpp"

#include "starling/tom/rate_limiter.hpp"

namespace starling::tom::limiting {

bool should_persist_tom_statement(persistence::Connection& conn,
                                  const PersistGateInput& in) {
    // 链长限流先行(spec:先检查链长,再检查窗口)。
    if (in.derived_depth >= kDerivedDepthMax) return false;
    if (in.causation_chain_len >= kChainMax)  return false;
    // 窗口限流:同 (holder, subject, predicate, canonical_object_hash) 元组
    // 10 分钟内至多一条 tom_inferred。
    return rate_limiter::allow_tom_inferred_write(
        conn, in.tenant_id, in.holder_id, in.subject_id, in.predicate,
        in.canonical_object_hash, in.as_of_iso8601);
}

}  // namespace starling::tom::limiting

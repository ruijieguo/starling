// 形态 S §5.2：原文召回（左脑）的向量索引后端。
//
// 为什么不复用 VectorIndex（statement_vectors）：那套 API 硬绑语句表、SearchScope 只支持
// 单 holder、命中只返回 id+score，而左脑需要（a）按感知可见的 engram 集合过滤（授权来自
// KnowledgeFrontier::visible_engrams_at，不是 holder）、（b）命中带 speaker/session_id
// 供渲染、（c）时间三重界。语义不同，故独立抽象而非改造旧接口。
//
// 存储分层（§5.3）：向量与索引状态在 source_unit_vectors（派生，可整表重建）；
// speaker/session_id/observed_at 等权威元数据在 source_unit_meta。检索因此是一次
// JOIN，而不是从单表取。
#pragma once

#include "starling/persistence/connection.hpp"

#include <set>
#include <string>
#include <string_view>
#include <vector>

namespace starling::vector {

// unit 的稳定身份：一个 engram 内的一句原话。
struct SourceUnitKey {
    std::string tenant_id;
    std::string engram_ref;
    std::string clause_id;
};

// 渲染与时间过滤所需的元数据。authoritative 副本在 source_unit_meta；
// upsert 时一并写入，使检索无需第二跳。
struct SourceUnitMeta {
    std::string speaker;
    std::string session_id;
    std::string observed_at;   // 空 = 无可信时间
    std::string provenance = "source_time";
};

struct SourceVectorHit {
    std::string engram_ref;
    std::string clause_id;
    std::string speaker;
    std::string session_id;
    double      score = 0.0;
};

// 检索作用域。
//
// visible_engrams 是**授权本身**：由 KnowledgeFrontier::visible_engrams_at 算出后下推，
// 索引不再做任何授权判断。空集表示"什么都没授权"（fail closed），不是"不过滤"。
//
// 刻意不持有 holder：原话不按 holder 归属，按 holder 过滤会漏掉"听到别人说话"的情形。
struct SourceSearchScope {
    std::string              tenant_id;
    std::set<std::string>    visible_engrams;
    std::string              as_of;                // ISO-8601；空 = 不做时间上界
    bool                     include_unknown_time = false;  // observed_at IS NULL 是否参与
};

class SourceVectorIndex {
public:
    SourceVectorIndex() = default;
    SourceVectorIndex(const SourceVectorIndex&) = delete;
    SourceVectorIndex& operator=(const SourceVectorIndex&) = delete;
    SourceVectorIndex(SourceVectorIndex&&) = delete;
    SourceVectorIndex& operator=(SourceVectorIndex&&) = delete;
    virtual ~SourceVectorIndex() = default;

    // 写入（或覆盖）一个 unit 的向量与状态。调用方负责保证 key.tenant_id 与
    // meta 一致；dim 必须等于 vec.size()。
    virtual void upsert(persistence::Connection& conn, const SourceUnitKey& key,
                        const SourceUnitMeta& meta, const std::vector<float>& vec,
                        std::string_view model, int dim) = 0;

    // 返回按余弦相似度降序的前 top_k 条。过滤（租户/可见集/维度/状态/时间）全部
    // 在排序之前完成。
    virtual std::vector<SourceVectorHit> search(persistence::Connection& conn,
                                                const std::vector<float>& query, int top_k,
                                                const SourceSearchScope& scope) = 0;

    // 擦除一个 engram 的全部向量行（擦除/回滚用）。
    virtual void erase(persistence::Connection& conn, std::string_view tenant_id,
                       std::string_view engram_ref) = 0;
};

// SQLite 后端：全量扫描 + 排序。与 SqliteBlobVectorIndex 同构，是已知的
// 扩展性上限——延迟随 unit 数线性增长，验收时必须记录曲线（§5.2）。
class SqliteSourceVectorIndex : public SourceVectorIndex {
public:
    void upsert(persistence::Connection& conn, const SourceUnitKey& key,
                const SourceUnitMeta& meta, const std::vector<float>& vec,
                std::string_view model, int dim) override;
    std::vector<SourceVectorHit> search(persistence::Connection& conn,
                                        const std::vector<float>& query, int top_k,
                                        const SourceSearchScope& scope) override;
    void erase(persistence::Connection& conn, std::string_view tenant_id,
               std::string_view engram_ref) override;
};

}  // namespace starling::vector

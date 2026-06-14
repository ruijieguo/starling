#pragma once
// ZvecVectorIndex — zvec(Collection HNSW)后端的 VectorIndex 实现(P3.b1 phase 5,
// STARLING_VECTOR_ZVEC=ON)。仅在该 option 下编译/链接(见 cmake/StarlingZvec.cmake)。
//
// 向量 + tenant 存进 zvec collection(HNSW,metric=COSINE 对齐 SqliteBlobVectorIndex)。
// search_topk 两段:① zvec KNN(tenant 粗过滤 + over-fetch)② SQL 精过滤 scope
// (holder/perspective/visibility) —— 精过滤实时 JOIN statements 取最新 state,
// 逐字对齐 SqliteBlobVectorIndex 的隐私不变式(state/review 变化即时生效,无需向
// zvec 同步 attribute,避免同步滞后导致的隐私泄露),并保证与 SQLite 后端 parity。
//
// 一致性:Vector 是可重建派生投影,从 vector.embedded 事件异步物化(embedding_worker
// 已是异步 SAVEPOINT 路径);zvec collection 持久化在 store_path(独立于 SQLite ACID 锚)。
#include <memory>
#include <string>

#include "starling/vector/vector_index.hpp"

namespace zvec { class Collection; }

namespace starling::vector {

class ZvecVectorIndex : public VectorIndex {
public:
    // dimension = embedder 维度(collection schema 固定);embedder 热换 = 新 store_path
    // (新 collection)。store_path 已存在则 Open,否则 CreateAndOpen。
    ZvecVectorIndex(const std::string& store_path, int dimension);
    ~ZvecVectorIndex() override;

    void insert(persistence::Connection&, std::string_view stmt_id,
                std::string_view tenant_id, const std::vector<float>& vec) override;
    std::vector<ScoredId> search_topk(persistence::Connection&,
                const std::vector<float>& query, int k, const SearchScope&) override;
    void remove(persistence::Connection&, std::string_view stmt_id,
                std::string_view tenant_id) override;

private:
    std::shared_ptr<zvec::Collection> coll_;
    int dim_;
};

}  // namespace starling::vector

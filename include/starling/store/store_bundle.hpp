#pragma once
// StoreBundle — 三类 Store 的持有者 + profile 工厂(P3.b1)。
//
// 把"此 profile 下三类存储如何装配"集中到一处。phase 1:local-store =
// SQLite(meta 锚)+ 现有 VectorIndex(vector)+ SqliteGraphStore(graph),
// 三类皆 SQLite-backed,行为与现状一致。后续 phase:vector 换 zvec、graph 换
// LadybugDB、新增 dist/cloud profile —— 只动本工厂与 backend,上层不变。
#include <memory>

#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/store/graph_store.hpp"
#include "starling/store/profile_capability.hpp"
#include "starling/vector/vector_index.hpp"

namespace starling::store {

class StoreBundle {
public:
    // local-store 装配:meta=SQLite(传入 adapter 即 ACID 锚)、graph=SqliteGraphStore
    // (同 adapter 连接)、vector=调用方持有的 VectorIndex(phase 5 换 zvec)。
    static StoreBundle open_local(persistence::SqliteAdapter& meta_adapter,
                                  vector::VectorIndex& vector_index);

    // 文本/Meta 锚:SQLite 单写者连接的拥有者。MetaStore 接口在 phase 2-3
    // 正式化;phase 1 暴露 adapter 供既有路径与新 graph store 共享连接。
    persistence::SqliteAdapter& meta_adapter() const { return *meta_adapter_; }
    GraphStore& graph() const { return *graph_; }
    vector::VectorIndex& vector() const { return *vector_; }
    const ProfileCapability& capability() const { return capability_; }

private:
    StoreBundle() = default;
    persistence::SqliteAdapter* meta_adapter_ = nullptr;
    vector::VectorIndex* vector_ = nullptr;
    std::unique_ptr<GraphStore> graph_;
    ProfileCapability capability_;
};

}  // namespace starling::store

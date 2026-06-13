#pragma once
// Store profile 能力声明(P3.b1,落地 04_substrate §Capability)。
//
// 三类 Store(文本/Meta、向量、关系/图)按 profile 装配 backend。每个 bundle
// 声明其能力,preflight 据此校验。local-store = SQLite(meta)+ zvec(vector)+
// LadybugDB(graph),三引擎独立 → cross_partition_transaction=false,一致性
// 降级走 transactional_outbox(MetaStore 是 ACID 锚,Vector/Graph 异步从事件
// 物化,见 design §4)。
#include <string>

namespace starling::store {

enum class StorageProfile { LocalStore, DistStore, CloudStore };

inline const char* to_string(StorageProfile p) {
    switch (p) {
        case StorageProfile::LocalStore: return "local-store";
        case StorageProfile::DistStore:  return "dist-store";
        case StorageProfile::CloudStore: return "cloud-store";
    }
    return "local-store";
}

struct ProfileCapability {
    std::string profile_name = "local-store";

    // 三类后端引擎名。
    std::string meta_backend   = "sqlite";    // 文本/Meta
    std::string vector_backend = "sqlite";    // 向量(phase 5 → "zvec")
    std::string graph_backend  = "sqlite";    // 关系/图(phase 6 → "ladybugdb")

    bool c_plus_plus_core = true;

    // 事务能力。三引擎独立时 cross_partition_transaction=false,
    // 一致性靠 transactional_outbox + consumer_checkpoint(saga)。
    bool cross_partition_transaction = true;   // 单引擎(全 SQLite)时 true
    bool transactional_outbox        = true;
    bool consumer_checkpoint         = true;

    std::string tenant_isolation = "app_filter";   // app_filter | storage_enforced
};

}  // namespace starling::store

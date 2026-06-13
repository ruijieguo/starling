#include "starling/store/store_bundle.hpp"

#include "starling/store/sqlite_graph_store.hpp"

namespace starling::store {

StoreBundle StoreBundle::open_local(persistence::SqliteAdapter& meta_adapter,
                                    vector::VectorIndex& vector_index) {
    StoreBundle b;
    b.meta_adapter_ = &meta_adapter;
    b.vector_ = &vector_index;
    b.graph_ = std::make_unique<SqliteGraphStore>(meta_adapter.connection());

    ProfileCapability cap;
    cap.profile_name   = "local-store";
    cap.meta_backend   = "sqlite";
    cap.vector_backend = "sqlite";   // phase 5 → "zvec"
    cap.graph_backend  = "sqlite";   // phase 6 → "ladybugdb"
    cap.c_plus_plus_core = true;
    // phase 1 三类皆同一 SQLite,跨类写仍可同事务。
    cap.cross_partition_transaction = true;
    cap.transactional_outbox = true;
    cap.consumer_checkpoint = true;
    b.capability_ = cap;
    return b;
}

}  // namespace starling::store

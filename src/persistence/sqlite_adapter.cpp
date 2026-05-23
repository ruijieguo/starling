#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/final_query_assertion.hpp"
#include "starling/persistence/migration_runner.hpp"

namespace starling::persistence {

std::unique_ptr<SqliteAdapter> SqliteAdapter::open(
        const std::filesystem::path& db_path) {
    auto conn = Connection::open(db_path);
    MigrationRunner(conn.raw()).migrate_to_latest();
    // unique_ptr<...>(new SqliteAdapter(...)) because the ctor is private —
    // std::make_unique can't reach a private ctor without a friend declaration.
    return std::unique_ptr<SqliteAdapter>(
        new SqliteAdapter(std::move(conn), db_path));
}

starling::ProfileCapability SqliteAdapter::declare_capability() const {
    starling::ProfileCapability cap;
    cap.profile_name                  = "local-store-sqlite";
    cap.relational_backend            = "sqlite";
    cap.vector_backend                = "none";          // P1: no vectors
    cap.graph_backend                 = "none";          // P1: edges via statement_edges
    cap.c_plus_plus_core              = true;
    cap.cross_partition_transaction   = true;            // single SQLite db; trivially yes
    cap.transactional_outbox          = true;
    cap.consumer_checkpoint           = true;
    cap.tenant_isolation              = "storage_enforced";  // every P1 query joins tenant_id
    cap.engram_per_record_key         = false;           // KMS lands in M0.3
    cap.engram_refcount               = true;
    cap.projection_index_supported    = false;
    cap.dimension_versions_supported  = false;
    cap.testing_helper_marker         = false;
    return cap;
}

bool SqliteAdapter::check_final_query(const std::string& sql) const {
    return starling::is_final_query_safe(sql);
}

}  // namespace starling::persistence

#pragma once
#include "starling/adapter.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/profile_capability.hpp"
#include <filesystem>
#include <functional>
#include <memory>
#include <string>

namespace starling::persistence {

// SqliteAdapter is the local-store-sqlite Adapter implementation. open()
// creates the connection (WAL + foreign_keys=ON) and runs migrations to the
// latest version before returning, so the schema invariants (idx_statement_id_tenant,
// outbox_sequence_counter row, etc.) are guaranteed before Runtime preflight.
//
// The Adapter base deletes its move-ctor (and copy ops). open() therefore
// returns a std::unique_ptr<SqliteAdapter> so callers can hold the adapter
// without slicing or copying.
class SqliteAdapter : public starling::Adapter {
public:
    static std::unique_ptr<SqliteAdapter> open(const std::filesystem::path& db_path);

    starling::ProfileCapability declare_capability() const override;
    bool check_final_query(const std::string& sql) const override;
    [[nodiscard]] bool has_index(std::string_view name);

    // 写门钩子(P3.c write-gate):未设 → 放行(behavior-neutral by construction)。
    // 返回 bool 避免 persistence 依赖 governance。production Runtime 经
    // governance::install_write_gate 设一次:钩子内读 supervisor 健康态。
    void set_write_admit(std::function<bool()> fn) { write_admit_ = std::move(fn); }
    [[nodiscard]] bool write_admitted() const { return !write_admit_ || write_admit_(); }

    Connection& connection() noexcept { return conn_; }
    const std::filesystem::path& db_path() const noexcept { return db_path_; }

private:
    SqliteAdapter(Connection c, std::filesystem::path p)
        : conn_(std::move(c)), db_path_(std::move(p)) {}
    Connection conn_;
    std::filesystem::path db_path_;
    std::function<bool()> write_admit_;
};

}  // namespace starling::persistence

#pragma once
#include "starling/persistence/sqlite_adapter.hpp"
#include <cstdint>
#include <string>
#include <string_view>

namespace starling::projection {

struct MaintainerStats { int events_processed=0; int rows_upserted=0; };

struct RebuildReport {
    std::string projection_name;
    int64_t ground_truth_count=0;
    int64_t rebuilt_count=0;
    bool truncation_suspected=false;
};

class ProjectionMaintainer {  // Outbox subscriber
public:
    explicit ProjectionMaintainer(persistence::SqliteAdapter& adapter);
    // 消费 statement.written/derived/archived/consolidated → 增量更新投影 + checkpoint.
    MaintainerStats tick_one_batch(persistence::Connection& conn, std::string_view now_iso);
    // 全量 rebuild + repair guard — Task 27.
    RebuildReport rebuild_projection(persistence::Connection& conn,
                                     std::string_view projection_name, std::string_view now_iso);
private:
    persistence::SqliteAdapter& adapter_;
};

}  // namespace starling::projection

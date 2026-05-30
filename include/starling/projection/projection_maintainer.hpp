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
    // 测试钩子: 注入一个 rebuilt_count 以触发 truncation 路径 (TC-PROJECTION-REPAIR).
    // prod 不调. injected_rebuilt < ground_truth → truncation_suspected + 不替换 active.
    RebuildReport rebuild_projection_with_injected_count(
        persistence::Connection& conn, std::string_view projection_name,
        int64_t injected_rebuilt, std::string_view now_iso);

    // Python binding helper.
    persistence::Connection& connection() { return adapter_.connection(); }

private:
    persistence::SqliteAdapter& adapter_;
    RebuildReport do_rebuild(persistence::Connection& conn,
                             std::string_view projection_name,
                             int64_t rebuilt_override,
                             std::string_view now_iso);
};

}  // namespace starling::projection

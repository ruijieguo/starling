#pragma once
#include "starling/embedding/embedding_adapter.hpp"
#include "starling/vector/source_vector_index.hpp"
#include "starling/vector/vector_index.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <cstdint>
#include <filesystem>

namespace starling::embedding {

struct EmbeddingStats {
    int embedded = 0;
    int failed = 0;
    int overlaps_created = 0;
    // 左脑来源 lane（形态 S §5.5）：与语句分支分开计数，便于诊断是哪个分支
    // 在工作。两者在同一次 tick 内互不影响。
    int source_embedded = 0;
    int source_failed = 0;
};

// 最终状态与 EmbeddingStats 的尝试计数分离；全部计数仅覆盖活动声明。
struct EmbeddingHealth {
    int64_t total = 0;
    int64_t embedded = 0;
    int64_t missing = 0;
    int64_t retryable_failed = 0;
    int64_t exhausted = 0;
    int64_t invalid = 0;
    bool complete() const { return total == embedded; }
    std::string to_json() const;
};

// 无迁移、无模型调用；只接受没有 WAL/SHM 的冻结数据库。
EmbeddingHealth frozen_embedding_health(const std::filesystem::path&, int dim,
                                        std::string_view model, int max_retry = 3);

struct WorkerConfig {
    int batch_size = 32;
    int top_k_neighbors = 5;
    double theta_sep = 0.85;
    double strength = 0.5;
    int max_retry = 3;
};

class EmbeddingWorker {
public:
    // source_index 为空 = 关闭左脑来源 lane（默认），语句分支行为完全不变。
    EmbeddingWorker(persistence::SqliteAdapter& a, EmbeddingAdapter& e,
                    vector::VectorIndex& idx,
                    const WorkerConfig& worker_cfg = WorkerConfig(),
                    vector::SourceVectorIndex* source_index = nullptr)
        : adapter_(a), embedder_(e), index_(idx), cfg_(worker_cfg),
          source_index_(source_index) {}
    EmbeddingStats tick_one_batch(persistence::Connection&, std::string_view now_iso);
    EmbeddingHealth health(persistence::Connection&) const;
    persistence::Connection& connection() { return adapter_.connection(); }  // pybind helper
private:
    // source 分支：扫 pending/failed 的 unit、取 payload 里的原文、嵌入并写回。
    EmbeddingStats tick_source_units(persistence::Connection& conn_handle,
                                     std::string_view now_iso_utc);

    // worker 不拥有 adapter / embedder / index，只借用（与既有的 adapter_ 同一约定）。
    // 引用成员是刻意的：换成指针会让每一处调用点都要判空。
    // NOLINTBEGIN(cppcoreguidelines-avoid-const-or-ref-data-members)
    persistence::SqliteAdapter& adapter_;
    EmbeddingAdapter& embedder_;
    vector::VectorIndex& index_;
    // NOLINTEND(cppcoreguidelines-avoid-const-or-ref-data-members)
    WorkerConfig cfg_;
    vector::SourceVectorIndex* source_index_ = nullptr;
};

}  // namespace starling::embedding

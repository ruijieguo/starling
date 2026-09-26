#pragma once
#include "starling/embedding/embedding_adapter.hpp"
#include "starling/vector/vector_index.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <cstdint>
#include <filesystem>

namespace starling::embedding {

struct EmbeddingStats { int embedded = 0; int failed = 0; int overlaps_created = 0; };

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
    EmbeddingWorker(persistence::SqliteAdapter& a, EmbeddingAdapter& e,
                    vector::VectorIndex& idx, WorkerConfig cfg = {})
        : adapter_(a), embedder_(e), index_(idx), cfg_(cfg) {}
    EmbeddingStats tick_one_batch(persistence::Connection&, std::string_view now_iso);
    EmbeddingHealth health(persistence::Connection&) const;
    persistence::Connection& connection() { return adapter_.connection(); }  // pybind helper
private:
    persistence::SqliteAdapter& adapter_;
    EmbeddingAdapter& embedder_;
    vector::VectorIndex& index_;
    WorkerConfig cfg_;
};

}  // namespace starling::embedding

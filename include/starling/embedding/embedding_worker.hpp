#pragma once
#include "starling/embedding/embedding_adapter.hpp"
#include "starling/vector/vector_index.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

namespace starling::embedding {

struct EmbeddingStats { int embedded = 0; int failed = 0; int overlaps_created = 0; };

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
    persistence::Connection& connection() { return adapter_.connection(); }  // pybind helper
private:
    persistence::SqliteAdapter& adapter_;
    EmbeddingAdapter& embedder_;
    vector::VectorIndex& index_;
    WorkerConfig cfg_;
};

}  // namespace starling::embedding

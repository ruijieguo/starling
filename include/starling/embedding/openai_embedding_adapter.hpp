// include/starling/embedding/openai_embedding_adapter.hpp
#pragma once
#include "starling/embedding/embedding_adapter.hpp"
#include <cstddef>
#include <string>
#include <utility>
#include <vector>

namespace starling::embedding {

class OpenAIEmbeddingAdapter : public EmbeddingAdapter {
public:
    struct Config {
        std::string base_url;
        std::string api_key;                       // 仅 env 读,绝不日志/绑定 Python
        std::string model = "text-embedding-3-small";
        int dim = 1536;
        int timeout_ms = 60000;
        int max_retries = 3;
        // Per-call input cap. Default 10 batches correctly out-of-the-box on
        // BOTH OpenAI (cap 2048) and DashScope compatible-mode text-embedding-v3
        // (cap 10 — a 25-input batch 400s → per-row fallback → no speedup, MEASURED
        // 2026-07-03). Raise via EMBEDDING_MAX_BATCH on higher-cap providers.
        int max_batch_inputs = 10;
        static Config from_env();                  // throw std::runtime_error if api_key unset
    };
    explicit OpenAIEmbeddingAdapter(Config cfg) : cfg_(std::move(cfg)) {}
    EmbeddingResult embed(std::string_view text) override;
    std::vector<EmbeddingResult> embed_batch(const std::vector<std::string>& texts) override;
    int dim() const override { return cfg_.dim; }
    std::string model() const override { return cfg_.model; }

    // Pure, offline-testable helpers (static — reachable from ctest, no network).
    [[nodiscard]] static std::string
        build_embeddings_request(const std::string& model,
                                 const std::vector<std::string>& texts);
    [[nodiscard]] static std::vector<std::vector<float>>
        parse_embeddings_batch(const std::string& body, int expected_count, int expected_dim);
    [[nodiscard]] static std::vector<std::pair<std::size_t, std::size_t>>
        chunk_ranges(std::size_t count, int max_inputs);
private:
    Config cfg_;
};

}  // namespace starling::embedding

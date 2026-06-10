#include "starling/embedding/openai_embedding_adapter.hpp"

#include <cstdlib>
#include <stdexcept>
#include <string>
#include <vector>

#include <nlohmann/json.hpp>

#include "starling/net/http_post_json.hpp"

namespace starling::embedding {

OpenAIEmbeddingAdapter::Config OpenAIEmbeddingAdapter::Config::from_env() {
    Config c;
    const char* key = std::getenv("OPENAI_API_KEY");
    if (!key || *key == '\0') {
        throw std::runtime_error("OPENAI_API_KEY not set");
    }
    c.api_key = key;
    const char* base = std::getenv("OPENAI_BASE_URL");
    c.base_url = (base && *base) ? base : "https://api.openai.com/v1";
    const char* model = std::getenv("EMBEDDING_MODEL");
    if (model && *model) {
        c.model = model;
    }
    return c;
}

EmbeddingResult OpenAIEmbeddingAdapter::embed(std::string_view text) {
    nlohmann::json body = {
        {"model", cfg_.model},
        {"input", std::string(text)}
    };
    const auto r = net::http_post_json(
        cfg_.base_url + "/embeddings",
        {"Authorization: Bearer " + cfg_.api_key},
        body.dump(), cfg_.timeout_ms, cfg_.max_retries);
    if (!r.ok) {
        // Historical type split, kept on purpose: EmbeddingError marks
        // retryable failures — EmbeddingWorker catches it at its
        // mark-failed-with-retry site (embedding_worker.cpp) — while permanent
        // HTTP errors stay std::runtime_error and propagate as hard failures.
        if (r.error.rfind("permanent_", 0) == 0) {
            throw std::runtime_error(r.error);
        }
        throw EmbeddingError(r.error);
    }
    try {
        auto j = nlohmann::json::parse(r.body);
        const auto& emb = j.at("data").at(0).at("embedding");
        std::vector<float> vec;
        vec.reserve(emb.size());
        for (const auto& x : emb) {
            vec.push_back(x.get<float>());
        }
        return {std::move(vec), cfg_.dim, cfg_.model};
    } catch (const std::exception&) {
        throw std::runtime_error("malformed_response");
    }
}

}  // namespace starling::embedding

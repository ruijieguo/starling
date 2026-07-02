#include "starling/embedding/openai_embedding_adapter.hpp"

#include <algorithm>
#include <cstddef>
#include <cstdlib>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include <nlohmann/json.hpp>

#include "starling/net/http_post_json.hpp"

namespace starling::embedding {

namespace {
// Map a failed HttpResult to the historical type split: permanent_<code> → hard
// std::runtime_error; everything else (transient_after_retry / transport_error)
// → retryable EmbeddingError. No-op when resp.ok.
void throw_for_http_error(const net::HttpResult& resp) {
    if (resp.ok) {
        return;
    }
    if (resp.error.starts_with("permanent_")) {
        throw std::runtime_error(resp.error);
    }
    throw EmbeddingError(resp.error);
}
}  // namespace

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
    const char* max_batch = std::getenv("EMBEDDING_MAX_BATCH");
    if (max_batch != nullptr && *max_batch != '\0') {
        std::istringstream iss{std::string(max_batch)};
        int parsed = 0;
        if ((iss >> parsed) && parsed > 0) {
            c.max_batch_inputs = parsed;
        }
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
    throw_for_http_error(r);
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

std::string
OpenAIEmbeddingAdapter::build_embeddings_request(const std::string& model,
                                                 const std::vector<std::string>& texts) {
    nlohmann::json input = nlohmann::json::array();
    for (const auto& text : texts) {
        input.push_back(text);
    }
    nlohmann::json body = {{"model", model}, {"input", std::move(input)}};
    return body.dump();
}

std::vector<std::pair<std::size_t, std::size_t>>
OpenAIEmbeddingAdapter::chunk_ranges(std::size_t count, int max_inputs) {
    const std::size_t step = max_inputs > 0 ? static_cast<std::size_t>(max_inputs) : 1;
    std::vector<std::pair<std::size_t, std::size_t>> ranges;
    for (std::size_t start = 0; start < count; start += step) {
        ranges.emplace_back(start, std::min(count, start + step));
    }
    return ranges;
}

std::vector<std::vector<float>>
OpenAIEmbeddingAdapter::parse_embeddings_batch(const std::string& body,
                                               int expected_count, int expected_dim) {
    if (expected_count < 0) {  // defensive: public static; a negative count would huge-alloc
        throw std::runtime_error("malformed_response");
    }
    std::vector<std::vector<float>> out(static_cast<std::size_t>(expected_count));
    std::vector<bool> seen(static_cast<std::size_t>(expected_count), false);
    try {
        const auto parsed = nlohmann::json::parse(body);
        const auto& data = parsed.at("data");
        if (static_cast<int>(data.size()) != expected_count) {
            throw std::runtime_error("count");
        }
        for (const auto& item : data) {
            const int index = item.at("index").get<int>();
            if (index < 0 || index >= expected_count || seen[static_cast<std::size_t>(index)]) {
                throw std::runtime_error("index");
            }
            const auto& emb = item.at("embedding");
            if (expected_dim > 0 && static_cast<int>(emb.size()) != expected_dim) {
                throw std::runtime_error("dim");
            }
            std::vector<float> vec;
            vec.reserve(emb.size());
            for (const auto& elem : emb) {
                vec.push_back(elem.get<float>());
            }
            out[static_cast<std::size_t>(index)] = std::move(vec);
            seen[static_cast<std::size_t>(index)] = true;
        }
    } catch (const std::exception&) {
        // Any structural problem (parse error, missing/short data, bad index,
        // wrong dim) → one normalized hard failure; never a silent short-write.
        throw std::runtime_error("malformed_response");
    }
    return out;
}

std::vector<EmbeddingResult>
OpenAIEmbeddingAdapter::embed_batch(const std::vector<std::string>& texts) {
    std::vector<EmbeddingResult> out;
    out.reserve(texts.size());
    for (const auto& [start, end] : chunk_ranges(texts.size(), cfg_.max_batch_inputs)) {
        std::vector<std::string> chunk(texts.begin() + static_cast<std::ptrdiff_t>(start),
                                       texts.begin() + static_cast<std::ptrdiff_t>(end));
        const auto resp = net::http_post_json(
            cfg_.base_url + "/embeddings",
            {"Authorization: Bearer " + cfg_.api_key},
            build_embeddings_request(cfg_.model, chunk), cfg_.timeout_ms, cfg_.max_retries);
        throw_for_http_error(resp);
        auto vecs = parse_embeddings_batch(resp.body, static_cast<int>(end - start), cfg_.dim);
        for (auto& vec : vecs) {
            out.push_back(EmbeddingResult{.vector = std::move(vec), .dim = cfg_.dim,
                                          .model = cfg_.model});
        }
    }
    return out;
}

}  // namespace starling::embedding

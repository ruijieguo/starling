// include/starling/embedding/openai_embedding_adapter.hpp
#pragma once
#include "starling/embedding/embedding_adapter.hpp"
#include <string>
#include <utility>

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
        static Config from_env();                  // throw std::runtime_error if api_key unset
    };
    explicit OpenAIEmbeddingAdapter(Config cfg) : cfg_(std::move(cfg)) {}
    EmbeddingResult embed(std::string_view text) override;
    int dim() const override { return cfg_.dim; }
    std::string model() const override { return cfg_.model; }
private:
    Config cfg_;
};

}  // namespace starling::embedding

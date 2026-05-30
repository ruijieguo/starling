// include/starling/embedding/embedding_adapter.hpp
#pragma once
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace starling::embedding {

struct EmbeddingResult { std::vector<float> vector; int dim = 0; std::string model; };

// 抛此表示可重试失败（网络/5xx/429）。
struct EmbeddingError : std::runtime_error { using std::runtime_error::runtime_error; };

class EmbeddingAdapter {
public:
    virtual ~EmbeddingAdapter() = default;
    virtual EmbeddingResult embed(std::string_view text) = 0;
    virtual int dim() const = 0;
    virtual std::string model() const = 0;
};

// 测试专用:从文本 hash 种子生成确定性单位向量。零 live API。
class StubEmbeddingAdapter : public EmbeddingAdapter {
public:
    explicit StubEmbeddingAdapter(int dim = 8) : dim_(dim) {}
    EmbeddingResult embed(std::string_view text) override;
    int dim() const override { return dim_; }
    std::string model() const override { return "stub"; }
    // 测试钩子:让指定文本一次性抛 EmbeddingError（验证 worker 重试路径）。
    void fail_next(std::string_view text) { fail_text_ = std::string(text); }
private:
    int dim_;
    std::string fail_text_;
};

}  // namespace starling::embedding

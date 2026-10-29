// include/starling/vector/vector_index.hpp
#pragma once
#include <optional>
#include <string>
#include <string_view>
#include <vector>
#include "starling/persistence/connection.hpp"

namespace starling::vector {

struct ScoredId { std::string stmt_id; double score; };  // score = cosine

struct SearchScope {
    std::string tenant_id;
    std::optional<std::string> holder_id;
    std::optional<std::string> holder_perspective;
    bool visible_only = true;  // consolidation_state IN(consolidated,archived) + review_status 过滤
    // 仅在 visible_only 时生效:巩固状态那一段额外放进 'volatile'(只嵌入、未经
    // tick 回放的语句)。volatile 是巩固状态,不是隐私状态:review_status 守卫与
    // holder/perspective 谓词不受它影响,照旧收紧。默认 false,既有调用方不变。
    bool include_volatile = false;
};

class VectorIndex {
public:
    virtual ~VectorIndex() = default;
    virtual void insert(persistence::Connection&, std::string_view stmt_id,
                        std::string_view tenant_id, const std::vector<float>& vec) = 0;
    virtual std::vector<ScoredId> search_topk(persistence::Connection&,
                        const std::vector<float>& query, int k, const SearchScope&) = 0;
    virtual void remove(persistence::Connection&, std::string_view stmt_id,
                        std::string_view tenant_id) = 0;
};

// 后端 = statement_vectors.index_vector (BLOB) + 暴力 cosine。
class SqliteBlobVectorIndex : public VectorIndex {
public:
    void insert(persistence::Connection&, std::string_view stmt_id,
                std::string_view tenant_id, const std::vector<float>& vec) override;
    std::vector<ScoredId> search_topk(persistence::Connection&,
                const std::vector<float>& query, int k, const SearchScope&) override;
    void remove(persistence::Connection&, std::string_view stmt_id,
                std::string_view tenant_id) override;
};

}  // namespace starling::vector

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

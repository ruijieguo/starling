#include "starling/vector/zvec_vector_index.hpp"

#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/persistence/sqlite_helpers.hpp"

#include <zvec/db/collection.h>
#include <zvec/db/doc.h>
#include <zvec/db/index_params.h>
#include <zvec/db/query.h>
#include <zvec/db/schema.h>

#include <sqlite3.h>

#include <cctype>
#include <memory>
#include <stdexcept>
#include <unordered_set>

namespace starling::vector {

using persistence::StmtHandle;
using persistence::detail::bind_sv;
using persistence::detail::make_sqlite_error;

namespace {

constexpr const char* kVecField = "dense";
// KNN over-fetch 倍数:zvec 多取候选,SQL scope 精过滤后取 k(候选被 holder/state
// 精过滤掉时仍尽量凑足 k)。
constexpr int kOverFetch = 4;

zvec::CollectionSchema make_schema(int dim) {
    zvec::CollectionSchema schema("starling_vectors");
    // tenant_id:粗过滤属性(zvec filter,InvertIndex 加速)。
    schema.add_field(std::make_shared<zvec::FieldSchema>(
        "tenant_id", zvec::DataType::STRING, /*nullable=*/false,
        std::make_shared<zvec::InvertIndexParams>(false)));
    // dense:向量字段,HNSW + COSINE(对齐 SqliteBlobVectorIndex 的 cosine)。
    schema.add_field(std::make_shared<zvec::FieldSchema>(
        kVecField, zvec::DataType::VECTOR_FP32, static_cast<std::uint32_t>(dim),
        /*nullable=*/false,
        std::make_shared<zvec::HnswIndexParams>(zvec::MetricType::COSINE)));
    return schema;
}

}  // namespace

ZvecVectorIndex::ZvecVectorIndex(const std::string& store_path, int dimension)
    : dim_(dimension) {
    auto schema = make_schema(dimension);
    auto created =
        zvec::Collection::CreateAndOpen(store_path, schema, zvec::CollectionOptions{});
    if (created.has_value()) {
        coll_ = std::move(created).value();
        return;
    }
    // 已存在 → Open(重启复用)。
    auto opened = zvec::Collection::Open(store_path, zvec::CollectionOptions{});
    if (!opened.has_value())
        throw std::runtime_error("ZvecVectorIndex: open '" + store_path +
                                 "' failed: " + opened.error().message());
    coll_ = std::move(opened).value();
}

ZvecVectorIndex::~ZvecVectorIndex() = default;

void ZvecVectorIndex::insert(persistence::Connection& /*conn*/,
                             std::string_view stmt_id, std::string_view tenant_id,
                             const std::vector<float>& vec) {
    if (static_cast<int>(vec.size()) != dim_)
        throw std::runtime_error("ZvecVectorIndex::insert: vector dim mismatch (got " +
                                 std::to_string(vec.size()) + ", expect " +
                                 std::to_string(dim_) + ")");
    zvec::Doc doc;
    doc.set_pk(std::string(stmt_id));
    doc.set<std::string>("tenant_id", std::string(tenant_id));
    doc.set<std::vector<float>>(kVecField, vec);
    std::vector<zvec::Doc> docs{std::move(doc)};
    auto r = coll_->Upsert(docs);
    if (!r.has_value())
        throw std::runtime_error("ZvecVectorIndex::insert: " + r.error().message());
}

std::vector<ScoredId> ZvecVectorIndex::search_topk(persistence::Connection& conn,
                                                   const std::vector<float>& query,
                                                   int k, const SearchScope& scope) {
    if (k <= 0) return {};

    // ① zvec KNN:tenant 粗过滤 + over-fetch。query 向量序列化为字节串。
    zvec::SearchQuery q;
    q.topk_ = k * kOverFetch;
    q.target_.field_name_ = kVecField;
    q.target_.set_vector(std::string(reinterpret_cast<const char*>(query.data()),
                                     query.size() * sizeof(float)));
    // zvec filter 是 SQL-like 字符串 DSL(无参数化绑定 API):tenant_id 拼入字符串
    // 字面 → 字符 allowlist 防 filter 注入(跨租户绕过)。tenant 是内部标识,异常
    // 字符即拒绝;tenant 隔离的第二层防御=下方 SQL 精过滤的参数化 s.tenant_id=?。
    for (const char c : scope.tenant_id) {
        const auto uc = static_cast<unsigned char>(c);
        if (!(std::isalnum(uc) || c == '_' || c == '-' || c == ':' || c == '.'))
            throw std::runtime_error(
                "ZvecVectorIndex: tenant_id has disallowed char (filter injection guard)");
    }
    q.filter_ = "tenant_id = '" + scope.tenant_id + "'";
    auto r = coll_->Query(q);
    if (!r.has_value())
        throw std::runtime_error("ZvecVectorIndex::search_topk: " +
                                 r.error().message());
    const auto& docs = r.value();
    if (docs.empty()) return {};

    // 候选(zvec KNN 顺序 = 相似度降序)。
    std::vector<ScoredId> cand;
    cand.reserve(docs.size());
    for (const auto& d : docs) cand.push_back({d->pk(), d->score()});

    // ② SQL 精过滤 scope(holder/perspective/visibility):实时 JOIN statements 取
    //    最新 state,逐字对齐 SqliteBlobVectorIndex。候选 id IN(...) + scope 谓词。
    std::string sql =
        "SELECT s.id FROM statements s"
        " WHERE s.tenant_id = ?"
        "   AND s.id IN (";
    for (std::size_t i = 0; i < cand.size(); ++i) sql += (i ? ",?" : "?");
    sql +=
        ")"
        "   AND (? = '' OR s.holder_id = ?)"
        "   AND (? = '' OR s.holder_perspective = ?)"
        "   AND (? = 0 OR (s.consolidation_state IN ('consolidated','archived')"
        "                  AND s.review_status NOT IN ('rejected','pending_review')))";

    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(conn.raw(), sql.c_str(), -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(conn.raw(), "ZvecVectorIndex::search_topk prepare");
    StmtHandle h(raw);

    int idx = 1;
    bind_sv(h.get(), idx++, scope.tenant_id);
    for (const auto& c : cand) bind_sv(h.get(), idx++, c.stmt_id);
    const std::string holder = scope.holder_id.value_or("");
    bind_sv(h.get(), idx++, holder);
    bind_sv(h.get(), idx++, holder);
    const std::string persp = scope.holder_perspective.value_or("");
    bind_sv(h.get(), idx++, persp);
    bind_sv(h.get(), idx++, persp);
    sqlite3_bind_int(h.get(), idx++, scope.visible_only ? 1 : 0);

    std::unordered_set<std::string> passed;
    while (sqlite3_step(h.get()) == SQLITE_ROW) {
        const auto* p = sqlite3_column_text(h.get(), 0);
        if (p) passed.insert(reinterpret_cast<const char*>(p));
    }

    // 按 zvec KNN 顺序(相似度降序)保留通过 scope 的候选,取前 k。
    std::vector<ScoredId> out;
    out.reserve(static_cast<std::size_t>(k));
    for (const auto& c : cand) {
        if (passed.count(c.stmt_id)) {
            out.push_back(c);
            if (static_cast<int>(out.size()) >= k) break;
        }
    }
    return out;
}

void ZvecVectorIndex::remove(persistence::Connection& /*conn*/,
                             std::string_view stmt_id,
                             std::string_view /*tenant_id*/) {
    std::vector<std::string> pks{std::string(stmt_id)};
    auto r = coll_->Delete(pks);
    if (!r.has_value())
        throw std::runtime_error("ZvecVectorIndex::remove: " + r.error().message());
}

}  // namespace starling::vector

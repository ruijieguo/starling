#include "starling/vector/source_vector_index.hpp"

#include "starling/vector/vector_math.hpp"
#include "starling/persistence/sqlite_helpers.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <sqlite3.h>

#include <algorithm>
#include <utility>
#include <ranges>
#include <cstddef>
#include <string>
#include <string_view>
#include <vector>

namespace starling::vector {

using starling::persistence::detail::bind_sv;
using starling::persistence::detail::make_sqlite_error;
using starling::persistence::StmtHandle;

namespace {

// 每条可见 engram 一个占位符；IN (...) 的参数个数取决于集合大小。
std::string placeholders(std::size_t count, int first_index) {
    std::string out;
    for (std::size_t i = 0; i < count; ++i) {
        if (i != 0) {
            out.push_back(',');
        }
        out.push_back('?');
        out += std::to_string(first_index + static_cast<int>(i));
    }
    return out;
}

std::string column_text(sqlite3_stmt* stmt, int column) {
    const unsigned char* text = sqlite3_column_text(stmt, column);
    // NOLINTNEXTLINE(cppcoreguidelines-pro-type-reinterpret-cast)
    return text != nullptr ? std::string(reinterpret_cast<const char*>(text)) : std::string();
}

}  // namespace

void SqliteSourceVectorIndex::upsert(
    persistence::Connection& conn,
    const SourceUnitKey& key,
    // 元数据权威副本由写入方（retain_source_turns）落 source_unit_meta；本后端只写
    // 派生索引。保留该参数是为了后端可移植——未来 zvec/外部向量库需要把 speaker 等
    // 冗余进自己的记录，SQLite 版靠 JOIN 取，故此处不用。
    [[maybe_unused]] const SourceUnitMeta& meta,
    const std::vector<float>& vec,
    std::string_view model,
    int dim)
{
    // dim 必须与向量本身一致：不一致说明调用方搞混了模型或适配器，
    // 静默写入会让检索期按错维度比较。
    if (std::cmp_not_equal(dim, vec.size())) {
        throw std::invalid_argument("SqliteSourceVectorIndex::upsert: dim != vec.size()");
    }

    const char* sql =
        "INSERT INTO source_unit_vectors"
        "(tenant_id,engram_ref,clause_id,dim,model,index_vector,raw_embedding,"
        " status,retry_count,embedded_at)"
        " VALUES(?1,?2,?3,?4,?5,?6,?6,'embedded',0,?7)"
        " ON CONFLICT(tenant_id,engram_ref,clause_id) DO UPDATE SET"
        "   dim=excluded.dim,"
        "   model=excluded.model,"
        "   index_vector=excluded.index_vector,"
        "   raw_embedding=excluded.raw_embedding,"
        "   status='embedded',"
        // 一次成功嵌入就是一次成功尝试：重试计数归零，否则退避状态会跟着
        // 这条 unit 走进"已嵌入却仍记为失败过"的矛盾态。
        "   retry_count=0,"
        "   last_attempt_at=NULL,"
        "   embedded_at=excluded.embedded_at";

    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(conn.raw(), "SqliteSourceVectorIndex::upsert prepare");
    }
    StmtHandle handle(raw);

    bind_sv(handle.get(), 1, key.tenant_id);
    bind_sv(handle.get(), 2, key.engram_ref);
    bind_sv(handle.get(), 3, key.clause_id);
    sqlite3_bind_int(handle.get(), 4, dim);
    bind_sv(handle.get(), 5, model);

    const std::string blob = to_blob(vec);
    sqlite3_bind_blob(handle.get(), 6, blob.data(), static_cast<int>(blob.size()), SQLITE_TRANSIENT);
    // embedded_at 只作审计，不参与排序或授权，用写入时刻即可。
    bind_sv(handle.get(), 7, "1970-01-01T00:00:00Z");

    if (sqlite3_step(handle.get()) != SQLITE_DONE) {
        throw make_sqlite_error(conn.raw(), "SqliteSourceVectorIndex::upsert step");
    }
}

std::vector<SourceVectorHit> SqliteSourceVectorIndex::search(
    persistence::Connection& conn,
    const std::vector<float>& query,
    int top_k,
    const SourceSearchScope& scope)
{
    // 空可见集 = 什么都没授权（fail closed）。直接在 SQL 之前返回，
    // 避免把"空 IN ()"变成"不过滤"。
    if (top_k <= 0 || query.empty()) {
        return {};
    }

    // 过滤顺序刻意与排序无关：可见集、租户、状态、维度、时间全部在 SQL 里，
    // 出库的每一行都已是合格候选。
    const std::string visible_placeholders =
        placeholders(scope.visible_engrams.size(), 5);
    const std::string sql =
        "SELECT m.engram_ref, m.clause_id, m.speaker, m.session_id, m.observed_at,"
        "       v.index_vector"
        " FROM source_unit_vectors v"
        " JOIN source_unit_meta m ON m.tenant_id = v.tenant_id"
        "   AND m.engram_ref = v.engram_ref AND m.clause_id = v.clause_id"
        " JOIN engrams e ON e.id = v.engram_ref AND e.tenant_id = v.tenant_id"
        " WHERE v.tenant_id = ?1 AND v.status = 'embedded' AND v.dim = ?2"
        // 擦除与保留策略：与 source_retriever.cpp:1497-1498 对齐。擦除后
        // 读侧立即不可见，不等异步清理。
        "   AND e.erased_at IS NULL AND e.retention_mode = 'audit_retain'"
        "   AND e.payload_inline IS NOT NULL"
        // 时间三重界里的 unit 级两界（as_of 上界、无可信时间是否放行）在 SQL 内完成
        // ——若留到 C++ 再判，NULL 行已经被 WHERE 丢掉，include_unknown_time 永远无效。
        "   AND ((m.observed_at IS NOT NULL AND (?3 = '' OR m.observed_at <= ?3))"
        "        OR (?4 = 1 AND m.observed_at IS NULL))"
        // 时间三重界：as_of 同时约束 engram 创建时刻与每句 observed_at。
        "   AND (?3 = '' OR julianday(e.created_at) <= julianday(?3))"
        "   AND v.engram_ref IN (" + visible_placeholders + ")"
        " ORDER BY v.engram_ref, v.clause_id";

    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(conn.raw(), sql.c_str(), -1, &raw, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(conn.raw(), "SqliteSourceVectorIndex::search prepare");
    }
    StmtHandle handle(raw);

    bind_sv(handle.get(), 1, scope.tenant_id);
    sqlite3_bind_int(handle.get(), 2, static_cast<int>(query.size()));
    bind_sv(handle.get(), 3, scope.as_of);
    sqlite3_bind_int(handle.get(), 4, scope.include_unknown_time ? 1 : 0);
    int index = 5;
    for (const auto& engram : scope.visible_engrams) {
        bind_sv(handle.get(), index, engram);
        ++index;
    }

    std::vector<SourceVectorHit> hits;
    while (sqlite3_step(handle.get()) == SQLITE_ROW) {
        const void* blob = sqlite3_column_blob(handle.get(), 5);
        const int blob_bytes = sqlite3_column_bytes(handle.get(), 5);
        if (blob == nullptr || blob_bytes <= 0) {
            continue;
        }

        // NOLINTNEXTLINE(cppcoreguidelines-pro-type-reinterpret-cast)
        const auto* bytes = reinterpret_cast<const char*>(blob);
        const std::vector<float> vec = from_blob(std::string(bytes, static_cast<std::size_t>(blob_bytes)));
        if (vec.size() != query.size()) {
            continue;
        }

        SourceVectorHit hit;
        hit.engram_ref = column_text(handle.get(), 0);
        hit.clause_id = column_text(handle.get(), 1);
        hit.speaker = column_text(handle.get(), 2);
        hit.session_id = column_text(handle.get(), 3);
        hit.score = cosine(query, vec);
        hits.push_back(std::move(hit));
    }

    std::ranges::sort(hits, [](const SourceVectorHit& lhs, const SourceVectorHit& rhs) {
        return lhs.score > rhs.score;
    });
    if (std::cmp_greater(hits.size(), top_k)) {
        hits.resize(static_cast<std::size_t>(top_k));
    }
    return hits;
}

// NOLINTNEXTLINE(bugprone-easily-swappable-parameters)
void SqliteSourceVectorIndex::erase(
    persistence::Connection& conn,
    std::string_view tenant_id,
    std::string_view engram_ref)
{
    const char* sql =
        "DELETE FROM source_unit_vectors WHERE tenant_id = ?1 AND engram_ref = ?2";

    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(conn.raw(), "SqliteSourceVectorIndex::erase prepare");
    }
    StmtHandle handle(raw);

    bind_sv(handle.get(), 1, tenant_id);
    bind_sv(handle.get(), 2, engram_ref);

    if (sqlite3_step(handle.get()) != SQLITE_DONE) {
        throw make_sqlite_error(conn.raw(), "SqliteSourceVectorIndex::erase step");
    }
}

}  // namespace starling::vector

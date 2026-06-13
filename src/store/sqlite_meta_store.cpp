#include "starling/store/sqlite_meta_store.hpp"

#include <sqlite3.h>

#include <string>
#include <vector>

#include "starling/persistence/sqlite_handles.hpp"
#include "starling/persistence/sqlite_helpers.hpp"

namespace starling::store {

using persistence::StmtHandle;
using persistence::detail::bind_sv;
using persistence::detail::make_sqlite_error;

namespace {

// 24 列 = retrieval::StatementRow 20 字段 + 4 个收编扩展列(salience/activation/
// provenance/nesting_depth)。read_row 顺序与此一致。
constexpr const char* kCols =
    "id, tenant_id, holder_id, holder_perspective, subject_kind, subject_id, "
    "predicate, object_kind, object_value, canonical_object_hash, modality, "
    "polarity, confidence, observed_at, valid_from, valid_to, "
    "consolidation_state, review_status, evidence_json, affect_json, "
    "salience, activation, provenance, nesting_depth";

retrieval::StatementRow read_row(sqlite3_stmt* h) {
    auto t = [&](int i) -> std::string {
        const auto* p = sqlite3_column_text(h, i);
        return p ? std::string(reinterpret_cast<const char*>(p)) : std::string();
    };
    retrieval::StatementRow r;
    r.id = t(0); r.tenant_id = t(1); r.holder_id = t(2); r.holder_perspective = t(3);
    r.subject_kind = t(4); r.subject_id = t(5); r.predicate = t(6);
    r.object_kind = t(7); r.object_value = t(8); r.canonical_object_hash = t(9);
    r.modality = t(10); r.polarity = t(11);
    r.confidence = sqlite3_column_double(h, 12);
    r.observed_at = t(13); r.valid_from = t(14); r.valid_to = t(15);
    r.consolidation_state = t(16); r.review_status = t(17);
    r.evidence_json = t(18); r.affect_json = t(19);
    r.salience = sqlite3_column_double(h, 20);
    r.activation = sqlite3_column_double(h, 21);
    r.provenance = t(22);
    r.nesting_depth = sqlite3_column_int(h, 23);
    return r;
}

}  // namespace

std::optional<retrieval::StatementRow> SqliteMetaStore::get_statement(
    std::string_view id, std::string_view tenant) {
    sqlite3* db = conn_.raw();
    const std::string sql = std::string("SELECT ") + kCols +
        " FROM statements WHERE id=?1 AND tenant_id=?2 LIMIT 1";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql.c_str(), -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "MetaStore::get_statement prepare");
    StmtHandle h(raw);
    bind_sv(h.get(), 1, id);
    bind_sv(h.get(), 2, tenant);
    if (sqlite3_step(h.get()) == SQLITE_ROW) return read_row(h.get());
    return std::nullopt;
}

std::vector<retrieval::StatementRow> SqliteMetaStore::query_statements(
    const StatementFilter& f) {
    sqlite3* db = conn_.raw();
    std::string sql = std::string("SELECT ") + kCols +
        " FROM statements WHERE tenant_id = ?";
    std::vector<std::string> binds{f.tenant_id};   // 顺序文本绑定

    auto eq = [&](const char* col, const std::string& v) {
        if (!v.empty()) { sql += " AND "; sql += col; sql += " = ?"; binds.push_back(v); }
    };
    eq("holder_id", f.holder_id);
    eq("subject_kind", f.subject_kind);
    eq("subject_id", f.subject_id);
    eq("predicate", f.predicate);
    eq("modality", f.modality);
    eq("object_kind", f.object_kind);
    eq("holder_perspective", f.holder_perspective);
    eq("provenance", f.provenance);

    auto in_clause = [&](const char* col, const std::vector<std::string>& vs) {
        if (vs.empty()) return;
        sql += " AND "; sql += col; sql += " IN (";
        for (std::size_t i = 0; i < vs.size(); ++i) {
            sql += (i ? ",?" : "?");
            binds.push_back(vs[i]);
        }
        sql += ")";
    };
    in_clause("predicate", f.predicate_in);
    in_clause("id", f.id_in);
    // 状态:默认 {consolidated,archived};显式覆盖。
    in_clause("consolidation_state",
              f.consolidation_states.empty()
                  ? std::vector<std::string>{"consolidated", "archived"}
                  : f.consolidation_states);
    if (f.default_review_guard)
        sql += " AND review_status NOT IN ('rejected','pending_review')";
    if (f.nesting_depth_ge >= 0) {
        sql += " AND nesting_depth >= ?";
        binds.push_back(std::to_string(f.nesting_depth_ge));
    }
    if (f.salience_ge >= 0.0) {
        sql += " AND salience >= ?";
        binds.push_back(std::to_string(f.salience_ge));
    }
    if (!f.as_of_iso8601.empty()) {
        sql += " AND (valid_from IS NULL OR valid_from <= ?)"
               " AND (valid_to   IS NULL OR valid_to   >  ?)";
        binds.push_back(f.as_of_iso8601);
        binds.push_back(f.as_of_iso8601);
    }
    // order_by 白名单(防注入:只接受固定值)。
    if (f.order_by == "observed_at ASC" || f.order_by == "observed_at DESC" ||
        f.order_by == "salience DESC"   || f.order_by == "created_at ASC" ||
        f.order_by == "salience DESC, created_at ASC")
        sql += " ORDER BY " + f.order_by;
    if (f.limit > 0) sql += " LIMIT " + std::to_string(f.limit);

    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql.c_str(), -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "MetaStore::query_statements prepare");
    StmtHandle h(raw);
    for (std::size_t i = 0; i < binds.size(); ++i)
        bind_sv(h.get(), static_cast<int>(i) + 1, binds[i]);
    std::vector<retrieval::StatementRow> out;
    while (sqlite3_step(h.get()) == SQLITE_ROW) out.push_back(read_row(h.get()));
    return out;
}

}  // namespace starling::store

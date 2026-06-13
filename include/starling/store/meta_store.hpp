#pragma once
// MetaStore —— 文本/Meta 类的读接口(P3.b1 phase 3)。纯 statements 单表读
// 收编(点查 get_statement + 多行查 query_statements);跨表 JOIN / 聚合 /
// EXISTS 的专用检索查询(frontier、向量、图、commitment 子查询)保留在各
// 子系统(非纯 statements 读,换引擎时各 backend 本就需专门实现)。
//
// 写收编在 StatementStore(phase 2)。MetaStore 读 + StatementStore 写共同
// 构成 local-store 的文本/Meta 存储接口;backend 实现两者。
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include "starling/retrieval/statement_row.hpp"

namespace starling::store {

// 覆盖纯 statements 单表读的 WHERE 模式。空/默认 = 不约束。
struct StatementFilter {
    std::string tenant_id;                          // 必填
    std::string holder_id;
    std::string subject_kind;
    std::string subject_id;
    std::string predicate;
    std::vector<std::string> predicate_in;          // predicate IN(...)
    std::string modality;
    std::string object_kind;
    std::string holder_perspective;
    std::string provenance;
    int nesting_depth_ge = -1;                      // >=0 时启用 nesting_depth >= ?
    double salience_ge = -1.0;                      // >=0 时启用 salience >= ?(affect buffer)
    // 状态:空 = 默认 {consolidated,archived};显式设覆盖(如 {"volatile"})。
    std::vector<std::string> consolidation_states;
    bool default_review_guard = true;               // review NOT IN(rejected,pending_review)
    std::string as_of_iso8601;                      // valid_from<=as_of AND valid_to>as_of
    std::vector<std::string> id_in;                 // id IN(...)
    std::string order_by;                           // 白名单:observed_at ASC|DESC / salience DESC / created_at ASC
    int limit = 0;                                  // 0 = 无限制
};

class MetaStore {
public:
    virtual ~MetaStore() = default;
    // 点查:WHERE id=? AND tenant_id=?。无则 nullopt。
    virtual std::optional<retrieval::StatementRow> get_statement(
        std::string_view id, std::string_view tenant) = 0;
    // 多行查:按 StatementFilter 动态组装(参数化绑定,无 SQL 注入面)。
    virtual std::vector<retrieval::StatementRow> query_statements(
        const StatementFilter&) = 0;
};

}  // namespace starling::store

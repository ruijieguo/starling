#include "starling/memory/memory_digest.hpp"

#include <sqlite3.h>

#include <algorithm>
#include <cstddef>
#include <optional>
#include <set>
#include <span>
#include <string>
#include <tuple>
#include <utility>
#include <vector>

#include <nlohmann/json.hpp>

#include "starling/crypto/sha256.hpp"
#include "starling/persistence/stmt.hpp"

namespace starling::memoryops {

namespace {

using Json = nlohmann::json;

// 下面三个列名名单都做成函数内 static const,不用命名空间级的全局:set 的构造会分配
// 内存、可能抛异常,放在静态存储期里抛了就没人接得住(cert-err58-cpp)。函数内静态
// 首次调用才构造,抛了就是一次普通的异常,线程安全由 C++ 的局部静态初始化保证。
using NameSet = std::set<std::string, std::less<>>;

// 簿记列:同一段内容在两个库里这些列必然不同(自增计数、墙钟、批次 id),或者是
// 行身份本身(id / stmt_id——身份正是摘要要换掉的东西)。设计源 4.5 节的清单。
// tenant_id 也排除:查询已用 WHERE tenant_id=?1 划定了作用域,若再把它折进每一行,
// 摘要就绑在 tenant 的名字上,同一段内容换个 tenant 名就成了另一个摘要。
// 排除是白名单的反面:这里没列到的列一律进摘要,包括将来新加的列。漏算一列会让
// 两个不同的库共用一个 config_hash;多算一列只会多判一次「不是同一个实验」。
const NameSet& excluded_columns() {
    static const NameSet columns = {
        "id", "stmt_id", "created_at", "updated_at", "last_accessed", "access_count",
        "last_replayed", "replay_count", "last_replay_batch_id", "retry_count",
        "last_attempt_at", "embedded_at", "inferred_at", "tenant_id",
    };
    return columns;
}

// 内容里嵌了 engram UUID 的语句列。键为 engram_ref / evidence_engram_ref 的值要换成
// engram 的 content_hash,否则两个库写同一段话也摘要不同(探针:这两列加
// events.engram_ref 是同内容两库间唯一剩下的差异)。
const NameSet& statement_json_columns() {
    static const NameSet columns = {
        "evidence_json", "source_spans_json", "semantic_claim_json",
        "confidence_history_json",
    };
    return columns;
}

// 引用列:指向另一条语句。不进内容 id(否则沿取代链递归,被指向行的内容 id 又要先
// 算出来),由摘要那一层加回来、UUID 换成被指向行的内容 id。
const NameSet& reference_columns() {
    static const NameSet columns = {
        "supersedes_id", "derived_from_json",
    };
    return columns;
}

// 生命周期列:语句写下之后后台还会改的状态——在线回放巩固(consolidation_state)、复核
// (review_status)、置信度修正(confidence 与它的历史)、显著性继承(salience、affect_json)、
// 巩固摘要。语句说的事没变,所以不进内容 id:内容 id 会写进调用方的 prompt 与轨迹,同一条
// 语句巩固前后必须是同一个 id(否则第三次写入触发在线回放后,召回给出的 id 就与写入时返回的
// 对不上)。但它们影响召回与排序,所以照旧进摘要,由摘要那一层与引用列一起加回来。
// 只有这些列被单列;没列到的列默认仍进内容 id,与排除清单「漏一列宁可过敏」同一口径。
const NameSet& lifecycle_columns() {
    static const NameSet columns = {
        "consolidation_state", "review_status", "confidence", "confidence_history_json",
        "salience", "affect_json", "consolidation_summary",
    };
    return columns;
}

bool in_set(const NameSet& columns, std::string_view name) {
    return columns.contains(name);
}

// obj[key] = value 的等价写法,但不经 operator[](cppcoreguidelines-pro-bounds-avoid-
// unchecked-container-access 对任何类的 operator[] 一律报)。键已存在就覆盖,不存在就插入,
// 与 operator[] 的语义一致。
void set_field(Json& obj, std::string key, Json value) {
    if (const auto found = obj.find(key); found != obj.end()) {
        *found = std::move(value);
    } else {
        obj.emplace(std::move(key), std::move(value));
    }
}

// 小写十六进制,逐字节两个字符:高半字节在前。先转成 unsigned 再移位/掩码——unsigned
// char 直接参与 >> 会先提升成 int,按有符号数做位运算(bugprone-signed-bitwise)。
std::string hex_lower(std::span<const unsigned char> bytes) {
    constexpr std::string_view kDigits = "0123456789abcdef";
    std::string out;
    out.reserve(bytes.size() * 2);
    for (const unsigned char byte : bytes) {
        const unsigned value = byte;
        out.push_back(kDigits.at(value >> 4U));
        out.push_back(kDigits.at(value & 0x0FU));
    }
    return out;
}

// 一个单元格 → JSON 值。NULL → null,INTEGER → 整数,REAL → 浮点原样,
// BLOB → 小写十六进制串(向量是 float32 紧凑小端,逐字节比),其余按 TEXT。
Json cell_to_json(sqlite3_stmt* stmt, int col) {
    switch (sqlite3_column_type(stmt, col)) {
        case SQLITE_NULL:
            return nullptr;
        case SQLITE_INTEGER:
            return sqlite3_column_int64(stmt, col);
        case SQLITE_FLOAT:
            return sqlite3_column_double(stmt, col);
        case SQLITE_BLOB: {
            const auto len = static_cast<std::size_t>(sqlite3_column_bytes(stmt, col));
            // NOLINTNEXTLINE(cppcoreguidelines-pro-type-cstyle-cast)
            const auto* raw = static_cast<const unsigned char*>(sqlite3_column_blob(stmt, col));
            return raw != nullptr ? hex_lower(std::span<const unsigned char>(raw, len))
                                  : std::string();
        }
        default: {
            // NOLINTNEXTLINE(cppcoreguidelines-pro-type-reinterpret-cast)
            const auto* text = reinterpret_cast<const char*>(sqlite3_column_text(stmt, col));
            return text != nullptr ? std::string(text) : std::string();
        }
    }
}

std::string column_text(sqlite3_stmt* stmt, int col) {
    // NOLINTNEXTLINE(cppcoreguidelines-pro-type-reinterpret-cast)
    const auto* text = reinterpret_cast<const char*>(sqlite3_column_text(stmt, col));
    return text != nullptr ? std::string(text) : std::string();
}

// engram UUID → "engram:<content_hash>",本租户没这个 engram 时 → kMissingRef。
// 懒查并缓存:一行的几个 JSON 列通常指向同一个 engram,一条事件行也指向它。
class EngramRefs {
public:
    EngramRefs(persistence::Connection& conn, std::string_view tenant)
        : conn_(&conn), tenant_(tenant) {}

    const std::string& ref_for(const std::string& engram_id) {
        if (const auto found = cache_.find(engram_id); found != cache_.end()) {
            return found->second;
        }
        // 空串原样留着:它不是一个指不到的引用,而是「还没填引用」(claim_contract 建
        // 证据时先写 ""、由 extractor 回填 engram id)。把它也折成 missing 就把两种状态
        // 混成一个值了。
        std::string value = engram_id.empty() ? std::string() : std::string(kMissingRef);
        if (!engram_id.empty()) {
            persistence::Stmt stmt(conn_->raw(),
                                   "SELECT content_hash FROM engrams "
                                   "WHERE tenant_id=?1 AND id=?2");
            stmt.bind(tenant_, engram_id);
            if (stmt.step_row()) {
                value = "engram:" + column_text(stmt.raw(), 0);
            }
        }
        return cache_.emplace(engram_id, std::move(value)).first->second;
    }

private:
    persistence::Connection* conn_;  // 不拥有、非空;用指针是因为引用成员会让类不可赋值
    std::string tenant_;
    std::map<std::string, std::string> cache_;
};

// 递归把 engram_ref / evidence_engram_ref 的字符串值换成 engram 的 content_hash 引用。
// 只认这两个键名(设计源与探针认定的两处);其余键原样递归。
void substitute_engram_refs(Json& node, EngramRefs& refs) {
    if (node.is_object()) {
        for (const auto& item : node.items()) {
            const std::string& key = item.key();
            Json& value = item.value();
            if ((key == "engram_ref" || key == "evidence_engram_ref") && value.is_string()) {
                value = refs.ref_for(value.get<std::string>());
            } else {
                substitute_engram_refs(value, refs);
            }
        }
    } else if (node.is_array()) {
        for (auto& value : node) {
            substitute_engram_refs(value, refs);
        }
    }
}

// confidence_history_json 每项带一个墙钟 ts(src/bus/bus.cpp 的 system_clock::now(),
// 以及 src/reconsolidation/arbitration.cpp 传进来的 now_iso)。设计源 4.5 节的排除清单
// 没写这一条,是探针发现的:不去掉,两个库写同一段话、走同一条弱修正路径,摘要也不同。
void drop_history_timestamps(Json& history) {
    if (!history.is_array()) {
        return;
    }
    for (auto& entry : history) {
        if (entry.is_object()) {
            entry.erase("ts");
        }
    }
}

// 列值 → 规范化后的 JSON。JSON 列解析后做 engram 替换(并顺带把对象键归一成字典序,
// nlohmann 的对象天然有序);解析不出来(列被外部写坏)就保留原串,不崩。
Json normalize_cell(sqlite3_stmt* stmt, int col, std::string_view name, EngramRefs& refs) {
    Json value = cell_to_json(stmt, col);
    if (!in_set(statement_json_columns(), name) || !value.is_string()) {
        return value;
    }
    Json parsed = Json::parse(value.get_ref<const std::string&>(), nullptr,
                              /*allow_exceptions=*/false);
    if (parsed.is_discarded()) {
        return value;
    }
    substitute_engram_refs(parsed, refs);
    if (name == "confidence_history_json") {
        drop_history_timestamps(parsed);
    }
    return parsed;
}

// 一条语句行的规范化结果。content 不含引用列与生命周期列,它的 dump 的 sha256 就是
// 内容 id;refs 是引用列的原值(UUID 还没映射),等全部内容 id 都算出来后由摘要层映射;
// lifecycle 是生命周期列的规范化值,摘要层原样并回行里。
struct StatementNorm {
    std::string id;
    std::string content_id;
    Json content   = Json::object();
    Json refs      = Json::object();
    Json lifecycle = Json::object();
};

// 本租户的语句行规范化。ids 为空 optional 表示全表;给了就只读这些 id(召回命中补
// content_id 的批量路径走这条,不必规范化整库)。
std::vector<StatementNorm> read_statements(persistence::Connection& conn,
                                           std::string_view tenant,
                                           EngramRefs& refs,
                                           const std::optional<std::vector<std::string>>& ids) {
    std::vector<StatementNorm> out;
    // SELECT * 的结果列名就是 PRAGMA table_info 的列名(表声明的那些列,声明顺序),
    // 所以新加的列自动进摘要,无需在这里登记。
    std::string sql = "SELECT * FROM statements WHERE tenant_id=?1";
    if (ids.has_value()) {
        sql += " AND id IN (";
        for (std::size_t i = 0; i < ids->size(); ++i) {
            sql += (i == 0 ? "?" : ",?");
        }
        sql += ')';
    }
    persistence::Stmt stmt(conn.raw(), sql.c_str());
    int idx = 0;
    persistence::detail::bind_sv(stmt.raw(), ++idx, tenant);
    if (ids.has_value()) {
        for (const auto& stmt_id : *ids) {
            persistence::detail::bind_sv(stmt.raw(), ++idx, stmt_id);
        }
    }
    while (stmt.step_row()) {
        StatementNorm row;
        const int columns = sqlite3_column_count(stmt.raw());
        for (int col = 0; col < columns; ++col) {
            const char* raw_name = sqlite3_column_name(stmt.raw(), col);
            const std::string_view name = raw_name != nullptr ? raw_name : "";
            if (name == "id") {
                row.id = column_text(stmt.raw(), col);
            }
            if (in_set(excluded_columns(), name)) {
                continue;
            }
            if (in_set(reference_columns(), name)) {
                set_field(row.refs, std::string(name), cell_to_json(stmt.raw(), col));
                continue;
            }
            if (in_set(lifecycle_columns(), name)) {
                set_field(row.lifecycle, std::string(name),
                          normalize_cell(stmt.raw(), col, name, refs));
                continue;
            }
            set_field(row.content, std::string(name),
                      normalize_cell(stmt.raw(), col, name, refs));
        }
        row.content_id = crypto::sha256_hex(row.content.dump());
        out.push_back(std::move(row));
    }
    return out;
}

// 一个指向语句的 UUID → 被指向行的内容 id;不在本租户时 → kMissingRef。NULL 原样留
// null:「没有取代谁」与「取代的那行不见了」是两件事,不该混成一个值。
Json map_statement_ref(const Json& value,
                       const std::map<std::string, std::string>& content_by_id) {
    if (!value.is_string()) {
        return value;
    }
    const auto found = content_by_id.find(value.get_ref<const std::string&>());
    return found != content_by_id.end() ? Json(found->second) : Json(std::string(kMissingRef));
}

// derived_from_json:字符串数组,每个 UUID 换成内容 id,原顺序不动(顺序是内容的
// 一部分——父语句的次序决定 derived_depth 的来源)。解析不出来就原样留着。
Json map_statement_ref_array(const Json& value,
                             const std::map<std::string, std::string>& content_by_id) {
    if (!value.is_string()) {
        return value;
    }
    Json parsed = Json::parse(value.get_ref<const std::string&>(), nullptr,
                              /*allow_exceptions=*/false);
    if (!parsed.is_array()) {
        return value;
    }
    for (auto& item : parsed) {
        item = map_statement_ref(item, content_by_id);
    }
    return parsed;
}

// 排序键 (内容 id, 规范化串) → 行对象。两者都相同的两行本身可互换,所以这个序完全
// 确定,不留任何由插入顺序(rowid)决定的并列。
using SortedRows = std::vector<std::tuple<std::string, std::string, Json>>;

Json finish(SortedRows& rows) {
    std::ranges::sort(rows, [](const auto& lhs, const auto& rhs) {
        return std::tie(std::get<0>(lhs), std::get<1>(lhs))
               < std::tie(std::get<0>(rhs), std::get<1>(rhs));
    });
    Json out = Json::array();
    for (auto& entry : rows) {
        out.push_back(std::move(std::get<2>(entry)));
    }
    return out;
}

void append(SortedRows& rows, std::string key, Json row) {
    std::string dumped = row.dump();
    rows.emplace_back(std::move(key), std::move(dumped), std::move(row));
}

}  // namespace

std::string digest(persistence::Connection& conn, std::string_view tenant) {
    EngramRefs refs(conn, tenant);

    // ① 语句行:先全部算出内容 id,引用列才有东西可指。
    auto statements = read_statements(conn, tenant, refs, std::nullopt);
    std::map<std::string, std::string> content_by_id;
    for (const auto& row : statements) {
        content_by_id.emplace(row.id, row.content_id);
    }

    // ② 语句行 = 内容 id 的规范化行 + 引用列(UUID → 被指向行的内容 id)+ 生命周期列。
    SortedRows statement_rows;
    for (auto& row : statements) {
        Json entry = std::move(row.content);
        for (const auto& item : row.refs.items()) {
            set_field(entry, item.key(),
                      item.key() == "derived_from_json"
                          ? map_statement_ref_array(item.value(), content_by_id)
                          : map_statement_ref(item.value(), content_by_id));
        }
        for (const auto& item : row.lifecycle.items()) {
            set_field(entry, item.key(), item.value());
        }
        append(statement_rows, row.content_id, std::move(entry));
    }

    // ③ 向量行:stmt_id 在排除清单里,改挂一个键 stmt,值是所属语句的内容 id。
    SortedRows vector_rows;
    {
        persistence::Stmt stmt(conn.raw(), "SELECT * FROM statement_vectors WHERE tenant_id=?1");
        stmt.bind(tenant);
        while (stmt.step_row()) {
            Json entry = Json::object();
            std::string stmt_id;
            const int columns = sqlite3_column_count(stmt.raw());
            for (int col = 0; col < columns; ++col) {
                const char* raw_name = sqlite3_column_name(stmt.raw(), col);
                const std::string_view name = raw_name != nullptr ? raw_name : "";
                if (name == "stmt_id") {
                    stmt_id = column_text(stmt.raw(), col);
                }
                if (in_set(excluded_columns(), name)) {
                    continue;
                }
                set_field(entry, std::string(name), cell_to_json(stmt.raw(), col));
            }
            const auto found = content_by_id.find(stmt_id);
            const std::string stmt_ref =
                found != content_by_id.end() ? found->second : std::string(kMissingRef);
            set_field(entry, "stmt", stmt_ref);
            append(vector_rows, stmt_ref, std::move(entry));
        }
    }

    // ④ 事件行:engram_ref 换成 engram 引用,statement_ids_json 按原顺序换成内容 id。
    // state='abandoned' 只留 {key, state}:放弃是终局,行里留着的原文、seq 与失败原因
    // 只是事后查原因用的痕迹,对「这个库里有什么记忆」没有贡献——两个库各放弃过一个
    // 同 key 不同文本的事件,记忆内容是一样的。
    SortedRows event_rows;
    {
        persistence::Stmt stmt(conn.raw(), "SELECT * FROM events WHERE tenant_id=?1");
        stmt.bind(tenant);
        while (stmt.step_row()) {
            Json entry = Json::object();
            std::string key;
            std::string state;
            const int columns = sqlite3_column_count(stmt.raw());
            for (int col = 0; col < columns; ++col) {
                const char* raw_name = sqlite3_column_name(stmt.raw(), col);
                const std::string_view name = raw_name != nullptr ? raw_name : "";
                if (name == "key") {
                    key = column_text(stmt.raw(), col);
                }
                if (name == "state") {
                    state = column_text(stmt.raw(), col);
                }
                if (in_set(excluded_columns(), name)) {
                    continue;
                }
                Json value = cell_to_json(stmt.raw(), col);
                if (name == "engram_ref" && value.is_string()) {
                    value = refs.ref_for(value.get<std::string>());
                } else if (name == "statement_ids_json" && value.is_string()) {
                    Json parsed = Json::parse(value.get_ref<const std::string&>(), nullptr,
                                              /*allow_exceptions=*/false);
                    if (parsed.is_array()) {
                        for (auto& item : parsed) {
                            item = map_statement_ref(item, content_by_id);
                        }
                        value = std::move(parsed);
                    }
                }
                set_field(entry, std::string(name), std::move(value));
            }
            if (state == "abandoned") {
                entry = Json::object({{"key", key}, {"state", state}});
            }
            append(event_rows, key, std::move(entry));
        }
    }

    const Json library = {
        {"events", finish(event_rows)},
        {"statements", finish(statement_rows)},
        {"statement_vectors", finish(vector_rows)},
    };
    return crypto::sha256_hex(library.dump());
}

std::map<std::string, std::string> content_ids(persistence::Connection& conn,
                                               std::string_view tenant,
                                               const std::vector<std::string>& stmt_ids) {
    std::map<std::string, std::string> out;
    for (const auto& stmt_id : stmt_ids) {
        out.emplace(stmt_id, std::string(kMissingRef));
    }
    if (out.empty()) {
        return out;
    }

    // 分批查,一次一个 IN:SQLITE_MAX_VARIABLE_NUMBER 在老 SQLite 上只有 999。
    constexpr std::size_t kChunk = 400;
    EngramRefs refs(conn, tenant);
    std::vector<std::string> chunk;
    chunk.reserve(kChunk);
    const auto flush = [&] {
        if (chunk.empty()) {
            return;
        }
        for (const auto& row : read_statements(conn, tenant, refs, chunk)) {
            out[row.id] = row.content_id;
        }
        chunk.clear();
    };
    for (const auto& entry : out) {
        chunk.push_back(entry.first);
        if (chunk.size() == kChunk) {
            flush();
        }
    }
    flush();
    return out;
}

}  // namespace starling::memoryops

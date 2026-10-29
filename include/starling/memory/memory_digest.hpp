#pragma once
// Memory digest — 一个 library 的逻辑摘要:换掉身份、只留内容,再取 sha256。
//
// rise 的训练 config_hash 含起点 library 的摘要:两个库内容相同就必须给同一个摘要,
// 内容一变就必须变(否则换了起点的续训会被当成同一个实验接着跑)。行 id 是 UUID、
// 库与库之间必然不同,所以字节比对没用。这里按「内容 id」重排身份:
//
//   内容 id = 一条语句行规范化后的 sha256(64 位小写十六进制)。规范化去掉簿记列
//             (见下面的排除清单)、把 JSON 列里的 engram UUID 换成 engram 的
//             content_hash、去掉置信史里的墙钟,再去掉引用列 supersedes_id 与
//             derived_from_json。引用列不进内容 id:否则沿取代链递归,被指向行的
//             内容 id 又要先算出来,互相等着。
//   摘要   = statements / statement_vectors / events 三张表的规范化行,语句行加回
//            引用列(UUID 换成被指向行的内容 id),向量行的 stmt_id 换成所属语句的
//            内容 id,事件行的 statement_ids_json 换成内容 id,排序后整体取 sha256。
//
// 排除清单(设计源 4.5 节):id、stmt_id、created_at、updated_at、last_accessed、
// access_count、last_replayed、replay_count、last_replay_batch_id、retry_count、
// last_attempt_at、embedded_at、inferred_at。列名从 PRAGMA table_info 取,新加的列
// 默认进摘要——漏掉只会让摘要过敏感(多判一次「不是同一个实验」),静默少算一列却会
// 让两个不同的库共用一个 config_hash。
//
// 另外两条排除是探针逼出来的,设计源 4.5 节没写:
//   - confidence_history_json 每项的墙钟 ts(src/bus/bus.cpp 与
//     src/reconsolidation/arbitration.cpp 都按 system_clock::now() 追加);
//   - JSON 列与 events.engram_ref 里的 engram UUID(换成 content_hash)。
// 不处理这两条就做不到「两个库内容相同、摘要相同」。
//
// 全行进摘要,不按召回可见性过滤:被取代后 archived 的行仍是召回候选,volatile 与
// pending_review 行此刻召回不到但仍参与写入时的冲突探测与强化,都会改后续写入的结果。
//
// 规范化与哈希都在 C++(Starling CLAUDE.md 的边界);Python 门面只转发。
#include <map>
#include <string>
#include <string_view>
#include <vector>

#include "starling/persistence/connection.hpp"

namespace starling::memoryops {

// 指向一行/一个 engram 的引用,而被指向的东西不在本租户里时,规范化后写这个词。
// 两个库各自指向一个不存在的不同 UUID 时,靠它收敛成同一个值。
inline constexpr std::string_view kMissingRef = "missing";

// 本租户 library 的逻辑摘要,64 位小写十六进制。空库固定是
// sha256(R"({"events":[],"statement_vectors":[],"statements":[]})")。
[[nodiscard]] std::string digest(persistence::Connection& conn, std::string_view tenant);

// 语句 UUID → 内容 id(64 位小写十六进制)。本租户没有这个 id 时映射成
// kMissingRef,调用方不必先自己查在不在。入参顺序不影响结果;重复 id 只出现一次。
[[nodiscard]] std::map<std::string, std::string> content_ids(
    persistence::Connection& conn, std::string_view tenant,
    const std::vector<std::string>& stmt_ids);

}  // namespace starling::memoryops

#pragma once
// Memory events — 按调用方给的稳定 key 记一次写入的收据(迁移 0038 的 events 表)。
//
// rise 的记忆写入要幂等:同一个 key 重放不会再抽取一次。收据行记下 key、原文、
// 说话对象、序号和状态(pending / committed / abandoned)。本头文件放读侧(序号时钟
// next_seq 与待处理清单 pending_events)与写侧(remember_event)。abandon_event 随
// 后续任务加进同一对文件。
//
// 状态机与查询放在 C++(Starling CLAUDE.md 的边界);Python 绑定只转发,门面只把
// 行包成 PendingEvent。
#include <cstdint>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

#include "starling/extractor/llm_adapter.hpp"
#include "starling/extractor/statement_validator.hpp"
#include "starling/memory/memory_ops.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

namespace starling::memoryops {

// 同一个 key 被用来写另一段文本,或该 key 已被放弃(state='abandoned')。收据行是
// 「这个 key 写的是这段文本」的承诺,改文本会让幂等失去意义,所以这里不静默覆盖。
// std::runtime_error 子类 → pybind register_exception → starling.EventConflict。
class EventConflict : public std::runtime_error {
public:
    explicit EventConflict(const std::string& what) : std::runtime_error(what) {}
};

// events 表里一条 state='pending' 的行,只带调用方恢复所需的字段。
struct PendingEventRow {
    std::string key;
    std::string text;
    std::string interlocutor;
    std::int64_t seq = 0;
    std::string failure_category;
};

// 本租户下一个可用序号:COALESCE(MAX(seq) + 1, 0)。含 abandoned 行,所以序号只增
// 不复用;空库为 0,第一条事件的 seq 就是 0。
[[nodiscard]] std::int64_t next_seq(persistence::Connection& conn, std::string_view tenant);

// 本租户 state='pending' 的行,按 seq 升序。committed 与 abandoned 不返回。
[[nodiscard]] std::vector<PendingEventRow> pending_events(persistence::Connection& conn,
                                                          std::string_view tenant);

// 按调用方给的稳定 key 记一次写入,崩溃安全、可重放(设计源 §8)。三段:
//
// ① 短事务:按 (tenant_id, key) 读行。无行 → seq = next_seq,插 state='pending' 的行
//    (text、interlocutor、text_sha256)后提交。有行且 state='abandoned',或
//    text_sha256 与本次文本不同 → 抛 EventConflict。state='committed' → 直接返回
//    outcome="idempotent" 与行里存的 engram_ref / statement_ids,一次 LLM 都不调。
//    state='pending' → 进补齐分支。
// ② 事务外(抽取要走网络,绝不持写事务):payload 是 "[" + key + "] " + text
//    (key 作为前缀写进 Starling 的文本,设计源 4.3),时刻是 epoch_iso + seq 秒。
//    补齐分支先按该 payload 的 engram content_hash 找 engrams 行,找到且有语句的
//    evidence_json 指向它、holder_id 相同时,直接把这批 id(按 rowid 升序)当结果,
//    不调 LLM;否则照 remember_all 走一遍(用行里存的原文,不是调用方这次传的)。
// ③ 短事务:仅当证据真入库(outcome 为 accepted/idempotent)且抽取未失败,行才改
//    committed,填 engram_ref 与 statement_ids_json、清空 failure_category。其余情形
//    (抽取失败,或 no_store / rejected / source_missing 这三种未入库的 outcome——它们的
//    extraction_failed 都是 false)行一律留 pending 并写 failure_category(抽取失败写原
//    类别,未入库写 "not_stored:<outcome>";有 engram_ref 时一并写)。返回值的
//    failure_category 与行里记的一致(未入库时 remember_all 不填这个字段,这里补上),
//    不抛:留着 pending 行才让调用方看得见,下次调用照原 seq 重试,记忆不会静默丢失。
//    remember_all 抛异常时行同样留 pending,异常原样上抛。
//
// base 提供 tenant_id / holder_id / interlocutor / adapter_name / source_prefix;
// base 的 payload 与 created_at_iso8601 被忽略(由 key+text 与 epoch+seq 推出)。
// 重试 pending 行时用行里原来的 seq,时钟不漂移,也不另分配序号。
// 走 SqliteAdapter(而非裸 Connection)以便经过写准入门。
RememberOutcome remember_event(persistence::SqliteAdapter& adapter,
                               extractor::LLMAdapter& llm,
                               const RememberParams& base,
                               const RememberPrompts& prompts,
                               std::string_view key,
                               std::string_view text,
                               std::string_view epoch_iso,
                               const extractor::ValidationPolicy& policy = {});

}  // namespace starling::memoryops

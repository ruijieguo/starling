#pragma once
// sub-project A phase 5 Task 5.1:EpisodicExtractor —— remember() 的第二条
// (episodic)抽取管线。叙事段落 → OCCURRED 事件语句 + episodic_events 行。
//
// 与 Extractor(belief/conversation 管线)并列、互相独立:Extractor 抽取信念/
// 承诺/规范,EpisodicExtractor 抽取「发生了什么」的物理事件序列(Sally put
// ball in basket / Sally leave room / Anne move ball to box)。LLM 返回叙事
// 顺序的事件数组,逐个按 1-based seq 写一条 modality=OCCURRED 语句
// (holder=self,subject=actor,predicate=action,object=theme),并尽力补写一条
// episodic_events 扩展行(seq/location/participants/time)。扩展行写在与语句
// 同一个写事务内、且失败不回滚语句(best-effort)。
//
// prompt_template 由调用方注入(prompt 是配置数据,单一源在
// python/starling/extractor/episodic_prompt.py),"{passage}" 字面替换。
#include "starling/extractor/llm_adapter.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <string>
#include <string_view>
#include <vector>

namespace starling::extractor {

struct EpisodicExtractionResult {
    // 本次写入的 OCCURRED 语句 id,按叙事顺序(seq 升序)。
    std::vector<std::string> event_statement_ids;
};

// 相①(extract_llm)产物:解析好、待落库的单个事件。actor/participants 仍是 raw
// surface —— cognizer 名解析(resolve_name)会写库,留到 persist(锁内)。
struct ParsedEpisodicEvent {
    long long seq = 0;                       // 1-based,密集于完整事件
    std::string actor;                       // raw surface(persist 里 resolve_name)
    std::string action;
    std::string object_value;                // normalize_theme(theme)(M8 entity-kind)
    std::string canonical_object_hash;       // canonicalize_object(object_value)
    std::string location;                    // "" → episodic_events NULL
    std::string event_time;                  // "" → NULL
    std::vector<std::string> participants;   // raw surfaces(persist 里逐个 resolve_name)
};

// 相① LLM+parse 输出容器,零 DB。ok = 适配器 ok 且解析出非空合法数组
// (决定 persist 是否开事务:与单体一致——非空合法数组即使全 incomplete 也开事务)。
struct EpisodicLlmResult {
    bool ok = false;
    std::vector<ParsedEpisodicEvent> events{};
};

class EpisodicExtractor {
public:
    EpisodicExtractor(persistence::Connection& conn, LLMAdapter& adapter,
                      std::string prompt_template = "")
        : conn_(conn), adapter_(adapter),
          prompt_template_(std::move(prompt_template)) {}

    // Phase 2 (Task 2.2): an OPTIONAL SqliteAdapter enables cognizer-name
    // resolution. When present, the actor + each participant surface is resolved
    // to its canonical first-seen name (via CognizerHub, reusing the cognizers
    // table) before the OCCURRED statement is written, so name-surface drift
    // ("Xiao Hong"/"XiaoHong") grounds to one entity. The resolver registers on a
    // miss inside the existing write transaction; it is best-effort (a resolve
    // failure returns the raw surface). The connection-only ctor preserves the
    // pre-phase-2 behavior (raw surfaces). store_adapter and conn MUST back the
    // same database.
    EpisodicExtractor(persistence::Connection& conn, LLMAdapter& adapter,
                      persistence::SqliteAdapter& store_adapter,
                      std::string prompt_template = "")
        : conn_(conn), adapter_(adapter), store_adapter_(&store_adapter),
          prompt_template_(std::move(prompt_template)) {}

    // 抽取叙事 passage 的物理事件并写库。engram_ref 作为语句证据来源;
    // agent_self 是事件 holder(第一人称观察者);now 作为缺省 observed_at。
    // 解析失败 / 空数组 → 返回空结果、零写入、不抛。
    EpisodicExtractionResult extract(
        std::string_view passage,
        std::string_view engram_ref,
        std::string_view tenant,
        std::string_view agent_self,
        std::string_view now);

    // 相①(锁外,零 DB 无 TransactionGuard):build_prompt + LLM + 解析数组 + 逐事件
    // 抽 raw 字段 + 完整性过滤 + 密集 seq + 纯计算 normalize_theme/canonicalize_object。
    // resp 失败 / 无数组 / 空数组 → ok=false、events 空。
    EpisodicLlmResult extract_llm(std::string_view passage);

    // 相②(锁内):!llm_result.ok → 零写返回(不开事务,镜像单体 early-return)。否则开
    // TransactionGuard,逐事件 resolve_name(actor+participants) → writer.write →
    // ep_store.upsert(best-effort),commit。返回 event_statement_ids(seq 升序)。
    EpisodicExtractionResult persist(
        std::string_view engram_ref,
        std::string_view tenant,
        std::string_view agent_self,
        std::string_view now,
        const EpisodicLlmResult& llm_result);

    // {passage} 字面替换(无占位符则在末尾追加 passage)。镜像
    // Extractor::build_prompt 的 {convo} 处理。prompt_template_ 为空时(单测路径)
    // 返回稳定的确定性串,使 prompt-hash keyed 的 FakeLLMAdapter 仍能命中默认响应。
    std::string build_prompt(std::string_view passage) const;

private:
    persistence::Connection& conn_;
    LLMAdapter& adapter_;
    persistence::SqliteAdapter* store_adapter_ = nullptr;  // null → raw surfaces (no name resolution)
    std::string prompt_template_;
};

}  // namespace starling::extractor

#pragma once
// Memory ops — remember / tick_all 管线编排(2026-06-11 边界归位第二件,
// 继 Working Set 之后)。
//
// 此前编排在 python/starling/_memory_core.py:幂等键派生
// (source_prefix + sha256(payload)[:16])、入库策略默认值(USER_INPUT/
// WHOLE_RECORD/byte_preserving)、以及「先 engram 后抽取、仅
// accepted/idempotent 才抽取」的顺序规则——按边界判据(换绑定语言需重写)
// 全部属核心语义。Python 仅剩签名归一(datetime→ISO)与绑定转发。
#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

#include "starling/embedding/embedding_worker.hpp"
#include "starling/extractor/llm_adapter.hpp"
#include "starling/extractor/statement_validator.hpp"
#include "starling/governance/stage_timer.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/prospective/policy_engine.hpp"
#include "starling/retrieval/semantic_retriever.hpp"
#include "starling/runtime_health.hpp"

namespace starling::memoryops {

struct RememberParams {
    std::string tenant_id;
    std::string holder_id;            // agent/self
    std::string interlocutor;         // 可空;非空时抽取带 scope_parties
    std::string adapter_name;         // 来源标识:"facade" / "dashboard"
    std::string source_prefix;        // 幂等键前缀:"mem-" / "dash-"
    std::string created_at_iso8601;   // Python 侧 datetime→ISO(签名归一)
    std::vector<std::uint8_t> payload;
};

struct RememberOutcome {
    std::string engram_ref;                   // 空 = 未入库(no_store/rejected)
    std::vector<std::string> statement_ids;   // 本次新写入的语句
    std::string outcome;                      // accepted/idempotent/no_store/rejected
    bool extraction_failed = false;           // 证据已入库但抽取 LLM 失败(Extractor
                                              // 吞失败返回 FAILED 而非抛异常)——供
                                              // converse 区分「抽取失败」与「抽取空」。
};

// 标准写管线:内容确定性幂等键 → Bus::append_evidence(证据入库)→
// 仅 accepted/idempotent 时 Extractor::run(LLM 抽取)→ 写后泵一次
// (SubscriberPump::run_post_write:投影/信念/再巩固/在线回放/策略)。
// 泵的生产宿主在这里而非 Bus::write——生产语句写经 Extractor→StatementWriter,
// 不经 Bus::write,挂在那里的泵在 remember 路径永不运行(P2.o 实测根因)。
// prompt_template 由调用方注入(prompt 是配置数据,单一源在
// python/starling/extractor/prompts.py)。
RememberOutcome remember(persistence::SqliteAdapter& adapter,
                         extractor::LLMAdapter& llm,
                         std::string_view prompt_template,
                         const RememberParams& params,
                         const extractor::ValidationPolicy& policy = {});

// ── converse — chat-with-memory turn (Phase 2c) ──
struct ConverseParams {
    std::string tenant_id;
    std::string holder_id;            // querier (recall) + holder (remember) = agent/self
    std::string interlocutor;         // 可空;沉淀对话时带 scope_parties
    std::string adapter_name;         // 来源标识:"dashboard"
    std::string source_prefix;        // 幂等键前缀:"dash-"
    std::string created_at_iso8601;   // 签名归一(datetime→ISO)
    std::string message;              // 用户本轮输入
    int recall_k = 6;                 // 注入的相关记忆条数上限
};

struct ConverseOutcome {
    std::string reply;                       // ok=false 时空(generate 失败)
    bool ok = false;                         // generate 成功 → 有回复
    std::string error;                       // ok=false 时的错误码
    std::string context_pack;                // 注入的记忆(带标签),供轨迹展示
    bool abstained = false;                  // recall 主动拒答
    std::vector<std::string> statement_ids;  // 本轮沉淀的语句
    bool remember_ok = false;                // false → 回复保留但记忆未落库
    std::string remember_error;              // remember 失败原因(可观测)
    // 2b:本轮「回复生成」成本(chat_llm.generate 这一段;remember 的抽取成本
    // 待 extraction_attempt 持久化后单列)。真模型填充,Fake/stub 留 0。
    int gen_prompt_tokens     = 0;
    int gen_completion_tokens = 0;
    int gen_total_tokens      = 0;
    int gen_latency_ms        = 0;
};

// 带记忆的聊天轮(三段式,决策 A):recall(RetrievalPlanner,只读)→ 注入
// context_pack → chat_llm.generate_stream(网络,不持写事务)→ remember 对话
// (extraction_llm,写)。失败语义:generate 失败 → ok=false 且无回复;
// remember 失败 → 回复保留(ok=true)且 remember_ok=false——用户已看到的回复
// 绝不因事后抽取失败而丢。网络 generate 期间不持任何写事务。
//
// on_token(可空):流式回调。非空时,回复在「第二段」生成期间逐 token 经
// on_token 增量回传(WS token stream);空 = 不流式(等价旧 generate 路径)。
// 流式只发生在第二段(不持写事务的网络段),沉淀(第四段写)仍在整段回复流完
// 之后,故 no-write-txn-across-generate 与「回复绝不因 remember 失败而丢」两条
// 不变式都不受流式影响。on_token 不改变返回的 ConverseOutcome(reply 仍是完整
// 文本,成本/落库结果照常),只是把同样的文本在生成时先推一遍。
ConverseOutcome converse(persistence::SqliteAdapter& adapter,
                         extractor::LLMAdapter& chat_llm,
                         extractor::LLMAdapter& extraction_llm,
                         retrieval::SemanticRetriever& semantic,
                         std::string_view extraction_prompt,
                         const ConverseParams& params,
                         const extractor::ValidationPolicy& policy = {},
                         const extractor::TokenSink& on_token = {});

// converse 三相拆分(2026-07-05,锁外生成 slice 第一步):prepare(相位 1+2,只读
// recall + inject)/ commit(相位 3 失败短路+成本填充 + 相位 4 write remember)。
// host 后续会在 prepare/commit 之间持锁外调用 chat_llm.generate_stream——三相
// 拆分让「持写事务的锁」不再跨网络生成段。converse() 本身内联三相,行为字节级
// 不变(单一语义源:分调用与单体调用逐字段 parity,见 test_converse_phases.cpp)。
struct ConversePrepared {
    std::string prompt;         // 拼好待发给 chat_llm 的完整 prompt(围栏+召回+问题)
    std::string context_pack;   // 注入的记忆(带标签),原样透传给 commit 供轨迹展示
    bool abstained = false;     // recall 阶段的主动拒答标记,原样透传
    // prepare 时刻快照;commit 以此为权威时刻(而非 commit 调用时另传的
    // params.created_at_iso8601),保证幂等键/召回种子与 prepare 阶段同刻——
    // 即使调用方在 prepare/commit 两次传入的 now 发生漂移,也不产生分叉。
    std::string created_at_iso8601;
};

// 相位 1(recall)+ 相位 2(inject):只读,不持写事务。开头即 fail-fast 写门校验——
// 若门已关(DRAINING/UNREADY),在烧生成段网络成本之前就抛 WriteGateRejected,
// 避免「白烧一次 LLM 调用后才发现无法沉淀」。
ConversePrepared converse_prepare(persistence::SqliteAdapter& adapter,
                                  retrieval::SemanticRetriever& semantic,
                                  const ConverseParams& params);

// 相位 3(generate 失败短路 + 成本填充)+ 相位 4(remember 写)。调用方在
// prepare 与 commit 之间自行调用 chat_llm.generate_stream(不持写事务的网络段)。
// commit 不再另查一次 write admission——remember() 内部的 require_write_admission
// 已经覆盖「prepare 时门开、生成期间门关(DRAINING)」的中途翻转:门关时
// remember 抛 WriteGateRejected,被下面的 catch 降级为 remember_ok=false +
// remember_error(回复绝不因此丢,失败语义 A)。
ConverseOutcome converse_commit(persistence::SqliteAdapter& adapter,
                                extractor::LLMAdapter& extraction_llm,
                                std::string_view extraction_prompt,
                                const ConverseParams& params,
                                const ConversePrepared& prepared,
                                const extractor::LLMResponse& gen_resp,
                                const extractor::ValidationPolicy& policy = {});

// 二阶提示注入防御:中和召回文本里的围栏定界符 token,使存储数据无法伪造
// <recalled_memory> 开/闭标签提前闭合围栏(converse 拼 prompt 前调用)。导出以便单测。
std::string neutralize_recall_fence(std::string_view context_pack);

struct TickOutcome {
    int embedded = 0;
    int fired = 0;
    int broken = 0;
    int auto_withdrawn = 0;
    // P2.o 周期维护:回放巩固 + 投影兜底 + 出箱收敛。
    int replay_sampled = 0;   // 本批 idle 回放采样数
    int consolidated = 0;     // volatile→consolidated 晋升数(op_compress)
    int ttl_archived = 0;     // VOLATILE TTL 超期归档数
    int projected = 0;        // 投影兜底批处理事件数
    int dispatched = 0;       // 出箱 pending→delivered 数(in_process 消费者)
    // P3.c1 Phase 3b: per-stage wall-clock timings, in execution order — 8 stages
    // (embed/policy/common_ground/replay_oscillation_guard/replay_ttl_sweep/
    // replay_idle/projection/outbox). metadata_only trace tier.
    std::vector<governance::StageTiming> stage_timings_ms;
    // P3.c LW.2: stages skipped by load-shedding this tick (LOCKED L8/OQ-LW.6).
    // Same string labels as stage_timings_ms; a stage is in exactly one of the
    // two. Empty = nothing shed (READY). Excluded from the host idle-heartbeat
    // predicate (LW.3).
    std::vector<std::string> stages_skipped;
};

// 周期维护(P2.o 扩展):嵌入一批待向量语句 → 承诺触发器 tick → grounding
// 滞后冲账(P2.j)→ 回放维护(振荡防护 → volatile TTL sweep → idle 批)→
// 投影兜底批 → 出箱派发(Accept-all "in_process" 消费者:嵌入式单进程无外部
// 消费者,五个进程内消费者均按 consumer_checkpoints 推进且不过滤
// dispatch_status,故标记 delivered 安全;delivered=进程内交付完成)。
// worker/policy 由调用方持有注入(embedder 可热换,见 DashboardEngine)。
// health (P3.c LW.2): gates each stage through governance::should_run_stage;
// defaults to READY (behavior-preserving — existing 4-arg callers unchanged).
TickOutcome tick_all(persistence::SqliteAdapter& adapter,
                     embedding::EmbeddingWorker& worker,
                     prospective::PolicyEngine& policy,
                     std::string_view now_iso,
                     RuntimeHealth health = RuntimeHealth::READY);

// P3.b2:逻辑删除一批 statements(→forgotten),返回实际转换计数。
int forget(persistence::SqliteAdapter& adapter, std::string_view tenant,
           const std::vector<std::string>& ids, std::string_view now_iso);

// 片 6 干预集:人工审批 review_requested → approved(守卫幂等、tenant-scoped),返回转换计数(0/1)。
// reject 不在此 —— reject = forget(→forgotten 终态)。
int approve_review(persistence::SqliteAdapter& adapter, std::string_view tenant,
                   std::string_view stmt_id, std::string_view now_iso);

// P3.a3 再巩固显式触发:发 reconsolidate.requested 事件,engine 异步开窗。返回 outbox
// event_id。(边界归位:原写逻辑在 bind_09 lambda,本 slice 提取入核心以受门管辖。)
std::string request_reconsolidation(persistence::SqliteAdapter& adapter,
                                    std::string_view tenant_id,
                                    std::string_view stmt_id,
                                    std::string_view request_id,
                                    std::string_view now_iso);

}  // namespace starling::memoryops

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
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/prospective/policy_engine.hpp"

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
                         const RememberParams& params);

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
};

// 周期维护(P2.o 扩展):嵌入一批待向量语句 → 承诺触发器 tick → grounding
// 滞后冲账(P2.j)→ 回放维护(振荡防护 → volatile TTL sweep → idle 批)→
// 投影兜底批 → 出箱派发(Accept-all "in_process" 消费者:嵌入式单进程无外部
// 消费者,五个进程内消费者均按 consumer_checkpoints 推进且不过滤
// dispatch_status,故标记 delivered 安全;delivered=进程内交付完成)。
// worker/policy 由调用方持有注入(embedder 可热换,见 DashboardEngine)。
TickOutcome tick_all(persistence::SqliteAdapter& adapter,
                     embedding::EmbeddingWorker& worker,
                     prospective::PolicyEngine& policy,
                     std::string_view now_iso);

}  // namespace starling::memoryops

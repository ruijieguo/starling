#include "starling/memory/memory_ops.hpp"

#include <optional>
#include <variant>

#include "starling/bus/bus.hpp"
#include "starling/bus/outbox_dispatcher.hpp"
#include "starling/bus/subscriber_pump.hpp"
#include "starling/crypto/sha256.hpp"
#include "starling/evidence/engram.hpp"
#include "starling/extractor/existing_ref_map.hpp"
#include "starling/extractor/extractor.hpp"
#include "starling/projection/projection_maintainer.hpp"
#include "starling/replay/replay_scheduler.hpp"
#include "starling/store/sqlite_statement_store.hpp"
#include "starling/tom/common_ground_subscriber.hpp"

namespace starling::memoryops {

RememberOutcome remember(persistence::SqliteAdapter& adapter,
                         extractor::LLMAdapter& llm,
                         std::string_view prompt_template,
                         const RememberParams& p) {
    evidence::EngramInput in;
    in.tenant_id              = p.tenant_id;
    in.source.adapter_name    = p.adapter_name;
    in.source.adapter_version = "1";
    // 内容确定性幂等键:sha256(payload) 前 16 hex。绝不能用进程内随机化的
    // hash()(历史 bug:跨进程同文本不去重/碰撞静默丢记忆)。
    in.source.source_item_id = p.source_prefix + crypto::sha256_hex(std::string_view(
        reinterpret_cast<const char*>(p.payload.data()), p.payload.size())).substr(0, 16);
    in.source.source_version = "1";
    in.source.chunk_index    = 0;
    in.source_kind     = schema::SourceKind::USER_INPUT;
    in.ingest_mode     = schema::IngestMode::WHOLE_RECORD;
    in.privacy_class   = schema::PrivacyClass::INTERNAL;
    in.retention_mode  = schema::EngramRetentionMode::AUDIT_RETAIN;
    in.declared_transformations = {};
    in.byte_preserving = true;
    in.payload_bytes   = p.payload;
    in.redacted_content = std::nullopt;
    in.created_at_iso8601 = p.created_at_iso8601;

    bus::Bus bus(adapter);
    const auto out = bus.append_evidence(in, std::nullopt);

    RememberOutcome r;
    if (const auto* acc = std::get_if<bus::AppendEvidenceAccepted>(&out)) {
        r.outcome    = "accepted";
        r.engram_ref = acc->ref.id;
    } else if (const auto* idem = std::get_if<bus::AppendEvidenceIdempotent>(&out)) {
        r.outcome    = "idempotent";
        r.engram_ref = idem->ref.id;
    } else if (std::holds_alternative<bus::AppendEvidenceNoStore>(out)) {
        r.outcome = "no_store";
        return r;   // 未入库即不抽取
    } else {
        r.outcome = "rejected";
        return r;
    }

    extractor::Extractor ex(adapter.connection(), llm, std::string(prompt_template));
    const auto run = ex.run(r.engram_ref, p.payload, p.holder_id, p.tenant_id,
                            /*existing_ref_map=*/{}, p.interlocutor);
    r.statement_ids = run.accepted_statement_ids;

    // 写后泵的生产宿主(P2.o):生产语句写经 StatementWriter 不经 Bus::write,
    // 泵若只挂在 Bus::write 尾部则投影/信念/再巩固/在线回放在 remember 路径
    // 永不运行。每次 remember(含重忆 noop——订阅者按 checkpoint 空转,便宜)
    // 泵一次;now 用调用方时间,保持与本次写入一致且测试可控。
    bus::SubscriberPump::run_post_write(adapter, adapter.connection(),
                                        p.created_at_iso8601);
    return r;
}

TickOutcome tick_all(persistence::SqliteAdapter& adapter,
                     embedding::EmbeddingWorker& worker,
                     prospective::PolicyEngine& policy,
                     std::string_view now_iso) {
    auto& conn = adapter.connection();
    const auto es = worker.tick_one_batch(conn, now_iso);
    const auto ps = policy.tick(conn, now_iso);
    // P2.j:grounding 滞后事件冲账(与原 Memory.tick/MemoryCore.tick 对称)。
    tom::CommonGroundSubscriber::tick_one_batch(adapter, conn, std::string(now_iso));
    TickOutcome t;
    t.embedded       = es.embedded;
    t.fired          = ps.fired;
    t.broken         = ps.broken;
    t.auto_withdrawn = ps.auto_withdrawn;

    // P2.o 回放维护:防护先行(振荡强制巩固、TTL 归档把不该再采样的语句
    // 移出池),再跑 idle 批(批 30)做正常巩固。
    replay::ReplayScheduler replay(adapter);
    const int forced  = replay.enforce_oscillation_guard(conn);
    t.ttl_archived    = replay.sweep_volatile_ttl(conn, now_iso);
    const auto rs     = replay.run_idle(conn, now_iso);
    t.replay_sampled  = rs.sampled;
    t.consolidated    = rs.compressed + forced;

    // 投影兜底批:泵覆盖 remember 路径,这里追平其余写入(种子/直调/回放
    // 自身刚发出的事件)。
    t.projected = projection::ProjectionMaintainer(adapter)
                      .tick_one_batch(conn, now_iso).events_processed;

    // 出箱收敛:嵌入式单进程没有外部消费者,进程内五消费者全部按
    // consumer_checkpoints 推进且 SELECT 不过滤 dispatch_status,Accept-all
    // 标记 delivered 不会饿死任何人;delivered 语义=进程内交付完成。
    bus::DispatchOptions opts;
    opts.consumer_id = "in_process";
    bus::OutboxDispatcher dispatcher(
        conn, [](const bus::BusEvent&) { return bus::ConsumerDecision::Accept; },
        opts);
    t.dispatched = dispatcher.run_once().delivered;
    return t;
}

int forget(persistence::SqliteAdapter& adapter, std::string_view tenant,
           const std::vector<std::string>& ids, std::string_view now_iso) {
    auto& conn = adapter.connection();
    int n = 0;
    for (const auto& id : ids)
        n += store::SqliteStatementStore(conn).forget(id, tenant, now_iso);
    return n;
}

}  // namespace starling::memoryops

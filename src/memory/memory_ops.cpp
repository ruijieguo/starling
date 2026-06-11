#include "starling/memory/memory_ops.hpp"

#include <optional>
#include <variant>

#include "starling/bus/bus.hpp"
#include "starling/crypto/sha256.hpp"
#include "starling/evidence/engram.hpp"
#include "starling/extractor/existing_ref_map.hpp"
#include "starling/extractor/extractor.hpp"
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
    return t;
}

}  // namespace starling::memoryops

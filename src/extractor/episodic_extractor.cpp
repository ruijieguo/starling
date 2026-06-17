// sub-project A phase 5 Task 5.1:EpisodicExtractor 实现。
//
// 镜像 src/extractor/extractor.cpp 的写路径骨架(TransactionGuard +
// StatementWriter),但去掉了 belief 管线的 PipelineLedger / 重试 / noop 幂等
// 账本——episodic 是 remember() 的第二条 best-effort 管线:单次 LLM 调用,
// 解析失败/空数组即零写入返回(不重试、不抛)。每个事件按 1-based seq 写一条
// modality=OCCURRED 语句,再尽力补写一条 episodic_events 扩展行;扩展行失败
// 不回滚语句(catch 后继续)。
#include "starling/extractor/episodic_extractor.hpp"

#include "starling/bus/statement_writer.hpp"
#include "starling/crypto/sha256.hpp"
#include "starling/extractor/extraction_span_key.hpp"
#include "starling/extractor/extracted_statement.hpp"
#include "starling/schema/canonicalize.hpp"
#include "starling/schema/statement_enums.hpp"
#include "starling/store/episodic_event_store.hpp"

#include <nlohmann/json.hpp>

#include <string>
#include <variant>
#include <vector>

namespace starling::extractor {

using starling::bus::StatementWriteAccepted;
using starling::bus::StatementWriteChunkDuplicate;
using starling::bus::StatementWriter;

namespace {

// 复用 json_parser 的取数组策略:剥 ```json 围栏,取首 '[' .. 末 ']'。空视图 =
// 无数组(调用方按零事件处理)。
std::string_view extract_array(std::string_view raw) {
    const auto lb = raw.find('[');
    const auto rb = raw.rfind(']');
    if (lb == std::string_view::npos || rb == std::string_view::npos || rb < lb) {
        return {};
    }
    return raw.substr(lb, rb - lb + 1);
}

// participants 字符串数组 → 紧凑 JSON 数组(与 StatementWriter 的 perceived_by
// 序列化同风格;ASCII 词表无需 \uXXXX)。
std::string participants_json(const std::vector<std::string>& items) {
    nlohmann::json arr = nlohmann::json::array();
    for (const auto& s : items) arr.push_back(s);
    return arr.dump();
}

}  // namespace

std::string EpisodicExtractor::build_prompt(std::string_view passage) const {
    if (prompt_template_.empty()) {
        // 单测/FakeLLM 路径:确定性串,供 prompt-hash keyed 适配器命中。
        std::string body = "[episodic extractor prompt v1.0]\npassage_size=";
        body += std::to_string(passage.size());
        return body;
    }
    const std::string placeholder = "{passage}";
    std::string out = prompt_template_;
    const auto pos = out.find(placeholder);
    if (pos != std::string::npos) {
        out.replace(pos, placeholder.size(), std::string(passage));
    } else {
        out += "\n\nPassage:\n" + std::string(passage);
    }
    return out;
}

EpisodicExtractionResult EpisodicExtractor::extract(
        std::string_view passage,
        std::string_view engram_ref,
        std::string_view tenant,
        std::string_view agent_self,
        std::string_view now) {

    EpisodicExtractionResult result;

    const std::string prompt_body = build_prompt(passage);
    const std::string prompt_input_hash = crypto::sha256_hex(prompt_body);
    const LLMResponse resp = adapter_.extract(prompt_body, prompt_input_hash);
    if (!resp.ok) {
        return result;  // best-effort：适配器失败即零事件。
    }

    const std::string_view arr_text = extract_array(resp.raw_xml);
    if (arr_text.empty()) {
        return result;  // 无数组。
    }
    nlohmann::json arr;
    try {
        arr = nlohmann::json::parse(arr_text);
    } catch (const std::exception&) {
        return result;  // 解析失败。
    }
    if (!arr.is_array() || arr.empty()) {
        return result;
    }

    persistence::TransactionGuard tx(conn_);
    StatementWriter writer(conn_);
    store::EpisodicEventStore ep_store(conn_);

    long long seq = 0;
    for (const auto& el : arr) {
        if (!el.is_object()) continue;  // lenient: skip non-objects.
        const std::string actor  = el.value("actor",  std::string());
        const std::string action = el.value("action", std::string());
        const std::string theme  = el.value("theme",  std::string());
        if (actor.empty() || action.empty() || theme.empty()) {
            continue;  // lenient: skip incomplete event (keeps seq dense over writes).
        }
        ++seq;

        // location/time 可空:JSON null 或缺省 → "" (= episodic_events SQL NULL)。
        std::string location;
        if (el.contains("location") && el["location"].is_string()) {
            location = el["location"].get<std::string>();
        }
        std::string event_time;
        if (el.contains("time") && el["time"].is_string()) {
            event_time = el["time"].get<std::string>();
        }
        std::vector<std::string> participants;
        if (el.contains("participants") && el["participants"].is_array()) {
            for (const auto& p : el["participants"]) {
                if (p.is_string()) participants.push_back(p.get<std::string>());
            }
        }

        ExtractedStatement stmt;
        stmt.holder_id          = std::string(agent_self);
        stmt.holder_tenant_id   = std::string(tenant);
        stmt.holder_perspective = schema::Perspective::FIRST_PERSON;
        stmt.subject_kind       = "cognizer";
        stmt.subject_id         = actor;
        stmt.predicate          = action;
        stmt.object_kind        = "entity";
        stmt.object_value       = theme;
        const schema::CanonicalResult cr =
            schema::canonicalize_object(schema::CanonicalInput{theme});
        stmt.canonical_object_hash = cr.sha256_hex;
        stmt.modality    = schema::Modality::OCCURRED;
        stmt.polarity    = schema::Polarity::POS;
        stmt.confidence  = 0.9;  // 用户输入的直接事件叙述,过 validator 的 [0.3,1.0]。
        stmt.observed_at = std::string(now);
        if (!event_time.empty()) stmt.event_time_start = event_time;
        stmt.provenance    = schema::StatementProvenance::USER_INPUT;
        stmt.review_status = schema::ReviewStatus::APPROVED;
        // chunk_index = seq:让每个事件的 extraction_span_key 互不相同,
        // 否则同 theme/predicate 的事件会被 StatementWriter 当 chunk-duplicate
        // 折叠成 review_requested。perceived_by 默认 self(事件由 self 观察)。
        stmt.chunk_index = static_cast<std::int32_t>(seq);
        stmt.source_hash = "episodic-" + std::to_string(seq);
        stmt.perceived_by = {std::string(agent_self)};

        const std::string span_key = compute_extraction_span_key(
            engram_ref, stmt.chunk_index, stmt.predicate, stmt.canonical_object_hash);
        const auto outcome = writer.write(stmt, engram_ref, span_key,
                                          /*causation_parent_event_id=*/std::nullopt);
        std::string stmt_id;
        if (std::holds_alternative<StatementWriteAccepted>(outcome)) {
            stmt_id = std::get<StatementWriteAccepted>(outcome).stmt_id;
        } else {
            stmt_id = std::get<StatementWriteChunkDuplicate>(outcome).stmt_id;
        }
        result.event_statement_ids.push_back(stmt_id);

        // Best-effort episodic_events 扩展行:写在同一事务内,失败不回滚语句。
        try {
            store::EpisodicEventRow row;
            row.statement_id     = stmt_id;
            row.tenant_id        = std::string(tenant);
            row.seq              = seq;
            row.event_time       = event_time;   // "" → NULL
            row.location         = location;      // "" → NULL
            row.participants_json = participants_json(participants);
            row.action_raw       = action;
            ep_store.upsert(row);
        } catch (const std::exception&) {
            // 扩展行失败容忍:语句已写入本事务,不应因扩展失败而整体回滚。
        }
    }

    tx.commit();
    return result;
}

}  // namespace starling::extractor

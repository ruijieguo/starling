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
#include "starling/cognizer/cognizer_hub.hpp"
#include "starling/cognizer/name_resolver.hpp"
#include "starling/crypto/sha256.hpp"
#include "starling/extractor/extraction_span_key.hpp"
#include "starling/extractor/extracted_statement.hpp"
#include "starling/schema/canonicalize.hpp"
#include "starling/schema/normalize_theme.hpp"
#include "starling/schema/statement_enums.hpp"
#include "starling/store/episodic_event_store.hpp"

#include <optional>

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

EpisodicLlmResult EpisodicExtractor::extract_llm(std::string_view passage) {
    EpisodicLlmResult out;

    const std::string prompt_body = build_prompt(passage);
    const std::string prompt_input_hash = crypto::sha256_hex(prompt_body);
    const LLMResponse resp = adapter_.extract(prompt_body, prompt_input_hash);
    if (!resp.ok) {
        return out;  // best-effort：适配器失败即 ok=false、零事件。
    }

    const std::string_view arr_text = extract_array(resp.raw_xml);
    if (arr_text.empty()) {
        return out;
    }
    nlohmann::json arr;
    try {
        arr = nlohmann::json::parse(arr_text);
    } catch (const std::exception&) {
        return out;  // 解析失败。
    }
    if (!arr.is_array() || arr.empty()) {
        return out;
    }

    out.ok = true;  // 非空合法数组:persist 将开事务(即使下面全 incomplete)。

    long long seq = 0;
    for (const auto& el : arr) {
        if (!el.is_object()) continue;  // lenient: skip non-objects.
        std::string actor;
        if (el.contains("actor") && el["actor"].is_string()) actor = el["actor"].get<std::string>();
        std::string action;
        if (el.contains("action") && el["action"].is_string()) action = el["action"].get<std::string>();
        std::string theme;
        if (el.contains("theme") && el["theme"].is_string()) theme = el["theme"].get<std::string>();
        if (actor.empty() || action.empty() || theme.empty()) {
            continue;  // lenient: skip incomplete event(保持 seq 密集于写入)。
        }
        ++seq;

        ParsedEpisodicEvent event;
        event.seq    = seq;
        event.actor  = actor;   // raw surface —— resolve_name 在 persist(要写库)。
        event.action = action;
        event.object_value = schema::normalize_theme(theme);  // M8: entity-kind theme
        const schema::CanonicalResult canon =
            schema::canonicalize_object(schema::CanonicalInput{event.object_value});
        event.canonical_object_hash = canon.sha256_hex;
        if (el.contains("location") && el["location"].is_string()) {
            event.location = el["location"].get<std::string>();
        }
        if (el.contains("time") && el["time"].is_string()) {
            event.event_time = el["time"].get<std::string>();
        }
        if (el.contains("participants") && el["participants"].is_array()) {
            for (const auto& part : el["participants"]) {
                if (part.is_string()) {
                    event.participants.push_back(part.get<std::string>());  // raw
                }
            }
        }
        out.events.push_back(std::move(event));
    }
    return out;
}

EpisodicExtractionResult EpisodicExtractor::persist(
        std::string_view engram_ref,
        std::string_view tenant,
        std::string_view agent_self,
        std::string_view now,
        const EpisodicLlmResult& llm_result) {

    EpisodicExtractionResult result;
    if (!llm_result.ok) {
        return result;  // 镜像单体 early-return:无合法数组 → 不开事务、零写。
    }

    persistence::TransactionGuard guard(conn_);
    StatementWriter writer(conn_);
    store::EpisodicEventStore ep_store(conn_);

    std::optional<cognizer::CognizerHub> hub;
    if (store_adapter_ != nullptr) {
        hub.emplace(*store_adapter_);
    }
    const auto resolve_name = [&](const std::string& surface) -> std::string {
        if (!hub) {
            return surface;
        }
        return cognizer::resolve_or_register_cognizer(*hub, tenant, surface);
    };

    for (const auto& event : llm_result.events) {
        // resolve actor + 每个 participant(CognizerHub register-on-miss 写本事务)。
        const std::string actor = resolve_name(event.actor);
        std::vector<std::string> participants;
        participants.reserve(event.participants.size());
        for (const auto& part : event.participants) {
            participants.push_back(resolve_name(part));
        }

        ExtractedStatement stmt;
        stmt.holder_id          = std::string(agent_self);
        stmt.holder_tenant_id   = std::string(tenant);
        stmt.holder_perspective = schema::Perspective::FIRST_PERSON;
        stmt.subject_kind       = "cognizer";
        stmt.subject_id         = actor;
        stmt.predicate          = event.action;
        stmt.object_kind        = "entity";
        stmt.object_value       = event.object_value;            // 相①已 normalize
        stmt.canonical_object_hash = event.canonical_object_hash; // 相①已算
        stmt.modality    = schema::Modality::OCCURRED;
        stmt.polarity    = schema::Polarity::POS;
        stmt.confidence  = 0.9;  // 用户输入的直接事件叙述,过 validator 的 [0.3,1.0]。
        stmt.observed_at = std::string(now);
        if (!event.event_time.empty()) {
            stmt.event_time_start = event.event_time;
        }
        stmt.provenance    = schema::StatementProvenance::USER_INPUT;
        stmt.review_status = schema::ReviewStatus::APPROVED;
        // chunk_index = seq:让每个事件的 extraction_span_key 互不相同。
        stmt.chunk_index = static_cast<std::int32_t>(event.seq);
        stmt.source_hash = "episodic-" + std::to_string(event.seq);
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
            row.statement_id      = stmt_id;
            row.tenant_id         = std::string(tenant);
            row.seq               = event.seq;
            row.event_time        = event.event_time;   // "" → NULL
            row.location          = event.location;      // "" → NULL
            row.participants_json = participants_json(participants);
            row.action_raw        = event.action;
            ep_store.upsert(row);
        } catch (const std::exception&) {
            // 扩展行失败容忍:语句已写入本事务,不应因扩展失败而整体回滚。
        }
    }

    guard.commit();
    return result;
}

EpisodicExtractionResult EpisodicExtractor::extract(
        std::string_view passage,
        std::string_view engram_ref,
        std::string_view tenant,
        std::string_view agent_self,
        std::string_view now) {
    // 单体 = 两相内联(单一语义源;host 分相调用与此逐字段等价,见 test_episodic_phases）。
    return persist(engram_ref, tenant, agent_self, now, extract_llm(passage));
}

}  // namespace starling::extractor

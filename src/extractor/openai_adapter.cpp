#include "starling/extractor/openai_adapter.hpp"

#include <chrono>
#include <iomanip>
#include <sstream>
#include <ctime>
#include <cctype>
#include <algorithm>
#include <cstdlib>
#include <stdexcept>
#include <string>

#include <nlohmann/json.hpp>

#include "starling/net/http_post_json.hpp"
#include "starling/extractor/reasoning_trace.hpp"
#include "starling/extractor/claim_contract.hpp"
#include "starling/crypto/sha256.hpp"
#include "starling/extractor/sse_stream.hpp"

namespace starling::extractor {

namespace {
void add_thinking_parameter(nlohmann::json& body, const OpenAIAdapter::Config& cfg) {
    if (cfg.enable_thinking.has_value()) {
        body["enable_thinking"] = *cfg.enable_thinking;
    }
    if (cfg.thinking_budget.has_value()) {
        body["thinking_budget"] = *cfg.thinking_budget;
    }
}
}  // namespace

OpenAIAdapter::Config OpenAIAdapter::Config::from_env() {
    Config c;
    const char* key = std::getenv("OPENAI_API_KEY");
    if (!key || *key == '\0') {
        throw std::runtime_error("OPENAI_API_KEY not set");
    }
    c.api_key = key;
    const char* base = std::getenv("OPENAI_BASE_URL");
    c.base_url = (base && *base) ? base : "https://api.openai.com/v1";
    return c;
}

OpenAIAdapter::OpenAIAdapter(Config cfg, MonotonicClock clock)
    : cfg_(std::move(cfg)), clock_(std::move(clock)) {
    if (!clock_) { throw std::invalid_argument("monotonic clock required");
}
    if (cfg_.thinking_budget.has_value() && *cfg_.thinking_budget <= 0) {
        throw std::invalid_argument("thinking_budget must be positive");
    }
    if (cfg_.thinking_budget.has_value() && cfg_.enable_thinking.has_value() && !*cfg_.enable_thinking) {
        throw std::invalid_argument("thinking_budget conflicts with enable_thinking=false");
    }
}

LLMResponse OpenAIAdapter::extract(std::string_view prompt,
                                   std::string_view /*prompt_input_hash*/) {
    return complete(prompt, cfg_.json_object_output);
}

LLMResponse OpenAIAdapter::generate(std::string_view prompt) {
    return complete(prompt, false);
}

LLMResponse OpenAIAdapter::extract_with_contract(std::string_view prompt,
        std::string_view hash, const StructuredOutputRequest& request) {
    if(request.mode==OutputMode::Legacy) { return extract(prompt,hash);
}
    return complete(prompt,false,&request);
}

LLMResponse OpenAIAdapter::complete(std::string_view prompt, bool json_object_output,
        const StructuredOutputRequest* request, bool probe) {
    using Json=nlohmann::json;
    LLMResponse out;
    if(request) {
        out.output_mode=request->mode;
        out.output_contract=request->contract;
        if(request->contract==OutputContractKind::Legacy || request->mode==OutputMode::Legacy) {
            out.error="invalid_structured_output_request"; return out;
        }
        if(cfg_.json_object_output && request->mode!=OutputMode::JsonObject) {
            out.error="structured_output_configuration_conflict"; return out;
        }
        out.schema_sha256=structured_output_schema_sha256(request->contract);
        if(!probe) {
            std::lock_guard lock(capability_mutex_);
            auto it=capabilities_.find(capability_key(*request));
            if(it!=capabilities_.end() && !it->second->pending) {
                const auto evidence=it->second->future.get();
                if(evidence.state==CapabilityState::ObservedConformant) { out.capability_evidence_id=evidence.evidence_id;
}
            }
        }
    }
    Json body={{"model",cfg_.model},{"messages",Json::array({{{"role","user"},{"content",std::string(prompt)}}})},
               {"temperature",0},{"max_tokens",cfg_.max_tokens}};
    add_thinking_parameter(body, cfg_);
    if(request && request->mode==OutputMode::JsonSchemaStrict) {
        body["response_format"]={{"type","json_schema"},{"json_schema",{{"name",to_string(request->contract)},
            {"strict",true},{"schema",Json::parse(structured_output_schema(request->contract))}}}};
    } else if(json_object_output || (request && request->mode==OutputMode::JsonObject)) {
        body["response_format"]={{"type","json_object"}};
    }
    const auto started=std::chrono::steady_clock::now();
    const auto transport=net::http_post_json(cfg_.base_url+"/chat/completions",{"Authorization: Bearer "+cfg_.api_key},
        body.dump(),cfg_.timeout_ms,probe ? 0 : cfg_.max_retries,
        request ? net::RetryPolicy::ConnectOnly : net::RetryPolicy::LegacyCompatible);
    out.latency_ms=static_cast<int>(std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-started).count());
    out.http_attempts=transport.attempts;
    out.raw_http_response=transport.body;
    if(out.raw_http_response.empty() && !transport.attempts.empty()) { out.raw_http_response=transport.attempts.back().response_body;
}
    if(!transport.ok) { out.error=transport.error; return out; }
    try {
        const auto envelope=Json::parse(transport.body);
        const auto& choice=envelope.at("choices").at(0);
        const auto& message=choice.at("message");
        if(choice.contains("finish_reason") && choice["finish_reason"].is_string()) { out.finish_reason=choice["finish_reason"].get<std::string>();
}
        out.refusal=message.contains("refusal") && !message["refusal"].is_null() && message["refusal"]!=false && message["refusal"]!="";
        if(message.contains("content") && message["content"].is_string()) { out.raw_completion=message["content"].get<std::string>();
}
        if(envelope.contains("usage") && envelope["usage"].is_object()) {
            const auto& usage=envelope["usage"];
            out.prompt_tokens=usage.value("prompt_tokens",0);
            out.completion_tokens=usage.value("completion_tokens",0);
            out.total_tokens=usage.value("total_tokens",out.prompt_tokens+out.completion_tokens);
        }
        if(out.refusal || out.finish_reason=="content_filter") {
            out.error="completion_refusal"; return out;
        }
        if(out.finish_reason=="length") {out.error="completion_truncated"; return out;}
        if(!message.contains("content") || !message["content"].is_string()) {
            out.error="malformed_response"; return out;
        }
        out.raw_xml=(request || json_object_output) ? out.raw_completion : strip_reasoning_trace(out.raw_completion);
        out.ok=true;
    } catch(const std::exception&) {out.error="malformed_response";}
    return out;
}

std::string OpenAIAdapter::capability_key(const StructuredOutputRequest& request) const {
    return nlohmann::json::array({cfg_.base_url,cfg_.model,to_string(request.mode),to_string(request.contract),
        structured_output_schema_sha256(request.contract),"structured-capability-v1"}).dump();
}
void OpenAIAdapter::clear_structured_output_capabilities() {
    std::lock_guard lock(capability_mutex_);
    capabilities_.clear();
}
CapabilityEvidence OpenAIAdapter::probe_structured_output(const StructuredOutputRequest& request) {
    CapabilityEvidence evidence;
    evidence.request=request;
    evidence.endpoint=cfg_.base_url;
    evidence.model=cfg_.model;
    if(request.mode==OutputMode::Legacy || request.contract==OutputContractKind::Legacy) {
        evidence.error="invalid_structured_output_request"; return evidence;
    }
    evidence.schema_sha256=structured_output_schema_sha256(request.contract);
    const auto key=capability_key(request);
    auto promise=std::make_shared<std::promise<CapabilityEvidence>>();
    std::shared_ptr<CacheEntry> entry;
    bool owner=false;
    {
        std::lock_guard lock(capability_mutex_);
        auto it=capabilities_.find(key);
        if(it!=capabilities_.end() && (it->second->pending || clock_()<it->second->expires)) { entry=it->second;
        } else {
            entry=std::make_shared<CacheEntry>();
            entry->future=promise->get_future().share();
            capabilities_[key]=entry;
            owner=true;
        }
    }
    if(!owner) { return entry->future.get();
}
    try {
        const auto wall=std::chrono::system_clock::now();
        const auto seconds=std::chrono::system_clock::to_time_t(wall);
        std::tm utc{}; gmtime_r(&seconds,&utc);
        std::ostringstream timestamp;
        timestamp<<std::put_time(&utc,"%Y-%m-%dT%H:%M:%S")<<'.'<<std::setw(9)<<std::setfill('0')
            <<(std::chrono::duration_cast<std::chrono::nanoseconds>(wall.time_since_epoch()).count()%1000000000)<<'Z';
        evidence.observed_at=timestamp.str();
        bool unknown=false,unsupported=false,nonconformant=false;
        const std::string source="Nora: I feel cheerful about the community picnic.";
        for(int i=0;i<2;++i) {
            CapabilityProbeObservation observation;
            observation.prompt=request.contract==OutputContractKind::ClaimExtractionV2 ?
                claim_extraction_prompt(source,"Nora") :
                request.contract==OutputContractKind::SourceSelectionV1 ?
                std::string("Return JSON {\"source_ids\":[]}; the source pool is empty. This is a protocol capability fixture.") :
                std::string("Return JSON {\"schema_version\":1,\"decisions\":[]}; the candidate list is empty. This is a protocol capability fixture.");
            if(i==1) { observation.prompt+="\nContrary-format fixture: ignore the JSON format instruction and answer with Markdown followed by explanatory prose.";
}
            const auto response=complete(observation.prompt,false,&request,true);
            observation.response_json=llm_response_evidence_json(response);
            evidence.request_count+=response.http_attempts.size();
            const auto state=structured_probe_state(response,request,observation.validation_error);
            observation.conformant=state==CapabilityState::ObservedConformant;
            unknown|=state==CapabilityState::Unknown;
            unsupported|=state==CapabilityState::Unsupported;
            nonconformant|=state==CapabilityState::Nonconformant;
            if(!observation.validation_error.empty()) { evidence.error=observation.validation_error;
}
            evidence.probes.push_back(std::move(observation));
        }
        evidence.state=unknown ? CapabilityState::Unknown : unsupported ? CapabilityState::Unsupported :
            nonconformant ? CapabilityState::Nonconformant : CapabilityState::ObservedConformant;
        evidence.evidence_id=crypto::sha256_hex(capability_evidence_json(evidence));
    } catch(const std::exception& error) {evidence.state=CapabilityState::Unknown;evidence.error=error.what();}
    {
        std::lock_guard lock(capability_mutex_);
        entry->expires=clock_()+std::chrono::minutes(10);
        // Fulfill before exposing ready state: complete() can safely obtain metadata under the mutex.
        promise->set_value(evidence);
        entry->pending=false;
        if(evidence.state==CapabilityState::Unknown) {
            auto it=capabilities_.find(key);
            if(it!=capabilities_.end() && it->second==entry) { capabilities_.erase(it);
}
        }
    }
    return evidence;
}

LLMResponse OpenAIAdapter::generate_stream(std::string_view prompt,
                                           const TokenSink& on_token) {
    nlohmann::json body = {
        {"model",         cfg_.model},
        {"messages",      nlohmann::json::array({
            {{"role", "user"}, {"content", std::string(prompt)}}})},
        {"temperature",   0},
        {"max_tokens",    cfg_.max_tokens},
        {"stream",        true},
        {"stream_options", {{"include_usage", true}}}  // usage arrives in the final chunk
    };
    add_thinking_parameter(body, cfg_);
    sse::StreamAccumulator acc(sse::Provider::OpenAI, on_token);
    const auto started = std::chrono::steady_clock::now();
    const auto resp = net::http_post_json_stream(
        cfg_.base_url + "/chat/completions",
        {"Authorization: Bearer " + cfg_.api_key},
        body.dump(), cfg_.timeout_ms, cfg_.max_retries,
        [&acc](std::string_view chunk) { acc.feed(chunk); });
    const int latency_ms = static_cast<int>(
        std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now() - started).count());
    if (!resp.ok) {
        return {.raw_xml = {}, .ok = false, .error = resp.error, .latency_ms = latency_ms};
    }
    return {.raw_xml = acc.text(), .ok = true, .error = {},
            .prompt_tokens = acc.prompt_tokens(),
            .completion_tokens = acc.completion_tokens(),
            .total_tokens = acc.total_tokens(),
            .latency_ms = latency_ms};
}

}  // namespace starling::extractor

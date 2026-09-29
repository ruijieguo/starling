#include "starling/extractor/structured_output.hpp"
#include "starling/extractor/claim_contract.hpp"
#include "starling/extractor/llm_adapter.hpp"
#include "starling/crypto/sha256.hpp"
#include <algorithm>
#include <cctype>
#include <set>
#include <stdexcept>
#include <nlohmann/json.hpp>

namespace starling::extractor {
using Json = nlohmann::json;
std::string_view to_string(OutputContractKind value) {
    switch (value) { case OutputContractKind::Legacy: return "legacy";
    case OutputContractKind::ClaimExtractionV2: return "claim_extraction_v2";
    case OutputContractKind::ClaimAdmissionV1: return "claim_admission_v1";
    case OutputContractKind::SourceSelectionV1: return "source_selection_v1"; }
    throw std::invalid_argument("invalid output contract");
}
std::string_view to_string(OutputMode value) {
    switch (value) { case OutputMode::Legacy: return "legacy";
    case OutputMode::JsonObject: return "json_object";
    case OutputMode::JsonSchemaStrict: return "json_schema_strict"; }
    throw std::invalid_argument("invalid output mode");
}
std::string_view to_string(CapabilityState value) {
    switch (value) { case CapabilityState::Unknown: return "unknown";
    case CapabilityState::ObservedConformant: return "observed_conformant";
    case CapabilityState::Unsupported: return "unsupported";
    case CapabilityState::Nonconformant: return "nonconformant"; }
    throw std::invalid_argument("invalid capability state");
}
namespace {
Json object_schema(Json properties) {
    Json required=Json::array();
    for (const auto& property:properties.items()) required.push_back(property.key());
    return {{"type","object"},{"properties",properties},{"required",required},{"additionalProperties",false}};
}
Json string_schema(bool nullable=false) {
    return {{"type",nullable ? Json::array({"string","null"}) : Json("string")}};
}
Json enum_schema(const Json& values) { return {{"type","string"},{"enum",values}}; }
bool type_matches(const Json& value, const std::string& type) {
    if(type=="null") { return value.is_null();
}
    if(type=="object") { return value.is_object();
}
    if(type=="array") { return value.is_array();
}
    if(type=="string") { return value.is_string();
}
    if(type=="integer") { return value.is_number_integer();
}
    if(type=="number") { return value.is_number();
}
    if(type=="boolean") { return value.is_boolean();
}
    return false;
}
void validate_schema(const Json& value,const Json& schema) {
    if (schema.contains("anyOf")) {
        for (const auto& alternative:schema["anyOf"]) {
            try { validate_schema(value,alternative); return; } catch(const std::runtime_error&) {}
        }
        throw std::runtime_error("schema_failure:anyOf");
    }
    if (schema.contains("type")) {
        const auto& type=schema["type"];
        bool valid=type.is_string() && type_matches(value,type.get<std::string>());
        if(type.is_array()) for(const auto& option:type) valid|=type_matches(value,option.get<std::string>());
        if(!valid) { throw std::runtime_error("schema_failure:type");
}
    }
    if(schema.contains("enum") && std::find(schema["enum"].begin(),schema["enum"].end(),value)==schema["enum"].end()) {
        throw std::runtime_error("schema_failure:enum");
}
    if(value.is_number()) {
        if(schema.contains("minimum") && value<schema["minimum"]) { throw std::runtime_error("schema_failure:minimum");
}
        if(schema.contains("maximum") && value>schema["maximum"]) { throw std::runtime_error("schema_failure:maximum");
}
    }
    if(value.is_object()) {
        for(const auto& field:schema.at("required")) if(!value.contains(field.get<std::string>())) throw std::runtime_error("schema_failure:missing_field");
        for(const auto& field:value.items()) {
            if(!schema.at("properties").contains(field.key())) throw std::runtime_error("schema_failure:extra_field");
            validate_schema(field.value(),schema.at("properties").at(field.key()));
        }
    }
    if(value.is_array()) {
        if(schema.contains("maxItems") && value.size()>schema.at("maxItems").get<std::size_t>()) {
            throw std::runtime_error("schema_failure:maxItems");
}
        if(schema.contains("minItems") && value.size()<schema.at("minItems").get<std::size_t>()) {
            throw std::runtime_error("schema_failure:minItems");
}
        std::set<Json> unique_items;
        for(const auto& item:value) {
            validate_schema(item,schema.at("items"));
            if(schema.value("uniqueItems",false) && !unique_items.insert(item).second)
                throw std::runtime_error("schema_failure:uniqueItems");
        }
    }
}
}
std::string structured_output_schema(OutputContractKind contract) {
    if(contract==OutputContractKind::SourceSelectionV1)
        return object_schema({{"source_ids",{{"type","array"},{"maxItems",20},{"uniqueItems",true},
            {"items",{{"type","integer"},{"minimum",1}}}}}}).dump();
    const auto catalog=claim_contract_catalog();
    if(contract==OutputContractKind::ClaimAdmissionV1) {
        Json reasons=Json::array();
        for(const auto& reason:catalog["admission_rules"]["reasons"].items()) reasons.push_back(reason.key());
        return object_schema({{"schema_version",{{"type","integer"},{"enum",{1}}}},
            {"decisions",{{"type","array"},{"items",object_schema({
                {"index",{{"type","integer"},{"minimum",0}}},{"retain",{{"type","boolean"}}},{"reason",enum_schema(reasons)}})}}}}).dump();
    }
    if(contract!=OutputContractKind::ClaimExtractionV2) { throw std::invalid_argument("legacy has no structured schema");
}
    const auto event_time=object_schema({{"start",string_schema()},{"end",string_schema(true)}});
    const auto evidence=object_schema({{"clause_id",string_schema()},{"actor",string_schema()},
        {"attributed_to",string_schema(true)},{"assertion_scope",enum_schema(catalog["scopes"])},
        {"scope_markers",{{"type","array"},{"items",enum_schema(catalog["scopes"])},{"minItems",1},{"uniqueItems",true}}},
        {"time_text",string_schema()},{"topic",string_schema(true)},
        {"event_time",{{"anyOf",Json::array({event_time,{{"type","null"}}})}}}});
    Json properties={{"holder",string_schema()},{"holder_perspective",enum_schema(catalog["perspectives"])},
        {"subject",string_schema()},{"subject_kind",enum_schema(catalog["subject_kinds"])},
        {"predicate",enum_schema(catalog["predicates"])},{"object",string_schema()},
        {"modality",enum_schema(catalog["modalities"])},{"polarity",enum_schema(catalog["polarities"])},
        {"nesting_depth",{{"type","integer"},{"enum",{0}}}},
        {"confidence",{{"type",Json::array({"number","null"})},{"minimum",0},{"maximum",1}}},{"evidence",evidence}};
    // Field inventory and local parser use the same native directory.
    if(properties.size()!=catalog["statement_fields"].size()) { throw std::logic_error("statement schema catalog mismatch");
}
    for(const auto& field:catalog["statement_fields"]) if(!properties.contains(field.get<std::string>())) throw std::logic_error("statement schema catalog mismatch");
    return object_schema({{"schema_version",{{"type","integer"},{"enum",{2}}}},
        {"statements",{{"type","array"},{"items",object_schema(properties)}}}}).dump();
}
std::string structured_output_schema_sha256(OutputContractKind contract) {
    return crypto::sha256_hex(structured_output_schema(contract));
}
std::string structured_output_validation_error(std::string_view raw,OutputContractKind contract) {
    try {
        const auto parsed=claim_strict_json(raw);
        validate_schema(parsed,Json::parse(structured_output_schema(contract)));
        if(contract==OutputContractKind::ClaimAdmissionV1) {
            ParseResult candidates;
            candidates.statements.resize(parsed.at("decisions").size());
            auto result=apply_claim_admission(raw,candidates,false);
            if(!result.errors.empty()) { return result.errors.front().kind+":"+result.errors.front().detail;
}
        }
        return {};
    } catch(const std::exception& e) {return e.what();}
}
std::string llm_response_evidence_json(const LLMResponse& response) {
    Json attempts=Json::array();
    for(const auto& attempt:response.http_attempts) {
        const std::string certainty=attempt.execution_certainty==net::ExecutionCertainty::NotConnected ? "not_connected" :
            attempt.execution_certainty==net::ExecutionCertainty::ResponseReceived ? "response_received" : "unknown";
        attempts.push_back({{"attempt",attempt.attempt},{"http_status",attempt.http_status},{"curl_code",attempt.curl_code},
            {"response_body",attempt.response_body},{"response_bytes",attempt.response_bytes},{"streamed_bytes",attempt.streamed_bytes},
            {"elapsed_ms",attempt.elapsed_ms},{"retry_policy",attempt.retry_policy==net::RetryPolicy::ConnectOnly ? "connect_only" : "legacy_compatible"},
            {"execution_certainty",certainty}});
    }
    return Json{{"output_mode",to_string(response.output_mode)},{"output_contract",to_string(response.output_contract)},
        {"schema_sha256",response.schema_sha256},{"capability_evidence_id",response.capability_evidence_id},
        {"finish_reason",response.finish_reason},{"refusal",response.refusal},{"raw_completion",response.raw_completion},
        {"raw_http_response",response.raw_http_response},{"http_attempts",attempts},{"attempt_count",attempts.size()},
        {"raw_response",response.raw_xml},{"ok",response.ok},{"error",response.error},
        {"prompt_tokens",response.prompt_tokens},{"completion_tokens",response.completion_tokens},
        {"total_tokens",response.total_tokens},{"latency_ms",response.latency_ms}}.dump();
}
CapabilityState structured_probe_state(const LLMResponse& response,const StructuredOutputRequest& request,
        std::string& validation_error) {
    validation_error=response.error;
    if(!response.ok) {
        if(!response.http_attempts.empty() && (response.http_attempts.back().http_status==400 || response.http_attempts.back().http_status==422)) {
            try {
                auto message=Json::parse(response.raw_http_response).at("error").value("message","");
                std::transform(message.begin(),message.end(),message.begin(),[](unsigned char c){return static_cast<char>(std::tolower(c));});
                const bool named_format=message.find("response_format")!=std::string::npos || message.find("json_schema")!=std::string::npos || message.find("json_object")!=std::string::npos;
                const bool rejects_support=message.find("not supported")!=std::string::npos || message.find("unsupported")!=std::string::npos || message.find("does not support")!=std::string::npos;
                if(named_format && rejects_support) { return CapabilityState::Unsupported;
}
            } catch(const std::exception&) {}
        }
        if(response.error=="completion_truncated" || response.error=="completion_refusal" || response.error=="malformed_response") {
            return CapabilityState::Nonconformant;
}
        return CapabilityState::Unknown;
    }
    validation_error=structured_output_validation_error(response.raw_completion,request.contract);
    if(validation_error.empty() && request.contract==OutputContractKind::ClaimExtractionV2) {
        const auto parsed=parse_claim_response(response.raw_completion,"Nora: I feel cheerful about the community picnic.","Nora",false);
        if(!parsed.errors.empty()) { validation_error=parsed.errors.front().kind+":"+parsed.errors.front().detail;
}
    }
    if(validation_error.empty() && request.contract==OutputContractKind::ClaimAdmissionV1 && !claim_strict_json(response.raw_completion).at("decisions").empty()) {
        validation_error="schema_failure:probe requires an empty candidate decision list";
}
    if(validation_error.empty() && request.contract==OutputContractKind::SourceSelectionV1 && !claim_strict_json(response.raw_completion).at("source_ids").empty()) {
        validation_error="schema_failure:probe requires an empty source selection";
}
    return validation_error.empty() ? CapabilityState::ObservedConformant : CapabilityState::Nonconformant;
}

std::string capability_evidence_json(const CapabilityEvidence& evidence) {
    Json probes=Json::array();
    for(const auto& probe:evidence.probes) probes.push_back({{"prompt",probe.prompt},
        {"response",Json::parse(probe.response_json)},{"conformant",probe.conformant},{"validation_error",probe.validation_error}});
    return Json{{"schema_version",1},{"state",to_string(evidence.state)},{"output_mode",to_string(evidence.request.mode)},
        {"output_contract",to_string(evidence.request.contract)},{"probe_version",evidence.probe_version},
        {"schema_sha256",evidence.schema_sha256},{"endpoint",evidence.endpoint},{"model",evidence.model},
        {"observed_at",evidence.observed_at},{"evidence_id",evidence.evidence_id},{"error",evidence.error},
        {"request_count",evidence.request_count},{"probes",probes}}.dump();
}
std::string validate_capability_evidence_json(std::string_view raw) {
    try {
        auto evidence=claim_strict_json(raw);
        if(evidence.at("schema_version")!=1 || evidence.at("probe_version")!="structured-capability-v1") { return "capability_version_mismatch";
}
        StructuredOutputRequest request;
        const auto mode=evidence.at("output_mode").get<std::string>();
        const auto contract=evidence.at("output_contract").get<std::string>();
        if(mode=="json_object") { request.mode=OutputMode::JsonObject;
        } else if(mode=="json_schema_strict") { request.mode=OutputMode::JsonSchemaStrict;
        } else { return "capability_mode_invalid";
}
        if(contract=="claim_extraction_v2") { request.contract=OutputContractKind::ClaimExtractionV2;
        } else if(contract=="claim_admission_v1") { request.contract=OutputContractKind::ClaimAdmissionV1;
        } else if(contract=="source_selection_v1") { request.contract=OutputContractKind::SourceSelectionV1;
        } else { return "capability_contract_invalid";
}
        const auto schema_hash=structured_output_schema_sha256(request.contract);
        if(evidence.at("schema_sha256")!=schema_hash) { return "capability_schema_mismatch";
}
        const auto evidence_id=evidence.at("evidence_id").get<std::string>();
        evidence["evidence_id"]="";
        if(crypto::sha256_hex(evidence.dump())!=evidence_id) { return "capability_evidence_hash_mismatch";
}
        const auto& probes=evidence.at("probes");
        if(!probes.is_array() || probes.size()!=2U) { return "capability_probe_count_mismatch";
}
        std::size_t calls=0;
        bool unknown=false,unsupported=false,nonconformant=false;
        for(const auto& probe:probes) {
            const auto& stored=probe.at("response");
            if(stored.at("output_mode")!=mode || stored.at("output_contract")!=contract || stored.at("schema_sha256")!=schema_hash)
                return "capability_response_contract_mismatch";
            const auto& attempts=stored.at("http_attempts");
            if(!attempts.is_array() || attempts.size()>1u || stored.at("attempt_count")!=attempts.size()) return "capability_attempt_count_mismatch";
            LLMResponse response;
            response.output_mode=request.mode;response.output_contract=request.contract;
            response.ok=stored.at("ok").get<bool>();response.error=stored.at("error").get<std::string>();
            response.raw_completion=stored.at("raw_completion").get<std::string>();
            response.raw_xml=stored.at("raw_response").get<std::string>();
            response.raw_http_response=stored.at("raw_http_response").get<std::string>();
            response.finish_reason=stored.at("finish_reason").get<std::string>();response.refusal=stored.at("refusal").get<bool>();
            if(response.ok && response.raw_xml!=response.raw_completion) return "capability_raw_completion_mismatch";
            for(const auto& attempt:attempts) {
                if(attempt.at("attempt")!=1 || attempt.at("retry_policy")!="connect_only" || attempt.at("response_bytes")!=attempt.at("response_body").get<std::string>().size()) return "capability_attempt_evidence_mismatch";
                if(response.raw_http_response!=attempt.at("response_body").get<std::string>()) return "capability_raw_http_mismatch";
                net::HttpAttemptEvidence item;
                item.http_status=attempt.at("http_status").get<long>();
                item.curl_code=attempt.at("curl_code").get<int>();
                if(response.ok && (item.http_status>=400 || item.curl_code!=0)) return "capability_transport_status_mismatch";
                response.http_attempts.push_back(item);
            }
            if(response.ok) {
                const auto envelope=claim_strict_json(response.raw_http_response);
                if(envelope.at("choices").at(0).at("message").at("content")!=response.raw_completion) return "capability_http_completion_mismatch";
            }
            calls+=attempts.size();
            std::string validation_error;
            const auto state=structured_probe_state(response,request,validation_error);
            if(probe.at("conformant")!=(state==CapabilityState::ObservedConformant) || probe.at("validation_error")!=validation_error)
                return "capability_probe_classification_mismatch";
            unknown|=state==CapabilityState::Unknown;unsupported|=state==CapabilityState::Unsupported;nonconformant|=state==CapabilityState::Nonconformant;
        }
        if(evidence.at("request_count")!=calls) { return "capability_request_count_mismatch";
}
        const auto state=unknown ? CapabilityState::Unknown : unsupported ? CapabilityState::Unsupported : nonconformant ? CapabilityState::Nonconformant : CapabilityState::ObservedConformant;
        if(evidence.at("state")!=to_string(state)) { return "capability_state_mismatch";
}
        return {};
    } catch(const std::exception& error) {return std::string("invalid_capability_evidence:")+error.what();}
}
} // namespace starling::extractor

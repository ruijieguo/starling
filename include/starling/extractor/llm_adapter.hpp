#pragma once

#include "starling/extractor/structured_output.hpp"
#include "starling/net/http_post_json.hpp"

#include <functional>
#include <string>
#include <string_view>

namespace starling::extractor {

// Streaming sink: invoked once per generated token delta (incremental reply
// text) during generate_stream. "Done" is signalled by generate_stream
// returning — no separate terminal callback. Empty sink = caller wants no
// streaming (non-streaming generate path). The C++ core owns when/what emits;
// a binding may wrap a host callback (e.g. pybind re-acquires the GIL per
// delta). Deltas are reply text only — usage/latency arrive on the returned
// LLMResponse, exactly as the non-streaming path.
using TokenSink = std::function<void(std::string_view /*delta*/)>;

struct LLMResponse {
    std::string raw_xml;   // raw LLM body (now a JSON array; name kept for blast-radius); empty when ok=false
    bool        ok = false;
    std::string error;     // semantic error code on ok=false; empty otherwise
    // 2b 成本采集:真适配器填充网络往返耗时 + token 用量(失败响应也带 latency)。
    // Fake / 未返回 usage 的端点留 0;采集落在适配器(核心)而非绑定层。
    int prompt_tokens     = 0;
    int completion_tokens = 0;
    int total_tokens      = 0;
    int latency_ms        = 0;
    OutputMode output_mode = OutputMode::Legacy;
    OutputContractKind output_contract = OutputContractKind::Legacy;
    std::string schema_sha256 = {};
    std::string capability_evidence_id = {};
    std::string finish_reason = {};
    bool refusal = false;
    std::string raw_completion = {};
    std::string raw_http_response = {};
    std::vector<net::HttpAttemptEvidence> http_attempts = {};
};

// Pluggable seam: anything that can turn a prompt + a stable input hash into
// a raw LLM response (a JSON array, or a typed transient error). M0.4 ships FakeLLMAdapter
// only; P2 lands real OpenAI / Anthropic / local-compatible adapters. The
// prompt_input_hash is opaque to the adapter — extractor.cpp computes it as
// sha256(prompt_template_version + prompt_body + existing_ref_map_json) so
// the adapter can use it as a deterministic cache key without parsing the
// prompt.
class LLMAdapter {
public:
    virtual ~LLMAdapter() = default;
    virtual LLMResponse extract(
        std::string_view prompt,
        std::string_view prompt_input_hash) = 0;

    virtual LLMResponse extract_with_contract(std::string_view prompt,
            std::string_view hash, const StructuredOutputRequest& request) {
        if (request.mode == OutputMode::Legacy) return extract(prompt, hash);
        LLMResponse out;
        out.error = "structured_output_unsupported";
        out.output_mode = request.mode;
        out.output_contract = request.contract;
        return out;
    }

    // generate — free-form completion (a chat reply), for converse(). The base
    // default routes through extract(): for real chat adapters the HTTP path is
    // identical (POST the prompt, return choices[0].message.content); only what
    // the CALLER does with the text differs (converse uses it as the reply;
    // extract parses it as a statements JSON array). raw_xml carries the
    // generated text. Adapters may override for chat-specific params
    // (temperature / token usage) in a later phase.
    virtual LLMResponse generate(std::string_view prompt) {
        return extract(prompt, std::string_view{});
    }

    // generate_stream — like generate(), but emits the reply incrementally via
    // on_token as it is produced, returning the SAME complete LLMResponse
    // (full reply in raw_xml + usage/latency) the non-streaming path returns,
    // so callers do remember/cost accounting identically. The base default is
    // non-streaming: it calls generate() and emits the whole reply as ONE
    // delta. Streaming-capable adapters (real SSE) override to emit token-by-
    // token. An empty on_token means "no streaming" — the whole call collapses
    // to generate(). This keeps every existing adapter (Fake + real) working
    // unchanged and lets converse() always call generate_stream().
    virtual LLMResponse generate_stream(std::string_view prompt,
                                        const TokenSink& on_token) {
        LLMResponse resp = generate(prompt);
        if (resp.ok && on_token && !resp.raw_xml.empty()) {
            on_token(resp.raw_xml);
        }
        return resp;
    }
};

}  // namespace starling::extractor

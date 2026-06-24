#pragma once

#include <string>
#include <string_view>

namespace starling::extractor {

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
};

}  // namespace starling::extractor

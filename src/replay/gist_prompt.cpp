#include "starling/replay/gist_prompt.hpp"

#include <nlohmann/json.hpp>

#include <cstddef>
#include <string>
#include <string_view>
#include <vector>

namespace starling::replay {
namespace {

// CORE single-source NORM-gist prompt. Asks the consolidation LLM to judge
// whether a multi-holder (predicate, object) agreement is a genuine
// generalizable norm and to render it in one sentence. Reply must be a bare
// JSON object {confidence, summary}; parse_gist_judgment tolerates fences/prose
// around it. Placeholders are filled by build_norm_gist_prompt.
constexpr std::string_view kNormGistPromptTemplate =
    R"PROMPT(You are the consolidation faculty of a brain-like memory system. Several DISTINCT holders have INDEPENDENTLY asserted the same belief. Judge whether this is a genuine, generalizable NORM — something people in general believe or do — rather than a coincidental overlap.

Candidate norm:
  predicate: {predicate}
  object: {object}
  asserted by {holder_count} distinct holders: {holders}

Reply with ONLY a JSON object (no prose, no markdown):
{"confidence": <number 0.0-1.0 — how strongly this is a real generalizable norm>, "summary": "<one concise sentence stating the norm in natural language>"}
)PROMPT";

void replace_first(std::string& haystack, std::string_view needle, std::string_view value) {
    const auto pos = haystack.find(needle);
    if (pos != std::string::npos) {
        haystack.replace(pos, needle.size(), value);
    }
}

std::string join_with_commas(const std::vector<std::string>& items) {
    std::string out;
    for (std::size_t idx = 0; idx < items.size(); ++idx) {
        if (idx != 0) {
            out += ", ";
        }
        out += items[idx];
    }
    return out;
}

}  // namespace

std::string build_norm_gist_prompt(const GistCluster& cluster) {
    std::string prompt(kNormGistPromptTemplate);
    replace_first(prompt, "{predicate}", cluster.predicate);
    replace_first(prompt, "{object}", cluster.object_value);
    replace_first(prompt, "{holder_count}", std::to_string(cluster.holder_ids.size()));
    replace_first(prompt, "{holders}", join_with_commas(cluster.holder_ids));
    return prompt;
}

GistJudgment parse_gist_judgment(std::string_view llm_reply) {
    GistJudgment judgment;
    // Isolate the JSON object — tolerate ```json fences / surrounding prose.
    const std::string text(llm_reply);
    const auto open = text.find('{');
    const auto close = text.rfind('}');
    if (open == std::string::npos || close == std::string::npos || close < open) {
        return judgment;  // ok=false
    }
    try {
        const auto obj = nlohmann::json::parse(text.substr(open, close - open + 1));
        if (!obj.contains("confidence") || !obj.at("confidence").is_number()) {
            return judgment;  // ok=false — confidence is mandatory
        }
        judgment.confidence = obj.at("confidence").get<double>();
        if (judgment.confidence < 0.0 || judgment.confidence > 1.0) {
            return GistJudgment{};  // out of [0,1] → treat as unparseable (skip; avoids a
                                    // misbehaving adapter being retried every cycle forever)
        }
        if (obj.contains("summary") && obj.at("summary").is_string()) {
            judgment.summary = obj.at("summary").get<std::string>();
        }
        judgment.ok = true;
    } catch (const nlohmann::json::exception&) {
        return GistJudgment{};  // ok=false on any parse error
    }
    return judgment;
}

}  // namespace starling::replay

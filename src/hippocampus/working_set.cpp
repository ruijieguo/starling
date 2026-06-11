#include "starling/hippocampus/working_set.hpp"

#include <algorithm>
#include <array>
#include <cstdio>

#include "starling/affect/affect_vector.hpp"
#include "starling/neocortex/common_ground_container.hpp"
#include "starling/neocortex/persona_container.hpp"
#include "starling/prospective/commitment_engine.hpp"

namespace starling::hippocampus {

namespace {

// UTF-8 码点工具:估算与截断都按码点(与原 Python 实现的 len()/切片语义
// 对齐),截断绝不切断多字节序列。
bool is_continuation(unsigned char b) { return (b & 0xC0) == 0x80; }

std::size_t codepoint_count(std::string_view s) {
    std::size_t n = 0;
    for (const char ch : s) {
        if (!is_continuation(static_cast<unsigned char>(ch))) ++n;
    }
    return n;
}

std::string take_codepoints(std::string_view s, std::size_t n_codepoints) {
    std::size_t taken = 0;
    std::size_t i = 0;
    while (i < s.size()) {
        if (!is_continuation(static_cast<unsigned char>(s[i]))) {
            if (taken == n_codepoints) break;
            ++taken;
        }
        ++i;
    }
    return std::string(s.substr(0, i));
}

// 行动关键优先;记忆吃剩余预算的大头。
constexpr std::array<std::string_view, 5> kPriority = {
    "pending_commitments", "persona", "common_ground", "relevant_memories", "affect",
};

}  // namespace

int estimate_tokens(std::string_view text) {
    return std::max<int>(1, static_cast<int>(codepoint_count(text) / 4));
}

std::string ContextBlock::render() const {
    static const std::map<std::string, std::string> kTitles = {
        {"persona", "## About me"},
        {"common_ground", "## What we share"},
        {"relevant_memories", "## Relevant memories"},
        {"pending_commitments", "## Pending commitments"},
        {"affect", "## Current tone"},
    };
    std::string out;
    for (const auto& b : blocks) {
        if (b.content.find_first_not_of(" \t\r\n") == std::string::npos) continue;
        if (!out.empty()) out += "\n\n";
        const auto it = kTitles.find(b.label);
        out += (it != kTitles.end() ? it->second : "## " + b.label);
        out += "\n";
        out += b.content;
    }
    return out;
}

ContextBlock assemble(const std::map<std::string, std::string>& sections,
                      int token_budget) {
    ContextBlock cb;
    int remaining = token_budget;
    for (const auto label : kPriority) {
        const auto it = sections.find(std::string(label));
        if (it == sections.end() || it->second.empty()) continue;
        const std::string& content = it->second;
        const int est = estimate_tokens(content);
        if (est <= remaining) {
            cb.blocks.push_back({std::string(label), content, est});
            remaining -= est;
        } else {
            const std::size_t keep = static_cast<std::size_t>(std::max(0, remaining)) * 4;
            std::string cut = take_codepoints(content, keep);
            const int cut_est = estimate_tokens(cut);
            cb.blocks.push_back({std::string(label), std::move(cut), cut_est});
            cb.truncated.push_back(std::string(label));
            remaining = 0;
        }
    }
    return cb;
}

ContextBlock build_working_set(persistence::SqliteAdapter& adapter,
                               retrieval::SemanticRetriever& retriever,
                               const WorkingSetParams& p) {
    std::map<std::string, std::string> sections;

    // persona ← Neocortex 物化容器(self 锚点仲裁结果)。
    {
        const auto pv = neocortex::PersonaContainer(adapter).read(
            adapter.connection(), p.tenant_id, p.agent_id);
        if (pv.found && !pv.dimensions.empty()) {
            std::string s;
            for (const auto& [k, v] : pv.dimensions) {
                if (!s.empty()) s += "; ";
                s += k + ": " + v;
            }
            sections["persona"] = std::move(s);
        }
    }

    // common_ground ← 双方 sorted-pair key 的已 grounded 共识。
    {
        std::string a = p.agent_id, b = p.interlocutor;
        if (b < a) std::swap(a, b);
        const auto cg = neocortex::CommonGroundContainer(adapter).read(
            adapter.connection(), p.tenant_id, a + "::" + b);
        if (cg.found && !cg.grounded.empty()) {
            std::string s;
            for (const auto& g : cg.grounded) {
                if (!s.empty()) s += "\n";
                s += "- " + g;
            }
            sections["common_ground"] = std::move(s);
        }
    }

    // relevant_memories(+affect 峰值)← 语义召回,goal 为空则两区缺省。
    std::vector<retrieval::SemanticScored> hits;
    if (!p.goal.empty()) {
        retrieval::SemanticRetrieverParams rp;
        rp.tenant_id          = p.tenant_id;
        rp.holder_id          = p.agent_id;
        rp.holder_perspective = "first_person";
        rp.query_text         = p.goal;
        rp.k                  = p.recall_k;
        hits = retriever.vector_recall(adapter.connection(), rp).rows;
        if (!hits.empty()) {
            std::string s;
            for (const auto& h : hits) {
                if (!s.empty()) s += "\n";
                s += "- " + h.row.subject_id + " " + h.row.predicate + " " + h.row.object_value;
            }
            sections["relevant_memories"] = std::move(s);
        }
    }

    // pending_commitments ← 前瞻环;fired → ⚠ DUE(B3 提醒闭环)。
    {
        const auto pend = prospective::CommitmentEngine(adapter).pending(
            adapter.connection(), p.tenant_id, p.agent_id, p.interlocutor);
        if (!pend.empty()) {
            std::string s;
            for (const auto& c : pend) {
                if (!s.empty()) s += "\n";
                s += "- ";
                if (c.fired) s += "⚠ DUE: ";
                s += c.subject_id + " " + c.predicate + " " + c.object_value;
                if (!c.deadline.empty()) s += " (by " + c.deadline + ")";
            }
            sections["pending_commitments"] = std::move(s);
        }
    }

    // affect ← 召回行 affect_json 的 salience 峰值。
    {
        double peak = 0.0;
        bool have = false;
        for (const auto& h : hits) {
            const std::string& aj = h.row.affect_json;
            if (aj.empty() || aj == "{}") continue;
            const double s = affect::salience(affect::parse_affect_json(aj), 1.0);
            if (s > peak) {
                peak = s;
                have = true;
            }
        }
        if (have) {
            char buf[32];
            std::snprintf(buf, sizeof(buf), "salience %.2f", peak);
            sections["affect"] = buf;
        }
    }

    return assemble(sections, p.token_budget);
}

}  // namespace starling::hippocampus

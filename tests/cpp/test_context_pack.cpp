// Context Pack 8 标签判定(13_retrieval.md §核心算法-3)。
// 优先级(首中即停):TODO > CONFLICT > COMMON > INFERRED > HEARSAY > BELIEF > FACT。
// ABSTAIN 不走 classify——由 abstention gate 注入整包。
#include "starling/retrieval/context_pack.hpp"

#include <gtest/gtest.h>

namespace starling::retrieval {

namespace {
StatementRow row(const char* id, const char* holder, const char* modality,
                 double conf, const char* evidence_count = "two") {
    StatementRow r;
    r.id = id; r.holder_id = holder; r.subject_id = "Bob";
    r.predicate = "responsible_for"; r.object_value = "auth";
    r.modality = modality; r.confidence = conf;
    r.consolidation_state = "consolidated";
    // 单证据 → evidence_json 一个元素;双证据 → 两个。
    r.evidence_json = (std::string(evidence_count) == "one")
        ? R"([{"engram_id":"e1"}])"
        : R"([{"engram_id":"e1"},{"engram_id":"e2"}])";
    return r;
}
}  // namespace

TEST(ContextPack, ClassifyPrecedence) {
    PackContext ctx;
    ctx.querier = "cog-self";
    ctx.todo_ids.insert("t1");
    ctx.conflict_ids.insert("c1");
    ctx.common_ids.insert("g1");

    EXPECT_EQ(classify(row("t1", "cog-self", "COMMITS", 0.9), ctx), ContextPackLabel::TODO);
    EXPECT_EQ(classify(row("c1", "cog-self", "KNOWS", 0.9), ctx), ContextPackLabel::CONFLICT);
    EXPECT_EQ(classify(row("g1", "cog-self", "KNOWS", 0.9), ctx), ContextPackLabel::COMMON);
    // provenance≠user_input → INFERRED。
    EXPECT_EQ(classify_with_provenance(row("i1", "cog-self", "BELIEVES", 0.7), ctx,
                                       "tom_inferred"),
              ContextPackLabel::INFERRED);
    // 他者单证据 → HEARSAY。
    EXPECT_EQ(classify(row("h1", "Alice", "BELIEVES", 0.6, "one"), ctx),
              ContextPackLabel::HEARSAY);
    // 他者多证据 → BELIEF;自我低置信 BELIEVES → BELIEF。
    EXPECT_EQ(classify(row("b1", "Alice", "KNOWS", 0.9), ctx), ContextPackLabel::BELIEF);
    EXPECT_EQ(classify(row("b2", "cog-self", "BELIEVES", 0.5), ctx), ContextPackLabel::BELIEF);
    // 默认:自我高置信 → FACT。
    EXPECT_EQ(classify(row("f1", "cog-self", "KNOWS", 0.95), ctx), ContextPackLabel::FACT);
}

TEST(ContextPack, RenderShape) {
    PackContext ctx; ctx.querier = "cog-self";
    auto r = row("f1", "cog-self", "KNOWS", 0.95);
    std::vector<PackEntry> entries{
        {ContextPackLabel::FACT, r.id, render_line(r, ContextPackLabel::FACT)}};
    const std::string pack = render_pack(entries, "");
    EXPECT_NE(pack.find("[FACT]"), std::string::npos);
    EXPECT_NE(pack.find("Bob responsible_for auth"), std::string::npos);
    // 拒答包:单 ABSTAIN 行带 reason。
    const std::string ab = render_pack({}, "low_score");
    EXPECT_NE(ab.find("[ABSTAIN]"), std::string::npos);
    EXPECT_NE(ab.find("low_score"), std::string::npos);
}

}  // namespace starling::retrieval

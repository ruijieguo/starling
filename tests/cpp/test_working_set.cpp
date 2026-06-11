// test_working_set.cpp — P2.e Working Set(2026-06-11 自 Python 迁入 C++)。
// 端到端(五源汇集经 Memory 门面)由 tests/python/test_working_set.py 覆盖;
// 这里钉核心语义:优先级预算分配、截断记账、渲染标题、UTF-8 码点安全。

#include "starling/hippocampus/working_set.hpp"

#include <gtest/gtest.h>

#include <map>
#include <string>

namespace starling::hippocampus {

TEST(WorkingSet, AssemblePriorityOrderAndBudget) {
    std::map<std::string, std::string> sections = {
        {"relevant_memories", std::string(200, 'm')},   // 50 tok
        {"persona", std::string(40, 'p')},              // 10 tok
        {"pending_commitments", std::string(40, 'c')},  // 10 tok
        {"affect", "salience 0.50"},
    };
    const auto cb = assemble(sections, 1000);
    ASSERT_EQ(cb.blocks.size(), 4u);
    // 行动关键优先:承诺 > 人设 > 记忆 > 情感(common_ground 缺省跳过)。
    EXPECT_EQ(cb.blocks[0].label, "pending_commitments");
    EXPECT_EQ(cb.blocks[1].label, "persona");
    EXPECT_EQ(cb.blocks[2].label, "relevant_memories");
    EXPECT_EQ(cb.blocks[3].label, "affect");
    EXPECT_TRUE(cb.truncated.empty());
    EXPECT_EQ(cb.blocks[0].token_estimate, 10);
}

TEST(WorkingSet, OverflowTruncatesByRemainingBudget) {
    // persona 10 tok 吃掉预算后,memories 只剩 0 → 截到 0 字符并记账;
    // 预算 12:persona(10)后剩 2 → memories 截到 8 字符。
    std::map<std::string, std::string> sections = {
        {"persona", std::string(40, 'p')},
        {"relevant_memories", std::string(200, 'm')},
    };
    const auto cb = assemble(sections, 12);
    ASSERT_EQ(cb.blocks.size(), 2u);
    EXPECT_EQ(cb.blocks[1].label, "relevant_memories");
    EXPECT_EQ(cb.blocks[1].content.size(), 8u);
    ASSERT_EQ(cb.truncated.size(), 1u);
    EXPECT_EQ(cb.truncated[0], "relevant_memories");
}

TEST(WorkingSet, RenderTitlesAndSkipsBlankBlocks) {
    std::map<std::string, std::string> sections = {
        {"pending_commitments", "- ⚠ DUE: bob owes design doc (by 2026-06-01T12:00:00Z)"},
        {"persona", "role: engineer"},
    };
    const auto out = assemble(sections, 100).render();
    EXPECT_NE(out.find("## Pending commitments"), std::string::npos);
    EXPECT_NE(out.find("## About me"), std::string::npos);
    EXPECT_NE(out.find("⚠ DUE"), std::string::npos);
    EXPECT_EQ(out.find("## Relevant memories"), std::string::npos);
}

TEST(WorkingSet, Utf8TruncationIsCodepointSafe) {
    // 估算与截断都按 Unicode 码点(对齐原 Python len()/切片语义):
    // 40 个中文字 = 10 tok;预算 3 → 截 12 个码点 = 36 字节,绝不切断序列。
    std::string cjk;
    for (int i = 0; i < 40; ++i) cjk += "记";
    EXPECT_EQ(estimate_tokens(cjk), 10);
    std::map<std::string, std::string> sections = {{"persona", cjk}};
    const auto cb = assemble(sections, 3);
    ASSERT_EQ(cb.blocks.size(), 1u);
    EXPECT_EQ(cb.blocks[0].content.size(), 36u);  // 12 码点 × 3 字节
    // 截断结果是合法 UTF-8:最后一字节不是孤立的续字节序列开头。
    EXPECT_EQ(cb.blocks[0].content, std::string(cjk.substr(0, 36)));
    ASSERT_EQ(cb.truncated.size(), 1u);
}

}  // namespace starling::hippocampus

# P3.a1 Retrieval Planner(检索规划核心)Implementation Plan

> 状态:**已完成**(2026-06-12,inline 执行)。ctest 551(+15)/ pytest 591(+4)/
> svelte-check 0-0 / vitest / build ✔。Task 6 与 Task 7 合并落地(helper 结构
> 使九意图一次成型);其余按计划逐 task 提交。
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 P1 的单意图 basic_retrieve 升级为 spec 13_retrieval.md 的完整检索规划器——9 种 QueryIntent、7 步管线(parse→mask→plan→fetch→fuse→ground→abstain)、Affect-aware Reranker、Abstention Gate 四条件、Context Pack 8 标签、RetrievalReceipt 完整字段——并暴露到 Python facade 与 dashboard。

**Architecture:** 全部核心语义落 C++ `src/retrieval/`(仓库 CLAUDE.md 边界规则):新建 `query_intent` / `affect_reranker` / `retrieval_scope` / `context_pack` / `abstention` / `retrieval_planner` 六个模块;`BasicRetriever` 与既有钉测**零改动**(planner 自带各 intent 的 SQL 路径,中心化 emit)。Python 仅绑定转发(`Memory.query()` / dashboard `/api/recall` 加 `intent`)。perspective filter 在**排序之前**生效(结构化路径 SQL 谓词下推;语义路径在 rerank 前按 KnowledgeFrontier 可见集遮蔽并计数)。

**Tech Stack:** C++20 + SQLite(无新 migration,只读现表)+ pybind11(bind_05 扩展,planner 绑定带 `gil_scoped_release`——fetch 含 embedder 网络调用)+ SvelteKit(interact 页 intent 选择器)。

**工程约定(每个 task 生效):**
- 工作目录:仓库根 `/Users/jaredguo-mini/develop/memory/starling`(**不是** worktree;每条 Bash 显式 cd)。
- 构建:`PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build`;改绑定/C++ 后跑 Python 测试前先 `--python-editable`。
- C++ 测试:`./build/tests/cpp/starling_tests --gtest_filter='<Suite>.*'`;全量 `ctest --test-dir build`(基线 536)。
- Python:`.venv/bin/python -m pytest tests/python -q`(基线 587 passed/13 skipped)。
- git:explicit-path add(禁 `.`/`-A`);commit 尾行 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`;禁 --no-verify/--amend;中文 body。
- 不可破坏钉测:`tests/cpp/test_basic_retriever_*`、`test_semantic_retriever`、`test_pattern_completor`、`tests/python/test_basic_retrieve_*`、`test_recalled_window_bucket`、`test_semantic_retrieve_e2e`。Receipt 既有 9 字段语义不变(只增不改);`basic_retrieve` 对非 FACT_LOOKUP 仍 throw;`statement.recalled` 既有幂等键公式不动。

**Spec 裁剪登记(写进 Task 10 文档补记,不是悄悄砍):**
- `sanitized_query` 字段:P3.b 安全产品化时随 query 清洗管线一起做,本期 receipt 不含。
- 三级 RRF/bm25 融合(spec "P3 可升级"):本期 reranker 落五因子公式;RRF 归 P3.c 检索 fan-out。
- `temporal_distance_penalty` v1 简化:有界惩罚(过期窗口 0.3,在窗 0),非连续距离函数。
- `ScopedWorkGate(lane=retrieval)` 并发闸门:P3.c 治理项;本期 fetch 串行(progressive)。
- `access_count` in-memory 软统计 + Replay flush:本期不改(现状已由 Replay 周期路径覆盖 activation/last_accessed)。

---

## File Structure(先定边界)

```
include/starling/retrieval/
  query_intent.hpp          # 9 种枚举 + to_string(自 basic_retriever.hpp 迁出,类型同一)
  affect_reranker.hpp       # 四因子函数 + RerankCandidate + rerank()
  retrieval_scope.hpp       # RetrievalScopeStep / RetrievalScopePlan
  context_pack.hpp          # ContextPackLabel + classify + render
  abstention.hpp            # AbstentionConfig/Input + evaluate_abstention
  retrieval_planner.hpp     # PlannerQuery/PlannerResult + RetrievalPlanner(7 步)
  retrieval_receipt.hpp     # [修改] 追加 P3 字段(ScoreRow 在此定义)
  basic_retriever.hpp       # [修改] 枚举迁出,改 include(其余零改)
src/retrieval/
  affect_reranker.cpp
  context_pack.cpp
  abstention.cpp
  retrieval_planner.cpp     # 7 步编排 + 9 intent fetch 路径 + 中心化 emit
bindings/python/bind_05_retrieval.cpp   # [修改] 枚举扩值 + 新 DTO/Planner 绑定
python/starling/memory.py               # [修改] Memory.query()
python/starling/_memory_core.py         # [修改] MemoryCore.plan_query 一行转发
python/starling/dashboard/routes/commands.py  # [修改] RecallBody.intent/target
dashboard/web/src/routes/interact/+page.svelte # [修改] intent 选择器+标签+拒答
tests/cpp/
  test_affect_reranker.cpp
  test_context_pack.cpp
  test_abstention_gate.cpp
  test_retrieval_planner.cpp
tests/python/
  test_retrieval_planner_e2e.py
CMakeLists.txt              # [修改] src 清单 +4
tests/cpp/CMakeLists.txt    # [修改] 测试清单 +4
```

依赖序:Task 1(枚举)→ Task 2(reranker)→ Task 3(scope+receipt)→ Task 4(abstention)→ Task 5(context pack)→ Task 6(planner 核心三路)→ Task 7(其余六路+多 holder)→ Task 8(绑定+facade)→ Task 9(dashboard+前端)→ Task 10(e2e+文档+全量门)。

---

### Task 1: QueryIntent 九种枚举(迁出独立头,类型同一)

**Files:**
- Create: `include/starling/retrieval/query_intent.hpp`
- Modify: `include/starling/retrieval/basic_retriever.hpp:11-19`(枚举定义替换为 include)
- Modify: `bindings/python/bind_05_retrieval.cpp:18-20`(扩 8 值)
- Test: 复用既有钉测(枚举值兼容)+ Python 绑定断言(Task 8 e2e 里钉)

- [ ] **Step 1: 新建 query_intent.hpp**

```cpp
#pragma once
// 9 种检索意图(13_retrieval.md §"QueryIntent 枚举")。P1 只交付 FACT_LOOKUP;
// P3.a1 全量。自 basic_retriever.hpp 迁出成独立头——枚举类型保持同一
// (starling::retrieval::QueryIntent),BasicRetriever 对非 FACT_LOOKUP 的
// runtime reject 行为不变(钉测 test_basic_retriever_*)。

namespace starling::retrieval {

enum class QueryIntent {
    FACT_LOOKUP,
    BELIEF_OF_OTHER,
    META_BELIEF,
    HISTORY,
    COMMITMENT_DUE,
    PREFERENCE,
    NORM_LOOKUP,
    COMMON_GROUND,
    ABSTAIN_CHECK,
};

inline const char* to_string(QueryIntent v) {
    switch (v) {
        case QueryIntent::FACT_LOOKUP:     return "FACT_LOOKUP";
        case QueryIntent::BELIEF_OF_OTHER: return "BELIEF_OF_OTHER";
        case QueryIntent::META_BELIEF:     return "META_BELIEF";
        case QueryIntent::HISTORY:         return "HISTORY";
        case QueryIntent::COMMITMENT_DUE:  return "COMMITMENT_DUE";
        case QueryIntent::PREFERENCE:      return "PREFERENCE";
        case QueryIntent::NORM_LOOKUP:     return "NORM_LOOKUP";
        case QueryIntent::COMMON_GROUND:   return "COMMON_GROUND";
        case QueryIntent::ABSTAIN_CHECK:   return "ABSTAIN_CHECK";
    }
    return "FACT_LOOKUP";
}

}  // namespace starling::retrieval
```

- [ ] **Step 2: basic_retriever.hpp 改 include(11-19 行的枚举与注释整段替换)**

替换前(basic_retriever.hpp:13-19):
```cpp
// P1 ships only FACT_LOOKUP. The remaining 8 intents (BELIEF_OF_OTHER,
// META_BELIEF, HISTORY, COMMITMENT_DUE, PREFERENCE, NORM_LOOKUP,
// COMMON_GROUND, ABSTAIN_CHECK) are spec'd at 13_retrieval.md
// §"QueryIntent 枚举（9 种）" but rejected at runtime in P1.
enum class QueryIntent {
    FACT_LOOKUP,
};
```
替换后(同位置):
```cpp
// QueryIntent 全 9 种见 query_intent.hpp(P3.a1 迁出)。BasicRetriever 仍只
// 接受 FACT_LOOKUP——结构化单意图入口的 runtime reject 行为是 P1 契约。
#include "starling/retrieval/query_intent.hpp"
```
(同时把文件顶部 `#include <chrono>` 之后的 include 块保持原状;新 include 放枚举原位置即可。)

- [ ] **Step 3: bind_05 扩枚举值(18-20 行)**

```cpp
    py::enum_<starling::retrieval::QueryIntent>(m, "QueryIntent")
        .value("FACT_LOOKUP",     starling::retrieval::QueryIntent::FACT_LOOKUP)
        .value("BELIEF_OF_OTHER", starling::retrieval::QueryIntent::BELIEF_OF_OTHER)
        .value("META_BELIEF",     starling::retrieval::QueryIntent::META_BELIEF)
        .value("HISTORY",         starling::retrieval::QueryIntent::HISTORY)
        .value("COMMITMENT_DUE",  starling::retrieval::QueryIntent::COMMITMENT_DUE)
        .value("PREFERENCE",      starling::retrieval::QueryIntent::PREFERENCE)
        .value("NORM_LOOKUP",     starling::retrieval::QueryIntent::NORM_LOOKUP)
        .value("COMMON_GROUND",   starling::retrieval::QueryIntent::COMMON_GROUND)
        .value("ABSTAIN_CHECK",   starling::retrieval::QueryIntent::ABSTAIN_CHECK)
        .export_values();
```

- [ ] **Step 4: 构建 + 跑既有检索钉测(必须全绿——枚举迁移零行为变化)**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling && PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build 2>&1 | tail -2
./build/tests/cpp/starling_tests --gtest_filter='*BasicRetriever*:*Retriev*' 2>&1 | tail -3
```
Expected: `PASSED`(数量与改前一致,0 fail)

- [ ] **Step 5: Commit**

```bash
cd /Users/jaredguo-mini/develop/memory/starling
git add include/starling/retrieval/query_intent.hpp include/starling/retrieval/basic_retriever.hpp bindings/python/bind_05_retrieval.cpp
git commit -F - <<'EOF'
feat(P3.a1): QueryIntent 扩为 9 种意图(独立头迁出,类型同一)

basic_retriever 对非 FACT_LOOKUP 的 runtime reject 契约不变;绑定层扩值。

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
```

---

### Task 2: Affect-aware Reranker(四因子 + 五因子乘法公式)

**Files:**
- Create: `include/starling/retrieval/affect_reranker.hpp`
- Create: `src/retrieval/affect_reranker.cpp`
- Modify: `CMakeLists.txt`(src 清单 `src/retrieval/pattern_completor.cpp` 行后加一行)
- Modify: `tests/cpp/CMakeLists.txt`(`test_memory_ops.cpp` 行后加 `test_affect_reranker.cpp`)
- Test: `tests/cpp/test_affect_reranker.cpp`

注:`ScoreRow`(score_breakdown 行格式)定义在 Task 3 的 receipt 扩展里——本 task 先在 reranker 头里定义,Task 3 让 receipt include 本头。**本 task 即定稿**,避免循环依赖:`affect_reranker.hpp` 只依赖 `statement_row.hpp` 与 `affect/affect_vector.hpp`。

- [ ] **Step 1: 写失败测试 tests/cpp/test_affect_reranker.cpp**

```cpp
// Affect-aware Reranker(13_retrieval.md §核心算法-2)。钉:四因子各自的
// 边界值、五因子乘法的次序反转、breakdown 与排序对齐。全确定性零 IO。
#include "starling/retrieval/affect_reranker.hpp"
#include <gtest/gtest.h>

namespace starling::retrieval {

namespace {
StatementRow row(const char* id, const char* observed_at,
                 const char* valid_to = "", const char* affect = "{}") {
    StatementRow r;
    r.id = id; r.observed_at = observed_at; r.valid_to = valid_to;
    r.affect_json = affect;
    return r;
}
}  // namespace

TEST(AffectReranker, FactorBounds) {
    // recency:同刻=1;30 天≈e^-1;负龄按 0 龄处理(=1)。
    EXPECT_DOUBLE_EQ(recency_factor("2026-06-12T00:00:00Z", "2026-06-12T00:00:00Z"), 1.0);
    EXPECT_NEAR(recency_factor("2026-05-13T00:00:00Z", "2026-06-12T00:00:00Z"),
                std::exp(-1.0), 1e-9);
    EXPECT_DOUBLE_EQ(recency_factor("2026-07-01T00:00:00Z", "2026-06-12T00:00:00Z"), 1.0);
    // activation clamp。
    EXPECT_DOUBLE_EQ(activation_level(-0.5), 0.0);
    EXPECT_DOUBLE_EQ(activation_level(0.4), 0.4);
    EXPECT_DOUBLE_EQ(activation_level(2.0), 1.0);
    // temporal penalty:窗内 0;valid_to 已过 0.3。
    EXPECT_DOUBLE_EQ(temporal_distance_penalty(row("a", "2026-06-01T00:00:00Z"),
                                               "2026-06-12T00:00:00Z"), 0.0);
    EXPECT_DOUBLE_EQ(temporal_distance_penalty(
        row("b", "2026-06-01T00:00:00Z", "2026-06-10T00:00:00Z"),
        "2026-06-12T00:00:00Z"), 0.3);
    // affect_consistency:双中性=1;最大差异→0.5 下界。
    affect::AffectVector neutral{};
    EXPECT_DOUBLE_EQ(affect_consistency("{}", neutral), 1.0);
    affect::AffectVector hot{}; hot.valence = 1.0f; hot.arousal = 1.0f;
    hot.dominance = 1.0f; hot.novelty = 1.0f; hot.stakes = 1.0f;
    EXPECT_NEAR(affect_consistency("{}", hot), 0.5, 1e-9);
}

TEST(AffectReranker, RerankOrdersAndBreakdownAligns) {
    // 同 base 下,高 salience+新近者必须排前;breakdown 与输出同序同 id。
    std::vector<RerankCandidate> cands;
    cands.push_back({row("old-dull", "2026-01-01T00:00:00Z"), 0.8, 0.0, 0.0});
    cands.push_back({row("new-hot",  "2026-06-11T00:00:00Z"), 0.8, 0.9, 0.5});
    QuerierAffectState q{};  // 中性
    const auto breakdown = rerank(cands, q, "2026-06-12T00:00:00Z");
    ASSERT_EQ(cands.size(), 2u);
    ASSERT_EQ(breakdown.size(), 2u);
    EXPECT_EQ(cands[0].row.id, "new-hot");
    EXPECT_EQ(breakdown[0].statement_id, "new-hot");
    EXPECT_GT(breakdown[0].final_score, breakdown[1].final_score);
    // 公式抽查:final = base·(1+0.3r)·(1+0.4s)·(1+0.3a)·affect·(1-penalty)
    const auto& b = breakdown[0];
    EXPECT_NEAR(b.final_score,
                b.base * (1 + 0.3 * b.recency) * (1 + 0.4 * b.salience)
                       * (1 + 0.3 * b.activation) * b.affect_consistency
                       * (1 - b.temporal_penalty), 1e-9);
}

}  // namespace starling::retrieval
```

- [ ] **Step 2: 跑测试确认编译失败(头不存在)**

Run: `cd /Users/jaredguo-mini/develop/memory/starling && PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build 2>&1 | tail -3`
Expected: FAIL,`affect_reranker.hpp: No such file or directory`(先把测试文件加进 tests/cpp/CMakeLists.txt 再跑;见 Step 3 文件清单改动)

- [ ] **Step 3: 实现 affect_reranker.hpp**

```cpp
#pragma once
// Affect-aware Reranker(13_retrieval.md §核心算法-2):
//   score = base·(1+0.3·recency)·(1+0.4·salience)·(1+0.3·activation)
//           ·affect_consistency·(1−temporal_penalty)
// 因子全部 [0,1] 有界;affect_consistency 有 0.5 下界(情感失配降权但绝不
// 清零候选——零分会让 abstention 的 low_score 判定失真)。
#include <string>
#include <string_view>
#include <vector>

#include "starling/affect/affect_vector.hpp"
#include "starling/retrieval/statement_row.hpp"

namespace starling::retrieval {

struct QuerierAffectState {
    affect::AffectVector affect;   // 默认全零 = 中性
};

// 一行可审计打分(receipt.score_breakdown 行;Task 3 receipt include 本头)。
struct ScoreRow {
    std::string statement_id;
    double base{};
    double recency{};
    double salience{};
    double activation{};
    double affect_consistency{};
    double temporal_penalty{};
    double final_score{};
};

struct RerankCandidate {
    StatementRow row;
    double base_relevance{};   // 语义路径=cosine;结构化路径=1.0
    double salience{};         // statements.salience 列(planner SELECT 附带)
    double activation{};       // statements.activation 列
};

// 30 天半衰 e 指数;observed_at 晚于 as_of(未来)按 1.0。
double recency_factor(std::string_view observed_at_iso, std::string_view as_of_iso);
// clamp [0,1]。
double activation_level(double activation);
// v1 有界惩罚:valid_to 非空且 <= as_of → 0.3(过期降权);否则 0。
double temporal_distance_penalty(const StatementRow& row, std::string_view as_of_iso);
// 1 − L1(Δ affect)/5 映射到 [0.5, 1];"{}"/解析失败按中性向量。
double affect_consistency(std::string_view affect_json,
                          const affect::AffectVector& querier);

// 原地按 final_score 降序排序 cands,返回同序 breakdown。
std::vector<ScoreRow> rerank(std::vector<RerankCandidate>& cands,
                             const QuerierAffectState& querier,
                             std::string_view as_of_iso);

}  // namespace starling::retrieval
```

- [ ] **Step 4: 实现 affect_reranker.cpp**

```cpp
#include "starling/retrieval/affect_reranker.hpp"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <ctime>

namespace starling::retrieval {

namespace {
double parse_iso_epoch(std::string_view iso) {
    if (iso.empty()) return 0.0;
    std::tm tm{}; int y, mo, d, h, mi, s;
    if (std::sscanf(std::string(iso).c_str(), "%d-%d-%dT%d:%d:%d",
                    &y, &mo, &d, &h, &mi, &s) != 6) return 0.0;
    tm.tm_year = y - 1900; tm.tm_mon = mo - 1; tm.tm_mday = d;
    tm.tm_hour = h; tm.tm_min = mi; tm.tm_sec = s;
    return static_cast<double>(timegm(&tm));
}
double clamp01(double v) { return v < 0.0 ? 0.0 : (v > 1.0 ? 1.0 : v); }
}  // namespace

double recency_factor(std::string_view observed_at_iso, std::string_view as_of_iso) {
    const double dt = parse_iso_epoch(as_of_iso) - parse_iso_epoch(observed_at_iso);
    if (dt <= 0.0) return 1.0;
    return std::exp(-dt / (30.0 * 86400.0));
}

double activation_level(double activation) { return clamp01(activation); }

double temporal_distance_penalty(const StatementRow& row, std::string_view as_of_iso) {
    if (row.valid_to.empty()) return 0.0;
    return parse_iso_epoch(row.valid_to) <= parse_iso_epoch(as_of_iso) ? 0.3 : 0.0;
}

double affect_consistency(std::string_view affect_json,
                          const affect::AffectVector& querier) {
    const affect::AffectVector c = affect::parse_affect_json(affect_json);
    const double l1 = std::abs(double(c.valence)   - double(querier.valence))
                    + std::abs(double(c.arousal)   - double(querier.arousal))
                    + std::abs(double(c.dominance) - double(querier.dominance))
                    + std::abs(double(c.novelty)   - double(querier.novelty))
                    + std::abs(double(c.stakes)    - double(querier.stakes));
    const double sim = clamp01(1.0 - l1 / 5.0);
    return 0.5 + 0.5 * sim;
}

std::vector<ScoreRow> rerank(std::vector<RerankCandidate>& cands,
                             const QuerierAffectState& querier,
                             std::string_view as_of_iso) {
    std::vector<ScoreRow> breakdown;
    breakdown.reserve(cands.size());
    std::vector<std::pair<double, std::size_t>> order;
    order.reserve(cands.size());
    for (std::size_t i = 0; i < cands.size(); ++i) {
        const auto& c = cands[i];
        ScoreRow s;
        s.statement_id      = c.row.id;
        s.base              = c.base_relevance;
        s.recency           = recency_factor(c.row.observed_at, as_of_iso);
        s.salience          = clamp01(c.salience);
        s.activation        = activation_level(c.activation);
        s.affect_consistency = affect_consistency(c.row.affect_json, querier.affect);
        s.temporal_penalty  = temporal_distance_penalty(c.row, as_of_iso);
        s.final_score = s.base * (1 + 0.3 * s.recency) * (1 + 0.4 * s.salience)
                      * (1 + 0.3 * s.activation) * s.affect_consistency
                      * (1 - s.temporal_penalty);
        breakdown.push_back(std::move(s));
        order.emplace_back(breakdown.back().final_score, i);
    }
    std::sort(order.begin(), order.end(),
              [](const auto& a, const auto& b) { return a.first > b.first; });
    std::vector<RerankCandidate> sorted_c; sorted_c.reserve(cands.size());
    std::vector<ScoreRow> sorted_b; sorted_b.reserve(breakdown.size());
    for (const auto& [score, idx] : order) {
        sorted_c.push_back(std::move(cands[idx]));
        sorted_b.push_back(std::move(breakdown[idx]));
    }
    cands = std::move(sorted_c);
    return sorted_b;
}

}  // namespace starling::retrieval
```

- [ ] **Step 5: CMake 两清单登记**

`CMakeLists.txt`:在 `src/retrieval/pattern_completor.cpp` 行(:139)后加:
```cmake
    src/retrieval/affect_reranker.cpp
```
`tests/cpp/CMakeLists.txt`:在 `test_memory_ops.cpp` 行(:134)后加:
```cmake
    test_affect_reranker.cpp
```

- [ ] **Step 6: 构建 + 测试通过**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling && PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build 2>&1 | tail -2
./build/tests/cpp/starling_tests --gtest_filter='AffectReranker.*' 2>&1 | tail -3
```
Expected: `[  PASSED  ] 2 tests.`

- [ ] **Step 7: Commit**

```bash
cd /Users/jaredguo-mini/develop/memory/starling
git add include/starling/retrieval/affect_reranker.hpp src/retrieval/affect_reranker.cpp tests/cpp/test_affect_reranker.cpp CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -F - <<'EOF'
feat(P3.a1): Affect-aware Reranker — 五因子乘法公式 + 可审计 breakdown

recency(30 天半衰)/salience/activation/affect_consistency(0.5 下界)/
temporal_penalty(v1 有界);ScoreRow 即 receipt.score_breakdown 行格式。

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
```

---

### Task 3: RetrievalScopePlan/Step + Receipt 完整字段(纯增量)

**Files:**
- Create: `include/starling/retrieval/retrieval_scope.hpp`
- Modify: `include/starling/retrieval/retrieval_receipt.hpp`(44 行后追加字段)
- Test: 编译期 + 既有 receipt 钉测全绿(行为零变化;新字段默认空)

- [ ] **Step 1: 新建 retrieval_scope.hpp**

```cpp
#pragma once
// RetrievalScopeStep / RetrievalScopePlan(13_retrieval.md §数据结构)。
// scope 取值:working_set | statement_main | projection_index | semantic_index
// | graph_index | container_view | engram_evidence | tom_runtime。
#include <string>
#include <vector>

namespace starling::retrieval {

struct FilterApplied;  // fwd(定义在 retrieval_receipt.hpp;两头互不 include,
                       // planner 同时 include 两者)

struct RetrievalScopeStep {
    std::string scope;
    std::string holder_scope;            // 本步唯一 holder(多 holder 隔离契约)
    std::string group_scope;             // "" 除非群组
    std::vector<std::pair<std::string, std::string>> filters;  // name→value
    int max_candidates = 50;
    std::string on_error = "degrade";    // degrade | abstain | fail_closed
};

struct RetrievalScopePlan {
    std::string plan_id;                 // = query_id
    std::string mode = "progressive";    // basic|progressive|parallel|exhaustive
    std::vector<RetrievalScopeStep> steps;
    std::string stop_policy = "after_first_sufficient";
    std::string merge_policy = "ranked_union";
    std::string filter_mode = "per_scope_explicit";
};

}  // namespace starling::retrieval
```

- [ ] **Step 2: receipt 追加字段(retrieval_receipt.hpp,`sufficiency_status` 行后)**

文件头部 include 区加:
```cpp
#include "starling/retrieval/affect_reranker.hpp"   // ScoreRow
#include "starling/retrieval/retrieval_scope.hpp"   // RetrievalScopePlan
```
`Sufficiency  sufficiency_status{Sufficiency::ABSTAINED};` 之后追加:
```cpp

    // ── P3.a1 planner 字段(默认空;P1 basic_retrieve 路径不填,旧钉测不变)──
    struct PlanStepTrace { std::string step; std::string detail; };
    struct SkippedScope  { std::string scope; std::string reason; std::string stop_policy; };
    struct DegradedPath  { std::string path;  std::string reason; std::string fallback; };

    std::string querier;
    std::string perspective;
    std::string intent_name;                       // to_string(intent)
    std::string runtime_health{"READY"};           // 调用方注入(Python runtime 知情方)
    std::string trace_retention{"metadata_only"};
    RetrievalScopePlan scope_plan;                 // plan_id 空 = 未走 planner
    std::vector<PlanStepTrace> plan_steps;         // 7 步各一行
    std::vector<SkippedScope> skipped_scopes;      // progressive 跳过的 scope
    std::string stop_reason;
    std::vector<std::string> scopes_searched;
    std::vector<ScoreRow> score_breakdown;
    std::vector<DegradedPath> degraded_paths;
    std::string abstention_reason;                 // ""=未拒答
    std::vector<std::string> emitted_events;       // statement.recalled 事件 id
    std::int64_t projection_lag_events{};          // outbox 头 − 最慢消费者 checkpoint
```

- [ ] **Step 3: 构建 + 既有钉测全绿**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling && PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build 2>&1 | tail -2
./build/tests/cpp/starling_tests --gtest_filter='*Receipt*:*BasicRetriever*' 2>&1 | tail -3
```
Expected: PASSED,0 fail

- [ ] **Step 4: Commit**

```bash
cd /Users/jaredguo-mini/develop/memory/starling
git add include/starling/retrieval/retrieval_scope.hpp include/starling/retrieval/retrieval_receipt.hpp
git commit -F - <<'EOF'
feat(P3.a1): RetrievalScopePlan/Step + Receipt 完整字段(纯增量)

新字段默认空,P1 basic_retrieve 行为与既有钉测零变化。sanitized_query 按
spec 裁剪登记延至 P3.b(随 query 清洗管线)。

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
```

---

### Task 4: Abstention Gate(四条件,结构化拒答)

**Files:**
- Create: `include/starling/retrieval/abstention.hpp`
- Create: `src/retrieval/abstention.cpp`
- Modify: `CMakeLists.txt` / `tests/cpp/CMakeLists.txt`(各 +1 行,加在 Task 2 新增行后)
- Test: `tests/cpp/test_abstention_gate.cpp`

- [ ] **Step 1: 失败测试 tests/cpp/test_abstention_gate.cpp**

```cpp
// Abstention Gate 四条件(13_retrieval.md §Abstention 触发条件)。
// 结构化 reason,绝不模糊;条件优先级:frontier > only_recanted > conflict > low_score。
#include "starling/retrieval/abstention.hpp"
#include <gtest/gtest.h>

namespace starling::retrieval {

TEST(AbstentionGate, FourConditionsAndPriority) {
    AbstentionInput in;
    in.any_candidates = true; in.max_score = 0.9;
    EXPECT_EQ(evaluate_abstention(in), "");                       // 不拒答

    in.max_score = 0.1;
    EXPECT_EQ(evaluate_abstention(in), "low_score");              // τ=0.25 默认

    AbstentionConfig loose; loose.tau_recall = 0.05;
    EXPECT_EQ(evaluate_abstention(in, loose), "");                // 阈值可配

    in.unresolved_conflict = true;
    EXPECT_EQ(evaluate_abstention(in), "conflict_unresolved");    // 优先于 low_score

    in.only_recanted_evidence = true;
    EXPECT_EQ(evaluate_abstention(in), "only_recanted");

    in.frontier_denied = true;
    EXPECT_EQ(evaluate_abstention(in), "frontier_deny");          // 最高优先

    // 无候选 + frontier 没遮蔽过任何东西 → low_score(max_score=0)。
    AbstentionInput empty;
    EXPECT_EQ(evaluate_abstention(empty), "low_score");
}

}  // namespace starling::retrieval
```

- [ ] **Step 2: 实现 abstention.hpp**

```cpp
#pragma once
// Abstention Gate(13_retrieval.md §Abstention 触发条件):四条件任一满足
// 即结构化拒答("我不知道,因为 ___"),不编造、不输出模糊"不确定"。
// reason 枚举字符串:frontier_deny | only_recanted | conflict_unresolved | low_score。
#include <string>

namespace starling::retrieval {

struct AbstentionConfig {
    double tau_recall = 0.25;   // rerank 后 max(final_score) 阈值
};

struct AbstentionInput {
    double max_score = 0.0;            // rerank 后最高分(无候选=0)
    bool any_candidates = false;
    bool frontier_denied = false;      // mask 遮蔽后候选清零(遮蔽前非零)
    bool only_recanted_evidence = false;  // 全部候选的 cg 状态 recanted
    bool unresolved_conflict = false;  // 最高分候选挂未仲裁 CONFLICTS_WITH 边
};

// 返回 "" = 不拒答;否则四 reason 之一(优先级 frontier > recanted > conflict > score)。
std::string evaluate_abstention(const AbstentionInput& in,
                                const AbstentionConfig& cfg = {});

}  // namespace starling::retrieval
```

- [ ] **Step 3: 实现 abstention.cpp**

```cpp
#include "starling/retrieval/abstention.hpp"

namespace starling::retrieval {

std::string evaluate_abstention(const AbstentionInput& in,
                                const AbstentionConfig& cfg) {
    if (in.frontier_denied)         return "frontier_deny";
    if (in.only_recanted_evidence)  return "only_recanted";
    if (in.unresolved_conflict)     return "conflict_unresolved";
    if (!in.any_candidates || in.max_score < cfg.tau_recall) return "low_score";
    return "";
}

}  // namespace starling::retrieval
```

- [ ] **Step 4: CMake 登记(两清单各 +1)、构建、测试**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling && PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build 2>&1 | tail -2
./build/tests/cpp/starling_tests --gtest_filter='AbstentionGate.*' 2>&1 | tail -3
```
Expected: `[  PASSED  ] 1 test.`

- [ ] **Step 5: Commit**

```bash
cd /Users/jaredguo-mini/develop/memory/starling
git add include/starling/retrieval/abstention.hpp src/retrieval/abstention.cpp tests/cpp/test_abstention_gate.cpp CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -F - <<'EOF'
feat(P3.a1): Abstention Gate — 四条件结构化拒答(τ_recall 可配默认 0.25)

优先级 frontier_deny > only_recanted > conflict_unresolved > low_score。

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
```

---

### Task 5: Context Pack 8 标签分类器 + 渲染

**Files:**
- Create: `include/starling/retrieval/context_pack.hpp`
- Create: `src/retrieval/context_pack.cpp`
- Modify: `CMakeLists.txt` / `tests/cpp/CMakeLists.txt`(各 +1)
- Test: `tests/cpp/test_context_pack.cpp`

- [ ] **Step 1: 失败测试 tests/cpp/test_context_pack.cpp**

```cpp
// Context Pack 8 标签判定(13_retrieval.md §核心算法-3)。
// 优先级(首中即停):TODO > CONFLICT > COMMON > INFERRED > HEARSAY > BELIEF > FACT。
// ABSTAIN 不走 classify——由 abstention gate 注入整包。
#include "starling/retrieval/context_pack.hpp"
#include <gtest/gtest.h>

namespace starling::retrieval {

namespace {
StatementRow row(const char* id, const char* holder, const char* modality,
                 double conf, const char* provenance_evidence_count = "two") {
    StatementRow r;
    r.id = id; r.holder_id = holder; r.subject_id = "Bob";
    r.predicate = "responsible_for"; r.object_value = "auth";
    r.modality = modality; r.confidence = conf;
    r.consolidation_state = "consolidated";
    // 单证据 → evidence_json 一个元素;双证据 → 两个。
    r.evidence_json = (std::string(provenance_evidence_count) == "one")
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
    // provenance≠user_input → INFERRED(用 derived 行模拟:本测试直接改字段)。
    auto inferred = row("i1", "cog-self", "BELIEVES", 0.7);
    inferred.modality = "BELIEVES";
    EXPECT_EQ(classify_with_provenance(inferred, ctx, "tom_inferred"),
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
```

- [ ] **Step 2: 实现 context_pack.hpp**

```cpp
#pragma once
// Context Pack 8 标签(13_retrieval.md §核心算法-3):LLM 收到的不是无差别
// 文本,而是带认识论地位标注的语用结构。classify 为纯函数:行 + 三个成员集
// (planner 预查的承诺/冲突/共识 id 集)→ 标签;首中即停的优先级链。
#include <string>
#include <string_view>
#include <unordered_set>
#include <vector>

#include "starling/retrieval/statement_row.hpp"

namespace starling::retrieval {

enum class ContextPackLabel { FACT, BELIEF, HEARSAY, INFERRED, COMMON, TODO, CONFLICT, ABSTAIN };

inline const char* to_string(ContextPackLabel v) {
    switch (v) {
        case ContextPackLabel::FACT:     return "FACT";
        case ContextPackLabel::BELIEF:   return "BELIEF";
        case ContextPackLabel::HEARSAY:  return "HEARSAY";
        case ContextPackLabel::INFERRED: return "INFERRED";
        case ContextPackLabel::COMMON:   return "COMMON";
        case ContextPackLabel::TODO:     return "TODO";
        case ContextPackLabel::CONFLICT: return "CONFLICT";
        case ContextPackLabel::ABSTAIN:  return "ABSTAIN";
    }
    return "FACT";
}

struct PackContext {
    std::unordered_set<std::string> todo_ids;      // 活跃承诺的 stmt_id
    std::unordered_set<std::string> conflict_ids;  // 未仲裁 CONFLICTS_WITH 端点
    std::unordered_set<std::string> common_ids;    // grounded 共识 stmt_id
    std::unordered_set<std::string> recanted_ids;  // recanted 共识 stmt_id
    std::string querier;
};

struct PackEntry {
    ContextPackLabel label;
    std::string statement_id;
    std::string line;
};

// provenance 不在 StatementRow 里(P1 列裁剪);planner 持有该列时走带参版本。
ContextPackLabel classify_with_provenance(const StatementRow& row,
                                          const PackContext& ctx,
                                          std::string_view provenance);
// 便捷版:provenance 视为 "user_input"。
ContextPackLabel classify(const StatementRow& row, const PackContext& ctx);

// "[LABEL] subject predicate object (conf 0.93, holder Alice)"
std::string render_line(const StatementRow& row, ContextPackLabel label);
// 整包渲染;abstention_reason 非空时输出单行 "[ABSTAIN] 无可靠记忆(reason)"。
std::string render_pack(const std::vector<PackEntry>& entries,
                        std::string_view abstention_reason);

}  // namespace starling::retrieval
```

- [ ] **Step 3: 实现 context_pack.cpp**

```cpp
#include "starling/retrieval/context_pack.hpp"

#include <sstream>

namespace starling::retrieval {

namespace {
// evidence_json 是 EvidenceRef 数组;数 "engram_id" 出现次数即证据条数。
int evidence_count(std::string_view evidence_json) {
    int n = 0;
    std::string::size_type pos = 0;
    const std::string s(evidence_json);
    while ((pos = s.find("engram_id", pos)) != std::string::npos) { ++n; pos += 9; }
    return n;
}
}  // namespace

ContextPackLabel classify_with_provenance(const StatementRow& row,
                                          const PackContext& ctx,
                                          std::string_view provenance) {
    if (ctx.todo_ids.count(row.id))     return ContextPackLabel::TODO;
    if (ctx.conflict_ids.count(row.id)) return ContextPackLabel::CONFLICT;
    if (ctx.common_ids.count(row.id))   return ContextPackLabel::COMMON;
    if (!provenance.empty() && provenance != "user_input")
        return ContextPackLabel::INFERRED;
    const bool other_holder = !ctx.querier.empty() && row.holder_id != ctx.querier;
    if (other_holder && evidence_count(row.evidence_json) <= 1)
        return ContextPackLabel::HEARSAY;
    if (other_holder) return ContextPackLabel::BELIEF;
    if ((row.modality == "BELIEVES" || row.modality == "ASSUMES" ||
         row.modality == "DOUBTS") && row.confidence < 0.8)
        return ContextPackLabel::BELIEF;
    return ContextPackLabel::FACT;
}

ContextPackLabel classify(const StatementRow& row, const PackContext& ctx) {
    return classify_with_provenance(row, ctx, "user_input");
}

std::string render_line(const StatementRow& row, ContextPackLabel label) {
    std::ostringstream os;
    os << "[" << to_string(label) << "] "
       << row.subject_id << " " << row.predicate << " " << row.object_value;
    os.setf(std::ios::fixed); os.precision(2);
    os << " (conf " << row.confidence;
    if (!row.holder_id.empty()) os << ", holder " << row.holder_id;
    os << ")";
    return os.str();
}

std::string render_pack(const std::vector<PackEntry>& entries,
                        std::string_view abstention_reason) {
    if (!abstention_reason.empty()) {
        std::string s = "[ABSTAIN] 无可靠记忆,主动拒答(";
        s += abstention_reason; s += ")";
        return s;
    }
    std::ostringstream os;
    for (std::size_t i = 0; i < entries.size(); ++i) {
        if (i) os << "\n";
        os << entries[i].line;
    }
    return os.str();
}

}  // namespace starling::retrieval
```

- [ ] **Step 4: CMake 登记、构建、测试**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling && PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build 2>&1 | tail -2
./build/tests/cpp/starling_tests --gtest_filter='ContextPack.*' 2>&1 | tail -3
```
Expected: `[  PASSED  ] 2 tests.`

- [ ] **Step 5: Commit**

```bash
cd /Users/jaredguo-mini/develop/memory/starling
git add include/starling/retrieval/context_pack.hpp src/retrieval/context_pack.cpp tests/cpp/test_context_pack.cpp CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -F - <<'EOF'
feat(P3.a1): Context Pack 8 标签分类器 + 渲染

纯函数 classify(行+承诺/冲突/共识成员集),优先级 TODO>CONFLICT>COMMON>
INFERRED>HEARSAY>BELIEF>FACT;ABSTAIN 由 gate 注入整包。

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
```

---

### Task 6: RetrievalPlanner 7 步管线(核心三路:FACT_LOOKUP / BELIEF_OF_OTHER / HISTORY)

**Files:**
- Create: `include/starling/retrieval/retrieval_planner.hpp`
- Create: `src/retrieval/retrieval_planner.cpp`
- Modify: `CMakeLists.txt` / `tests/cpp/CMakeLists.txt`(各 +1)
- Test: `tests/cpp/test_retrieval_planner.cpp`(本 task 首批 4 例)

设计要点(写进头注释):
- **perspective filter 位序**:结构化路径在 SQL WHERE 下推(`holder_id`/frontier EXISTS);语义路径取回候选后、**rerank 之前**按 `KnowledgeFrontier::visible_engrams_at(perspective)` 的可见集过滤 evidence(`frontier_masked_count` 计数)。两路都满足 spec :107「排序之前」。
- **中心化 emit**:planner 不复用 `BasicRetriever::run`(那会双发事件);自带 SELECT(附 salience/activation 两列),对**最终返回**的 rows 统一 emit `statement.recalled`,幂等键沿用既有公式(`compute_idempotency_key("statement.recalled", row.id, row.id, query_id, 2s bucket)`),`emitted_events` 记 event_id。
- **progressive**:`statement_main` 先行;命中 ≥ k 则跳过 `semantic_index` 并记 `skipped_scopes` + `stop_reason="after_first_sufficient"`;`ABSTAIN_CHECK` 永远 exhaustive。

- [ ] **Step 1: 实现 retrieval_planner.hpp**

```cpp
#pragma once
// Retrieval Planner — 7 步规划管线(13_retrieval.md §P3 完整 7 步规划):
//   parse → mask → plan → fetch → fuse → ground → abstain
// 每步写 receipt.plan_steps 一行;perspective filter 必须先于语义排序
// (结构化路径 SQL 下推,语义路径 rerank 前按可见集遮蔽)。对外唯一副作用
// 是 fire-and-forget emit statement.recalled(读副作用契约)。
#include <string>
#include <vector>

#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/retrieval/abstention.hpp"
#include "starling/retrieval/affect_reranker.hpp"
#include "starling/retrieval/context_pack.hpp"
#include "starling/retrieval/query_intent.hpp"
#include "starling/retrieval/retrieval_receipt.hpp"
#include "starling/retrieval/semantic_retriever.hpp"
#include "starling/retrieval/statement_row.hpp"

namespace starling::retrieval {

struct PlannerQuery {
    std::string tenant_id;
    std::string querier;                 // 谁在问(默认 self)
    std::string perspective;             // 从谁的视角;空 = querier
    QueryIntent intent = QueryIntent::FACT_LOOKUP;
    std::string text;                    // 语义线索(semantic_index 源)
    std::string subject_id;              // 结构化提示(可空)
    std::string predicate;               // 结构化提示(可空)
    std::string target;                  // BELIEF_OF_OTHER/META_BELIEF/COMMON_GROUND 对方
    std::string as_of_iso8601;
    int k = 10;
    std::string trace_id;
    std::string query_id;
    std::string runtime_health = "READY";   // 调用方注入
    AbstentionConfig abstention;
};

struct PlannerEntryOut {
    StatementRow row;
    double score = 0.0;
    ContextPackLabel label = ContextPackLabel::FACT;
};

struct PlannerResult {
    std::vector<PlannerEntryOut> entries;
    RetrievalReceipt receipt;
    std::string context_pack;            // 渲染后的 8 标签文本
    bool abstained = false;
};

class RetrievalPlanner {
 public:
    // SemanticRetriever 调用方注入:与写入侧同一 embedder(DashboardEngine
    // rebuild_embedder 纪律)。
    RetrievalPlanner(persistence::SqliteAdapter& adapter, SemanticRetriever& semantic)
        : adapter_(adapter), semantic_(semantic) {}

    RetrievalPlanner(const RetrievalPlanner&)            = delete;
    RetrievalPlanner& operator=(const RetrievalPlanner&) = delete;

    // 空 tenant/querier/as_of/query_id → throw std::invalid_argument。
    PlannerResult run(const PlannerQuery& q);

 private:
    persistence::SqliteAdapter& adapter_;
    SemanticRetriever& semantic_;
};

}  // namespace starling::retrieval
```

- [ ] **Step 2: 实现 retrieval_planner.cpp(7 步骨架 + 三条 intent 路径)**

```cpp
#include "starling/retrieval/retrieval_planner.hpp"

#include <algorithm>
#include <chrono>
#include <stdexcept>
#include <unordered_map>
#include <unordered_set>

#include <sqlite3.h>

#include "starling/bus/bus_event.hpp"
#include "starling/bus/outbox_writer.hpp"
#include "starling/cognizer/knowledge_frontier.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/persistence/sqlite_helpers.hpp"
#include "starling/persistence/transaction_guard.hpp"
#include "starling/tom/common_ground.hpp"

namespace starling::retrieval {

using persistence::StmtHandle;
using persistence::detail::bind_sv;
using persistence::detail::make_sqlite_error;

namespace {

// 候选行 + planner 需要、StatementRow 不含的三列。
struct FetchedRow {
    StatementRow row;
    double salience = 0.0;
    double activation = 0.0;
    std::string provenance;
    double base = 1.0;   // 结构化路径=1.0;语义路径=cosine
};

constexpr const char* kSelectCols =
    "SELECT id, tenant_id, holder_id, holder_perspective, subject_kind, "
    "subject_id, predicate, object_kind, object_value, canonical_object_hash, "
    "modality, polarity, confidence, observed_at, valid_from, valid_to, "
    "consolidation_state, review_status, evidence_json, affect_json, "
    "salience, activation, provenance FROM statements ";

FetchedRow read_row(sqlite3_stmt* st) {
    auto txt = [&](int i) {
        const auto* p = sqlite3_column_text(st, i);
        return p ? std::string(reinterpret_cast<const char*>(p)) : std::string();
    };
    FetchedRow f;
    auto& r = f.row;
    r.id = txt(0); r.tenant_id = txt(1); r.holder_id = txt(2);
    r.holder_perspective = txt(3); r.subject_kind = txt(4); r.subject_id = txt(5);
    r.predicate = txt(6); r.object_kind = txt(7); r.object_value = txt(8);
    r.canonical_object_hash = txt(9); r.modality = txt(10); r.polarity = txt(11);
    r.confidence = sqlite3_column_double(st, 12);
    r.observed_at = txt(13); r.valid_from = txt(14); r.valid_to = txt(15);
    r.consolidation_state = txt(16); r.review_status = txt(17);
    r.evidence_json = txt(18); r.affect_json = txt(19);
    f.salience = sqlite3_column_double(st, 20);
    f.activation = sqlite3_column_double(st, 21);
    f.provenance = txt(22);
    return f;
}

// 稳定状态 + 审核过滤 + 时间窗,全部结构化路径共用的 WHERE 尾巴。
constexpr const char* kStableTail =
    " AND consolidation_state IN ('consolidated','archived')"
    " AND review_status NOT IN ('rejected','pending_review')"
    " AND (valid_from IS NULL OR valid_from <= ?9)"
    " AND (valid_to   IS NULL OR valid_to   >  ?9) ";

void push_filter(RetrievalScopeStep& step, std::string name, std::string value) {
    step.filters.emplace_back(std::move(name), std::move(value));
}

}  // namespace

PlannerResult RetrievalPlanner::run(const PlannerQuery& q) {
    if (q.tenant_id.empty() || q.querier.empty() || q.as_of_iso8601.empty()
        || q.query_id.empty()) {
        throw std::invalid_argument(
            "RetrievalPlanner: tenant_id/querier/as_of/query_id are required");
    }
    auto& conn = adapter_.connection();
    sqlite3* db = conn.raw();

    PlannerResult out;
    auto& rc = out.receipt;
    rc.trace_id = q.trace_id; rc.query_id = q.query_id;
    rc.querier = q.querier;
    rc.perspective = q.perspective.empty() ? q.querier : q.perspective;
    rc.intent_name = to_string(q.intent);
    rc.runtime_health = q.runtime_health;
    rc.scope_plan.plan_id = q.query_id;
    rc.scope_plan.mode =
        (q.intent == QueryIntent::ABSTAIN_CHECK) ? "exhaustive" : "progressive";
    const std::string perspective = rc.perspective;

    // ── 1. parse:意图显式传入;归一结构化提示。──────────────────────────
    rc.plan_steps.push_back({"parse",
        std::string("intent=") + rc.intent_name +
        (q.subject_id.empty() ? "" : " subject=" + q.subject_id) +
        (q.predicate.empty() ? "" : " predicate=" + q.predicate)});

    // ── 2. mask:perspective ≠ querier 时取 KnowledgeFrontier 可见集。────
    const bool need_mask = perspective != q.querier;
    std::unordered_set<std::string> visible;
    if (need_mask) {
        cognizer::KnowledgeFrontier frontier(adapter_);
        visible = frontier.visible_engrams_at(q.tenant_id, perspective,
                                              q.as_of_iso8601);
    }
    rc.plan_steps.push_back({"mask",
        need_mask ? "frontier visible_engrams=" + std::to_string(visible.size())
                  : "perspective==querier, no mask"});

    // ── 3. plan:Intent→Path(本 task 三路;Task 7 补其余)。──────────────
    auto add_step = [&](std::string scope, std::string holder,
                        int max_candidates) {
        RetrievalScopeStep step;
        step.scope = std::move(scope);
        step.holder_scope = std::move(holder);
        step.max_candidates = max_candidates;
        push_filter(step, "tenant_id", q.tenant_id);
        push_filter(step, "holder_scope", step.holder_scope);
        push_filter(step, "perspective", perspective);
        rc.scope_plan.steps.push_back(std::move(step));
    };
    switch (q.intent) {
        case QueryIntent::FACT_LOOKUP:
            add_step("statement_main", q.querier, q.k * 5);
            add_step("semantic_index", q.querier, q.k * 5);
            break;
        case QueryIntent::BELIEF_OF_OTHER:
            add_step("statement_main", q.target, q.k * 5);
            break;
        case QueryIntent::HISTORY:
            add_step("statement_main", q.querier, q.k * 10);
            add_step("graph_index", q.querier, q.k * 5);   // supersedes 链
            break;
        default:
            // Task 7 填充其余 intent;在那之前走 FACT_LOOKUP 等价路径。
            add_step("statement_main", q.querier, q.k * 5);
            add_step("semantic_index", q.querier, q.k * 5);
            break;
    }
    rc.plan_steps.push_back({"plan",
        "steps=" + std::to_string(rc.scope_plan.steps.size()) +
        " mode=" + rc.scope_plan.mode});

    // ── 4. fetch:按 plan 逐 scope;progressive 早停。─────────────────────
    std::vector<FetchedRow> fetched;
    auto fetch_statement_main = [&](const RetrievalScopeStep& step) {
        std::string sql = std::string(kSelectCols) +
            "WHERE tenant_id = ?1 AND holder_id = ?2 ";
        if (!q.subject_id.empty()) sql += " AND subject_id = ?3 ";
        if (!q.predicate.empty())  sql += " AND predicate  = ?4 ";
        sql += kStableTail;
        sql += (q.intent == QueryIntent::HISTORY)
                   ? " ORDER BY observed_at ASC LIMIT ?5"
                   : " ORDER BY observed_at DESC LIMIT ?5";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db, sql.c_str(), -1, &raw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(db, "planner: statement_main prepare");
        StmtHandle h(raw);
        bind_sv(h.get(), 1, q.tenant_id);
        bind_sv(h.get(), 2, step.holder_scope);
        if (!q.subject_id.empty()) bind_sv(h.get(), 3, q.subject_id);
        if (!q.predicate.empty())  bind_sv(h.get(), 4, q.predicate);
        bind_sv(h.get(), 9, q.as_of_iso8601);
        sqlite3_bind_int(h.get(), 5, step.max_candidates);
        while (sqlite3_step(h.get()) == SQLITE_ROW) fetched.push_back(read_row(h.get()));
    };
    auto fetch_semantic = [&](const RetrievalScopeStep& step) {
        if (q.text.empty()) {
            rc.skipped_scopes.push_back({"semantic_index", "empty_query_text",
                                         rc.scope_plan.stop_policy});
            return;
        }
        SemanticRetrieverParams sp;
        sp.tenant_id = q.tenant_id; sp.holder_id = step.holder_scope;
        sp.query_text = q.text; sp.k = step.max_candidates;
        sp.trace_id = q.trace_id; sp.query_id = q.query_id;
        const auto sr = semantic_.vector_recall(conn, sp);
        if (sr.degraded)
            rc.degraded_paths.push_back({"semantic_index", "embedder_unavailable",
                                         "statement_main_only"});
        for (const auto& s : sr.rows) {
            FetchedRow f; f.row = s.row; f.base = s.score;
            // salience/activation 语义路径不带列 → 单行补查。
            sqlite3_stmt* raw = nullptr;
            if (sqlite3_prepare_v2(db,
                "SELECT salience, activation, provenance FROM statements "
                "WHERE id=?1 AND tenant_id=?2", -1, &raw, nullptr) == SQLITE_OK) {
                StmtHandle h(raw);
                bind_sv(h.get(), 1, s.row.id); bind_sv(h.get(), 2, q.tenant_id);
                if (sqlite3_step(h.get()) == SQLITE_ROW) {
                    f.salience   = sqlite3_column_double(h.get(), 0);
                    f.activation = sqlite3_column_double(h.get(), 1);
                    const auto* p = sqlite3_column_text(h.get(), 2);
                    f.provenance = p ? reinterpret_cast<const char*>(p) : "";
                }
            }
            fetched.push_back(std::move(f));
        }
    };
    auto fetch_graph_supersedes = [&](const RetrievalScopeStep& step) {
        // HISTORY 辅路:从已取行沿 supersedes 边补链上行。
        std::unordered_set<std::string> have;
        for (const auto& f : fetched) have.insert(f.row.id);
        std::vector<std::string> seeds;
        seeds.reserve(have.size());
        for (const auto& id : have) seeds.push_back(id);
        for (const auto& id : seeds) {
            sqlite3_stmt* raw = nullptr;
            if (sqlite3_prepare_v2(db,
                "SELECT dst_id FROM statement_edges WHERE src_id=?1 AND "
                "tenant_id=?2 AND edge_kind='supersedes' "
                "UNION SELECT src_id FROM statement_edges WHERE dst_id=?1 AND "
                "tenant_id=?2 AND edge_kind='supersedes'",
                -1, &raw, nullptr) != SQLITE_OK) continue;
            StmtHandle h(raw);
            bind_sv(h.get(), 1, id); bind_sv(h.get(), 2, q.tenant_id);
            while (sqlite3_step(h.get()) == SQLITE_ROW) {
                const auto* p = sqlite3_column_text(h.get(), 0);
                if (!p) continue;
                const std::string other(reinterpret_cast<const char*>(p));
                if (have.count(other)) continue;
                sqlite3_stmt* raw2 = nullptr;
                const std::string sql2 = std::string(kSelectCols) +
                    "WHERE id=?1 AND tenant_id=?2";
                if (sqlite3_prepare_v2(db, sql2.c_str(), -1, &raw2, nullptr)
                        != SQLITE_OK) continue;
                StmtHandle h2(raw2);
                bind_sv(h2.get(), 1, other); bind_sv(h2.get(), 2, q.tenant_id);
                if (sqlite3_step(h2.get()) == SQLITE_ROW) {
                    fetched.push_back(read_row(h2.get()));
                    have.insert(other);
                }
            }
        }
        (void)step;
    };

    for (const auto& step : rc.scope_plan.steps) {
        const bool progressive = rc.scope_plan.mode == "progressive";
        if (progressive && static_cast<int>(fetched.size()) >= q.k
            && step.scope == "semantic_index") {
            rc.skipped_scopes.push_back({step.scope, "sufficient_from_prior_scope",
                                         rc.scope_plan.stop_policy});
            rc.stop_reason = "after_first_sufficient";
            continue;
        }
        if (step.scope == "statement_main")      fetch_statement_main(step);
        else if (step.scope == "semantic_index") fetch_semantic(step);
        else if (step.scope == "graph_index")    fetch_graph_supersedes(step);
        rc.scopes_searched.push_back(step.scope);
    }
    rc.candidate_counts.fetched = static_cast<std::int64_t>(fetched.size());
    rc.plan_steps.push_back({"fetch",
        "fetched=" + std::to_string(fetched.size())});

    // mask 应用(语义/图路径取回的行在 rerank 前过滤;evidence 任一可见即可见)。
    std::int64_t masked = 0;
    const std::size_t before_mask = fetched.size();
    if (need_mask) {
        std::vector<FetchedRow> kept;
        kept.reserve(fetched.size());
        for (auto& f : fetched) {
            bool any_visible = false;
            for (const auto& eng : visible) {
                if (f.row.evidence_json.find(eng) != std::string::npos) {
                    any_visible = true; break;
                }
            }
            if (any_visible) kept.push_back(std::move(f));
            else ++masked;
        }
        fetched = std::move(kept);
    }
    rc.frontier_masked_count = masked;

    // ── 5. fuse:按 id 去重(保最高 base)→ Affect-aware rerank → 截断 k。──
    std::unordered_map<std::string, FetchedRow> dedup;
    for (auto& f : fetched) {
        auto it = dedup.find(f.row.id);
        if (it == dedup.end() || f.base > it->second.base)
            dedup[f.row.id] = std::move(f);
    }
    std::vector<RerankCandidate> cands;
    std::unordered_map<std::string, std::string> provenance_by_id;
    cands.reserve(dedup.size());
    for (auto& [id, f] : dedup) {
        provenance_by_id[id] = f.provenance;
        cands.push_back({std::move(f.row), f.base, f.salience, f.activation});
    }
    QuerierAffectState qa{};
    auto breakdown = rerank(cands, qa, q.as_of_iso8601);
    if (static_cast<int>(cands.size()) > q.k) {
        cands.resize(static_cast<std::size_t>(q.k));
        breakdown.resize(static_cast<std::size_t>(q.k));
    }
    rc.score_breakdown = breakdown;
    rc.plan_steps.push_back({"fuse",
        "deduped=" + std::to_string(dedup.size()) +
        " returned<=" + std::to_string(q.k)});

    // ── 6. ground:共识/承诺/冲突三集预查(Context Pack 成员集)。──────────
    PackContext pctx;
    pctx.querier = q.querier;
    const std::string cg_other = q.target.empty() ? perspective : q.target;
    for (const auto& e : tom::common_ground::query(adapter_, q.querier, cg_other,
                                                   q.tenant_id, q.as_of_iso8601)) {
        if (e.status == "grounded") pctx.common_ids.insert(e.statement_id);
        if (e.status == "recanted") pctx.recanted_ids.insert(e.statement_id);
    }
    {
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db,
            "SELECT stmt_id FROM commitments WHERE tenant_id=?1 AND "
            "state IN ('ACTIVE','created')", -1, &raw, nullptr) == SQLITE_OK) {
            StmtHandle h(raw);
            bind_sv(h.get(), 1, q.tenant_id);
            while (sqlite3_step(h.get()) == SQLITE_ROW) {
                const auto* p = sqlite3_column_text(h.get(), 0);
                if (p) pctx.todo_ids.insert(reinterpret_cast<const char*>(p));
            }
        }
    }
    {
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db,
            "SELECT src_id, dst_id FROM statement_edges WHERE tenant_id=?1 AND "
            "edge_kind='CONFLICTS_WITH'", -1, &raw, nullptr) == SQLITE_OK) {
            StmtHandle h(raw);
            bind_sv(h.get(), 1, q.tenant_id);
            while (sqlite3_step(h.get()) == SQLITE_ROW) {
                const auto* a = sqlite3_column_text(h.get(), 0);
                const auto* b = sqlite3_column_text(h.get(), 1);
                if (a) pctx.conflict_ids.insert(reinterpret_cast<const char*>(a));
                if (b) pctx.conflict_ids.insert(reinterpret_cast<const char*>(b));
            }
        }
    }
    rc.plan_steps.push_back({"ground",
        "common=" + std::to_string(pctx.common_ids.size()) +
        " todo=" + std::to_string(pctx.todo_ids.size()) +
        " conflict=" + std::to_string(pctx.conflict_ids.size())});

    // ── 7. abstain:四条件。──────────────────────────────────────────────
    AbstentionInput ab;
    ab.any_candidates = !cands.empty();
    ab.max_score = breakdown.empty() ? 0.0 : breakdown.front().final_score;
    ab.frontier_denied = need_mask && before_mask > 0 && cands.empty();
    if (!cands.empty()) {
        bool all_recanted = true;
        for (const auto& c : cands)
            if (!pctx.recanted_ids.count(c.row.id)) { all_recanted = false; break; }
        ab.only_recanted_evidence = all_recanted;
        ab.unresolved_conflict = pctx.conflict_ids.count(cands.front().row.id) > 0;
    }
    rc.abstention_reason = evaluate_abstention(ab, q.abstention);
    rc.plan_steps.push_back({"abstain",
        rc.abstention_reason.empty() ? "pass" : rc.abstention_reason});

    // ── 输出组装 + sufficiency + projection lag + 中心化 emit。────────────
    if (!rc.abstention_reason.empty()) {
        out.abstained = true;
        out.context_pack = render_pack({}, rc.abstention_reason);
        rc.sufficiency_status = Sufficiency::ABSTAINED;
        rc.candidate_counts.returned = 0;
        return out;
    }
    std::vector<PackEntry> entries;
    for (std::size_t i = 0; i < cands.size(); ++i) {
        const auto label = classify_with_provenance(
            cands[i].row, pctx, provenance_by_id[cands[i].row.id]);
        entries.push_back({label, cands[i].row.id,
                           render_line(cands[i].row, label)});
        out.entries.push_back({std::move(cands[i].row),
                               breakdown[i].final_score, label});
    }
    out.context_pack = render_pack(entries, "");
    rc.candidate_counts.returned = static_cast<std::int64_t>(out.entries.size());
    rc.sufficiency_status = out.entries.empty() ? Sufficiency::MISSING_INFO
                                                : Sufficiency::SUFFICIENT;
    {   // projection lag:outbox 头 − 最慢 checkpoint(无消费者按 0)。
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db,
            "SELECT COALESCE((SELECT MAX(outbox_sequence) FROM bus_events),0) - "
            "COALESCE((SELECT MIN(last_dispatched_sequence) FROM consumer_checkpoints),"
            "(SELECT COALESCE(MAX(outbox_sequence),0) FROM bus_events))",
            -1, &raw, nullptr) == SQLITE_OK) {
            StmtHandle h(raw);
            if (sqlite3_step(h.get()) == SQLITE_ROW)
                rc.projection_lag_events = sqlite3_column_int64(h.get(), 0);
        }
    }
    // fire-and-forget recalled emit(既有键公式;失败仅 stderr,不上抛)。
    try {
        persistence::TransactionGuard tx(conn);
        bus::OutboxWriter w(conn);
        const auto now = std::chrono::system_clock::now();
        const std::string bucket =
            bus::compute_window_bucket("statement.recalled", now);
        for (const auto& e : out.entries) {
            bus::BusEvent ev = bus::BusEvent::make(
                q.tenant_id, e.row.id, e.row.holder_id,
                "statement.recalled", now);
            ev.idempotency_key = bus::compute_idempotency_key(
                "statement.recalled", e.row.id, e.row.id, q.query_id, bucket);
            ev.payload_json = std::string("{\"statement_id\":\"") + e.row.id +
                "\",\"querier\":\"" + q.querier + "\",\"perspective\":\"" +
                perspective + "\",\"intent\":\"" + rc.intent_name +
                "\",\"query_id\":\"" + q.query_id + "\"}";
            try {
                w.append(ev);
                rc.emitted_events.push_back(ev.event_id);
            } catch (const persistence::SqliteError& err) {
                if (err.code() != SQLITE_CONSTRAINT_UNIQUE) throw;  // 2s 窗口去重
            }
        }
        tx.commit();
    } catch (...) {
        std::fprintf(stderr, "retrieval_planner: recalled emit failed (ignored)\n");
    }
    return out;
}

}  // namespace starling::retrieval
```

> 实现提示(给执行者):`bus::BusEvent::make` 的实际工厂签名以 `include/starling/bus/bus_event.hpp` 为准——basic_retriever.cpp:360-407 是同一 emit 的现成范本,字段填法照抄它;若那边是手工填结构体而非 `make`,本文件同样手工填。`compute_window_bucket`/`compute_idempotency_key` 两个函数签名同样以 basic_retriever.cpp 的用法为权威。

- [ ] **Step 3: 失败测试 tests/cpp/test_retrieval_planner.cpp(首批 4 例)**

```cpp
// RetrievalPlanner 7 步管线(13_retrieval.md)。fixtures 直接 SQL 写
// statements(模式照 test_common_ground_read.cpp);StubEmbeddingAdapter
// 走真语义路径零网络。
#include "starling/retrieval/retrieval_planner.hpp"

#include "starling/embedding/embedding_adapter.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/vector/vector_index.hpp"

#include <gtest/gtest.h>

namespace starling::retrieval {

namespace {

constexpr const char* kNow = "2026-06-12T10:00:00Z";

std::unique_ptr<persistence::SqliteAdapter> make_adapter() {
    auto a = persistence::SqliteAdapter::open(":memory:");
    persistence::MigrationRunner(a->connection().raw()).migrate_to_latest();
    return a;
}

void insert_statement(persistence::Connection& conn, const char* id,
                      const char* holder, const char* subject,
                      const char* predicate, const char* object,
                      const char* state = "consolidated",
                      double salience = 0.5,
                      const char* observed = "2026-06-10T00:00:00Z") {
    char sql[1024];
    std::snprintf(sql, sizeof(sql),
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
        "subject_kind,subject_id,predicate,object_kind,object_value,"
        "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
        "confidence,observed_at,salience,affect_json,activation,last_accessed,"
        "provenance,evidence_json,consolidation_state,review_status,"
        "nesting_depth,created_at,updated_at) VALUES("
        "'%s','default','%s','FIRST_PERSON','cognizer','%s','%s','str','%s',"
        "'h-%s','v1','KNOWS','POS',0.9,'%s',%f,'{}',0.0,'%s','user_input',"
        "'[{\"engram_id\":\"eng-%s\"}]','%s','approved',0,'%s','%s')",
        id, holder, subject, predicate, object, id, observed, salience,
        observed, id, state, observed, observed);
    char* err = nullptr;
    ASSERT_EQ(sqlite3_exec(conn.raw(), sql, nullptr, nullptr, &err), SQLITE_OK)
        << (err ? err : "");
}

struct Rig {
    std::unique_ptr<persistence::SqliteAdapter> a = make_adapter();
    embedding::StubEmbeddingAdapter emb{8};
    vector::SqliteBlobVectorIndex idx;
    SemanticRetriever semantic{*a, emb, idx};
    RetrievalPlanner planner{*a, semantic};

    PlannerQuery q(QueryIntent intent) {
        PlannerQuery p;
        p.tenant_id = "default"; p.querier = "cog-self";
        p.intent = intent; p.as_of_iso8601 = kNow;
        p.trace_id = "tr-1"; p.query_id = "qy-1";
        return p;
    }
};

}  // namespace

TEST(RetrievalPlanner, FactLookupSevenStepsAndReceipt) {
    Rig rig;
    insert_statement(rig.a->connection(), "s1", "cog-self", "Bob",
                     "responsible_for", "auth");
    auto q = rig.q(QueryIntent::FACT_LOOKUP);
    q.subject_id = "Bob"; q.predicate = "responsible_for";
    const auto r = rig.planner.run(q);
    ASSERT_FALSE(r.abstained);
    ASSERT_EQ(r.entries.size(), 1u);
    EXPECT_EQ(r.entries[0].row.id, "s1");
    EXPECT_EQ(r.entries[0].label, ContextPackLabel::FACT);
    // 7 步各留痕。
    ASSERT_EQ(r.receipt.plan_steps.size(), 7u);
    EXPECT_EQ(r.receipt.plan_steps[0].step, "parse");
    EXPECT_EQ(r.receipt.plan_steps[6].step, "abstain");
    EXPECT_EQ(r.receipt.intent_name, "FACT_LOOKUP");
    EXPECT_EQ(r.receipt.sufficiency_status, Sufficiency::SUFFICIENT);
    EXPECT_FALSE(r.receipt.scope_plan.steps.empty());
    EXPECT_FALSE(r.receipt.score_breakdown.empty());
    EXPECT_NE(r.context_pack.find("[FACT]"), std::string::npos);
    // 中心化 emit:每条返回行一条 recalled。
    EXPECT_EQ(r.receipt.emitted_events.size(), 1u);
}

TEST(RetrievalPlanner, AbstainsOnEmptyWithLowScore) {
    Rig rig;
    auto q = rig.q(QueryIntent::FACT_LOOKUP);
    q.subject_id = "Nobody"; q.predicate = "responsible_for";
    const auto r = rig.planner.run(q);
    EXPECT_TRUE(r.abstained);
    EXPECT_EQ(r.receipt.abstention_reason, "low_score");
    EXPECT_EQ(r.receipt.sufficiency_status, Sufficiency::ABSTAINED);
    EXPECT_NE(r.context_pack.find("[ABSTAIN]"), std::string::npos);
    EXPECT_TRUE(r.receipt.emitted_events.empty());   // 拒答不发事件
}

TEST(RetrievalPlanner, BeliefOfOtherUsesTargetHolder) {
    Rig rig;
    insert_statement(rig.a->connection(), "s-alice", "Alice", "Bob",
                     "responsible_for", "deploy");
    auto q = rig.q(QueryIntent::BELIEF_OF_OTHER);
    q.target = "Alice";
    const auto r = rig.planner.run(q);
    ASSERT_FALSE(r.abstained);
    ASSERT_EQ(r.entries.size(), 1u);
    EXPECT_EQ(r.entries[0].row.holder_id, "Alice");
    // 他者视角 + 单证据 → HEARSAY 标签(分类器联动)。
    EXPECT_EQ(r.entries[0].label, ContextPackLabel::HEARSAY);
}

TEST(RetrievalPlanner, HistoryFollowsSupersedesChain) {
    Rig rig;
    auto& conn = rig.a->connection();
    insert_statement(conn, "old", "cog-self", "Bob", "responsible_for", "auth",
                     "archived", 0.4, "2026-05-01T00:00:00Z");
    insert_statement(conn, "new", "cog-self", "Bob", "responsible_for", "deploy",
                     "consolidated", 0.6, "2026-06-01T00:00:00Z");
    char* err = nullptr;
    ASSERT_EQ(sqlite3_exec(conn.raw(),
        "INSERT INTO statement_edges(id,tenant_id,src_id,dst_id,edge_kind,"
        "weight,created_at) VALUES('e1','default','new','old','supersedes',"
        "1.0,'2026-06-01T00:00:00Z')", nullptr, nullptr, &err), SQLITE_OK)
        << (err ? err : "");
    auto q = rig.q(QueryIntent::HISTORY);
    q.subject_id = "Bob"; q.predicate = "responsible_for"; q.k = 10;
    const auto r = rig.planner.run(q);
    ASSERT_FALSE(r.abstained);
    EXPECT_EQ(r.entries.size(), 2u);   // 主路时间线 + supersedes 链补全
}

}  // namespace starling::retrieval
```

> fixtures 注意:`statements` 的 NOT NULL 列以 migration 实表为准——执行者先 `sqlite3 <tmp> "PRAGMA table_info(statements)"` 核对 INSERT 列单;若有本 plan 未列的 NOT NULL 无默认列(如 `event_time_start` 可空、`derived_depth` 默认 0),补默认值即可,断言不变。

- [ ] **Step 4: CMake 登记、构建、4 例全绿**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling && PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build 2>&1 | tail -2
./build/tests/cpp/starling_tests --gtest_filter='RetrievalPlanner.*' 2>&1 | tail -3
```
Expected: `[  PASSED  ] 4 tests.`

- [ ] **Step 5: 全量 ctest 防回归(536 + 新增全绿)**

Run: `cd /Users/jaredguo-mini/develop/memory/starling && PATH="$PWD/.venv/bin:$PATH" ctest --test-dir build 2>&1 | tail -2`
Expected: `100% tests passed`

- [ ] **Step 6: Commit**

```bash
cd /Users/jaredguo-mini/develop/memory/starling
git add include/starling/retrieval/retrieval_planner.hpp src/retrieval/retrieval_planner.cpp tests/cpp/test_retrieval_planner.cpp CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -F - <<'EOF'
feat(P3.a1): RetrievalPlanner 7 步管线 — parse/mask/plan/fetch/fuse/ground/abstain

核心三路(FACT_LOOKUP/BELIEF_OF_OTHER/HISTORY+supersedes 链);perspective
mask 先于 rerank(spec :107 位序硬约束);progressive 早停记 skipped_scopes;
中心化 recalled emit(既有幂等键公式,拒答零事件);receipt 全程留痕。

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
```

---

### Task 7: 其余六条 intent 路径 + 多 holder 隔离契约

**Files:**
- Modify: `src/retrieval/retrieval_planner.cpp`(switch 的 default 分支拆成六路)
- Test: `tests/cpp/test_retrieval_planner.cpp`(追加 6 例)

路径设计(Intent→Path 映射落地;数据源全部已存在):

| Intent | statement_main WHERE 变化 | 附加源 |
|---|---|---|
| META_BELIEF | `holder_id=?querier AND nesting_depth>=1`(text/subject 提示可选) | 无(嵌套行自含链) |
| COMMITMENT_DUE | `id IN (SELECT stmt_id FROM commitments WHERE tenant_id=? AND state IN ('ACTIVE','created'))` | 无 |
| PREFERENCE | `predicate='prefers' AND holder_id=?(target 非空用 target,否则 querier)` | 无 |
| NORM_LOOKUP | `predicate IN ('forbids','requires')` | 无 |
| COMMON_GROUND | `id IN (grounded cg statement_ids for (querier,target))`(cg 集已在 ground 步预查——本路把它提前到 fetch) | 无 |
| ABSTAIN_CHECK | FACT_LOOKUP 全路 + exhaustive(不早停)| semantic_index 必跑 |

多 holder 隔离:每个 `RetrievalScopeStep.holder_scope` 单一 holder 且写 `filters`(Task 6 已留 push_filter);新增**混合过滤拒绝**——`PlannerQuery` 加 `global_holder_filter`(默认空);非空且与任一 step.holder_scope 不一致 → 不执行,receipt `abstention_reason="invalid_scope_filter_mix"`、`sufficiency=ABSTAINED`(spec §filter 混合形式拒绝规则)。

- [ ] **Step 1: 追加 6 个失败测试(test_retrieval_planner.cpp 末尾)**

```cpp
TEST(RetrievalPlanner, CommitmentDueReturnsTodoLabel) {
    Rig rig;
    auto& conn = rig.a->connection();
    insert_statement(conn, "cmt", "cog-self", "cog-self", "promises", "ship Friday");
    char* err = nullptr;
    ASSERT_EQ(sqlite3_exec(conn.raw(),
        "INSERT INTO commitments(tenant_id,stmt_id,state,broken_count,deadline,"
        "created_at,updated_at) VALUES('default','cmt','ACTIVE',0,"
        "'2026-06-13T00:00:00Z','2026-06-10T00:00:00Z','2026-06-10T00:00:00Z')",
        nullptr, nullptr, &err), SQLITE_OK) << (err ? err : "");
    const auto r = rig.planner.run(rig.q(QueryIntent::COMMITMENT_DUE));
    ASSERT_FALSE(r.abstained);
    ASSERT_EQ(r.entries.size(), 1u);
    EXPECT_EQ(r.entries[0].label, ContextPackLabel::TODO);
    EXPECT_NE(r.context_pack.find("[TODO]"), std::string::npos);
}

TEST(RetrievalPlanner, PreferenceFiltersPredicate) {
    Rig rig;
    auto& conn = rig.a->connection();
    insert_statement(conn, "pref", "cog-self", "cog-self", "prefers", "dark roast");
    insert_statement(conn, "fact", "cog-self", "Bob", "responsible_for", "auth");
    const auto r = rig.planner.run(rig.q(QueryIntent::PREFERENCE));
    ASSERT_EQ(r.entries.size(), 1u);
    EXPECT_EQ(r.entries[0].row.predicate, "prefers");
}

TEST(RetrievalPlanner, NormLookupFiltersRegistryPredicates) {
    Rig rig;
    auto& conn = rig.a->connection();
    insert_statement(conn, "norm1", "cog-self", "team", "requires", "code review");
    insert_statement(conn, "norm2", "cog-self", "team", "forbids", "force push");
    insert_statement(conn, "fact", "cog-self", "Bob", "responsible_for", "auth");
    const auto r = rig.planner.run(rig.q(QueryIntent::NORM_LOOKUP));
    EXPECT_EQ(r.entries.size(), 2u);
}

TEST(RetrievalPlanner, CommonGroundIntentReturnsGroundedOnly) {
    Rig rig;
    auto& conn = rig.a->connection();
    insert_statement(conn, "g1", "cog-self", "team", "knows", "v2 goal");
    insert_statement(conn, "u1", "cog-self", "team", "knows", "draft idea");
    char* err = nullptr;
    ASSERT_EQ(sqlite3_exec(conn.raw(),
        "INSERT INTO common_ground(id,tenant_id,statement_id,status,parties_json,"
        "grounded_at,created_at,updated_at) VALUES"
        "('cg1','default','g1','grounded','[\"Alice\",\"cog-self\"]',"
        "'2026-06-11T00:00:00Z','2026-06-11T00:00:00Z','2026-06-11T00:00:00Z'),"
        "('cg2','default','u1','asserted_unack','[\"Alice\",\"cog-self\"]',"
        "NULL,'2026-06-11T00:00:00Z','2026-06-11T00:00:00Z')",
        nullptr, nullptr, &err), SQLITE_OK) << (err ? err : "");
    auto q = rig.q(QueryIntent::COMMON_GROUND);
    q.target = "Alice";
    const auto r = rig.planner.run(q);
    ASSERT_EQ(r.entries.size(), 1u);
    EXPECT_EQ(r.entries[0].row.id, "g1");
    EXPECT_EQ(r.entries[0].label, ContextPackLabel::COMMON);
}

TEST(RetrievalPlanner, MetaBeliefRequiresNestedRows) {
    Rig rig;
    auto& conn = rig.a->connection();
    insert_statement(conn, "flat", "cog-self", "Bob", "responsible_for", "auth");
    char* err = nullptr;
    ASSERT_EQ(sqlite3_exec(conn.raw(),
        "UPDATE statements SET nesting_depth=1 WHERE id='flat'",
        nullptr, nullptr, &err), SQLITE_OK) << (err ? err : "");
    const auto r = rig.planner.run(rig.q(QueryIntent::META_BELIEF));
    ASSERT_EQ(r.entries.size(), 1u);
    // depth>=1 且 querier 持有 → BELIEF 系标签(嵌套信念非一手事实)。
    EXPECT_NE(r.entries[0].label, ContextPackLabel::FACT);
}

TEST(RetrievalPlanner, RejectsScopeFilterMix) {
    Rig rig;
    auto q = rig.q(QueryIntent::BELIEF_OF_OTHER);
    q.target = "Alice";
    q.global_holder_filter = "cog-self";   // 全局 holder 与 step holder(Alice)冲突
    const auto r = rig.planner.run(q);
    EXPECT_TRUE(r.abstained);
    EXPECT_EQ(r.receipt.abstention_reason, "invalid_scope_filter_mix");
    EXPECT_TRUE(r.entries.empty());
}
```

- [ ] **Step 2: 实现六路 + 混合拒绝**

`PlannerQuery` 加字段(retrieval_planner.hpp,`runtime_health` 行后):
```cpp
    std::string global_holder_filter;    // 非空且与任一 step.holder_scope 不一致
                                         // → invalid_scope_filter_mix 拒绝
```
`run()` 的 plan 步 switch 替换 default,加五个 case(COMMON_GROUND 在 fetch 前预查 cg 集;META_BELIEF 在 fetch_statement_main 的 SQL 上附 `AND nesting_depth>=1`;COMMITMENT_DUE 附 `AND id IN (SELECT stmt_id FROM commitments WHERE tenant_id=?1 AND state IN ('ACTIVE','created'))`;PREFERENCE 附 `AND predicate='prefers'` 且 holder 取 `q.target.empty()?q.querier:q.target`;NORM_LOOKUP 附 `AND predicate IN ('forbids','requires')`;ABSTAIN_CHECK 复用 FACT_LOOKUP 两步但 `mode="exhaustive"` 不早停)。实现技法:给 `fetch_statement_main` 加一个 `extra_where` 字符串参数(lambda 捕获改签名),每个 case 决定 extra_where 与 holder。

plan 步开头加混合拒绝(在 add_step 之后、fetch 之前):
```cpp
    if (!q.global_holder_filter.empty()) {
        for (const auto& step : rc.scope_plan.steps) {
            if (step.holder_scope != q.global_holder_filter) {
                rc.abstention_reason = "invalid_scope_filter_mix";
                rc.sufficiency_status = Sufficiency::ABSTAINED;
                out.abstained = true;
                out.context_pack = render_pack({}, rc.abstention_reason);
                rc.plan_steps.push_back({"plan", "rejected: scope filter mix"});
                return out;
            }
        }
    }
```
(注意:此路径 plan_steps 不足 7 行——Task 6 的 `FactLookupSevenStepsAndReceipt` 钉的是正常路径,不受影响。)

COMMON_GROUND 的 fetch:不走 extra_where,直接按预查的 grounded statement_id 集逐行 `SELECT ... WHERE id=? AND tenant_id=?`(复用 kSelectCols),scope 名记 `"container_view"`。

- [ ] **Step 3: 构建 + 10 例全绿 + 全量 ctest**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling && PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build 2>&1 | tail -2
./build/tests/cpp/starling_tests --gtest_filter='RetrievalPlanner.*' 2>&1 | tail -3
PATH="$PWD/.venv/bin:$PATH" ctest --test-dir build 2>&1 | tail -2
```
Expected: `[  PASSED  ] 10 tests.` / `100% tests passed`

- [ ] **Step 4: Commit**

```bash
cd /Users/jaredguo-mini/develop/memory/starling
git add include/starling/retrieval/retrieval_planner.hpp src/retrieval/retrieval_planner.cpp tests/cpp/test_retrieval_planner.cpp
git commit -F - <<'EOF'
feat(P3.a1): 九意图路径补全 + 多 holder 隔离契约

META_BELIEF(nesting_depth>=1)/COMMITMENT_DUE(承诺联查)/PREFERENCE/
NORM_LOOKUP(注册表谓词)/COMMON_GROUND(grounded 集)/ABSTAIN_CHECK
(exhaustive);global_holder_filter 与 step holder 不一致 →
invalid_scope_filter_mix 结构化拒绝(spec §filter 混合形式拒绝规则)。

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
```

---

### Task 8: Python 绑定 + facade(Memory.query / MemoryCore.plan_query)

**Files:**
- Modify: `bindings/python/bind_05_retrieval.cpp`(新 DTO + Planner 绑定,带 GIL 释放)
- Modify: `python/starling/_memory_core.py`(`plan_query` 转发)
- Modify: `python/starling/memory.py`(`Memory.query()` 公开面)
- Test: `tests/python/test_retrieval_planner_e2e.py`(首批 3 例)

- [ ] **Step 1: bind_05 追加绑定(文件末 `bind_05_retrieval` 函数体内、BasicRetriever 绑定之后)**

```cpp
    // ----- P3.a1: RetrievalPlanner -----
    py::enum_<starling::retrieval::ContextPackLabel>(m, "ContextPackLabel")
        .value("FACT",     starling::retrieval::ContextPackLabel::FACT)
        .value("BELIEF",   starling::retrieval::ContextPackLabel::BELIEF)
        .value("HEARSAY",  starling::retrieval::ContextPackLabel::HEARSAY)
        .value("INFERRED", starling::retrieval::ContextPackLabel::INFERRED)
        .value("COMMON",   starling::retrieval::ContextPackLabel::COMMON)
        .value("TODO",     starling::retrieval::ContextPackLabel::TODO)
        .value("CONFLICT", starling::retrieval::ContextPackLabel::CONFLICT)
        .value("ABSTAIN",  starling::retrieval::ContextPackLabel::ABSTAIN)
        .export_values();

    py::class_<starling::retrieval::RetrievalScopeStep>(m, "RetrievalScopeStep")
        .def_readonly("scope",          &starling::retrieval::RetrievalScopeStep::scope)
        .def_readonly("holder_scope",   &starling::retrieval::RetrievalScopeStep::holder_scope)
        .def_readonly("filters",        &starling::retrieval::RetrievalScopeStep::filters)
        .def_readonly("max_candidates", &starling::retrieval::RetrievalScopeStep::max_candidates);

    py::class_<starling::retrieval::RetrievalScopePlan>(m, "RetrievalScopePlan")
        .def_readonly("plan_id",     &starling::retrieval::RetrievalScopePlan::plan_id)
        .def_readonly("mode",        &starling::retrieval::RetrievalScopePlan::mode)
        .def_readonly("steps",       &starling::retrieval::RetrievalScopePlan::steps)
        .def_readonly("stop_policy", &starling::retrieval::RetrievalScopePlan::stop_policy)
        .def_readonly("merge_policy",&starling::retrieval::RetrievalScopePlan::merge_policy);

    py::class_<starling::retrieval::ScoreRow>(m, "ScoreRow")
        .def_readonly("statement_id", &starling::retrieval::ScoreRow::statement_id)
        .def_readonly("base",         &starling::retrieval::ScoreRow::base)
        .def_readonly("recency",      &starling::retrieval::ScoreRow::recency)
        .def_readonly("salience",     &starling::retrieval::ScoreRow::salience)
        .def_readonly("activation",   &starling::retrieval::ScoreRow::activation)
        .def_readonly("affect_consistency",
                      &starling::retrieval::ScoreRow::affect_consistency)
        .def_readonly("temporal_penalty",
                      &starling::retrieval::ScoreRow::temporal_penalty)
        .def_readonly("final_score",  &starling::retrieval::ScoreRow::final_score);

    py::class_<starling::retrieval::RetrievalReceipt::PlanStepTrace>(m, "PlanStepTrace")
        .def_readonly("step",   &starling::retrieval::RetrievalReceipt::PlanStepTrace::step)
        .def_readonly("detail", &starling::retrieval::RetrievalReceipt::PlanStepTrace::detail);

    py::class_<starling::retrieval::RetrievalReceipt::SkippedScope>(m, "SkippedScope")
        .def_readonly("scope",  &starling::retrieval::RetrievalReceipt::SkippedScope::scope)
        .def_readonly("reason", &starling::retrieval::RetrievalReceipt::SkippedScope::reason);

    // RetrievalReceipt 既有 class_ 上追加新字段(在上方原 receipt 绑定处直接
    // 续 .def_readonly——执行时合并到那一个 class_ 链):
    //   querier / perspective / intent_name / runtime_health / scope_plan /
    //   plan_steps / skipped_scopes / stop_reason / scopes_searched /
    //   score_breakdown / degraded_paths(name 同结构再绑)/ abstention_reason /
    //   emitted_events / projection_lag_events
    // DegradedPath:
    py::class_<starling::retrieval::RetrievalReceipt::DegradedPath>(m, "DegradedPathInfo")
        .def_readonly("path",     &starling::retrieval::RetrievalReceipt::DegradedPath::path)
        .def_readonly("reason",   &starling::retrieval::RetrievalReceipt::DegradedPath::reason)
        .def_readonly("fallback", &starling::retrieval::RetrievalReceipt::DegradedPath::fallback);

    py::class_<starling::retrieval::PlannerQuery>(m, "PlannerQuery")
        .def(py::init<>())
        .def_readwrite("tenant_id",     &starling::retrieval::PlannerQuery::tenant_id)
        .def_readwrite("querier",       &starling::retrieval::PlannerQuery::querier)
        .def_readwrite("perspective",   &starling::retrieval::PlannerQuery::perspective)
        .def_readwrite("intent",        &starling::retrieval::PlannerQuery::intent)
        .def_readwrite("text",          &starling::retrieval::PlannerQuery::text)
        .def_readwrite("subject_id",    &starling::retrieval::PlannerQuery::subject_id)
        .def_readwrite("predicate",     &starling::retrieval::PlannerQuery::predicate)
        .def_readwrite("target",        &starling::retrieval::PlannerQuery::target)
        .def_readwrite("as_of_iso8601", &starling::retrieval::PlannerQuery::as_of_iso8601)
        .def_readwrite("k",             &starling::retrieval::PlannerQuery::k)
        .def_readwrite("trace_id",      &starling::retrieval::PlannerQuery::trace_id)
        .def_readwrite("query_id",      &starling::retrieval::PlannerQuery::query_id)
        .def_readwrite("runtime_health",&starling::retrieval::PlannerQuery::runtime_health)
        .def_readwrite("global_holder_filter",
                       &starling::retrieval::PlannerQuery::global_holder_filter);

    py::class_<starling::retrieval::PlannerEntryOut>(m, "PlannerEntry")
        .def_readonly("row",   &starling::retrieval::PlannerEntryOut::row)
        .def_readonly("score", &starling::retrieval::PlannerEntryOut::score)
        .def_readonly("label", &starling::retrieval::PlannerEntryOut::label);

    py::class_<starling::retrieval::PlannerResult>(m, "PlannerResult")
        .def_readonly("entries",      &starling::retrieval::PlannerResult::entries)
        .def_readonly("receipt",      &starling::retrieval::PlannerResult::receipt)
        .def_readonly("context_pack", &starling::retrieval::PlannerResult::context_pack)
        .def_readonly("abstained",    &starling::retrieval::PlannerResult::abstained);

    py::class_<starling::retrieval::RetrievalPlanner>(m, "RetrievalPlanner")
        .def(py::init<starling::persistence::SqliteAdapter&,
                      starling::retrieval::SemanticRetriever&>(),
             py::keep_alive<1, 2>(), py::keep_alive<1, 3>(),
             py::arg("adapter"), py::arg("semantic"))
        // fetch 含 embedder 网络调用 → 必须释放 GIL(GIL 纪律,test_gil_release 同族)。
        .def("run", &starling::retrieval::RetrievalPlanner::run,
             py::arg("query"), py::call_guard<py::gil_scoped_release>());
```
(头部 include 区加 `#include "starling/retrieval/retrieval_planner.hpp"`。)

- [ ] **Step 2: _memory_core.py 转发(MemoryCore 类内,recall 方法后)**

```python
    def plan_query(self, text: str = "", *, intent: str = "FACT_LOOKUP",
                   perspective: str | None = None, target: str | None = None,
                   subject: str | None = None, predicate: str | None = None,
                   k: int = 10, now=None):
        """P3.a1 检索规划:一行转发 _core.RetrievalPlanner(7 步管线居 C++)。"""
        q = _core.PlannerQuery()
        q.tenant_id = self.tenant
        q.querier = self.agent
        q.perspective = perspective or ""
        q.intent = getattr(_core.QueryIntent, intent)
        q.text = text
        q.subject_id = subject or ""
        q.predicate = predicate or ""
        q.target = target or ""
        q.as_of_iso8601 = self._now_iso(now)
        q.k = k
        q.trace_id = str(uuid.uuid4())
        q.query_id = str(uuid.uuid4())
        planner = _core.RetrievalPlanner(self.rt.adapter, self.semantic)
        return planner.run(q)
```
(`self._now_iso(now)`:若 MemoryCore 已有同语义 helper 用之;否则照 remember 的 `parse_now(now)...strftime` 写法内联。`import uuid` 已有则不重复。)

- [ ] **Step 3: memory.py 公开面(Memory 类,recall 后)**

```python
    def query(self, text: str = "", *, intent: str = "FACT_LOOKUP",
              perspective: str | None = None, target: str | None = None,
              subject: str | None = None, predicate: str | None = None,
              k: int = 10, now=None) -> dict:
        """检索规划入口(P3.a1):9 种意图 + Context Pack 8 标签 + 可审计回执。

        返回 dict:entries(row/score/label)、context_pack(LLM-ready 文本)、
        abstained、abstention_reason、receipt(完整回执对象)。
        """
        r = self._core.plan_query(text, intent=intent, perspective=perspective,
                                  target=target, subject=subject,
                                  predicate=predicate, k=k, now=now)
        return {
            "entries": [{"row": e.row, "score": e.score,
                         "label": e.label.name} for e in r.entries],
            "context_pack": r.context_pack,
            "abstained": r.abstained,
            "abstention_reason": r.receipt.abstention_reason,
            "receipt": r.receipt,
        }
```

- [ ] **Step 4: 失败测试 tests/python/test_retrieval_planner_e2e.py**

```python
"""P3.a1 检索规划 e2e:facade 全链(remember→tick→query)+ 意图分支 + 拒答。

stub LLM + 默认 stub embedder,零网络。巩固依赖 P2.o 闭环(tick 内 idle 回放)。
"""
import starling

CANNED = (
    '[{"holder":"self","holder_perspective":"FIRST_PERSON",'
    '"subject":"Bob","predicate":"responsible_for","object":"auth",'
    '"modality":"BELIEVES","polarity":"POS","nesting_depth":0}]'
)


def _mem(tmp_path):
    llm = starling.make_stub_llm(default_response=CANNED)
    return starling.Memory.open(str(tmp_path / "plan.db"), agent="alice", llm=llm)


def test_query_fact_lookup_end_to_end(tmp_path):
    mem = _mem(tmp_path)
    try:
        assert mem.remember("Bob owns the auth module").outcome == "accepted"
        mem.tick()   # 巩固 + 嵌入(P2.o)
        r = mem.query("who owns auth", intent="FACT_LOOKUP",
                      subject="Bob", predicate="responsible_for")
        assert not r["abstained"]
        assert len(r["entries"]) >= 1
        assert r["entries"][0]["label"] in ("FACT", "BELIEF")
        assert "[" in r["context_pack"]            # 带标签行
        rc = r["receipt"]
        assert [s.step for s in rc.plan_steps] == [
            "parse", "mask", "plan", "fetch", "fuse", "ground", "abstain"]
        assert rc.intent_name == "FACT_LOOKUP"
        assert rc.scope_plan.plan_id == rc.query_id
        assert len(rc.score_breakdown) >= 1
    finally:
        mem.close()


def test_query_abstains_structured(tmp_path):
    mem = _mem(tmp_path)
    try:
        r = mem.query("anything about quantum", intent="FACT_LOOKUP",
                      subject="Nobody", predicate="responsible_for")
        assert r["abstained"] is True
        assert r["abstention_reason"] == "low_score"
        assert "[ABSTAIN]" in r["context_pack"]
        assert r["receipt"].sufficiency_status == starling._core.Sufficiency.ABSTAINED
    finally:
        mem.close()


def test_query_intent_enum_exposed(tmp_path):
    from starling import _core
    names = {"FACT_LOOKUP", "BELIEF_OF_OTHER", "META_BELIEF", "HISTORY",
             "COMMITMENT_DUE", "PREFERENCE", "NORM_LOOKUP", "COMMON_GROUND",
             "ABSTAIN_CHECK"}
    assert names.issubset(set(dir(_core.QueryIntent)))
```

- [ ] **Step 5: editable 重装 + 测试通过**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling && PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --python-editable --build-dir build 2>&1 | tail -2
.venv/bin/python -m pytest tests/python/test_retrieval_planner_e2e.py -q 2>&1 | tail -3
.venv/bin/python -m pytest tests/python -q 2>&1 | tail -2
```
Expected: `3 passed` / 全量 `590 passed, 13 skipped`(587+3)

- [ ] **Step 6: Commit**

```bash
cd /Users/jaredguo-mini/develop/memory/starling
git add bindings/python/bind_05_retrieval.cpp python/starling/_memory_core.py python/starling/memory.py tests/python/test_retrieval_planner_e2e.py
git commit -F - <<'EOF'
feat(P3.a1): RetrievalPlanner 绑定(GIL 释放)+ Memory.query() facade

plan_query 一行转发(7 步管线居 C++);query() 返回 entries/context_pack/
abstained/receipt;e2e 钉 facade 全链与结构化拒答。

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
```

---

### Task 9: dashboard /api/recall intent 扩展 + 前端 interact 面板

**Files:**
- Modify: `python/starling/dashboard/engine.py`(`plan_query` 包装,持引擎锁)
- Modify: `python/starling/dashboard/routes/commands.py`(RecallBody + 分支)
- Modify: `dashboard/web/src/lib/api.ts`(RecallResponse 类型扩展)
- Modify: `dashboard/web/src/routes/interact/+page.svelte`(intent 选择器/标签 chips/拒答横幅)
- Test: `tests/python/test_dashboard_commands.py`(追加 1 例)+ 前端 `npm run check`/`npx vitest run`/`npm run build`

- [ ] **Step 1: engine.py 加包装(tick 方法后)**

```python
    def plan_query(self, text: str, *, intent: str, perspective=None,
                   target=None, k: int = 10) -> dict:
        with self._lock:
            r = self._core.plan_query(text, intent=intent,
                                      perspective=perspective, target=target, k=k)
            return {
                "results": [{"subject": e.row.subject_id,
                             "predicate": e.row.predicate,
                             "object": e.row.object_value,
                             "score": e.score, "label": e.label.name}
                            for e in r.entries],
                "context_pack": r.context_pack,
                "abstained": r.abstained,
                "abstention_reason": r.receipt.abstention_reason,
                "plan_steps": [{"step": s.step, "detail": s.detail}
                               for s in r.receipt.plan_steps],
                "scopes_searched": list(r.receipt.scopes_searched),
            }
```

- [ ] **Step 2: commands.py — RecallBody 加字段 + 路由分支**

`RecallBody` 改为:
```python
class RecallBody(BaseModel):
    query: str
    perspective: str = "first_person"
    k: int = 10
    mode: str = "semantic"
    intent: str | None = None    # 非空 → 走 RetrievalPlanner(P3.a1)
    target: str | None = None    # BELIEF_OF_OTHER / COMMON_GROUND 对方
```
`recall` 路由函数体开头加分支(原 semantic 路径不动):
```python
        if body.intent:
            payload = await to_thread.run_sync(partial(
                eng.plan_query, body.query, intent=body.intent,
                target=body.target, k=body.k))
            await _broadcast(request, "recall", {"n": len(payload["results"])})
            return payload
```

- [ ] **Step 3: pytest 追加(test_dashboard_commands.py 末尾)**

```python
def test_recall_with_intent_goes_through_planner(client):
    client.post("/api/remember", json={"text": "Bob owns auth"})
    client.post("/api/tick", json={})
    r = client.post("/api/recall", json={
        "query": "auth", "intent": "FACT_LOOKUP", "k": 5})
    assert r.status_code == 200
    body = r.json()
    assert {"results", "context_pack", "abstained", "plan_steps"} <= set(body)
    assert [s["step"] for s in body["plan_steps"]][:3] == ["parse", "mask", "plan"]
```

- [ ] **Step 4: 前端 — api.ts 类型 + interact 页**

`api.ts`:recall 响应类型旁补充(找到现 recall 类型定义处追加):
```ts
export type PlannedRecallResponse = {
	results: { subject: string; predicate: string; object: string; score: number; label: string }[];
	context_pack: string;
	abstained: boolean;
	abstention_reason: string;
	plan_steps: { step: string; detail: string }[];
	scopes_searched: string[];
};
```
`interact/+page.svelte` 召回区(现 recall 表单处):
1. 加 `<select bind:value={recallIntent}>`,选项:`语义检索(默认)` 值 `""`,以及 9 个 intent(`FACT_LOOKUP` 显示 `事实`、`BELIEF_OF_OTHER` 显示 `他者信念`、`META_BELIEF` 显示 `二阶信念`、`HISTORY` 显示 `时间线`、`COMMITMENT_DUE` 显示 `待办承诺`、`PREFERENCE` 显示 `偏好`、`NORM_LOOKUP` 显示 `规范`、`COMMON_GROUND` 显示 `共识`、`ABSTAIN_CHECK` 显示 `拒答检查`);`BELIEF_OF_OTHER`/`COMMON_GROUND` 选中时显示 `target` 输入框。
2. 提交逻辑:`recallIntent` 非空时 POST 带 `intent`(+`target`),响应按 `PlannedRecallResponse` 渲染——结果行前加 `<Chip>{label}</Chip>`(`Chip` 组件 P2.n 已有);`abstained===true` 时用 `EmptyState` 显示 `主动拒答:{abstention_reason}` 与 context_pack 文本。
3. 结果区下方可折叠 `<details>` 显示 `plan_steps`(step: detail 列表,等宽字体)。
样式遵循现页 Card/Button/Field 用法,不引新组件。

- [ ] **Step 5: 门禁(后端 + 前端四件套)**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling && .venv/bin/python -m pytest tests/python/test_dashboard_commands.py -q 2>&1 | tail -2
cd dashboard/web && npm run check 2>&1 | tail -2 && npx vitest run 2>&1 | tail -2 && npm run build 2>&1 | tail -2
```
Expected: pytest 全绿;`svelte-check found 0 errors and 0 warnings`;vitest 全绿;build ✓

- [ ] **Step 6: Commit**

```bash
cd /Users/jaredguo-mini/develop/memory/starling
git add python/starling/dashboard/engine.py python/starling/dashboard/routes/commands.py tests/python/test_dashboard_commands.py dashboard/web/src/lib/api.ts dashboard/web/src/routes/interact/+page.svelte
git commit -F - <<'EOF'
feat(P3.a1/dash): /api/recall intent 分支 + interact 意图选择器/标签/拒答

intent 非空走 RetrievalPlanner(语义模式零变化);结果行带 8 标签 Chip,
拒答渲染结构化原因 + context_pack;plan_steps 可折叠展示。

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
```

---

### Task 10: 文档同步 + 全量门 + 收尾

**Files:**
- Modify: `docs/design/subsystems_design/13_retrieval.md`(文末「实现补记」节)
- Modify: `docs/design/system_design.md`(附录 H 追加一行)
- Modify: `docs/superpowers/plans/2026-05-23-roadmap.md`(P2.n 行后登记 P3.a1 行;P3 子阶段表 P3.a 注"a1 已交付")
- Modify: 本 plan 文件头部状态改「已完成」

- [ ] **Step 1: 13_retrieval.md 文末加实现补记**

```markdown
---

## 实现补记(2026-06-12 P3.a1)

P3.a1 交付:9 种 QueryIntent、7 步管线(`src/retrieval/retrieval_planner.cpp`,
每步写 receipt.plan_steps)、Affect-aware Reranker 五因子(`affect_reranker.cpp`,
breakdown 落 receipt.score_breakdown)、Abstention Gate 四条件(`abstention.cpp`,
优先级 frontier>recanted>conflict>score,τ_recall 默认 0.25 可配)、Context Pack
8 标签(`context_pack.cpp`,优先级 TODO>CONFLICT>COMMON>INFERRED>HEARSAY>
BELIEF>FACT)、Receipt 完整字段与 RetrievalScopePlan。perspective mask:结构化
路径 SQL 下推,语义路径取回后、rerank 前按 KnowledgeFrontier 可见集遮蔽
(满足"排序之前"位序)。

本期裁剪(后续里程碑):`sanitized_query`(P3.b 随 query 清洗)、三级 RRF/bm25
融合与多源并发 latency budget(P3.c)、`ScopedWorkGate(lane=retrieval)`(P3.c
治理)、`temporal_distance_penalty` 连续距离函数(v1 为有界惩罚:过期 0.3)。
META_BELIEF 的 ToMDepthEstimator 上限调制接线归 P3.a2(估计器已存在)。
```

- [ ] **Step 2: 附录 H 行(2026-06-12 P2.o 行上方插一行)**

```markdown
| 2026-06-12 P3.a1 检索规划 | 9 种 QueryIntent + 7 步管线 + Affect-aware Reranker + Abstention Gate 四条件 + Context Pack 8 标签 + Receipt 完整字段(§13_retrieval 实现补记;sanitized_query/RRF/WorkGate 裁剪登记) |
```

- [ ] **Step 3: roadmap 登记(P2.n 行格式照抄,纪要含测试数)+ plan 状态行**

- [ ] **Step 4: 全量门(四道)**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling
PATH="$PWD/.venv/bin:$PATH" ctest --test-dir build 2>&1 | tail -2
.venv/bin/python -m pytest tests/python -q 2>&1 | tail -2
.venv/bin/python scripts/ci_static_scan.py 2>&1 | tail -1
cd dashboard/web && npm run check 2>&1 | tail -1 && npm run build 2>&1 | tail -1
```
Expected: ctest 100%(546+:536 基线 + 本期 ~10);pytest 591+(587 基线 + 4);scan OK;check 0/0;build ✓

- [ ] **Step 5: 收尾 Commit(文档)+ 向用户汇报(推送征求)**

```bash
cd /Users/jaredguo-mini/develop/memory/starling
git add docs/design/subsystems_design/13_retrieval.md docs/design/system_design.md docs/superpowers/plans/2026-05-23-roadmap.md docs/superpowers/plans/2026-06-12-p3-a1-retrieval-planner.md
git commit -F - <<'EOF'
docs(P3.a1): 13_retrieval 实现补记 + 附录 H + roadmap 登记

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
```

---

## Self-Review 记录

- **Spec coverage**:9 intent ✓(Task 1/6/7)、7 步 ✓(Task 6)、perspective 位序 ✓(Task 6 mask 先于 rerank + SQL 下推)、Reranker 公式 ✓(Task 2)、Abstention 四条件 ✓(Task 4)、Context Pack 8 标签 ✓(Task 5)、Receipt 完整字段 ✓(Task 3,sanitized_query 显式裁剪登记)、多 holder 隔离 + filter 混合拒绝 ✓(Task 7)、statement.recalled 异步契约 ✓(Task 6 中心化 emit,沿用既有幂等键)、渐进式 scope + skipped_scopes ✓(Task 6)、Intent→Path 映射 ✓(Task 6/7,KG 源 P3 后期、tom_runtime 源归 P3.a2 注记)。
- **Placeholder scan**:无 TBD/TODO;Task 6 的 BusEvent 工厂与 Task 8 receipt 续绑、Task 9 前端改动给的是"以现文件既有写法为权威"的锚定指令,属现场核对而非占位。
- **类型一致性**:`ScoreRow` 定义于 affect_reranker.hpp、receipt include 之(Task 2/3);`PlannerQuery.global_holder_filter` Task 7 增、Task 8 绑定含之;`classify_with_provenance` Task 5 定义、Task 6 调用;`Sufficiency::ABSTAINED` 既有枚举复用。

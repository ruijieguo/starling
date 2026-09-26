<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](../specs/2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](../specs/2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](../specs/2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](../specs/2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](../specs/2026-09-22-socialmem-r44-claim-attribution-design.md)。

# SocialMemBench 谓词覆盖扩展实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox ( - [ ] ) syntax for tracking.

**Goal:** 在 C++ 原生结构化声明合同中补齐 legacy mental-state 已承诺的七类谓词，保持 evidence/admission/持久化闭环，并用固定协议重新评测 SocialMemBench。

**Architecture:** PredicateCatalog 是唯一语义来源，C++ 生成目录、提示、解析和校验；Python 只调用 binding、执行评测编排和归档。新增谓词沿用现有 ExtractedStatement、semantic_claim_json 和 admission 回执，不增加第二条序列化或 Python 语义实现。

**Tech Stack:** C++17、nlohmann/json、GoogleTest、pybind11、pytest、现有 SocialMemBench 结构化评测脚本。

---

### Task 1: 保存基线并同步中文设计入口

**Files:**
- Create: build/socialmem_20260920_predicate_expansion/before/（本轮修改前相关源码快照）
- Create: docs/superpowers/specs/2026-09-20-socialmem-predicate-coverage-expansion-design.md
- Modify: docs/design/system_design.md
- Modify: docs/design/claim_contract_sync.md
- Modify: docs/design/subsystems_design/07_neocortex.md
- Modify: docs/design/subsystems_design/08_cognizer.md
- Modify: docs/design/subsystems_design/13_retrieval.md
- Modify: docs/superpowers/specs/2026-09-15-predicate-coverage-r1b-design.md
- Modify: docs/eval/2026-09-20-socialmem-structured-coverage-diagnosis.md

- [ ] **Step 1: 保存受影响源码和当前核心哈希**

运行：

~~~bash
mkdir -p build/socialmem_20260920_predicate_expansion/before
cp include/starling/extractor/claim_contract.hpp build/socialmem_20260920_predicate_expansion/before/
cp src/extractor/claim_contract.cpp build/socialmem_20260920_predicate_expansion/before/
cp src/extractor/statement_validator.cpp build/socialmem_20260920_predicate_expansion/before/
cp tests/cpp/test_claim_contract.cpp build/socialmem_20260920_predicate_expansion/before/
sha256sum build/socialmem_20260920_structured_eval_hybrid_fenced_baseline/summary.json
~~~

预期：快照存在，summary 中的 baseline 为 18/57，当前核心哈希为 60dafea16e0670212e1080c2a9bc2b80274b6b01e88f9ee6882739facb0b9ddc。

- [ ] **Step 2: 自检设计文档**

检查：

~~~bash
rg -n 'TODO|TBD|待定|占位|Python.*谓词|claim-predicate-v3|prefers|promises|responsible_for' docs/superpowers/specs/2026-09-20-socialmem-predicate-coverage-expansion-design.md
~~~

预期：没有 TODO/TBD/待定/占位；七个新增谓词、C++ 边界和 QA 归因限制均有明确描述。

- [ ] **Step 3: 同步当前设计入口**

在五个当前入口和上一轮 R1B 设计末尾追加同一中文“R2 谓词覆盖扩展（2026-09-20）”摘要，包含目录版本、七个谓词、C++ 唯一来源、Python 禁止复制、测试顺序和评测门槛。历史目录不改写。

### Task 2: 先写 C++ RED 测试

**Files:**
- Create: tests/cpp/test_predicate_coverage_expansion.cpp
- Modify: tests/cpp/CMakeLists.txt

- [ ] **Step 1: 写目录和别名失败测试**

测试：

~~~cpp
TEST(PredicateCoverageExpansion, NativeCatalogContainsLegacyMentalRelations) {
    const auto catalog = claim_predicate_catalog();
    EXPECT_EQ(catalog.version, "claim-predicate-v3");
    EXPECT_EQ(canonical_claim_predicate("wants"), "prefers");
    EXPECT_EQ(canonical_claim_predicate("commits_to"), "promises");
    EXPECT_EQ(canonical_claim_predicate("owns_area"), "responsible_for");
    EXPECT_NE(find_claim_predicate("requires"), nullptr);
}
~~~

- [ ] **Step 2: 写模态和正反例失败测试**

为 prefers/DESIRES、promises/COMMITS、doubts/DOUBTS、believes/BELIEVES、responsible_for/BELIEVES、requires/NORM_OUGHT、forbids/NORM_FORBID 准备不含 SocialMemBench 人物的英文和中文来源。断言正例保留 subject/object/topic/time；把每个候选替换为错误 modality 时断言 scope_failure 或 schema_failure。

- [ ] **Step 3: 写 admission 和存储失败测试**

构造同时含 prefers、promises 与 feels 的候选，使用 FakeLLM 的 admission 响应拒绝其中两条，断言 receipt 按规范谓词计数；再用 Extractor::persist 断言 semantic_family、predicate_catalog_version、source span 和对象原文可回读。

- [ ] **Step 4: 写兼容和提示失败测试**

断言 knows/BELIEVES 与 knows/KNOWS 都通过；抽取和准入提示包含新增目录及允许模态，不包含 Josh、Marcus、SocialMemBench、评测答案等字符串。

- [ ] **Step 5: 将测试加入 CMake 并运行 RED**

运行：

~~~bash
cmake --build build -j2 --target test_predicate_coverage_expansion
ctest --test-dir build -R PredicateCoverageExpansion --output-on-failure
~~~

预期：测试能编译但因目录版本、别名或新增谓词不存在而失败；如果测试直接通过，先修测试直到证明当前能力缺失。

### Task 3: 先写 Python RED 测试

**Files:**
- Create: tests/python/test_predicate_coverage_expansion.py

- [ ] **Step 1: 写 binding 目录一致性失败测试**

断言 _core.claim_predicate_catalog().version == "claim-predicate-v3"，七个新增谓词和三个别名可见，并与 claim_predicate_catalog_json() 完全一致。

- [ ] **Step 2: 写 Python 边界失败测试**

断言 ExtractionConfig() 默认仍关闭结构化合同；源文件和评测脚本不包含第二份新增谓词集合或 Python 语义拒绝函数。该测试只检查 binding/归档边界，不实现谓词判断。

- [ ] **Step 3: 运行 Python RED**

运行：

~~~bash
.venv/bin/python -m pytest tests/python/test_predicate_coverage_expansion.py -q
~~~

预期：版本仍为 v2 或新增谓词缺失，测试失败；确认失败来自能力而不是导入错误。

### Task 4: C++ 最小实现

**Files:**
- Modify: include/starling/extractor/claim_contract.hpp（如需接口字段保持最小）
- Modify: src/extractor/claim_contract.cpp
- Modify: src/extractor/statement_validator.cpp
- Modify: include/starling/extractor/predicate_registry.hpp（仅在 legacy 目录与 v3 目录确有漂移时同步）

- [ ] **Step 1: 扩展唯一原生 PredicateCatalog**

把版本升级为 claim-predicate-v3；按设计添加七个 PredicateSpec，别名只在 C++ 目录中声明。既有条目不删除，knows 增加 KNOWS 兼容模态但保留 BELIEVES。

- [ ] **Step 2: 让解析器和 validator 使用目录模态**

删除 statement_validator.cpp 对 decided_on/其他谓词的二分硬编码，改为查找 find_claim_predicate 并检查 allowed_modalities、allowed_polarities；保留 uncertain_about POS 专项和已有 scope guard。

- [ ] **Step 3: 更新 C++ 提示和通用例**

更新 meanings、generation_guidance 和 relation_boundaries，加入七类语义边界和模态矩阵；参考例使用 Elin、陶宁 等隔离名字，不写评测人物或答案。目录 JSON 仍由同一函数输出，抽取/准入提示自动同步。

- [ ] **Step 4: 保持旧路径和 Python 边界**

不修改 Python 谓词表；只让既有 binding 返回新增 C++ 目录。general_fact、episodic 和 legacy 默认行为不改。

- [ ] **Step 5: 运行新增 C++ 测试 GREEN**

运行：

~~~bash
cmake --build build -j2 --target test_predicate_coverage_expansion
ctest --test-dir build -R PredicateCoverageExpansion --output-on-failure
~~~

预期：新增测试全部通过；失败时只修生产代码，不放宽测试。

### Task 5: 回归和固定重放

**Files:**
- Modify: docs/eval/2026-09-20-socialmem-structured-coverage-diagnosis.md
- Create: build/socialmem_20260920_predicate_expansion/

- [ ] **Step 1: 运行相关 C++/Python 回归**

运行：

~~~bash
ctest --test-dir build -R 'ClaimContract|Structured|SourceTurn|MemoryClosure|PredicateCoverageExpansion' --output-on-failure
.venv/bin/python -m pytest tests/python/test_predicate_coverage_expansion.py tests/python/test_source_turn_receipt.py tests/python/test_socialmem_structured_eval_guard.py tests/python/test_analyze_socialmem_structured_coverage.py -q
~~~

预期：相关 C++ 和 Python 测试无失败；既有环境限制单独记录。

- [ ] **Step 2: 验证固定旧回执解析稳定**

用当前模块对 build/socialmem_20260920_structured_eval_hybrid_fenced_baseline 的 extraction 回执做离线重解析，核对旧 18 条的 predicate/object/source span 未改变；只允许目录版本字段和提示哈希出现预期的 v3 差异。

- [ ] **Step 3: 运行新固定协议评测**

在网络沙箱外运行：

~~~bash
.venv/bin/python scripts/run_socialmem_structured_eval.py run \
  --arm hybrid_fenced \
  --work build/socialmem_20260920_structured_eval_hybrid_fenced_predicate_v3
~~~

保持 qwen3.8-27b、零重试、SourceTurn 完整输入、同题目和裁判；不得复用 source_only。如 HTTP 预算、网络或提供商失败，保存原始失败状态并不把它当 QA 结果。

- [ ] **Step 4: 分层分析与中文报告**

比较 baseline 与 v3 的 7/7 scope、36/36 holder、空候选率、原生/准入拒绝、谓词分布、声明数、逐题正确率和 50,000 次网络 bootstrap。将结果写入 docs/eval/2026-09-20-socialmem-predicate-coverage-expansion.md，明确区分能力变化、诊断相关性和 QA/F1 归因。

### Task 6: 设计文档收口

**Files:**
- Modify: docs/eval/2026-09-20-socialmem-structured-coverage-diagnosis.md
- Modify: docs/design/claim_contract_sync.md
- Modify: docs/design/system_design.md
- Modify: docs/design/subsystems_design/{07_neocortex,08_cognizer,13_retrieval}.md
- Modify: docs/superpowers/specs/2026-09-15-predicate-coverage-r1b-design.md

- [ ] **Step 1: 记录实际目录、测试、模块哈希和评测状态**

补充本阶段日期、claim-predicate-v3、新测试输出、当前 _core SHA-256、评测请求数和是否完整。

- [ ] **Step 2: 更新限制和下一步**

明确：本阶段改善的是表达/诊断能力；若 QA 未达事前晋升门槛，继续保持结构化合同非生产默认，下一轮按失败分层选择提示、admission 或检索改进。

- [ ] **Step 3: 文档一致性检查**

运行：

~~~bash
rg -n 'claim-predicate-v3|prefers|promises|responsible_for|Python.*谓词|semantic_claim_contract' docs/design docs/superpowers/specs docs/eval | head -200
~~~

预期：当前入口中文描述一致，历史目录和历史评测分数未被改写。

### Task 7: 修复首次 v3 运行暴露的结构化输出协议失败

**原因证据：**首次 v3 评测 57 题中 47 题在抽取建库阶段失败；原始回执包含 `completion_truncated`、未转义 JSON 字符串和范围/时间标记缺失。失败发生在 C++ 原生解析前后，不能通过 Python 侧清洗响应解决。

**顺序：**先在本设计末尾记录问题和边界，再新增 Python 配置/评测门禁测试，最后让 `ExtractionConfig` 将 `claim_output_mode` 传递到 C++ `ValidationPolicy`，运行器使用 `JsonObject` 请求；不改变 predicate catalog、解析器或评分器。

**验收：**配置测试断言结构化 arm 使用原生 `JsonObject`、legacy arm 保持默认；相关 C++/Python 回归通过；新实验身份记录输出模式；若提供商仍返回围栏/坏 JSON，回执必须保留协议失败，不得清洗后计入 QA。

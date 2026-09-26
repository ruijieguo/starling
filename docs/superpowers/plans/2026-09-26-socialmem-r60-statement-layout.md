# SocialMemBench R6.0 声明布局一致化实施计划

<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **执行记录更正：** C++布局已实现并完成部分本机验证；任务未全部按计划验收，故未统一勾选完成。隔离构建、三holder配对探测、完整布局断言和新core准入存在偏差，详见[R6.0诊断](../../eval/2026-09-26-socialmem-r60-build-diagnosis.md)。历史记录保持，后续按R6.1计划实施。

**目标：** 在目标批次的原生 few-shot 参考示例中稳定输出声明字段顺序，使十个声明标量字段位于 `evidence` 之前，并保持值、证据内部顺序、旧模式提示和严格 schema 行为不变。

**架构：** C++ 在 `claim_contract.cpp` 内以 `nlohmann::ordered_json` 构造目标批次的私有参考示例序列化副本；共享的默认 JSON 示例和非目标模式仍走原路径。Python 不新增字段重排或语义修复，只读取已有 binding 暴露的 profile、plan 和 prompt。

**技术栈：** C++20、nlohmann/json、GoogleTest、pybind11、pytest、CMake。

**规格：** `docs/superpowers/specs/2026-09-26-socialmem-r60-statement-layout-design.md`

## 全局约束

- 设计、计划和执行报告全部使用中文。
- 核心逻辑只放 C++；Python 仅负责 binding、编排和统计。
- `claim_batch_target_units=false` 的历史提示、plan、纠错提示和回执保持逐字兼容。
- 目标批次严格使用 schema v2，不在解析器中搬移、补全或猜测错层字段。
- 不修改 admission、范围/时间、实体或谓词语义，不删除失败候选的原始回执和费用。
- 不覆盖 R5.9 frozen core 或旧评测目录；候选 core、探测和八库重建使用隔离目录。

---

### 任务 1：补齐中文实施记录与状态入口

**文件：**
- 修改：`docs/superpowers/specs/2026-09-26-socialmem-r60-statement-layout-design.md`
- 修改：受 R6.0 状态入口索引引用的中文状态文档（仅更新“未实现/已验证”状态）
- 创建：`build/socialmem_20260926_r59_work/r60-implementation-plan-review.md`

**接口：**
- 输入：R6.0 设计、R5.9 handoff、现有 target-units 测试。
- 输出：实现前状态证据、候选 profile 名称 `target_units_statement_first_v1` 和测试命令清单。

- [ ] **步骤 1：** 记录实现边界、旧 profile 与新 profile 的身份差异，以及“真实评测未开始”的限制。
- [ ] **步骤 2：** 用 `sha256` 固化设计、计划和预审记录，保存到构建工作目录。
- [ ] **步骤 3：** 检查文档无英文设计正文、无 TODO/TBD 和无与 R5.9 健康状态矛盾的断言。

### 任务 2：为原生声明布局写 RED 用例

**文件：**
- 修改：`tests/cpp/test_claim_batch_target_units.cpp`
- 修改：`tests/python/test_claim_batch_target_units.py`
- 创建：`build/socialmem_20260926_r59_work/r60-layout-red.log`

**接口：**
- 输入：现有 `claim_extraction_batch_prompt`、`claim_extraction_batch_plan` 和 C++ binding。
- 输出：能观察实际 prompt 字节顺序和值等价性的失败测试。

- [ ] **步骤 1：** 在 C++ 测试中从 `REFERENCE_EXAMPLES_JSON` 读取原生文本，使用保序解析器确认 15 个示例的 statement 键序为 `holder, holder_perspective, subject, subject_kind, predicate, object, modality, polarity, nesting_depth, confidence, evidence`。
- [ ] **步骤 2：** 在同一测试中把新目标提示与 `claim_batch_target_units=false` 的 frozen reference 做差量比较，只允许参考示例 statement 键序变化；比较 statement 值、evidence 内部键序、示例数量和示例数组顺序。
- [ ] **步骤 3：** 断言首次和纠错提示的参考示例字节完全相同；断言 profile 为 `target_units_statement_first_v1`，历史 false 模式不出现该字段。
- [ ] **步骤 4：** 增加错层候选（声明字段移入 evidence、同时存在两层）的严格 schema 失败和无 semantic_claim 写入断言；同时覆盖合法声明、后批失败、general_fact/episodic 路径。
- [ ] **步骤 5：** 在 Python 测试中只调用已有 binding 验证 profile、plan 和 prompt，不实现任何字段搬移逻辑。
- [ ] **步骤 6：** 运行聚焦 C++/Python 测试并确认它们因新顺序/profile 尚未实现而失败；保存完整失败输出，不修改生产代码迎合测试。

### 任务 3：在 C++ 中实现保序目标提示

**文件：**
- 修改：`src/extractor/claim_contract.cpp`
- 修改：`src/extractor/extractor.cpp`
- 修改：`tests/cpp/test_claim_batch_target_units.cpp`（仅在实现后补齐必要的断言消息）

**接口：**
- 消费：任务 2 的失败断言。
- 产出：目标批次使用保序参考示例、plan/receipt 使用新 profile，旧模式完全复用旧 JSON 序列化入口。

- [ ] **步骤 1：** 新增只读的目标批次 profile 常量和有序参考示例序列化辅助函数；每个 statement 按十个标量字段后接 `evidence` 的顺序逐项复制，evidence 内部键顺序保持不变。
- [ ] **步骤 2：** 输出后用严格 JSON 解析和值等价检查，确保字段集合、类型、数量和内容未改变；失败时抛出原生错误而不是静默修复。
- [ ] **步骤 3：** 让目标模式首次与纠错路径共享同一有序参考示例入口；SOURCE_DATA_JSON、批次索引、目录、边界、模板和末端骨架保持原字节。
- [ ] **步骤 4：** 将 plan 与 receipt 的 profile 更新为 `target_units_statement_first_v1`，并让完整性校验只接受新 profile 的同一计划/提示/hash 组合。
- [ ] **步骤 5：** 保持 false/未分批分支原样，禁止 Python binding 新增重排逻辑或参数。
- [ ] **步骤 6：** 运行任务 2 的聚焦测试，确认由 RED 转为 GREEN。

### 任务 4：构建候选 core 并完成本机回归

**文件：**
- 创建：`build/socialmem_20260926_r60_work/` 下的隔离构建、日志和清单
- 修改：`docs/superpowers/specs/2026-09-26-socialmem-r60-statement-layout-design.md`
- 创建：`build/socialmem_20260926_r60_work/evaluation-implementation-report.md`

**接口：**
- 输入：任务 3 的 C++ 变更。
- 输出：候选 core SHA、CTest/pytest 结果、prompt 差量证据和独立 binding 检查。

- [ ] **步骤 1：** 在全新构建目录编译 C++ 与 Python binding，不覆盖 R5.9 frozen core。
- [ ] **步骤 2：** 运行目标测试、全部 CTest 和相关 Python 回归；记录退出码、通过数、失败数和耗时。
- [ ] **步骤 3：** 运行无 provider 的原生独立检查，验证合法输出可消费、篡改 profile/source/target/prompt/hash 被拒绝、错层候选不写入。
- [ ] **步骤 4：** 保存候选 core/source/profile/prompt/hash 的 SHA-256，并由独立脚本复核差量仅落在参考示例 statement 键序。
- [ ] **步骤 5：** 若任一回归失败，先恢复 RED→GREEN 证据并修正 C++；未通过前不得调用 provider。

### 任务 5：冻结真实探测与八库重建门禁

**文件：**
- 创建：`docs/superpowers/specs/2026-09-26-socialmem-r60-real-probe-design.md`
- 创建：`build/socialmem_20260926_r60_work/` 下的真实探测日志、原始回执和 manifest
- 修改：相关中文评测状态入口及 R6.0 执行报告

**接口：**
- 输入：任务 4 的候选 core 和独立检查结果。
- 输出：旧/新 profile 的完整 holder 交错探测结论；仅在健康且有来源 admitted claim 时放行八库 fresh 重建。

- [ ] **步骤 1：** 冻结 Tomas、Mum、Kwame 的完整来源、批次清单、旧/新 core、交错次序、预算和放行门槛；不复用旧失败答案。
- [ ] **步骤 2：** 对每个任务记录每个批次的请求、纠错、schema、admission、来源保留和费用，区分技术健康、语义保留和消费。
- [ ] **步骤 3：** 若探测通过，创建全新八库目录，用统一新 core 重建 8/8；若失败，保存阴性结果并停止，不叠加无界重试。
- [ ] **步骤 4：** 8/8 健康后运行 266 检索和 532 fresh QA，才生成 133 题 baseline；按来源缺失、语义遗漏、检索选择和回答错误分类分析。
- [ ] **步骤 5：** 把真实 provider 结果、历史 R5.4/R5.9 结果、fixture 测试和静态诊断分开汇报，不把协议健康或空数组当成准确率提升。

## 验收清单

- [ ] 中文设计、实施计划、执行报告和状态入口同步，SHA 与链接校验通过。
- [ ] RED 日志证明测试在实现前按预期失败；GREEN 日志证明实现后通过。
- [ ] 目标模式 15 个参考示例的声明键序统一，值与 evidence 内部顺序不变。
- [ ] false/未分批历史 prompt SHA 不变；新 profile 不能被旧 profile 产物伪装。
- [ ] 严格 schema 继续拒绝错层候选，失败回执和费用完整保留。
- [ ] 候选 core 的 CTest、Python 回归和独立 binding 检查均有新鲜退出码证据。
- [ ] 只有 8/8 fresh build 健康后才报告 SocialMemBench baseline；没有 baseline 时明确写“暂无分数”。

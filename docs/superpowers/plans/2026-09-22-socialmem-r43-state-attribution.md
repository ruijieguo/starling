<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

# SocialMemBench R4.3 事件状态与信念归属实施计划

> 本计划按“中文设计 → RED 测试 → C++ 实现 → 离线验证 → 真实评测”执行；每一步都保留旧策略和封存目录。

**目标：** 在 C++ 来源选择和回答提示中补齐事件状态链、信念归属和逐成员覆盖能力，降低原生回答截断，并在固定 SocialMemBench 57 题协议下验证是否有可重复的准确率提升。

**架构：** `evidence_profile_v5` 在 `source_retriever.cpp` 中复用 v4 的授权候选和主体/support 规则，新增状态、归属、成员三条受限车道；`compact_grounded_memory_answer_prompt` 在 C++ 中构造短输出协议。Python binding 只传递策略名、调用原生函数和归档结果。

**技术栈：** C++17、nlohmann/json、GoogleTest、pybind11、pytest、现有 SocialMemBench 冻结运行器、DashScope `qwen3.8-27b`。

## 任务一：文档与冻结边界

**文件：**

- 新增：`docs/superpowers/specs/2026-09-22-socialmem-r43-state-attribution-design.md`
- 新增：本计划文件
- 修改：320 份中文设计入口的首行导航
- 新增：`docs/eval/2026-09-22-socialmem-r43-state-attribution.md`（评测完成后）

- [x] 写入 R4.3 设计，明确字段、角色、Python/C++ 边界和回滚条件。
- [x] 运行 `rg -n 'TODO|TBD|待定|占位' docs/superpowers/specs/2026-09-22-socialmem-r43-state-attribution-design.md`，预期无占位语句。
- [x] 在所有已有 R4.2 导航入口加入 R4.3 设计链接，但不修改历史正文和封存目录。

## 任务二：C++ RED 测试

**文件：** `tests/cpp/test_source_retriever.cpp`、`tests/cpp/test_evidence_answer.cpp`、`tests/cpp/CMakeLists.txt`

- [ ] 添加 v5 选择夹具：变化题缺少主体角色时断言 `state_chain_missing`，完整状态链按时间顺序选择三条。
- [ ] 添加归属夹具：信念持有者和被谈论者分别出现时断言 `belief_attribution_selected`，speaker 不匹配的候选不计入归属。
- [ ] 添加全体成员夹具：低相关 holder 仍获得一条来源；没有授权来源的 holder 出现在 `member_missing`。
- [ ] 添加策略校验回归：v2/v3/v4 输出保持相同，非法策略仍抛出异常。
- [ ] 添加短回答提示 RED：断言 binding 前不存在 `compact_grounded_memory_answer_prompt`，并记录失败原因是接口缺失而非测试错误。
- [ ] 运行 `cmake --build build -j2 --target test_source_retriever test_evidence_answer` 与对应 `ctest`，确认 RED。

## 任务三：Python RED 合同

**文件：** `tests/python/test_socialmem_r43.py`

- [ ] 断言 `_core` 暴露 `compact_grounded_memory_answer_prompt`，R4.3 配置只传递 `evidence_profile_v5` 和 `grounded_memory_v2`。
- [ ] 检查 `scripts/` 与 binding 中没有第二份事件、归属或成员关键词判定表；Python 只读取原生 diagnostics。
- [ ] 运行 `.venv/bin/python -m pytest tests/python/test_socialmem_r43.py -q`，在实现前保存预期失败。

## 任务四：C++ GREEN 实现

**文件：**

- 修改：`include/starling/retrieval/source_retriever.hpp`
- 修改：`src/retrieval/source_retriever.cpp`
- 修改：`include/starling/retrieval/evidence_answer.hpp`
- 修改：`src/retrieval/evidence_answer.cpp`
- 修改：`bindings/python/bind_05_retrieval.cpp`
- 修改：`tests/cpp/test_source_retriever.cpp`
- 修改：`tests/cpp/test_evidence_answer.cpp`

- [ ] 在 v5 校验中加入策略名，旧策略分支保持逐字行为。
- [ ] 在 C++ Source 结构中增加候选角色标记和确定性词法分类；角色只来源于授权 source/ref 或结构化 claim metadata。
- [ ] 实现三条车道、缺口诊断、字节预算和 rendered 对齐；不新增网络请求。
- [ ] 实现 `compact_grounded_memory_answer_prompt`，复用 packet 校验并限制输出长度指令。
- [ ] 运行新 C++ 测试，确认 RED→GREEN；再运行 `ctest --test-dir build --output-on-failure`。

## 任务五：离线冻结验证

**文件：** 新增 `scripts/run_socialmem_r43.py`、`tests/python/test_socialmem_r43.py`

- [ ] 复制 R3.5 父输入到独立目录，写入 v5/v2 配置和核心 hash；禁止复用 R4.2 目录。
- [ ] 使用替代网络适配器完成 57 次检索、114 个终态，核验角色诊断、账本和 completion seal；网络请求必须为零。
- [ ] 运行全部 R4.0–R4.3 Python 合同和冻结目录验证。

## 任务六：真实评测与报告

- [ ] 先 `prepare/check`，再在获得完整配置身份后发起 DashScope 请求；零重试、600 HTTP、`qwen3.8-27b`。
- [x] 真实目录通过 `verify`，保存精确来源、角色缺口、失败、token、配对 bootstrap 和 completion seal。
- [x] 编写中文 R4.3 报告；结果未达到门槛，生产继续回滚到 v4/v1。
- [x] 更新 320 份设计导航、R4.3 设计状态和本计划复选框。


## R4.3 实评结果（2026-09-22）

- [x] 检索 17/57，原生回答 19/57；相对 R4.2 两臂 0 净变化。
- [x] 547/600 HTTP，0 技术失败，账本无未决请求。
- [x] 评测报告与独立诊断已写入；`promoted=false`。
- [ ] v5 结构化 claim metadata 兑现：推迟到 R4.4/v6，先完成中文设计与 RED 测试。

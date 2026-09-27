<!-- regression-boundary-20260927:start -->
> **回归验收边界（2026-09-27）**：日常回归与固定历史评测回放分开执行；默认跳过项须显式报告，历史封存、SHA 和失败断言保持有效。部分无有效提升产物已退役，旧文中的回放链接不保证仍可用。当前执行规则见[测试说明](../../../tests/README.md)和[中文设计](2026-09-27-python-regression-boundary-design.md)；这不产生新的准确率结论，产品核心仍由 C++ 实现。
<!-- regression-boundary-20260927:end -->

<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

# SocialMemBench R5.2 同库 v6/v7 QA 对照设计

日期：2026-09-25

状态：在 R5.1 上执行的真实 QA 诊断设计。默认策略继续保持不变。

## 1. 目标

R5.1 已在同一 `runs/*/frozen.db` 快照上证明 v6/v7 的 source/block 发生了真实变化。R5.2 让这两套冻结上下文进入同一套 qwen3.8-27B 回答与裁判协议，回答“检索变化是否转化为 QA 准确率变化”。

## 2. 对照臂与 provenance

- v6：来自 R5.1 的 57 个新生成上下文；不重新抽取、不重新嵌入。
- v7：来自 R5.0 retry4 的 57 个已封存上下文；R5.1 已逐题验证 source_refs、block 和 runs 数据库哈希均无漂移。
- legacy：使用冻结 runner 的原始 `answer_prompt`，配置为 qwen3.8-27B、`answer_max_tokens=512`、不启用 thinking、无重试。
- native：使用冻结 C++ `grounded_memory_v1` 提示，其他回答和裁判配置相同。
- v7 的 legacy/native answer/judge 回执复用 retry4 已封存结果，并在发送 v6 请求前重新校验 prompt、模型配置和题目身份；v6 只发送两套 answer 请求以及自由题的 judge 请求。

复用 v7 回执的原因是避免同一上下文再次产生回答调用成本。它保持回答配置和评分协议一致，但回答服务时间与生成随机性仍可能不同；复用结果只能作为成本受限的诊断点，不能单独解释检索因果或晋升。需要正式单变量结论时，必须使用本计划的 `fresh_v7` 模式，在同一进程内重新生成 v6/v7 两臂 answer/judge。

## 3. 执行合同

1. 输入只能是 R5.1 `comparison.json`、v6/v7 recall 回执、R5.0 retry4 `summary.json` 和 `native-answer/` 回执；任何上下文或提示哈希不匹配都在模型调用前失败。`fresh_v7` 模式仍复用 v7 上下文，但不复用回答回执。
2. Python 只编排冻结 C++ binding、发送请求、归档回执和统计；答案提示路由、证据渲染和评分协议使用冻结 runner/core，不在 Python 重写。
3. 每个 v6/policy/item 使用持久请求账本预留最多 2 次请求；实际 answer/judge 尝试数结算，未知失败保持 `charged_upper`，禁止重试未完成任务。
4. 选择题由冻结 `eval_longmemeval._parse_option_index` 解析；自由题由冻结 `eval_judge_audit._judge_prompt` 和 `_parse_judge_verdict` 裁判。技术失败计零并单列。
5. 保存完整 prompt、answer/judge native receipt、token usage、HTTP attempt、状态和上下文 SHA-256；不覆盖 R5.0/R5.1 目录。

## 4. 统计

分别对 legacy/native 报告 v6/v7 正确数、技术失败、共同正常子集、四格配对转移、按 network 聚类 bootstrap、answer/judge 请求和 token。主差值定义为 `v7 - v6`；题目和 network 分母固定为 57 题/6 network。

bootstrap 只反映 network 重采样，不覆盖同题重复生成、裁判随机性、服务端时间变化和开发集选择偏差。晋升沿用既定门槛：至少一臂共同正常子集净增 5 题，且 network 95% 区间下界大于 0；否则 v7 仍为实验策略。

## 5. 默认策略

R5.2 只产生诊断报告，不修改 `source_strategy` 默认值，不把 v6/v7 任一结果外推为全量 SocialMemBench 或生产质量。

## 6. Fresh 双臂实施与结果

为消除“v7 复用历史回答、v6 重新请求”的主要混杂，runner 增加 `--fresh-v7` 模式。该模式在同一进程内为每个 policy 复用同一组 native adapter，依次执行 v6、v7 的 answer/judge，请求账本和提示/解析协议保持一致；默认模式仍只生成 v6 并复用已封存 v7 回执。

2026-09-25 fresh 结果如下：

| policy | v6 | v7 | v7−v6 | bootstrap 95% 区间 |
|---|---:|---:|---:|---:|
| legacy | 22/57 | 12/57 | −10 题（−17.54 pp） | [−25.86, −8.51] pp |
| grounded_memory_v1 | 24/57 | 11/57 | −13 题（−22.81 pp） | [−30.65, −13.46] pp |

四臂共 228 个终态任务、400 次实际请求，`reserved=0`、`charged_upper=0`；逐题 prompt/context 核验为 4×57/57。两种 policy 均无 v7 改善题，v7 不满足晋升门槛，默认策略继续关闭。完整数字和技术失败分层见 [R5.2 fresh QA 报告](../../eval/2026-09-25-socialmem-r52-v6-v7-qa.md)。


## 7. 后续设计入口

R5.2 的退化诊断已转入 R5.3：v7 的来源与结构化声明争用同一 k 名额，导致 SOURCE 数量从 10 降为 7。后续不修改本报告的历史结果，按“来源主预算、结构化声明 sidecar、C++ 唯一选择逻辑”的方案继续。详见 [R5.3 来源预算与结构化声明 sidecar 设计](2026-09-25-socialmem-r53-source-sidecar-design.md)。

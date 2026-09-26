# SocialMemBench R3.1 抽取容量评测报告

日期：2026-09-20。模型：DashScope `qwen3.8-27b`。臂：`hybrid_fenced`。题目：固定 57 题、6 个网络、7 个 scope。R3.1 唯一变量是结构化抽取 `extract_max_tokens=8192`；R2.3 对照为 4096。回答上限 512、裁判上限 64、超时 120000、零重试、题目、评分和 C++ 语义均保持不变。

## 1. 执行状态

首次在默认沙箱运行时，28 次抽取请求全部出现 `transport_error: Couldn't resolve host name`，得到 0/57；该目录仅作为环境 DNS 失败证据，不计入容量对照。升级权限验证 DashScope 端点返回 HTTP 401，证明端点可达但未提供请求认证头；随后在已授权网络环境重新运行，结果目录为：

`build/socialmem_20260920_structured_eval_hybrid_fenced_predicate_v3_r31_extract8192_net`

该目录在网络运行前完成 `prepare` 和 `check`，固定题目、来源快照、配置和 core 指纹均通过。网络运行完成 57/57 题，未发生写入失败、SQLite/WAL 失败或预算耗尽。运行后有 4 个 scope 抽取失败，因此严格结构化覆盖门禁按设计拒绝把该目录标记为完整结构化快照；逐题回执、失败 scope、账本和分析文件均保留。

## 2. 主结果与 R2.3 对照

| 运行 | 正确/题数 | 主准确率 | 技术失败 | 成功分母 | 成功子集准确率 | 完成 scope | holder |
|---|---:|---:|---:|---:|---:|---:|---:|
| R2.3，4096 | 7/57 | 12.28% | 26 | 31 | 22.58% | 4/7 | 19/36 |
| R3.1，8192 | 6/57 | 10.53% | 30 | 27 | 22.22% | 3/7 | 15/36 |

R3.1 的 3 个完成 scope 为 `grp_2b3c4d5e`、`grp_3c4d5e6f`、`grp_4d5e6f7a`，覆盖 27 题；失败 scope 为 `grp_0d1e2f3a` 的两个评测范围、`grp_9c0d1e2f` 和 `grp_a3b4c5d6`，影响 30 题。失败 holder 为 Josh（两个 scope）、Luca（6 题 scope）和 Otto（18 题 scope）。

R3.1 与 R2.3 逐题交集为 57 题。两轮共同 `ok` 的 27 题中，转移为“对→对”5 题、“对→错”1 题、“错→对”1 题、“错→错”20 题；两轮在该交集各正确 6 题。由于完成 scope 集合不同，不能把总分从 7/57 变为 6/57 归因于抽取容量。

逐题和技术统计产物为 [analysis_r31_selected.json](../../build/socialmem_20260920_structured_eval_hybrid_fenced_predicate_v3_r31_extract8192_net/analysis_r31_selected.json)，运行器汇总为 [selected-summary.json](../../build/socialmem_20260920_structured_eval_hybrid_fenced_predicate_v3_r31_extract8192_net/selected-summary.json)，离线全量汇总为 [analysis_r31.json](../../build/socialmem_20260920_structured_eval_hybrid_fenced_predicate_v3_r31_extract8192_net/analysis_r31.json)。

## 3. 抽取可靠性诊断

R3.1 的 `extraction_attempt` 共有 163 次：159 次成功，4 次失败，其中 `schema_failure` 3 次、`envelope_failure` 1 次；没有出现 `completion_truncated`。完成 token 的最大值为 6833，低于 8192 上限。

R2.3 共有 165 次抽取尝试：162 次成功，失败为 `envelope_failure` 1 次、`completion_truncated` 1 次和超时 1 次；最大完成 token 为 4096。R3.1 因提高上限消除了已观察的截断，但严格解析仍拒绝了 3 次 schema 响应，重复键 envelope 风险也仍存在。容量提升因此是局部可靠性修复，不是完整协议修复。

R3.1 完成的 3 个 scope 保存 121 条 statement，其中 24 条带 `semantic_claim_json`。结构化语义族分布为 belief 7、plan_decision 6、preference 5、uncertainty 3、affect 2、possession 1。R2.3 的 4 个完成 scope 保存 40 条结构化声明；两轮完成 scope 不同，声明数量和谓词分布不能直接作为能力增减指标。

## 4. QA 结论与下一步

R3.1 没有证明 SocialMemBench QA 提升：主分数低 1 题，成功子集几乎不变，共同 `ok` 题正确数相同。它证明了 4096 上限确实能造成 `completion_truncated`，8192 可以消除该类已观察失败；同时暴露出输出变长后仍有 schema/envelope 合同风险。生产默认继续保持 `semantic_claim_contract=false`，不晋升 8192 为默认容量，也不把本轮结果报告为 F1 或端到端质量提升。

下一轮应把变量收窄到 schema/envelope 鲁棒性：先对 R3.1 原始失败响应做 C++ RED 夹具，区分重复键、误嵌套和字段缺失，再由 C++ 提示或结构化响应边界修复；Python 继续只负责 binding 和评测编排。谓词丰富度和检索/回答优化应在技术失败稳定、7/7 scope 可完成后单独评估。

## 后继 R3.2

R3.1 观察到的 schema/envelope 失败进入 R3.2 结构化信封专项：先中文设计和 RED 测试，再由 C++ 生成末端字段骨架，最后以同题独立评测验证。R3.1 的历史数值不改写，R3.2 尚未产生新模型分数。详见 [R3.2 设计](../superpowers/specs/2026-09-20-socialmem-r32-schema-envelope-design.md)。

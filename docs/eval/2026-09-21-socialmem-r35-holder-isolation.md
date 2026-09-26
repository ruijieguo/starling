# SocialMemBench R3.5 Holder 隔离评测报告

日期：2026-09-21

## 1. 结论

R3.5 完成了 57/57 道题的回答流程，技术失败从 R3.4 的 9/57 降为 0/57；最终全题正确 16/57（28.07%），R3.4 为 12/57（21.05%），逐题净增 4 题（+7.02 个百分点）。这个增益主要来自 R3.4 未能进入回答的技术失败题，不能证明结构化 holder 隔离已经提升共同技术正常题的语义回答能力。

两轮共同技术正常的 48 道题中，R3.4 和 R3.5 都正确 12 题；R3.5 新增 3 题同时回退 3 题，净变化为 0。以 network 为重采样单位、随机种子 `20260921`、100,000 次 bootstrap 计算，R3.5 相对 R3.4 的全题差值 95% 区间为 **[-3.17, +21.82] 个百分点**；共同技术正常子集为 **[-9.52, +12.07] 个百分点**，均未证明下界大于 0。

因此 R3.5 不满足预注册晋升门槛：共同正常题净增至少 5 题、network bootstrap 区间下界大于 0、7/7 scope 完整和 36/36 holder 完整均未同时满足。生产默认继续保持：

```text
semantic_claim_contract=false
claim_protocol_retry_budget=0
```

## 2. 固定配置与证据身份

- 基准：SocialMemBench 固定 57 题、7 个 scope、6 个 network。
- 模型：抽取、回答和裁判均为 DashScope `qwen3.8-27b`。
- 抽取：C++ semantic claim contract、JSON Object、`claim-predicate-v3`、`claim_protocol_retry_budget=1`。
- 检索：`hybrid`、`focused_coverage`、`min_source_items=7`、`source_seed_k=5`、邻句半径 1。
- 回答/裁判：回答上限 512，裁判上限 64，温度 0，传输重试 0，超时 120 秒。
- HTTP 预算：1200；账本终态为 `committed=813`、`charged_upper=324`、`remaining=387`，未超预算。
- R3.5 独立目录：[build/socialmem_20260921_structured_eval_hybrid_holder_isolation_r35_dashscope](../../build/socialmem_20260921_structured_eval_hybrid_holder_isolation_r35_dashscope)。
- 冻结 `_core` SHA256：`9d23b3d699653b81b1ef07160a9ad2b8ebd5a1a7f81f1e256ef83f50e0bf853a`。
- 逐题配对和 bootstrap 原始 JSON：[socialmem_20260921_r35_pairwise_diagnostics.json](../../build/socialmem_20260921_r35_pairwise_diagnostics.json)。

## 3. QA 结果

| 分层 | 题数 | 正确 | 技术失败 | 正确率 |
|---|---:|---:|---:|---:|
| 全题 | 57 | 16 | 0 | 28.07% |
| 完整 scope（6/7） | 49 | 13 | 0 | 26.53% |
| partial scope（1/7） | 8 | 3 | 0 | 37.50% |
| long_form | 36 | 5 | 0 | 13.89% |
| multiple_choice | 13 | 10 | 0 | 76.92% |
| short_answer | 8 | 1 | 0 | 12.50% |

按问题类型，Q4 为 5/6、Q6 为 3/3，Q3 为 0/2；Q7 为 1/8、Q8 为 2/16。错误主要集中在需要跨 session 组织、行为模式归纳和短文本事实综合的长答案路径，选择题仍明显强于自由回答。

## 4. Holder 与 scope 诊断

36 个预期 holder 中 35 个完整、1 个失败。6 个 scope 完整，1 个 scope 为 partial；失败 holder 为 `Yusuf`，类别为 `schema_failure`，详情为：

```text
schema_failure: one admission decision per candidate required
```

失败 holder 的 source evidence、attempt prompt/hash、原始响应和三通道 receipt 均已保留；其余 holder 继续完成并进入 frozen snapshot，证明 C++ 批量 holder 管线的隔离目标成立。partial scope 的 8 道题单独统计，没有把失败 holder 伪装成成功声明。

## 5. 与 R3.4 的逐题配对

| 配对分母 | R3.4 | R3.5 | 净变化 | 新增正确 | 回退 | network bootstrap 95% 区间 |
|---|---:|---:|---:|---:|---:|---:|
| 全 57 题（技术失败计 0） | 12 | 16 | +4 | 7 | 3 | [-3.17, +21.82] pp |
| 共同技术正常 48 题 | 12 | 12 | 0 | 3 | 3 | [-9.52, +12.07] pp |

R3.5 全题净增不能归因于回答语义变好：R3.4 的 9 个技术失败中有 9 题重新进入回答，其中 4 题得到正确答案；共同正常子集没有净增。R3.5 更可靠地证明了可用性和失败隔离改善，尚未证明端到端质量改善。

## 6. 诊断与下一步

本轮已经解决的短板是批级技术失败放大：holder 失败不再阻断后续 holder，失败详情可直接从 C++ 汇总字段读取，Python 只做 binding 和归档。当前主要短板转移到回答链：完整来源和结构化事实已经进入 57 道题，但 long_form 仅 5/36 正确，Q7/Q8 等跨 session 行为归纳仍弱；共同正常题的配对净增为零，说明继续增加协议重试或 holder 隔离不能单独获得高分。

下一轮应先做中文设计和预注册测试，再考虑编码，候选方向为：

1. 在 C++ retrieval core 中为 Q7/Q8 的跨 session 变化、重复行为和多主体关系建立问题类型驱动的证据覆盖检查，并把证据缺口显式传给回答策略。
2. 在 C++ answer/retrieval boundary 增加长答案的事实分解与证据对齐约束，保持 Python 只负责 binding、调度和归档。
3. 用固定 57 题、相同 qwen3.8-27b 和 R3.5 frozen source 做单变量评测；完整 scope、partial scope、共同正常题和技术失败继续分层报告。

在下一轮达到“共同正常题净增至少 5、network bootstrap 下界大于 0、7/7 scope、36/36 holder”之前，不改变生产默认。

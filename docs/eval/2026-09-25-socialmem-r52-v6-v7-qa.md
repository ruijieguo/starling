> **R5.3 追溯修正（2026-09-25）**：逐条回执发现，本报告所用 R5.1 v6 上下文的345次嵌入尝试全部降级，v7无该降级。下列问答分数保留，但策略差值包含嵌入健康混杂；来源共享名额不是已被单独隔离的唯一因果解释。健康对照及诊断见[R5.3报告](2026-09-25-socialmem-r53-source-sidecar.md)。

# SocialMemBench R5.2 同库 v6/v7 fresh QA 对照报告

日期：2026-09-25。状态：已完成同一进程内的 fresh 双臂真实评测、独立封存核验和统计分析。v7 仍不晋升，开发对照保持 `evidence_profile_v6`，产品默认保持 `bm25`。

## 1. 结论

R5.2 在 R5.1 冻结的同一份 `runs/*/frozen.db` 来源快照上，使用同一份冻结回答/裁判代码、同一 qwen3.8-27B 配置，在一个 Python 进程内依次重新生成 v6 和 v7 的回答与裁判结果。两臂均覆盖 57/57 题，所有题目的回答 prompt 和上下文 SHA-256 均通过冻结 runner 重算核对；v6/v7 的 prompt 和上下文逐题均发生变化，说明本轮确实比较了两套检索上下文。

两种回答策略都显示 v7 退化：

| 回答策略 | v6 | v7 | v7−v6 | 95% network bootstrap 区间 | 共同正常题 | 转移（改善/退化/不变） |
|---|---:|---:|---:|---:|---:|---:|
| legacy | 22/57（38.60%） | 12/57（21.05%） | −10 题（−17.54 pp） | [−25.86, −8.51] pp | 57 | 0 / 10 / 47 |
| grounded_memory_v1 | 24/57（42.11%） | 11/57（19.30%） | −13 题（−22.81 pp） | [−30.65, −13.46] pp | 51 | 0 / 13 / 38 |

两臂没有出现 v7 将错误题改正确的配对转移。按既定“共同正常子集净增至少 5 题且 network 区间下界大于 0”的晋升门槛，v7 明确不满足；默认策略和历史 v2–v6 行为不改写。

## 2. 评测边界与执行合同

- 题目：R5.1 同库开发 cohort，57 题、7 个 scope、6 个 network；不能外推为完整 SocialMemBench 或保留集成绩。
- 来源：v6/v7 均读取 `build/socialmem_20260925_r51_same_db_v6_v7` 的冻结 recall；父目录为 R5.0 retry4，来源数据库和 statement 身份保持不变。
- 进程：`--fresh-v7` 让同一个进程内先后执行 v6、v7 两臂；v7 不复用 R5.0 answer/judge 回执。
- 模型：`qwen3.8-27b`，`answer_max_tokens=512`，`judge_max_tokens=64`，关闭 thinking；回答提示、选择题解析、自由题裁判均由冻结 runner/C++ binding 提供。
- Python 只负责编排、请求账本、回执封存和统计；检索、证据渲染和选择逻辑仍由 C++ 实现。

同进程消除了“v7 使用历史回答、v6 使用新回答”的主要混杂，但 qwen 服务的生成随机性、请求时间和裁判随机性仍未被完全锁定。因此结果是强诊断证据，尚不是多重复实验后的最终因果估计。

## 3. 终态、成本与完整性

| policy×arm | 题目 | `ok` | 其他终态 | answer 请求 | judge 请求 | tokens |
|---|---:|---:|---|---:|---:|---:|
| legacy×v6 | 57 | 57 | 0 | 57 | 44 | 104,908 |
| legacy×v7 | 57 | 57 | 0 | 57 | 44 | 95,164 |
| grounded_memory_v1×v6 | 57 | 51 | 4 answer_failure、2 judge_failure | 57 | 40 | 202,064 |
| grounded_memory_v1×v7 | 57 | 57 | 0 | 57 | 44 | 183,255 |

四个臂共 228 个终态任务，实际 HTTP 请求 400 次；请求账本为 `committed=400`、`reserved=0`、`charged_upper=0`，没有未结算 reservation、预算上限扣费或传输技术失败。grounded v6 的 6 个失败被保留并计零，不能与 v7 的正常回答混称为 QA 提升。

独立核验重新加载冻结 `run_socialmem_r44.py`，逐题重算四个臂的 answer prompt 和 context SHA-256，四个臂均为 57/57 匹配；同时核对了题目集合、终态字段和 SQLite 账本。核验结果保存在 [independent-verification.json](../../build/socialmem_20260925_r52_v6_v7_qa_fresh/independent-verification.json)。

## 4. 分层诊断

在两臂均为 `ok` 的题目上，v7 仍全面落后：

| 回答策略 | 题型 | 共同正常题 | v6 正确 | v7 正确 |
|---|---|---:|---:|---:|
| legacy | long_form | 36 | 11 | 4 |
| legacy | multiple_choice | 13 | 8 | 7 |
| legacy | short_answer | 8 | 3 | 1 |
| grounded_memory_v1 | long_form | 31 | 11 | 3 |
| grounded_memory_v1 | multiple_choice | 13 | 9 | 7 |
| grounded_memory_v1 | short_answer | 7 | 4 | 1 |

退化集中在需要跨话轮组织证据的长文本题。legacy 的 10 个退化题为 Q1、Q5、Q6、Q7、Q8 组；grounded v1 的 13 个退化题覆盖 Q1、Q2、Q5、Q6、Q7、Q8。两策略共有的退化题包括 `Q1_a3b4c609`、`Q1_n2c3d4e5`、`Q5_c0s4c1`、`Q5_v4s4c2`、`Q6_r3c1d2e3`、`Q7_a3b4c601`、`Q7_r3a7b8c9`、`Q8_a3b4c607` 和 `Q8_r3b8c9d0`。v7 没有改善项，说明当前语义 source 与 event 邻域的加入更可能改变了证据排序/密度，却没有稳定补足回答所需的关系谓词。

R5.0 已证明 v7 机制在同库上真实生效（953 semantic links、1,897 event candidates、34 event selected，且 57/57 source/block 改变）。R5.2 进一步证明“机制生效”没有转化为 QA 提升；当前最可信的短板是证据选择与回答任务之间的契合度，而不是 v7 开关未生效。由于本轮只做一次 fresh 双臂，不能把全部退化量拆分为语义回链、事件邻域、模型抽样或它们的交互。

## 5. 后续改进与准入条件

下一轮按以下顺序推进：

1. 对上述共同退化题保存 v6/v7 的 source refs、semantic/event lane 计数和渲染块，先做离线逐题归因；不使用金标反向调排序。
2. 在 C++ 增加“直接 claim、语义 source、event 邻域、回退 source”四类可审计 lane 统计，并补充跨人物、状态和时间谓词的反例测试。
3. 对同一 v6/v7 上下文做多次 answer/judge 重复，记录题内翻转率；若服务端支持固定采样参数，再固定 temperature/seed 后复测。
4. 只有在共同正常子集净增至少 5 题且 network bootstrap 95% 区间下界大于 0 时，才重新评估 v7 是否可晋升；在此之前保持默认 v6。

## 6. 可复核产物

- [R5.2 fresh 执行计划](../../build/socialmem_20260925_r52_v6_v7_qa_fresh/execution-plan.json)
- [R5.2 fresh 总结](../../build/socialmem_20260925_r52_v6_v7_qa_fresh/summary.json)
- [R5.2 fresh 独立核验](../../build/socialmem_20260925_r52_v6_v7_qa_fresh/independent-verification.json)
- [legacy 配对比较](../../build/socialmem_20260925_r52_v6_v7_qa_fresh/answers/legacy/comparison.json)
- [grounded v1 配对比较](../../build/socialmem_20260925_r52_v6_v7_qa_fresh/answers/grounded_memory_v1/comparison.json)
- [R5.2 中文设计](../superpowers/specs/2026-09-25-socialmem-r52-v6-v7-qa-design.md)
- [R5.2 实施计划](../superpowers/plans/2026-09-25-socialmem-r52-v6-v7-qa.md)

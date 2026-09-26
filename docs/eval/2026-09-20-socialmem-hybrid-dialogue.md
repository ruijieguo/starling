# SocialMemBench hybrid 对话检索优化评测报告

> **2026-09-20 后续诊断修正**：本报告的历史 QA 数值保持，但发现 7 个 scope 中 1 个（9 题）继承了仅来源快照，未执行结构化抽取。17/57 不能解释为完整结构化 baseline；14 条结构化声明均缺会话时间元数据。详见[结构化覆盖诊断与修复](2026-09-20-socialmem-structured-coverage-diagnosis.md)。

日期：2026-09-20
模型：`qwen3.8-27b`  端点：DashScope  题目：固定开发子集 57 题、6 个网络、7 个 scope  ᠎
回答/裁判：与来源对照完全相同，回答上限 512，裁判上限 64，零重试。

## 结论

本轮先修复 C++ 查询合同，再验证 focused dialogue 的邻句预算。合同修复有效：`mode=hybrid` 可以进入来源和声明两个分支，`mode=statements` 仍拒绝非 `bm25`。但两组真实问答均未达到晋级门槛，生产默认保持不变，下一阶段转向结构化谓词覆盖和 admission 诊断。

## 工程修复

旧校验把所有 `source_strategy != bm25` 限定在 `mode=sources`，导致 `hybrid_dialogue` 的 57 题全部在查询阶段返回 `ValueError: invalid observer query`，没有消耗模型请求。C++ 现允许 `hybrid` 搭配 `focused`、`focused_window`、`focused_dialogue` 和 `focused_coverage`；声明专用 `statements` 路径仍拒绝这些策略。

上一轮最终验证：来源检索专项 51/51；Python 相关测试 22/22。完整 C++ 回归最终为 1204 项，其中 1181 通过、22 跳过；唯一失败是当前沙箱禁止 loopback listener 的既有 HTTP 测试 `OpenAIAdapterHttpTest.LegacyAndGenerationRejectIncompleteOrRefusedCompletions`。后续诊断新增测试及本地 HTTP 复跑见上方新报告，避免混入本轮历史验证数字。

## 真实结果

| 候选 | 正确 | 准确率 | 技术失败 | 邻句新增 |
|---|---:|---:|---:|---|
| `sources` | 15/57 | 26.32% | 0 | 不适用 |
| `hybrid_fenced` | 16/57 | 28.07% | 0 | 不适用 |
| `hybrid_dialogue` | 17/57 | 29.82% | 0 | 0/57 |
| `hybrid_dialogue_expanded` | 15/57 | 26.32% | 0 | 57 题各新增 5 条 |

`hybrid_dialogue` 相对来源净增 2 题，按仓库既有 5,000 次网络级 bootstrap，95% 区间为 `[-3.03%, +11.63%]`；相对 `hybrid_fenced` 净增 1 题，区间为 `[-4.29%, +8.51%]`。`hybrid_dialogue_expanded` 相对来源净增 0 题，区间为 `[-5.26%, +4.76%]`；相对 `hybrid_dialogue` 净减 2 题，区间为 `[-12.20%, +3.08%]`。均未满足“净增至少 5 题且区间下界大于 0”。

格式分层显示，`hybrid_dialogue` 为长答 8/36、多选 8/13、短答 1/8；expanded 为长答 5/36、多选 8/13、短答 2/8。邻句扩展确实被 C++ 执行，但额外上下文使长答下降，不能把来源数量增加解释为能力提升。

## 可复核产物

- 修复后对话候选：[build/socialmem_20260919_structured_eval_dialogue_v3](../../build/socialmem_20260919_structured_eval_dialogue_v3)
- 邻句预算候选：[build/socialmem_20260920_structured_eval_dialogue_expanded](../../build/socialmem_20260920_structured_eval_dialogue_expanded)
- 来源对照：[build/socialmem_20260919_structured_eval/sources](../../build/socialmem_20260919_structured_eval/sources)
- hybrid 对照：[build/socialmem_20260919_structured_eval_hybrid/hybrid_fenced](../../build/socialmem_20260919_structured_eval_hybrid/hybrid_fenced)

两组候选的 7 份冻结数据库与父 scope 快照一致；每组均为 57/57 完整终态，账本均为 446 committed、754 remaining。候选只改变 C++ 查询策略或 seed 预算，没有重新抽取、修改题目、裁判、参考答案或历史归档。

## 后续方向

focused dialogue 参数方向关闭。当前更可能限制得分的是结构化声明覆盖：已生成的结构化声明数量、原生 semantic admission 拒绝类别、谓词族分布与声明检索命中之间仍缺少按 scope 的闭环统计。下一阶段先做离线诊断并补充 C++/Python RED 测试，再决定是否扩展 C++ 谓词目录或 admission 规则；不按题目或参考答案定制谓词。

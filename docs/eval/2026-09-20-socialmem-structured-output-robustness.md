# SocialMemBench 结构化输出鲁棒性 R2.3 评测报告

日期：2026-09-20。模型：DashScope `qwen3.8-27b`。协议：`hybrid_fenced`、JSON Object、`claim-predicate-v3`、同一冻结 source parent、57 题、7 个 scope。R2.3 只修改 C++ `claim_extraction_prompt` 的末端格式提醒，未修改解析器、谓词目录、检索、答案、裁判、题目或评分分母。

## 1. 执行结论

R2.3 的本地工程验证通过，但本次真实网络重跑不能证明 QA 提升，也不能证明提示造成了整体退化。R2.3 独立目录完成 57/57 题，得到 7/57（12.28%），26/57 技术失败，成功技术分母 31，成功子集为 7/31（22.58%）。4/7 scope 完成结构化抽取，holder 完成率为 19/36（52.78%）。生产默认继续关闭 `semantic_claim_contract`。

相较上一轮格式提醒目录的 15/57、16/57 技术失败和 15/41 成功子集准确率，本轮结果较低，但两轮成功 scope 集合不同，且本轮新增 1 次抽取超时、1 次抽取截断和 1 次回答截断。两轮共同拥有 `ok` 逐题结果的只有 17 题：上一轮 7 正确，本轮 6 正确，转移为“对→错”仅 1 题，“对→对”6 题，“错→错”10 题。因此不能把 7/57 与 15/57 的差异归因于 R2.3。

R2.3 的协议目标也没有被充分证实：当前失败回执仍有 1 条重复 `time_text`/`topic` key，触发 C++ `envelope_failure`；当前没有出现 evidence 误嵌套的 `schema_failure`，但上一轮该类失败也只发生在另一个 holder。当前证据支持“解析器继续严格拒绝，提示未消除重复键风险”，不支持“R2.3 已显著降低协议失败”。

## 2. 三轮结果对照

| 实验目录 | 正确/题数 | 技术失败 | 成功分母 | 成功子集准确率 | scope 完成 | 备注 |
|---|---:|---:|---:|---:|---:|---|
| JSON Object 首轮 | 3/57 | 48 | 9 | 33.33% | 1/7 | 误嵌套集中出现 |
| R2.2 格式提醒 | 15/57 | 16 | 41 | 36.59% | 4/7 | 2 个重复 key、1 个 evidence 误嵌套 |
| R2.3 布局对照（本报告） | 7/57 | 26 | 31 | 22.58% | 4/7 | 1 个重复 key、1 个超时、1 个抽取截断、1 个回答截断 |

三行使用同一 57 题选择集；历史结果保持原值。技术失败按题计零是主评分协议，成功子集只用于诊断，不能替代主分数。

## 3. R2.3 实现与验证

C++ 末端提醒新增两条约束：同一对象内每个 JSON key 只能出现一次；增加不含真实人物、题目或答案的 `BAD:`/`GOOD:` 顶层布局占位对照。`parse_claim_response` 未放宽，重复 key、误嵌套、缺字段和额外字段仍原样拒绝。Python 只透传 binding、配置和归档，不包含 `flatten_evidence` 或 `repair_nested` 逻辑。

RED/GREEN 证据：

- C++ RED：2 个新增 R2.3 断言失败，既有 3 个提示/合同断言通过；日志为 `build/socialmem_20260920_structured_output_layout_red.log`。
- Python RED：新增断言失败，既有 2 个断言通过；日志为 `build/socialmem_20260920_structured_output_layout_py_red.log`。
- C++ GREEN：结构化相关 7 个 suite 共 93/93，通过日志 `build/socialmem_20260920_structured_output_layout_cpp_regression.log`。
- Python GREEN：相关 7 个模块共 64/64，通过日志 `build/socialmem_20260920_structured_output_layout_py_regression.log`。
- 当前 binding 模块：`.venv/lib/python3.14/site-packages/starling/_core.cpython-314-darwin.so`，SHA-256 为 `adfa3ecec3217fc2d552d4b6a2dc97b4e8d9600e282405c3bb4f80195906344b`。

## 4. 真实评测证据

独立目录为 `build/socialmem_20260920_structured_eval_hybrid_fenced_predicate_v3_layout_r23_net`，`prepare` 和 `check` 均通过，网络执行使用用户授权的 DashScope 请求。完整原始回执、冻结数据库、请求账本和逐题文件均保留。

失败按 scope 归因如下：

| scope / 网络 | 失败 holder | 失败类别 | 影响题数 |
|---|---|---|---:|
| `3c2b930eaabb88e5f3da20b4` / `grp_0d1e2f3a` | Josh | `envelope_failure`；重复 `time_text`、`topic` | 1 |
| `135c86f3d282d1560e6fe9e7` / `grp_9c0d1e2f` | Diane | `transport_error:Timeout was reached` | 6 |
| `1006e75410f2bcc6cd666ef9` / `grp_a3b4c5d6` | Otto | `completion_truncated` | 18 |
| `dfd44fe5e0a8b6c7c6c38303` / `grp_0d1e2f3a` | 无抽取失败 | 1 题回答 `completion_truncated` | 1 |

没有观察到写入失败、SQLite/WAL 失败或 Python 清洗。当前失败 scope 的原始重复 key 回执为：`time_text` 和 `topic` 各出现两次；C++ 以 `envelope_failure` 拒绝，未自动展平。R2.2 的 evidence 误嵌套回执在本轮未复现，但这只是 scope/模型抽样差异，不能归因于提示改动。

离线诊断产物为 [analysis_r23_selected.json](../../build/socialmem_20260920_structured_eval_hybrid_fenced_predicate_v3_layout_r23_net/analysis_r23_selected.json)。其中记录了 7 个 scope、36 个预期 holder、19 个完成 holder、56 个持久化逻辑抽取尝试、原生语义族与谓词分布及两轮共同成功题目交集。分析器明确不把 statement 数量当作语义召回率。

## 5. 已持久化声明与能力短板

本轮 4 个成功 scope 共保存 121 条 statement，其中 40 条带 `semantic_claim_json`。谓词分布为 `believes=15`、`prefers=11`、`decided_on=7`、`uncertain_about=3`、`feels=2`、`owns=1`、`knows=1`；语义族为 belief 15、preference 11、plan_decision 7、uncertainty 3、affect 2、possession 1、knowledge 1。上一轮 4 个成功 scope 为 264 条 statement、82 条结构化声明，分布差异来自成功 scope 与模型输出随机性，不能解释成 R2.3 的语义能力变化。

本轮结构化抽取的 `failure_category` 主要是已完成 holder 上的 `semantic_rejection`，但 scope 级技术失败发生在更早的 envelope/transport/completion 阶段；二者不能合并为同一“谓词不足”指标。当前报告没有可复核的独立 QA judge/F1 输出，只有既有本地答案协议的正确性字段，因此 F1 记为未测量。

## 6. 统计边界与决定

本轮不是完整配对实验：成功 scope 集合在两轮之间发生变化，且网络服务返回存在超时与截断。因而不计算把两轮当作同一批完整配对样本的 bootstrap 置信区间，也不把当前 7/57 作为 R2.3 的最终能力分数。17 题共同 `ok` 交集只能作为稳定性诊断，不能作为完整 57 题因果检验。

结论是：R2.3 已完成 C++ 提示实现、严格边界回归和独立真实评测，但未达到事前“技术失败显著下降且 QA 置信区间改善”的门槛。保留 R2.3 代码和失败证据，生产默认关闭；下一轮应优先解决服务超时/截断的可归因性和完整 7/7 scope 基线，再做单变量提示或谓词优化。任何修复仍遵循中文设计 → RED 测试 → C++ 实现 → 评测。

## 7. 复现入口

```bash
./.venv/bin/python scripts/run_socialmem_structured_eval.py check \
  --arm hybrid_fenced \
  --work build/socialmem_20260920_structured_eval_hybrid_fenced_predicate_v3_layout_r23_net

./.venv/bin/python scripts/analyze_socialmem_baseline.py \
  --work build/socialmem_20260920_structured_eval_hybrid_fenced_predicate_v3_layout_r23_net \
  --output build/socialmem_20260920_structured_eval_hybrid_fenced_predicate_v3_layout_r23_net/analysis.json
```

`analysis.json` 的总量汇总包含完整 corpus 的未执行记录；本报告的 57 题主分数以 `selected-summary.json` 为准，避免把未选题目混入分母。

# SocialMemBench R5.0 语义证据回链与事件邻域评测报告

日期：2026-09-25。状态：实现、定向回归、完整 CTest、Python 回归、同库 v6/v7 检索消融和 57 题真实双臂评测均完成。R5.0 让 `evidence_profile_v7` 的语义回链与事件邻域真正生效，但没有带来可晋升的 QA 提升；默认策略保持不变。

## 1. 结论

R5.0 的核心机制已经在真实新鲜来源库上生效：57/57 题的检索诊断都 `semantic_verified=true`，共建立 953 条严格 `engram_ref + clause_id` 语义回链，产生 1,897 个同 session 邻域候选，实际选入 34 条事件邻域；没有题目走 `semantic_fallback`。同一新鲜数据库上的 qwen embedding v6/v7 离线对照中，57/57 题的 source/block 发生变化，v7 选择轨迹累计选入 365 条 semantic source 和 34 条 event source。

真实 QA 结果为：

| 轮次 | 检索/legacy | 原生/native | 技术失败 | 备注 |
|---|---:|---:|---:|---|
| R4.9 | 17/57 | 16/57 | 0 | 旧来源库、`evidence_profile_v6` |
| R5.0 | 10/57 | 10/57 | 0 | 新鲜身份一致来源库、`evidence_profile_v7` |

R5.0 相对 R4.9 分别净减 7 题和 6 题。这个差值不能归因于 v7：R5.0 为修复来源回链而重新执行了 qwen3.8-27B 抽取，statement 数量、语义 claim、engram UUID 和来源候选集合均发生变化。R5.0 是“来源身份修复 + 新鲜抽取 + v7 检索”的端到端结果，不是只改变检索策略的单变量 QA 对照。因此本轮结论是“机制生效、质量未证明提升”，不是“v7 已证明退化”。

R5.0 两臂使用完全相同的冻结检索上下文；legacy 与 native 各 10/57，配对净变化为 0（1 题改善、1 题退化）。长文本 2/36、选择题 7/13、简答 1/8。legacy 回答/裁判共 101 次 HTTP，观察 token 95,617；native 共 101 次 HTTP，观察 token 181,170。两臂均 57/57 终态、0 技术失败、零传输重试。

## 2. 设计与实现验证

本轮首先补充中文设计，固定以下合同：

- source key 只能是 `engram_ref + clause_id`，不能按文本、人物名或 session 猜测；
- 语义 source 必须先通过 tenant、holder、as-of、retention、claim evidence 和来源身份校验；
- 事件邻域只在同 holder、同 session、连续 `turn_index` 的距离 1–2 内扩展；
- 邻域是原文候选，不能被解释成因果、同一观点或“早已知道”；
- Python 只传入身份和 `ObserverQuery`，排序、回链、衰减和诊断均在 C++；
- v7 缺少语义证据时 fail closed 并退回 v6 选择合同。

C++ 定向测试覆盖语义回链压过词汇干扰、同 key 取最高分、tenant/holder/clause 隔离、连续同 session 邻域和无效 source span 回退。定向三项实际通过；完整 `starling_tests` 为 1,294/1,294 通过，HTTP 补跑保持既有跳过项边界。Python 来源登记与 holder 抽取身份回归为 18/18 通过，确认两条路径都使用：

```text
adapter_name = source_turns
source_prefix = source-<holder>-
```

当前核心扩展 SHA256：`f8c1d092b5bdc1fe710b11b67543c67f085540e767edde4331ba99ce615cf9f6`。

## 3. 评测过程与请求账本

第一次真实目录因 DashScope DNS 失败而终止，所有失败题均为 `transport_error: Couldn't resolve host name`，不计入 QA。第二次目录发现通用 runner 仍读取完整 1031 行语料，600 请求预算在预注册 57 题完成前耗尽，也不计入 QA。最终 retry4 目录固定为预注册的 57 题，并使用 2,000 请求上界：

- 7 个 scope、57 题、6 个 network；
- 新鲜抽取只对缺失 scope 执行，前 6 个已完成 scope 通过 provenance 复用；
- 抽取、来源嵌入、57 次共享检索、legacy/native 回答及裁判分别记账；
- 终态请求账本：`committed=542`，`charged_upper=81`，无 reserved，余量 1,458；
- 来源数据库完整生成，scope 状态 7/7 为 `complete`，题目 57/57 为 `ok`。

两次失败目录和 retry4 均保留，失败目录不进入分数比较。retry4 的来源复用关系记录于 `reuse-provenance.json`，没有覆盖 R4.9 历史封存。

## 4. 语义与事件诊断

v7 真实检索累计诊断如下：

| 字段 | 数值 |
|---|---:|
| 题目 | 57 |
| semantic links | 953 |
| event candidates | 1,897 |
| event selected | 34 |
| semantic fallback 题数 | 0 |
| missing/invalid source span 拒绝 | 1,059 |
| invalid semantic score 拒绝 | 6 |
| 真实 qwen embedding 请求 | 345（v7 检索）|

同库 v6/v7 qwen embedding 消融没有回答或裁判请求，v6、v7 各 345 次 query embedding。57/57 题 source/block 改变；这证明 v7 不是空开关，并且改变来自 C++ source profile。此前 Stub embedding 离线运行是 57/57、0 网络请求，但由于冻结向量来自 qwen embedding，Stub 空间不兼容，semantic link 为 0；该结果仅用于合同、回退和排序诊断，不能用于质量结论。

真实新鲜库的严格身份校验解决了上一轮根因：R4.9 数据库同时存在 `source_turns` 和 `ladder` 两套相同 payload 的 engram，statement 指向 `ladder` 副本，v7 按合同拒绝回链。R5.0 抽取和来源登记复用 `source_turns/source-<holder>-` 后，回链恢复。这个修复提高了可观测性和机制覆盖，但也改变了抽取产物，因此不能把 QA 差异单独分配给 v7。

## 5. 与 R4.9 的诊断边界

R5.0 legacy 相对 R4.9 retrieval 为 2 题转正确、9 题退化，净减 7；native 相对 R4.9 native 为 1 题转正确、7 题退化，净减 6。六 network 聚类 bootstrap（100,000 次，seed=20260925）对 legacy−R4.9 retrieval 的区间为 `[-24.56, -3.51]` 个百分点，但该区间只描述两个端到端目录的差值，不能消除重新抽取、来源身份和服务时间差异，不能作为 v7 单变量效果区间。

来源锚点计数从 R4.9 的 51/104 变为 R5.0 的 27/104。由于来源库重新抽取后 source/block 和 statement 集合全部发生变化，锚点变化只能作为事后诊断，不能解释为 v7 单独丢失或恢复证据。R5.0 不使用题号、金标或公开锚点驱动排序，也没有追加词表追分。

R5.0 当前能支持的判断是：

1. 严格 semantic source 回链已在真实语料上生效；
2. 同 session 事件邻域已在真实语料上被候选和有限选入；
3. 权限、holder、tenant、时间、预算和缺失回退合同未见回归；
4. 在当前新鲜抽取和回答配置下，没有观察到 QA 提升，且端到端分数低于 R4.9；
5. 尚不能判断下降来自抽取随机性、来源集合变化、v7 排序，还是它们的交互。

因此 R5.0 不晋升默认策略，`evidence_profile_v7` 保持实验开关；默认检索和 v2–v6 历史行为不改写。

## 6. 后续改进方案

下一轮应先冻结同一份“身份一致的新鲜来源库”，再用同一 statement/source snapshot 做 v6 与 v7 的回答双臂对照，避免把抽取税混入检索结论。具体顺序为：

1. 复用 retry4 的 7 个新鲜 scope，另行生成 v6 source/block 与 v7 source/block 的冻结包；
2. 预注册相同 qwen3.8-27B answer/judge 请求，双臂共享每题检索输入；
3. 分析 semantic 直接证据、event 邻域和 relevance 回退三类题目的得失；
4. 对 Q5/Q6 等跨表达题建立不含基准金标的 C++ 事件组合反例，验证前态、触发、回应和反证边界；
5. 只有同库 v6/v7 的共同正常题达到既定净增门槛，才考虑实验候选晋升；默认策略继续关闭。

## 7. 可复核产物

- [中文设计](../superpowers/specs/2026-09-24-socialmem-r50-semantic-event-evidence-design.md)
- [实施计划](../superpowers/plans/2026-09-24-socialmem-r50-semantic-event-evidence.md)
- [R5.0 retry4 总结](../../build/socialmem_20260925_r50_semantic_real_retry4/summary.json)
- [native answer 总结](../../build/socialmem_20260925_r50_semantic_real_retry4/native-answer/summary.json)
- [同库 v6/v7 embedding 消融](../../build/socialmem_20260925_r50_semantic_real_retry4/v6-v7-ablation/comparison.json)
- [来源复用 provenance](../../build/socialmem_20260925_r50_semantic_real_retry4/reuse-provenance.json)
- [R4.9 对照报告](2026-09-24-socialmem-r49-topic-ranking.md)

## 8. R5.2 后续同库 fresh QA 结论

按本报告第 6 节的建议，R5.2 已在同一份 R5.1 来源快照上完成同进程 fresh v6/v7 answer/judge 对照。legacy 为 v6 22/57、v7 12/57（−10 题，network bootstrap 95% 区间 −25.86 至 −8.51 pp）；grounded_memory_v1 为 v6 24/57、v7 11/57（−13 题，区间 −30.65 至 −13.46 pp）。两种策略均无 v7 改善题，v7 未达到晋升门槛，默认策略继续保持 v6。该结果比 R5.0 的复用回执诊断具有更强的双臂一致性，但仍需重复采样和逐题 lane 归因后才能拆分排序变化与模型随机性。详见[R5.2 fresh QA 报告](2026-09-25-socialmem-r52-v6-v7-qa.md)。

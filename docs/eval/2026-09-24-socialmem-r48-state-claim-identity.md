# SocialMemBench R4.8 同一声明状态资格修复与复评

开始日期：2026-09-23；完成日期：2026-09-24。中文设计 → RED → C++ 修复 → 回归 → 离线 → 真实复评已完成。**两条状态资格误判路径已修复；本轮未提高准确率，不晋升生产。**

## 1. 真实结果与决策

| 同一 57 题开发队列 | 检索臂 | 原生回答臂 | 来源锚点 | 技术失败 |
|---|---:|---:|---:|---:|
| R3.5 冻结父基线 | 16/57，28.07% | 无独立臂 | 53/104 | 0 |
| R4.6 | 15/57，26.32% | 15/57，26.32% | 48/104 | 检索臂 1 |
| R4.7 | 19/57，33.33% | 17/57，29.82% | 48/104 | 0 |
| **R4.8** | **18/57，31.58%** | **17/57，29.82%** | **48/104** | **0** |

R4.8 的检索臂相对 R4.7 净减 1 题（2 得、3 失，-1.75 个百分点），95% network bootstrap 区间为 [-8.70, 3.30] 个百分点；原生臂净差 0（1 得、1 失）。相对 R3.5，检索和原生分别多 2 题、1 题，区间为 [-6.98, 10.45]、[-4.26, 6.67] 个百分点。没有达到事前“净增至少 5 题且区间下界大于 0”的门槛。

两臂合计 114/114 正常终态，无技术失败或重试。实际 HTTP 547/600：345 query embedding、114 answer、88 judge；reserved=0、charged_upper=0，剩余 53 次未使用。answer+judge 观测 token 为检索臂 115376、原生臂 180111。

本轮是 57 题、7 scopes、6 networks 的开发诊断，不是全量或保留集成绩。父库仍只有 35/36 个完整 holder。生产默认不晋升，较高分目标尚未达到。

## 2. 实际修复了什么

R4.7 的状态车道存在两条已经由测试复现的误判路径：

1. **跨 claim 拼接资格。** 同一来源的一条 claim 表示 Alice 的偏好，另一条表示说话者 Bob 拥有地图；代码分别用两个 `any_of` 判断状态类型和 actor，使来源被误当成 Bob 的状态变化证据。
2. **原文关键词绕过状态类型。** 来源只有合法的 ownership/knowledge claim，或状态 claim 已被合同拒绝，仍可能因原文出现 `now/after/prefer` 而被优先放入状态车道。

修复在 `src/retrieval/source_retriever.cpp` 内完成：v6 的 state family、actor 等于 speaker、有效 source_turn 必须由同一条已通过证据合同的 claim 满足。任一完整合格 sibling 可以保留来源资格，但不同 sibling 不得拼接条件。v6 不再用原文关键词弥补缺失的状态 claim；v2-v5 的原文启发式保持原契约。

当前状态 family 集合未扩充；knowledge/ownership 仍可用于其他车道或普通检索。修复不删除原文，也不把缺少结构化状态解释为原文一定没有变化信息。Python 没有新增核心语义逻辑。

## 3. 测试与身份

新增 7 项原生测试，全部写在生产实现之前。初始 RED 中 4 项按预期失败，3 项正向及 v5 兼容控制通过；修复后全部通过。测试覆盖两种写入顺序、SQLite 反向读取、无效 sibling、合法 self state 与非状态 sibling 共存、预算拒绝以及 v5 兼容。负例同时检查来源仍可经普通检索保留，避免把“未入状态车道”误实现为丢弃整个来源。

| 验证 | 结果 |
|---|---|
| 来源检索定向 C++ | 61/61 通过 |
| 完整 CTest | 1283 项：1260 通过、23 沙箱跳过、0 失败 |
| localhost HTTP 补跑 | 30/30 通过，覆盖上述跳过项 |
| 相关 Python 回归 | 65/65 通过 |
| 独立离线闭环 | 57 recalls、114 terminals、0 网络请求，封存通过 |

本轮 Python 测试选择与 R4.7 的 71 项集合不完全相同，因此只报告实际运行的 65 项，不写成数量回退或全 Python 测试集。

构建、安装及真实封存核心 SHA256 一致：

`4c5c964bf55df68f9997a38a16235ae414cd4ab84cf4d368d5361b00466e6593`

当前源码与真实封存源码字节相同。R4.7/R4.8、离线/真实四组各 7 个来源数据库 SHA256 相同，均来自固定 R3.5 父库，没有重新抽取或写入。运行器保留历史 `r44_claim_attribution` 和 coverage 的 `r40` 字段；实际轮次由独立目录及核心哈希确定。

## 4. 上下文差异说明修复的实际影响

离线采用与 R4.7 相同的替身 embedding，真实采用 `qwen3.7-text-embedding`。各自跨轮比较得到同一结论：

- 57/57 题的来源引用、statement ID 和原始渲染 block 全部不变。
- 检索臂 57 个 prompt 全部不变。
- 原生回答臂 55 个 prompt 不变，2 个 prompt 仅 coverage 诊断变化。

两个变化题为 `Q1_r3a1b2c3` 和 `Q8_r3b8c9d0`。修复前各有 2 条来源被计作状态链，修复后为 1 条；`late_state` 从已覆盖改为缺失。Q1 被撤销状态资格的知识来源由归属车道承接，Q8 的相应来源由相关性车道承接。因此来源内容仍在，但不再虚报为后期状态证据。

逐题累计状态 claim 来源计数从 38 降为 36，归属 claim 来源从 16 增为 17；成员来源仍为 20，普通成员回退仍为 7。claim 加载累计 1142、拒绝 0。57 题车道计数与最终渲染、UTF-8 字节预算一致。这些是逐题累计诊断，不能解释为独立知识条数或准确率收益。

离线每题为 10 source、0 statement，真实每题为 7 source、3 statement；不能直接把两种 embedding 的完整上下文当成同一次检索。离线替身回答不计入质量结论。

## 5. 分数变化主要反映运行波动

| 臂与分层 | 题数 | R4.7 正确 | R4.8 正确 | 正误互换 |
|---|---:|---:|---:|---|
| retrieval，同 prompt | 57 | 19 | 18 | 2 得、3 失 |
| native_answer，同 prompt | 55 | 16 | 16 | 1 得、1 失 |
| native_answer，变更 prompt | 2 | 1 | 1 | 无互换 |

所有跨轮正误变化都发生在 prompt 完全相同的题目。两道受本次修改影响的题目没有判分变化。因此，本轮没有证据表明修复提高或降低了回答质量；检索臂 -1 不能直接归因于代码。

`Q7_r3a7b8c9` 检索臂又一次出现完全相同答案、相同裁判 prompt 的翻转：R4.6 为 YES、R4.7 为 NO、R4.8 又为 YES。答案描述 Bev 留意 Marcus 膝伤并照顾其路线偏好，文本未变。

对 R4.6—R4.8 的正常自由回答做事后精确分组，发现 31 组自然重复的相同裁判输入，其中 4 组判分不一致。分组包含跨轮和跨臂的自然重复，不是随机抽样的重复裁判试验；不能用 4/31 推断总体裁判错误率。原始分数和裁判结果全部保留，没有重判或择优改分。

统计仍为 6 个 network、100000 次 bootstrap、seed=20260921。原生臂差值区间为 [0,0]，是因为同一网络内一得一失恰好抵消；它不代表不存在生成或裁判方差，也不是等效性证明。

## 6. 下一处瓶颈已定位到来源选择

Q6 共 3 题，两臂均 1/3，公开锚点仍为 0/6。只读核查显示，**6 个锚点都已进入授权候选池，全部未被渲染，且 `budget_rejected=false`**。

| 题目 | 锚点对应内容 | BM25 候选排名 | 最终表现 |
|---|---|---|---|
| `Q6_c0s5c1` | Leon 在群聊中请求投资推荐 | 28 | 为 Leon 选了另一条来源，未保留该例外行为 |
| `Q6_n2a7b8c9` | Adaora 请求豆类食物、延后解释饮食变化 | 62、28 | 覆盖了 Adaora，但未选中这两条饮食证据 |
| `Q6_r3c1d2e3` | Bev 多次要求喝茶休息 | 14、47、23 | 选了 Bev 的其他来源，未覆盖停止休息的偏好 |

这里“没有预算拒绝”只排除了字节预算拒绝记录，来源名额竞争仍然存在。具体原因需要对排序与成员车道优先级继续做消融，不能从锚点遗漏直接推断唯一根因。

当前排序先比较人物匹配，再比较未加权的词重合数，然后才比较原始相关性；通用词也可能参与重合计数，成员车道又优先考虑有 claim 的来源。这是两个可检验的选择偏差，下一轮应先做 C++ 合成反例与冻结库消融：

1. 固定人物和名额，比较同一人物的“高词重合但异话题”与“较少词重合但直接行为证据”。目标是让题目主题与实际行为支配同人来源排序。
2. 独立检查 claim 优先是否压过更直接的原文证据；把合同有效性与回答相关性分开，避免结构化 metadata 变成无条件优先权。
3. 对群体规范题覆盖明确例外行为，而不仅覆盖每个人名。测试数据使用与评测无关的人名、话题和措辞，禁止按题号、金标或锚点定制规则。
4. 对时序题继续建立同人物、同话题、同事件阶段的候选约束；先验证上下文确实改变并改善相关证据选择，再执行真实 QA。

本轮已经说明，仅纠正车道资格无法解决当前主要缺证问题。下一轮重点应转向可解释的来源排序和行为证据覆盖；裁判一致性作为独立诊断保留。

## 7. 实验与封存边界

真实目录 `build/socialmem_20260923_r48_state_claim_real`；模型 `qwen3.8-27b`，answer 512、judge 64、k=10、至少 7 sources、8000 bytes、4 workers、600 HTTP、零重试。两臂共享一次检索。首次网络执行的自动审批超时未执行，按工具允许重试一次后通过；这不属于模型请求重试，也没有产生重复检索。

新旧实验均调用各自冻结运行器核验；SQLite 诊断使用 `mode=ro&immutable=1`，拒绝忽略非空 WAL。补充诊断与日志保存在 `build/socialmem_20260923_r48_diagnostics/`，不写回封存目录。333 个设计、规格、计划及技术报告入口同步当前中文结论，历史正文和冻结副本保留当时状态。

可复核证据：

- [中文设计](../superpowers/specs/2026-09-23-socialmem-r48-state-claim-identity-design.md)、[实施计划](../superpowers/plans/2026-09-23-socialmem-r48-state-claim-identity.md)、[相对 R4.7 的 C++ 补丁](../../build/socialmem_20260923_r48_diagnostics/r47_to_r48_core.patch)。
- [真实汇总](../../build/socialmem_20260923_r48_state_claim_real/analysis.json)、[完成封存](../../build/socialmem_20260923_r48_state_claim_real/completion-seal.json)、[最终核验](../../build/socialmem_20260923_r48_diagnostics/verification.json)。
- [离线上下文比较](../../build/socialmem_20260923_r48_diagnostics/offline_context_comparison.json)、[真实上下文比较](../../build/socialmem_20260923_r48_diagnostics/real_context_comparison.json)、[配对与分层](../../build/socialmem_20260923_r48_diagnostics/paired_comparison.json)。
- [相同裁判输入翻转](../../build/socialmem_20260923_r48_diagnostics/identical_judge_input_flips.json)、[三轮自然重复输入审计](../../build/socialmem_20260923_r48_diagnostics/repeated_judge_input_audit.json)、[Q6 候选证据审计](../../build/socialmem_20260923_r48_diagnostics/q6_candidate_audit.json)。
- [RED](../../build/socialmem_20260923_r48_diagnostics/r48_state_red.log)、[61 项 GREEN](../../build/socialmem_20260923_r48_diagnostics/r48_state_green.log)、[完整 CTest](../../build/socialmem_20260923_r48_diagnostics/r48_ctest.log)、[HTTP](../../build/socialmem_20260923_r48_diagnostics/r48_http_ctest.log)、[Python](../../build/socialmem_20260923_r48_diagnostics/r48_python.log)。
- [核心与数据库身份](../../build/socialmem_20260923_r48_diagnostics/identity_comparison.json)、[外置诊断哈希清单](../../build/socialmem_20260923_r48_diagnostics/artifact_manifest.json)。

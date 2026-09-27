<!-- regression-boundary-20260927:start -->
> **回归验收边界（2026-09-27）**：日常回归与固定历史评测回放分开执行；默认跳过项须显式报告，历史封存、SHA 和失败断言保持有效。部分无有效提升产物已退役，旧文中的回放链接不保证仍可用。当前执行规则见[测试说明](../../../tests/README.md)和[中文设计](2026-09-27-python-regression-boundary-design.md)；这不产生新的准确率结论，产品核心仍由 C++ 实现。
<!-- regression-boundary-20260927:end -->

<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

# SocialMemBench R4.3 事件状态与信念归属车道设计

日期：2026-09-22。状态：已完成开发评测，未修改生产默认；真实评测已完成，结果不满足晋升门槛。

## 1. 诊断依据

R4.2 使用 `evidence_profile_v4` 增加了一条受限支持性第三方来源。真实结果为检索臂 17/57、原生回答臂 19/57，来源原话精确命中 52/104；支持车道能够找回部分“已经知道/说明/为何”句子，但不能稳定回答四类问题：

1. 变化题需要主体的早期状态、触发或回应、后期状态，当前时间车道只保证日期/会话代表；
2. “谁知道谁的什么”需要 actor、被谈论者、命题和归属来源同时出现，当前 support 车道只保证第三方数量；
3. “所有成员/每个人是否都”需要逐成员证据，当前相关性和行为车道会留下 `no_selected_utterance:<holder>`；
4. 原生回答在 512 token 上限下仍出现截断，长提示重复引用和解释，技术损失会覆盖检索收益。

R4.2 冻结数据库中已有 102 条结构化声明，主要是 `believes`、`prefers`、`decided_on`、`feels`、`uncertain_about`、`knows` 和 `owns`。目录中的 `promises`、`doubts`、`responsible_for`、`requires`、`forbids` 在该样本没有保存实例。因此本轮先使用已有 C++ 谓词和来源原话建立角色链，不盲目扩张词表。

## 2. 目标和非目标

目标：

- 在 C++ 来源选择器中增加 `evidence_profile_v5`，只使用已经通过权限、时间、完整性和 holder 过滤的候选；
- 为变化/模式问题输出可审计的 `early_state`、`trigger_or_response`、`late_state` 角色，缺失角色必须记录诊断缺口；
- 为信念/知识问题区分真实 speaker、信念持有者、被谈论人物和 topic，保留至少一个归属支持来源；
- 为全体成员问题提供最多一条/holder 的受限成员覆盖车道，缺失成员显式记录 `member_missing`；
- 在 C++ 提供短回答提示，固定输出“结论—角色证据—缺口”顺序，减少 512 token 截断；Python binding 只暴露该函数和策略名。

非目标：

- 不从问题、答案或公开锚点生成候选；不读取 SocialMemBench 题号和 query type；
- 不把时间顺序自动解释为因果，不把第三方描述改写为主体自述；
- 不在 Python 复制事件、信念或成员判断；不修改 `evidence_profile_v2/v3/v4`、生产默认、R3.5/R4.0/R4.1/R4.2 封存目录；
- 不把 `member_missing=false`、来源命中或提示通过率当作 QA 提升；不因为目录存在就声称 `promises` 等谓词已被基准验证。

## 3. C++ 接口与选择契约

### 3.1 策略和诊断字段

`ObserverQuery.source_strategy` 接受新值 `evidence_profile_v5`。v5 复用 v4 的主体、话题、时间和 support 选择，新增：

```json
{
  "state_chain_requested": true,
  "state_chain_limit": 3,
  "state_chain_selected": {"early_state": 1, "trigger_or_response": 1, "late_state": 1},
  "state_chain_missing": [],
  "belief_attribution_requested": true,
  "belief_attribution_selected": 2,
  "belief_attribution_missing": [],
  "member_coverage_requested": false,
  "member_coverage_selected": [],
  "member_missing": []
}
```

`lane_selected` 增加 `state_chain`、`attribution`、`member` 计数；旧字段含义保持不变。所有角色都引用候选的真实 `source_refs`，不会创造 turn_id。

### 3.2 事件状态车道

当问题含 `change/changed/shift/earlier/later/before/after/turning point/evolved/变化/改变/转变/早期/后来` 等变化线索时启用。对每个 focused holder，按有效时间、session 和 turn_index 建立候选队列：

- `early_state`：最早的主体相关状态候选；
- `late_state`：最晚的主体相关状态候选；
- `trigger_or_response`：位于两者之间、且包含明确回应、异议、修正或原因线索的候选；
- 只有主体发言或明确提及主体的来源可进入角色链；第三方不能替代主体状态；
- 缺少任一角色时保留已有角色，并记录 `state_chain_missing`，不以会话数量推断链完整。

角色分类使用 C++ 确定性词法和已有结构化声明 metadata（predicate、semantic_family、topic、source_turn、attributed_to）；不做新的 LLM 请求，不将词法命中当作语义证明。

### 3.3 信念归属车道

当问题包含 `knew/know/aware/believe/think/assume/已经知道/了解/相信/认为`，或询问“某人的话说明什么”并同时点名两名人物时启用。候选必须满足以下至少两项并单独记录：

- `speaker` 是问题中授权人物，保留真实说话者；
- 文本明确提及另一名 focused holder，或结构化 claim 的 `actor`/`attributed_to` 指向该人物；
- 文本包含知识、信念、预期、回应、确认或纠正线索；
- topic 与问题词有重合。

归属车道最多占两条来源名额，分别优先信念持有者句和被谈论人物/命题句。没有同时满足归属条件时记录 `belief_attribution_missing`，回答提示要求说出缺口。

### 3.4 成员覆盖车道

当问题含 `each member/all members/everyone/each person/所有成员/每个人/大家` 时启用。对 `focused_holders` 中每个 holder：

- 若已有候选入选，记录其最相关的一条；
- 若未入选，从授权候选中选择一条最低相关但仍通过完整性过滤的该 holder 来源；
- 每个 holder 最多一条，超过 source limit 时按问题中出现顺序轮询；
- 没有任何授权来源时记录 `member_missing`，不得用其他人的事实补齐。

成员覆盖不改变 subject_sessions 或 third_party_sessions 统计，不把低相关来源冒充答案证据。

### 3.5 短回答提示

新增 C++ `compact_grounded_memory_answer_prompt(question, recall_json)`，binding 暴露同名函数。它复用 `grounded_memory_answer_packet` 的身份校验，要求：

1. 第一段直接回答结论；
2. 变化题最多三条短句，按 early/trigger-or-response/late 排列；
3. 信念题明确写出“谁知道/相信谁的什么”，不能转移 speaker；
4. 多成员题逐人一句，缺失者写“证据不足”；
5. 全文 90–150 个英文词等价长度，最多两条短引文，不重复问题、标题或总结。

该提示只改变实验 answer policy `grounded_memory_v2`，不改变旧 `grounded_memory_v1` 和 legacy 提示。

## 4. 测试先行

先新增 C++ RED，再实现 GREEN：

- v5 策略可通过校验，v2/v3/v4 行为和非法策略回归不变；
- 变化夹具在日期齐全但缺少主体早期/触发/后期时输出对应 `state_chain_missing`；角色选择保留真实 speaker；
- 信念夹具区分“Luca 知道 Raj 的状态”和“Raj 自述”，错误归属不能进入 attribution lane；
- 全体成员夹具即使某人 BM25 分数低也保留一条，完全无来源的 holder 进入 `member_missing`；
- source limit、UTF-8 字节预算、tenant/holder、擦除、未知时间和 `selection_trace.rendered` 保持约束；
- 短回答提示包含三类角色约束，不包含题号、答案或 Python 词表；
- Python 合同只检查 binding 暴露和配置策略，不实现任何语义判断。

## 5. 评测与晋升门槛

真实评测新建 `build/socialmem_20260922_r43_state_attribution_real`，继承 R3.5 父快照但不修改父目录和 R4.x 封存目录。固定 57 题、两臂共用一次检索、`qwen3.8-27b`、零重试、600 HTTP。检索臂使用 v5 + legacy，原生回答臂使用 v5 + `grounded_memory_v2`；所有 HTTP、失败、token、角色缺口和精确来源命中独立封存。

继续条件不变：相对 R3.5 共同正常题净增至少 5，网络 bootstrap 95% 区间下界大于 0，技术失败不得增加；同时 `state_chain_missing`、`belief_attribution_missing`、`member_missing` 不能比 R4.2 恶化。否则仅保留开发诊断，不修改生产默认。

## 6. 回滚

若角色车道降低选择题或长答正确率、增加缺口误报、破坏 holder 隔离或提示仍截断，则停止使用 v5/v2，恢复 v4/v1；旧代码、旧 binding 和封存目录不覆盖。生产仍保持 `semantic_claim_contract=false`、`claim_protocol_retry_budget=0`。

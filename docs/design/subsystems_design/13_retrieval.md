<!-- regression-boundary-20260927:start -->
> **回归验收边界（2026-09-27）**：日常回归与固定历史评测回放分开执行；默认跳过项须显式报告，历史封存、SHA 和失败断言保持有效。部分无有效提升产物已退役，旧文中的回放链接不保证仍可用。当前执行规则见[测试说明](../../../tests/README.md)和[中文设计](../../superpowers/specs/2026-09-27-python-regression-boundary-design.md)；这不产生新的准确率结论，产品核心仍由 C++ 实现。
<!-- regression-boundary-20260927:end -->

<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../../superpowers/specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](../../superpowers/specs/2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](../../superpowers/specs/2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](../../superpowers/specs/2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](../../superpowers/specs/2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：已完成真实评测；当前按中文设计、RED 测试、C++ 实现顺序修复 consolidated source 与原始 claim engram 的安全回连，详见 [中文设计](../../superpowers/specs/2026-09-22-socialmem-r44-claim-attribution-design.md)。

> **R3.1 实评收口（2026-09-20）**：检索和回答协议未改；8192 抽取容量只减少截断，未带来 QA 配对增益。57 题完成 6/57、技术失败 30，成功 scope 为 3/7；后续先修复 C++ schema/envelope 边界，再单独评估谓词和检索。详见 [R3.1 评测报告](../../eval/2026-09-20-socialmem-r31-extraction-capacity.md)。

> **R3.1 抽取容量诊断设计（2026-09-20）**：检索和回答协议不变；评测阶段仅把结构化输入的抽取上限由 4096 提升至 8192，并保留 4096 来源臂作为对照。任何 QA 变化都须结合技术失败和共同题目配对结果解释，不能由声明数量直接推断。详见 [R3.1 设计](../../superpowers/specs/2026-09-20-socialmem-r31-extraction-capacity-design.md)。

> **结构化覆盖诊断修正（2026-09-20）**：历史 hybrid_dialogue 17/57 只覆盖 6/7 结构化抽取 scope；另 9 题复用仅来源库。96 条记录仅 14 条有结构化证据，且全部缺会话/话轮时间元数据。本轮补齐 C++ 拒绝分类和评测覆盖门禁，零新模型请求，无新 QA 提升；下一步先补输入与回执。详见[诊断与修复报告](../../eval/2026-09-20-socialmem-structured-coverage-diagnosis.md)。本条同步当前评测边界，各子系统原有语义以正文为准，历史分数不重写。

> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](../../eval/2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](../../eval/2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](../../eval/2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](../../eval/2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](../../eval/2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](../../eval/2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：C++自由回答政策使开发273/733→332/733（45.29%，+8.05百分点），通过预注册开发门槛；技术失败11→74，60项回答截断。来源/模型/评分不变，默认legacy保持；无本轮保留或全量成绩，详见[当前报告](../../eval/2026-09-17-socialmem-grounded-answer.md)。

> **人物检索优化已验收（2026-09-17）**：C++人物路由与邻接完成开发及保留集验证，同一候选392/1031=38.02%，原baseline20.47%，累计+17.56百分点；保留集19.46%→39.93%。默认bm25保持，模型/评分不变，结构谓词能力另行验证；详见[当前报告](../../eval/2026-09-17-socialmem-source-focus.md)。历史结果按各自冻结版本解释。

# Retrieval Planner

## 观察者来源人物路由（2026-09-17设计增量）

`ObserverQuery.source_strategy`默认为`bm25`。`focused`、`focused_window`、`focused_dialogue`与`focused_coverage`由C++实现；其中前两者及对话/覆盖扩展可用于`sources`和`hybrid`的来源分支，`statements`仍拒绝非默认策略。人物识别、各人物独立队列、全局证据通道、已过滤话轮邻接与UTF-8预算均由C++实现。未匹配姓名时回退原BM25。选择结束后按原始观测时间/会话/话轮顺序渲染，引用逐行一致。安全过滤先于路由，任何通道不得放大allowed_holders。对话扩展的seed_k、seed_bytes和radius必须在原生查询合同中校验；外层k等于seed_k时合法但不会产生新增邻句，评测编排应显式记录该诊断状态。

Python绑定只透传，禁止复制核心算法。固定开发评测与现有k30同预算，候选是否晋升取决于真实733题结果，详见[冻结设计](../../superpowers/specs/2026-09-17-socialmem-source-focus-design.md)。
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](../../eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

> **后续修复同步（2026-09-12）**：可空主题允许缺省或 null，无效类型统一在 C++ 预检；情绪校验不以“觉得/感觉”或整轮认知词直接拒绝。写入与检索共用原生契约。重复裁判一致率与有效分母单列，原严格门槛保持。实现范围及尚未完成的能力见 [中文优化设计](../../superpowers/specs/2026-09-12-socialmem-optimization-design.md)。

> **语义证据契约状态（2026-09-12）**：已实现并通过完整工程验证；真实诊断已完成并核验，质量门槛未通过，默认关闭，设计见 [Source-Grounded Claim Contract](../../superpowers/specs/2026-09-11-source-grounded-claim-contract-design.md)。按已确认契约 Context Pack 返回 clause_id、source span/hash、assertion scope、attribution 和 event-time 状态；tenant/perspective 硬过滤先于排序，source-time fallback 单独记入 RetrievalReceipt。

> **中文优化同步（2026-09-12）**：检索上下文继续携带 SourceTurn 的 speaker、session、turn、topic 和原始时间；事件时间未知时只能标记 `UNKNOWN/source_time_fallback`。主题与话轮过滤由 C++ 执行，binding 不增加语义判断。详见 [优化设计](../../superpowers/specs/2026-09-12-socialmem-optimization-design.md)。

## 2026-09-11 语义证据契约

C++ basic/planner/MetaStore 读取可选证据。tenant、holder/perspective 和擦除过滤先于证据暴露与排序；证据不一致的行排除并累计原因。RetrievalReceipt 增加 `evidence_links_json`、`claim_exclusion_counts_json`、`source_time_fallback_count` 和 `candidate_counts.dropped_by_claim_evidence`。已有八种标签保持，范围、归属、event_time 和来源时间以注释表达。已知事件区间参与时间排序；未知事件时间仅用来源新近度并明确 fallback。原文片段只通过已选且已验证的链接提供，不能扩大召回范围。

诊断归档原生 `degraded_paths`；semantic-index 降级作为技术失败计数，保留 fallback 供分析。离线验证用 C++ 渲染所选数据库行，并核对原生 entries、标签、分数和 total-k 选择，不能只比较回答 prompt 与未经核验的上下文字符串。

实现状态与评测证据统一见 [同步清单](../claim_contract_sync.md)。

## 2026-09-23 consolidated source 声明回连

R4.4 的 `evidence_profile_v6` 在 C++ 中读取已通过 `claim_evidence_error` 的
`semantic_claim_json`。来源登记可能指向按 holder 合并的 consolidated engram，而
声明的 `source_span.engram_ref` 仍指向原始逐话轮 engram。两者不再以 engram id
直接相等作为唯一条件：在同一 tenant、holder 和 source speaker 范围内，C++ 使用
`speaker、turn_id、session_id、turn_index、observed_at` 五元 `source_turn` 精确回连。
五元组缺失或不一致、跨 tenant/holder、哈希/擦除/来源单元校验失败均拒绝。回答上下文
继续只渲染授权 SOURCE 原文；binding 不实现回连或语义评分。

回连过程输出 `claim_reconciliation_attempted`、`claim_reconciliation_succeeded` 和
按原因的 `claim_reconciliation_rejection_reasons`，并与
`claim_metadata_loaded/rejected`、`selection_trace` 一起归档。回连计数用于验证机制
生效，不替代 SocialMemBench QA 分数或晋升门槛。

## 功能定义

Retrieval Planner 是视角感知检索与心智摘要子系统。它按 `(querier, perspective, intent, goal)` 四元组重构 Context Pack，不是工具堆的 fan-out 封装。对外可见效果上它是纯读模块：不直接修改 Statement state，只以 fire-and-forget 方式 emit `statement.recalled` 事件，由 [Reconsolidation Engine](11_reconsolidation.md) 异步消费决定是否开窗。

---

## 输入

- query(querier, perspective, intent, goal) 调用
- 9 种 QueryIntent 之一（FACT_LOOKUP / BELIEF_OF_OTHER / META_BELIEF / HISTORY / COMMITMENT_DUE / PREFERENCE / NORM_LOOKUP / COMMON_GROUND / ABSTAIN_CHECK）
- holder 子图查询（来自 Neocortex）
- KnowledgeFrontier 遮蔽规则（来自 Cognizer Hub）
- CommonGround 共识池快照（来自 Neocortex）

## 输出

- Context Pack（8 标签：FACT / BELIEF / HEARSAY / INFERRED / COMMON / TODO / CONFLICT / ABSTAIN）
- RetrievalReceipt（trace_id / query_id / filters_applied / candidate_counts / evidence_erased_count / sufficiency_status）
- statement.recalled 事件（fire-and-forget，触发 Reconsolidation 异步开窗判定）
- Abstention 决策（拒答原因：max_score < τ_recall / perspective frontier 不允许 / 唯一证据来自 RECANTED 链 / 冲突未仲裁）

---

## 主要流程

### P1 basic_retrieve 闭环

```
basic_retrieve(holder=self, intent=FACT_LOOKUP, subject, predicate, as_of=now())
  → 只查 Statement 主表轻量索引 (holder, consolidation_state, valid_from, valid_to)
  → 只返回 consolidation_state ∈ {CONSOLIDATED, ARCHIVED}
  → 过滤 review_status ∈ {REJECTED, PENDING_REVIEW}
  → 过滤 EvidenceRef.status = ERASED
  → 不做 rerank / ToM / CommonGround
  → 返回 list[Statement]（附 evidence hash / source metadata）
```

约束：`basic_retrieve` 只支持单 holder。传入多 holder 必须拒绝（或显式拆分调用），不得 silently broaden scope。

### P3 完整 7 步规划

```
1. parse   → Query → intent + 关键 entity
2. mask    → 按 perspective 的 KnowledgeFrontier 遮蔽不可见证据（EnigmaToM iterative masking）
3. plan    → 按 intent 选择路径（见 Intent→Path 映射）
4. fetch   → 并发多源（向量 / 图 / KG / EngramStore / Working Set / ToM API）
             fetch 完成后异步 emit statement.recalled × N（Bus 防抖合并）
5. fuse    → 按 holder 子图 + salience + recency 重排；Affect-aware Reranker
6. ground  → 检查 CommonGround，标"已 grounded"以便复述抑制
7. abstain → Abstention Gate（max_score / frontier / RECANTED / conflict 四条件）
```

step 4 fetch 完成后，**异步** emit `statement.recalled`，Retrieval 主流程不等待。Reconsolidation Engine 异步判定是否开窗（频繁召回短窗口内 ≥ K 次、或与近期 `belief.conflict` 同 key 则开窗；否则只升软 activation）。

### 多 holder 隔离

多 holder 检索时，Planner 必须为每个 holder 构建独立 substrate context，分别执行 fetch，再在 fuse 阶段合并。

规则：
- 每个子查询 filters 必须包含单一 `tenant_id + holder_scope/group_scope`，并写入 `RetrievalReceipt.filters_applied`。
- 并发度受 `ScopedWorkGate(lane=retrieval)` 限制；某 holder 失败只降级该 scope，不扩大到无 scope fallback。
- fuse/merge 阶段只处理 StatementRef / score / metadata，不得重新打开未授权 Engram raw 内容。

### statement.recalled emit 契约

- fire-and-forget，Retrieval 主流程不阻塞。
- Bus 防抖合并同 key 的重复事件。
- 同一 `(querier, perspective, intent, text, time)` 在 2s 内多次调用，返回相同结果，事件去重（幂等窗口）。
- `access_count` 是 in-memory 软统计，由 Replay Scheduler 周期批量 flush 到 Statement，非每次召回即写库。

### Abstention 触发条件

```
abstain if:
    max_score < τ_recall                   # 召回分低于阈值
    OR perspective frontier 不允许该信息   # KnowledgeFrontier 硬约束
    OR 唯一证据来自已 RECANTED 链
    OR conflict 未仲裁（请求澄清，而非赌一边）
```

abstain 时输出结构化"我不知道，因为 ___"，而非编造或模糊的"不确定"。

### 渐进式 scope 计划

Progressive plan 先查低成本 scope（`working_set / statement_main / projection_index`）；若 `sufficiency_status=SUFFICIENT` 且 stop\_policy 允许，跳过 `graph_index / semantic_index / engram_evidence`。跳过的 scope 必须写入 `skipped_scopes` 与 `stop_reason`，不得让 Receipt 看起来像全量检索。

### Intent → Path 映射

| Intent | 主路径 | 辅助 |
|---|---|---|
| FACT\_LOOKUP | Neocortex Semantic（holder=self）+ EngramStore 证据 | Working Set |
| BELIEF\_OF\_OTHER | Neocortex Semantic（holder=target） | EngramStore 中 target 发言 |
| META\_BELIEF | 嵌套 Statement（nesting\_depth=2） | perspective\_take 即时构建 |
| HISTORY | 时间索引 + supersedes 链 | EngramStore time-window |
| COMMITMENT\_DUE | Prospective Loop 队列 | — |
| PREFERENCE | Persona.preferences | PREFERS 类 Statement |
| NORM\_LOOKUP | Norms 子区 + scope 过滤 | enforcement\_history |
| COMMON\_GROUND | CommonGround pool（parties=...） | — |
| ABSTAIN\_CHECK | 跨子区低召回判定 + 校准置信度 | KnowledgeFrontier |

---

## 核心算法

### 1. perspective filter 位序

perspective filter 必须在语义排序之前执行。这是隐私边界硬约束，不可绕过。`filters_applied` 必须能证明 perspective filter 与 tenant/holder scope 已执行，否则结果不得返回。

### 2. Affect-aware Reranker

```python
def rerank(candidates, querier_state):
    for c in candidates:
        c.score = (
            base_relevance(c)
            * (1 + 0.3 * recency_factor(c))
            * (1 + 0.4 * c.salience)
            * (1 + 0.3 * activation_level(c))
            * affect_consistency(c.affect, querier_state.affect)
            * (1 - temporal_distance_penalty(c, query_time))
        )
    return sorted(candidates, key=lambda c: -c.score)
```

`affect_consistency` 对情感一致性加权；`temporal_distance_penalty` 对距查询时间锚点远的 triplet 降权（借鉴 cognee temporal\_retriever）。

P3 可升级为三级 RRF 融合（Topic → Episode → Fact），使用 vector-anchored fusion：

```python
score = alpha * vector_score_or_floor + (1 - alpha) * bm25_saturated_or_floor
# 默认 alpha=0.7, saturation_k=5.0
```

最终 score breakdown 必须写入 RetrievalReceipt。

### 3. Context Pack 8 标签判定

| 标签 | 语义 |
|---|---|
| FACT | 已建立共识，持有者确认 |
| BELIEF | 某方视角下的信念，含置信度 |
| HEARSAY | 单一来源，可能过时 |
| INFERRED | 基于行为模式推断 |
| COMMON | 所有 party 共同知道 |
| TODO | 待办承诺，含 deadline |
| CONFLICT | 多方陈述矛盾，待澄清 |
| ABSTAIN | 无可靠记忆，主动拒答 |

LLM 接收到的不是无差别文本块，而是已分类、归因、置信度标注的语用结构。

Context Pack 示例：

```
[FACT]    Bob 当前负责 auth（Alice 在 4/15 群聊宣布，共识已建立）
[BELIEF]  据 Carol 所知，新方案下周一上线（置信 0.7，但 Bob 暂未确认）
[HEARSAY] 我听 Alice 说 Bob 上周休假（单一来源，可能过时）
[INFERRED]根据 Bob 长期工作模式，他可能晚于 deadline 交付
[COMMON]  我们都知道：本季度目标是发布 v2
[TODO]    你 3/12 答应给 Alice 看代码（还有 2 天）
[CONFLICT]关于 X 的负责人：Alice 认为是 Bob，Carol 认为是 Dave，待澄清
[ABSTAIN] 关于 Y 的最新进展：无可靠记忆（Bob 上次提及在 2 月，之后无更新）
```

### 4. Abstention Gate 输出

输出结构化"我不知道，因为 ___"。四条件任意一条满足即触发：低召回分、frontier 不允许、唯一证据 RECANTED、冲突未仲裁。

### 5. RetrievalReceipt 合法性约束

- `filters_applied` 必须能证明 perspective filter 与 tenant/holder scope 已执行，否则结果不得返回。
- projection lag 超过 §4.1 SLA 时，必须记录 `degraded_paths` 与 fallback；无 fallback 则 Context Pack 加 `[ABSTAIN]` 或 stale 标记。
- `score_breakdown` 只记录可审计分数与 StatementRef，不泄露被遮蔽证据正文。
- `sufficiency_status` 四态：`SUFFICIENT / MISSING_INFO / NEEDS_RAW / ABSTAINED`。`NEEDS_RAW` 必须先通过 retention/visibility 检查，gate 失败则 `ABSTAINED`。

### 6. filter 混合形式拒绝规则

禁止同一 plan 同时使用全局 filter 又让部分 scope 自带不同 holder/group。这种混合形式必须拒绝，写入 `RetrievalReceipt.abstention_reason=invalid_scope_filter_mix`。

### 7. 幂等与 access_count flush

- 同 `(querier, perspective, intent, text, time)` 在 2s 内多次调用，返回相同结果，事件去重。
- `access_count` 是 in-memory 软统计，通过 Replay Scheduler 周期批量 flush，非每次召回写库。

---

## 数据结构

### QueryIntent 枚举（9 种）

```python
class QueryIntent(Enum):
    FACT_LOOKUP        # 查事实
    BELIEF_OF_OTHER    # 查 X 相信什么
    META_BELIEF        # 查 X 以为 Y 知道什么（二阶，深度上限受 ToMDepthEstimator 调制）
    HISTORY            # 查时间线
    COMMITMENT_DUE     # 查待办
    PREFERENCE         # 查偏好
    NORM_LOOKUP        # 查规范
    COMMON_GROUND      # 查共识
    ABSTAIN_CHECK      # 主动检查"是否真的不知道"
```

### Query 输入

```python
class Query:
    querier:      CognizerRef               # 谁在问（默认 self）
    perspective:  CognizerRef               # 从谁的视角检索（默认 = querier）
    intent:       QueryIntent
    text:         str
    time:         datetime                  # 检索时间锚（as_of）
    goal_context: Optional[GoalRef]
```

### basic_retrieve 函数签名（P1）

```python
def basic_retrieve(
    holder:    CognizerRef,         # 仅支持单 holder，多 holder 必须拒绝
    intent:    QueryIntent,         # P1 固定 FACT_LOOKUP
    subject:   str,
    predicate: str,
    as_of:     datetime,
) -> list[Statement]:
    ...
```

### RetrievalScopeStep / RetrievalScopePlan（P3）

```python
class RetrievalScopeStep(BaseModel):
    scope: Literal[
        "working_set", "statement_main", "projection_index",
        "semantic_index", "graph_index", "container_view",
        "engram_evidence", "tom_runtime"
    ]
    adapter_scope:  Optional[str]           # 外部库原生 scope，仅作 metadata
    holder_scope:   Optional[CognizerRef]
    group_scope:    Optional[str]
    filters:        dict
    max_candidates: int
    on_error:       Literal["degrade","abstain","fail_closed"]

class RetrievalScopePlan(BaseModel):
    plan_id:      str
    mode:         Literal["basic","progressive","parallel","exhaustive"]
    steps:        list[RetrievalScopeStep]
    stop_policy:  Literal["after_first_sufficient","merge_all",
                           "needs_raw_gate","abstain_on_gap"]
    merge_policy: Literal["ranked_union","intersection",
                           "priority_order","rrf"]
    filter_mode:  Literal["global_inherited","per_scope_explicit"]
```

注：P1 不需要创建 `RetrievalScopePlan` 对象，Receipt 可用固定字段记录 `scope="statement_main"`、filters、candidate\_counts 与 sufficiency。

### Affect-aware Reranker 输入输出

```python
# 输入
candidates:    list[StatementCandidate]   # 含 base_relevance / salience / affect
querier_state: CognizerState              # 含 affect 向量

# 输出
list[StatementCandidate]                  # 按 score 降序排列，score breakdown 写入 RetrievalReceipt
```

### RetrievalReceipt（P1 最小字段加粗，完整结构如下）

```python
class RetrievalReceipt(BaseModel):
    trace_id:             str                 # P1 必填
    query_id:             str                 # P1 必填
    querier:              CognizerRef
    perspective:          CognizerRef
    intent:               QueryIntent
    runtime_health:       Literal["READY","DEGRADED","DRAINING","UNREADY"]
    trace_retention:      Literal["metadata_only","hash_only",
                                  "redacted_debug","full_debug"]
    sanitized_query:      Optional[dict]      # method/original_length/clean_length
    sufficiency_status:   Literal["SUFFICIENT","MISSING_INFO",
                                  "NEEDS_RAW","ABSTAINED"]
    scope_plan:           Optional[RetrievalScopePlan]
    plan_steps:           list[dict]          # parse/mask/plan/fetch/fuse/ground/abstain
    skipped_scopes:       list[dict]          # scope + reason + stop_policy
    stop_reason:          Optional[str]
    projection_lag:       dict                # per projection: lag_seconds/sequence_delta/stale
    scopes_searched:      list[str]
    filters_applied:      list[dict]          # P1 必填：holder/perspective/tenant/review/evidence erasure
    candidate_counts:     dict                # P1 必填：fetched/reranked/returned/dropped_by_mask/dropped_by_review
    score_breakdown:      list[dict]          # statement_id + base/vector/bm25/salience/recency/final
    evidence_erased_count: int                # P1 必填
    degraded_paths:       list[dict]          # path + reason + fallback
    abstention_reason:    Optional[str]
    emitted_events:       list[str]           # statement.recalled ids，或抑制时为空
```

P1 `basic_retrieve` 只需填 `trace_id / query_id / filters_applied / candidate_counts / evidence_erased_count`。

### Context Pack 8 标签

```python
ContextPackLabel = Literal[
    "FACT", "BELIEF", "HEARSAY", "INFERRED",
    "COMMON", "TODO", "CONFLICT", "ABSTAIN"
]
```

---

上述 Python 示例为绑定层接口契约。核心实现为 C++ 抽象类，Python/JS/Rust 等绑定通过 pybind11 / NAPI / cxx 自动生成存根。

## 相关概念

**9 种 QueryIntent**
`FACT_LOOKUP / BELIEF_OF_OTHER / META_BELIEF / HISTORY / COMMITMENT_DUE / PREFERENCE / NORM_LOOKUP / COMMON_GROUND / ABSTAIN_CHECK`。覆盖事实、信念、二阶信念、时间线、承诺、偏好、规范、共识、主动拒答九类检索意图。

**7 步规划**
`parse → mask → plan → fetch → fuse → ground → abstain`。每步有明确输入输出，fetch 后异步 emit 事件，主流程不阻塞。

**perspective filter**
硬约束，必须在语义排序之前执行。依赖 [Cognizer Hub](08_cognizer.md) 的 KnowledgeFrontier 实现 EnigmaToM iterative masking，决定哪些证据对当前 perspective 可见。

**Affect-aware Reranker**
在 base\_relevance 基础上乘以 recency、salience、activation、affect\_consistency、temporal\_distance\_penalty 五个因子。affect\_consistency 来自 [AffectVector](../history/04_starling_design_v17.md#数据本体) 与 querier 当前情感状态的匹配程度。

**Context Pack 8 标签**
`FACT / BELIEF / HEARSAY / INFERRED / COMMON / TODO / CONFLICT / ABSTAIN`。Retrieval 输出不是无差别 RAG 文本，而是带语用标注的心智摘要，让 LLM 理解每条记忆的认识论地位。

**RetrievalReceipt**
每次检索生成一份回执，记录 scope、filter、候选数量、score breakdown、被遮蔽/删除证据计数、abstention 原因。`filters_applied` 必须能证明 perspective filter 与 tenant/holder scope 已执行，否则结果不得返回。评测体系可直接用 receipt 区分"没查到"、"被权限遮蔽"、"projection stale"、"主动 abstain"。

**Abstention（主动拒答，LongMemEval 关键失分项）**
四条件任意一满足即输出结构化"我不知道，因为 ___"：召回分低于 τ\_recall、perspective frontier 不允许、唯一证据来自 RECANTED 链、冲突未仲裁。不编造，不输出"不确定"。

**读副作用契约**
Retrieval Planner 不修改 Statement state，不直接写 confidence，不直接开 Reconsolidation 窗口，不改 supersedes 链。对外唯一副作用是 emit `statement.recalled`（fire-and-forget）。

**statement.recalled 异步契约**
`statement.recalled` 事件由 Bus 防抖合并，[Reconsolidation Engine](11_reconsolidation.md) 异步消费。频繁召回（短窗口内 ≥ K 次）或与近期 `belief.conflict` 同 key 时开窗；否则只升软 activation，不开窗。Retrieval 主流程不等待。

**Mentalizing Primitives**
META\_BELIEF intent 的嵌套深度由 [Mentalizing Primitives](09_tom.md) 的 ToMDepthEstimator 调制，防止无限递归二阶信念推断。

**basic\_retrieve（P1 闭环）**
P1 最简路径。只查 Statement 主表轻量索引，只返回 `CONSOLIDATED / ARCHIVED` 状态，过滤被拒绝与被删除证据，不做 rerank / ToM / CommonGround。验证目标是"Bus.append\_evidence → Extractor → Bus.write → direct state transition helper → basic\_retrieve"端到端可跑通。

**多 holder 隔离**
多 holder 检索为每个 holder 构建独立 substrate context 分别执行，fetch 后 fuse 阶段合并。P1 `basic_retrieve` 只支持单 holder。

**幂等窗口**
同 `(querier, perspective, intent, text, time)` 在 2s 内多次调用返回相同结果，`statement.recalled` 事件去重。

**access\_count flush**
in-memory 软统计，Replay Scheduler 周期批量 flush 到 Statement，不是每次召回即写库。

- 配置：所有 Adapter 与运行时配置采用 JSON 格式，统一 schema 见主文档 §2.0

---

## 实现补记(2026-06-12 P3.a1)

P3.a1 交付:9 种 QueryIntent、7 步管线(`src/retrieval/retrieval_planner.cpp`,
每步写 receipt.plan_steps)、Affect-aware Reranker 五因子(`affect_reranker.cpp`,
breakdown 落 receipt.score_breakdown)、Abstention Gate 四条件(`abstention.cpp`,
优先级 frontier>recanted>conflict>score,τ_recall 默认 0.25 可配)、Context Pack
8 标签(`context_pack.cpp`,优先级 TODO>CONFLICT>COMMON>INFERRED>HEARSAY>
BELIEF>FACT,ABSTAIN 由 gate 注入整包)、Receipt 完整字段与 RetrievalScopePlan、
多 holder 隔离(per-step 单一 holder_scope + `invalid_scope_filter_mix` 拒绝)。
perspective mask:结构化路径 SQL 下推,语义路径取回后、rerank 前按
KnowledgeFrontier 可见集遮蔽(满足"排序之前"位序)。statement.recalled 由
planner 中心化 emit(键公式与 basic_retrieve 一致,拒答零事件)。入口:
`Memory.query()` / dashboard `POST /api/recall`(intent 非空)。

本期裁剪(后续里程碑):`sanitized_query`(P3.b 随 query 清洗)、三级 RRF/bm25
融合与多源并发 latency budget(P3.c)、`ScopedWorkGate(lane=retrieval)`(P3.c
治理)、`temporal_distance_penalty` 连续距离函数(v1 为有界惩罚:过期 0.3)。
META_BELIEF 的 ToMDepthEstimator 上限调制接线归 P3.a2(估计器已存在)。


## 来源时间与独立扩展标签（2026-09-12）

按已批准优化范围执行 [中文来源话轮设计](../../superpowers/specs/2026-09-12-source-turn-evaluation-design.md)。C++ 生成并解析版本化话轮，保留原始消息时间与 UTF-8 来源位置，正文与元数据分开校验；Bus/检索重建 source_turn 防止篡改。Python 仅映射和统计，独立扩展标签不进入模型输入，不修改原 P1 金标。真实时间不推断为事件时间或 UTC；已完成 C++ 实现、全量测试、离线与真实核验；真实诊断为 verified / complete_with_errors，质量门槛未通过。普通正文冒号保留完整语义，直接写入/回读使用共享严格解析器拒绝嵌套重复键。详见 [来源话轮评测报告](../../eval/2026-09-12-socialmem-source-turn.md)。


## 生成契约完整性同步（2026-09-12）

按 [中文生成契约设计](../../superpowers/specs/2026-09-12-claim-generation-design.md)，C++ 在抽取提示中明确对象、逐字主题、原始时间限定和字段类型约束，并提供与本次来源隔离的通用中英文参考示例。模型输出校验、准入、存储/检索与默认开关保持既有约束，Python 仅绑定和评测编排；参考示例不作为当前证据。本轮 C++ 实现、完整回归、离线核验及历史响应 140/140 一致性重放已完成；真实诊断于北京时间 2026-09-13 完成核验，为 `verified / complete_with_errors`。固定候选 59/64、synthetic 契约 13/16、独立对象 12/14、主题/联合各 1/14，原生技术失败 5；主题字面匹配分数不能解释为字段缺失。P1 兼容与逐例不退步门槛仍失败，Q1/Q9 结构化及链接组仍为 0/3，默认关闭。详见 [生成契约评测报告](../../eval/2026-09-12-socialmem-generation.md)。其他专项职责沿用设计同步清单，历史快照保持。

## 输出协议与偏好边界同步（2026-09-13）

按 [中文修复设计](../../superpowers/specs/2026-09-13-claim-protocol-boundary-design.md) 继续已批准优化：C++ 提示强调键唯一、时间原文及同话轮引用，准入与解析共用合法原因目录，窄范围拒绝把明确偏好对象写成 feels。真情绪不因同源其他偏好句被拒；Bus/回读复用共享契约，Python 仅绑定与编排。当前已完成 RED、C++ 实现与复审修复后的完整回归（C++ 1,062 项，Python 1,319 项通过/15 项跳过）；旧响应重解析 137/140 一致，3 条偏好误标候选提前拒绝。复合/因果情绪及被动 preferred 感受保留准入，句尾标点边界有正反例覆盖。独立复审发现均已关闭，最终离线 140 条/144 数据库核验通过；真实诊断已完成并由原生验证器核验为 `verified / complete_with_errors`：140 条重放、144 个数据库；固定候选 56/64（TP 30、TN 26、误收 0、误拒 1、技术失败 7），synthetic 冻结 11/16、契约 11/16（有效分母 15/16），P1 combined F1 为 holder 0.7317、holder/perspective 0.6829、predicate/object 0.7683；扩展标签 object/topic/scope/time/joint 为 12/14、2/14、12/14、12/14、2/14（有效目标 13）；Q1/Q9 的 baseline、structured、linked 均为 0/3，full 均为 3/3；实际证据链仍受入库与证据聚合限制。原生技术失败共 10 条，主要为重复 JSON 键和准入 JSON 后追加文本；无效裁判票 0。`promotion_ready=false`，生产默认保持关闭，不运行 1,031 题全量。默认、原标签、检索与历史归档保持。

## 声明范围与覆盖诊断职责（2026-09-15）

检索继续重放 C++ parse_claim_response，沿用相同定位规则及完整来源完整性检查，不在检索器复制范围推断。来源链接仍指向整 source unit；局部诊断不是新的可信证据或召回排序信号。Marcus 的未生成状态不能通过本方案的检索阶段补出；已实施，本地验证结果见实施分析。

详见[声明范围定位与生成覆盖诊断设计](../../superpowers/specs/2026-09-15-claim-scope-localization-design.md)。

## 2026-09-16 能力与得分路线修订（已授权自主迭代）

拟将 Python 评测中的跨 holder 候选合并收进 C++，统一范围、评分、去重、top-k 与 token 预算；复用时间视图并加入受控来源证据组合。通过结构、RAG、联合证据消融验证收益。 具体范围、测试与验收见[统一方案](../../superpowers/specs/2026-09-16-socialmem-capability-and-score-design.md)。本段描述计划，不代表已经实现或获得新分数。

最新执行顺序已按用户指令调整：先冻结当前默认 Starling 并完成全部 1031 题基线，再按真实失分执行中文文档→失败测试→C++ 改进→同条件复测，循环自主迭代，无需重复申请常规步骤授权。基线前仅补评测编排及题目允许来源范围，不预修被测能力。详见[基线优先执行计划](../../superpowers/plans/2026-09-16-socialmem-baseline-first.md)。

## 2026-09-17 独立来源与观察者检索

新增C++来源保留接口经既有Bus写入Engram，0035的source_documents只登记tenant/holder/Engram及首次登记时间，不复制正文。旧来源不猜测owner回填。宿主提供显式授权holder，核心执行范围、擦除、保留策略、完整性哈希与时间截止过滤；SourceTurn保留说话人、来源时间和会话/话轮身份，未经声明抽取也可独立召回。

ObserverRetriever将跨holder声明融合收进C++，并提供statements/sources/hybrid三种显式模式，统一去重、整行UTF-8字节预算和原生渲染；sources当前是确定性BM25，hybrid交替来源与声明。旧默认路径不变，新路径不会扫描整个租户来扩大权限。来源以SOURCE标记原始发言，不自动变成已认证事实；时间表示来源时间，不推断事件发生时间。Python和其他binding只转发接口。

设计、验收和本轮开发评测状态见[独立来源专项](../../superpowers/specs/2026-09-17-socialmem-independent-source-design.md)。现有39项原生与53项Python聚焦回归通过；两轮6题四臂已终态，回答关闭思考后声明/来源/融合/全文为1/6、2/6、2/6、3/6，零技术失败。1031题原始来源模式全量复测已完成，201题正确（19.50%），1007题成功评分、24题来源失败；其后的57题姓名词项候选未晋升。


## 2026-09-17 来源可靠性与上下文回执更新

C++在认证与时间过滤之后、BM25统计之前按可靠话轮身份及原文/来源时间去掉增量批次重复候选；缺身份或不同内容版本保留。登记与查询截止要求明确合法UTC时间，原始来源观察时间不改写。SOURCE模型输入保留说话人、观察时间、会话和位置及转义正文；完整Engram/clause/turn身份保留在按行对应的source_refs回执，避免把内部标识重复占用模型上下文。k=30/8000字节仅在显式开发候选配置测试，未切换旧默认记忆路径。实测与边界见[候选报告](../../eval/2026-09-17-source-context-density.md)。

## 2026-09-17 坏时间容错与未知时间候选

原生来源写入显式开启preserve_invalid_time时，坏时间字符串保留在v2载荷，读取时观察时间为null并附原值和invalid标记。include_unknown_time默认false；本轮来源基线显式开启，按来源登记及Engram创建截止接纳候选，已知未来时间仍拒绝。授权、tenant、擦除、hash及预算约束保持。unknown_time_included是候选计数，最终返回以source_refs为准；不把登记时间当作事件时刻。详见[修复设计](../../superpowers/specs/2026-09-17-baseline-recovery-design.md)。

## 2026-09-18 原生两阶段证据回答边界

新增`evidence_answer.hpp/.cpp`提供`source_evidence_prompt`、`verify_source_evidence`、`evidence_answer_prompt`及`answer_with_evidence`。输入仅为已授权召回的SOURCE块及问题；C++为来源分配局部编号，发起证据选择，核验source_id、实际发言人与连续原文引语，再以完整原来源和通过引用核验的证据生成答案。Python绑定只暴露DTO和原生调用，评测脚本只负责路由、三阶段回执与预算结算。

该能力只认证引语与来源匹配，`interpretation`仍为未验证模型解释；不能把被描述主体、时间顺序或因果关系当成已经获得语义认证。未新增持久化事实、推断谓词或隐式授权，也没有将`select_temporal_evidence`的有序早晚声明视为因果验证。规划失败按固定策略回到原grounded提示，保留失败与成本记录；适配器异常标记未知预算，并按上界结算。

`evidence_v1`为显式实验政策，sources自由回答最多增加一次模型调用；默认legacy及选择题原协议保持。工程契约和733题真实开发评测均已完成：313/733＝42.70%，相对同1024容量父下降4.37个百分点，未晋升。实验设计和诊断见文档首部；引用来源核验不表示社会语义推断已验证。

## 两阶段证据回答验收结论（2026-09-18）

C++实现和733开发题真实评测完成：313/733＝42.70%，相对同1024容量父345/733净减32题（−4.37个百分点），33网络95%差值区间[−7.89,−0.86]个百分点；自由题236→203/581。观测tokens5,397,777（+69.46%），1894 HTTP，24裁判超时和1回答截断全计零，4次规划降级。预注册五项仅截断与观测用量通过，拒绝晋升；通过门槛的推荐配置仍为grounded_v1/512，默认legacy不变。

引用核验成功不表示解释正确：本轮2631条合格引语、115条不连续引用被拒；双方技术正常690题仍净减26题，不能仅用超时解释下降。固定案例暴露目标事件和时间错配、双向互动链遗漏；后续优先验证C++事件指向、主体归属与回应关系，先文档、再独立测试、最后实现，不追加本轮候选搜索。全部模型请求已结束，主评分保持原协议；保存的模型响应驱动581最终提示原生回放一致。完整诊断见本轮评测报告。

## 2026-09-18 连续话轮扩展接口

ObserverQuery新增focused_dialogue策略及source_seed_k、source_seed_max_context_bytes、source_dialogue_radius三个参数。C++在既有权限/时间/完整性过滤后复用focused_window选种子，再加入同会话、连续位置的原文；预算先保障种子，邻接不等于已验证的回复或因果边。Python仅暴露字段与透传配置。其他策略维持原行为。

本轮固定30条/8000字节种子、半径2、总60条/16000字节，grounded_v1/1024，无额外模型规划。新增原生14项与实际绑定3项已通过；733题旧路径兼容、真实准确率及成本仍待冻结评测。与容量父比较同时改变组织和容量，不声称等预算的单因素收益。

本接口开发验收：旧focused_window的733份block/refs/prompt全部逐字复现，focused_dialogue的733份实际来源完整保留原种子；39来源库不变。真实成绩376/733，相对345净增31，观测tokens+52.21%，未达到净增37的预注册门槛，因此不作为推荐默认。剩余主要限制是问题范围、时序、冲突陈述和答案覆盖；邻接仅提供来源上下文，不证明因果。原生54项、新Python31项、既有回归42项及封存辅助10项通过。完整结果见本页顶部链接。


## 单次综合回答接口（2026-09-18）

C++在evidence_answer.hpp/.cpp提供synthesis_source_answer_packet与synthesis_source_answer_prompt，复用来源解析器，将已授权的原生SOURCE块转换为synthesis_v1证据包。保留来源顺序、说话人、会话、话轮、陈述时间、未知时间元数据及原文；source_id是包内位置，text是正文保留字段，输入元数据不得占用这两个名称；空白说话人与损坏来源在请求前拒绝。证据包不是权限过滤器，也不补写事件时间或认证答案语义，semantic_verified始终为false。

新提示引导单次模型回答注意问题范围、事件时序、实际触发、回应与反证、推断强度和多成员覆盖；规则没有实现自动语义校验。Python仅暴露接口和路由；synthesis_v1只允许sources召回，自由题一次回答、至多一次原裁判，选择题保持旧提示。旧政策与推荐默认不变。本轮固定上一轮733题来源和1024回答容量，仅证据表示与生成政策改变；输入token数可能因表示而变化，真实效果见本节终态验证及文档首部报告。

单次综合回答终态验证：61项原生、37项新Python、22项旧政策、27项基线与账本、10项封存辅助测试通过。733题预检来源相同，581证据包无损，152选择题提示不变；实际可用上下文733题、证据包581题、选择题提示152题完成核验。真实成绩309/733，较376净增-67，观测tokens为4,857,066；未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。此结果只评估固定开发集单次生成政策，不证明已实现问题范围、时序、关系或因果的自动语义校验。

本轮成本口径补充：回答显式关闭thinking，裁判沿用旧协议且未显式设置此参数；原始HTTP usage中裁判有821,168个reasoning_tokens。judge_max_tokens=64不是观测总completion tokens的上限。后续若修改裁判配置须作为独立实验，不混入当前配对成绩。

## 2026-09-18 回答表示与指导消融设计

已新增C++显式实验接口source_answer_ablation_prompt，组合SOURCE/JSON表示与grounded/synthesis指导。两个历史对角提示逐字兼容，Python仅绑定和实验编排；模型qwen3.8-27b、固定来源、1024回答上限、原裁判不变。按33开发网络各3题抽样，99题四组合、上限792次请求，结果仅作机制诊断，不晋升。来源包保真不等于人物归属、因果或社会推断已验证。详见本文件顶部本轮报告。

## 2026-09-19 回答消融结果与结构化能力边界

99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。 五项配对区间均包含0，没有达到完整开发集验证条件的方向。C++已提供显式source_answer_ablation_prompt，两个历史对角提示逐字复现，Python只做绑定和实验编排；默认推荐未改。39个来源库的statements与非空semantic_claim_json均为0，本轮不检验结构化抽取/记忆闭环。

事后原文核对确认关键发言漏召回、人物归属错误及否认未约束推断；部分原裁判YES也包含错误归属。跨时段重复中另有3例相同答案与相同裁判提示标签翻转，不能当作总体误判率或修改主评分。下一阶段先用独立用例诊断召回选择，再复用现有claim_contract、claim_evidence、temporal_evidence，单独验收抽取→校验→写入→检索→回答；这些后续改动尚未执行。来源/字段完整性不认证人物归属或因果语义，补充契约的五类关系不代表全量谓词。评分稳定性校准须独立记录，不与旧主分数混比。

## 2026-09-19 人物与会话覆盖检索设计

显式focused_coverage候选已在既有来源过滤及focused_window种子后，用剩余条数与字节预算的一半按人物/会话轮转补充本人发言，再围绕原种子扩展；保持整行原文、总预算和授权范围。选择与trace均由C++实现，Python只绑定和实验编排。C++与99题同期对照已完成；99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。结构化记忆闭环和裁判校准仍待独立验证。

## 2026-09-19 结构化声明检索闭环首轮状态

新增 `structured_claim_retriever.hpp/.cpp`，把结构化候选选择归回 C++：请求必须带 tenant 及 holder/subject 范围，可选规范谓词、topic、UTC 截止时间和 `TemporalEvidenceRequest`；候选先通过 `claim_evidence_error` 的来源哈希、span、Engram、scope、holder/perspective、模态/极性和原生合同重放，再做谓词归一、主题、时间和 top-k/early-late 选择。回执保留 `excluded_scope`、`excluded_invalid_evidence`、`excluded_unknown_predicate`、`excluded_missing_order` 和不足原因。无有效证据时返回不足状态，不把原文或单条声明升级为事实。

`context_pack` 与 Python binding 只消费 C++ 选择结果；Python 不复制谓词列表、语义族、范围判断、证据认证或时间选择。首轮专项 C++ 8/8、Python 10/10 通过，但现有合成测试对 temporal 正向候选仍为空候选路径，尚未证明“写入后成功检索”的闭环率。因此结构化检索保持实验状态，默认路径、旧 receipt 和历史评测不变；补强正向 source/temporal fixture 后再进入真实评测门槛。

## 2026-09-19 正向结构化检索夹具验收更新

已补强正向夹具：一条真实 C++ 抽取→持久化→consolidation→BasicRetriever→结构化证据检索路径，以及两条带真实 Engram source hash/span 和 SourceTurn 的 early/late 路径均通过，正向夹具 3/3。专项 C++ 9/9、Python 10/10、相关合同/证据/抽取/记忆回归 105/105；完整回归的唯一失败仍是当前沙箱禁止 loopback listener 的既有 HTTP 测试。结构化检索的离线专项门槛通过，可以进入一次固定模型对照；默认检索路径和历史归档继续保持不变。

## R2 谓词覆盖扩展设计同步（2026-09-20）

本阶段承接结构化覆盖诊断和 SourceTurn/三通道回执修复，目标是补齐结构化合同与 legacy mental-state 之间的能力断层。C++ 原生目录版本升级为 `claim-predicate-v3`，新增 `prefers`、`promises`、`doubts`、`believes`、`responsible_for`、`requires`、`forbids` 七类规范谓词及受控别名；既有谓词、来源证据、admission 和持久化格式保持兼容。目录、别名、语义族、允许模态/极性、抽取提示和准入提示均由 C++ `PredicateCatalog` 唯一生成，Python 只绑定、编排和归档，不维护第二份语义逻辑。

本阶段严格执行中文设计文档 → C++/Python RED 测试 → C++ 实现 → 固定协议回归。测试覆盖中英文正反例、错误模态、主体与对象保真、admission 拒绝计数、`knows` 历史模态兼容、三通道证据回读和 Python binding 边界。新增结构化声明数量或离线测试通过率不等于 QA/F1 提升；只有 7/7 scope、36/36 holder 的同协议 SocialMemBench 结果和预注册统计门槛满足后，才讨论晋升。生产默认仍保持 `semantic_claim_contract=false`。

## R2.1 结构化输出协议修正（2026-09-20）

首次 `claim-predicate-v3` 固定评测中，qwen3.8-27b 在 legacy 结构化请求下出现截断、未转义 JSON 和证据范围不完整，57 题中 47 题在抽取建库阶段失败。该结果只说明协议性技术失败，不能解释为谓词扩展导致 QA 下降。下一轮由 C++ `OpenAIAdapter::extract_with_contract` 使用 `ValidationPolicy.claim_output_mode=JsonObject` 发送原生 `response_format`；C++ 继续执行 envelope、schema、scope、admission 和持久化校验，Python 仅传递配置和归档回执，不清洗模型文本。生产默认仍为 `semantic_claim_contract=false`、`claim_output_mode=Legacy`；新评测必须使用独立身份并分别报告技术完成率和 QA。

## R2.2 结构化输出末端格式提醒（2026-09-20）

检索层不负责修复结构化声明。抽取提示的末端格式提醒仅改善进入存储/检索前的协议完成率；原始响应、schema 失败和 scope 失败继续按 C++ 回执归档，不能把提示协议收益直接当成 QA 收益。

## R2.3 重复键与布局对照（2026-09-20）

检索继续只消费通过 C++ 合同的声明。末端唯一 key 和布局对照降低结构化抽取在进入检索前的协议失败，但不改变检索排序和 QA 评分。

### R2.3 实评证据收口（2026-09-20）

独立网络评测完成 57/57 题，7/57 正确、26/57 技术失败；4/7 scope 完成，holder 为 19/36。失败包括重复 `time_text`/`topic` 的 `envelope_failure`、抽取超时、抽取/回答 `completion_truncated`。两轮共同完整题目只有 17 题，不能从 15/57 与 7/57 的非配对差异推断提示因果收益。当前仍保持 C++ 严格拒绝和 Python 仅 binding/编排，生产默认 `semantic_claim_contract=false`；完整证据见 [R2.3 鲁棒性评测报告](../../eval/2026-09-20-socialmem-structured-output-robustness.md)。

## R3.2 结构化证据入口（2026-09-20）

检索只消费通过 C++ wire/schema/scope/admission 契约并成功持久化的声明。R3.2 先修复结构化输出信封的生成提示，不改变检索排序、证据过滤或回答协议；技术完成率与 QA 必须在独立评测中分开报告。

## R3.2 语义诊断与 R3.3 检索方案（2026-09-21）

R3.2 完成 57/57 题但成功子集为 13/56；43 道错误题中 26 道来源和结构化声明均未命中金标话轮，说明协议修复没有解决检索覆盖。零请求回放显示既有 C++ `focused_coverage` 比 BM25 能覆盖更多金标话轮，R3.3 因此只在 C++ 增强该策略：识别全体成员问题、对变化问题首尾交替选择 session，并在 hybrid 中先满足 `min_source_items` 来源配额。

`ObserverQuery.min_source_items` 默认 0，旧 `bm25` 输出保持兼容；评测候选使用 `focused_coverage`、seed=5、radius=1、最小 SOURCE=7。配额达成、预算拒绝、source/statement 数量和选择 trace 必须进入回执。来源命中是召回指标，不等于事实正确、关系正确或因果正确；完整设计见[R3.3 证据覆盖设计](../../superpowers/specs/2026-09-21-socialmem-r33-evidence-coverage-design.md)。

R3.3 C++ 专项 24/24、Python binding/门禁 24/24 通过；零请求回放为 BM25 24/56、focused coverage 45/56。真实评测的 38 道正常题全部达到 7 条 SOURCE 配额，但整体因 19 道抽取技术失败而不晋升；`min_source_items=0` 的历史交替输出继续作为兼容路径。

## R3.4 抽取可用性与检索输入边界（2026-09-21）

R3.4 只修复进入检索前的两类原生协议失败：C++ 对 envelope/schema 错误最多重试一次，成功后才允许声明写入和结构化检索；scope 语义拒绝、无证据声明和持久化失败仍被排除。检索排序、来源配额和 Python binding 不变，技术完成率与 QA 继续分开报告。

## R3.5 Partial holder 检索边界（2026-09-21）

R3.5 允许带完整 holder 结果和 `holder_failures` 的 partial snapshot 继续进入诊断检索；检索器只消费实际通过 C++ 合同并成功持久化的声明和已授权 SOURCE，绝不为缺失 holder 生成占位事实。receipt 必须暴露 scope_state、holder_complete、失败 holder 及 attempt 路径，报告按完整/partial holder 分层；生产默认检索和历史快照不变。

## R4.5 Claim-aware 车道优先级（2026-09-23）

`evidence_profile_v6` 在 C++ 中先处理已回连且通过 `claim_evidence_error` 的声明车道，再用 relevance 补齐来源名额。状态链、信念归属和成员覆盖分别输出 claim 选中计数及 fallback；计数只有 `take()` 成功、来源确实渲染且 `claim_loaded=true` 时才增加。最终 `lane_selected_rendered` 始终从 `selection_trace.selected_by` 重新计算，避免诊断计数与上下文集合分离。失败回连、跨 tenant/holder、source_turn 不一致和预算拒绝只能保留为普通来源或缺口，不能获得 claim 车道分数。Python 只传递 `source_strategy` 并读取原生诊断。


### R4.6 车道计数与排序补充（2026-09-23）

v6 的 `lane_selected` 仅由成功的 `take()` 计一次，claim 计数仅统计该车道新选入的有效 claim。共享来源只归属于首次选中它的车道，可以满足其他覆盖要求，但不重复计数也不记回退。`claim_lane_fallbacks` 仅统计成员车道成功新增普通来源的次数，不统计名额/字节预算拒绝、缺失候选和 relevance 补齐。状态与归属车道保持严格 claim 资格。成员车道按有效 claim 优先稳定分组，组内沿用相关性排序，避免仅因时间早而抢占题目相关来源。内部优先级使用资格布尔值和现有排序，不新增无标定的浮点 claim 分数。R4.5 历史分数与 R4.6 新核心结果分开记录。


R4.6 真实复评已封存：检索与原生回答均 15/57，来源锚点 48/104，546/600 次 HTTP，检索臂 1 次 512-token 截断。相对 R4.5 所有判分变化来自相同 prompt 的题目，变更 prompt 队列没有判分变化；无可归因的准确率提升，不晋升。底层 102 条 claim 全为第一人称，归属车道排除自述导致选中数为 0；同一来源多 claim 的单视图覆盖风险待下一轮 RED 验证。当前契约与详细结论见本文顶部 R4.6 中文报告入口。


## R4.7 多声明与第一人称归属设计入口（2026-09-23）

R4.6 暴露了同一来源多条 claim 覆盖和第一人称信念无法进入归属车道的问题。R4.7 先保留全部通过证据校验的 claim，再按人物边界进入 C++ 归属车道；设计见 [2026-09-23-socialmem-r47-multi-claim-attribution-design.md](../../superpowers/specs/2026-09-23-socialmem-r47-multi-claim-attribution-design.md)，实施计划见 [2026-09-23-socialmem-r47-multi-claim-attribution.md](../../superpowers/plans/2026-09-23-socialmem-r47-multi-claim-attribution.md)。R4.7 已完成离线、真实复评和最终封存核验，详见[中文诊断报告](../../eval/2026-09-23-socialmem-r47-multi-claim-attribution.md)。R4.6 原结果保留；本轮检索 19/57、原生回答 17/57，涨分尚不能归因于代码修复，不晋升。


## R5.3 来源预算与结构化声明 sidecar 实现及评测边界（2026-09-25）

C++ ObserverRetriever 的共享名额机制已确认：在 k=10 下，v7 先把 source_limit 算为 7，再追加 3 条结构化声明；R5.1 冻结上下文中 v6 为 10 条 SOURCE，v7 为 7 条 SOURCE 加 3 条声明。但 R5.1 v6 的 345 次嵌入尝试全部降级，v7 无此降级，复用这些上下文的 R5.2 分数比较受检索健康状态混杂，不能据此认定主要退化或全部退化来自共享名额。R5.2 两种回答政策均无 v7 改善题的历史分数保留；产品默认仍为 bm25，开发对照为 v6。

R5.3 实验策略 evidence_profile_v8 已在 C++ 实现。来源选择与 sidecar 选择分成两个阶段：k 只约束来源；来源先按主体、主题、BM25 和稳定时间顺序选择，semantic link 只在直接相关性相当时参与排序或在无直接候选时回退；event 邻接的设计合同限定其从已保留 anchor 派生，具体修复与验证状态以本轮报告为准。来源集合确定后，最多追加 3 条声明 sidecar；声明必须有合法 source_span、回链到已选来源并满足相关性、tenant、holder、as-of、review、hash/span 约束。sidecar 超过数量或字节预算时只丢弃声明，不减少来源。

v8 的 block 仍由 C++ 渲染，SOURCE 行在前、sidecar 行在后；source_count、statement_count、source_context_bytes、statement_context_bytes 分开记录，context_bytes 仍等于完整 block 的 UTF-8 字节数。拒绝原因写入 sidecar_rejections，selected 保持来源数语义以兼容既有评测。Python 只透传策略和读取诊断，不维护谓词、回链、相关性或预算逻辑。同库真实语义检索已完成：三臂健康、来源控制一致，但 v8 来源锚点低于 v6，未通过门槛，未启动 QA、不晋升。测试与门槛见 [R5.3 设计文档](../../superpowers/specs/2026-09-25-socialmem-r53-source-sidecar-design.md)，冻结评测核心与后续修复验证分别见 [R5.3 中文评测报告](../../eval/2026-09-25-socialmem-r53-source-sidecar.md)。

## R5.4 来源预算与有效期合同（2026-09-25）

实验策略 `evidence_profile_v9` 在 C++ 复用 v6 的来源选择顺序和 v8 的独立来源预算/严格 sidecar 准入；不启用 v8 的直接命中优先排序，也不启用 v7/v8 的 semantic/event 来源排序。`k` 只约束来源，先渲染来源，再按共同 UTF-8 字节预算追加最多三条声明，不能挤掉来源。v9 `sources` 不调用 planner/embedding，v9 `hybrid` 才查询声明候选。Python 仅透传和编排，不复制这些决策。

语义 planner 和 source claim metadata 的声明有效期统一为 `[valid_from, valid_to)`，NULL/空界无界；复用既有结构化资格过滤并保持 semantic DTO、cosine 及 salience/activation/provenance，不用 observed_at 推断有效期。原行为兼容仅针对合法时间数据，未来/过期声明的旧准入属于已修复漏洞。

同核心57题四臂检索完成：baseline/source7锚点51/104，source10/sidecar为67/104，228条回执全健康；两对来源控制逐题一致，source10无声明且无嵌入请求。source10通过预注册QA门槛，问答结论以当前R5.4评测报告为准。没有声明时相关性指标“不适用”；sidecar仍为诊断臂。fresh QA只比较baseline/source10的组合效果，不把锚点增量当作答题增量，不更改产品默认。

## R6.7 原生语义来源选择与评测边界（2026-09-26）

新增独立实验模块 `include/starling/retrieval/source_selection.hpp` 和 `src/retrieval/source_selection.cpp`。`collect_selection_pool(observer, query)` 复制查询，以sources/bm25收集经租户、holder、时间、保留和擦除策略过滤的来源，最多1000条、131072字节；`eligible_sources`必须与池实际条数相同，溢出或不完整池显式失败。C++按观察时间、会话、turn_index和稳定身份排序，未知时间置后。模型输入只含问题、来源编号、原文、speaker/session/time及预算，不包含标准答案、题型或公开锚点。

`source_selection_prompt`生成选择提示词，`select_sources`最多进行一次原生LLM调用，`apply_source_selection`验证并渲染回执。模型仅提议整数`source_ids`；C++拒绝额外字段、重复键/编号、未知编号、布尔/浮点编号、超过20条或8000 UTF-8字节的计划。来源整行、归属和引用保真，按原池时序呈现，不截断、不补齐、不回退。空池零调用；模型失败或异常保留原始响应和费用不确定性。纯回放接口消费已授权池，不是新的授权入口。

这些规则只在C++实现，Python绑定仅透传；Python评测层负责快照、任务调度、started回执、HTTP账本、冻结和统计。选择核心与历史回答/审计核心在不同进程使用。候选无声明附加区，不证明谓词、人物状态或因果关系能力已被补齐，也不改变默认检索路径。

R6.7已完成文档、RED、实现及评测：13项新增原生反例包含在1389项完整C++回归中，12项binding、14项选择编排和16项QA编排测试通过。同八库、六网络、133题来源选择129题成功，锚点194→205/263。同期v9→selector正确50→56/133（37.59%→42.11%，+4.51个百分点），聚类95%区间[-4.58,17.17]；正常130→125/133。共同正常123题正确49→55。增益、区间和健康门槛未全部满足，未晋升；不是全量、保留集或生产结论。

本轮已证实尚未修复的边界：`OpenAIAdapter::generate()`调用`complete(prompt,false)`，选择工厂设置的`json_object_output`不会在此路径启用结构化输出。四次选择合同失败按完整分母计错；下一轮须在C++修复真实调用路径并测试HTTP请求体，不能在Python剥除围栏后事后修分。群体反例丢失、变化事件直接行为被压缩、回答遗漏已有证据分别进入后续设计；格式修复本身不等于质量晋升。

真实调用共602/611 HTTP、零重试、零新增embedding；已知tokens为3,679,744，7次QA超时缺用量，总消费未知，账本无未结算预约。候选读取完整池的额外选择开销必须计入收益评估。详细数据、逐题机制及复现入口见[本轮中文诊断报告](../../eval/2026-09-26-socialmem-r67-source-selection.md)。

## R6.8 显式结构化来源选择合同（2026-09-26）

新增C++ `select_sources_structured(question,pool,llm,k,max_context_bytes)`，显式传递`SourceSelectionV1/JsonObject`至已有`extract_with_contract`路径，实际HTTP体含`response_format.type=json_object`。SourceSelectionV1限定唯一键source_ids及最多20个互异正整数；池内编号与UTF-8动态预算继续由原生apply_source_selection验证。新旧入口共用一个执行器，旧select_sources保留自由生成以支持历史对照，Python只做绑定和实验编排。

新入口核对响应合同、模式、schema哈希和原始内容一致性；不支持、超量、围栏或不健康响应直接失败，不隐式能力探测、不重试或回退。JSON mode只约束传输格式，不能保证来源选择语义正确或满足20条预算。既有显式能力探测API新增空来源列表夹具与可重放证据，真实评测不自动调用它。

本地1395项C++回归、20项绑定/localhost HTTP、14项选择编排和16项QA编排测试通过。R6.8已完成133题结构化来源选择与同期QA：v9为52/133，selector为60/133，净增6.02个百分点；六网络聚类95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升。选择合同失败从R6.7的4题降为3题，均为超过20条预算；Markdown围栏失败为0。来源池、选择提示词、预算及回答政策保持R6.7合同；群体反例、事件角色和裁判规则本轮不改。完整设计见[中文设计](../../superpowers/specs/2026-09-26-socialmem-r68-structured-selection-design.md)，详细结果见[中文评测报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)，历史R6.7原始结果保留。

<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../../superpowers/specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](../../superpowers/specs/2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](../../superpowers/specs/2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](../../superpowers/specs/2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](../../superpowers/specs/2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](../../superpowers/specs/2026-09-22-socialmem-r44-claim-attribution-design.md)。

> **结构化覆盖诊断修正（2026-09-20）**：历史 hybrid_dialogue 17/57 只覆盖 6/7 结构化抽取 scope；另 9 题复用仅来源库。96 条记录仅 14 条有结构化证据，且全部缺会话/话轮时间元数据。本轮补齐 C++ 拒绝分类和评测覆盖门禁，零新模型请求，无新 QA 提升；下一步先补输入与回执。详见[诊断与修复报告](../../eval/2026-09-20-socialmem-structured-coverage-diagnosis.md)。本条同步当前评测边界，各子系统原有语义以正文为准，历史分数不重写。

> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](../../eval/2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](../../eval/2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](../../eval/2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](../../eval/2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](../../eval/2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](../../eval/2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：C++自由回答政策使开发273/733→332/733（45.29%，+8.05百分点），通过预注册开发门槛；技术失败11→74，60项回答截断。来源/模型/评分不变，默认legacy保持；无本轮保留或全量成绩，详见[当前报告](../../eval/2026-09-17-socialmem-grounded-answer.md)。

> **人物检索优化已验收（2026-09-17）**：C++人物路由与邻接完成开发及保留集验证，同一候选392/1031=38.02%，原baseline20.47%，累计+17.56百分点；保留集19.46%→39.93%。默认bm25保持，模型/评分不变，结构谓词能力另行验证；详见[当前报告](../../eval/2026-09-17-socialmem-source-focus.md)。历史结果按各自冻结版本解释。

# Hippocampus
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](../../eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

> **后续修复同步（2026-09-12）**：可空主题允许缺省或 null，无效类型统一在 C++ 预检；情绪校验不以“觉得/感觉”或整轮认知词直接拒绝。写入与检索共用原生契约。重复裁判一致率与有效分母单列，原严格门槛保持。实现范围及尚未完成的能力见 [中文优化设计](../../superpowers/specs/2026-09-12-socialmem-optimization-design.md)。

> **语义证据契约状态（2026-09-12）**：已实现并通过完整工程验证；真实诊断已完成并核验，质量门槛未通过，默认关闭，设计见 [Source-Grounded Claim Contract](../../superpowers/specs/2026-09-11-source-grounded-claim-contract-design.md)。Hippocampus 只缓冲带 Engram 引用的 VOLATILE Statement；按已确认契约保留确定性 clause_id、source time 和未决 event-time 状态，不从 utterance time 推断事件发生时间。

## 2026-09-11 语义证据契约

易失态 Statement 携带同一份可选 semantic_claim_json；巩固仅更新状态时保留原证据。Hippocampus 不重新解释范围，不把 `source_time` 转为事件起点；未知 event_time 保持 NULL。新命题经 derived_from 追溯父节点，不能复制直接准入证书。

实现状态与评测证据统一见 [同步清单](../claim_contract_sync.md)。

## 功能定义

Hippocampus 是快记忆子系统，承担 VOLATILE 状态 Statement 的写入缓冲、事件切分（EM-LLM 惊奇度阈值）、模式分离（反相似偏移 + MAY_OVERLAP_WITH 软边）、Working Set 渲染快照维护、Affect Buffer 优先级入队。它不做：长期语义存储（Neocortex 的事，见 [v24_07_neocortex.md](07_neocortex.md)）、检索路由（见 [v24_05_bus.md](05_bus.md)）、巩固决策（Replay Scheduler 的事，见 [v24_10_replay.md](10_replay.md)）。它是逻辑分区，由 `consolidation_state` 标签区分，非物理表迁移目标（见 [v24_04_substrate.md](04_substrate.md) §3 三层抽象）。

## 输入

- Bus 路由的 VOLATILE Statement（来自 statement.written 事件）
- EM-LLM 切分原始输入流（chunked Engram 内容）
- Working Set rebuild 请求（每回合对话触发）
- Affect Buffer 入队请求（高 salience 事件）

## 输出

- VOLATILE 分区持久化结果
- EpisodicEvent 边界（boundary_score 超阈值时切出新 episode）
- 模式分离结果（反相似偏移向量 + MAY_OVERLAP_WITH 软边）
- Working Set 快照（7 种 label 渲染产物，含 token 预算）
- Affect Buffer 优先级队列（供 Replay 采样）

## 主要流程

### 1. EM-LLM 事件切分

```
流式话语输入
  → LLM 在线计算 boundary_score = -log P(next | context)
  → boundary_score > θ_boundary
      → emit EpisodicEvent（含 boundary_score、episode_index、reference_time、statement_refs）
      → 继续积累下一段 context
```

- boundary_score 即负对数似然，反映当前话语相对上一段上下文的惊奇度。
- 跨阈值时刻即为 episode 边界，切出 EpisodicEvent 并写入 Episodes 分区。
- 该机制动机：LLM 的 parametric memory 擅长孤立事实，无法跨时间绑定相关 episodes（Episodic Knowledge Binding，OpenReview 2026），因此需外显 EpisodicEvent 与 episodic_link 结构。

### 2. 模式分离写入

```
新 Statement 到达
  → 查询 top-K 已有 Statement（余弦距离）
  → max_similarity > θ_sep ?
      是 → 反相似偏移：index_vector = orthogonalize(embedding, against=top_k_neighbors, strength=boost)
           → 建 MAY_OVERLAP_WITH 软边（记录 similarity 值），留巩固期再决策
      否 → index_vector = embedding（直接写）
```

- 默认保留细微差异，不做 UPDATE/NOOP（与 mem0 的根本区别）。
- MAY_OVERLAP_WITH 边由 Replay 巩固阶段决定是否合并或保留。

### 3. 模式补全（P2 引入，CA3 风格图游走）

```
partial cue 输入
  → vector_recall(cue, k=5) → seeds 集合（初始 activation=1.0）
  → 沿边类型（derived_from / evidence / OBSERVED_BY / SHARED_GROUND / MAY_OVERLAP_WITH）带权游走
  → 每步：next_act[target] += act[node] * edge_weight(kind) * decay
  → 合并 activation（取最大，不累加）
  → 终止条件：max(activation) < θ_propagate=0.05 OR 访问节点数 > 1000
  → 返回情节性子图（activation 最高的 K=20 个节点），超资源上限时标记 completion_truncated=true
```

- 返回情节性子图而非孤立 Statement。
- P1 不实现；P2 实现时上述资源边界作为单元测试约束。

### 4. Working Set 维护

```
每回合（per-turn）触发
  → 从 Persona（持久化结构）读取 self_model_anchor + traits
  → 从当前会话状态读取 interlocutor_persona / common_ground / pending_commitments
  → 按各 label 的 token_limit 截断
  → 渲染为 prompt block，注入本轮 LLM context
```

- 7 种 label 各有独立 token_limit 与 refresh_strategy。
- Working Set 是 view，Persona 是 model；前者跟 turn 走，后者由 Replay 周期更新（见 [v24_10_replay.md](10_replay.md)）。

### 5. Affect Buffer 入队

```
Statement 写入事件（statement.written）触发
  → salience > θ_buffer ?
      是 → 加入优先级队列（priority = salience）
           → 队列满？
               是 → 比较新 stmt.salience vs 队列最低 salience
                    → 新 > 最低：替换最低（被替换者仍留 Hippocampus VOLATILE，不丢）
                    → 新 <= 最低：丢弃（stmt 仍在 VOLATILE）
      否 → 不入 Buffer
```

- Buffer 只存引用，不存 stmt 副本。
- Replay Scheduler Online 模式优先从 Buffer 取；Idle/Sleep 模式从 Hippocampus 全分区采样（见 [v24_10_replay.md](10_replay.md)）。

## 核心算法

### 1. EM-LLM boundary_score

$$
\text{boundary\_score}(u_t) = -\log P(u_t \mid u_1, u_2, \ldots, u_{t-1})
$$

- $u_t$：第 $t$ 条话语（token 序列）。
- $P(\cdot \mid \text{context})$：LLM 在线推理的条件概率（token 级别 sum）。
- 超过阈值 $\theta_{\text{boundary}}$ 时切出 EpisodicEvent，boundary_score 直接赋给 `EpisodicEvent.boundary_score`。

### 2. 模式分离反相似偏移

设新 Statement 嵌入向量 $\mathbf{e}$，top-K 邻居集合 $\mathcal{N} = \{n_1, \ldots, n_K\}$，相似度上限 $\theta_{\text{sep}}$。

```
若 max_{n ∈ N} cos(e, n.embedding) > θ_sep：
    v_perp = e - Σ_i (e · n_i / ||n_i||²) * n_i   # Gram-Schmidt 正交化（多邻居版本）
    index_vector = normalize(e + strength * v_perp)
    对每个 n ∈ N：建 MAY_OVERLAP_WITH(new_stmt → n, similarity=cos(e, n.embedding))
否则：
    index_vector = e
```

- `orthogonalize(e, against=N, strength=s)`：将 $\mathbf{e}$ 沿各邻居方向去分量后加权叠回，使索引向量主动偏离邻居聚类（模拟 DG sparse coding）。
- `pattern_separation_boost`（即 strength）为可配置超参数。

### 3. CA3 风格图游走（pattern completion，P2）

```python
def pattern_completion(cue, budget=20):
    seeds = vector_recall(cue, k=5)
    activation = {s: 1.0 for s in seeds}
    visited = set(seeds)
    node_count = len(seeds)

    for step in range(budget):
        next_acts = {}
        for node, act in activation.items():
            for edge in node.edges:
                if edge.kind not in PROPAGATION_EDGE_TYPES:
                    continue
                w = edge_weight(edge.kind)
                contrib = act * w * decay
                if contrib < θ_propagate:
                    continue
                next_acts[edge.target] = max(
                    next_acts.get(edge.target, 0), contrib
                )
        # 合并（取最大，不累加）
        for node, act in next_acts.items():
            if node not in visited:
                node_count += 1
                visited.add(node)
            activation[node] = max(activation.get(node, 0), act)

        if node_count >= 1000:
            return _truncated_result(activation, K=20, truncated=True)
        if max(activation.values()) < θ_propagate:
            break

    return as_episodic_subgraph(activation, K=20)
```

- `PROPAGATION_EDGE_TYPES`：`{derived_from, evidence, OBSERVED_BY, SHARED_GROUND, MAY_OVERLAP_WITH}`。
- `θ_propagate = 0.05`（默认）；`decay` 为每步衰减系数。
- 资源上限：最多访问 1000 节点，超出时返回 top-K=20 + `completion_truncated=true`。

### 4. Affect Buffer 淘汰策略

```
容量 = C（可配置上限）
入队时：
    若 len(buffer) < C：直接 heappush(buffer, (-salience, stmt_ref))
    否则：
        min_salience_entry = heapmin(buffer)
        若 stmt.salience > min_salience_entry.salience：
            heapreplace(buffer, (-stmt.salience, stmt_ref))
            # 被替换者仍在 Hippocampus VOLATILE，不丢失
        否则：
            丢弃（stmt 仍在 VOLATILE）
```

- 优先级队列以 `-salience` 为 key（最小堆模拟最大堆）。
- 淘汰最低 salience，非最旧（区别于 FIFO 队列）。
- 借鉴 Anderson adaptive forgetting 机制。

## 数据结构

### EpisodicEvent

```python
@dataclass
class EpisodicEvent:
    episode_id: str                  # UUID
    boundary_score: float            # -log P(u_t | context)，切分阈值比较用
    episode_index: int               # 本会话内 episode 序号（单调递增）
    reference_time: datetime         # 事件发生时刻（ISO 8601）
    statement_refs: list[str]        # 指向 EngramStore 中 Statement 的 UUID 列表
    completion_truncated: bool = False  # pattern_completion 是否因资源上限截断
```

### WorkingSet（WorkingBlock 集合）

```python
@dataclass
class WorkingBlock:
    label: Literal[
        "self_persona",          # Persona.self_model_anchor + traits 的渲染
        "active_persona",        # 当前激活的角色/任务锚
        "current_goal",          # 当前会话目标
        "interlocutor_persona",  # 对话对象的推断模型
        "common_ground",         # 双方已确认的共享前提
        "norm_active",           # 激活中的规范/约束
        "pending_commitments",   # 尚未履行的承诺/行动项
    ]
    value: str                   # 渲染后的文本内容
    limit: int                   # token 上限（超出时截断）
    version: int                 # 乐观锁（并发写保护）
    refresh_strategy: Literal[
        "never",                 # 不自动刷新
        "per_turn",              # 每回合重建
        "per_session",           # 每会话重建
        "on_event",              # 触发事件时重建
    ]
```

- 7 种 label 中，`interlocutor_persona` / `common_ground` / `pending_commitments` 为 Starling 独有（主流开源系统无此三块）。
- Working Set 整体是 prompt 时刻的渲染快照（view），非持久化存储。

### AffectBufferEntry

```python
@dataclass
class AffectBufferEntry:
    priority: float              # = salience（越高越不被淘汰）
    stmt_ref: str                # EngramStore Statement UUID（只存引用）
    enqueued_at: datetime        # 入队时刻（调试用，不参与淘汰决策）

# 内部以最小堆维护（key = -priority）
# 容量上限：C（可配置）
```

### MAY_OVERLAP_WITH 边

```python
@dataclass
class MemoryEdge:
    kind: Literal["MAY_OVERLAP_WITH"]
    source_id: str               # Statement UUID（新写入的）
    target_id: str               # Statement UUID（已有邻居）
    similarity: float            # cos(source.embedding, target.embedding)，写入时刻计算
    created_at: datetime
    resolved: bool = False       # 巩固后置 True（Replay 决策合并或保留）
```

- 该边为软边，不阻止两端 Statement 独立存在。
- 巩固期（Replay）读取后更新 `resolved=True`，或删边并建 `DERIVED_FROM` 等强边。

上述 Python 示例为绑定层接口契约。核心实现为 C++ 抽象类，Python/JS/Rust 等绑定通过 pybind11 / NAPI / cxx 自动生成存根。

## 相关概念

### VOLATILE 状态

`consolidation_state = VOLATILE`：Statement 刚写入 Hippocampus，尚未经历 Replay 巩固。VOLATILE Statement 保留细粒度原始形式，包括模式分离偏移后的 index_vector。另一合法值为 `REPLAYING_CONSOLIDATING`（巩固进行中，见 [v24_10_replay.md](10_replay.md)）。

### EM-LLM 边界切分

利用 LLM 自身的条件概率计算话语惊奇度（负对数似然），无需外部分词器或固定窗口。边界由语义跳变驱动，天然对齐认知心理学的 event segmentation theory。

### 模式分离 vs 模式补全

| | 模式分离（Pattern Separation） | 模式补全（Pattern Completion） |
|---|---|---|
| 触发时机 | 写入时 | 检索时 |
| 目的 | 防止相似记忆混淆 | 从残缺线索恢复完整情节 |
| 生物对应 | 齿状回（DG）sparse coding | CA3 自联想回路 |
| 实现 | 反相似偏移 + MAY_OVERLAP_WITH | 图游走（Personalized PageRank 风格） |
| 阶段 | P1 实现 | P2 实现 |

### 反相似偏移

正交化（Gram-Schmidt）操作：将新 Statement 的嵌入向量沿已有邻居方向去分量，使索引向量主动偏离聚类中心。偏移强度由 `pattern_separation_boost` 控制。效果是索引空间更稀疏，减少错误召回，同时原始 embedding 不变（只有 index_vector 被修改）。

### Working Set vs Persona 的关系

- **Working Set**：每回合（per-turn）重建的 prompt 渲染快照，负责"此刻 LLM 需要看到什么"。跟 turn 走，token 数受 limit 约束，可频繁重建。
- **Persona**（见 [v24_07_neocortex.md](07_neocortex.md) §3.6）：持久化结构，跨会话稳定，跟 cognizer 走，由 Replay 周期更新。
- 关系：Working Set 是 view，Persona 是 model。`self_persona` block 是 `Persona.self_model_anchor + Persona.traits` 的渲染投影。

### Affect Buffer vs Replay 优先级队列的关系

| | Affect Buffer | Replay Scheduler 优先级队列 |
|---|---|---|
| 性质 | 入口缓冲（数据结构） | 调度决策队列 |
| 内容 | salience > θ_buffer 的 stmt 引用 | 多来源采样结果（Buffer + VOLATILE 全区） |
| 淘汰策略 | 最低 salience 被替换 | 由 Replay Scheduler 调度策略决定 |
| 位置 | Hippocampus 内部 | Replay 子系统（见 [v24_10_replay.md](10_replay.md)）|

Replay Scheduler 在 Online 模式优先消费 Affect Buffer；Idle/Sleep 模式从 Hippocampus 全分区采样。Buffer 满时被替换的 stmt 不丢失，仍留在 VOLATILE 区，只是不在快通道。

### Working Set 7 种 label 定义

| label | 内容 | 来源 | refresh_strategy |
|---|---|---|---|
| `self_persona` | Agent 自身身份、价值观、traits | Persona（持久化） | per_session 或 on_event |
| `active_persona` | 当前激活的角色或任务锚 | Persona + 任务上下文 | on_event |
| `current_goal` | 当前会话/任务的目标描述 | 会话状态 | per_turn |
| `interlocutor_persona` | 对话对象的推断模型（偏好、背景、立场） | 会话历史推断 | per_turn |
| `common_ground` | 双方已确认的共享前提与信念 | 会话历史推断 | per_turn |
| `norm_active` | 当前激活的规范、约束、协议 | 规范库 + 触发条件 | on_event |
| `pending_commitments` | 尚未履行的承诺、待办行动项 | 会话历史 + 任务追踪 | per_turn |

后三项（`interlocutor_persona` / `common_ground` / `pending_commitments`）为 Starling 独有，主流开源 memory 系统无此显式注入。

- 配置：所有 Adapter 与运行时配置采用 JSON 格式，统一 schema 见主文档 §2.0


## 来源时间与独立扩展标签（2026-09-12）

按已批准优化范围执行 [中文来源话轮设计](../../superpowers/specs/2026-09-12-source-turn-evaluation-design.md)。C++ 生成并解析版本化话轮，保留原始消息时间与 UTF-8 来源位置，正文与元数据分开校验；Bus/检索重建 source_turn 防止篡改。Python 仅映射和统计，独立扩展标签不进入模型输入，不修改原 P1 金标。真实时间不推断为事件时间或 UTC；已完成 C++ 实现、全量测试、离线与真实核验；真实诊断为 verified / complete_with_errors，质量门槛未通过。普通正文冒号保留完整语义，直接写入/回读使用共享严格解析器拒绝嵌套重复键。详见 [来源话轮评测报告](../../eval/2026-09-12-socialmem-source-turn.md)。


## 生成契约完整性同步（2026-09-12）

按 [中文生成契约设计](../../superpowers/specs/2026-09-12-claim-generation-design.md)，C++ 在抽取提示中明确对象、逐字主题、原始时间限定和字段类型约束，并提供与本次来源隔离的通用中英文参考示例。模型输出校验、准入、存储/检索与默认开关保持既有约束，Python 仅绑定和评测编排；参考示例不作为当前证据。本轮 C++ 实现、完整回归、离线核验及历史响应 140/140 一致性重放已完成；真实诊断于北京时间 2026-09-13 完成核验，为 `verified / complete_with_errors`。固定候选 59/64、synthetic 契约 13/16、独立对象 12/14、主题/联合各 1/14，原生技术失败 5；主题字面匹配分数不能解释为字段缺失。P1 兼容与逐例不退步门槛仍失败，Q1/Q9 结构化及链接组仍为 0/3，默认关闭。详见 [生成契约评测报告](../../eval/2026-09-12-socialmem-generation.md)。其他专项职责沿用设计同步清单，历史快照保持。

## 输出协议与偏好边界同步（2026-09-13）

按 [中文修复设计](../../superpowers/specs/2026-09-13-claim-protocol-boundary-design.md) 继续已批准优化：C++ 提示强调键唯一、时间原文及同话轮引用，准入与解析共用合法原因目录，窄范围拒绝把明确偏好对象写成 feels。真情绪不因同源其他偏好句被拒；Bus/回读复用共享契约，Python 仅绑定与编排。当前已完成 RED、C++ 实现与复审修复后的完整回归（C++ 1,062 项，Python 1,319 项通过/15 项跳过）；旧响应重解析 137/140 一致，3 条偏好误标候选提前拒绝。复合/因果情绪及被动 preferred 感受保留准入，句尾标点边界有正反例覆盖。独立复审发现均已关闭，最终离线 140 条/144 数据库核验通过；真实诊断已完成并由原生验证器核验为 `verified / complete_with_errors`：140 条重放、144 个数据库；固定候选 56/64（TP 30、TN 26、误收 0、误拒 1、技术失败 7），synthetic 冻结 11/16、契约 11/16（有效分母 15/16），P1 combined F1 为 holder 0.7317、holder/perspective 0.6829、predicate/object 0.7683；扩展标签 object/topic/scope/time/joint 为 12/14、2/14、12/14、12/14、2/14（有效目标 13）；Q1/Q9 的 baseline、structured、linked 均为 0/3，full 均为 3/3；实际证据链仍受入库与证据聚合限制。原生技术失败共 10 条，主要为重复 JSON 键和准入 JSON 后追加文本；无效裁判票 0。`promotion_ready=false`，生产默认保持关闭，不运行 1,031 题全量。默认、原标签、检索与历史归档保持。

## 声明范围与覆盖诊断职责（2026-09-15）

由 C++ 在行级来源校验时调用受限范围定位器，并在准入前保存原始行到候选索引。不能把旧 source unit 重新分句、重编号或按 topic 裁剪来源；完整 payload 继续进入准入。Python 只转发诊断。该职责已实施，当前结果以本地回归与派生重放为证。

详见[声明范围定位与生成覆盖诊断设计](../../superpowers/specs/2026-09-15-claim-scope-localization-design.md)。

## 2026-09-16 能力与得分路线修订（已授权自主迭代）

拟由 C++ 按会话/大小构造可追溯窗口，支持固定邻近上下文及跨窗口来源去重。写入不接收题目参考答案或锚点，保持 prepare→extract_all→commit_all 的真实持久化路径。 具体范围、测试与验收见[统一方案](../../superpowers/specs/2026-09-16-socialmem-capability-and-score-design.md)。本段描述计划，不代表已经实现或获得新分数。

最新执行顺序已按用户指令调整：先冻结当前默认 Starling 并完成全部 1031 题基线，再按真实失分执行中文文档→失败测试→C++ 改进→同条件复测，循环自主迭代，无需重复申请常规步骤授权。基线前仅补评测编排及题目允许来源范围，不预修被测能力。详见[基线优先执行计划](../../superpowers/plans/2026-09-16-socialmem-baseline-first.md)。


## R4.7 多声明与第一人称归属设计入口（2026-09-23）

R4.6 暴露了同一来源多条 claim 覆盖和第一人称信念无法进入归属车道的问题。R4.7 先保留全部通过证据校验的 claim，再按人物边界进入 C++ 归属车道；设计见 [2026-09-23-socialmem-r47-multi-claim-attribution-design.md](../../superpowers/specs/2026-09-23-socialmem-r47-multi-claim-attribution-design.md)，实施计划见 [2026-09-23-socialmem-r47-multi-claim-attribution.md](../../superpowers/plans/2026-09-23-socialmem-r47-multi-claim-attribution.md)。R4.7 当前只完成行为与离线验证，真实复评尚未封存，不提前宣称质量提升。

## R5.6 原生分批声明抽取补记（2026-09-25）

新增候选能力 `ValidationPolicy.claim_batch_size`：默认0保留原行为，1至32仅用于semantic claim，当前实验为8。C++用完整payload规划互斥的全局来源单元批，每批保留全部上下文；模型只能输出目标clause，原生在语义过滤前拒绝越界行。证据的原始字节坐标、来源hash及SourceTurn身份保持，不把批号写入声明身份。Python配置仅映射该字段；general_fact派生policy清零，episodic独立。

原生 `claim_extraction_batch_plan(payload, policy)` 给出计划与请求上界；分批回执保留全局attempt编号、batch_index、target_clause_ids和 `claim_batches_complete`。全部批成功才允许该holder分批claim写入；后批失败保留全部原始回执与成本，0条分批claim落库。持久化重新验证计划、policy与候选来源，批间写异常由事务回滚；跨分批大小重放保持幂等。完整上下文重复输入增加成本，有限来源单元不等于token硬上限。

本轮本地验证已通过，真实同输入验收与扩大评测尚待完成；不把测试结果当QA增益。完整设计与当前证据见[R5.6中文设计](../../superpowers/specs/2026-09-25-socialmem-r56-bounded-claim-design.md)，历史评测继续按各自冻结核心解释。
